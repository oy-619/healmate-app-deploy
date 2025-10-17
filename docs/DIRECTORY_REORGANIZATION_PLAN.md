# ディレクトリ構成整理プラン

## 現在の問題点
- ルートディレクトリにファイルが散らばっている
- テストファイル、ドキュメント、メインファイルが混在
- 隠しファイル（.db、メタデータ）がルートに存在

## 整理後の構成

```
healmate-app-deploy/
├── src/                          # メインソースコード
│   ├── healmate_replymsg_strawberry.py
│   └── healmate_message_gen.py
├── tests/                        # テストファイル
│   ├── test_chromadb_efficiency.py
│   ├── test_chromadb_standalone.py
│   └── test_real_system.py
├── docs/                         # ドキュメント
│   ├── README.md
│   └── FINAL_SYSTEM_REPORT.md
├── data/                         # データファイル
│   ├── .db/                      # ChromaDBデータ（移動）
│   └── .db_metadata.json         # メタデータ（移動）
├── config/                       # 設定ファイル
│   ├── .env
│   └── .flake8
├── .vscode/                      # VS Code設定（そのまま）
├── .git/                         # Git設定（そのまま）
├── env/                          # Python仮想環境（そのまま）
├── __pycache__/                  # Python キャッシュ（そのまま）
├── .gitignore                    # Git ignore（そのまま）
├── requirements.txt              # 依存関係（そのまま）
└── healmate-app-deploy.code-workspace  # VS Code workspace（そのまま）
```

## 実行手順
1. 新しいディレクトリを作成
2. ファイルを適切なディレクトリに移動
3. パス参照を更新
4. 動作確認