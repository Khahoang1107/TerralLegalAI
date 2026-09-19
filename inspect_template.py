import zipfile, re

path = 'backend/data/templates/b7413cfd-1b21-4a18-a524-f5206ba9726b.docx'
xml = zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')

alts = re.findall(r'<mc:AlternateContent>.*?</mc:AlternateContent>', xml, re.DOTALL)
checkboxes = [a for a in alts if 'cx="144145"' in a]

for i, cb in enumerate(checkboxes):
    # Get VML fallback margin info
    margin = re.search(r'margin-left:([\d.]+)pt;margin-top:([\d.]+)pt', cb)
    # Get anchor position from Choice
    posx = re.search(r'<wp:posOffset>(\d+)</wp:posOffset>', cb)
    posy_matches = re.findall(r'<wp:posOffset>(\d+)</wp:posOffset>', cb)
    
    print(f"Checkbox {i}:")
    if margin:
        print(f"  VML margin: left={margin.group(1)}pt top={margin.group(2)}pt")
    if len(posy_matches) >= 2:
        x_emu = int(posy_matches[0])
        y_emu = int(posy_matches[1])
        print(f"  OOXML pos: x={x_emu/12700:.1f}pt y={y_emu/12700:.1f}pt (from col/para)")
    # Check txbxContent
    txbx = re.search(r'<w:txbxContent>(.*?)</w:txbxContent>', cb, re.DOTALL)
    if txbx:
        txbx_text = re.sub(r'<[^>]+>', '', txbx.group(1))
        print(f"  txbxContent: {repr(txbx_text.strip())}")
    print()
