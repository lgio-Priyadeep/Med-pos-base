with open('known_areas_to_improve.md', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'mirroring the `adjustment-in` flow (§6 L219) and the transfer breakage photo requirement (§6 L208).'
replacement = 'mirroring the `adjustment-in` flow (§6 D-54) and the transfer breakage photo requirement (§6 D-60).'

if target in text:
    text = text.replace(target, replacement)
    print("Successfully replaced target!")
else:
    print("Target string not found, doing regex replacement...")
    import re
    text = re.sub(
        r'mirroring the `adjustment-in` flow \(§6 L219\) and the transfer breakage photo requirement \(§6 L208\)\.',
        replacement,
        text
    )

with open('known_areas_to_improve.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Saved known_areas_to_improve.md.")
