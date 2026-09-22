import re

with open("scratch/draft_content.md", "r", encoding="utf-8") as f:
    text = f.read()

sections = re.split(r'\n(?=## )', text)

print(f"Total sections: {len(sections)}")
total_words = len(text.split())
print(f"Total words: {total_words}")

for s in sections:
    lines = s.strip().split('\n')
    header = lines[0] if lines else "Unknown"
    words = len(s.split())
    print(f"{words:4d} words | {header[:60]}")
