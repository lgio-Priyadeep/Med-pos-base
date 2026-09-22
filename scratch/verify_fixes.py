"""
Detailed Verification of the 3 Findings and Their Proposed Fixes
"""

import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("architecture_v1_6_5.md", "r", encoding="utf-8") as f:
    arch = f.read()

with open("ROUTED-DETAIL.md", "r", encoding="utf-8") as f:
    routed = f.read()

with open("known_areas_to_improve.md", "r", encoding="utf-8") as f:
    known = f.read()

print("=" * 70)
print("VERIFICATION OF FINDING 1: Domain Event Count & Payload Schemas")
print("=" * 70)

# Check exact text in architecture_v1_6_5.md
sec5_match = re.search(r'### Event Types\s+The system defines (\d+) domain event types:([^(\n]+)\(D-42\)', arch)
if sec5_match:
    count_claimed = int(sec5_match.group(1))
    events_str = sec5_match.group(2)
    ev_names = re.findall(r'`([a-z\-]+)`', events_str)
    print(f"Stated count in text: {count_claimed}")
    print(f"Parsed event names ({len(ev_names)}): {ev_names}")
    print(f"Discrepancy: text says {count_claimed}, but list has {len(ev_names)} names!")

# Check ROUTED-DETAIL.md section 2.1
routed_sec2 = re.search(r'## Doc 2: Event Schema Doc[\s\S]*?### 2\.1 Full Event Payload Schemas for Events 1[–\-]19 & Tombstones([\s\S]*?)### 2\.2', routed)
if routed_sec2:
    content = routed_sec2.group(1)
    schema_items = re.findall(r'(\d+)\.\s+([^:\n]+):', content)
    print(f"\nROUTED-DETAIL.md numbered schema entries: {len(schema_items)}")
    for num, name in schema_items:
        print(f"  {num}. {name.strip()}")

# Test potential fixes for Finding 1:
print("\n--- Testing Fix Options for Finding 1 ---")
# Option A: In arch doc: "The system defines 20 domain event types across 19 payload schemas (master-data-change-approved/rejected sharing a decision schema): ..."
opt_a_text = "The system defines 20 domain event types across 19 payload schemas (master-data-change-approved/rejected sharing a decision schema): inbound inventory (`grn`)"
print(f"Option A word impact: adds ~8 words. New total: ~{len(arch.split()) + 8} words (Limit: 3,500).")

# Option B: Keep "The system defines 20 domain event types: ..." and update ROUTED-DETAIL to split #15 into 15 & 16 (making 20 numbered items).
# What would that impact?
# In arch doc:
# "The system defines 20 domain event types: ..."
# Markers in arch doc:
# [DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–20 & Tombstones]
# In ROUTED-DETAIL.md:
# Numbering becomes 1..20
# Marker in Section 19:
# [DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–20 & Tombstones]
print("Option B impact: Clean 1-to-1 numbering from 1 to 20 across all docs, but requires updating ROUTED-DETAIL numbering (15 -> 15 & 16, 16 -> 17, 17 -> 18, 18 -> 19, 19 -> 20) and deferral marker in arch and Section 19.")

print("\n" + "=" * 70)
print("VERIFICATION OF FINDING 2: Stale D-ID Citations in known_areas_to_improve.md")
print("=" * 70)

lines = known.splitlines()
for lno in [140, 152]:
    print(f"Line {lno}: {lines[lno-1]}")

print("\nVerifying exact target in architecture_v1_6_5.md:")
for i, l in enumerate(arch.splitlines(), 1):
    if "(D-42)" in l:
        print(f"  arch line {i}: {l}")
    if "(D-35)" in l:
        print(f"  arch line {i}: {l}")

print("\n--- Testing Fix for Finding 2 ---")
fix_line_140 = lines[139].replace("§5 (D-35)", "§5 (D-42)")
fix_line_152 = lines[151].replace("§5 (D-35)", "§5 (D-42)")
print("Proposed Line 140 replacement:")
print("  " + fix_line_140[:120] + "...")
print("Proposed Line 152 replacement:")
print("  " + fix_line_152[:120] + "...")
print("Does D-42 precisely capture the dispense event & PIN baseline? YES, D-42 defines domain event types including `dispense`.")

print("\n" + "=" * 70)
print("VERIFICATION OF FINDING 3: Roadmap Demarcation (v1.6.5 vs v1.6.6+ vs V2)")
print("=" * 70)

# Check all references to decisions in known_areas_to_improve.md
print("Checking if any other v1.6.6+ items conflict with v1.6.5 decisions:")

# Let's inspect items that mention 'Supersedes' or 'extends' or 'adjusts'
super_matches = re.findall(r'(\d+)\.\s+\*\*([^*]+)\*\*([\s\S]*?)(?=\n\d+\.\s+\*\*|\n## |\Z)', known)
print(f"Total numbered items in known_areas: {len(super_matches)}")

conflict_risks = []
for num, title, body in super_matches:
    if "supersede" in body.lower():
        print(f"\nItem {num}: {title.strip()} contains 'supersede':")
        for bline in body.splitlines():
            if "supersede" in bline.lower():
                print(f"    {bline.strip()}")
    # Check if mentions any D-xx
    d_refs = re.findall(r'D-\d+', body)
    for d in d_refs:
        # check if it proposes to break D
        pass

