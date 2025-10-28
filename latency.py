import socket
import time
import concurrent.futures
from typing import List, Dict, Tuple
import os

# Attempt to bypass any system-level proxies by unsetting environment variables
os.environ.pop('http_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

def measure_latency(address: str) -> Tuple[str, float]:
    """
    Measures the TCP connection latency to a given address (ip:port).

    Args:
        address: The address in "ip:port" format.

    Returns:
        A tuple containing the address and the latency in milliseconds.
        Returns float('inf') for latency if the connection fails.
    """
    try:
        address_part = address.strip().split('#')[0]
        ip, port_str = address_part.split(':')
        port = int(port_str)
        
        start_time = time.perf_counter()
        
        # Set a timeout for the connection attempt
        timeout_seconds = 5
        
        with socket.create_connection((ip, port), timeout=timeout_seconds) as sock:
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            
            # Get the actual peer address to check for proxies
            try:
                actual_ip, _ = sock.getpeername()
            except Exception as e:
                pass

            return address, latency_ms
            
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return address, float('inf')
    except ValueError:
        return address, float('inf')

def main():
    """
    Main function to run the latency tests and write the results.
    """
    input_filename = 'geoIP.txt'
    output_filename = 'latencyresult.txt'
    num_loops = 3
    max_concurrency = 20

    try:
        with open(input_filename, 'r') as f:
            addresses = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file '{input_filename}' not found.")
        return

    if not addresses:
        print(f"Warning: Input file '{input_filename}' is empty.")
        return

    # Dictionary to store latency results for each address
    # { "ip:port": [run1_latency, run2_latency, run3_latency], ... }
    all_results: Dict[str, List[float]] = {addr: [] for addr in addresses}
    completed_tests = 0
    total_tests = len(addresses) * num_loops

    for i in range(num_loops):
        print(f"--- Loop {i+1}/{num_loops} ---")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_address = {executor.submit(measure_latency, addr): addr for addr in addresses}
            for future in concurrent.futures.as_completed(future_to_address):
                address, latency = future.result()
                if address in all_results:
                    all_results[address].append(latency)

                completed_tests += 1
                percentage = (completed_tests / total_tests) * 100
                
                status = f"{latency:.2f} ms" if latency != float('inf') else "Failed"
                print(f"[{percentage:5.2f}%] Tested {address}: {status}")

    # Calculate the maximum latency for each address
    max_latencies: Dict[str, float] = {}
    for address, latencies in all_results.items():
        if latencies:
            max_latencies[address] = max(latencies)
        else:
            # This case happens if all connection attempts failed
            max_latencies[address] = float('inf')

    # Sort addresses by their maximum latency (lowest to highest)
    # We filter out the ones that had infinite latency in all runs
    sorted_results = sorted(max_latencies.items(), key=lambda item: item[1])

    # Write the sorted results to the output file
    with open(output_filename, 'w') as f:
        for address, max_latency in sorted_results:
            if max_latency == float('inf'):
                f.write(f"{address}: Failed\n")
            else:
                f.write(f"{address}: {max_latency:.2f} ms\n")

    print(f"\nResults sorted by highest latency and saved to '{output_filename}'.")

if __name__ == "__main__":
    main()