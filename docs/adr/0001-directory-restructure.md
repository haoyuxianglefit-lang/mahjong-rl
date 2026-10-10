# ADR-0001：目录结构重构与多规则/多版本架构

- 日期：2026-10-11
- 状态：已执行

## 背景
项目即将开始规则迁移（日麻 → 川麻/三麻）与模块融合训练（多 encoder/head 版本组合），
原平面目录（engine/ reports/ research/ Mortal/ mahjong-play/ 并列）无法承载
「规则是配置」「实验是一等公民」两条主线。

## 决策
1. **规则是配置**：所有规则差异收进 `RuleSpec`（src/mahjong_rl/engines/rule_spec.py +
   configs/rules/*.yaml），引擎/编码/动作空间从 spec 派生。
2. **模型模块化**：encoder 与 heads 经注册表（models/registry.py）组合，
   融合关系写在 manifest（configs/models/*.json），不改代码。
3. **实验快照**：每次训练生成 runs/<run_id>/，内含展开后的完整配置快照 + git hash +
   checkpoint + tensorboard + eval.json；configs/ 模板可变，runs/ 快照不可变。
4. **三层解耦**：引擎适配（src/mahjong_rl/engines）／训练（src/mahjong_rl/train）／
   前端展示（apps/mahjong-play，只加载 checkpoint，不依赖训练代码）。
5. **第三方代码隔离**：Mortal 完整克隆移入 third_party/Mortal（暂不纳入 git 跟踪，
   后续改 submodule）；脚本按 build/ data/ ops 三层归类。

## 影响
- 所有历史文档（reports/ research/）迁入 docs/，路径引用已在同批提交中更新。
- Mortal venv 随迁至 third_party/Mortal/.venv，直接调用 python.exe 不受影响
  （pyvenv.cfg 的 home 指向 miniconda）；若 venv 内 console 脚本失效，用
  `python -m pip` / `python -m uvicorn` 形式调用。
