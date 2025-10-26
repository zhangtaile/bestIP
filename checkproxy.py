import requests
import json
import concurrent.futures

def check_proxy(proxy_line):
    """
    Parses a proxy line, checks a single proxy IP, and returns the 'ip:port' if successful.
    """
    if not proxy_line:
        return None

    parts = proxy_line.strip().split(',')
    if len(parts) < 2:
        print(f"SKIPPING invalid line format: {proxy_line.strip()}")
        return None

    proxy_ip_port = f"{parts[0]}:{parts[1]}"

    url = f"https://check.proxyip.cmliussss.net/check?proxyip={proxy_ip_port}"
    print(f"\nRequesting URL: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        print(f"Query result: {json.dumps(data)}")
        if data.get('success') is True:
            print(f"SUCCESS: {proxy_ip_port}")
            return proxy_ip_port
        else:
            # The server itself might give a FAILED message, which is not an error in the script.
            print(f"FAILED: {proxy_ip_port} - {data.get('message', 'No message')}")
            return None
    except requests.exceptions.RequestException as e:
        # This is for network-level errors (DNS, connection refused, timeout, 4xx/5xx status codes)
        print(f"Query result: ERROR - {e}")
        return None
    except json.JSONDecodeError:
        # This is for when the server response is not valid JSON
        print(f"Query result: ERROR - Invalid JSON response")
        return None

def main():
    """
    Reads proxies from proxy.txt, tests them in parallel, and writes successful ones to CFproxy.txt immediately.
    """
    # Clear the output file at the start
    try:
        with open('CFproxy.txt', 'w') as f_out:
            pass
    except IOError as e:
        print(f"Error preparing CFproxy.txt: {e}")
        return

    try:
        with open('proxy.txt', 'r') as f_in:
            proxy_lines = [line.strip() for line in f_in if line.strip()]
    except FileNotFoundError:
        print("Error: proxy.txt not found.")
        return

    print(f"Found {len(proxy_lines)} proxies to test with 5 concurrent workers.")

    successful_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_proxy = {executor.submit(check_proxy, line): line for line in proxy_lines}
        for future in concurrent.futures.as_completed(future_to_proxy):
            result = future.result()
            if result:
                try:
                    with open('CFproxy.txt', 'a') as f_out:
                        f_out.write(result + '\n')
                    successful_count += 1
                except IOError as e:
                    print(f"Error writing to CFproxy.txt: {e}")

    print(f"\nFinished testing. Found {successful_count} successful proxies.")
    print("Successful proxies have been saved to CFproxy.txt.")

if __name__ == "__main__":
    main()
