import zipfile, re
xml = zipfile.ZipFile('backend/data/templates/b7413cfd-1b21-4a18-a524-f5206ba9726b.docx').read('word/document.xml').decode('utf-8')
alts = re.findall(r'<mc:AlternateContent>.*?</mc:AlternateContent>', xml, re.DOTALL)
cbs = [a for a in alts if 'cx="144145"' in a]
patched = sum(1 for c in cbs if '<a:noFill/>' in c)
print(f'Checkbox noFill: {patched}/{len(cbs)}')
