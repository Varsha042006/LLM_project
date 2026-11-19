@echo off
echo ========================================================
echo Starting LocalGPT Pro Platform...
echo Frontend: http://localhost:3001
echo Backend:  http://127.0.0.1:8000
echo ========================================================

set "PATH=C:\Users\pc\Downloads\node-bin\node-v24.14.0-win-x64;%PATH%"

echo Starting FastAPI Backend on port 8000...
start "FastAPI Backend" /min "C:\Users\pc\AppData\Local\Programs\Python\Python39\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

echo Starting Next.js Frontend on port 3001...
cd /d "e:\projects\llm\frontend"
start "Next.js Frontend" /min "C:\Users\pc\Downloads\node-bin\node-v24.14.0-win-x64\node.exe" node_modules\next\dist\bin\next start -p 3001

echo.
echo Both servers started successfully!
echo Open http://localhost:3001 in your browser.
echo ========================================================

