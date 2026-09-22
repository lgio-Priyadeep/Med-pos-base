with open("scratch/draft_content.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

curr_sec = "Header"
sec_words = {}
for line in lines:
    if line.startswith("#"):
        curr_sec = line.strip()
        sec_words[curr_sec] = 0
    else:
        if curr_sec not in sec_words:
            sec_words[curr_sec] = 0
        sec_words[curr_sec] += len(line.split())

total = sum(sec_words.values())
for sec, cnt in sec_words.items():
    print(f"{cnt:4d} words | {sec[:60]}")
print(f"Total: {total}")
