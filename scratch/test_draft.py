import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/draft_content.md', 'r', encoding='utf-8') as f:
    draft = f.read()

words = len(draft.split())
print(f'Total Draft Word Count: {words}')

# Check markers in body vs register
parts = draft.split('## 19. Deferred Items Register')
body = parts[0]
register = parts[1]

body_markers = re.findall(r'\[DEFERRED → Doc \d+:[^\]]+\]', body)
reg_markers = re.findall(r'\[DEFERRED → Doc \d+:[^\]]+\]', register)

print(f'Body markers count: {len(body_markers)}')
print(f'Register markers count: {len(reg_markers)}')
print(f'Unique body markers: {len(set(body_markers))}')
print(f'Unique reg markers: {len(set(reg_markers))}')

diff1 = set(body_markers) - set(reg_markers)
diff2 = set(reg_markers) - set(body_markers)
print('In body but NOT register:', diff1)
print('In register but NOT body:', diff2)

if not diff1 and not diff2 and len(body_markers) == len(reg_markers):
    print('PERFECT 1-TO-1 MARKER MATCH!')
