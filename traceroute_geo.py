#!/usr/bin/env python3
import subprocess
import re
import requests
import argparse
import socket
import time

def traceroute(target: str, max_hops: int = 30, use_tcp: bool = False):
    cmd = ['traceroute', '-m', str(max_hops), '-w', '2', '-q', '1']
    if use_tcp:
        cmd.extend(['-T', '-p', '80'])
    cmd.append(target)
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                               text=True, bufsize=1)
    
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split()
        if len(parts) < 2:
            continue
        
        try:
            hop_num = int(parts[0])
        except ValueError:
            continue
        
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ip_match = re.search(ip_pattern, line)
        
        if not ip_match:
            print(f"{parts[0]:2}. {'*':15} {'*':>12} - No response")
            continue
        
        ip = ip_match.group()
        if ip == '0.0.0.0':
            continue
        
        latency = None
        ms_match = re.findall(r'(\d+\.?\d*)\s*ms', line, re.IGNORECASE)
        if ms_match:
            latency = float(ms_match[0])
        
        yield hop_num, ip, latency
    
    process.wait()

def get_ip_location(ip: str) -> dict:
    url = f"https://ipinfo.io/{ip}/json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 429:
            raise Exception("Rate limit")
        data = resp.json()
        if 'country' in data:
            return {
                'country': data.get('country', 'Unknown'),
                'region': data.get('region', ''),
                'city': data.get('city', ''),
                'isp': data.get('org', 'Unknown')
            }
    except:
        pass
    
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = resp.json()
        if data.get('status') == 'success':
            return {
                'country': data.get('countryCode', ''),
                'region': data.get('regionName', ''),
                'city': data.get('city', ''),
                'isp': data.get('isp', '')
            }
    except:
        pass
    
    return {'country': 'Unknown', 'region': '', 'city': '', 'isp': 'Unknown'}

def print_hop(hop_num: int, ip: str, latency: float | None, location: dict):
    country = location.get('country', 'Unknown')
    region = location.get('region', '')
    city = location.get('city', '')
    isp = location.get('isp', '')
    
    location_str = f"{country}"
    if region:
        location_str += f", {region}"
    if city:
        location_str += f", {city}"
    if isp:
        location_str += f" ({isp})"
    
    latency_str = f"{latency:.2f} ms" if latency else "*"
    print(f"{hop_num:2}. {ip:15} {latency_str:>12} - {location_str}")

def main():
    parser = argparse.ArgumentParser(description='Traceroute with Geo-location')
    parser.add_argument('ip', help='Target IP address or domain')
    parser.add_argument('--max-hops', type=int, default=30, help='Max hops')
    parser.add_argument('--tcp', action='store_true', help='Use TCP SYN mode (requires root)')
    parser.add_argument('--auto', action='store_true', default=True, help='Auto: try TCP first, fallback to UDP if needed')
    args = parser.parse_args()

    try:
        target_ip = socket.gethostbyname(args.ip)
    except socket.gaierror:
        print(f"Error: Cannot resolve {args.ip}")
        return

    print(f"Traceroute to {args.ip} ({target_ip}):\n")

    collected_ips = []
    last_hop_num = 0
    
    if args.tcp:
        hops_dict = {}
        for hop_num, ip, latency in traceroute(target_ip, args.max_hops, use_tcp=True):
            hops_dict[hop_num] = (ip, latency)
            last_hop_num = max(last_hop_num, hop_num)
        
        for hop_num in sorted(hops_dict.keys()):
            ip, latency = hops_dict[hop_num]
            location = get_ip_location(ip)
            print_hop(hop_num, ip, latency, location)
            collected_ips.append(ip)
            time.sleep(0.3)
    else:
        hops_dict = {}
        no_response_count = 0
        
        for hop_num, ip, latency in traceroute(target_ip, args.max_hops, use_tcp=True):
            hops_dict[hop_num] = (ip, latency, True)
            no_response_count = 0
        
        for line in subprocess.Popen(['traceroute', '-m', str(args.max_hops), '-w', '2', '-q', '1', target_ip], 
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                hop_num = int(parts[0])
            except ValueError:
                continue
            
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ip_match = re.search(ip_pattern, line)
            
            if hop_num not in hops_dict:
                if ip_match:
                    hops_dict[hop_num] = (ip_match.group(), None, False)
                else:
                    hops_dict[hop_num] = (None, None, False)
        
        for hop_num in sorted(hops_dict.keys()):
            ip, latency, from_tcp = hops_dict[hop_num]
            if ip:
                location = get_ip_location(ip)
                print_hop(hop_num, ip, latency, location)
                collected_ips.append(ip)
            else:
                print(f"{hop_num:2}. {'*':15} {'*':>12} - No response (TCP failed)")
            time.sleep(0.3)
            last_hop_num = max(last_hop_num, hop_num)
    
    if target_ip not in collected_ips:
        location = get_ip_location(target_ip)
        print_hop(last_hop_num + 1, target_ip, None, location)

if __name__ == "__main__":
    main()
