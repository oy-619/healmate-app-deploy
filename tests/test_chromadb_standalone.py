"""
ChromaDB効率化システム - 単体テスト用の関数
Streamlitに依存しない独立したテスト関数
"""

import os
import sys
import json
import warnings
from datetime import datetime

# アプリケーションのパスを追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, "src"))

# 必要な設定とインポート
save_dir = os.path.join(project_root, "data", ".db")
metadata_file = os.path.join(project_root, "data", ".db_metadata.json")


def load_db_metadata_test():
    """テスト用：データベースのメタデータを読み込み"""
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"message_count": 0, "last_update": None}
    return {"message_count": 0, "last_update": None}


def save_db_metadata_test(message_count, last_update=None):
    """テスト用：データベースのメタデータを保存"""
    if last_update is None:
        last_update = datetime.now().isoformat()

    metadata = {"message_count": message_count, "last_update": last_update}

    try:
        os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"  📊 メタデータを保存: {metadata_file}")
        return True
    except Exception as e:
        print(f"  ❌ メタデータ保存エラー: {str(e)}")
        return False


def is_db_test():
    """テスト用：データベース存在確認"""
    return os.path.exists(save_dir) and os.listdir(save_dir)


def safe_delete_db_test():
    """テスト用：データベースの安全な削除"""
    try:
        if os.path.exists(save_dir):
            import shutil

            shutil.rmtree(save_dir)
        if os.path.exists(metadata_file):
            os.remove(metadata_file)
        print("  🧹 既存のデータベースとメタデータを削除しました")
        return True
    except Exception as e:
        print(f"  ❌ データベース削除エラー: {str(e)}")
        return False


def create_test_documents():
    """テスト用のドキュメントを作成"""
    from langchain.schema import Document

    test_messages = [
        {
            "content": "こんにちは！よろしくお願いします",
            "date": "2025/10/15",
            "time": "10:00",
            "sender": "partner",
        },
        {
            "content": "こちらこそ、よろしくお願いします",
            "date": "2025/10/15",
            "time": "10:05",
            "sender": "me",
        },
        {
            "content": "今日はいい天気ですね",
            "date": "2025/10/15",
            "time": "10:10",
            "sender": "partner",
        },
        {
            "content": "そうですね！散歩日和です",
            "date": "2025/10/15",
            "time": "10:15",
            "sender": "me",
        },
        {
            "content": "週末の予定はありますか？",
            "date": "2025/10/15",
            "time": "10:20",
            "sender": "partner",
        },
    ]

    documents = []
    for msg in test_messages:
        doc = Document(
            page_content=msg["content"],
            metadata={
                "date": msg["date"],
                "time": msg["time"],
                "sender": msg["sender"],
            },
        )
        documents.append(doc)

    return documents


def safe_init_chromadb_test(force_recreate=False):
    """テスト用：ChromaDBの初期化"""
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    try:
        # 必要なインポート
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings()

        # 強制再作成が指定された場合
        if force_recreate and is_db_test():
            if not safe_delete_db_test():
                return None

        # データベースが存在しない場合（初回作成）
        if not is_db_test():
            print("  📊 初回データベースを作成中...")

            # テスト用のドキュメントを作成
            documents = create_test_documents()

            if not documents:
                print("  ❌ テストドキュメントの作成に失敗しました")
                return None

            # 初回DB作成
            db = Chroma.from_documents(
                documents, embedding=embeddings, persist_directory=save_dir
            )
            db.persist()

            # メタデータ保存
            success = save_db_metadata_test(len(documents))
            if success:
                print(
                    f"  ✅ データベース作成完了: {len(documents)}件のメッセージを保存"
                )
                return db
            else:
                print("  ❌ メタデータの保存に失敗しました")
                return None
        else:
            # 既存のデータベースを読み込み
            print("  📖 既存のデータベースを読み込み中...")
            db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

            metadata = load_db_metadata_test()
            print(f"  📊 既存データ: {metadata.get('message_count', 0)}件のメッセージ")
            return db

    except Exception as e:
        print(f"  💥 データベース初期化エラー: {str(e)}")
        return None


def update_chromadb_with_diff_test():
    """テスト用：差分更新"""
    try:
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings()

        # 既存のデータベースを確認
        if not is_db_test():
            print("  ❌ 既存のデータベースが見つかりません")
            return False

        # 既存のデータベースを読み込み
        db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

        # 新しいテストメッセージを作成（差分として追加）
        from langchain.schema import Document

        new_messages = [
            {
                "content": "明日は雨の予報ですね",
                "date": "2025/10/16",
                "time": "09:00",
                "sender": "partner",
            },
            {
                "content": "傘を持って行きましょう",
                "date": "2025/10/16",
                "time": "09:05",
                "sender": "me",
            },
            {
                "content": "コーヒーでも飲みませんか？",
                "date": "2025/10/16",
                "time": "14:00",
                "sender": "partner",
            },
        ]

        new_documents = []
        for msg in new_messages:
            doc = Document(
                page_content=msg["content"],
                metadata={
                    "date": msg["date"],
                    "time": msg["time"],
                    "sender": msg["sender"],
                },
            )
            new_documents.append(doc)

        # データベースに新しいドキュメントを追加
        db.add_documents(new_documents)
        db.persist()

        # メタデータを更新
        existing_metadata = load_db_metadata_test()
        new_total = existing_metadata.get('message_count', 0) + len(new_documents)
        success = save_db_metadata_test(new_total)

        if success:
            print(f"  ✅ 差分更新完了: {len(new_documents)}件の新しいメッセージを追加")
            print(f"  📊 総メッセージ数: {new_total}件")
            return True
        else:
            print("  ❌ メタデータの更新に失敗しました")
            return False

    except Exception as e:
        print(f"  💥 差分更新エラー: {str(e)}")
        return False


def run_standalone_test():
    """独立したテストの実行"""
    print("🚀 ChromaDB効率化システム - 独立テスト開始")
    print("=" * 50)

    # 環境変数の確認
    import os

    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY が設定されていません")
        return False

    # テスト1: 初回データベース作成
    print("\n📊 テスト1: 初回データベース作成")
    result1 = safe_init_chromadb_test(force_recreate=True)
    if result1:
        print("✅ 初回作成: 成功")
    else:
        print("❌ 初回作成: 失敗")
        return False

    # メタデータ確認
    metadata = load_db_metadata_test()
    print(f"📋 作成後のメタデータ: {metadata}")

    # テスト2: 差分更新
    print("\n🔄 テスト2: 差分更新")
    result2 = update_chromadb_with_diff_test()
    if result2:
        print("✅ 差分更新: 成功")
    else:
        print("❌ 差分更新: 失敗")
        return False

    # 最終メタデータ確認
    final_metadata = load_db_metadata_test()
    print(f"📋 更新後のメタデータ: {final_metadata}")

    # テスト3: データベース検索
    print("\n🔍 テスト3: データベース検索")
    try:
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings()
        db = Chroma(persist_directory=save_dir, embedding_function=embeddings)

        # 検索テスト
        results = db.similarity_search("天気", k=3)
        print(f"  🔍 検索結果: {len(results)}件")
        for i, result in enumerate(results):
            print(f"    {i+1}: {result.page_content[:30]}...")

        print("✅ データベース検索: 成功")

    except Exception as e:
        print(f"❌ データベース検索エラー: {str(e)}")
        return False

    print("\n" + "=" * 50)
    print("🎉 全ての独立テスト完了: 成功!")
    return True


if __name__ == "__main__":
    success = run_standalone_test()
    sys.exit(0 if success else 1)
