import os
import re

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'setHtmlTemplate\s*\(.*?\);?', '', content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
