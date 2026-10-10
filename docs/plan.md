# Mahjong RL 学期计划（日麻 · 混合路线 · 10-20h/周 + 游戏级显卡）

> 📌 历史文档：本文写于目录重构（2026-10-11，见 docs/adr/0001）之前，文中的
> `engine/ reports/ Mortal/ mahjong-play/` 等路径已迁移为
> `src/mahjong_rl/engines/ docs/experiments/ third_party/Mortal/ apps/mahjong-play/`。

最终目标：学期末产出一个可演示、可写进简历/GitHub 的立直麻将 RL AI，并沉淀通往 crypto 量化策略的迁移路径。

## 总体路线

1. **站在成熟组件上**：规则引擎与 gym 环境直接用开源的 `cythonriichi`（C++ 引擎的 Python 绑定，Mortal 使用同一引擎）+ Mortal 开源的 gymnasium 环境封装（`github.com/EquationNW/Mortal`），阅读其代码理解设计。
2. **自己写训练管线**：特征编码、模型、BC 训练、PPO 自对弈微调全部自己实现（PyTorch），这是练手和学习 RL 的核心。
3. **以 akochan（开源 alpha-beta 强引擎）作为评测对手**，用四位对局积分（天凤段位规则）衡量强度。
4. 方法学习主线：Suphx（BC→PPO 两阶段）+ Mortal（transformer 编码器 + 专家牌谱 BC）+ LuckyJ（搜索+RL 混合，作为学期末延伸）。

## 技术选型

| 组件 | 选择 | 说明 |
| --- | --- | --- |
| 规则引擎 | cythonriichi（Mortal fork: EquationNW/cythonriichi） | 快速、和牌/副露判定完备，避免自己写规则引擎的时间黑洞 |
| 环境 | Mortal 的 gymnasium wrapper（参考/复用其 `MortalEngine` 思路） | 决策点驱动（摸切/吃碰杠/立直/荣和），而非逐步模拟 |
| 牌谱数据 | 天凤公开 mjlog 牌谱存档（按日期批量下载）+ Mortal 仓库里的转换工具 | BC 阶段约需 50-100 万半庄，优先下载凤桌/上级桌牌谱 |
| 模型 | 小型 Transformer 编码器（3-6M 参数，d_model≈192，4-6 层） | Mortal 量级，3060 级别显卡可训 |
| RL 算法 | PPO（Suphx 方案）+ 对手池自对弈 | 比 Mortal 的 DQN 更主流，课程和资料更多 |
| 评测 | akochan 引擎 + 自建 headless 四人桌轮询 | rank 分布 / 和了率 / 铳率 / 平均顺位 |
| 实验跟踪 | tensorboard 或 wandb + 固定 seed + hydra/argparse 配置 | 复现性是作品集的一部分 |

## 特征与动作设计（Suphx/Mortal 风格）

- 观测编码为 34（牌种）× c 的 plane：手牌、副露、各家舍牌（含立直宣言牌标记）、宝牌/里宝牌指示牌、场上剩余牌估计、局数/本场/立直棒/点数等标量通道。
- 动作 = 候选掩码后的离散集合：切牌 34 + pass（吃/碰/杠回应）+ 立直 + 杠 + 荣和/自摸，无效动作 mask 掉。
- 奖励：半庄结束时按天凤顺位规则给 rank 奖励（如 +60/+20/-20/-60）+ 0.1 × 终局点差；局内不给 reward，靠 value bootstrap（Suphx 同款：一局只在一处给 reward 缓解信用分配问题）。

## 阶段计划（约 16 周）

### Phase 0 — 打基础（第 1-3 周）
- RL 理论：Sutton & Barto 第 1-8 章；OpenAI Spinning Up 的 DQN/PPO 两节；对照学校强化学习课程进度。
- 论文精读：Suphx（arXiv:2003.13590）、Mortal 各版本 release note 与博客、LuckyJ（arXiv:2303.13375）泛读。
- 工程准备：本仓库初始化（uv/conda 环境、README、目录结构如下）、GPU/驱动确认、`cythonriichi` 安装跑通示例。
- **出口标准**：能口头讲清 Suphx 两阶段训练的动机；环境里跑通一局随机对局。

### Phase 1 — 环境与数据（第 3-5 周）
- 封装 gym 环境：决策点 API（obs, candidate_mask, reward, done），写 `features.py` 完成上述 plane 编码，写单元测试（和牌型、振听、役种判定交给引擎，编码函数用固定牌局快照做 golden test）。
- 牌谱管线：下载天凤 mjlog → 解析为 `(obs, action, candidate_mask)` 序列数据集 → 统计决策点分布（切牌/回应副露/立直比例）。
- **出口标准**：BC 数据集落地（≥50 万决策点），`env.step` 与引擎对账 1 万随机动作零误差。

### Phase 2 — 行为克隆 BC（第 6-9 周）
- 实现 Transformer 策略网络 + cross-entropy 损失（只对候选动作归一化）。
- 训练并调参：观察 top-1 / top-3 命中率、按决策类型分桶的准确率。
- 评测：BC 模型上桌 vs 随机/简单贪心策略四位对局，记录 rank 分布与铳率。
- 错误分析：抽样对比模型与专家在相同局面的选择，分类错误模式（牌效差/防守差/副露判断）。
- **出口标准**：BC 模型平均顺位明显优于随机基线（目标 ≤2.5），有 tensorboard 曲线和错误分析报告。

### Phase 3 — PPO 自对弈微调（第 10-13 周）
- 实现 PPO：candidate-mask 的 Categorical 策略、GAE、entropy bonus、value net（共享 encoder + 独立 head）。
- 自对弈 setup：3 个对手槽位轮换填充 —— BC 快照、历史 checkpoint 对手池、随机策略；CPU 引擎多进程向量化采样，3060 上训练。
- 关键技巧（来自 Suphx）：KL 正则或小 lr 防止 BC 学到的专家知识崩掉；reward 只用半庄终局信号。
- 每 N 个 update 做一次评测：vs BC / vs akochan 的 rank 分布，保存 best checkpoint。
- **出口标准**：RL 模型在 100+ 半庄评测中平均顺位稳定优于 BC 模型；训练曲线（reward、entropy、KL）完整可复现。

### Phase 4 — 评测、分析与收尾（第 14-16 周）
- 大规模评测：四方轮询赛（RL / BC / akochan / 规则基线），每人数百半庄，报告 rank 分布、和了率、铳率、立直判断差异。
- 延伸尝试（二选一，有余力都做）：LuckyJ 式浅层搜索（决策时 alpha-beta + 学习价值函数）；或对 BC 模型做蒸馏缩小部署成本。
- 写报告 + GitHub 打磨：README 含方法、曲线、对局示例；简历条目定稿。
- **出口标准**：可复现仓库 + 评测报告 + 简历素材。

## 目录结构（Phase 0 建立）

```
mahjong-rl/
  engine/          # cythonriichi 封装（只读依赖，注明来源）
  env/             # gym 环境、features.py、actions.py、tests/
  data/            # mjlog 下载、解析、数据集构建脚本
  models/          # encoder.py, policy.py, value.py
  train_bc.py
  train_ppo.py
  eval/            # vs akochan、四位轮询赛脚本
  configs/         # 每阶段超参配置
  reports/         # 错误分析、评测报告
```

## 通往 crypto 量化的迁移（学期末再启动，现在只做记录）

- MDP/奖励设计 → 组合调仓问题建模；自对弈评测 → 回测框架与防过拟合；akochan 对局分析 → 交易归因分析。
- 学期末如有余力：用 gym-anytrading 或自写 BTC 环境跑一个 DQN/PPO 调仓小 demo，作为下一段故事的起点。

## 主要风险与对策

| 风险 | 对策 |
| --- | --- |
| 引擎 CPU 采样吞吐不足拖慢 PPO | 多进程向量化 + 减小模型；先小规模验证再放大 |
| BC 命中率不低但实战弱（分布外局面） | 尽早评测对局强度而不是只看准确率；用对手池保持局面多样性 |
| 牌谱下载/解析格式坑 | Phase 1 就完成对账测试；解析器单测覆盖流局、抢杠等罕见分支 |
| 学期中段时间被课业挤压 | 各阶段出口标准即"可交付的最小成果"，BC 模型本身就是能展示的成果 |
