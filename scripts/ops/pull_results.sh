#!/bin/bash
# 从服务器拉回训练结果（checkpoint / 日志）
# 用法：bash scripts/pull_results.sh <服务器项目路径> [本地保存目录]
# 例： bash scripts/pull_results.sh ~/mahjong-project/checkpoints ./checkpoints
set -e
REMOTE="${1:?用法: bash scripts/pull_results.sh <服务器路径> [本地目录]}"
LOCAL="${2:-./results}"
mkdir -p "$LOCAL"
if command -v rsync >/dev/null 2>&1; then
    rsync -avP "4090:$REMOTE/" "$LOCAL/"
else
    scp -r "4090:$REMOTE" "$LOCAL/"
fi
echo "已拉取到本地：$LOCAL"
