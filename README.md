# Mahjong RL

立直麻将（日麻）强化学习 AI —— 学期项目，最终目标：训练出可与开源强引擎对局的 RL 策略，并沉淀通往 crypto 量化策略的迁移经验。

## 路线

- **规则引擎 / 环境**：复用开源引擎（Mortal 同款，C++/Rust 核心 + Python 绑定）+ gymnasium 封装；多规则统一接口见 `src/mahjong_rl/engines/`
- **训练管线**：自研（PyTorch）——特征编码、模型、行为克隆（BC）、PPO 自对弈微调
- **方法主线**：[Suphx](https://arxiv.org/abs/2003.13590)（专家牌谱 BC → PPO 两阶段）+ Mortal（小型 Transformer 编码器）+ [LuckyJ](https://arxiv.org/abs/2303.13375)（搜索 + RL 混合，学期末延伸）
- **评测**：akochan（alpha-beta 强引擎）+ 自建 headless 四位轮询赛，按天凤顺位规则计分
- **扩展方向**：规则迁移（川麻/三麻，见 `docs/rules/`）与模块融合训练（多 encoder/head 版本组合）

## 架构约定（2026-10-11 起，详见 docs/adr/0001）

- **规则是配置**：规则差异全部收进 `RuleSpec`（`src/mahjong_rl/engines/rule_spec.py` + `configs/rules/*.yaml`）
- **模型模块化**：encoder / heads 经注册表组合（`src/mahjong_rl/models/registry.py`），融合关系写 manifest（`configs/models/`）
- **实验快照**：每次训练输出到 `runs/<run_id>/`（展开配置快照 + git hash + checkpoint + tensorboard + eval.json）
- 架构决策记录见 `docs/adr/`；规则对照表见 `docs/rules/`；路线图见 `docs/plan.md`

## 目录结构

```
src/mahjong_rl/   # 核心代码包：engines/ models/ train/ eval/ common/
configs/          # 配置模板（rules/ models/ data/ exp/ 四层）
docs/             # 长期文档：plan.md rules/ adr/ research/ experiments/ refs/
data/             # 牌谱数据集（不入 git），按规则分子目录
runs/             # 实验输出（不入 git）：runs/<run_id>/{config快照,checkpoints,tb,eval.json}
eval_results/     # 跨 run 评测对比（不入 git）
tools/            # replay_viewer.py 等独立小工具
scripts/          # 运维脚本，按 build/（编译）data/（数据集）ops/（远程机）三层归类
third_party/
  Mortal/         # 参考实现：Equim-chan/Mortal 完整 clone（不入 git，后续改 submodule；
                  # ✅ 2026-09-27 已在本机完整复现：venv + libriichi.pyd + 212万局数据集
                  # + baseline 权重，环境差异与重建步骤见
                  # third_party/Mortal/TRAINING_GUIDE.md 第 6 节）
.toolchain/       # Rust 工具链（rustup/cargo，gnu 版；cargo 命令必须在 cmd 里跑，见下）
apps/
  mahjong-play/   # 日麻对弈 Web 程序（人类 vs 本地模型，推理/展示前端，不依赖训练代码）
installers/       # 新机环境安装包留档（Miniconda/rustup/MinGW/torch wheel，稳定后可删）
```

⚠️ 本机 **Smart App Control 开启**：Git Bash 里跑 cargo 会被拦（error 4551），编译/测试统一用 `scripts/build/build_libriichi.bat`、`scripts/build/cargo_test.bat`（cmd 批处理）。

## 环境

Windows，RTX 5090 (32GB)（2026-09 迁自旧笔记本 RTX 3060；旧机文件仍在 `\\LAPTOP-CTIU4UNF\F_Laptop`）。

```bash
# Python 3.10.18 来自 Miniconda（本机 MSI 安装通道故障，勿用 python.org 安装器）
PY=/d/Mahjong\ AI/third_party/Mortal/.venv/Scripts/python.exe   # Mortal 训练用 venv
# venv 重建：C:\Users\admin\miniconda3\python.exe -m venv third_party/Mortal/.venv
# 依赖：torch 2.9.1+cu128（5090=sm_120，cu124 不支持）+ tqdm + toml + tensorboard
# 注意：pip.ini 若配了 127.0.0.1:7897 代理，代理软件未启动时需加 --proxy=""
```

规则引擎 / 环境：[riichienv](https://github.com/smly/RiichiEnv)（Rust 核心 + Python 绑定，Mortal 生态同款）。

已验证的引擎语义（踩坑记录，写训练代码前必读）：

- `step()` 返回"当前需要做决策的玩家 → Observation"字典；鸣牌窗口会轮流询问每个可鸣牌的玩家
- `obs.hands` 是按玩家遮蔽的视图：`obs.hands[obs.player_id]` 才是自己的手牌（136 制牌 ID）
- 动作类型比较必须用枚举成员（`a.action_type == ActionType.Discard`），`str()` 得到 `"ActionType.Discard"` 而 f-string 得到 `"Discard"`，容易写错
- 均匀随机策略几乎永远不和牌（随机打牌向听数降不下去）——随机对局全是流局是正常现象，不是引擎 bug；`--policy greedy` 会产生有和牌/立直的对局
- `env.mjai_log` 是全知事件流（mjai 协议 JSON），`hora` 事件不含役种信息，random_play.py 会用 MjaiReplay 回补

## 快速开始

根目录 `.venv`（riichienv 引擎用）✅ 2026-09-27 已用 Miniconda Python 重建：Python 3.10.18 + numpy 2.2.6 + gymnasium 1.3.0 + riichienv 0.4.10，随机/greedy 自检全绿。旧机拷来的坏 venv 备份在 `.venv.bak-old-laptop/`，确认无用后可删。

```bash
PY=./.venv/Scripts/python.exe

# 1. 打一个随机对局（或 --policy greedy 产生有和牌的对局），输出 mjai JSONL
$PY src/mahjong_rl/engines/riichi/random_play.py --seed 42 --policy greedy --output data/game.mjai.jsonl

# 2. 规则自检：N 个种子断言 end_game 出现、分数守恒=100000、发牌结构合法
$PY src/mahjong_rl/engines/riichi/random_play.py --self-test 20
$PY src/mahjong_rl/engines/riichi/random_play.py --self-test 10 --policy greedy

# 3. 生成自包含交互式回放 HTML（双击打开，←/→ 逐步查看，含手牌/副露/舍牌河/宝牌/收支）
$PY tools/replay_viewer.py data/game.mjai.jsonl -o docs/experiments/viewer.html
```

历史样例回放：`docs/experiments/sample_greedy_viewer.html`、`sample_random_viewer.html`（对应牌谱待从旧机迁移至 `data/`）。

## 复现约定

- 固定 seed；超参模板落在 `configs/`，每次实验在 `runs/<run_id>/config_resolved.yaml` 留展开快照
- 实验曲线用 tensorboard / wandb 记录
- 引擎行为以 `cythonriichi`/`riichienv` 为准，不自写规则判定
