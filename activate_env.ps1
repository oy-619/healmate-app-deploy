#!/usr/bin/env pwsh
# Healmate App Development Environment Setup

Write-Host "🔧 Setting up Healmate App development environment..." -ForegroundColor Green

# Change to project directory
Set-Location "C:\work\ws_python\Healmate-app\healmate-app-deploy"

# Activate virtual environment
Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
& ".\env_new\Scripts\Activate.ps1"

# Display environment info
Write-Host "✅ Environment activated!" -ForegroundColor Green
Write-Host "📍 Project path: $(Get-Location)" -ForegroundColor Cyan
Write-Host "🐍 Python path: $((& python -c "import sys; print(sys.executable)"))" -ForegroundColor Cyan
Write-Host "📦 Virtual env: $env:VIRTUAL_ENV" -ForegroundColor Cyan

Write-Host "`n🚀 Available commands:" -ForegroundColor Magenta
Write-Host "  streamlit run src/healmate_replymsg_strawberry.py  # Main app" -ForegroundColor White
Write-Host "  streamlit run src/healmate_message_gen.py         # Message gen" -ForegroundColor White
Write-Host "  python -m pytest tests/ -v                       # Run tests" -ForegroundColor White
Write-Host "  black src/ tests/ --check                         # Check formatting" -ForegroundColor White
Write-Host "  flake8 src/ tests/                                # Lint code" -ForegroundColor White

Write-Host "`n🎯 Ready to develop! Happy coding! 💻✨" -ForegroundColor Green
