@echo off
cd /d "%~dp0"
if exist "%~dp0.env" (
    for /f "tokens=1,* delims==" %%A in ('findstr /b "BRILLIANTPAY_" "%~dp0.env"') do set "%%A=%%B"
)
if not defined BRILLIANTPAY_SECRET_KEY (
    echo Set BRILLIANTPAY_SECRET_KEY in the ignored .env file or process environment before starting.
    exit /b 1
)
if not defined BRILLIANTPAY_ENV set BRILLIANTPAY_ENV=development

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:5000 wsgi:app
) else if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:5000 wsgi:app
) else (
    python -m waitress --listen=127.0.0.1:5000 wsgi:app
)
