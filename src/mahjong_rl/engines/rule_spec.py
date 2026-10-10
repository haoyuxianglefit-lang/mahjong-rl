"""规则描述（RuleSpec）—— 所有规则差异收进配置，引擎/编码/动作空间从此派生。

新增一种规则 = 写一份 RuleSpec（+ 引擎侧少量规则钩子），
不要在整个代码库里加 if-else 分支。
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuleSpec:
    """一种麻将规则的完整机器可读描述。

    Attributes:
        name:         规则标识，如 "riichi" / "sanma" / "sichuan_xuezhan"
        players:      玩家数（4 或 3）
        tile_count:   总牌张数（日麻 136 / 三麻、川麻 108）
        tile_kinds:   牌种数（34 制编码的行数，未用牌行置零以保持迁移兼容）
        action_space: 动作空间大小（与引擎动作枚举一致）
        obs_shape:    观测编码形状 (channels, tile_kinds)
        has_riichi:   是否有立直
        has_chii:     是否有吃
        has_honors:   是否有字牌（风牌/三元牌）
        queque:       开局是否定缺（川麻）——定缺动作占一个独立决策点
        multi_win:    一家和牌后牌局是否继续（血战到底）
        notes:        规则要点备注（番型、结算、地方变体）
    """
    name: str
    players: int
    tile_count: int
    tile_kinds: int
    action_space: int
    obs_shape: tuple
    has_riichi: bool = False
    has_chii: bool = True
    has_honors: bool = True
    queque: bool = False
    multi_win: bool = False
    notes: str = ""
    extra: dict = field(default_factory=dict)
