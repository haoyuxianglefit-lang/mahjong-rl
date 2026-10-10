@echo off
rem 一键启动日麻对弈：后端(:8765) + 前端(:7100)
chcp 65001 >nul
start "mahjong-backend" /D "D:\Mahjong AI\apps\mahjong-play\backend" "D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8765
timeout /t 3 >nul
start "mahjong-frontend" /D "D:\Mahjong AI\apps\mahjong-play\frontend" cmd /c npm run dev
echo 后端: http://127.0.0.1:8765  前端: http://localhost:7100/
