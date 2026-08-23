@echo off
set "IA_ROOT=__IA_ROOT__"
cd /d "__REPO_DIR__"

if errorlevel 1 (
    echo.
    echo Nao foi possivel acessar a pasta do ai-engine.
    pause
    exit /b 1
)

uv run python application\ia_interativa.py

if errorlevel 1 (
    echo.
    echo O ai-engine terminou com erro.
    pause
    exit /b 1
)
