# 🚀 Healmate App - Streamlit Cloud デプロイガイド

Healmate AppをStreamlit Cloudにデプロイする手順を説明します。

## 📋 前提条件

- GitHubアカウント
- StreamIt Cloudアカウント ([https://share.streamlit.io/](https://share.streamlit.io/))
- OpenAI APIキー

## 🔧 Step 1: リポジトリの準備

### 1.1 必要なファイルの確認

以下のファイルが正しく配置されていることを確認：

```
healmate-app-deploy/
├── src/
│   └── healmate_replymsg_strawberry.py  # メインアプリファイル
├── requirements.txt                     # Python依存関係
├── .gitignore                          # 機密ファイル除外設定
└── .streamlit/
    └── secrets.toml                    # ローカル用（Gitにはプッシュしない）
```

### 1.2 .gitignore確認

以下が `.gitignore` に含まれていることを確認：

```gitignore
# Streamlit secrets
.streamlit/secrets.toml
.streamlit/config.toml

# Environment files
config/.env
.env*
```

## 🚀 Step 2: Streamlit Cloudデプロイ

### 2.1 GitHubリポジトリ作成

1. GitHubで新しいリポジトリを作成
2. ローカルのコードをプッシュ：

```bash
git init
git add .
git commit -m "Initial commit: Healmate App"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/healmate-app.git
git push -u origin main
```

⚠️ **重要**: `config/.env` と `.streamlit/secrets.toml` はプッシュしないでください

### 2.2 Streamlit Cloudでデプロイ

1. [Streamlit Cloud](https://share.streamlit.io/) にアクセス
2. 「New app」をクリック  
3. GitHubリポジトリを選択
4. 以下を設定：
   - **Repository**: `your-username/healmate-app`
   - **Branch**: `main`
   - **Main file path**: `src/healmate_replymsg_strawberry.py`

### 2.3 Secrets設定 🔑

デプロイ後、**非常に重要**:

1. Streamlit CloudのApp dashboard → **Settings**
2. **Secrets** タブを開く
3. 以下をコピー&ペースト：

```toml
# OpenAI API設定
OPENAI_API_KEY = "sk-proj-YOUR_ACTUAL_OPENAI_API_KEY_HERE"

# その他のAPI設定（必要に応じて）  
# AZURE_OPENAI_API_KEY = "your_azure_openai_key_here"
# HUGGINGFACE_API_KEY = "your_huggingface_key_here"
```

4. **Save** をクリック
5. アプリが自動的に再起動されます

## 🧪 Step 3: 動作確認

### 3.1 デプロイ後チェックリスト

- [ ] アプリが正常に起動する
- [ ] OpenAI APIキーエラーが表示されない  
- [ ] 「✅ OpenAI Embeddings接続成功」メッセージが表示される
- [ ] 基本機能が動作する

### 3.2 トラブルシューティング

#### ❌ "OPENAI_API_KEYが設定されていません" エラー

**原因**: Streamlit Cloud SecretsでAPIキーが設定されていない

**解決方法**:
1. App Settings → Secrets
2. 正しいAPIキーを設定
3. アプリを再起動

#### ❌ "無効なAPIキー形式です" エラー

**原因**: APIキーの形式が間違っている

**解決方法**:
1. OpenAI APIキーを確認（`sk-` または `sk-proj-` で始まる）
2. コピー時の余分な文字や改行を削除
3. Secretsで正しく設定

#### ❌ アプリが起動しない

**原因**: 依存関係またはファイルパスの問題

**解決方法**:
1. `requirements.txt` が正しく設定されている
2. Main file pathが `src/healmate_replymsg_strawberry.py` になっている
3. Streamlit Cloud logsでエラー詳細を確認

## 🔄 Step 4: アップデート手順

コードを更新してデプロイする場合：

```bash
git add .
git commit -m "Update: 機能追加"  
git push origin main
```

Streamlit Cloudが自動的に新しいバージョンをデプロイします。

## 📚 参考リンク

- [Streamlit Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 🆘 サポート

デプロイに問題がある場合：

1. Streamlit Cloud App logs を確認
2. GitHub Issues で問題を報告
3. [Streamlit Community Forum](https://discuss.streamlit.io/) で質問

---

🎉 **デプロイ成功おめでとうございます！** Healmate Appがクラウドで動作しています。
