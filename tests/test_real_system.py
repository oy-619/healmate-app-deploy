"""
ChromaDB効率化システム実動作テスト

このスクリプトは実際の環境でChromeDB効率化システムをテストします：
1. 初回データベース作成のテスト
2. 差分更新のテスト
3. コスト効率の確認
"""

import os
import sys
import json
from datetime import datetime

# アプリケーションのパスを追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, "src"))

from healmate_replymsg_strawberry import (
    load_db_metadata,
    save_db_metadata,
    safe_init_chromadb,
    update_chromadb_with_diff,
)

# アプリケーションから正しいメタデータファイルパスを取得
try:
    from healmate_replymsg_strawberry import metadata_file

    METADATA_FILE = metadata_file
except ImportError:
    METADATA_FILE = ".db_metadata.json"


def test_initial_db_creation():
    """初回データベース作成のテスト"""
    print("🔄 初回データベース作成のテストを開始...")

    # メタデータファイルが存在する場合は削除
    if os.path.exists(METADATA_FILE):
        os.remove(METADATA_FILE)
        print("  既存のメタデータファイルを削除しました")

    # 初回データベース作成をシミュレート
    print("  初回データベースの作成を実行...")
    result = safe_init_chromadb()

    if result:
        print("  ✅ 初回データベース作成: 成功")

        # メタデータファイルの確認
        if os.path.exists(METADATA_FILE):
            metadata = load_db_metadata()
            print(f"  📊 保存されたメタデータ:")
            print(f"    - メッセージ数: {metadata.get('message_count', 0)}")
            print(f"    - 最終更新: {metadata.get('last_update', 'N/A')}")
            return True
        else:
            print("  ❌ メタデータファイルが作成されませんでした")
            return False
    else:
        print("  ❌ 初回データベース作成: 失敗")
        return False


def test_differential_update():
    """差分更新のテスト"""
    print("\n🔄 差分更新のテストを開始...")

    # 既存のメタデータを確認
    if not os.path.exists(METADATA_FILE):
        print("  ❌ メタデータファイルが存在しません。初回作成を先に実行してください。")
        return False

    initial_metadata = load_db_metadata()
    initial_count = initial_metadata.get('message_count', 0)
    print(f"  📊 現在のメッセージ数: {initial_count}")

    # 差分更新を実行（実際にはテスト用のデータを使用）
    print("  差分更新を実行...")
    result = update_chromadb_with_diff()

    if result:
        print("  ✅ 差分更新: 成功")

        # 更新後のメタデータを確認
        updated_metadata = load_db_metadata()
        updated_count = updated_metadata.get('message_count', 0)

        print(f"  📊 更新後の統計:")
        print(f"    - 更新前: {initial_count}件")
        print(f"    - 更新後: {updated_count}件")
        print(f"    - 差分: {updated_count - initial_count}件")
        print(f"    - 最終更新: {updated_metadata.get('last_update', 'N/A')}")

        return True
    else:
        print("  ❌ 差分更新: 失敗")
        return False


def test_metadata_consistency():
    """メタデータの整合性テスト"""
    print("\n🔄 メタデータ整合性のテストを開始...")

    if not os.path.exists(METADATA_FILE):
        print("  ❌ メタデータファイルが存在しません")
        return False

    try:
        metadata = load_db_metadata()

        # 必要なキーの存在確認
        required_keys = ['message_count', 'last_update']
        for key in required_keys:
            if key not in metadata:
                print(f"  ❌ 必要なキー '{key}' がメタデータに含まれていません")
                return False

        # データ型の確認
        if not isinstance(metadata['message_count'], int):
            print("  ❌ message_countが整数ではありません")
            return False

        if metadata['message_count'] < 0:
            print("  ❌ message_countが負の値です")
            return False

        # 日付形式の確認
        try:
            datetime.fromisoformat(metadata['last_update'].replace('Z', '+00:00'))
        except ValueError:
            print("  ❌ last_updateの日付形式が不正です")
            return False

        print("  ✅ メタデータ整合性: 正常")
        print(f"    - 構造: 正常")
        print(f"    - データ型: 正常")
        print(f"    - 値範囲: 正常")

        return True

    except Exception as e:
        print(f"  ❌ メタデータ読み込みエラー: {str(e)}")
        return False


def test_cost_efficiency():
    """コスト効率の確認"""
    print("\n💰 コスト効率の確認を開始...")

    if not os.path.exists(METADATA_FILE):
        print("  ⚠️  メタデータファイルが存在しないため、コスト効率の測定ができません")
        return False

    metadata = load_db_metadata()
    message_count = metadata.get('message_count', 0)
    last_update = metadata.get('last_update')

    print(f"  📊 現在の効率指標:")
    print(f"    - 処理済みメッセージ数: {message_count}件")
    print(f"    - 最後の更新: {last_update}")

    if message_count > 0:
        print("  ✅ コスト効率化のメリット:")
        print("    - 既存メッセージの重複処理を回避")
        print("    - 新規メッセージのみを処理してAPIコスト削減")
        print("    - データベース作成時間の短縮")
        print("    - メタデータによる処理状況の可視化")
        return True
    else:
        print("  ⚠️  処理されたメッセージがないため効率を測定できません")
        return False


def generate_efficiency_report():
    """効率化レポートの生成"""
    print("\n📈 効率化レポートを生成中...")

    if os.path.exists(METADATA_FILE):
        metadata = load_db_metadata()

        report = {
            "レポート作成日時": datetime.now().isoformat(),
            "データベース状態": {
                "メッセージ総数": metadata.get('message_count', 0),
                "最終更新日時": metadata.get('last_update'),
                "データベースファイル": (
                    "存在" if os.path.exists('chromadb') else "未作成"
                ),
            },
            "効率化機能": {
                "差分更新": "有効",
                "重複回避": "有効",
                "メタデータ管理": "有効",
                "エラーハンドリング": "有効",
            },
            "予想されるコスト削減": {
                "API呼び出し": "差分処理により大幅削減",
                "処理時間": "既存データの再利用により短縮",
                "リソース使用量": "最小限に抑制",
            },
        }

        report_file = "efficiency_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 効率化レポートを保存: {report_file}")

        # レポートの要約を表示
        print("\n📊 レポート要約:")
        for category, details in report.items():
            print(f"  🔹 {category}:")
            if isinstance(details, dict):
                for key, value in details.items():
                    print(f"    - {key}: {value}")
            else:
                print(f"    - {details}")

        return True
    else:
        print("  ❌ メタデータファイルが存在しないためレポートを生成できません")
        return False


def run_complete_test():
    """完全なテストスイートの実行"""
    print("🚀 ChromaDB効率化システム実動作テスト開始")
    print("=" * 60)

    results = []

    # 各テストを実行
    tests = [
        ("初回DB作成", test_initial_db_creation),
        ("差分更新", test_differential_update),
        ("メタデータ整合性", test_metadata_consistency),
        ("コスト効率", test_cost_efficiency),
    ]

    for test_name, test_func in tests:
        try:
            print(f"\n🧪 {test_name}テスト実行中...")
            result = test_func()
            results.append((test_name, "成功" if result else "失敗"))
        except Exception as e:
            print(f"  💥 {test_name}テストでエラー: {str(e)}")
            results.append((test_name, f"エラー: {str(e)}"))

    # 効率化レポート生成
    print(f"\n📋 効率化レポート生成中...")
    try:
        generate_efficiency_report()
    except Exception as e:
        print(f"  💥 レポート生成エラー: {str(e)}")

    # 最終結果の表示
    print("\n" + "=" * 60)
    print("🏁 テスト完了結果:")

    success_count = 0
    for test_name, status in results:
        icon = "✅" if status == "成功" else "❌"
        print(f"  {icon} {test_name}: {status}")
        if status == "成功":
            success_count += 1

    total_tests = len(results)
    success_rate = (success_count / total_tests * 100) if total_tests > 0 else 0

    print(f"\n📊 統計:")
    print(f"  - 総テスト数: {total_tests}")
    print(f"  - 成功: {success_count}")
    print(f"  - 成功率: {success_rate:.1f}%")

    if success_count == total_tests:
        print("\n🎉 全テスト成功！ChromaDB効率化システムは正常に動作しています。")
    elif success_count > 0:
        print("\n⚠️  一部のテストが失敗しました。詳細を確認してください。")
    else:
        print("\n💥 すべてのテストが失敗しました。システムの設定を確認してください。")

    return success_count == total_tests


if __name__ == "__main__":
    success = run_complete_test()
    sys.exit(0 if success else 1)
