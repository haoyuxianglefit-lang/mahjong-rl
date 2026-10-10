#!/bin/bash
# 一键连接同学的 4090 服务器（需先在 ~/.ssh/config 里填好 Tailscale IP 和用户名）
# 用法：bash scripts/connect.sh          → 打开登录终端
#       bash scripts/connect.sh train    → 直接回到名为 train 的 tmux 训练会话
if [ -n "$1" ]; then
    ssh -t 4090 "tmux attach -t $1 2>/dev/null || tmux new -s $1"
else
    ssh 4090
fi
