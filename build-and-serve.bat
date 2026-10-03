@echo off
REM Builds the frontend and serves everything from http://127.0.0.1:8000 (single process).
cd /d %~dp0frontend
call npm install
call npm run build || exit /b 1
cd /d %~dp0backend
python -m uvicorn app.main:app --port 8000 --host 127.0.0.1
