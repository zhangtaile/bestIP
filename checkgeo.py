import requests


def get_geo_address(ip_port):
    """
    Fetches the geo address for a given IP and returns it with the original IP:port.
    """
    ip = ip_port.strip().split(':')[0]
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}')
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        if data['status'] == 'success':
            country = data.get('country', '')
            city = data.get('city', '')
            geo_address = f'{country}{city}'.replace(' ', '')
            output_line = f'{ip_port.strip()}#{geo_address}'
            print(output_line)
            return output_line
        else:
            print(f"{ip_port.strip()}#Failed to get location")
            return None
    except requests.exceptions.RequestException as e:
        print(f"{ip_port.strip()}#Error: {e}")
        return None

def main():
    """
    Reads IPs from CFproxy.txt, gets their geo address, and writes to geoIP.txt.
    """
    input_file = '/home/taile/iptest/CFproxy.txt'
    output_file = '/home/taile/iptest/geoIP.txt'

    with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
        for line in f_in:
            line = line.strip()
            if line:
                result = get_geo_address(line)
                if result:
                    f_out.write(f'{result}\n')

if __name__ == '__main__':
    main()