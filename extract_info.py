import re

def extract_and_format(input_file, output_file):
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            line = line.strip()
            if not line:
                continue

            # Use regex to find the IP, port, and alias
            match = re.search(r'@([^?]+)\?.*#(.+)', line)
            if match:
                ip_port = match.group(1)
                alias = match.group(2)
                
                # Write the formatted string to the output file
                outfile.write(f"{ip_port}#{alias}\n")

# Specify the input and output file paths
input_file_path = '/home/taile/iptest/benchmarked.txt'
output_file_path = '/home/taile/iptest/final.txt'

# Run the extraction and formatting
extract_and_format(input_file_path, output_file_path)

print(f"Data has been extracted and saved to {output_file_path}")