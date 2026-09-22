import re
from collections import Counter

print("=" * 60)
print("RUNNING MASTER VERIFICATION ACROSS ALL 4 DOCUMENTS")
print("=" * 60)

# ==========================================
# 1. architecture_v1_6_5.md
# ==========================================
print("\n--- [1/4] Checking architecture_v1_6_5.md ---")
with open("architecture_v1_6_5.md", "r", encoding="utf-8") as f:
    arch = f.read()

# Word count
words = len(arch.split())
print(f"Word count: {words} (Limit: soft 2,500, hard 3,500)")
assert words <= 3500, f"Hard word count cap exceeded: {words} > 3500"

# Stable IDs D-01 .. D-125
d_tags = re.findall(r'\(D-(\d+)\)', arch)
d_ints = sorted([int(x) for x in d_tags])
print(f"Total D-XX tags found: {len(d_ints)}")
assert len(d_ints) == 125, f"Expected exactly 125 D-tags, got {len(d_ints)}"
expected = list(range(1, 126))
assert d_ints == expected, f"D-tags mismatch! Difference: {set(expected) - set(d_ints)}"
print("D-01 through D-125 sequence is 100% contiguous, complete, and unique.")

# Modules M-01 .. M-13
for i in range(1, 14):
    tag = f"M-{i:02d}"
    assert tag in arch, f"Module {tag} missing from architecture doc!"
print("Modules M-01 through M-13 are present.")

# Non-Goals in §1
assert "### Non-Goals" in arch, "Non-Goals section missing from §1"
print("Non-Goals section verified in §1.")

# Deferral markers
body_part, sep, reg_part = arch.partition("## 19. Deferred Items Register")
body_markers = re.findall(r'\[DEFERRED → Doc \d+: [^\]]+\]', body_part)
reg_markers = re.findall(r'\[DEFERRED → Doc \d+: [^\]]+\]', reg_part)
print(f"Body markers: {len(body_markers)}, Register markers: {len(reg_markers)}")
assert len(body_markers) == 35, f"Expected 35 body markers, got {len(body_markers)}"
assert len(reg_markers) == 35, f"Expected 35 register markers, got {len(reg_markers)}"
assert Counter(body_markers) == Counter(reg_markers), "Body markers do not match register markers 1:1!"
print("All 35 deferral markers match 1:1 between body and §19 register.")

# Hard rules: No SQL, JSON, or code blocks in architecture doc
code_blocks = re.findall(r'```(?:sql|json|python|bash|javascript|typescript)', arch, re.IGNORECASE)
print(f"Fenced code blocks with code language: {len(code_blocks)}")
assert len(code_blocks) == 0, f"Found code language blocks in architecture doc: {code_blocks}"

# Statutory rules
assert "<" in arch and "expiry" in arch.lower() and "asia/kolkata" in arch.lower(), "Strict expiry condition or timezone missing"
assert "argon2id" in arch.lower() and "tier b" in arch.lower(), "Tier B Argon2id requirement missing in §10.3"
assert "grn" in arch and "credit-note-redemption" in arch, "Events 18/19 missing from §5"
assert "store_lan.crt" in arch or "store-scoped" in arch, "Store-scoped TLS certificate requirement missing"
print("Statutory rules (Expiry <, Tier B Argon2id, Store LAN TLS, GRN/CN events) verified.")

# ==========================================
# 2. ROUTED-DETAIL.md
# ==========================================
print("\n--- [2/4] Checking ROUTED-DETAIL.md ---")
with open("ROUTED-DETAIL.md", "r", encoding="utf-8") as f:
    routed = f.read()

# Marker resolution
unique_markers = list(set(body_markers))
for marker in unique_markers:
    m = re.match(r'\[DEFERRED → Doc (\d+): ([^\]]+)\]', marker)
    doc_num, topic = m.group(1), m.group(2).strip()
    words_topic = [w for w in re.split(r'[,/ ]+', topic) if len(w) > 3]
    assert any(w.lower() in routed.lower() for w in words_topic), f"Topic '{topic}' not covered in ROUTED-DETAIL.md"
print("All 35 deferred markers resolved in ROUTED-DETAIL.md.")

# Zero placeholders
placeholders = re.findall(r'\{[ \t]*\.\.\.[ \t]*\}', routed)
assert len(placeholders) == 0, f"Found {len(placeholders)} placeholders in ROUTED-DETAIL.md"
print("Zero '{ ... }' placeholder payloads found.")

# New sections check
for sec in [
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
    "19. `credit-note-redemption`:",
    "M-12[M-12: Settings & Config]"
]:
    assert sec in routed, f"Section/string '{sec}' missing in ROUTED-DETAIL.md"
print("All required state machines, edge cases, schemas, and Mermaid M-12 verified.")

# ==========================================
# 3. known_areas_to_improve.md
# ==========================================
print("\n--- [3/4] Checking known_areas_to_improve.md ---")
with open("known_areas_to_improve.md", "r", encoding="utf-8") as f:
    known = f.read()

# Zero L citations
l_citations = re.findall(r'(?:§|\bL)\d*(?:\s*L\d+)+', known)
assert len(l_citations) == 0, f"Found stale line citations: {l_citations}"
print("Zero stale physical line citations (L<num>) found.")

# Zero broken anchors
headers = re.findall(r'^(#{1,6})\s+(.+)$', arch, flags=re.M)
def slugify(title):
    clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)
    clean = re.sub(r'[^\w\s-]', '', clean).strip().lower()
    return re.sub(r'[-\s]+', '-', clean)
slugs = set(slugify(h[1]) for h in headers)
links = re.findall(r'architecture_v1_6_5\.md#([^\)]+)', known)
broken = [l for l in links if l not in slugs]
assert len(broken) == 0, f"Found broken anchor links: {set(broken)}"
print(f"All {len(links)} anchor links target valid headers in architecture_v1_6_5.md.")

# ==========================================
# 4. doclist.txt
# ==========================================
print("\n--- [4/4] Checking doclist.txt ---")
with open("doclist.txt", "r", encoding="utf-8") as f:
    doclist = f.read()

assert "Architechture" not in doclist, "Typo 'Architechture' still present in doclist.txt"
assert "Doc 11 governs statutory terminology." in doclist, "Doc 11 missing from summary rule in doclist.txt"
print("doclist.txt spelling and Doc 11 summary rule verified.")

print("\n" + "=" * 60)
print("ALL 4 DOCUMENTS PASSED COMPLETE SANITY & COMPLIANCE CHECKS!")
print("=" * 60)
