import re

PLACEHOLDER = "BLANKZONE_PLACEHOLDER"
html = f"Hello {PLACEHOLDER}  {PLACEHOLDER}&nbsp;{PLACEHOLDER} World"
merged = re.sub(r'(?:' + PLACEHOLDER + r'(?:&nbsp;| )*)+', PLACEHOLDER, html)
print("ORIGINAL:", html)
print("MERGED:", merged)
