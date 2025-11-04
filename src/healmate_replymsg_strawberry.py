import os
import time
from datetime import datetime

import openai
import streamlit as st

# ページ設定（最初に実行する必要がある）
st.set_page_config(
    page_title="Healmate Message Generator",
    page_icon="💬",
    layout="wide",  # 画面を広く使用
    initial_sidebar_state="expanded"
)
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import Document, HumanMessage
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# .envファイルのパスを指定
env_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"
)
load_dotenv(env_path)

# ------------------------------------------------------
# 変数定義
# ------------------------------------------------------
# プロジェクトルートディレクトリを取得
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

save_dir = os.path.join(project_root, "data", ".db")
metadata_file = os.path.join(project_root, "data", ".db_metadata.json")
partner_nickname = None

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

    # 最初のHTMLからパートナーのニックネームを取得（この関数では使用しない）
    # if html_list:
    #     soup = BeautifulSoup(html_list[0], "html.parser")
    #     name_elements = soup.select_one("div.hover")
    #     if name_elements:
    #         partner_nickname = name_elements.get_text(strip=True)

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
            msg_tag_partner = child.select_one(
                "div.talkBalloonColor2"
            )  # 🍓さんのメッセージ
            msg_time = time_tag.get_text(strip=True) if time_tag else ""

            # 男性のメッセージ
            if msg_tag_self:
                msg = msg_tag_self.get_text(strip=True)
                all_recent_messages.append((current_date, msg_time, "男性", msg))

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

    # print(f"🍓{partner_nickname}さんの最新メッセージ:", latest_partner_msg)
    # print(f"男性の最新メッセージ:, {latest_self_msg}")

    return {
        'partner_nickname': partner_nickname,
        'latest_partner_msg': latest_partner_msg,
        'latest_self_msg': latest_self_msg,
        'recent_context': recent_context,
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
        # print(f"🍓{partner_nickname}さんの最新メッセージ:", partner_messages_sorted[0])
        latest_partner_msg = partner_messages_sorted[0]
    else:
        # print(f"🍓{partner_nickname}さんのメッセージが見つかりませんでした")
        latest_partner_msg = None

    return (
        None,  # self_docs（不要）
        latest_partner_msg,  # 🍓さんの最新メッセージのみ
        [],  # documents_sorted（不要）
        [],  # docs（不要）
        partner_nickname,
    )


def get_custom_css():
    """モダンで落ち着いたトーンのカスタムCSSスタイル"""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* 暖かいブラウン系の全体設定 */
    .stApp {
        background: linear-gradient(180deg, #fdf6f0 0%, #faf0e6 100%);
    }
    
    /* メイン表示領域を広げる */
    .main .block-container {
        max-width: none !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* Streamlitのデフォルト制限を解除 */
    .stMainBlockContainer {
        max-width: none !important;
    }
    
    /* コンテンツエリアを最大限活用 */
    .element-container {
        width: 100% !important;
    }
    
    .main-header {
        background: linear-gradient(135deg, #b37b32 0%, #c8956d 25%, #d4a574 50%, #e0b87a 75%, #ecc881 100%);
        padding: 3rem 2.5rem;
        border-radius: 24px;
        text-align: center;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 20px 40px rgba(179, 123, 50, 0.25), 0 8px 25px rgba(200, 149, 109, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(20px);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        animation: modern-shimmer 6s ease-in-out infinite;
        z-index: 0;
    }
    
    .main-header::after {
        content: '✨ 洗練されたコミュニケーション';
        position: absolute;
        top: 15px;
        right: 20px;
        background: rgba(255, 255, 255, 0.15);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 500;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        z-index: 2;
    }
    
    @keyframes modern-shimmer {
        0%, 100% { transform: rotate(0deg) scale(1); opacity: 0.3; }
        50% { transform: rotate(90deg) scale(1.05); opacity: 0.5; }
    }
    
    .main-header h1 {
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 20px rgba(0,0,0,0.1);
        position: relative;
        z-index: 1;
        letter-spacing: -0.8px;
        line-height: 1.2;
    }
    
    .main-header p {
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.1rem;
        margin: 1rem 0 0 0;
        font-weight: 400;
        position: relative;
        z-index: 1;
        text-shadow: 0 1px 10px rgba(0,0,0,0.1);
        opacity: 0.95;
    }
    
    .message-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 2rem;
        border-radius: 16px;
        border: 1px solid rgba(179, 123, 50, 0.2);
        margin: 1rem 0;
        box-shadow: 0 4px 25px rgba(179, 123, 50, 0.08);
        backdrop-filter: blur(12px);
        transition: all 0.3s ease;
    }
    
    .message-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 35px rgba(179, 123, 50, 0.12);
    }
    
    .partner-message {
        background: linear-gradient(135deg, #c8956d 0%, #b37b32 100%);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 6px 30px rgba(200, 149, 109, 0.2);
    }
    
    .self-message {
        background: linear-gradient(135deg, #f5e6d3 0%, #e0b87a 100%);
        color: #8b4513;
        border: 1px solid rgba(200, 149, 109, 0.3);
        box-shadow: 0 6px 30px rgba(200, 149, 109, 0.15);
    }
    
    .stats-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(253, 246, 240, 0.95) 100%);
        padding: 2rem 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(179, 123, 50, 0.15);
        text-align: center;
        box-shadow: 0 8px 30px rgba(179, 123, 50, 0.08), 0 2px 12px rgba(139, 69, 19, 0.06);
        backdrop-filter: blur(16px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .stats-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #b37b32, #c8956d, #d4a574, #e0b87a);
        border-radius: 16px 16px 0 0;
    }
    
    .stats-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 40px rgba(200, 149, 109, 0.15), 0 6px 20px rgba(179, 123, 50, 0.1);
    }
    
    .stats-card h3 {
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
        opacity: 0.8;
    }
    
    .stats-card h2 {
        color: #b37b32;
        font-weight: 700;
        font-size: 2.5rem;
        margin: 0.5rem 0;
        text-shadow: 0 2px 10px rgba(179, 123, 50, 0.2);
    }
    
    .stats-card p strong {
        color: #8b4513;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    .action-button {
        background: linear-gradient(135deg, #c8956d 0%, #b37b32 100%);
        color: white;
        border: none;
        padding: 1rem 2rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1rem;
        letter-spacing: 0.2px;
        box-shadow: 0 8px 25px rgba(200, 149, 109, 0.25), 0 3px 12px rgba(179, 123, 50, 0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-transform: none;
        position: relative;
        overflow: hidden;
    }
    
    .action-button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        transition: left 0.6s ease;
    }
    
    .action-button:hover::before {
        left: 100%;
    }
    
    .action-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 35px rgba(200, 149, 109, 0.3), 0 6px 20px rgba(179, 123, 50, 0.2);
        background: linear-gradient(135deg, #b37b32 0%, #a0522d 100%);
    }
    
    .action-button:active {
        transform: translateY(0px);
        box-shadow: 0 4px 15px rgba(200, 149, 109, 0.3);
    }
    
    .result-container {
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(255, 182, 193, 0.3);
        border-radius: 20px;
        padding: 2.5rem;
        margin: 2rem 0;
        box-shadow: 0 8px 32px rgba(255, 107, 157, 0.1);
        backdrop-filter: blur(10px);
    }
    
    /* ヒールメイト風のボタンスタイル */
    .stButton > button {
        background: linear-gradient(45deg, #ff6b9d, #ff8fab) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 25px !important;
        font-weight: 600 !important;
        padding: 0.75rem 2rem !important;
        box-shadow: 0 4px 15px rgba(255, 107, 157, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 107, 157, 0.4) !important;
    }
    
    /* テキストエリアのスタイル */
    .stTextArea > div > div > textarea {
        border: 2px solid rgba(255, 182, 193, 0.3) !important;
        border-radius: 15px !important;
        background: rgba(255, 255, 255, 0.9) !important;
        backdrop-filter: blur(5px) !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #ff6b9d !important;
        box-shadow: 0 0 0 2px rgba(255, 107, 157, 0.2) !important;
    }
    
    /* セクションタイトル */
    .section-title {
        color: #b37b32;
        font-weight: 700;
        font-size: 1.5rem;
        margin: 2rem 0 1rem 0;
        text-align: center;
    }
    
    /* 入力セクションの暖かいブラウンスタイル */
    .input-section {
        background: linear-gradient(135deg, #b37b32 0%, #8b4513 100%);
        padding: 2.5rem;
        border-radius: 16px;
        margin: 2rem 0;
        color: white;
        box-shadow: 0 12px 35px rgba(179, 123, 50, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .input-section h3 {
        text-align: center;
        margin-bottom: 1rem;
        font-size: 1.8rem;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        font-weight: 600;
    }
    
    .input-section p {
        text-align: center;
        opacity: 0.9;
        font-size: 1.1rem;
        margin-bottom: 0;
        font-weight: 400;
    }
    
    /* アクションカードの薄い暖かいブラウンスタイル */
    .action-card-message {
        background: linear-gradient(135deg, #c8956d 0%, #b37b32 100%);
        padding: 1.5rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 8px 30px rgba(200, 149, 109, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .action-card-analysis {
        background: linear-gradient(135deg, #d4a574 0%, #e0b87a 100%);
        padding: 1.5rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 8px 30px rgba(212, 165, 116, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .action-card-wishlist {
        background: linear-gradient(135deg, #e0b87a 0%, #f5e6d3 100%);
        padding: 1.5rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 8px 30px rgba(224, 184, 122, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    /* サイドバーの薄い暖かいブラウンスタイル */
    .sidebar-header {
        background: linear-gradient(135deg, #c8956d 0%, #d4a574 100%);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(200, 149, 109, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .sidebar-status {
        background: rgba(255, 255, 255, 0.95);
        padding: 1.2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid rgba(200, 149, 109, 0.2);
        box-shadow: 0 4px 15px rgba(200, 149, 109, 0.08);
    }

    /* サイドバーのボタンスタイル */
    .stSidebar .stButton > button {
        background: linear-gradient(135deg, #c8956d, #b37b32);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.8rem 1.2rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(200,149,109,0.2);
        margin-bottom: 0.5rem;
        width: 100%;
    }

    .stSidebar .stButton > button:hover {
        background: linear-gradient(135deg, #b37b32, #a06328);
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(179,123,50,0.3);
    }

    .stSidebar .stButton > button:active {
        transform: translateY(0px);
        box-shadow: 0 2px 10px rgba(179,123,50,0.4);
    }
    </style>
    """


def render_main_header(partner_nickname):
    """メインヘッダーを表示する関数（Healmate公式デザイン風）"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)

    # モダンなヘッダーバッジ
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 1rem;">
        <span style="background: linear-gradient(135deg, #c8956d, #d4a574); color: white; padding: 0.5rem 1.5rem; border-radius: 12px; font-size: 0.9rem; font-weight: 600; box-shadow: 0 4px 15px rgba(200, 149, 109, 0.2);">
            ✨ インテリジェントメッセージアシスタント
        </span>
    </div>
    """,
        unsafe_allow_html=True,
    )
    
    st.markdown(
        f"""
    <div class="main-header">
        <h1>� {partner_nickname}さんへの返信メッセージ生成</h1>
        <p>AIが心のこもったメッセージ作成をサポートします</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    
    # モダンな利用案内
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="background: rgba(255, 255, 255, 0.9); padding: 1rem 2rem; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(179, 123, 50, 0.08); border: 1px solid rgba(179, 123, 50, 0.15);">
            <span style="color: #b37b32; font-weight: 600; font-size: 1rem;">🤖 スマートで効率的なコミュニケーション体験</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
def render_stats_cards(latest_messages_sorted):
    """統計カードを表示する関数（4列レイアウト）"""
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4, gap="medium")

    with stats_col1:
        st.markdown(
            """
        <div class="stats-card">
            <h3>📊</h3>
            <p><strong>メッセージ数</strong></p>
            <h2>{}</h2>
        </div>
        """.format(
                len(latest_messages_sorted)
            ),
            unsafe_allow_html=True,
        )

    with stats_col2:
        latest_time = latest_messages_sorted[-1][1] if latest_messages_sorted else "---"
        st.markdown(
            """
        <div class="stats-card">
            <h3>⏰</h3>
            <p><strong>最新時刻</strong></p>
            <h2>{}</h2>
        </div>
        """.format(
                latest_time.replace("既読", "")
            ),
            unsafe_allow_html=True,
        )

    with stats_col3:
        st.markdown(
            """
        <div class="stats-card">
            <h3>💝</h3>
            <p><strong>会話状況</strong></p>
            <h2>進行中</h2>
        </div>
        """,
            unsafe_allow_html=True,
        )
    
    with stats_col4:
        st.markdown(
            """
        <div class="stats-card">
            <h3>⚡</h3>
            <p><strong>効率性</strong></p>
            <h2>HIGH</h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)


def render_message_card(date, msg_time, sender, msg, title, card_class):
    """個別のメッセージカードを表示する関数"""
    msg_formatted = format_message(msg)
    return f"""
    <div class="message-card {card_class}">
        <h4>{title}</h4>
        <div style="display: flex; justify-content: space-between; margin-bottom: 1rem;">
            <span><strong>📅 {date}</strong></span>
            <span><strong>🕒 {msg_time}</strong></span>
        </div>
        <div style="margin-bottom: 0.5rem;"><strong>👤 {sender}</strong></div>
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; white-space: pre-wrap;">{msg_formatted}</div>
    </div>
    """


def render_input_section(partner_nickname):
    """入力セクションを表示する関数（ヒールメイト風）"""
    st.markdown(
        """
    <div class="input-section">
        <h3>✍️ あなたの想いを入力してください</h3>
        <p>今日の出来事や、{}さんからのメッセージへの思いをお聞かせください</p>
    </div>
    """.format(
            partner_nickname
        ),
        unsafe_allow_html=True,
    )

    label_text = f"💭 今日の出来事や{partner_nickname}さんからの最新メッセージに対する思いを入力してください。"
    return st.text_area(
        label=label_text,
        height=150,
        placeholder="例：今日は仕事で大変だったけど、🍓さんのメッセージを見て元気が出ました...",
        help="具体的な出来事や感情を書くと、より自然なメッセージが生成されます",
    )


def render_action_buttons():
    """アクションボタンを表示する関数"""
    st.markdown("<br>", unsafe_allow_html=True)

    button_col1, button_col2, button_col3 = st.columns([1, 1, 1], gap="medium")

    with button_col1:
        st.markdown(
            """
        <div class="action-card-message">
            <h4 style="color: white; margin: 0; font-size: 1.3rem;">💬 メッセージ生成</h4>
            <p style="color: white; margin: 0.5rem 0 0 0; font-size: 0.95em;">AIが心のこもったメッセージを作成</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        generate_message = st.button(
            "💬 メッセージを生成する", use_container_width=True, type="primary"
        )

    with button_col2:
        st.markdown(
            """
        <div class="action-card-analysis">
            <h4 style="color: #444; margin: 0; font-size: 1.3rem;">🧠 人格分析</h4>
            <p style="color: #666; margin: 0.5rem 0 0 0; font-size: 0.95em;">相手の性格や特徴を詳細分析</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        analyze_personality = st.button(
            "🧠 人格分析を実行", use_container_width=True, type="secondary"
        )

    with button_col3:
        st.markdown(
            """
        <div class="action-card-wishlist">
            <h4 style="color: #444; margin: 0; font-size: 1.3rem;">💕 やりたいことリスト</h4>
            <p style="color: #666; margin: 0.5rem 0 0 0; font-size: 0.95em;">二人の未来の計画を作成</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        create_wishlist = st.button(
            "💕 リストを作成", use_container_width=True, type="secondary"
        )

    return generate_message, analyze_personality, create_wishlist


def render_sidebar():
    """サイドバーを表示する関数（ヒールメイト風）"""
    with st.sidebar:
        st.markdown(
            """
        <div class="sidebar-header">
            <h2 style="color: white; margin: 0; font-size: 1.4rem;">⚙️ システム管理</h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 0.95rem;">データベース操作</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # 現在の状態表示
        st.markdown(
            """
        <div class="sidebar-status">
            <h4 style="color: #ff6b9d; margin: 0 0 0.5rem 0; font-size: 1.1rem;">📊 システム状態</h4>
            <p style="margin: 0; color: #28a745; font-weight: 600;"><strong>✅ 正常稼働中</strong></p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # システム管理ボタン
        if st.button(
            "🔄 データベースをリセット",
            help="データベースエラーが発生した場合に使用",
            use_container_width=True,
        ):
            with st.spinner("データベースをリセット中..."):
                try:
                    # 既存のDBを削除
                    delete_success = safe_delete_db()

                    # メタデータファイルも削除
                    metadata_file = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data",
                        ".db_metadata.json",
                    )
                    if os.path.exists(metadata_file):
                        try:
                            os.remove(metadata_file)
                            st.success("✅ メタデータファイルを削除しました")
                        except Exception as meta_error:
                            st.warning(
                                f"メタデータファイルの削除に失敗: {str(meta_error)}"
                            )

                    if delete_success:
                        st.success("✅ 既存データベースを削除しました")

                        # 少し待ってから新しいDBを作成
                        import time

                        time.sleep(1)

                        # 新しいDBを作成（全会話履歴で初期化）
                        new_db = safe_init_chromadb(
                            force_recreate=True, data_type="full_conversation"
                        )
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

        if st.button(
            "🚨 緊急リセット",
            help="強制的にデータベースをクリアして再起動",
            use_container_width=True,
        ):
            st.error("⚠️ 緊急リセットモード")
            show_manual_deletion_guide()

        if st.button(
            "🧹 アプリケーションを再起動",
            help="完全にアプリケーションを再起動",
            use_container_width=True,
        ):
            st.info("📋 再起動手順:")
            st.markdown(
                """
            1. **ブラウザのこのタブを閉じる**
            2. **ターミナルでCtrl+Cを押してアプリを停止**
            3. **再度 `streamlit run` コマンドで起動**
            """
            )


def render_message_result():
    """メッセージ生成結果を表示する関数（ヒールメイト風）"""
    if st.session_state.message_result:
        st.markdown(
            """
        <div class="result-container">
            <h2 style="color: #ff6b9d; text-align: center; margin-bottom: 2rem; font-size: 2rem;">
                💬 生成されたメッセージ
            </h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # メッセージを美しいカードで表示（ヒールメイト風）
        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #ff6b9d 0%, #ff8fab 100%); 
                    color: white; padding: 2.5rem; border-radius: 20px; 
                    box-shadow: 0 12px 40px rgba(255, 107, 157, 0.3); margin: 2rem 0;
                    border: 1px solid rgba(255, 255, 255, 0.2);">
            <div style="background: rgba(255,255,255,0.15); padding: 2rem; 
                        border-radius: 15px; white-space: pre-wrap; 
                        font-size: 1.15em; line-height: 1.7; 
                        backdrop-filter: blur(5px);">{st.session_state.message_result}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # アクションボタン
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button(
                "📋 クリップボードにコピー",
                key="copy_message",
                use_container_width=True,
            ):
                st.success(
                    "✅ メッセージがコピーされました（手動でコピーしてください）"
                )
        with action_col2:
            st.download_button(
                label="💾 テキストファイルで保存",
                data=st.session_state.message_result,
                file_name=f"generated_message_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with action_col3:
            if st.button(
                "🗑️ メッセージをクリア", key="clear_message", use_container_width=True
            ):
                st.session_state.message_result = None
                st.rerun()


def render_personality_result():
    """人格分析結果を表示する関数"""
    if st.session_state.personality_result:
        st.markdown(
            """
        <div class="result-container">
            <h2 style="color: #667eea; text-align: center; margin-bottom: 2rem;">
                🧠 人格分析結果
            </h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # 分析結果を美しく表示
        # f-string内でバックスラッシュを避けるため、先に文字列処理を行う
        formatted_result = st.session_state.personality_result.replace(
            '##', '<h3 style="color: #ffd700;">'
        )
        formatted_result = formatted_result.replace('\n\n', '</h3>\n\n')

        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    color: white; padding: 2rem; border-radius: 15px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1); margin: 1rem 0;">
            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; 
                        border-radius: 10px;">
                {formatted_result}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # アクションボタン
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            st.download_button(
                label="💾 分析結果を保存",
                data=st.session_state.personality_result,
                file_name=f"personality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with action_col2:
            if st.button(
                "🗑️ 人格分析をクリア", key="clear_personality", use_container_width=True
            ):
                st.session_state.personality_result = None
                st.rerun()


def render_wishlist_result(partner_nickname):
    """やりたいことリスト結果を表示する関数"""
    if st.session_state.wishlist_result:
        st.markdown(
            """
        <div class="result-container">
            <h2 style="color: #f5576c; text-align: center; margin-bottom: 2rem;">
                💕 やりたいことリスト
            </h2>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state.wishlist_result)

        # LINE用プレビュー
        st.subheader("📱 LINE用プレビュー")
        st.info("以下のテキストはLINEでコピペしやすい形式です")

        # LINE用テキスト変換
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

        line_text_display = convert_to_line_format_display(
            st.session_state.wishlist_result
        )
        st.text(line_text_display)

        # ダウンロードボタン
        col_dl1, col_dl2, col_dl3 = st.columns(3)

        with col_dl1:
            line_data = "\ufeff" + line_text_display
            st.download_button(
                label="📱 LINE用DL",
                data=line_data.encode("utf-8"),
                file_name=f"{partner_nickname}_LINE用_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8",
            )

        with col_dl2:
            markdown_data = "\ufeff" + st.session_state.wishlist_result
            st.download_button(
                label="📄 Markdown DL",
                data=markdown_data.encode("utf-8"),
                file_name=f"{partner_nickname}_やりたいこと_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8",
            )

        with col_dl3:
            if st.button("🗑️ リストをクリア", key="clear_wishlist"):
                st.session_state.wishlist_result = None
                st.session_state.wishlist_line_text = None
                st.rerun()


def format_message(msg):
    """メッセージの改行位置を維持して返す（WEBサイトの書式を保持）"""
    # 先頭と末尾の余分な空白のみ削除、改行は保持
    return msg.strip()


def safe_delete_db():
    """ChromaDBディレクトリを安全に削除する関数（Windowsファイルロック対応）"""
    import gc
    import shutil
    import time

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


def load_db_metadata():
    """データベースのメタデータを読み込み"""
    import json

    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"message_count": 0, "last_update": None}
    return {"message_count": 0, "last_update": None}


def save_db_metadata(message_count, last_update=None):
    """データベースのメタデータを保存"""
    import json

    if last_update is None:
        last_update = datetime.now().isoformat()

    metadata = {"message_count": message_count, "last_update": last_update}

    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"メタデータの保存に失敗しました: {str(e)}")


def get_message_ids_from_docs(docs):
    """Documentリストからメッセージ識別子のセットを作成"""
    ids = set()
    for doc in docs:
        # メッセージの内容とメタデータから一意IDを生成
        content = doc.page_content
        metadata = doc.metadata
        msg_id = f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"
        ids.add(msg_id)
    return ids


def get_new_messages_only(current_docs, existing_db=None):
    """新しいメッセージのみを抽出する差分関数"""
    if existing_db is None:
        return current_docs

    try:
        # 既存DBからすべてのドキュメントを取得
        existing_docs = existing_db.get()
        if not existing_docs or not existing_docs.get('documents'):
            return current_docs

        # 既存メッセージのIDセットを作成
        existing_ids = set()
        existing_contents = existing_docs.get('documents', [])
        existing_metadatas = existing_docs.get('metadatas', [])

        for i, content in enumerate(existing_contents):
            metadata = existing_metadatas[i] if i < len(existing_metadatas) else {}
            msg_id = (
                f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"
            )
            existing_ids.add(msg_id)

        # 新しいメッセージのみを抽出
        new_docs = []

        for doc in current_docs:
            content = doc.page_content
            metadata = doc.metadata
            msg_id = (
                f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"
            )

            if msg_id not in existing_ids:
                new_docs.append(doc)

        return new_docs

    except Exception as e:
        st.warning(f"差分抽出でエラー: {str(e)}。全データを使用します。")
        return current_docs


def safe_init_chromadb(force_recreate=False, data_type="partner_only"):
    """
    ChromaDBを効率的に初期化・更新する関数
    data_type: "partner_only", "full_conversation", "all_messages"
    """
    import gc
    import warnings

    # LangChain の非推奨警告を抑制
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    if force_recreate:
        st.info("🔄 データベースを強制的に再作成しています...")

    # 強制再作成が指定された場合
    if force_recreate and os.path.exists(save_dir):
        if not safe_delete_db():
            return None
        # メタデータファイルも削除
        if os.path.exists(metadata_file):
            try:
                os.remove(metadata_file)
            except Exception:
                pass

    try:
        # データベースが存在しない場合（初回作成）
        if not is_db():
            st.info("📊 初回データベースを作成中...")
            with st.spinner("全メッセージ履歴を取得中..."):
                # 初回は全会話履歴を取得してデータベースを作成
                if data_type == "full_conversation":
                    documents = get_full_conversation_history()
                elif data_type == "all_messages":
                    documents = get_all_messages()
                else:  # partner_only
                    documents = get_all_messages()

                if not documents:
                    st.warning("メッセージが取得できませんでした。")
                    return None

                # 初回DB作成
                db = Chroma.from_documents(
                    documents, embedding=embeddings, persist_directory=save_dir
                )
                db.persist()

                # メタデータ保存
                save_db_metadata(len(documents))

            st.success(
                f"✅ 初回データベースを作成しました（{len(documents)}件のメッセージ）"
            )
            return db

        else:
            # 既存DBを読み込み
            db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

            # 動作確認
            try:
                test_retriever = db.as_retriever(search_kwargs={"k": 1})
                test_retriever.invoke("テスト")

                # メタデータ確認
                metadata = load_db_metadata()
                st.info(
                    f"💾 既存データベースを読み込みました（前回: {metadata['message_count']}件）"
                )

                return db

            except Exception as test_error:
                st.warning(f"既存データベースに問題があります: {str(test_error)}")
                del db
                gc.collect()
                return safe_init_chromadb(force_recreate=True, data_type=data_type)

    except Exception as db_error:
        st.error(f"データベースエラー: {str(db_error)}")

        if not force_recreate:
            st.info("データベースを再作成しています...")
            return safe_init_chromadb(force_recreate=True, data_type=data_type)
        else:
            st.error("⚠️ データベース初期化に失敗しました")
            show_manual_deletion_guide()
            return None


def update_chromadb_with_diff(db, data_type="partner_only"):
    """既存のChromaDBに差分データのみを追加する関数"""
    try:
        # 現在のデータを取得
        with st.spinner("新しいメッセージをチェック中..."):
            if data_type == "full_conversation":
                current_docs = get_full_conversation_history()
            elif data_type == "all_messages":
                current_docs = get_all_messages()
            else:  # partner_only
                current_docs = get_all_messages()

        if not current_docs:
            st.warning("新しいメッセージが取得できませんでした。")
            return db

        # 差分を抽出
        new_docs = get_new_messages_only(current_docs, db)

        if not new_docs:
            st.success("📱 新しいメッセージはありません")
            return db

        # 新しいメッセージをDBに追加
        with st.spinner(f"新しいメッセージ {len(new_docs)}件をデータベースに追加中..."):
            db.add_documents(new_docs)
            db.persist()

        # メタデータ更新
        save_db_metadata(len(current_docs))

        st.success(
            f"✅ {len(new_docs)}件の新しいメッセージをデータベースに追加しました"
        )

        return db

    except Exception as e:
        st.error(f"差分更新でエラー: {str(e)}")
        return db


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

    # サイドバーの表示
    render_sidebar()

    # メインヘッダーの表示
    render_main_header(partner_nickname)

    st.markdown("### 📱 最新メッセージ")

    # 最新メッセージを送信時間で昇順に表示
    latest_messages = []

    # パートナーの最新メッセージを追加
    if partner_docs:
        date, msg_time, role, msg = partner_docs
        latest_messages.append((date, msg_time, f"🍓{partner_nickname}", msg))

    # 男性の最新メッセージを追加
    if self_docs:
        date, msg_time, role, msg = self_docs
        latest_messages.append((date, msg_time, "👤男性(あなた)", msg))

    # 送信時間で昇順ソート（古い順）
    latest_messages_sorted = sorted(
        latest_messages, key=lambda x: parse_datetime(x[0], x[1]), reverse=False
    )

    # 統計情報の表示
    render_stats_cards(latest_messages_sorted)

    # 最新メッセージを横並びで表示（リッチなカードスタイル）
    if len(latest_messages_sorted) == 1:
        date, msg_time, sender, msg = latest_messages_sorted[0]
        card_class = "partner-message" if "🍓" in sender else "self-message"
        st.markdown(
            render_message_card(
                date, msg_time, sender, msg, "🆕 最新メッセージ", card_class
            ),
            unsafe_allow_html=True,
        )

    elif len(latest_messages_sorted) == 2:
        col1, col2 = st.columns([1, 1], gap="medium")  # 均等な幅で少し狭いギャップ
        for i, (date, msg_time, sender, msg) in enumerate(latest_messages_sorted):
            title = (
                "🆕 最新メッセージ"
                if i == len(latest_messages_sorted) - 1
                else "📝 前のメッセージ"
            )
            card_class = "partner-message" if "🍓" in sender else "self-message"

            with col1 if i == 0 else col2:
                st.markdown(
                    render_message_card(date, msg_time, sender, msg, title, card_class),
                    unsafe_allow_html=True,
                )
    else:
        for i, (date, msg_time, sender, msg) in enumerate(latest_messages_sorted):
            title = (
                "🆕 最新メッセージ"
                if i == len(latest_messages_sorted) - 1
                else f"📝 メッセージ {i+1}"
            )
            card_class = "partner-message" if "🍓" in sender else "self-message"
            st.markdown(
                render_message_card(date, msg_time, sender, msg, title, card_class),
                unsafe_allow_html=True,
            )

    # 入力セクションとアクションボタンの表示
    today_txt = render_input_section(partner_nickname)
    generate_message, analyze_personality, create_wishlist = render_action_buttons()

    if generate_message:
        # ユーザー入力のチェック
        if not today_txt or today_txt.strip() == "":
            st.error("メッセージを生成するには、今日の出来事や思いを入力してください。")
        else:
            with st.spinner("💬 メッセージを生成中..."):
                # 既存DBを効率的に利用（全会話履歴用）
                db = safe_init_chromadb(data_type="full_conversation")

                if db is None:
                    st.error("データベースの初期化に失敗しました。")
                    st.stop()

                # 差分更新を実行
                db = update_chromadb_with_diff(db, data_type="full_conversation")
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
                llm = ChatOpenAI(model="gpt-4o-mini")

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
                    sorted_context = sorted(
                        recent_context, key=lambda x: parse_datetime(x[0], x[1])
                    )
                    for i, (date, msg_time, speaker, msg) in enumerate(sorted_context):
                        recent_conversation += f"{i+1}. [{speaker}] {msg}\n"

                query = f"""
                        # 役割
                        あなたは恋愛心理カウンセラーであり、LINEメッセージの脚本家です。
                        これから出力するのは「男性が実際に送るLINEメッセージ本文」そのものです。

                        # 文脈
                        - 男性と{partner_nickname}は1カ月前にマッチングして継続的にやり取りしている。
                        - 男性は{partner_nickname}に好意を持ち、真剣な交際を考えている。
                        - 男性の年齢: 51歳
                        - 会話の流れを踏まえ、**自然かつ印象に残る返信**を作成する。

                        {recent_conversation}

                        # 出力の必須条件（重要）
                        - 出力は「送信メッセージ本文」のみ（分析・前置きは禁止）。
                        - 会話の続きとして自然で違和感のない流れにすること。
                        - {partner_nickname}の最新メッセージへの**具体的な反応・共感・解釈**を含めること。
                        - 男性の前回メッセージとの**つながりを意識**して書くこと。
                        - 話題転換がある場合は**自然な橋渡しの一言**を入れること。
                        - 感情表現には**共感・理解・自分の解釈**を入れること。

                        # 文体・トーンの指示
                        - 一人称は「俺」または「自分」。
                        - 柔らかく知的で親しみがあり、**余白・ユーモア・人間味**を含める。
                        - 抽象的な感想ではなく、**自分なりの考え・視点・たとえ話**を盛り込む。
                        - 単なる「いいよね」ではなく、**一歩踏み込んだ本音・解釈・共感**を入れる。
                        - 会話に“ちょっとした遊び心”や“ニヤリとする一言”を加える（例：「語りすぎ？笑」「…なんてね」など）
                        - 自分と相手・ドラマ・状況などを**リンクさせる表現**を盛り込む（例：「中身は俺と似てるかも」）
                        - 最後は**軽やかで余韻のある一言**で締める。

                        # メッセージ構成の目安
                        1. 冒頭：挨拶＋相手の行動への反応（「おっ、〜したんだね！」など自然な導入）
                        2. 本題1：共感・感想＋自分なりの深い解釈
                        3. 本題2：そこから派生する価値観・考え方・自分とのリンク
                        4. 結び：ユーモア・余白のある一言で締める

                        # 表現ルール
                        - 「〜とのこと」は使わない。
                        - 抽象的すぎる表現は避け、具体例・比喩・価値観を織り交ぜる。
                        - 下品・即会い・過度な褒めは禁止。
                        - 10〜20文、絵文字を適度に使う。

                        # 出力形式
                        - テキストのみ
                        - 3パターン（知的で落ち着き／甘めでドキッとする／ユーモラスで軽やか）

                        # {partner_nickname}の最新メッセージ
                        {partner_docs[3] if partner_docs and len(partner_docs) > 3 else "メッセージが見つかりませんでした"}

                        # 男性の最新メッセージ
                        {self_docs[3] if self_docs and len(self_docs) > 3 else "メッセージが見つかりませんでした"}

                        # 男性側の思い
                        {today_txt}

                    """

                ai_msg = rag_chain.invoke(
                    {"input": query, "chat_history": chat_history}
                )
                # セッション状態に結果を保存
                st.session_state.message_result = ai_msg['answer']
                chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])
                # print(
                #     f"\n\n==================生成メッセージ=================="
                #     f"\n{ai_msg['answer']}\n\n"
                # )

    # これまでのメッセージ履歴からわかる人間性を分析する処理
    elif analyze_personality:
        st.divider()
        st.write(
            f"🍓{partner_nickname}さんの全メッセージ履歴からわかる人間性を分析しました。"
        )

        # 既存DBを効率的に利用（パートナーメッセージ用）
        db = safe_init_chromadb(data_type="partner_only")

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 差分更新を実行
        db = update_chromadb_with_diff(db, data_type="partner_only")

        # メタデータから件数取得
        metadata = load_db_metadata()
        st.info(
            f"分析対象: 🍓{partner_nickname}さんのメッセージ {metadata['message_count']}件"
        )

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

        llm = ChatOpenAI(model="gpt-4o-mini")

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

        # 既存DBを効率的に利用（全会話履歴用）
        db = safe_init_chromadb(data_type="full_conversation")

        if db is None:
            st.error("データベースの初期化に失敗しました。")
            st.stop()

        # 差分更新を実行
        db = update_chromadb_with_diff(db, data_type="full_conversation")

        # メタデータから件数取得
        metadata = load_db_metadata()
        st.info(f"分析対象: 全会話履歴 {metadata['message_count']}件のメッセージ")

        # DBからRetrieverを作成（より多くの関連会話を検索）
        retriever = db.as_retriever(search_kwargs={"k": 30})

        query = f"""
        あなたは優秀な恋愛コンサルタントです。
        以下のメッセージ履歴から、{partner_nickname}さんと男性が**二人で一緒に**行きたいと思っていること、
        やりたいと思っていること、興味を示していることを抽出して、具体的な「二人のやりたいことリスト」を作成してください。
        二人のやりたいことリストは「男性が実際に送るLINEメッセージ本文」そのものです。

        # 抽出対象（二人で行う事項に限定）
        - 目標が具体的に指定されているもの
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
        - チェックリスト形式

        # 注意事項
        - 推測ではなく、実際のメッセージ内容に基づいて抽出すること
        - デートやカップル活動として実現可能なアクションとして表現すること
        - チェックボックス形式で、実行可能なリストとして作成すること
        - 「一緒に」といった表現を意識すること
        - 情報が不足している場合は「メッセージからは二人での具体的な希望が確認できませんでした」と記載
        """

        llm = ChatOpenAI(model="gpt-4o-mini")

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
                help="LINEでコピペしやすい形式のテキストファイル",
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
                help="元のMarkdown形式のテキストファイル",
            )

    # ------------------------------------------------------
    # 保存された結果の表示（常に表示）
    # ------------------------------------------------------

    # 結果表示関数を使用
    render_message_result()
    render_personality_result()
    render_wishlist_result(partner_nickname)

    # 以下は削除予定のコード（関数化済み）
    if False and st.session_state.message_result:
        st.markdown(
            """
        <div class="result-container">
            <h2 style="color: #ff6b6b; text-align: center; margin-bottom: 2rem;">
                💬 生成されたメッセージ
            </h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # メッセージを美しいカードで表示
        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 2rem; border-radius: 15px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1); margin: 1rem 0;">
            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; 
                        border-radius: 10px; white-space: pre-wrap; 
                        font-size: 1.1em; line-height: 1.6;">{st.session_state.message_result}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # アクションボタン
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button(
                "📋 クリップボードにコピー",
                key="copy_message",
                use_container_width=True,
            ):
                st.success(
                    "✅ メッセージがコピーされました（手動でコピーしてください）"
                )
        with action_col2:
            st.download_button(
                label="💾 テキストファイルで保存",
                data=st.session_state.message_result,
                file_name=f"generated_message_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with action_col3:
            if st.button(
                "🗑️ メッセージをクリア", key="clear_message", use_container_width=True
            ):
                st.session_state.message_result = None
                st.rerun()

    # 人格分析結果の表示
    if st.session_state.personality_result:
        st.markdown(
            """
        <div class="result-container">
            <h2 style="color: #667eea; text-align: center; margin-bottom: 2rem;">
                🧠 人格分析結果
            </h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # 分析結果を美しく表示
        # f-string内でバックスラッシュを避けるため、先に文字列処理を行う
        formatted_result = st.session_state.personality_result.replace(
            '##', '<h3 style="color: #ffd700;">'
        )
        formatted_result = formatted_result.replace('\n\n', '</h3>\n\n')

        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    color: white; padding: 2rem; border-radius: 15px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1); margin: 1rem 0;">
            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; 
                        border-radius: 10px;">
                {formatted_result}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # アクションボタン
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            st.download_button(
                label="💾 分析結果を保存",
                data=st.session_state.personality_result,
                file_name=f"personality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with action_col2:
            if st.button(
                "🗑️ 人格分析をクリア", key="clear_personality", use_container_width=True
            ):
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

        line_text_display = convert_to_line_format_display(
            st.session_state.wishlist_result
        )
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
                mime="text/plain; charset=utf-8",
            )

        with col_dl2:
            # Markdown形式ダウンロード
            markdown_data = "\ufeff" + st.session_state.wishlist_result
            st.download_button(
                label="📄 Markdown DL",
                data=markdown_data.encode("utf-8"),
                file_name=f"{partner_nickname}_やりたいこと_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain; charset=utf-8",
            )

        with col_dl3:
            # クリアボタン
            if st.button("🗑️ リストをクリア", key="clear_wishlist"):
                st.session_state.wishlist_result = None
                st.session_state.wishlist_line_text = None
                st.rerun()


if __name__ == "__main__":
    main()
