#!/bin/bash

# 设置遇到错误立即退出
set -e

# 获取脚本所在目录，确保在正确的路径执行
cd "$(dirname "$0")"

echo "--- 正在删除旧的 proxyList.txt ---"
rm -f proxyList.txt

echo "--- 正在从 GitHub 下载最新的 proxyList.txt ---"
if wget https://raw.githubusercontent.com/FoolVPN-ID/Nautica/refs/heads/main/proxyList.txt; then
    echo "下载成功。"
else
    echo "下载失败，请检查网络连接。"
    exit 1
fi

echo "--- 正在运行延迟测试 (预计需要几分钟) ---"
# 如果你想测试真实的端到端延迟，请在下方命令加上 --worker 参数
# 例如: python3 ./latency.py -t 20 --worker myworker.yourdomain.workers.dev
python3 ./latency.py -t 20

echo "--- 正在提取前 55 行到 ipinfo.txt ---"
head -n 55 latencyresult.txt > ipinfo.txt

echo "--- 正在提交更改到 Git ---"
git add .
# 使用当前时间作为提交信息的一部分，更具可读性
git commit -m "update: $(date '+%Y-%m-%d %H:%M:%S')"

echo "--- 正在推送至远程仓库 ---"
git push

echo "--- 所有任务已完成！ ---"
