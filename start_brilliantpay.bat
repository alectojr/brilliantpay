@echo off
cd /d "%~dp0"
set BRILLIANTPAY_SECRET_KEY=3njRru5Q2AaFORD0LQnCTJLBn38De3T9uA5iNIKwZdw
set BRILLIANTPAY_ENV=production
REM Optional first-time admin (remove after first run)
REM set BRILLIANTPAY_ADMIN_USERNAME=admin
REM set BRILLIANTPAY_ADMIN_PASSWORD=BrilliantAdmin1
REM set BRILLIANTPAY_ADMIN_EMAIL=

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:5000 app:app
) else if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:5000 app:app
) else (
    python -m waitress --listen=127.0.0.1:5000 app:app
)