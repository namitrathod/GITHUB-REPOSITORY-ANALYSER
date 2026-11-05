@echo off
echo ===============================================================
echo   GitHub Repository Explainer - Local Hybrid AI Launcher
echo   Fast Model (GPU): gemma3:4b  ^|  Smart Model (GPU+RAM): gemma3:12b
echo ===============================================================
echo.

REM Ensure Node.js and Ollama default install paths are in PATH for this session
if exist "C:\Program Files\nodejs" set "PATH=C:\Program Files\nodejs;%PATH%"
if exist "%LOCALAPPDATA%\Programs\Ollama" set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*") do set "PATH=%%P;%%P\Scripts;%PATH%"

REM 1. Check Node.js / npm
where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Node.js / npm not found. Installing Node.js LTS via winget...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    if exist "C:\Program Files\nodejs" set "PATH=C:\Program Files\nodejs;%PATH%"
)

REM 2. Check Python
python --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Python not found. Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*") do set "PATH=%%P;%%P\Scripts;%PATH%"
)

REM 3. Start Backend in a new terminal window
echo Starting FastAPI Backend on http://localhost:8000 ...
start "Repo Explainer Backend" cmd /k "cd /d %~dp0Backend && (if not exist venv python -m venv venv) && call venv\Scripts\activate && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM 4. Start Frontend in a new terminal window
echo Starting React + Vite Frontend on http://localhost:5173 ...
start "Repo Explainer Frontend" cmd /k "cd /d %~dp0Frontend && (if not exist node_modules npm install) && npm run dev"

echo.
echo Both servers are launching in separate windows!
echo Open http://localhost:5173 in your browser once ready.
pause
