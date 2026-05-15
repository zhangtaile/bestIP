#!/bin/bash

# 设置遇到错误立即退出
set -e

# 获取脚本所在目录，确保在正确的路径执行
cd "$(dirname "$0")"

RAW_CSV="02_proxies.csv"
PROCESSED_TXT="new_proxy.txt"

echo "--- 正在删除旧的中间文件 ---"
rm -f "$RAW_CSV" "$PROCESSED_TXT"

echo "--- 正在从 GitHub 下载最新的 $RAW_CSV ---"
if wget https://raw.githubusercontent.com/NiREvil/vless/refs/heads/main/sub/country_proxies/02_proxies.csv -O "$RAW_CSV"; then
    echo "下载成功。"
else
    echo "下载失败，请检查网络连接。"
    exit 1
fi

echo "--- 正在调整数据格式以兼容 latency.py ---"
# 处理逻辑：
# 1. 跳过第一行标题 (NR>1)
# 2. 原始列顺序: IP(1), Port(2), TLS(3), Country(4), Region(5), City(6), ASN(7), latency(8)
# 3. latency.py 筛选 -r 时检查第 3 列，因此我们将 Country(4) 移动到第 3 列
# 4. 输出格式: IP, Port, Country, TLS, Region, City, ASN, latency
awk -F',' 'NR>1 {
    # 去除各字段首尾空格（防止 CSV 格式不规范）
    for(i=1;i<=NF;i++) gsub(/^[ \t]+|[ \t]+$/, "", $i);
    # 交换第 3 和第 4 列
    print $1","$2","$4","$3","$5","$6","$7","$8 
}' "$RAW_CSV" > "$PROCESSED_TXT"

# 获取地区参数（可选）
REGION=$1
REGION_ARG=""
if [ -n "$REGION" ]; then
    REGION_ARG="-r $REGION"
    echo "--- 正在运行延迟测试 (仅限地区: $REGION) ---"
else
    echo "--- 正在运行延迟测试 (所有地区) ---"
fi

# 使用处理后的文件作为输入
python3 ./latency.py -i "$PROCESSED_TXT" -t 20 $REGION_ARG

echo "--- 正在提取前 55 行到 ipinfo.txt ---"
head -n 55 latencyresult.txt > ipinfo.txt

echo "--- 正在提交更改到 Git ---"
git add .
# 使用当前时间作为提交信息的一部分，更具可读性
git commit -m "update(new-src): $(date '+%Y-%m-%d %H:%M:%S')" || echo "没有更改需要提交"

echo "--- 正在推送至远程仓库 ---"
git push

echo "--- 所有任务已完成！ ---"
