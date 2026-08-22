import zipfile, re, os
path = 'backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx'
out_path = path + '.tmp'
with zipfile.ZipFile(path, 'r') as zin:
    with zipfile.ZipFile(out_path, 'w') as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = content.decode('utf-8')
                xml = xml.replace('{{ field_9007 }}', '')
                state = {'count': 0}
                def replace_rect(m):
                    rect = m.group(0)
                    if '17.35pt' in rect:
                        count = state['count']
                        group = (count // 13) + 1
                        idx = count % 13
                        state['count'] += 1
                        new_content = f'<v:textbox inset="0,0,0,0"><w:txbxContent><w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:t>{{{{ mst_{group}_{idx} }}}}</w:t></w:r></w:p></w:txbxContent></v:textbox>'
                        if '<v:textbox' in rect:
                            rect = re.sub(r'<v:textbox.*?</v:textbox>', new_content, rect)
                        else:
                            rect = rect.replace('</v:rect>', f'{new_content}</v:rect>')
                    return rect
                xml = re.sub(r'<v:rect.*?</v:rect>', replace_rect, xml)
                print(f"Patched {state['count']} squares.")
                content = xml.encode('utf-8')
            zout.writestr(item, content)
os.replace(out_path, path)
print("Done")
