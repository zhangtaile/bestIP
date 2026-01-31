import socket
import time
import concurrent.futures
from typing import List, Dict, Tuple
import os
import argparse
import sys

# Attempt to bypass any system-level proxies by unsetting environment variables
for env_var in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(env_var, None)

def measure_latency(address: str, timeout: float = 5.0) -> Tuple[str, float]:
    """
    Measures the TCP connection latency to a given address (IP,Port,Region,DataCenter).

    Args:
        address: The address line from proxy.txt.
        timeout: Socket timeout in seconds.

    Returns:
        A tuple containing the address and the latency in milliseconds.
        Returns float('inf') for latency if the connection fails.
    """
    try:
        # Parse IP and Port from the comma-separated line
        parts = address.strip().split(',')
        if len(parts) < 2:
            return address, float('inf')
            
        ip = parts[0]
        port = int(parts[1])
        
        start_time = time.perf_counter()
        
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            
            # Optional: Get the actual peer address (overhead is minimal)
            try:
                sock.getpeername()
            except Exception:
                pass

            return address, latency_ms
            
    except (socket.timeout, ConnectionRefusedError, OSError, ValueError):
        return address, float('inf')

def save_results(results: Dict[str, List[float]], output_filename: str):
    """
    Calculates max latency and saves sorted results to the output file.
    """
    # Calculate the maximum latency for each address
    max_latencies: Dict[str, float] = {}
    for address, latencies in results.items():
        if latencies:
            # Filter out failures (inf) unless all failed
            valid_latencies = [l for l in latencies if l != float('inf')]
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
        print(f"\nSaved {len(sorted_results)} results to '{output_filename}'.")
    except IOError as e:
        print(f"\nError saving results: {e}")

def main():
    parser = argparse.ArgumentParser(description="Multi-threaded TCP Latency Tester")
    parser.add_argument("-i", "--input", default="proxy.txt", help="Input file containing proxies (IP,Port,...)")
    parser.add_argument("-o", "--output", default="latencyresult.txt", help="Output file for sorted results")
    parser.add_argument("-t", "--threads", type=int, default=100, help="Number of concurrent threads (default: 100)")
    parser.add_argument("-l", "--loops", type=int, default=3, help="Number of testing loops (default: 3)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Connection timeout in seconds (default: 5.0)")
    
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        return

    try:
        with open(args.input, 'r') as f:
            addresses = [line.strip() for line in f if line.strip()]
    except IOError as e:
        print(f"Error reading input file: {e}")
        return

    if not addresses:
        print(f"Warning: Input file '{args.input}' is empty.")
        return

    print(f"Loaded {len(addresses)} proxies.")
    print(f"Starting latency test with {args.threads} threads, {args.loops} loops, timeout {args.timeout}s.")
    print("Press Ctrl+C to stop early and save current results.")

    # Dictionary to store latency results: { "ip:port...": [latency1, latency2, ...] }
    all_results: Dict[str, List[float]] = {addr: [] for addr in addresses}
    
    total_tasks = len(addresses) * args.loops
    completed_tasks = 0

    try:
        for loop in range(args.loops):
            print(f"\n--- Loop {loop+1}/{args.loops} ---")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
                # Submit all tasks for this loop
                future_to_address = {executor.submit(measure_latency, addr, args.timeout): addr for addr in addresses}
                
                for future in concurrent.futures.as_completed(future_to_address):
                    address, latency = future.result()
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
        print("\n\nTesting interrupted by user. Saving collected results...")
    
    print() # Newline after progress bar
    save_results(all_results, args.output)

if __name__ == "__main__":
    main()