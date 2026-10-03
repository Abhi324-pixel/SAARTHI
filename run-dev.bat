@echo off
REM Starts the SAARTHI API (port 8000) and the web app (port 5173) in two windows.
cd /d %~dp0backend
start "SAARTHI API" cmd /k python -m uvicorn app.main:app --port 8000 --host 127.0.0.1 --reload
cd /d %~dp0frontend
start "SAARTHI Web" cmd /k npm run dev
echo.
echo  API: http://127.0.0.1:8000/docs     App: http://127.0.0.1:5173
echo  First time? Run:  python backend\scripts\check_env.py
