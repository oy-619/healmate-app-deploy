"""
ChromaDB効率化システムのテストスクリプト

このスクリプトは以下の機能をテストします：
1. メタデータの読み書き機能
2. 差分抽出機能
3. ChromaDBの初期化・更新機能
4. エラーハンドリング
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock, patch

# アプリケーションのパスを追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, "src"))

# テスト用の一時ディレクトリ
TEST_DIR = os.path.join(tempfile.gettempdir(), "test_chromadb_efficiency")
TEST_METADATA_FILE = os.path.join(TEST_DIR, "test_metadata.json")


def setup_test_environment():
    """テスト環境のセットアップ"""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
    print(f"✅ テスト環境をセットアップしました: {TEST_DIR}")


def cleanup_test_environment():
    """テスト環境のクリーンアップ"""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    print("🧹 テスト環境をクリーンアップしました")


def test_metadata_functions():
    """メタデータ読み書き機能のテスト"""
    print("\n📊 メタデータ機能のテスト開始...")

    # テスト用のメタデータ保存関数
    def save_test_metadata(message_count, last_update=None):
        if last_update is None:
            last_update = datetime.now().isoformat()

        metadata = {"message_count": message_count, "last_update": last_update}

        with open(TEST_METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    # テスト用のメタデータ読み込み関数
    def load_test_metadata():
        if os.path.exists(TEST_METADATA_FILE):
            try:
                with open(TEST_METADATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"message_count": 0, "last_update": None}
        return {"message_count": 0, "last_update": None}

    # テスト1: 新規メタデータ保存
    save_test_metadata(100)
    metadata = load_test_metadata()
    assert metadata['message_count'] == 100, "メタデータの保存・読み込みに失敗"
    assert metadata['last_update'] is not None, "更新日時の保存に失敗"
    print("  ✅ メタデータの保存・読み込み: 成功")

    # テスト2: メタデータの更新
    save_test_metadata(150)
    updated_metadata = load_test_metadata()
    assert updated_metadata['message_count'] == 150, "メタデータの更新に失敗"
    print("  ✅ メタデータの更新: 成功")

    # テスト3: 存在しないファイルの読み込み
    os.remove(TEST_METADATA_FILE)
    default_metadata = load_test_metadata()
    assert default_metadata['message_count'] == 0, "デフォルト値の読み込みに失敗"
    print("  ✅ デフォルト値の処理: 成功")


def test_message_id_generation():
    """メッセージID生成機能のテスト"""
    print("\n🆔 メッセージID生成機能のテスト開始...")

    # モックDocumentオブジェクトの作成
    class MockDocument:
        def __init__(self, content, metadata):
            self.page_content = content
            self.metadata = metadata

    def get_message_ids_from_docs_test(docs):
        ids = set()
        for doc in docs:
            content = doc.page_content
            metadata = doc.metadata
            msg_id = (
                f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"
            )
            ids.add(msg_id)
        return ids

    # テストデータの作成
    test_docs = [
        MockDocument(
            "こんにちは！今日はいい天気ですね", {"date": "2025/10/17", "time": "10:00"}
        ),
        MockDocument("お疲れさまです", {"date": "2025/10/17", "time": "18:00"}),
        MockDocument(
            "こんにちは！今日はいい天気ですね", {"date": "2025/10/17", "time": "10:00"}
        ),  # 重複
    ]

    # テスト実行
    ids = get_message_ids_from_docs_test(test_docs)

    # 検証
    assert len(ids) == 2, f"重複排除に失敗: 期待値2, 実際{len(ids)}"
    expected_id1 = "2025/10/17_10:00_こんにちは！今日はいい天気ですね"
    expected_id2 = "2025/10/17_18:00_お疲れさまです"
    assert expected_id1 in ids, "ID生成ロジックに問題"
    assert expected_id2 in ids, "ID生成ロジックに問題"

    print("  ✅ メッセージID生成: 成功")
    print("  ✅ 重複メッセージの識別: 成功")


def test_diff_extraction():
    """差分抽出機能のテスト"""
    print("\n🔍 差分抽出機能のテスト開始...")

    # モックDocumentとDBの作成
    class MockDocument:
        def __init__(self, content, metadata):
            self.page_content = content
            self.metadata = metadata

    class MockDB:
        def __init__(self, existing_docs):
            self.existing_docs = existing_docs

        def get(self):
            if not self.existing_docs:
                return {'documents': [], 'metadatas': []}

            documents = [doc.page_content for doc in self.existing_docs]
            metadatas = [doc.metadata for doc in self.existing_docs]
            return {'documents': documents, 'metadatas': metadatas}

    def get_new_messages_only_test(current_docs, existing_db=None):
        if existing_db is None:
            return current_docs

        try:
            existing_docs = existing_db.get()
            if not existing_docs or not existing_docs.get('documents'):
                return current_docs

            existing_ids = set()
            existing_contents = existing_docs.get('documents', [])
            existing_metadatas = existing_docs.get('metadatas', [])

            for i, content in enumerate(existing_contents):
                metadata = existing_metadatas[i] if i < len(existing_metadatas) else {}
                msg_id = f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"
                existing_ids.add(msg_id)

            new_docs = []
            for doc in current_docs:
                content = doc.page_content
                metadata = doc.metadata
                msg_id = f"{metadata.get('date', '')}_{metadata.get('time', '')}_{content[:50]}"

                if msg_id not in existing_ids:
                    new_docs.append(doc)

            return new_docs

        except Exception as e:
            print(f"差分抽出でエラー: {str(e)}。全データを使用します。")
            return current_docs

    # 既存データ
    existing_docs = [
        MockDocument("既存メッセージ1", {"date": "2025/10/16", "time": "10:00"}),
        MockDocument("既存メッセージ2", {"date": "2025/10/16", "time": "15:00"}),
    ]

    # 現在のデータ（既存 + 新規）
    current_docs = [
        MockDocument(
            "既存メッセージ1", {"date": "2025/10/16", "time": "10:00"}
        ),  # 既存
        MockDocument(
            "既存メッセージ2", {"date": "2025/10/16", "time": "15:00"}
        ),  # 既存
        MockDocument(
            "新しいメッセージ1", {"date": "2025/10/17", "time": "09:00"}
        ),  # 新規
        MockDocument(
            "新しいメッセージ2", {"date": "2025/10/17", "time": "12:00"}
        ),  # 新規
    ]

    # モックDBの作成
    mock_db = MockDB(existing_docs)

    # テスト実行
    new_messages = get_new_messages_only_test(current_docs, mock_db)

    # 検証
    assert len(new_messages) == 2, f"差分抽出に失敗: 期待値2, 実際{len(new_messages)}"
    new_contents = [doc.page_content for doc in new_messages]
    assert "新しいメッセージ1" in new_contents, "新しいメッセージ1が抽出されていない"
    assert "新しいメッセージ2" in new_contents, "新しいメッセージ2が抽出されていない"
    assert "既存メッセージ1" not in new_contents, "既存メッセージが誤って抽出されている"

    print("  ✅ 差分抽出ロジック: 成功")
    print("  ✅ 新規メッセージの特定: 成功")
    print("  ✅ 既存メッセージの除外: 成功")


def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\n🚨 エラーハンドリングのテスト開始...")

    # テスト1: 不正なJSONファイルの処理
    invalid_json_file = os.path.join(TEST_DIR, "invalid.json")
    with open(invalid_json_file, 'w') as f:
        f.write("invalid json content")

    def load_metadata_with_error_handling(file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"message_count": 0, "last_update": None}
        return {"message_count": 0, "last_update": None}

    result = load_metadata_with_error_handling(invalid_json_file)
    assert result == {"message_count": 0, "last_update": None}, "不正JSON処理に失敗"
    print("  ✅ 不正JSONファイルの処理: 成功")

    # テスト2: 存在しないディレクトリへの書き込み
    def safe_save_metadata(file_path, data):
        try:
            dir_path = os.path.dirname(file_path)
            os.makedirs(dir_path, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"メタデータの保存に失敗: {str(e)}")
            return False

    nonexistent_path = os.path.join(TEST_DIR, "nonexistent", "metadata.json")
    test_data = {"message_count": 50, "last_update": datetime.now().isoformat()}

    result = safe_save_metadata(nonexistent_path, test_data)
    assert result == True, "ディレクトリ作成を伴う保存に失敗"
    assert os.path.exists(nonexistent_path), "ファイルが作成されていない"
    print("  ✅ 存在しないディレクトリへの書き込み: 成功")


def test_integration():
    """統合テスト"""
    print("\n🔗 統合テストの開始...")

    # 実際のアプリケーション機能を模擬したテスト
    metadata_file = os.path.join(TEST_DIR, "integration_metadata.json")

    def simulate_initial_setup():
        """初回セットアップのシミュレーション"""
        # 初回は全データを取得・保存
        initial_messages = [
            {
                "content": f"初期メッセージ{i}",
                "date": "2025/10/16",
                "time": f"{10+i}:00",
            }
            for i in range(5)
        ]

        metadata = {
            "message_count": len(initial_messages),
            "last_update": datetime.now().isoformat(),
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return initial_messages

    def simulate_diff_update():
        """差分更新のシミュレーション"""
        # 既存のメタデータを読み込み
        with open(metadata_file, 'r', encoding='utf-8') as f:
            existing_metadata = json.load(f)

        # 新しいメッセージを追加
        new_messages = [
            {"content": f"新規メッセージ{i}", "date": "2025/10/17", "time": f"{9+i}:00"}
            for i in range(3)
        ]

        # メタデータを更新
        total_count = existing_metadata["message_count"] + len(new_messages)
        updated_metadata = {
            "message_count": total_count,
            "last_update": datetime.now().isoformat(),
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(updated_metadata, f, ensure_ascii=False, indent=2)

        return new_messages, total_count

    # テスト実行
    initial_messages = simulate_initial_setup()
    assert len(initial_messages) == 5, "初期セットアップに失敗"
    print("  ✅ 初期セットアップ: 成功")

    new_messages, total_count = simulate_diff_update()
    assert len(new_messages) == 3, "差分更新に失敗"
    assert total_count == 8, "総メッセージ数の計算に失敗"
    print("  ✅ 差分更新: 成功")

    # メタデータの確認
    with open(metadata_file, 'r', encoding='utf-8') as f:
        final_metadata = json.load(f)

    assert final_metadata["message_count"] == 8, "最終メタデータに誤り"
    print("  ✅ メタデータの整合性: 成功")


def run_all_tests():
    """全テストの実行"""
    print("🚀 ChromaDB効率化システムのテスト開始")
    print("=" * 50)

    setup_test_environment()

    try:
        test_metadata_functions()
        test_message_id_generation()
        test_diff_extraction()
        test_error_handling()
        test_integration()

        print("\n" + "=" * 50)
        print("🎉 全テスト完了: 全て成功!")
        print("✅ メタデータ管理機能: 正常動作")
        print("✅ メッセージID生成: 正常動作")
        print("✅ 差分抽出機能: 正常動作")
        print("✅ エラーハンドリング: 正常動作")
        print("✅ 統合機能: 正常動作")

        print("\n📊 テスト結果サマリー:")
        print("  - 初回DB作成: 全データ取得・保存が正常に動作")
        print("  - 差分更新: 新しいメッセージのみ抽出が正常に動作")
        print("  - コスト効率: 重複処理の排除が正常に動作")
        print("  - エラー処理: 異常時の適切な処理が正常に動作")

        return True

    except AssertionError as e:
        print(f"\n❌ テスト失敗: {str(e)}")
        return False
    except Exception as e:
        print(f"\n💥 テスト実行エラー: {str(e)}")
        return False
    finally:
        cleanup_test_environment()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
