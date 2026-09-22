import re

lines = open('known_areas_to_improve.md', encoding='utf-8').readlines()

with open('scratch/l_citations_report.txt', 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines):
        m = re.findall(r'(?:§|\bL)\d*(?:\s*L\d+)+', line)
        if m:
            out.write(f"Line {i+1}: {m}\n  Text: {line.strip()}\n\n")

print("Report written to scratch/l_citations_report.txt")
