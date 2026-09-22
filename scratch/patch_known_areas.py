import re

with open("known_areas_to_improve.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Fix broken anchors
anchor_replacements = {
    "architecture_v1_6_5.md#103-schedule-x--ndps-dual-prescription-custody--bound-ledger": "architecture_v1_6_5.md#103-schedule-x-ndps-dual-prescription-custody-bound-ledger",
    "architecture_v1_6_5.md#16-security--data-protection": "architecture_v1_6_5.md#16-security-data-protection",
    "architecture_v1_6_5.md#inter-store-stock-transfers--statutory-delivery-challans": "architecture_v1_6_5.md#near-expiry-vendor-returns-rtv-transfers",
    "architecture_v1_6_5.md#near-expiry-vendor-returns-rtv--alerts": "architecture_v1_6_5.md#near-expiry-vendor-returns-rtv-transfers",
    "architecture_v1_6_5.md#8-invoicing-gst-credit-notes-debit-notes--delivery-challans": "architecture_v1_6_5.md#8-invoicing-gst-credit-notes-debit-notes-delivery-challans",
    "architecture_v1_6_5.md#2-tech-stack--edge-infrastructure": "architecture_v1_6_5.md#2-tech-stack-edge-infrastructure",
    "architecture_v1_6_5.md#central-ingestion-atomicity--poison-pill-defense": "architecture_v1_6_5.md#central-ingestion-atomicity-poison-pill-quarantine",
    "architecture_v1_6_5.md#local-first-store-node--multi-counter-lan": "architecture_v1_6_5.md#local-first-store-node-multi-counter-lan",
    "architecture_v1_6_5.md#unit-of-measure-uom-hierarchy--fractional-billing": "architecture_v1_6_5.md#unit-of-measure-uom-hierarchy-fractional-billing",
}

for old_anchor, new_anchor in anchor_replacements.items():
    text = text.replace(old_anchor, new_anchor)

# 2. Replace line citations L<num> with D-XX
citations = [
    # Item 1: (§5 L125) -> (§5 D-39)
    (r'pattern Central uses \(§5 L125\)\.', r'pattern Central uses (§5 D-39).'),
    # Item 10: §15 L387 -> §15 (D-109)
    (r'§15 L387 already defines the trigger', r'§15 (D-109) already defines the trigger'),
    # Item 12: (§3 L10) -> (§8 D-121)
    (r'commit \(§3 L10\) releases', r'commit (§8 D-121) releases'),
    # Item 28: [architecture_v1_6_5.md §5 L150](architecture_v1_6_5.md#event-types), [§10.3 L298](...)
    (r'\[architecture_v1_6_5\.md §5 L150\]\(architecture_v1_6_5\.md#event-types\),\s*\[§10\.3 L298\]\(architecture_v1_6_5\.md#103-schedule-x-ndps-dual-prescription-custody-bound-ledger\)',
     r'[architecture_v1_6_5.md §5 (D-35)](architecture_v1_6_5.md#event-types), [§10.3 (D-88)](architecture_v1_6_5.md#103-schedule-x-ndps-dual-prescription-custody-bound-ledger)'),
    # Item 31: §5 L150 already carries
    (r'31\. \*\*Prescription Image Hash Verification on Retrieval\*\*: §5 L150 already carries',
     r'31. **Prescription Image Hash Verification on Retrieval**: §5 (D-35) already carries'),
    # Item 21: (CGNAT, no inbound ports, L83)
    (r'\(CGNAT, no inbound ports, L83\)', r'(CGNAT, no inbound ports, §4 D-26)'),
    # Item 32: (§17 L406)
    (r'staged rollouts \(§17 L406\)\.', r'staged rollouts (§17 D-117).'),
    # Item 33: (§2 L40)
    (r'promote_to_primary\.bat` \(§2 L40\),', r'promote_to_primary.bat` (§2 D-14),'),
    # Item 41: (§13 L343)
    (r'Manager force-closed \(§13 L343\)\.', r'Manager force-closed (§13 D-105).'),
    # Item 47: (§3 L63, §5 L160)
    (r'patient directory already exists \(§3 L63, §5 L160\)\.',
     r'patient directory already exists (§4 D-31, §5 D-42).'),
    # Item 18: (§6 L219) and (§6 L208)
    (r'adjustment-in flow \(§6 L219\) and the transfer breakage photo requirement \(§6 L208\)\.',
     r'adjustment-in flow (§6 D-54) and the transfer breakage photo requirement (§6 D-60).'),
    # Item 51: per §13 L343
    (r'transitions to `CLOSED_FORCE` per §13 L343,', r'transitions to `CLOSED_FORCE` per §13 (D-105),'),
    # Item 53: per §2 L54
    (r'UI warning triggered per §2 L54\.', r'UI warning triggered per §2 (D-22).'),
]

for pat, repl in citations:
    text, n = re.subn(pat, repl, text)
    if n == 0:
        print(f"WARNING: Citation pattern not replaced: {pat}")
    else:
        print(f"Replaced pattern: {pat} ({n} matches)")

with open("known_areas_to_improve.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved known_areas_to_improve.md")
