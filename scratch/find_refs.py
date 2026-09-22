import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('known_areas_to_improve.md', encoding='utf-8') as f:
    lines = f.readlines()

import re

for i, line in enumerate(lines, 1):
    refs = re.findall(r'(§\d+(?:\.\d+)?\s+L\d+|L\d+)', line)
    if refs:
        print(f"L{i}: {refs} -> {line.strip()[:100]}")
