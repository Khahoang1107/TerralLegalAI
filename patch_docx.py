import zipfile
import re
import os

docx_path = 'backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx'
out_path = 'backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx.new'

with zipfile.ZipFile(docx_path, 'r') as zin, zipfile.ZipFile(out_path, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/document.xml':
            xml = data.decode('utf-8')
            # Fix DrawingML (Word 2007+)
            # Change behindDoc="0" to behindDoc="1"
            xml = re.sub(r'(<wp:anchor[^>]*?behindDoc=")0(")', r'\g<1>1\2', xml)
            
            # Fix VML (Word 2003-)
            # Change z-index:25... to z-index:-1
            xml = re.sub(r'z-index:\d+', 'z-index:-251661312', xml)
            
            # Also set filled="f" on v:rect just to be safe
            xml = re.sub(r'(<v:rect)([^>]*?)(/?>)', r'\g<1> filled="f"\2\3', xml)
            
            zout.writestr(item, xml.encode('utf-8'))
        else:
            zout.writestr(item, data)

os.replace(out_path, docx_path)
print("DOCX patched successfully!")
