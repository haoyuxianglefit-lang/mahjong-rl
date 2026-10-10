"""日麻（四人东/南场，riichienv 引擎）适配器。

规则要点见 docs/rules/riichi.md；引擎语义踩坑记录见 ../../README.md。
"""
from ..rule_spec import RuleSpec

# libriichi / riichienv 常量（见 mortal-sanma 对照表：四麻 ACTION_SPACE=46, obs=(1012,34)）
RIICHI_SPEC = RuleSpec(
    name="riichi",
    players=4,
    tile_count=136,
    tile_kinds=34,
    action_space=46,
    obs_shape=(1012, 34),
    has_riichi=True,
    has_chii=True,
    has_honors=True,
    multi_win=False,
    notes="天凤四人东/南场规则；红宝牌 5mr/5pr/5sr；振听；宝牌指示牌",
)
