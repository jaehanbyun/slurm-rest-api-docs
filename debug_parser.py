#!/usr/bin/env python3
"""
Debug script to test return type extraction
"""
import requests
from bs4 import BeautifulSoup
import re

def fetch_html(url: str) -> str:
    """Fetch HTML content from URL"""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

url = "https://raw.githubusercontent.com/SchedMD/slurm/master/doc/html/rest_api.shtml"
print("Fetching HTML...")
html_content = fetch_html(url)
soup = BeautifulSoup(html_content, 'html.parser')

# Test: Find the partitions endpoint
method = "get"
path = "/slurm/v0.0.44/partitions"

print(f"\nLooking for: {method} {path}")
print("=" * 60)

code_blocks = soup.find_all('code')
print(f"Total code blocks found: {len(code_blocks)}")

for i, code in enumerate(code_blocks):
    text = code.get_text().strip()
    endpoint_pattern = f"{method}\\s+{re.escape(path)}"
    
    if re.search(endpoint_pattern, text, re.IGNORECASE):
        print(f"\n✓ Found matching code block #{i}: {text[:100]}")
        
        # Look for "Return type" heading after this code block
        current = code
        for j in range(30):
            current = current.find_next()
            if not current:
                print(f"  Reached end of document at step {j}")
                break
            
            elem_info = f"  [{j}] {current.name}: {current.get_text()[:80]}"
            
            # Check if this is a "Return type" heading
            if current.name in ['h3', 'h4', 'h2']:
                text_lower = current.get_text().lower()
                print(f"{elem_info} {'<-- HEADER' if 'return' in text_lower else ''}")
                
                if 'return type' in text_lower:
                    print(f"\n  ✓✓ Found 'Return type' heading!")
                    # Look at next few elements
                    next_elem = current
                    for k in range(5):
                        next_elem = next_elem.find_next()
                        if next_elem:
                            print(f"    Next[{k}] {next_elem.name}: {next_elem.get_text()[:100]}")
                            if next_elem.name == 'p':
                                link = next_elem.find('a')
                                if link:
                                    schema_name = link.get_text().strip()
                                    print(f"\n    ✓✓✓ FOUND SCHEMA: {schema_name}")
                                    break
                    break
