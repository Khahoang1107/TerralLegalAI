import zipfile
import re
import os

docx_path = 'backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx'
out_path = 'backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx.new2'

with zipfile.ZipFile(docx_path, 'r') as zin, zipfile.ZipFile(out_path, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/document.xml':
            xml = data.decode('utf-8')
            
            # Find the text run for " Mã số thuế: " and append {{ field_9007 }}
            # The xml has: <w:t xml:space="preserve"> Mã số thuế: </w:t>
            xml = xml.replace(
                '<w:t xml:space="preserve"> Mã số thuế: </w:t>',
                '<w:t xml:space="preserve"> Mã số thuế: {{ field_9007 }}</w:t>'
            )
            
            zout.writestr(item, xml.encode('utf-8'))
        else:
            zout.writestr(item, data)

os.replace(out_path, docx_path)
print("DOCX text patched successfully!")
