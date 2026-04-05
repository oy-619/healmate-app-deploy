# 💬 Healmate App

AI-powered message generation application built with Streamlit and OpenAI.

![Streamlit](https://img.shields.io/badge/Streamlit-ff6b6b?style=flat-square&logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-000000?style=flat-square&logo=openai&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white)

## 🚀 Features

- **AI Message Generation**: Generate contextual messages using OpenAI GPT models
- **Profile Scraping**: Extract information from web profiles  
- **Vector Search**: ChromaDB-powered semantic search
- **Interactive UI**: User-friendly Streamlit interface
- **Multi-environment Support**: Works both locally and on Streamlit Cloud

## 📋 Requirements

- Python 3.11+
- OpenAI API Key
- Chrome/Chromium browser (for web scraping)

## 🛠️ Local Setup

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/healmate-app.git
cd healmate-app-deploy

# Create virtual environment
python -m venv env_new
source env_new/bin/activate  # On Windows: env_new\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create `config/.env` with your OpenAI API key:

```env
OPENAI_API_KEY=sk-proj-your_openai_api_key_here
```

### 3. Run Locally

```bash
streamlit run src/healmate_replymsg_strawberry.py
```

The app will be available at `http://localhost:8501`

## ☁️ Streamlit Cloud Deployment  

### Quick Deploy

[![Deploy to Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)

### Manual Setup

1. **Fork this repository**
2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io/)
   - Connect your GitHub repository
   - Set main file path: `src/healmate_replymsg_strawberry.py`

3. **Configure Secrets:**
   - In Streamlit Cloud dashboard → Settings → Secrets
   - Add your OpenAI API key:
   ```toml
   OPENAI_API_KEY = "sk-proj-your_openai_api_key_here"
   ```

📚 **Detailed deployment guide**: [STREAMLIT_CLOUD_DEPLOY.md](./STREAMLIT_CLOUD_DEPLOY.md)

## 🧪 Testing

Test environment compatibility:

```bash
python test_deployment_compatibility.py
```

This script validates:
- ✅ Local environment setup (.env file)
- ✅ Streamlit Cloud compatibility (secrets.toml)  
- ✅ OpenAI API connectivity
- ✅ All dependencies

## 📁 Project Structure

```
healmate-app-deploy/
├── src/
│   ├── healmate_replymsg_strawberry.py    # Main application
│   ├── config.py                          # Configuration
│   └── ui_components.py                   # UI components
├── config/
│   └── .env                               # Environment variables (local)
├── .streamlit/
│   └── secrets.toml                       # Streamlit secrets (local)
├── data/                                  # Database and temp files
├── requirements.txt                       # Python dependencies  
├── .gitignore                            # Git ignore rules
└── README.md                             # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API Key | Yes |
| `DEBUG` | Enable debug mode | No |
| `LOG_LEVEL` | Logging level | No |

### Streamlit Secrets (Cloud)

For Streamlit Cloud deployment, configure secrets in the app dashboard:

```toml
OPENAI_API_KEY = "your_key_here"
```

## 🔒 Security

- **Never commit API keys** to version control
- Use `.env` files for local development  
- Use Streamlit Secrets for cloud deployment
- All sensitive files are in `.gitignore`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📖 [Deployment Guide](./STREAMLIT_CLOUD_DEPLOY.md)
- 🐛 [Report Issues](https://github.com/YOUR_USERNAME/healmate-app/issues)
- 💬 [Discussions](https://github.com/YOUR_USERNAME/healmate-app/discussions)

---

Made with ❤️ using [Streamlit](https://streamlit.io/) and [OpenAI](https://openai.com/)
