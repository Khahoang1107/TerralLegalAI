import re
import glob
import os

def test_extract(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    parts = text.split("\n")
    with open("output.txt", "a", encoding="utf-8") as out:
        for part in parts:
            matches = list(re.finditer(r'\[\[(\d+)\]\]', part))
            for i, m in enumerate(matches):
                idx = m.group(1)
                # Get text before the match
                start_search = matches[i-1].end() if i > 0 else 0
                text_before = part[start_search:m.start()].strip()
                
                # Clean up the text_before to get a nice label
                if text_before:
                    # Remove trailing colons, dots, dashes
                    label = text_before.strip(" :.-,\t\n")
                    # Split by some punctuation to get the last snippet
                    snippets = re.split(r'[\n\t\[\]]', label)
                    label = snippets[-1].strip()
                    if label:
                        out.write(f"Index {idx}: {label}\n")

with open("output.txt", "w", encoding="utf-8") as f:
    pass

for f in glob.glob("d:/TerraLegalAI/data/uploaded/*_ai_text.txt"):
    with open("output.txt", "a", encoding="utf-8") as out:
        out.write(f"\nTesting {os.path.basename(f)}\n")
    test_extract(f)
