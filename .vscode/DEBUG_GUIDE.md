# Healmate App Debug Configuration

## デバッグ設定の概要

このプロジェクトには、以下のデバッグ構成が用意されています：

### 🚀 Streamlit アプリケーション デバッグ

1. **🚀 Streamlit: Main App (healmate_replymsg_strawberry)**
   - メインアプリケーションのデバッグ
   - ポート: 8501
   - ホットリロード対応

2. **💬 Streamlit: Message Generator (healmate_message_gen)**
   - メッセージ生成アプリのデバッグ
   - ポート: 8502
   - ホットリロード対応

3. **🚀🚀 Launch Both Streamlit Apps**
   - 両方のアプリを同時にデバッグ
   - 複合デバッグ構成

### 🐍 Python スクリプト デバッグ

4. **🐍 Python: Current File (Simple)**
   - 現在のファイルを簡単実行
   - justMyCode: true（ユーザーコードのみ）

5. **🔍 Python: Debug Current File (Advanced)**
   - 現在のファイルを詳細デバッグ
   - justMyCode: false（ライブラリコードも含む）
   - 戻り値表示対応

6. **⚡ Python: Main Function Only**
   - healmate_replymsg_strawberry.py の main() 関数のみ実行
   - Streamlit なしでロジックテスト

### 🧪 テスト デバッグ

7. **🧪 Python: Run Tests (pytest)**
   - 全テストをデバッグ実行
   - tests/ フォルダ内のすべてのテスト

8. **🔬 Python: Debug Specific Test**
   - 特定のテストファイルをデバッグ
   - 現在開いているテストファイルを対象

### 🌐 外部プロセス アタッチ

9. **🌐 Attach to Running Streamlit Process**
   - 既に実行中のStreamlitプロセスにアタッチ
   - ポート: 5678

## 使用方法

### 基本的なデバッグの開始

1. **F5** キーを押す または **実行とデバッグ** ビューから設定を選択
2. ブレークポイントを設定したい行の左側をクリック
3. デバッグが開始されます

### Streamlit アプリのデバッグ

1. **🚀 Streamlit: Main App** を選択してF5
2. ブラウザが自動的に開きます (http://localhost:8501)
3. アプリを操作するとブレークポイントで停止します

### ホットリロード デバッグ

- ファイルを保存すると自動的にStreamlitアプリが再読み込みされます
- デバッグセッションは継続されます

### テストのデバッグ

1. テストファイルを開く
2. **🔬 Python: Debug Specific Test** を選択
3. 特定のテスト関数にブレークポイントを設定

## トラブルシューティング

### デバッグが開始されない場合

1. **🔧 Pre-Debug Setup** タスクを実行して環境を確認
2. 仮想環境がアクティブか確認: `./env_new/Scripts/Activate.ps1`
3. **🧹 Clean Debug Environment** タスクでプロセスをクリーンアップ

### ポート競合の場合

- 既存のStreamlitプロセスを終了: `Ctrl+C` または **🧹 Clean Debug Environment**
- 別のポートを使用: 設定の `--server.port` を変更

### ブレークポイントが無視される場合

- `justMyCode: false` の設定を使用
- ライブラリコード内でもデバッグ可能

## 環境変数

デバッグ時に設定される環境変数：

```
PYTHONPATH=${workspaceFolder}/src:${workspaceFolder}
STREAMLIT_SERVER_PORT=8501/8502
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
STREAMLIT_THEME_BASE=light
```

## パフォーマンス デバッグ

- **showReturnValue: true** で関数の戻り値を確認
- **subProcess: true** でサブプロセスもデバッグ対象
- **stopOnEntry: false** でエントリポイントでは停止しない

## 推奨ワークフロー

1. **🚀 Quick Debug Start** タスクで環境準備
2. 適切なデバッグ構成を選択
3. ブレークポイントを設定
4. F5でデバッグ開始
5. 問題解決後、**🧹 Clean Debug Environment** でクリーンアップ
