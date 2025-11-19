#!/usr/bin/env python3
"""
Test if example data extraction is working
"""
import sys
sys.path.insert(0, '.')

from parse_api_docs import fetch_html, extract_example_data, parse_example_to_schema
from bs4 import BeautifulSoup

url = "https://raw.githubusercontent.com/SchedMD/slurm/master/doc/html/rest_api.shtml"
print("Fetching HTML...")
html_content = fetch_html(url)
soup = BeautifulSoup(html_content, 'html.parser')

# Test nodes endpoint
method = "get"
path = "/slurm/v0.0.44/nodes"

print(f"\nTesting: {method} {path}")
print("=" * 60)

example_data = extract_example_data(soup, method, path)

if example_data:
    print(f"✓ Example data extracted! Length: {len(example_data)} chars")
    print(f"First 300 chars:\n{example_data[:300]}")
    
    print("\n" + "=" * 60)
    print("Testing schema generation...")
    schema = parse_example_to_schema(example_data)
    
    import json
    print(json.dumps(schema, indent=2)[:1000])
else:
    print("✗ No example data found")
