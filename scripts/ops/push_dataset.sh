#!/bin/bash
# 上传本地数据集到服务器共享目录（断点续传）
# 用法：bash scripts/push_dataset.sh <本地数据集目录> <数据集名>
# 例： bash scripts/push_dataset.sh ./dataset mahjong-logs
set -e
SRC="${1:?用法: bash scripts/push_dataset.sh <本地目录> <数据集名>}"
NAME="${2:?用法: bash scripts/push_dataset.sh <本地目录> <数据集名>}"
if command -v rsync >/dev/null 2>&1; then
    rsync -avP "$SRC/" "4090:/data/datasets/$NAME/"
else
    # Git Bash 默认没有 rsync，退回 scp（无断点续传，大文件建议装 rsync 或用 WSL）
    scp -r "$SRC" "4090:/data/datasets/$NAME"
fi
echo "上传完成：服务器 /data/datasets/$NAME"
