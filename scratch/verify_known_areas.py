import re

arch = open('architecture_v1_6_5.md', encoding='utf-8').read()
known = open('known_areas_to_improve.md', encoding='utf-8').read()

# 1. Verify no L citations remain
l_citations = re.findall(r'(?:§|\bL)\d*(?:\s*L\d+)+', known)
print(f"Remaining L citations count: {len(l_citations)}")
if l_citations:
    print("Found L citations:", l_citations)
assert len(l_citations) == 0, f"Expected 0 L citations, got {len(l_citations)}"

# 2. Verify all anchor links to architecture_v1_6_5.md
headers = re.findall(r'^(#{1,6})\s+(.+)$', arch, flags=re.M)
def slugify(title):
    clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)
    clean = re.sub(r'[^\w\s-]', '', clean).strip().lower()
    return re.sub(r'[-\s]+', '-', clean)

slugs = set(slugify(h[1]) for h in headers)
links = re.findall(r'architecture_v1_6_5\.md#([^\)]+)', known)
print(f"Total anchor links to architecture doc: {len(links)}")

broken = [link for link in links if link not in slugs]
print(f"Broken anchor links count: {len(broken)}")
if broken:
    print("Broken links:", set(broken))
assert len(broken) == 0, f"Expected 0 broken links, got {len(broken)}"

print("\nALL KNOWN_AREAS_TO_IMPROVE.MD VERIFICATIONS PASSED!")
