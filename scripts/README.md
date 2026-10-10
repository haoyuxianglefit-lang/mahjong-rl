# scripts/ — 环境运维与数据工具

> 跨电脑复用的运维脚本，按三层归类：**build/**（编译）· **data/**（数据集）· **ops/**（远程机）。
> 训练入口（train.py / train_grp.py）在 `third_party/Mortal/mortal/`，不在本目录。

## build/ — 环境构建（Windows，新机重装时用）

| 脚本 | 用途 | 运行方式 |
| --- | --- | --- |
| `build/build_libriichi.bat` | 编译 Rust 引擎并产出 `target/release/riichi.dll`（随后 `copy` 为 `mortal/libriichi.pyd`）。内含 PATH / PYO3_PYTHON / CC 全部配置 | **必须在 cmd/PowerShell 里跑**（Git Bash 会触发 Smart App Control 拦截，error 4551） |
| `build/cargo_test.bat` | 跑 libriichi 的 28 项 Rust 测试 | 同上，cmd 里跑 |

## data/ — 数据集获取与转换（parquet → Mortal 逐局 .mjson）

- `data/download_parquet.bat` — 从 HuggingFace 断点续传数据集**全部 24 个** parquet 分片（tenhou-*16 + new-*2 + release-*6，≈6.3GB / 212万局）
- `data/parquet_to_mjson.py` — 单个分片转换 + 按 game_id 去重 + 分桶（2022/2023/2024/2024_val），幂等可重跑
- `data/convert_all.py` — 批量调度 wrapper，每轮 250s 预算，中断后再跑自动续
- `data/torrent_download.py` — 作者官方 BT 种子选择性下载（2026-09 实测做种近乎死亡，留作备用）

```bash
PY=/c/Users/admin/miniconda3/python.exe   # 转换脚本用 base 环境的 pyarrow
"$PY" scripts/data/convert_all.py
```

## ops/ — 远程训练机（同学 4090）

- `ops/connect.sh` — 一键 ssh 登录 / 回到 tmux 训练会话
- `ops/push_dataset.sh` — 上传本地数据集到服务器共享目录（rsync 断点续传）
- `ops/pull_results.sh` — 从服务器拉回训练结果（checkpoint / 日志）

## installers/（项目根目录下）

新机环境安装包留档：Miniconda（py310）、rustup-init、winlibs MinGW zip、torch 2.9.1+cu128 wheel（2.8GB）。环境稳定后整个目录可删。
