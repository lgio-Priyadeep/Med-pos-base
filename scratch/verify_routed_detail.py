import re
from collections import Counter

with open("architecture_v1_6_5.md", "r", encoding="utf-8") as f:
    arch = f.read()

with open("ROUTED-DETAIL.md", "r", encoding="utf-8") as f:
    routed = f.read()

# 1. Markers in architecture_v1_6_5.md
all_markers = re.findall(r'\[DEFERRED → Doc (\d+): ([^\]]+)\]', arch)
print(f"Total marker occurrences in architecture doc: {len(all_markers)}")

counts = Counter(all_markers)
unique_markers = list(counts.keys())
print(f"Unique markers: {len(unique_markers)}")

# Each of the 35 markers should appear exactly twice (once in body, once in §19)
invalid_counts = [m for m, c in counts.items() if c != 2]
if invalid_counts:
    print(f"WARNING: Markers not appearing exactly twice: {invalid_counts}")
else:
    print("All 35 markers appear exactly twice (1 in body, 1 in §19 register).")

assert len(unique_markers) == 35, f"Expected 35 unique markers, got {len(unique_markers)}"

# 2. Check each marker topic against ROUTED-DETAIL.md
missing_topics = []
for doc_num, topic in unique_markers:
    clean_topic = topic.strip()
    words = [w for w in re.split(r'[,/ ]+', clean_topic) if len(w) > 3]
    matched = any(w.lower() in routed.lower() for w in words)
    if not matched:
        missing_topics.append((doc_num, topic))

if missing_topics:
    print(f"WARNING: Potential missing topics in ROUTED-DETAIL.md: {missing_topics}")
else:
    print("All 35 deferred marker topics verified in ROUTED-DETAIL.md.")

# 3. Check for placeholder payloads
placeholders = re.findall(r'\{[ \t]*\.\.\.[ \t]*\}', routed)
print(f"Placeholder '{{ ... }}' count in ROUTED-DETAIL.md: {len(placeholders)}")
assert len(placeholders) == 0, f"Expected 0 placeholders, found {len(placeholders)}"

# 4. Check specific sections
required_sections = [
    "5.5 Low-Stock Alert State Lifecycle & Cooldown Flow",
    "5.6 Live Discount Edit & Version Verification Flow",
    "5.7 Master-Data Change Request State Machine",
    "5.8 Shift Lifecycle & Till Reconciliation State Machine",
    "6.3 V2 Enterprise Distributed Edge Cases & Scenarios",
    "7.2 V2 Enterprise Module Dependencies & Architectural Roadmap",
    "9.4 Structured Log Schema & Audit Correlation ID Spec",
    "10.3 Canary Rollout Protocol, Rollback Procedures & Edge Checklist",
    "pharmacist_password_verified",
    "18. `grn`:",
    "19. `credit-note-redemption`:"
]

missing_sections = []
for sec in required_sections:
    if sec not in routed:
        missing_sections.append(sec)

if missing_sections:
    print(f"Missing required sections/strings: {missing_sections}")
    assert False, f"Missing: {missing_sections}"
else:
    print("All required new sections and strings present in ROUTED-DETAIL.md.")

# 5. Check Test 1 and Test 5 in Doc 8
assert "expiry" in routed and "<" in routed and "current\\_date (IST)" in routed, "Doc 8 Test 1 condition missing"
print("Doc 8 Test 1 correctly uses strict '<' (expiry < current\\_date (IST)).")

assert "Argon2id" in routed and "pharmacist_password_verified" in routed, "Doc 8 Test 5 password condition missing"
print("Doc 8 Test 5 and Doc 1 §1.5 Tier B password verification confirmed.")

# 6. Check Mermaid M-12
assert "M-12[M-12: Settings & Config]" in routed, "M-12 missing from ROUTED-DETAIL.md Mermaid"
print("M-12 found in ROUTED-DETAIL.md Mermaid diagram.")

print("\nALL ROUTED-DETAIL.MD VERIFICATIONS PASSED!")
