import re

with open('backend/app/api/v1/forms.py', 'rb') as f:
    raw = f.read()

# Try to decode with utf-8, replace bad chars
text = raw.decode('utf-8', 'replace')

# Remove all triple-quoted docstrings using regex
text_clean = re.sub(r'\"\"\"[\s\S]*?\"\"\"', '', text)

with open('backend/app/api/v1/forms.py', 'w', encoding='utf-8') as f:
    f.write(text_clean)
