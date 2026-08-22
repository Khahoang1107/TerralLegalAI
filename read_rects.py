import zipfile, sys, re
sys.stdout.reconfigure(encoding='utf-8')
with zipfile.ZipFile('backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx') as z:
    xml = z.read('word/document.xml').decode('utf-8')

for p in re.findall(r'<w:p[ >].*?</w:p>', xml):
    rects = re.findall(r'<v:rect.*?</v:rect>', p)
    if rects:
        text = re.sub(r'<[^>]+>', '', p)
        print('P:', text.strip())
        for r in rects:
            m = re.search(r'style="([^"]+)"', r)
            if m:
                s = m.group(1)
                w = re.search(r'width:([^;]+)', s)
                h = re.search(r'height:([^;]+)', s)
                print('  w:', w.group(1) if w else '?', 'h:', h.group(1) if h else '?')
