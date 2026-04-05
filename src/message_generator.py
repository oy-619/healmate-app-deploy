"""
Message generation functionality using LangChain and OpenAI.

This module handles AI-based message generation using retrieved profile information.
"""

from datetime import datetime
from typing import List

from dotenv import load_dotenv
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()


class MessageGenerator:
    """AI-based message generator for dating app interactions."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        self.embeddings = OpenAIEmbeddings()
        self.chat_history = []
        self.rag_chain = None

    def setup_rag_system(self, documents: List[str]) -> None:
        """
        Setup RAG (Retrieval-Augmented Generation) system.

        Args:
            documents (List[str]): List of document texts to index
        """
        # Create documents
        docs = [
            Document(
                page_content=text, metadata={"source": f"doc_{i}", "id": f"doc_{i}"}
            )
            for i, text in enumerate(documents)
        ]

        # Create vector database
        db = Chroma.from_documents(docs, embedding=self.embeddings)
        db.persist()
        retriever = db.as_retriever()

        # Setup question generator
        question_generator_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "会話履歴と最新の入力をもとに、"
                    "会話履歴なしでも理解できる独立した入力テキストを生成してください。",
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        history_aware_retriever = create_history_aware_retriever(
            self.llm, retriever, question_generator_prompt
        )

        # Setup question-answer system
        question_answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "あなたは優秀な質問応答アシスタントです。\n"
                    "以下のcontextを使用して質問に答えてください。\n"
                    "また答えが分からない場合は、無理に答えようとせず「分からない」という旨を答えてください。\n"
                    "{context}",
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        question_answer_chain = create_stuff_documents_chain(
            self.llm, question_answer_prompt
        )

        # Create final RAG chain
        self.rag_chain = create_retrieval_chain(
            history_aware_retriever, question_answer_chain
        )

        # Reset chat history
        self.chat_history = []

    def analyze_profiles(self, target_nickname: str, my_nickname: str) -> None:
        """
        Analyze both user profiles and update chat history.

        Args:
            target_nickname (str): Target user's nickname
            my_nickname (str): Current user's nickname
        """
        if not self.rag_chain:
            raise ValueError("RAG system not initialized. Call setup_rag_system first.")

        # Analyze female profile
        female_query = (
            f"{target_nickname}さんは、どのような女性であるかを"
            "日本語で些細なことまで詳しく教えてください。"
        )
        ai_msg = self.rag_chain.invoke(
            {"input": female_query, "chat_history": self.chat_history}
        )
        self.chat_history.extend([HumanMessage(content=female_query), ai_msg["answer"]])

        # Analyze male profile
        male_query = (
            f"{my_nickname}さんは、どのような男性であるかを"
            "日本語で些細なことまで詳しく教えてください。"
        )
        ai_msg = self.rag_chain.invoke(
            {"input": male_query, "chat_history": self.chat_history}
        )
        self.chat_history.extend([HumanMessage(content=male_query), ai_msg["answer"]])

    def generate_message(
        self,
        target_nickname: str,
        my_nickname: str,
        target_introduction: str,
        interest_txt: str,
    ) -> str:
        """
        Generate personalized message.

        Args:
            target_nickname (str): Target user's nickname
            my_nickname (str): Current user's nickname
            target_introduction (str): Target user's self-introduction
            interest_txt (str): Areas of interest to explore

        Returns:
            str: Generated message
        """
        if not self.rag_chain:
            raise ValueError("RAG system not initialized. Call setup_rag_system first.")

        # Get current time for greeting
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # Create message generation prompt
        message_query = f"""
役割
# あなたは港区女子です。洗練された価値観と自立心を持ち、上質な体験や知的な会話を大切にしています。

文脈
# 多くの男性からメッセージが届きますが、ありきたりな内容や軽いノリには惹かれません。
# あなたが魅力を感じるのは、知性・余裕・品の良さ・共感力・スマートな距離感・特別感を感じるメッセージです。
# プロフィールや自己紹介に書かれている内容を大切にしています。

命令
# 以下の条件に従い、港区女子が「この人に会ってみたい」と思うような、年上男性からの理想的なメッセージを、適度な絵文字も交えて作成してください。

条件
# 現在時刻({current_time})に合わせた自然で上品な挨拶を文頭に入れること。
# 起承転結でメッセージを構成すること。
# 「～とのこと、～」の表現は使わないこと。
# {my_nickname}から{target_nickname}さんへのメッセージであること。
# {target_nickname}さんのニックネームを文中で自然に使うこと。
# {target_nickname}さんと{my_nickname}は初対面であることを前提とすること。
# {target_nickname}さんのプロフィール情報（特に自己紹介）や価値観、趣味、日常などを具体的に反映すること。
# {my_nickname}の情報もさりげなく織り交ぜること。
# 文体はスマートで紳士的、落ち着きと余裕を感じさせるものにすること（軽すぎず、堅すぎず）。
# 丁寧な言葉遣いをベースに、知的なユーモアや上質な共感、特別感を演出する要素を含めること。
# 長文になりすぎず、5～10文程度で簡潔にまとめること。
# 自然な言い回しを心がけること。
# 絵文字は上品に、過剰にならないように使うこと。
# 深堀したい内容をメッセージに具体的に反映すること。
# 禁止事項：下品な表現、即会い目的と感じる文言、馴れ馴れしさ。

出力指示
# テキストのみ
# 句読点で適度に改行し、読みやすくすること。
# 以下の3パターンで提示すること：
1. 知的で落ち着きのあるメッセージ
2. 上質で特別感のあるメッセージ
3. 短文でクールなメッセージ
4. 甘めでドキッとするメッセージ
5. 少しフレンドリーで癒されるメッセージ

# 深堀したい内容
## {target_introduction}
## {interest_txt}
"""

        ai_msg = self.rag_chain.invoke(
            {"input": message_query, "chat_history": self.chat_history}
        )

        self.chat_history.extend(
            [HumanMessage(content=message_query), ai_msg["answer"]]
        )

        return ai_msg["answer"]
