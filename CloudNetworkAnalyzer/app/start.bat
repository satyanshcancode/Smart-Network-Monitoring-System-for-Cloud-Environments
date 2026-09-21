@echo off
chcp 65001 >nul
cls

echo ==============================================
echo   Adaptive Middleware Prototype Launcher
echo ==============================================
echo.

REM Check prerequisites
echo Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed
    exit /b 1
)

node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed
    exit /b 1
)

echo ✓ All prerequisites met
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Install backend dependencies if needed
if not exist "backend\__pycache__" (
    echo Installing Python dependencies...
    cd backend
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo Error: Failed to install Python dependencies
        exit /b 1
    )
    cd ..
    echo ✓ Python dependencies installed
)

REM Install frontend dependencies if needed
if not exist "node_modules" (
    echo Installing Node.js dependencies...
    call npm install -q
    if errorlevel 1 (
        echo Error: Failed to install Node.js dependencies
        exit /b 1
    )
    echo ✓ Node.js dependencies installed
)

echo.
echo ==============================================
echo   Starting Services
echo ==============================================
echo.

REM Start backend
echo Starting Backend Server...
cd backend
start "Backend Server" python main.py
cd ..

timeout /t 2 /nobreak >nul
echo ✓ Backend running on http://localhost:8000
echo.

REM Start frontend
echo Starting Frontend Development Server...
start "Frontend Server" npm run dev

timeout /t 3 /nobreak >nul
echo ✓ Frontend running on http://localhost:5173
echo.

echo ==============================================
echo   Services Started Successfully!
echo ==============================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo   Close this window to stop both services
echo.
echo ==============================================

pause
