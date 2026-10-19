@echo off
cd /d "%~dp0"
set BRILLIANTPAY_SECRET_KEY=3njRru5Q2AaFORD0LQnCTJLBn38De3T9uA5iNIKwZdw
set BRILLIANTPAY_ENV=production
REM Optional first-time admin (remove after first run)
REM set BRILLIANTPAY_ADMIN_USERNAME=admin
REM set BRILLIANTPAY_ADMIN_PASSWORD=BrilliantAdmin1
REM set BRILLIANTPAY_ADMIN_EMAIL=

python -m waitress --listen=127.0.0.1:5000 app:app