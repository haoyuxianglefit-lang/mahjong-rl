"""一键外网分享：确保本地后端在跑，启动 cloudflared 临时隧道，打印外网地址。

用法（双击 启动外网分享.bat 或命令行）：
    "D:\\Mahjong AI\\Mortal\\.venv\\Scripts\\python.exe" launch_share.py

原理：后端 uvicorn(8765) 托管网页+API；cloudflared 临时隧道把 8765 暴露为
https://xxx.trycloudflare.com（免费、无需账号、自带 HTTPS）。
注意：这个窗口和电脑都不能关，关了朋友就访问不了。
"""
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
PY = Path(r"D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe")
CLOUDFLARED = ROOT / "tunnel" / "cloudflared.exe"
LOG = ROOT / "tunnel" / "tunnel.log"
PORT = 8765


def port_open() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def start_backend() -> None:
    print("[1/2] 启动后端 (uvicorn :8765) ...")
    subprocess.Popen(
        [str(PY), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=str(BACKEND_DIR), creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
    for _ in range(60):
        if port_open():
            print("      后端已就绪")
            return
        time.sleep(2)
    sys.exit("后端启动超时，请查看 启动服务-对外.bat 手动排查")


def main() -> None:
    if not port_open():
        start_backend()
    else:
        print("[1/2] 后端已在运行")

    print("[2/2] 启动 cloudflared 临时隧道 ...")
    log = open(LOG, "w")
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", f"http://localhost:{PORT}", "--no-autoupdate"],
        stdout=log, stderr=subprocess.STDOUT, close_fds=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE)
    log.close()

    url = None
    for _ in range(45):
        time.sleep(3)
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", LOG.read_text(errors="ignore"))
        if m:
            url = m.group(0)
            break
    if not url:
        sys.exit("隧道启动失败，查看 tunnel\\tunnel.log")

    print()
    print("=" * 60)
    print("  分享地址（已复制到剪贴板）：")
    print(f"    {url}")
    print("=" * 60)
    try:
        import tkinter  # noqa
        r = tkinter.Tk(); r.withdraw()
        r.clipboard_clear(); r.clipboard_append(url); r.update(); r.destroy()
    except Exception:
        pass
    print("此窗口请勿关闭（关闭后外网无法访问）。Ctrl+C 退出。")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
