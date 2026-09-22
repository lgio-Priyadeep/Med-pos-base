from collections import Counter
import re

with open("architecture_v1_6_5.md", "r", encoding="utf-8") as f:
    arch = f.read()

body_part, sep, reg_part = arch.partition("## 19. Deferred Items Register")
body_markers = re.findall(r'\[DEFERRED → Doc \d+: [^\]]+\]', body_part)
reg_markers = re.findall(r'\[DEFERRED → Doc \d+: [^\]]+\]', reg_part)

print(f"Body count: {len(body_markers)}, Register count: {len(reg_markers)}")
print(f"Unique body: {len(set(body_markers))}, Unique register: {len(set(reg_markers))}")

diff_body_minus_reg = set(body_markers) - set(reg_markers)
diff_reg_minus_body = set(reg_markers) - set(body_markers)
print(f"In body but not reg: {diff_body_minus_reg}")
print(f"In reg but not body: {diff_reg_minus_body}")

assert Counter(body_markers) == Counter(reg_markers)
print("SUCCESS: 1:1 parity between body and register markers confirmed!")
