@echo off
rem 一键外网分享：启动后端 + cloudflared 临时隧道，打印可发给朋友的网址
chcp 65001 >nul
cd /d "D:\Mahjong AI\apps\mahjong-play"
"D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe" launch_share.py
pause
