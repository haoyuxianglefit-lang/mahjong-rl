"""Mortal 模型桥接：加载 checkpoint、创建 mjai.Bot。

Mortal 的 config.py 与 checkpoint 路径都是相对于 Mortal/mortal 目录的，
因此在导入任何 Mortal 模块前必须先 chdir 并设置 MORTAL_CFG。
"""
import os
import sys

MORTAL_DIR = r"D:\Mahjong AI\third_party\Mortal\mortal"
CHECKPOINT_DIR = os.path.join(MORTAL_DIR, "checkpoints")

os.chdir(MORTAL_DIR)
os.environ.setdefault("MORTAL_CFG", "config.toml")
sys.path.insert(0, MORTAL_DIR)

import torch  # noqa: E402

_engine_cache = {}


def list_checkpoints():
    """列出可用的模型权重文件（不含目录）。"""
    if not os.path.isdir(CHECKPOINT_DIR):
        return []
    return sorted(f for f in os.listdir(CHECKPOINT_DIR) if f.endswith(".pth"))


def load_engine(checkpoint: str = "mortal.pth", device: str = "cpu"):
    """加载一个 Mortal checkpoint，返回可复用的 MortalEngine。

    同一个 engine 可被多个座位的 mjai.Bot 共享（对局状态在各自的
    PlayerState 里，engine 本身无状态）。
    """
    key = (checkpoint, device)
    if key in _engine_cache:
        return _engine_cache[key]

    from model import Brain, DQN
    from engine import MortalEngine

    path = os.path.join(CHECKPOINT_DIR, checkpoint)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"checkpoint not found: {path}")

    state = torch.load(path, weights_only=True, map_location="cpu")
    cfg = state["config"]
    version = cfg["control"].get("version", 1)
    num_blocks = cfg["resnet"]["num_blocks"]
    conv_channels = cfg["resnet"]["conv_channels"]

    mortal = Brain(version=version, num_blocks=num_blocks, conv_channels=conv_channels).eval()
    dqn = DQN(version=version).eval()
    mortal.load_state_dict(state["mortal"])
    dqn.load_state_dict(state["current_dqn"])

    engine = MortalEngine(
        mortal,
        dqn,
        version=version,
        is_oracle=False,
        device=torch.device(device),
        enable_amp=False,
        enable_quick_eval=True,
        enable_rule_based_agari_guard=True,
        name=f"mortal:{checkpoint}",
    )
    _engine_cache[key] = engine
    return engine


def make_bot(engine, seat: int):
    """为某个座位创建 mjai 协议 bot。喂 mjai 事件 JSON，返回 mjai 动作 JSON 或 None。"""
    from libriichi.mjai import Bot

    return Bot(engine, seat)


class ProbeEngine:
    """包装 MortalEngine，记录最近一次 react_batch 的 Q 值与合法动作掩码。

    用于给人类座位挂一个"影子 bot"：只喂事件、丢弃它的决策，
    但把模型对每个候选动作的打分留下来，供前端"AI 建议"面板展示。
    """

    def __init__(self, engine):
        self._engine = engine
        # 每次 react_batch 可能包含多行（多个决策点），只保留最后一行，
        # 即对应最新一次决策（也就是当前等待人类行动的时刻）。
        self.last_q = None      # list[float]，长度 46（ACTION_SPACE）
        self.last_mask = None   # list[bool]
        self.calls = 0

    def __getattr__(self, name):
        # Bot 只会用到 engine_type / react_batch 等属性，其余透传。
        return getattr(self._engine, name)

    def react_batch(self, obs, masks, invisible_obs):
        actions, q_out, masks_out, is_greedy = self._engine.react_batch(obs, masks, invisible_obs)
        self.last_q = list(q_out[-1])
        self.last_mask = [bool(m) for m in masks_out[-1]]
        self.calls += 1
        return actions, q_out, masks_out, is_greedy
