import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/draft_content.md', 'r', encoding='utf-8') as f:
    text = f.read()

words = len(text.split())
print(f'NEW Word Count: {words}')

# Let's count words per section
secs = re.split(r'\n(?=## \d+\.)', text)
for i, s in enumerate(secs):
    print(f'Sec {i:2d}: {s.splitlines()[0][:45]:45s} -> {len(s.split()):4d} words')
