import zipfile
import re

def main():
    doc_path = "backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx"
    
    with zipfile.ZipFile(doc_path, 'r') as zin:
        xml_content = zin.read('word/document.xml').decode('utf-8')
    
    new_xml = re.sub(r'<mc:AlternateContent>.*?mst_(\d+)_(\d+).*?</mc:AlternateContent>', r'<w:r><w:rPr><w:bdr w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:rPr><w:t> {{ mst_\1_\2 }} </w:t></w:r>', xml_content)
    
    with zipfile.ZipFile(doc_path + ".temp", 'w') as zout:
        with zipfile.ZipFile(doc_path, 'r') as zin:
            for item in zin.infolist():
                if item.filename == 'word/document.xml':
                    zout.writestr(item, new_xml)
                else:
                    zout.writestr(item, zin.read(item.filename))
                    
    import os
    os.replace(doc_path + ".temp", doc_path)
    print("Replaced mc:AlternateContent with inline w:bdr")

if __name__ == "__main__":
    main()
