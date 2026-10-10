"""mahjong_rl — 多规则麻将强化学习训练框架。

顶层包按职责分层：
- engines/  规则引擎适配层（统一接口 + RuleSpec，规则是配置不是分支）
- models/   模块化网络（共享 encoder + 可插拔 heads + 注册表）
- train/    训练入口（BC / PPO / 蒸馏）
- eval/     评测（轮询赛 / Elo / duplicate format）
- common/   数据管线、日志、seed 工具
"""
__version__ = "0.1.0"
