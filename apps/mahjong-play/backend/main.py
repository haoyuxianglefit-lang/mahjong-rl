"""日麻对弈后端 API（FastAPI），同时托管前端 dist 静态文件。

本地开发（在 Mortal venv 下）：
    cd D:\\Mahjong AI\\apps\\mahjong-play\\backend
    ..\\..\\..\\third_party\\Mortal\\.venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765

对外服务（Cloudflare 隧道 / 服务器部署，单端口同时提供网页与 API）：
    ..\\..\\..\\third_party\\Mortal\\.venv\\Scripts\\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8765

接口详见项目根目录 README.md。
"""
import os
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mortal_bridge import list_checkpoints, load_engine
from game_session import GameSession

app = FastAPI(title="Mahjong Play API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions = {}
_sessions_lock = threading.Lock()


class NewGameReq(BaseModel):
    checkpoint: str = "mortal.pth"
    human_seat: int = 0
    seed: int | None = None


class ActionReq(BaseModel):
    type: str
    tile: int | None = None
    consume_tiles: list[int] | None = None


def _get_session(gid: str) -> GameSession:
    with _sessions_lock:
        s = _sessions.get(gid)
    if s is None:
        raise HTTPException(404, f"game not found: {gid}")
    return s


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/checkpoints")
def checkpoints():
    return {"checkpoints": list_checkpoints()}


@app.post("/api/games")
def new_game(req: NewGameReq):
    if not 0 <= req.human_seat <= 3:
        raise HTTPException(400, "human_seat must be in [0, 3]")
    try:
        engine = load_engine(req.checkpoint, device="cpu")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"failed to load model: {e}")

    session = GameSession(engine, human_seat=req.human_seat, seed=req.seed)
    try:
        session.start()
    except Exception as e:
        raise HTTPException(500, f"failed to start game: {e}")

    with _sessions_lock:
        _sessions[session.gid] = session
        # 简单清理：最多保留 20 个会话
        if len(_sessions) > 20:
            for old in sorted(_sessions.values(), key=lambda s: s.created_at)[:-20]:
                _sessions.pop(old.gid, None)
    return session.state()


@app.get("/api/games/{gid}")
def get_state(gid: str):
    return _get_session(gid).state()


@app.post("/api/games/{gid}/action")
def submit_action(gid: str, req: ActionReq):
    session = _get_session(gid)
    try:
        session.submit_action(req.type, req.tile, req.consume_tiles)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"engine error: {e}")
    return session.state()


@app.get("/api/games/{gid}/mjai")
def get_mjai_log(gid: str):
    """完整 mjai 牌谱（天凤/mjai-reviewer 兼容格式，可导出复盘）。"""
    session = _get_session(gid)
    return {"game_id": gid, "log": session.env.mjai_log}


# 前端生产构建（dist）托管：放在所有 /api 路由之后挂载，
# 根路径返回单页应用，/api/* 仍由上面的路由处理。
_DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(_DIST_DIR):
    app.mount("/", StaticFiles(directory=_DIST_DIR, html=True), name="frontend")
else:
    import warnings
    warnings.warn(f"frontend dist not found at {_DIST_DIR}, API-only mode")
