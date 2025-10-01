import requests
from bs4 import BeautifulSoup
from llama_index.core import download_loader
from llama_index.core import GPTVectorStoreIndex
from llama_index.core import StorageContext, load_index_from_storage
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
import os
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import shutil
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

st.title("返信メッセージ自動生成アプリ")
st.divider()
today_txt = st.text_area(label="今日の出来事を入力してください。")

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

if st.button("実行"):
    st.divider()

    # ログイン後のターゲットページにアクセス(男性メッセージ)
    documents = []

    # Chromeをヘッドレス（画面非表示）で起動
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # ログインページにアクセス
    driver.get("https://healmate.jp/login")
    #time.sleep(2)  # ページ読み込み待ち

    # ログイン処理（例：フォーム入力と送信）
    driver.find_element("name", "id").send_keys("youcan9160@gmail.com")
    driver.find_element("name", "pass").send_keys("oy19740619")
    token = driver.find_element("name", "token").get_attribute("value")
    driver.find_element("tag name", "form").submit()
    #time.sleep(2)

    # ターゲットページにアクセス
    driver.get("https://my.healmate.jp/talk?code=o5wphl0zfx6rt41#bottom")
    #time.sleep(2)
    # ページ最下部までスクロール
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "container")))
    # ページ全体のHTMLを取得
    html = driver.page_source 
    # ブラウザを閉じる
    driver.quit()  
    # ここでHTMLを確認
    #print(html)
    # HTMLをパースして必要な情報を抽出
    soup = BeautifulSoup(html, "html.parser")
    name_elements = soup.select_one("div.hover")
    nickname = name_elements.get_text(strip=True)
    
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
            time = time_tag.get_text(strip=True) if time_tag else ""
            if msg_tag_self:
                msg = msg_tag_self.get_text(strip=True)
                self_docs.append((current_date, time, "【男性】", msg))
            elif msg_tag_partner:
                msg = msg_tag_partner.get_text(strip=True)
                partner_docs.append((current_date, time, f"【{nickname}】", msg))

    # 全てのメッセージをまとめる
    documents = self_docs + partner_docs

    # 日付と時間でソート
    self_docs_sorted = sorted(
        self_docs,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )
    print(self_docs_sorted[0-1])

    # 日付と時間でソート
    partner_docs_sorted = sorted(
        partner_docs,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )
    print(partner_docs_sorted[0])

    # 日付と時間でソート
    documents_sorted = sorted(
        documents,
        key=lambda x: parse_datetime(x[0], x[1]),
        reverse=True  # 最新順
    )

    # for date, time, role, msg in documents_sorted:
    #     print(f"{date} {time} [{role}] {msg}")

    docs = [
        Document(
            page_content=f"{date} {time} [{role}] {msg}",
            metadata={"source": f"doc_{i}", "id": f"doc_{i}"}
        )
        for i, (date, time, role, msg) in enumerate(documents)
    ]
    #print(docs)

    embeddings = OpenAIEmbeddings()
    # データベースの作成・読み込み
    save_dir = "C:\work\ws_python\GenerationAiCamp\HM\.db"
    if os.path.isdir(save_dir):
        db = Chroma(persist_directory=save_dir, embedding_function=embeddings)
        # 新しい文書を足すときは add_documents を使う
        db.add_documents(docs)
        db.persist()
    else:
        db = Chroma.from_documents(docs, embedding=embeddings, persist_directory=save_dir)
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
    #役割
    あなたは婚外カウンセラーです。女性からのメッセージに対して、魅力的な返信メッセージを作成することが得意です。

    #文脈
    ## 男性と{nickname}は、1カ月前にマッチングしていて、メッセージをやり取りしている。
    ## 男性は{nickname}に好意を持っていて、真剣に交際を考えている。

    # 命令
    ## {nickname}の最新メッセージ内容をもとに今日の出来事を含めて魅力的な返信メッセージを作成してください。

    # 条件
    ## 男性から{nickname}に対する返信メッセージであること。
    ## {nickname}の最新メッセージ内容に対する返信であること。
    ## 返信メッセージは、{nickname}のメッセージ内容にしっかりと応答していること。
    ## ニックネーム（{nickname}）を反映すること。
    ## 今日の出来事を必ず反映すること。
    ## 男性との会話の流れを時系列に把握した上で、 {nickname}の最新メッセージ内容を細かく反映すること。
    ## 現在の時刻に合わせた挨拶を文頭にいれること。
    ## 生成するメッセージには「とのこと」の言葉は使用しないこと。
    ## スマートで紳士的かつ、自然な文体にすること（軽すぎず、堅すぎず）
    ## 丁寧な言葉遣いをベースに、知的なユーモアや思いやりを感じさせる要素を含めること。
    ## 長文になりすぎず、5～10文程度で簡潔にまとめること。
    ## 絵文字を入れること。
    ## 禁止事項：下品な表現、即会い目的と感じる文言。

    # 出力指示
    ## テキストのみ-
    ## 句読点で適度に改行し、読みやすくすること。
    ## パターンを**3種類（知的で落ち着き／甘めでドキッとする／短文クール）**で提示

    # {nickname}の最新メッセージ
    {partner_docs_sorted[0]}

    # 男性の最新メッセージ
    {self_docs_sorted[0]}

    # 今日の出来事
    {today_txt}
    """

    ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
    # print(f"\n\n==================＜メッセージ＞==================\n{ai_msg['answer']}\n\n")
    chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])
    st.write(f"{ai_msg['answer']}")
    print(f"\n\n==================生成メッセージ==================\n{ai_msg['answer']}\n\n")