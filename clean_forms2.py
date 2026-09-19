with open('backend/app/api/v1/forms.py', 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', 'replace')

lines = text.split('\n')
clean_lines = []
for line in lines:
    if '"""' in line:
        continue # skip lines with quotes
    # Also skip lines with weird corrupted vietnamese characters
    if '\ufffd' in line:
        continue
    clean_lines.append(line)

with open('backend/app/api/v1/forms.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(clean_lines))
