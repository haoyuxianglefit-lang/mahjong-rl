@echo off
rem 生产模式启动：后端托管前端 dist，对外监听 0.0.0.0:8765（配合 cloudflared 隧道）
chcp 65001 >nul
cd /d "D:\Mahjong AI\apps\mahjong-play\backend"
"D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8765
