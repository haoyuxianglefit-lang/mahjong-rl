"""riichienv 引擎适配器 —— MahjongEngine 接口的第一个实现（规则迁移的接口契约样板）。"""
from __future__ import annotations

import riichienv
from riichienv import GameType, RiichiEnv

from ...engines.base import MahjongEngine
from ...engines import register_engine
from . import RIICHI_SPEC

_GAME_MODES = {
    "hanchan": GameType.YON_HANCHAN,
    "tonpu": GameType.YON_TONPUSEN,
    "ikkyoku": GameType.YON_IKKYOKU,
}


@register_engine("riichi")
class RiichiEngine(MahjongEngine):
    """四人日麻。MahjongEngine 语义与 riichienv 一致，直接转发。

    Usage:
        from mahjong_rl.engines import make_engine
        env = make_engine("riichi", seed=42)
        obs = env.reset()
        ...
    """
    SPEC = RIICHI_SPEC

    def __init__(self, seed: int | None = None, game_mode: str = "hanchan"):
        self._game_mode = game_mode
        self._env = RiichiEnv(game_mode=_GAME_MODES[game_mode], seed=seed)

    def reset(self, seed: int | None = None):
        if seed is not None:
            self._env = RiichiEnv(game_mode=_GAME_MODES[self._game_mode], seed=seed)
        return self._env.reset()

    def step(self, actions: dict):
        return self._env.step(actions)

    @property
    def done(self) -> bool:
        return len(self._env.mjai_log) > 0 and self._env.mjai_log[-1].get("type") == "end_game"

    @property
    def mjai_log(self):
        """全知事件流（mjai 协议 JSON list）。"""
        return self._env.mjai_log
