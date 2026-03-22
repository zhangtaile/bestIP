import socket
import time
import concurrent.futures
from typing import List, Dict, Tuple, Optional
import os
import argparse
import sys
import re
import logging
import ssl

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Attempt to bypass any system-level proxies by unsetting environment variables
for env_var in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(env_var, None)

class ValidationError(Exception):
    """Raised when address validation fails."""
    pass


def validate_ip(ip: str) -> bool:
    """Validate IP address format (IPv4 or IPv6)."""
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip):
        octets = ip.split('.')
        return all(0 <= int(octet) <= 255 for octet in octets)
    return False


def validate_port(port: int) -> bool:
    """Validate port number range."""
    return 1 <= port <= 65535


def parse_address(address: str) -> Tuple[str, int, List[str]]:
    """
    Parse and validate address string.
    
    Args:
        address: The address line from proxy.txt.
        
    Returns:
        Tuple of (ip, port, info_parts).
        
    Raises:
        ValidationError: If format is invalid or values are out of range.
    """
    parts = [p.strip() for p in address.strip().split(',')]
    if len(parts) < 2:
        raise ValidationError(f"Invalid format: {address}")
    
    ip = parts[0]
    if not validate_ip(ip):
        raise ValidationError(f"Invalid IP address: {ip}")
    
    try:
        port = int(parts[1])
    except ValueError:
        raise ValidationError(f"Invalid port number: {parts[1]}")
    
    if not validate_port(port):
        raise ValidationError(f"Port out of range (1-65535): {port}")
    
    info = parts[2:] if len(parts) > 2 else []
    return ip, port, info


def measure_latency(parsed_addr: Tuple[str, int, str], timeout: float = 5.0, worker_domain: str = None) -> Tuple[str, float, Optional[str]]:
    """
    Measures the connection latency to a given address.
    If worker_domain is provided, performs an end-to-end HTTP(S) GET request via the IP.
    Otherwise, performs a simple TCP connect.

    Args:
        parsed_addr: Tuple of (ip, port, original_address).
        timeout: Socket timeout in seconds.
        worker_domain: The Cloudflare Worker domain to test end-to-end latency.

    Returns:
        A tuple containing the original address, latency in milliseconds, and error message.
    """
    ip, port, original_address = parsed_addr
    
    try:
        start_time = time.perf_counter()
        
        if not worker_domain:
            # Standard TCP Connect Ping
            with socket.create_connection((ip, port), timeout=timeout) as sock:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                return original_address, latency_ms, None
        else:
            # End-to-end HTTP(S) Ping
            # Determine if TLS should be used based on typical Cloudflare HTTPS ports
            use_ssl = port in [443, 8443, 2053, 2083, 2087, 2096]
            
            with socket.create_connection((ip, port), timeout=timeout) as sock:
                if use_ssl:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE  # Connecting via IP, so standard validation fails
                    with context.wrap_socket(sock, server_hostname=worker_domain) as ssock:
                        request = f"GET /ping HTTP/1.1\r\nHost: {worker_domain}\r\nConnection: close\r\n\r\n"
                        ssock.sendall(request.encode('utf-8'))
                        # Read response until we get the headers
                        response = ssock.recv(1024)
                        if not response.startswith(b"HTTP/"):
                            raise ValueError("Invalid HTTP response")
                else:
                    request = f"GET /ping HTTP/1.1\r\nHost: {worker_domain}\r\nConnection: close\r\n\r\n"
                    sock.sendall(request.encode('utf-8'))
                    response = sock.recv(1024)
                    if not response.startswith(b"HTTP/"):
                        raise ValueError("Invalid HTTP response")
                        
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            return original_address, latency_ms, None
            
    except socket.timeout:
        return original_address, float('inf'), "Connection timeout"
    except ConnectionRefusedError:
        return original_address, float('inf'), "Connection refused"
    except Exception as e:
        return original_address, float('inf'), f"Network error: {e}"

def save_results(results: Dict[str, List[float]], output_filename: str) -> None:
    """
    Calculates max latency and saves sorted results to the output file.
    """
    # Calculate the maximum latency for each address
    max_latencies: Dict[str, float] = {}
    for address, latencies in results.items():
        if latencies:
            # Filter out failures (inf) unless all failed
            valid_latencies = [latency for latency in latencies if latency != float('inf')]
            if valid_latencies:
                # Use max latency of successful attempts to be conservative
                max_latencies[address] = max(valid_latencies)
            else:
                max_latencies[address] = float('inf')
        else:
            max_latencies[address] = float('inf')

    # Sort addresses: lowest latency first, failures last
    sorted_results = sorted(max_latencies.items(), key=lambda item: item[1])

    try:
        with open(output_filename, 'w') as f:
            for address, max_latency in sorted_results:
                # Parse the CSV line: IP,Port,Region,DataCenter
                parts = address.strip().split(',')
                if len(parts) >= 2:
                    ip = parts[0]
                    port = parts[1]
                    # Join Region and DataCenter with space
                    info = " ".join(parts[2:])
                    display_str = f"{ip}:{port}#{info}"
                else:
                    display_str = address

                if max_latency == float('inf'):
                    f.write(f"{display_str} Failed\n")
                else:
                    f.write(f"{display_str} {max_latency:.2f} ms\n")
        logger.info(f"Saved {len(sorted_results)} results to '{output_filename}'.")
    except IOError as e:
        logger.error(f"Error saving results: {e}")

def main():
    parser = argparse.ArgumentParser(description="Multi-threaded TCP/HTTP Latency Tester")
    parser.add_argument("-i", "--input", default="proxy.txt", help="Input file containing proxies (IP,Port,...)")
    parser.add_argument("-o", "--output", default="latencyresult.txt", help="Output file for sorted results")
    parser.add_argument("-t", "--threads", type=int, default=5, help="Number of concurrent threads (default: 5)")
    parser.add_argument("-l", "--loops", type=int, default=3, help="Number of testing loops (default: 3)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Connection timeout in seconds (default: 5.0)")
    parser.add_argument("--worker", type=str, default=None, help="Cloudflare Worker domain to test end-to-end latency (e.g. myworker.username.workers.dev)")
    
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file '{args.input}' not found.")
        return

    # Pre-parse and validate all addresses (only once)
    parsed_addresses: List[Tuple[str, int, str]] = []
    invalid_count = 0
    
    try:
        with open(args.input, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ip, port, _ = parse_address(line)
                    parsed_addresses.append((ip, port, line))
                except ValidationError as e:
                    logger.warning(f"Skipping invalid address: {e}")
                    invalid_count += 1
    except IOError as e:
        logger.error(f"Error reading input file: {e}")
        return

    if not parsed_addresses:
        logger.warning(f"Input file '{args.input}' is empty or all addresses are invalid.")
        return
    
    if invalid_count > 0:
        logger.warning(f"Skipped {invalid_count} invalid addresses.")

    logger.info(f"Loaded {len(parsed_addresses)} proxies.")
    
    if args.worker:
        logger.info(f"Testing end-to-end HTTP(S) latency through proxies to worker: {args.worker}")
    else:
        logger.info(f"Testing direct TCP connection latency to proxies.")
        
    logger.info(f"Threads: {args.threads}, Loops: {args.loops}, Timeout: {args.timeout}s.")
    logger.info("Press Ctrl+C to stop early and save current results.")

    # Dictionary to store latency results: { "original_address": [latency1, latency2, ...] }
    all_results: Dict[str, List[float]] = {addr[2]: [] for addr in parsed_addresses}
    
    total_tasks = len(parsed_addresses) * args.loops
    completed_tasks = 0

    try:
        for loop in range(args.loops):
            logger.info(f"--- Loop {loop+1}/{args.loops} ---")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
                # Submit all tasks for this loop
                future_to_address = {executor.submit(measure_latency, addr, args.timeout, args.worker): addr for addr in parsed_addresses}
                
                for future in concurrent.futures.as_completed(future_to_address):
                    address, latency, error = future.result()
                    all_results[address].append(latency)
                    
                    completed_tasks += 1
                    percent = (completed_tasks / total_tasks) * 100
                    
                    # Simple progress bar
                    bar_length = 40
                    filled_length = int(bar_length * completed_tasks // total_tasks)
                    bar = '=' * filled_length + '-' * (bar_length - filled_length)
                    sys.stdout.write(f'\r[{bar}] {percent:.1f}% ({completed_tasks}/{total_tasks})')
                    sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("Testing interrupted by user. Saving collected results...")
    
    print() # Newline after progress bar
    save_results(all_results, args.output)

if __name__ == "__main__":
    main()
