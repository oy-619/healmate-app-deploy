import os
import time
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import openai
from langchain_community.vectorstores import Chroma

from langchain.schema import Document, HumanMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

# ------------------------------------------------------
# 変数定義
# ------------------------------------------------------
save_dir = r"C:\work\ws_python\GenerationAiCamp\HM\.db"


# OpenAI APIキーの確認と設定
def check_openai_api_key():
    """OpenAI APIキーの有効性を確認する"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error(
            "❌ OPENAI_API_KEYが設定されていません。.envファイルを確認してください。"
        )
        st.info("💡 .envファイルに以下の形式で設定してください：")
        st.code("OPENAI_API_KEY=sk-proj-...", language="text")
        st.stop()

    if not api_key.startswith(("sk-", "sk-proj-")):
        st.error("❌ 無効なAPIキー形式です。正しいOpenAI APIキーを設定してください。")
        st.info(f"現在設定されているキー: {api_key[:10]}...")
        st.stop()

    # APIキーを環境変数に明示的に設定
    os.environ["OPENAI_API_KEY"] = api_key

    # APIキーの状態表示（デバッグ用 - コメントアウト）
    # st.success(f"✅ OpenAI APIキーを確認しました: {api_key[:15]}...{api_key[-4:]}")

    # 追加の環境変数設定（念のため）
    openai.api_key = api_key

    return api_key


# APIキーの確認
api_key = check_openai_api_key()

# Embeddingsの初期化（APIキー確認後）
try:
    embeddings = OpenAIEmbeddings()
    # 接続テスト（簡単なテキストで確認）
    test_embedding = embeddings.embed_query("test")
    st.success("✅ OpenAI Embeddings接続成功")
except Exception as e:
    st.error(f"❌ OpenAI Embeddings初期化エラー: {str(e)}")
    if "401" in str(e) or "invalid_api_key" in str(e):
        st.error("🔑 APIキーが無効です。正しいAPIキーを設定してください。")
    elif "quota" in str(e).lower() or "billing" in str(e).lower():
        st.error("💰 APIクォータを超過しています。OpenAIアカウントを確認してください。")
    else:
        st.error("🌐 ネットワーク接続または一時的な問題の可能性があります。")
    st.stop()

# ------------------------------------------------------
# 関数定義
# ------------------------------------------------------


# 日付・時間でソートする関数
def parse_datetime(date_str, time_str):
    # 例: date_str = "2025/9/24(水)", time_str = "06:15既読"
    date_str = date_str.split("(")[0]  # "(水)"を除去
    time_str = time_str.replace("既読", "").strip()
    dt_str = f"{date_str} {time_str}"
    try:
        return datetime.strptime(dt_str, "%Y/%m/%d %H:%M")
    except Exception:
        return datetime.min  # パース失敗時は最小値


def is_db():
    if os.path.isdir(save_dir):
        # ディレクトリが存在する場合の処理
        return True
    return False


def get_all_messages():
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()

    # パートナーとのメッセージページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")

    # スクロールしながら情報を取得
    html_list = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        # ページ全体のHTMLを取得してリストに追加
        html = driver.page_source
        html_list.append(html)

        # スクロールアップ
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)  # 読み込み待ち

        # 新しい高さを取得
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # これ以上スクロールできない場合終了
        last_height = new_height

    driver.quit()

    # 最初のHTMLからパートナーのニックネームを取得
    partner_nickname = None
    if html_list:
        soup = BeautifulSoup(html_list[0], "html.parser")
        name_elements = soup.select_one("div.hover")
        if name_elements:
            partner_nickname = name_elements.get_text(strip=True)

    # HTMLリストから🍓さんのメッセージのみを抽出
    partner_messages = []
    for html in html_list:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("div#container")
        if not container:
            continue
        current_date = None
        for child in container.children:
            if child.name == "p" and "talkDate" in child.get("class", []):
                current_date = child.get_text(strip=True)
            elif child.name == "div" and current_date:
                time_tag = child.select_one("div.talkTime")
                msg_tag_partner = child.select_one("div.talkBalloonColor2")
                msg_time = time_tag.get_text(strip=True) if time_tag else ""

                # 🍓さんのメッセージのみを収集
                if msg_tag_partner:
                    msg = msg_tag_partner.get_text(strip=True)
                    partner_messages.append((current_date, msg_time, msg))

    # 重複排除
    unique_msgs = {(d[0], d[1], d[2]): d for d in partner_messages}
    partner_messages = list(unique_msgs.values())

    # 🍓さんのメッセージのみでDocumentを作成
    docs = [
        Document(
            page_content=f"{date} {msg_time} {msg}",
            metadata={
                "source": f"partner_msg_{i}",
                "id": f"partner_msg_{i}",
                "role": "partner",
                "date": date,
                "time": msg_time,
            },
        )
        for i, (date, msg_time, msg) in enumerate(partner_messages)
    ]

    return docs


def get_full_conversation_history():
    """🍓さんと男性の全会話履歴を取得する関数"""
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()

    # パートナーとのメッセージページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")

    # スクロールしながら全履歴を取得
    html_list = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        html = driver.page_source
        html_list.append(html)

        # スクロールアップ
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()

    # パートナーのニックネームを取得
    partner_nickname = None
    if html_list:
        soup = BeautifulSoup(html_list[0], "html.parser")
        name_elements = soup.select_one("div.hover")
        if name_elements:
            partner_nickname = name_elements.get_text(strip=True)

    # 全会話履歴を抽出（🍓さんと男性両方）
    all_messages = []
    for html in html_list:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("div#container")
        if not container:
            continue
        current_date = None
        for child in container.children:
            if child.name == "p" and "talkDate" in child.get("class", []):
                current_date = child.get_text(strip=True)
            elif child.name == "div" and current_date:
                time_tag = child.select_one("div.talkTime")
                msg_tag_self = child.select_one("div.talkBalloonColor1")
                msg_tag_partner = child.select_one("div.talkBalloonColor2")
                msg_time = time_tag.get_text(strip=True) if time_tag else ""

                if msg_tag_self:
                    msg = msg_tag_self.get_text(strip=True)
                    all_messages.append((current_date, msg_time, "self", msg))
                elif msg_tag_partner:
                    msg = msg_tag_partner.get_text(strip=True)
                    all_messages.append((current_date, msg_time, "partner", msg))

    # 重複排除
    unique_msgs = {(d[0], d[1], d[2], d[3]): d for d in all_messages}
    all_messages = list(unique_msgs.values())

    # Documentオブジェクトを作成
    docs = [
        Document(
            page_content=f"{date} {msg_time} [{role}] {msg}",
            metadata={
                "source": f"conversation_{i}",
                "id": f"conversation_{i}",
                "role": role,
                "date": date,
                "time": msg_time,
                "speaker": "男性" if role == "self" else partner_nickname,
            },
        )
        for i, (date, msg_time, role, msg) in enumerate(all_messages)
    ]

    return docs


def get_recent_conversation_context():
    """最新の会話の流れを取得して、自然な文脈を提供する"""
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()

    # パートナーとのメッセージページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")

    # 最新情報のみを取得するため、ページ最下部までスクロール
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "container"))
    )

    # ページ全体のHTMLを取得
    html = driver.page_source

    # ブラウザを閉じる
    driver.quit()

    # HTMLをパースして直近の会話履歴を取得
    soup = BeautifulSoup(html, "html.parser")
    name_elements = soup.select_one("div.hover")
    partner_nickname = name_elements.get_text(strip=True)

    container = soup.select_one("div#container")
    all_recent_messages = []
    current_date = None

    # 直近のメッセージを両方（男性・🍓さん）収集
    for child in container.children:
        if child.name == "p" and "talkDate" in child.get("class", []):
            current_date = child.get_text(strip=True)
        elif child.name == "div" and current_date:
            time_tag = child.select_one("div.talkTime")
            msg_tag_self = child.select_one("div.talkBalloonColor1")  # 男性のメッセージ
            msg_tag_partner = child.select_one("div.talkBalloonColor2")  # 🍓さんのメッセージ
            msg_time = time_tag.get_text(strip=True) if time_tag else ""

            # 男性のメッセージ
            if msg_tag_self:
                msg = msg_tag_self.get_text(strip=True)
                all_recent_messages.append(
                    (current_date, msg_time, "男性", msg)
                )

            # 🍓さんのメッセージ
            if msg_tag_partner:
                msg = msg_tag_partner.get_text(strip=True)
                all_recent_messages.append(
                    (current_date, msg_time, f"{partner_nickname}", msg)
                )

    # メッセージを日付と時間でソート（最新順）
    all_recent_messages_sorted = sorted(
        all_recent_messages, key=lambda x: parse_datetime(x[0], x[1]), reverse=True
    )

    # 直近5件の会話履歴を取得（文脈のため）
    recent_context = all_recent_messages_sorted[:5]
    
    # 最新のパートナーメッセージを特定
    latest_partner_msg = None
    latest_self_msg = None
    
    for msg in all_recent_messages_sorted:
        if msg[2] == partner_nickname and latest_partner_msg is None:
            latest_partner_msg = msg
        if msg[2] == "男性" and latest_self_msg is None:
            latest_self_msg = msg
        
        # 両方見つかったらループを抜ける
        if latest_partner_msg and latest_self_msg:
            break

    print(f"🍓{partner_nickname}さんの最新メッセージ:", latest_partner_msg)
    print(f"男性の最新メッセージ:", latest_self_msg)

    return {
        'partner_nickname': partner_nickname,
        'latest_partner_msg': latest_partner_msg,
        'latest_self_msg': latest_self_msg,
        'recent_context': recent_context
    }


def get_new_messages():
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()

    # パートナーとのメッセージページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")

    # 最新情報のみを取得するため、ページ最下部までスクロール
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "container"))
    )

    # ページ全体のHTMLを取得
    html = driver.page_source

    # ブラウザを閉じる
    driver.quit()

    # HTMLをパースして🍓さんの最新メッセージのみを抽出
    soup = BeautifulSoup(html, "html.parser")
    name_elements = soup.select_one("div.hover")
    partner_nickname = name_elements.get_text(strip=True)

    container = soup.select_one("div#container")
    partner_messages = []
    current_date = None

    # 🍓さんのメッセージのみを収集
    for child in container.children:
        if child.name == "p" and "talkDate" in child.get("class", []):
            current_date = child.get_text(strip=True)
        elif child.name == "div" and current_date:
            time_tag = child.select_one("div.talkTime")
            msg_tag_partner = child.select_one("div.talkBalloonColor2")
            msg_time = time_tag.get_text(strip=True) if time_tag else ""

            # 🍓さんのメッセージのみ収集
            if msg_tag_partner:
                msg = msg_tag_partner.get_text(strip=True)
                partner_messages.append(
                    (current_date, msg_time, f"【{partner_nickname}】", msg)
                )

    # 🍓さんのメッセージを日付と時間でソート（最新順）
    partner_messages_sorted = sorted(
        partner_messages, key=lambda x: parse_datetime(x[0], x[1]), reverse=True
    )

    # 最新メッセージの確認
    if partner_messages_sorted:
        print(f"🍓{partner_nickname}さんの最新メッセージ:", partner_messages_sorted[0])
        latest_partner_msg = partner_messages_sorted[0]
    else:
        print(f"🍓{partner_nickname}さんのメッセージが見つかりませんでした")
        latest_partner_msg = None

    return (
        None,  # self_docs（不要）
        latest_partner_msg,  # 🍓さんの最新メッセージのみ
        [],  # documents_sorted（不要）
        [],  # docs（不要）
        partner_nickname,
    )


def format_message(msg):
    """メッセージをそのまま返す（元の改行を保持）"""
    return msg.strip()


def safe_delete_db():
    """ChromaDBディレクトリを安全に削除する関数（Windowsファイルロック対応）"""
    import shutil
    import time
    import gc

    if not os.path.exists(save_dir):
        return True

    # 1. ガベージコレクションを実行してリソースを解放
    gc.collect()

    # 2. 通常の削除を複数回試行
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                st.info(f"削除を再試行しています... ({attempt + 1}/{max_attempts})")
                time.sleep(2)  # 待機時間を延長

            shutil.rmtree(save_dir)
            st.success("✅ 古いデータベースを削除しました")
            return True

        except PermissionError:
            if attempt == max_attempts - 1:
                # 3. 最終手段：PowerShellスクリプトでの削除
                return force_delete_with_powershell()
            else:
                continue
        except Exception as delete_error:
            if attempt == max_attempts - 1:
                st.error(f"❌ データベース削除に失敗しました: {str(delete_error)}")
                return force_delete_with_powershell()
            else:
                continue

    return False


def force_delete_with_powershell():
    """PowerShellを使用した強制削除"""
    import subprocess

    try:
        st.info("🔧 PowerShellを使用して強制削除を試みています...")

        # PowerShellスクリプト
        ps_command = f'Remove-Item -Path "{save_dir}" -Recurse -Force -ErrorAction SilentlyContinue; Start-Sleep 1'

        # PowerShellコマンド実行
        subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # 削除確認
        if not os.path.exists(save_dir):
            st.success("✅ PowerShellによる強制削除が成功しました")
            return True
        else:
            st.error("❌ PowerShellでも削除できませんでした")
            show_manual_deletion_guide()
            return False

    except Exception as ps_error:
        st.error(f"PowerShell削除でエラー: {str(ps_error)}")
        show_manual_deletion_guide()
        return False


def show_manual_deletion_guide():
    """手動削除の詳細ガイドを表示"""
    st.error("🚨 自動削除が失敗しました")

    with st.expander("📋 手動削除の詳細手順", expanded=True):
        st.markdown(
            """
        **以下の手順を順番に実行してください:**
        
        ### 🛑 1. アプリケーションを完全停止
        - このブラウザタブを**完全に閉じる**
        - ターミナルで `Ctrl + C` を押してアプリを停止
        
        ### 🔍 2. プロセス確認・終了
        - タスクマネージャーを開く（`Ctrl + Shift + Esc`）
        - 「詳細」タブで **python.exe** プロセスをすべて終了
        - **streamlit** 関連プロセスも終了
        
        ### 🗂️ 3. データベースフォルダを手動削除
        """
        )

        st.code(save_dir, language="text")

        st.markdown(
            """
        **削除方法:**
        - エクスプローラーで上記パスを開く
        - `.db` フォルダーを右クリック → 削除
        - 「別のプロセスが使用中」エラーが出る場合は**PCを再起動**
        
        ### 🚀 4. アプリケーション再起動
        ```bash
        streamlit run healmate_replymsg_strawberry.py
        ```
        
        ### ⚠️ それでも削除できない場合
        - **PC を再起動** してから手順3を実行
        - 管理者権限でコマンドプロンプトを開き:
        ```cmd
        rmdir /s /q "C:\\work\\ws_python\\GenerationAiCamp\\HM\\.db"
        ```
        """
        )


def safe_init_chromadb(force_recreate=False):
    """ChromaDBを安全に初期化する関数"""
    import warnings
    import gc

    # LangChain の非推奨警告を抑制
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    if force_recreate:
        st.info("🔄 データベースを強制的に再作成しています...")

    # 強制再作成が指定された場合、または既存DBでエラーが発生した場合
    if force_recreate and os.path.exists(save_dir):
        if not safe_delete_db():
            return None

    try:
        if not is_db():
            # DBがなければ初回のみ作成
            st.info("データベースを初期化中...")
            with st.spinner("メッセージ履歴を取得中..."):
                documents = get_all_messages()
                if not documents:
                    st.warning("メッセージが取得できませんでした。")
                    return None

                db = Chroma.from_documents(
                    documents, embedding=embeddings, persist_directory=save_dir
                )
                db.persist()
            st.success("データベースを作成しました")
            return db
        else:
            # 既存DBを読み込み
            db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

            # データベースの簡単な動作確認
            try:
                # 小さなテストクエリでDBの動作を確認
                test_retriever = db.as_retriever(search_kwargs={"k": 1})
                test_retriever.invoke("テスト")
                return db
            except Exception as test_error:
                st.warning(f"既存データベースに問題があります: {str(test_error)}")
                # ChromaDBのインスタンスを明示的に削除
                del db
                gc.collect()
                # 再帰的に再作成を試みる
                return safe_init_chromadb(force_recreate=True)

    except Exception as db_error:
        st.error(f"データベースエラー: {str(db_error)}")

        # まだ再作成を試していない場合は試す
        if not force_recreate:
            st.info("データベースを再作成しています...")
            return safe_init_chromadb(force_recreate=True)
        else:
            st.error("⚠️ データベース初期化に失敗しました")
            st.error("⚠️ データベース初期化に失敗しました")

            with st.expander("🔧 手動解決方法", expanded=True):
                st.markdown(
                    """
                **以下の手順を順番に実行してください:**
                
                1. **サイドバーの「データベースをリセット」ボタンを試す**
                
                2. **それでも解決しない場合:**
                   - ブラウザのこのタブを閉じる
                   - ターミナルで `Ctrl+C` を押してアプリを完全停止
                   - 以下のフォルダを手動削除:
                """
                )
                st.code(save_dir, language="text")
                st.markdown(
                    """
                   - `streamlit run healmate_replymsg_strawberry.py` で再起動
                
                3. **Windowsでファイルが削除できない場合:**
                   - タスクマネージャーでPythonプロセスをすべて終了
                   - PCを再起動してから手順2を実行
                """
                )
            return None


def main():
    # ------------------------------------------------------
    # セッション状態の初期化
    # ------------------------------------------------------
    
    # 結果を保持するセッション状態を初期化
    if 'message_result' not in st.session_state:
        st.session_state.message_result = None
    if 'personality_result' not in st.session_state:
        st.session_state.personality_result = None
    if 'wishlist_result' not in st.session_state:
        st.session_state.wishlist_result = None
    if 'wishlist_line_text' not in st.session_state:
        st.session_state.wishlist_line_text = None
        
    # ------------------------------------------------------
    # メッセージ情報取得処理
    # ------------------------------------------------------

    # 最新の会話コンテキストを取得
    try:
        # 新しい会話コンテキスト取得関数を使用
        conversation_context = get_recent_conversation_context()
        partner_nickname = conversation_context['partner_nickname']
        partner_docs = conversation_context['latest_partner_msg']
        self_docs = conversation_context['latest_self_msg']
        recent_context = conversation_context['recent_context']

        # メッセージが取得できない場合のチェック
        if partner_docs is None:
            st.error("パートナーのメッセージが取得できませんでした。")
            st.stop()

        if self_docs is None:
            st.warning("自分のメッセージが取得できませんでした。")

    except Exception as e:
        st.error(f"メッセージの取得中にエラーが発生しました: {str(e)}")
        st.stop()

    # ------------------------------------------------------
    # Streamlitアプリ
    # ------------------------------------------------------

    # サイドバーにリセット機能を追加
    with st.sidebar:
        st.header("⚙️ システム管理")

        if st.button(
            "🔄 データベースをリセット", help="データベースエラーが発生した場合に使用"
        ):
            with st.spinner("データベースをリセット中..."):
                try:
                    # 既存のDBを削除
                    delete_success = safe_delete_db()

                    if delete_success:
                        st.success("✅ 既存データベースを削除しました")

                        # 少し待ってから新しいDBを作成
                        import time

                        time.sleep(1)

                        # 新しいDBを作成
                        new_db = safe_init_chromadb(force_recreate=True)
                        if new_db:
                            st.success("✅ 新しいデータベースを作成しました")
                            st.info("🔄 ページをリロードしてください（F5キー）")
                        else:
                            st.error("❌ データベース作成に失敗しました")
                    else:
                        st.warning("⚠️ 自動削除に失敗しました。手動削除が必要です。")

                except Exception as e:
                    st.error(f"リセット中にエラーが発生しました: {str(e)}")
                    show_manual_deletion_guide()

        if st.button("🚨 緊急リセット", help="強制的にデータベースをクリアして再起動"):
            st.error("⚠️ 緊急リセットモード")
            show_manual_deletion_guide()

        if st.button(
            "🧹 アプリケーションを再起動", help="完全にアプリケーションを再起動"
        ):
            st.info("📋 再起動手順:")
            st.markdown(
                """
            1. **ブラウザのこのタブを閉じる**
            2. **ターミナルでCtrl+Cを押してアプリを停止**
            3. **再度 `streamlit run` コマンドで起動**
            """
            )

    st.title(f"{partner_nickname}さんへの返信メッセージ自動生成アプリ")
    st.divider()
    st.subheader("最新メッセージ")

    # partner_docsは (date, msg_time, role, msg)
    date, msg_time, role, msg = partner_docs
    msg_formatted = format_message(msg)

    # Streamlitで見やすく表示
    st.markdown(
        f"""
    **日付**: {date}  
    **時間**: {msg_time}  
    **送信者**: {role}  
    **メッセージ**:
    {msg_formatted}
    """
    )
    st.divider()

    label_text = f"今日の出来事や{partner_nickname}さんからの最新メッセージに対する思いを入力してください。"
    today_txt = st.text_area(label=label_text)

    # ボタンを横並びで配置
    col1, col2, col3 = st.columns(3)

    with col1:
        generate_message = st.button("💬 メッセージ生成", use_container_width=True)

    with col2:
        analyze_personality = st.button("🧠 人格分析", use_container_width=True)

    with col3:
        create_wishlist = st.button("� やりたいことリスト", use_container_width=True)

    if generate_message:
        # ユーザー入力のチェック
        if not today_txt or today_txt.strip() == "":
            st.error("メッセージを生成するには、今日の出来事や思いを入力してください。")
        else:
            with st.spinner("💬 メッセージを生成中..."):
                # 全会話履歴を取得（メッセージ生成には全履歴が必要）
                all_conversation_docs = get_full_conversation_history()
                
                if not all_conversation_docs:
                    st.error("会話履歴が見つかりませんでした。")
                    st.stop()
                
                db = Chroma.from_documents(all_conversation_docs, embedding=embeddings)
                db.persist()
                retriever = db.as_retriever()

                # 手順1〜3の処理を実現するにあたり、LLMへのリクエストは以下の2回行われる。
                # 1.会話履歴がなくても理解できる、独立した入力を生成するためのLLMリクエスト
                # 2.生成された入力内容と関連ドキュメントを渡して、最終的な回答を生成するためのLLMリクエスト
                # ここでは「1. 会話履歴がなくても理解できる、独立した入力を生成するためのLLMリクエスト」を行うための、専用のプロンプトを用意。
                question_generator_template = (
                    "会話履歴と最新の入力をもとに、"
                    "会話履歴なしでも理解できる独立した入力テキストを生成してください。"
                )

                # ChatPromptTemplateでは、LLMの振る舞いを制御するシステムメッセージとユーザーメッセージ、
                # また会話履歴を差し込むためのプレースホルダーを用意している。
                # システムメッセージとユーザーメッセージは、このように省略した書き方が可能。
                question_generator_prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", question_generator_template),
                        MessagesPlaceholder("chat_history"),
                        ("human", "{input}"),
                    ]
                )

                # 呼び出すLLMのインスタンスを用意。
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

                # 呼び出すLLMと、ベクターストア検索のためのRetriever、
                # また独立した入力生成用のプロンプトを渡すことで
                # 「create_history_aware_retriever」のインスタンスを生成。
                # Retrieverには、「Retrievers」の前パートで作成したインスタンス
                # (retriever = db.as_retriever())を使う。
                # これで、手順1と2を実行する準備が完了。
                history_aware_retriever = create_history_aware_retriever(
                    llm, retriever, question_generator_prompt
                )

                # 会話履歴なしでも理解できる独立した入力内容と、
                # ベクターストアから取得した関連ドキュメントをもとに
                # LLMから回答を得るためのプロンプトを用意。
                # 「{context}」の箇所に関連ドキュメントが埋め込まれる。
                # このプロンプトを使うことで、入力内容に対して会話履歴を踏まえた回答を得られる。
                question_answer_template = """
                あなたは優秀な質問応答アシスタントです。以下のcontextを使用して質問に答えてください。
                また答えが分からない場合は、無理に答えようとせず「分からない」という旨を答えてください。"
                {context}
                """
                question_answer_prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", question_answer_template),
                        MessagesPlaceholder("chat_history"),
                        ("human", "{input}"),
                    ]
                )

                # 呼び出すLLMとプロンプトを引数として渡し
                # 「create_stuff_documents_chain」のインスタンスを生成。
                # このインスタンスの機能を使うことで、会話履歴なしでも理解できる
                # 独立した入力内容と取得した関連ドキュメントをもとに、LLMに回答を生成させることができる。
                question_answer_chain = create_stuff_documents_chain(
                    llm, question_answer_prompt
                )

                # 引数には、先ほど作成した「create_history_aware_retriever」のインスタンスと、
                # 「create_stuff_documents_chain」のインスタンスを渡す。
                # 後ほど、この「create_retrieval_chain」のインスタンスが持つ「invoke()」メソッドに
                # 「入力内容」と「会話履歴」の2つのデータを渡すことで、独立した入力内容の生成と
                # 関連ドキュメントの取得、最終的なLLMからの回答生成を内部的に一括で行える。
                rag_chain = create_retrieval_chain(
                    history_aware_retriever, question_answer_chain
                )

                # LLM呼び出しを行う前に、会話履歴を保持するためのデータの入れ物を用意。
                # 2回目以降のLLM呼び出しでは、入力内容と会話履歴をもとに、
                # 会話履歴なしでもLLMが理解できる「独立した入力内容」を生成する。
                # そのため入力内容とLLMからの回答内容は、LLM呼び出しのたびに
                # 会話履歴として保存していく必要がある。
                chat_history = []

                # 直近の会話履歴から文脈を作成
                recent_conversation = ""
                if recent_context:
                    recent_conversation = "# 直近の会話の流れ（時系列順）\n"
                    # 古い順に並び替えて会話の流れを表示
                    sorted_context = sorted(recent_context, 
                                          key=lambda x: parse_datetime(x[0], x[1]))
                    for i, (date, msg_time, speaker, msg) in enumerate(sorted_context):
                        recent_conversation += f"{i+1}. [{speaker}] {msg}\n"
                
                query = f"""
        # 役割
        あなたは恋愛心理カウンセラーです。女性からのメッセージに対して、魅力的で自然な返信メッセージを作成することが得意です。

        # 文脈
        - 男性と{partner_nickname}は、1カ月前にマッチングしていて、メッセージをやり取りしている。
        - 男性は{partner_nickname}に好意を持っていて、真剣に交際を考えている。
        - 男性の年齢: 51歳
        - 以下の会話の流れを踏まえて、自然で違和感のない返信を作成する必要がある。

        {recent_conversation}

        # 重要な指示
        - 上記の会話の流れを必ず把握し、話の続きとして自然になるように返信してください。
        - {partner_nickname}の最新メッセージに対する直接的な反応・応答を含めること。
        - 男性の前回のメッセージとのつながりを意識して、会話が不自然に途切れないようにする。
        - 話題の変更がある場合は、自然な移行を心がける。
        - 相手が質問している場合は、必ずその質問に答える。
        - 相手が感情を表現している場合は、それに共感や理解を示す。

        # メッセージ作成の基本方針
        - 現在の時刻に合わせた挨拶を文頭にいれること。
        - {partner_nickname}の最新メッセージの内容を細かく反映すること。
        - ニックネーム（{partner_nickname}）を適切に使用すること。
        - 男性側の思いを自然に反映すること。
        - 生成するメッセージには「とのこと」の言葉は使用しないこと。
        - スマートでフレンドリーかつ、自然な文体にすること（軽すぎず、堅すぎず）
        - 優しい言葉遣いをベースに、知的、ユーモア、冗談をバランスよく含めること。
        - 長文になりすぎず、10～20文程度で簡潔にまとめること。
        - 文の内容にあった絵文字を適度に入れること。
        - 自身のことを「自分」または「俺」という一人称で表現すること。
        - 語尾に力を入れすぎず、柔らかく表現すること。
        - 語尾に適度な抑揚をつけること。
        - ゆっくりと語尾を伸ばして、親しみやすさや柔らかい印象を与えること。
        - 禁止事項：下品な表現、即会い目的と感じる文言。

        # 出力指示
        - テキストのみ
        - 句読点で適度に改行し、読みやすくすること。
        - パターンを**3種類（知的で落ち着き／甘めでドキッとする／短文クール）**で提示

        # {partner_nickname}の最新メッセージ
        {partner_docs[3] if partner_docs and len(partner_docs) > 3 else "メッセージが見つかりませんでした"}

        # 男性の最新メッセージ
        {self_docs[3] if self_docs and len(self_docs) > 3 else "メッセージが見つかりませんでした"}

        # 男性側の思い
        {today_txt}
        """



                ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
                # セッション状態に結果を保存
                st.session_state.message_result = ai_msg['answer']
                chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])
                print(
                    f"\n\n==================生成メッセージ=================="
                    f"\n{ai_msg['answer']}\n\n"
                )

    # これまでのメッセージ履歴からわかる人間性を分析する処理
    elif analyze_personality:
        st.divider()
        st.write(
            f"🍓{partner_nickname}さんの全メッセージ履歴からわかる人間性を分析しました。"
        )

        # 全メッセージ履歴を取得
        with st.spinner("全メッセージ履歴を取得中..."):
            all_documents = get_all_messages()

        if not all_documents:
            st.error("メッセージ履歴が見つかりませんでした。")
            st.stop()

        # 🍓さんのメッセージのみを抽出
        partner_messages = [
            doc for doc in all_documents if doc.metadata.get("role") == "partner"
        ]

        if not partner_messages:
            st.error(f"🍓{partner_nickname}さんのメッセージが見つかりませんでした。")
            st.stop()

        st.info(
            f"分析対象: 🍓{partner_nickname}さんのメッセージ {len(partner_messages)}件"
        )

        # ChromaDBを安全に初期化
        db = safe_init_chromadb()

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 🍓さんの全メッセージをデータベースに追加
        try:
            db.add_documents(partner_messages)
            db.persist()
        except Exception as add_error:
            st.warning(f"メッセージの追加中にエラーが発生しました: {str(add_error)}")
            # エラーが発生しても処理を続行

        # DBからRetrieverを作成（検索結果数を増やして全体的な分析を可能にする）
        retriever = db.as_retriever(search_kwargs={"k": 20})

        query = f"""
        あなたは優秀な心理カウンセラーです。
        🍓{partner_nickname}さんの**これまでの全メッセージ履歴**を総合的に分析し、
        人間性・性格・価値観・コミュニケーションの特徴を詳細に分析してください。

        【重要】分析は蓄積された全メッセージを基に行い、時系列的な変化や一貫性も考慮してください。

        【分析項目】
        ## 1. 🌟 基本的な性格・人柄
        - 思いやり、誠実さ、ユーモア、知性、積極性、控えめさなどの特徴
        - 行動パターンや感情表現の傾向
        - メッセージから読み取れる価値観や人生観
        
        ## 2. 🎨 趣味・嗜好・ライフスタイル  
        - 好きな食べ物、料理、お酒、カフェなどのグルメ嗜好
        - 趣味や娯楽（映画、音楽、読書、アニメ、ゲームなど）
        - 休日の過ごし方や旅行への興味
        - 仕事や学業に対する姿勢・キャリア志向
        - ファッションや美容への関心
        - 運動やスポーツへの取り組み
        
        ## 3. 💬 コミュニケーションスタイル
        - メッセージの特徴（長さ、頻度、絵文字使用など）
        - 感情表現の仕方（嬉しい時、困った時、怒った時など）
        - 質問への答え方や会話の進め方
        - 相手への気遣いや配慮の表れ方
        
        ## 4. 💕 恋愛観・関係性への姿勢
        - 男性への好意や関心を示すメッセージの具体例
        - デートや会うことへの反応
        - 関係性の発展に対する期待や願望
        - 恋愛における価値観や理想像
        
        ## 5. 📈 時系列的変化・成長
        - メッセージの内容や態度の変化
        - 関係性の深まりに伴う変化
        - 新しい側面の発見や成長の兆し
        
        ## 6. ✨ 総合評価・魅力ポイント
        - {partner_nickname}さんの最大の魅力や特徴
        - 恋愛パートナーとしての相性や可能性
        - 今後の関係発展への提案

        【出力要件】
        - 各項目で必ず具体的なメッセージ内容を引用すること
        - 「メッセージ例：」として実際の発言を明記
        - 判断が困難な場合は「情報不足のため判断困難」と記載
        - 客観的で建設的な分析を心がける
        - {partner_nickname}さんの人格を尊重した表現を使用
        """

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

        # 新しいRAG chainの作成
        prompt_template = ChatPromptTemplate.from_template(
            "コンテキスト: {context}\n\n質問: {input}\n\n回答:"
        )
        document_chain = create_stuff_documents_chain(llm, prompt_template)
        rag_chain = create_retrieval_chain(retriever, document_chain)

        with st.spinner("🧠 人格分析中..."):
            result = rag_chain.invoke({"input": query})
            # セッション状態に結果を保存
            st.session_state.personality_result = result['answer']

    # 二人のやりたいことリストを作成する処理
    elif create_wishlist:
        st.divider()
        st.write(
            f"🍓{partner_nickname}さんと二人の全会話履歴から、やりたいことリストを作成しました。"
        )

        # 全メッセージ履歴を取得（🍓さんと男性両方）
        with st.spinner("全会話履歴を取得中..."):
            all_conversation = get_full_conversation_history()

        if not all_conversation:
            st.error("会話履歴が見つかりませんでした。")
            st.stop()

        st.info(f"分析対象: 全会話履歴 {len(all_conversation)}件のメッセージ")

        # ChromaDBを安全に初期化
        db = safe_init_chromadb()

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 全会話履歴をデータベースに追加
        try:
            db.add_documents(all_conversation)
            db.persist()
        except Exception as add_error:
            st.warning(f"会話履歴の追加中にエラーが発生しました: {str(add_error)}")
            # エラーが発生しても処理を続行

        # DBからRetrieverを作成（より多くの関連会話を検索）
        retriever = db.as_retriever(search_kwargs={"k": 30})

        query = f"""
        あなたは優秀な恋愛コンサルタントです。
        以下のメッセージ履歴から、{partner_nickname}さんと男性が**二人で一緒に**やりたいと思っていることや、
        興味を示していることを抽出して、具体的な「二人のやりたいことリスト」を作成してください。

        # 抽出対象（二人で行う事項に限定）
        - 一緒に行きたい場所や旅行先
        - 二人で食べに行きたい料理やレストラン
        - カップルで体験したいアクティビティやデート
        - 一緒に学びたいスキルや趣味
        - 二人で参加したいイベントや体験
        - カップルで楽しみたい娯楽や遊び
        - 一緒に達成したい目標や夢
        - 二人の関係で改善・発展させたいこと
        - パートナーとしてチャレンジしたいこと
        - 将来二人で実現したい生活スタイル

        # 出力形式
        ## 💕 {partner_nickname}さんと二人で叶えたいリスト

        ### 🌍 一緒に行きたい場所・旅行
        - [ ] 具体的なデートスポットや旅行先（根拠となるメッセージ内容も記載）

        ### 🍽️ 二人で楽しみたいグルメ
        - [ ] 一緒に行きたいレストランや食べたい料理（根拠となるメッセージ内容も記載）

        ### 🎯 カップルで体験したいアクティビティ
        - [ ] 二人で楽しめる趣味や活動（根拠となるメッセージ内容も記載）

        ### 🎪 一緒に参加したいイベント・体験
        - [ ] 二人で参加したいイベントや特別な体験（根拠となるメッセージ内容も記載）

        ### � 二人の関係で実現したいこと
        - [ ] 関係性の発展や共通の目標（根拠となるメッセージ内容も記載）

        ### ✨ 将来二人で叶えたい夢
        - [ ] 長期的な二人の目標や理想（根拠となるメッセージ内容も記載）

        # 注意事項
        - **必ず二人で行う事項のみ**を抽出すること（個人的な目標は除外）
        - 推測ではなく、実際のメッセージ内容に基づいて抽出すること
        - デートやカップル活動として実現可能なアクションとして表現すること
        - チェックボックス形式で、実行可能なリストとして作成すること
        - 各項目には根拠となるメッセージの引用や説明を含めること
        - 「一緒に」「二人で」といった表現を意識すること
        - 情報が不足している場合は「メッセージからは二人での具体的な希望が確認できませんでした」と記載
        """

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

        # 新しいRAG chainの作成
        prompt_template = ChatPromptTemplate.from_template(
            "コンテキスト: {context}\n\n質問: {input}\n\n回答:"
        )
        document_chain = create_stuff_documents_chain(llm, prompt_template)
        rag_chain = create_retrieval_chain(retriever, document_chain)

        with st.spinner("💕 やりたいことリスト作成中..."):
            result = rag_chain.invoke({"input": query})
            # セッション状態に結果を保存
            st.session_state.wishlist_result = result["answer"]

        # LINEでコピペしやすい形式に変換
        def convert_to_line_format(markdown_text):
            """MarkdownテキストをLINE用のプレーンテキストに変換"""
            import re
            
            # Markdownの変換処理
            text = markdown_text
            
            # ## 見出し → 絵文字付き見出し
            text = re.sub(r'^## (.+)$', r'✨\1✨', text, flags=re.MULTILINE)
            
            # ### 見出し → 絵文字のみ保持
            text = re.sub(r'^### (.+)$', r'\1', text, flags=re.MULTILINE)
            
            # チェックボックス変換
            text = re.sub(r'- \[ \] ', r'◯ ', text)
            text = re.sub(r'- \[x\] ', r'✅ ', text)
            
            # **太字** → そのまま
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            
            # 空行の整理（3行以上の空行を2行に）
            text = re.sub(r'\n\n\n+', r'\n\n', text)
            
            # 先頭と末尾の空行を削除
            text = text.strip()
            
            return text

        # 元のMarkdownテキスト
        original_text = result["answer"]
        
        # LINE用テキストに変換
        line_text = convert_to_line_format(original_text)
        
        # ダウンロード用データの準備
        # UTF-8 BOM付きエンコーディングで文字化けを防止（Windows対応）
        
        # 元のMarkdownテキスト用
        original_data = "\ufeff" + original_text
        original_bytes = original_data.encode("utf-8")
        
        # LINE用テキスト用  
        line_data = "\ufeff" + line_text
        line_bytes = line_data.encode("utf-8")

        # ダウンロードボタンを2つ提供（LINE用とMarkdown用）
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            st.download_button(
                label="� LINE用テキスト",
                data=line_bytes,
                file_name=(
                    f"{partner_nickname}_やりたいことリスト_LINE用_"
                    f"{datetime.now().strftime('%Y%m%d')}.txt"
                ),
                mime="text/plain; charset=utf-8",
                use_container_width=True,
                help="LINEでコピペしやすい形式のテキストファイル"
            )

        with col_dl2:
            st.download_button(
                label="� Markdown形式",
                data=original_bytes,
                file_name=(
                    f"{partner_nickname}_やりたいことリスト_"
                    f"{datetime.now().strftime('%Y%m%d')}.txt"
                ),
                mime="text/plain; charset=utf-8",
                use_container_width=True,
                help="元のMarkdown形式のテキストファイル"
            )

    # ------------------------------------------------------
    # 保存された結果の表示（常に表示）
    # ------------------------------------------------------
    
    # メッセージ生成結果の表示
    if st.session_state.message_result:
        st.divider()
        st.subheader("💬 生成されたメッセージ")
        st.write(st.session_state.message_result)
        
        # クリアボタン
        if st.button("🗑️ メッセージをクリア", key="clear_message"):
            st.session_state.message_result = None
            st.rerun()
    
    # 人格分析結果の表示
    if st.session_state.personality_result:
        st.divider()
        st.subheader("🧠 人格分析結果")
        st.markdown(st.session_state.personality_result)
        
        # クリアボタン
        if st.button("🗑️ 人格分析をクリア", key="clear_personality"):
            st.session_state.personality_result = None
            st.rerun()
    
    # やりたいことリスト結果の表示
    if st.session_state.wishlist_result:
        st.divider()
        st.subheader("💕 やりたいことリスト")
        st.markdown(st.session_state.wishlist_result)
        
        # LINE用プレビュー
        st.subheader("📱 LINE用プレビュー")
        st.info("以下のテキストはLINEでコピペしやすい形式です")
        
        # LINE用テキスト変換（同じロジック）
        def convert_to_line_format_display(markdown_text):
            import re
            text = markdown_text
            text = re.sub(r'^## (.+)$', r'✨\1✨', text, flags=re.MULTILINE)
            text = re.sub(r'^### (.+)$', r'\1', text, flags=re.MULTILINE)
            text = re.sub(r'- \[ \] ', r'◯ ', text)
            text = re.sub(r'- \[x\] ', r'✅ ', text)
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\n\n\n+', r'\n\n', text)
            return text.strip()
        
        line_text_display = convert_to_line_format_display(st.session_state.wishlist_result)
        st.text(line_text_display)
        
        # ダウンロードボタン（簡単版）
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        with col_dl1:
            # LINE用テキストダウンロード
            line_data = "\ufeff" + line_text_display
            st.download_button(
                label="📱 LINE用DL",
                data=line_data.encode("utf-8"),
                file_name=f"{partner_nickname}_LINE用_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8"
            )
        
        with col_dl2:
            # Markdown形式ダウンロード  
            markdown_data = "\ufeff" + st.session_state.wishlist_result
            st.download_button(
                label="📄 Markdown DL",
                data=markdown_data.encode("utf-8"),
                file_name=f"{partner_nickname}_やりたいこと_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8"
            )
            
        with col_dl3:
            # クリアボタン
            if st.button("🗑️ リストをクリア", key="clear_wishlist"):
                st.session_state.wishlist_result = None
                st.session_state.wishlist_line_text = None
                st.rerun()


if __name__ == "__main__":
    main()
