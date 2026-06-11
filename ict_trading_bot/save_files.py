# save_files.py
import re, os

with open("deepseek_output.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Split on the file marker
blocks = re.split(r'### FILE: (.+?)\n', content)
# blocks[0] is text before first marker; then alternating filepath and code
if len(blocks) > 1:
    # remove leading text before first marker
    blocks = blocks[1:]
    for i in range(0, len(blocks), 2):
        filepath = blocks[i].strip()
        code = blocks[i+1].strip()
        # ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"Saved {filepath}")
else:
    print("No file markers found in deepseek_output.txt")