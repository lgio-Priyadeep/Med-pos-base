import re, sys

with open('architecture_v1_6_5.md', encoding='utf-8') as f:
    text = f.read()

print('Initial word count:', len(text.split()))

# Let's verify all Dxx tags in text
dtags = re.findall(r'\(D\d+\)', text)
print(f'Total D-tags: {len(dtags)}')
