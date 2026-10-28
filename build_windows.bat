@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON=%~dp0venv\Scripts\python.exe"
) else (
    echo Create a virtual environment and install requirements.txt first.
    exit /b 1
)

set "BUILD_ROOT=dist\build-%RANDOM%-%RANDOM%"
"%PYTHON%" -m PyInstaller --noconfirm --distpath "%BUILD_ROOT%" --workpath build\release BrilliantPayClient.spec
if errorlevel 1 exit /b 1

set "ISCC="
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo The desktop app was built in %BUILD_ROOT%\BrilliantPay.
    echo To build the installation file, install Inno Setup 6 and run:
    echo   ISCC.exe /DBuildRoot="%BUILD_ROOT%" installer.iss
    exit /b 0
)

"%ISCC%" /DBuildRoot="%BUILD_ROOT%" installer.iss
if errorlevel 1 exit /b 1
echo.
echo Installer created at dist\installer\BrilliantPaySetup.exe
