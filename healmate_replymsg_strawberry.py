from bs4 import BeautifulSoup
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
import os
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

load_dotenv()

# ------------------------------------------------------
# 変数定義
# ------------------------------------------------------
save_dir = "C:\work\ws_python\GenerationAiCamp\HM\.db"

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

# 日付・時間でソートする関数
def is_db():
    if os.path.isdir(save_dir):
        # ディレクトリが存在する場合の処理
        return True
    return False

# 全メッセージ情報を取得する関数
def get_all_messages():
    all_documents = []
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    token = driver.find_element("name", "token").get_attribute("value")
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
    all_documents = list({(d[0], d[1], d[2]): d for d in all_documents}.values())

    docs = [
        Document(
            page_content=f"{date} {msg_time} {msg}",
            metadata={"source": f"doc_{i}", "id": f"doc_{i}"}
        )
        for i, (date, msg_time, msg) in enumerate(all_documents)
    ]

    return docs

def get_new_messages():
    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # ヒールメイトのログインページにアクセス
    driver.get("https://healmate.jp/login")

    # ログイン実行
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    token = driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()

    # パートナーとのメッセージページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")

    # 最新情報のみを取得するため、ページ最下部までスクロール
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "container")))

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
                partner_docs.append((current_date, msg_time, f"【{partner_nickname}】", msg))

    # 日付と時間でソート
    self_docs_sorted = sorted(
        self_docs,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )
    print(self_docs_sorted[0])

    # 日付と時間でソート
    partner_docs_sorted = sorted(
        partner_docs,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )
    print(partner_docs_sorted[0])

    # 全てのメッセージをまとめる
    documents = self_docs + partner_docs

    # 日付と時間でソート
    documents_sorted = sorted(
        documents,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )

    # for date, time, role, msg in documents_sorted:
    #   print(f"{date} {time} [{role}] {msg}")

    docs = [
        Document(
            page_content=f"{date} {msg_time} {msg}",
            metadata={"source": f"doc_{i}", "id": f"doc_{i}"}
        )
        for i, (date, msg_time, role, msg) in enumerate(documents_sorted)
    ]

    return self_docs_sorted[0], partner_docs_sorted[0], documents_sorted, docs, partner_nickname

# msgを適度に改行して見やすくする（句点・改行で分割して再結合する例）
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

def main():
    # ------------------------------------------------------
    # メッセージ情報取得処理
    # ------------------------------------------------------

    # パートナーと自分自身の最新メッセージ1件とパートナーのニックネームを情報を取得
    self_docs, partner_docs, documents_sorted, docs, partner_nickname = get_new_messages()

    # ------------------------------------------------------
    # Streamlitアプリ
    # ------------------------------------------------------

    st.title(f"{partner_nickname}さんへの返信メッセージ自動生成アプリ")
    st.divider()
    st.subheader(f"最新メッセージ")

    # partner_docsは (date, msg_time, role, msg)
    date, msg_time, role, msg = partner_docs
    msg_formatted = format_message(msg)

    # Streamlitで見やすく表示
    st.markdown(f"""
    **日付**: {date}  
    **時間**: {msg_time}  
    **送信者**: {role}  
    **メッセージ**:  
    {msg_formatted}
    """)
    st.divider()

    today_txt = st.text_area(label=f"今日の出来事や{partner_nickname}さんからの最新メッセージに対する思いを入力してください。")

    if st.button("メッセージ生成"):
        st.divider()

        db = Chroma.from_documents(docs, embedding=embeddings)
        db.persist()
        retriever = db.as_retriever()

        # 手順1〜3の処理を実現するにあたり、LLMへのリクエストは以下の2回行われる。
        # 1.会話履歴がなくても理解できる、独立した入力を生成するためのLLMリクエスト
        # 2.生成された入力内容と関連ドキュメントを渡して、最終的な回答を生成するためのLLMリクエスト
        # ここでは「1. 会話履歴がなくても理解できる、独立した入力を生成するためのLLMリクエスト」を行うための、専用のプロンプトを用意。
        question_generator_template = "会話履歴と最新の入力をもとに、会話履歴なしでも理解できる独立した入力テキストを生成してください。"

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
        question_answer_chain = create_stuff_documents_chain(llm, question_answer_prompt)

        # 引数には、先ほど作成した「create_history_aware_retriever」のインスタンスと、
        # 「create_stuff_documents_chain」のインスタンスを渡す。
        # 後ほど、この「create_retrieval_chain」のインスタンスが持つ「invoke()」メソッドに
        # 「入力内容」と「会話履歴」の2つのデータを渡すことで、独立した入力内容の生成と
        # 関連ドキュメントの取得、最終的なLLMからの回答生成を内部的に一括で行える。
        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        #chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)

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
        - {partner_nickname}の最新メッセージ内容をもとに男性側の思いを含めて、{partner_nickname}がキュンとする魅力的な返信メッセージを作成してください。
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
        {self_docs[0]}

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
        print(f"\n\n==================生成メッセージ==================\n{ai_msg['answer']}\n\n")
        st.divider()

    # これまでのメッセージ履歴からわかる人間性を分析する処理
    elif st.button("人格分析"):
        st.divider()
        st.write("これまでのメッセージ履歴からわかる人間性を分析しました。")

        # 最初の起動時のみ実行したい処理
        if "initialized" not in st.session_state:
            st.session_state["initialized"] = True
            # DBが存在しない場合の処理
            if not is_db():
                # DBがなければ初回のみ作成
                documents = get_all_messages()
                db = Chroma.from_documents(documents, embedding=embeddings, persist_directory=save_dir)
                db.persist()
            else:
                db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

        db = Chroma(persist_directory=save_dir, embedding_function=embeddings)
        # 新しい文書を足すときは add_documents を使う
        # ここでは、最新のパートナーからのメッセージを追加
        date, msg_time, role, msg = partner_docs
        partner_doc_obj = Document(
            page_content=f"{date} {msg_time} {role} {msg}",
            metadata={"source": "partner_latest", "id": "partner_latest"}
        )
        db.add_documents([partner_doc_obj])
        db.persist()

        # DBからRetrieverを作成
        retriever = db.as_retriever()

        query = f"""
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
        chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
        result = chain.run(query)
        st.write(f"{result}")
        st.divider()

if __name__ == "__main__":
    main()
