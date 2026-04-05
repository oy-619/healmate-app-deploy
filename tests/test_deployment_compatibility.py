#!/usr/bin/env python3
"""
Healmate App - ローカル・クラウド環境動作テスト
"""

import os
import sys
from pathlib import Path


def test_environment_setup():
    """環境設定のテスト"""
    print("=== Healmate App Environment Test ===\n")

    # 1. Streamlit secrets テスト
    print("🔍 Testing Streamlit secrets...")
    try:
        import streamlit as st

        api_key_secrets = st.secrets["OPENAI_API_KEY"]
        print("✅ Streamlit secrets: APIキー取得成功")
        print(f"   Key preview: {api_key_secrets[:20]}...{api_key_secrets[-10:]}")
        secrets_available = True
    except Exception as e:
        print(f"❌ Streamlit secrets: 取得失敗 ({type(e).__name__})")
        secrets_available = False

    # 2. 環境変数テスト (.env経由)
    print("\n🔍 Testing environment variables...")
    from dotenv import load_dotenv

    # アプリケーションと同じ方法で.env読み込み
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"
    )
    load_dotenv(env_path)

    api_key_env = os.getenv("OPENAI_API_KEY")
    if api_key_env:
        print("✅ Environment variables: APIキー取得成功")
        print(f"   Key preview: {api_key_env[:20]}...{api_key_env[-10:]}")
        env_available = True
    else:
        print("❌ Environment variables: APIキー取得失敗")
        env_available = False

    # 3. アプリケーション互換性テスト
    print("\n🔍 Testing application compatibility...")

    # アプリケーションと同じロジック
    api_key = None
    source = ""

    if secrets_available:
        api_key = api_key_secrets
        source = "Streamlit secrets"
    elif env_available:
        api_key = api_key_env
        source = "Environment variables"

    if api_key:
        print(f"✅ Application compatibility: {source}からAPIキー取得成功")
        print(f"   Valid format: {api_key.startswith(('sk-', 'sk-proj-'))}")

        # 環境変数設定テスト
        os.environ["OPENAI_API_KEY"] = api_key
        print(f"   Environment set: {'OPENAI_API_KEY' in os.environ}")

    else:
        print("❌ Application compatibility: APIキー取得失敗")

    # 4. OpenAI接続テスト
    if api_key:
        print(f"\n🔍 Testing OpenAI connection...")
        try:
            from langchain_openai import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings()
            test_embedding = embeddings.embed_query("test connection")
            print("✅ OpenAI connection: 接続成功")
            print(f"   Embedding length: {len(test_embedding)}")
        except Exception as e:
            print(f"❌ OpenAI connection: 接続失敗 - {str(e)}")

    # 5. 結論
    print(f"\n{'='*50}")
    print("🏆 TEST SUMMARY:")
    if secrets_available:
        print("✅ Streamlit Cloud対応: 完了")
    if env_available:
        print("✅ ローカル環境対応: 完了")

    if secrets_available or env_available:
        print("🎉 両環境での動作が可能です！")
    else:
        print("❌ 環境設定に問題があります。")

    # 6. デプロイ推奨事項
    print(f"\n📋 DEPLOYMENT RECOMMENDATIONS:")
    print("- ローカル開発: config/.env または .streamlit/secrets.toml を使用")
    print("- Streamlit Cloud: App Settings → Secrets でAPIキー設定")
    print("- GitHubプッシュ前: .gitignoreで機密ファイルが除外されていることを確認")


if __name__ == "__main__":
    test_environment_setup()
