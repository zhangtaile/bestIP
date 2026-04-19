import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= 配置区 =================
# 请在此处填入你在 AbuseIPDB 申请的 API Key
API_KEY = 'YOUR_ABUSEIPDB_API_KEY_HERE'
INPUT_FILE = 'ipinfo.txt'
OUTPUT_FILE = 'purity_results.json'
MAX_WORKERS = 5  # 并发线程数
# ==========================================

def extract_ips(file_path):
    """
    从 ipinfo.txt 中提取 IP 地址
    格式示例: 47.76.218.163:443#HK Alibaba Cloud - HK 61.99 ms
    """
    if not os.path.exists(file_path):
        print(f"错误: 找不到输入文件 {file_path}")
        return []
    
    ips = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
            # 提取冒号前的部分作为 IP
            ip = line.split(':')[0].strip()
            if ip not in ips:
                ips.append(ip)
    return ips

def check_ip_purity(ip):
    """调用 AbuseIPDB API 检查 IP 纯净度"""
    if API_KEY == 'YOUR_ABUSEIPDB_API_KEY_HERE':
        return {'ip': ip, 'error': '未配置 API Key'}

    url = 'https://api.abuseipdb.com/api/v2/check'
    params = {
        'ipAddress': ip,
        'maxAgeInDays': '90',
        'verbose': True
    }
    headers = {
        'Accept': 'application/json',
        'Key': API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()['data']
            return {
                'ip': ip,
                'abuse_score': data.get('abuseConfidenceScore', 0), # 恶意信心分 (0-100)
                'isp': data.get('isp', 'Unknown'),
                'domain': data.get('domain', 'Unknown'),
                'usage_type': data.get('usageType', 'Unknown'),
                'country': data.get('countryCode', 'Unknown'),
                'is_tor': data.get('isTor', False),
                'total_reports': data.get('totalReports', 0),
                'error': None
            }
        elif response.status_code == 429:
            return {'ip': ip, 'error': 'API 请求超限 (Rate Limit)'}
        elif response.status_code == 401:
            return {'ip': ip, 'error': 'API Key 无效'}
        else:
            return {'ip': ip, 'error': f'HTTP 错误 {response.status_code}'}
    except Exception as e:
        return {'ip': ip, 'error': str(e)}

def main():
    print("开始提取 IP 地址...")
    ips = extract_ips(INPUT_FILE)
    if not ips:
        print("未检测到有效 IP，程序退出。")
        return
    
    print(f"成功提取 {len(ips)} 个 IP。正在开始纯净度检测 (线程数: {MAX_WORKERS})...")
    
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ip = {executor.submit(check_ip_purity, ip): ip for ip in ips}
        
        for count, future in enumerate(as_completed(future_to_ip), 1):
            res = future.result()
            ip = res['ip']
            
            if res.get('error'):
                print(f"[{count}/{len(ips)}] ❌ {ip.ljust(15)} | 错误: {res['error']}")
            else:
                score = res['abuse_score']
                # 根据分数判定纯净度级别
                if score == 0:
                    status = "🟢 极纯净"
                elif score < 20:
                    status = "🟡 较纯净"
                elif score < 50:
                    status = "🟠 有风险"
                else:
                    status = "🔴 高风险"
                
                print(f"[{count}/{len(ips)}] {status} | {ip.ljust(15)} | 评分: {str(score).rjust(3)} | ISP: {res['isp']}")
            
            all_results.append(res)
            # 频率限制：AbuseIPDB 免费版每秒并发不能太快
            time.sleep(0.3)

    # 汇总保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ 检测完成！")
    print(f"详细报告已保存至: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
