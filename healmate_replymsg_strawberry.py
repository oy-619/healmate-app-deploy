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
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.schema import Document, HumanMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

# ------------------------------------------------------
# 変数定義
# ------------------------------------------------------
save_dir = r"C:\work\ws_python\GenerationAiCamp\HM\.db"

# Embeddingsの初期化
embeddings = OpenAIEmbeddings()

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
    all_documents = []
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

    # HTMLリストから情報を抽出してChromaに蓄積
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
                if msg_tag_partner:
                    msg = msg_tag_partner.get_text(strip=True)
                    all_documents.append((current_date, msg_time, msg))
    # ...既存コード...

    # 重複排除（必要なら）
    unique_docs = {(d[0], d[1], d[2]): d for d in all_documents}
    all_documents = list(unique_docs.values())

    docs = [
        Document(
            page_content=f"{date} {msg_time} {msg}",
            metadata={"source": f"doc_{i}", "id": f"doc_{i}"},
        )
        for i, (date, msg_time, msg) in enumerate(all_documents)
    ]

    return docs


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

    # HTMLをパースして必要な情報を抽出
    soup = BeautifulSoup(html, "html.parser")
    name_elements = soup.select_one("div.hover")
    partner_nickname = name_elements.get_text(strip=True)

    container = soup.select_one("div#container")
    documents = []
    self_docs = []
    partner_docs = []
    current_date = None

    # 会話履歴の各要素をループ処理
    for child in container.children:
        # 日付の要素とメッセージの要素を判別して処理
        if child.name == "p" and "talkDate" in child.get("class", []):
            # 日付を記憶
            current_date = child.get_text(strip=True)
        # メッセージの要素
        elif child.name == "div" and current_date:
            # 時間とメッセージを抽出
            time_tag = child.select_one("div.talkTime")
            msg_tag_self = child.select_one("div.talkBalloonColor1")
            msg_tag_partner = child.select_one("div.talkBalloonColor2")
            msg_time = time_tag.get_text(strip=True) if time_tag else ""
            if msg_tag_self:
                msg = msg_tag_self.get_text(strip=True)
                self_docs.append((current_date, msg_time, "【男性】", msg))
            elif msg_tag_partner:
                msg = msg_tag_partner.get_text(strip=True)
                partner_docs.append(
                    (current_date, msg_time, f"【{partner_nickname}】", msg)
                )

    # 日付と時間でソート
    self_docs_sorted = sorted(
        self_docs, key=lambda x: parse_datetime(x[0], x[1]), reverse=True  # 最新順
    )
    if self_docs_sorted:
        print("自分の最新メッセージ:", self_docs_sorted[0])
    else:
        print("自分のメッセージが見つかりませんでした")

    # 日付と時間でソート
    partner_docs_sorted = sorted(
        partner_docs, key=lambda x: parse_datetime(x[0], x[1]), reverse=True  # 最新順
    )
    if partner_docs_sorted:
        print("パートナーの最新メッセージ:", partner_docs_sorted[0])
    else:
        print("パートナーのメッセージが見つかりませんでした")

    # 全てのメッセージをまとめる
    documents = self_docs + partner_docs

    # 日付と時間でソート
    documents_sorted = sorted(
        documents, key=lambda x: parse_datetime(x[0], x[1]), reverse=True  # 最新順
    )

    # for date, time, role, msg in documents_sorted:
    #   print(f"{date} {time} [{role}] {msg}")

    docs = [
        Document(
            page_content=f"{date} {msg_time} {msg}",
            metadata={"source": f"doc_{i}", "id": f"doc_{i}"},
        )
        for i, (date, msg_time, role, msg) in enumerate(documents_sorted)
    ]

    return (
        self_docs_sorted[0] if self_docs_sorted else None,
        partner_docs_sorted[0] if partner_docs_sorted else None,
        documents_sorted,
        docs,
        partner_nickname,
    )


def format_message(msg):
    import re

    sentences = re.split(r"(。|\n)", msg)
    formatted = ""
    for s in sentences:
        if s and s != "\n":
            formatted += s.strip()
            if s == "。":
                formatted += "\n"
    return formatted


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
    # メッセージ情報取得処理
    # ------------------------------------------------------

    # パートナーと自分自身の最新メッセージ1件とパートナーのニックネームを情報を取得
    try:
        result = get_new_messages()
        self_docs, partner_docs, documents_sorted, docs, partner_nickname = result

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
        st.divider()

        db = Chroma.from_documents(docs, embedding=embeddings)
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
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)

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

        query = f"""
        # 役割
        あなたは恋愛心理カウンセラーです。女性からのメッセージに対して、魅力的な返信メッセージを作成することが得意です。

        # 文脈
        - 男性と{partner_nickname}は、1カ月前にマッチングしていて、メッセージをやり取りしている。
        - 男性は{partner_nickname}に好意を持っていて、真剣に交際を考えている。
        - 男性の年齢: 51歳
        - 女性の年齢: {partner_nickname}
        - 女性の趣味や性格: （プロフィール情報を追加）

        # 命令
        - {partner_nickname}の最新メッセージ内容をもとに男性側の思いを含めて、
          {partner_nickname}がキュンとする魅力的な返信メッセージを作成してください。
        - 現在の時刻に合わせた挨拶を文頭にいれること。
        - 男性から{partner_nickname}に対する返信メッセージであること。
        - {partner_nickname}の最新メッセージを細かくメッセージに反映すること。
        - 返信メッセージは、{partner_nickname}のメッセージ内容にしっかりと応答していること。
        - ニックネーム（{partner_nickname}）を反映すること。
        - 男性の最新メッセージと{partner_nickname}の最新メッセージを時系列で文脈を把握して、自然な会話となること。
        - 男性側の思いを必ず反映すること。
        - 生成するメッセージには「とのこと」の言葉は使用しないこと。
        - スマートでフレンドリーかつ、自然な文体にすること（軽すぎず、堅すぎず）
        - 優しい言葉遣いをベースに、知的、ユーモア、冗談をバランスよく含めること。
        - 長文になりすぎず、10～20文程度で簡潔にまとめること。
        - 文の内容にあった絵文字を入れること。
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
        {partner_docs}

        # 男性の最新メッセージ
        {self_docs if self_docs else "メッセージが見つかりませんでした"}

        # 男性側の思い
        {today_txt}
        """

        # 直近5件のメッセージ履歴をプロンプトに含める
        # recent_history = "\n".join([
        #     f"{date} {msg_time} [{role}] {msg}"
        #     for date, msg_time, role, msg in documents_sorted[:5]
        # ])
        # query += f"\n# 直近の会話履歴\n{recent_history}\n"

        ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
        # print(f"\n\n==================＜メッセージ＞==================\n{ai_msg['answer']}\n\n")
        chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])
        st.write(f"{ai_msg['answer']}")
        print(
            f"\n\n==================生成メッセージ=================="
            f"\n{ai_msg['answer']}\n\n"
        )
        st.divider()

    # これまでのメッセージ履歴からわかる人間性を分析する処理
    elif analyze_personality:
        st.divider()
        st.write("これまでのメッセージ履歴からわかる人間性を分析しました。")

        # ChromaDBを安全に初期化
        db = safe_init_chromadb()

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 新しい文書を安全に追加
        try:
            date, msg_time, role, msg = partner_docs
            partner_doc_obj = Document(
                page_content=f"{date} {msg_time} {role} {msg}",
                metadata={"source": "partner_latest", "id": "partner_latest"},
            )
            db.add_documents([partner_doc_obj])
            db.persist()
        except Exception as add_error:
            st.warning(
                f"最新メッセージの追加中にエラーが発生しました: {str(add_error)}"
            )
            # エラーが発生しても処理を続行

        # DBからRetrieverを作成
        retriever = db.as_retriever()

        query = """
        あなたは優秀な心理カウンセラーです。
        以下のメッセージ履歴から、女性の人間性・好意・性格・価値観・コミュニケーションの特徴を分析してください。
        - 好きな食べ物や趣味、休日の過ごし方、仕事や学業に対する姿勢などを具体的に挙げる
        - 性格や価値観、行動パターン、感情表現、対人関係の特徴を具体的に挙げる
        - 思いやり、誠実さ、ユーモア、知性、積極性、控えめさなどの要素を分析
        - 男性への好意や関心の度合い、感情や反応の場面を指摘
        - 判断が難しい場合はその旨も記載
        - 根拠となるメッセージ内容や表現も引用
        - 客観的かつ具体的に記述
        - やりたいことリストを具体的に抽出
        """
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)
        chain = RetrievalQA.from_chain_type(
            llm=llm, chain_type="stuff", retriever=retriever
        )
        result = chain.invoke({"query": query})
        st.write(f"{result['result']}")
        st.divider()

    # 二人のやりたいことリストを作成する処理
    elif create_wishlist:
        st.divider()
        st.write(f"{partner_nickname}さんと二人で叶えたいことリストを作成しました。")

        # ChromaDBを安全に初期化
        db = safe_init_chromadb()

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 新しい文書を安全に追加
        try:
            date, msg_time, role, msg = partner_docs
            partner_doc_obj = Document(
                page_content=f"{date} {msg_time} {role} {msg}",
                metadata={"source": "partner_latest", "id": "partner_latest"},
            )
            db.add_documents([partner_doc_obj])
            db.persist()
        except Exception as add_error:
            st.warning(
                f"最新メッセージの追加中にエラーが発生しました: {str(add_error)}"
            )
            # エラーが発生しても処理を続行

        # DBからRetrieverを作成
        retriever = db.as_retriever()

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

        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.3)
        chain = RetrievalQA.from_chain_type(
            llm=llm, chain_type="stuff", retriever=retriever
        )
        result = chain.invoke({"query": query})
        st.markdown(result["result"])
        st.divider()

        # 二人のやりたいことリストをダウンロード可能なテキストファイルとして提供
        # UTF-8 BOM付きエンコーディングで文字化けを防止（Windows対応）
        download_text = result["result"]
        # BOM（Byte Order Mark）を追加してWindowsでの文字化けを防ぐ
        download_data = '\ufeff' + download_text
        download_bytes = download_data.encode('utf-8')
        
        # ダウンロードボタンを2つ提供（日本語ファイル名とASCIIファイル名）
        col_dl1, col_dl2 = st.columns(2)
        
        with col_dl1:
            st.download_button(
                label="💕 やりたいことリスト（日本語）",
                data=download_bytes,
                file_name=f"{partner_nickname}_やりたいことリスト_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8",
                use_container_width=True,
            )
        
        with col_dl2:
            st.download_button(
                label="💕 Wishlist (ASCII)",
                data=download_bytes,
                file_name=f"{partner_nickname}_couple_wishlist_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
