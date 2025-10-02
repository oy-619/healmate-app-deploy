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

load_dotenv()

st.title("いいね付きメッセージ自動生成アプリ")
st.divider()
target_url = st.text_input(label="女性のプロフィールＵＲＬを入力してください。")
interest_txt = st.text_area(label="深堀したい内容を入力してください。")


if st.button("実行"):
    st.divider()
    if not target_url:
        st.error("ＵＲＬを入力してから「実行」ボタンを押してください。")
        st.stop()

    # セッション開始
    session = requests.Session()

    # ログインページにアクセスしてCSRFトークンなどを取得
    login_url = "https://healmate.jp/login"
    res = session.get(login_url)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("input", {"name": "token"}).get("value")  # サイトによって異なる

    # ログイン情報をPOST
    payload = {
        "id": "youcan9160@gmail.com",
        "pass": "oy19740619",
        "token": token
    }
    session.post(login_url, data=payload)

    # ログイン後のターゲットページにアクセス
    documents = []
    res = session.get(target_url)
    soup = BeautifulSoup(res.text, "html.parser")
    target_elements = soup.select("p.detailNickname")
    target_nickname = [el.get_text(strip=True) for el in target_elements]

    # 「自己紹介」タイトルの次に出現する「p.detailText」を取得
    target_introduction = ""
    titles = soup.select("div.detailTitle")
    for title in titles:
        if title.get_text(strip=True) == "自己紹介":
            # 次の兄弟要素を探索
            next_elem = title.find_next_sibling()
            while next_elem:
                if next_elem.name == "p" and "detailText" in next_elem.get("class", []):
                    target_introduction = next_elem.get_text(strip=True)
                    print(f"自己紹介: {target_introduction}")
                    break
                next_elem = next_elem.find_next_sibling()
            break  # 最初の「自己紹介」だけでOK

    target_elements = soup.select("p.detailNickname, p.detailText, div.detailFlaxBetween, div.detailNickname, div.detailTitle, div.detailText")
    target_text = "\n".join([el.get_text(strip=True) for el in target_elements])
    #print(text)
    documents.append(target_text)
    #print(documents)

    # ログイン後のマイページにアクセス
    res = session.get("https://my.healmate.jp/detail?code=iz3v8aswptmuunp&backpage=profile")
    soup = BeautifulSoup(res.text, "html.parser")
    my_elements = soup.select("p.detailNickname")
    my_nickname = [el.get_text(strip=True) for el in my_elements]
    my_elements = soup.select("p.detailNickname, p.detailText, div.detailFlaxBetween, div.detailNickname, div.detailTitle, div.detailText")
    my_text = "\n".join([el.get_text(strip=True) for el in my_elements])
    #print(text)
    documents.append(my_text)
    #print(documents)

    docs = [
        Document(page_content=text, metadata={"source": f"doc_{i}", "id": f"doc_{i}"})
        for i, text in enumerate(documents)
    ]

    print(docs)

    embeddings = OpenAIEmbeddings()
    # データベースの作成
    # index = GPTVectorStoreIndex.from_documents(documents)
    # index.storage_context.persist()
    # save_dir = "/tmp/.db"
    # if os.path.isdir(save_dir):
    #     shutil.rmtree(save_dir)

    # db = Chroma.from_documents(docs, embedding=embeddings, persist_directory=save_dir)
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

    # 入力内容を変数「query」として用意した後、
    # create_retrieval_chainのインスタンス「rag_chain」に対して
    # 「invoke()」メソッドを実行している。引数には入力内容と会話履歴を渡す。
    query = f"{target_nickname}さんは、どのような女性であるかを日本語で些細なことまで詳しく教えてください。"
    ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
    #print(f"\n\n==================＜女性情報＞==================\n{ai_msg['answer']}\n\n")

    # 「extend()」は、リスト同士を結合するメソッド。
    # 入力内容とLLMからの回答内容を要素に持つリストを渡すことで、会話履歴が更新される。
    chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])

    query = f"{my_nickname}さんは、どのような男性であるかを日本語で些細なことまで詳しく教えてください。"
    ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
    #print(f"\n\n==================＜男性情報＞==================\n{ai_msg['answer']}\n\n")
    chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])

    query = f"""
    #役割
    ## あなたは既婚者女性です。既婚者向けマッチングサイトに登録しています。

    #文脈
    ## 男性から1日に多数のメッセージを受け取りますが、その多くは惹かれる内容ではありません。
    ## あなたは「知性」「落ち着き」「余裕」「柔らかな表現」を感じるメッセージに魅力を感じます。
    ## あなたはプロフィールが示す通りの女性です。

    # 命令
    ## 以下の条件に従い、プロフィールの既婚女性が思わず返信したくなるような、
    ## 年上既婚男性からの理想的なメッセージを適度な絵文字も交えて作成してください。

    # 条件
    ## 現在の時刻に合わせた挨拶を文頭にいれること。
    ## 起承転結でメッセージを構成すること。
    ## 生成するメッセージには「～とのこと、～」の言葉は使用しないこと。
    ## {my_nickname}から{target_nickname}さんへのメッセージであること。
    ## {target_nickname}さんのニックネームを利用すること。
    ## {target_nickname}さんと{my_nickname}は面識がないこと。
    ## {target_nickname}さんの情報を細かく反映すること。（特に自己紹介の内容など）
    ## {my_nickname}の情報も考慮すること。（特に自己紹介の内容など）
    ## スマートで紳士的かつ、自然な文体にすること（軽すぎず、堅すぎず）
    ## 丁寧な言葉遣いをベースに、知的なユーモアや余裕を感じさせる要素を含めること。
    ## 長文になりすぎず、5～10文程度で簡潔にまとめること。
    ## 自然で控えめな言い回しにすること。
    ## 絵文字を入れること。
    ## 深堀したい内容をメッセージに細かく反映すること。
    ## 禁止事項：下品な表現、即会い目的と感じる文言。

    # 出力指示
    ## テキストのみ-
    ## 句読点で適度に改行し、読みやすくすること。
    ## パターンを**3種類（知的で落ち着き／甘めでドキッとする／短文クール）**で提示

    # 深堀したい内容
    ## {target_introduction}
    ## {interest_txt}
    
    """

    ai_msg = rag_chain.invoke({"input": query, "chat_history": chat_history})
    # print(f"\n\n==================＜メッセージ＞==================\n{ai_msg['answer']}\n\n")
    chat_history.extend([HumanMessage(content=query), ai_msg["answer"]])
    st.write(f"{ai_msg['answer']}")