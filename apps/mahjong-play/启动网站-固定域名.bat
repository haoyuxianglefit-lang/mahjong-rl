@echo off
rem 固定域名模式：启动后端 + 命名隧道，网址恒为 https://mahjongai.com.cn
rem 需要 cloudflared 已登录（C:\Users\admin\.cloudflared\cert.pem）且隧道已创建
chcp 65001 >nul
cd /d "D:\Mahjong AI\apps\mahjong-play"

rem 若后端已在跑则跳过
netstat -ano | findstr :8765 | findstr LISTENING >nul
if errorlevel 1 (
    echo [1/2] 启动后端 ...
    start "mahjong-backend" /min "D:\Mahjong AI\apps\mahjong-play\启动服务-对外.bat"
    timeout /t 8 >nul
) else (
    echo [1/2] 后端已在运行
)

echo [2/2] 启动命名隧道 cloudflared (config.yml) ...
start "mahjong-tunnel" /min "D:\Mahjong AI\apps\mahjong-play\tunnel\cloudflared.exe" tunnel --config "D:\Mahjong AI\apps\mahjong-play\tunnel\config.yml" run

echo.
echo  ============================================
echo    网站地址: https://mahjongai.com.cn
echo    此窗口关闭不影响服务（两个服务在独立窗口运行）
echo  ============================================
timeout /t 5
