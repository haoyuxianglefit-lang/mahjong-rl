# 日麻规则要点（引擎语义权威来源：riichienv / libriichi，以本机 .venv 安装版本为准）

## 基本
- 136 张：万/筒/条 各 36 + 字牌 28；红宝牌 5mr/5pr/5sr
- 四人，半庄（东 1-4 + 南 1-4）；摸切循环，鸣牌优先级：胡 > 杠/碰 > 吃
- 和牌需至少 1 番（役）；振听：同巡内放过同种类和牌后不能再荣和同种牌

## 与本项目相关的引擎语义（踩坑记录）
- `step()` 返回「当前需决策玩家 → Observation」字典；鸣牌窗口轮流询问每个可鸣牌玩家
- `obs.hands` 是按玩家遮蔽的视图，`obs.hands[obs.player_id]` 才是自己手牌（136 制牌 ID）
- 动作比较必须用枚举成员（`a.action_type == ActionType.Discard`）
- 均匀随机策略几乎永远不和牌（向听数降不下去），随机对局全流局是正常现象
- `env.mjai_log` 是全知事件流；`hora` 事件不含役种，需 MjaiReplay 回补

## 观测/动作空间
- obs (1012, 34)；ACTION_SPACE 46（见 src/mahjong_rl/engines/riichi/__init__.py）

## 训练资源
- 天凤凤凰桌 mjlog 牌谱（HuggingFace: hhim8826/tenhou-houou-mjai，212 万局）
- 强引擎对照：akochan；基线权重：Mortal baseline（third_party/Mortal）
