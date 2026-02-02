@echo off
REM Ralph Mode - Windows Batch Installer
REM =====================================
REM
REM Double-click this file or run from Command Prompt
REM

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║                                                           ║
echo ║   🔄 Copilot Ralph Mode Installer                         ║
echo ║                                                           ║
echo ║   Iterative AI Development Loops for GitHub Copilot       ║
echo ║                                                           ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

REM Check Python
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Python not found!
    echo.
    echo   Please install Python 3.9 or later:
    echo     1. Download from https://www.python.org/downloads/
    echo     2. Or run: winget install Python.Python.3.11
    echo.
    echo   Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   ✓ Python %PYTHON_VER% found

REM Check Git
echo [2/4] Checking Git installation...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Git not found!
    echo.
    echo   Please install Git:
    echo     1. Download from https://git-scm.com/download/win
    echo     2. Or run: winget install Git.Git
    pause
    exit /b 1
)
for /f "tokens=3" %%i in ('git --version') do set GIT_VER=%%i
echo   ✓ Git %GIT_VER% found

REM Installation directory
set INSTALL_DIR=%USERPROFILE%\.ralph-mode
echo [3/4] Installing to %INSTALL_DIR%...

if exist "%INSTALL_DIR%" (
    echo   Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull --quiet
) else (
    echo   Cloning repository...
    git clone --quiet https://github.com/sepehrbayat/copilot-ralph-mode.git "%INSTALL_DIR%"
)
echo   ✓ Repository ready

REM Add to PATH instructions
echo [4/4] Setup instructions...
echo.
echo   To add Ralph Mode to your PATH:
echo.
echo   1. Open System Properties ^> Environment Variables
echo   2. Edit "Path" under User variables
echo   3. Add: %INSTALL_DIR%
echo.
echo   Or run this in PowerShell as Administrator:
echo   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";%INSTALL_DIR%", "User")
echo.

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║                                                           ║
echo ║   ✅ Installation Complete!                               ║
echo ║                                                           ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.
echo Quick Start:
echo.
echo   1. Open a new terminal
echo.
echo   2. Navigate to your project:
echo      cd your-project
echo.
echo   3. Start a Ralph loop:
echo      python %INSTALL_DIR%\ralph_mode.py enable "Build a REST API"
echo      %INSTALL_DIR%\ralph-mode.cmd loop
echo.
echo Documentation:
echo   https://github.com/sepehrbayat/copilot-ralph-mode
echo.
pause
