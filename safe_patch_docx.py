import zipfile
import re
from bs4 import BeautifulSoup
import os

def patch_template(doc_path):
    with zipfile.ZipFile(doc_path, 'r') as zin:
        xml_content = zin.read('word/document.xml')
        
    soup = BeautifulSoup(xml_content, 'xml')
    
    # Find all mc:AlternateContent tags
    alts = soup.find_all('mc:AlternateContent')
    replaced = 0
    
    for alt in alts:
        if alt.string and 'mst_' in alt.string:
            # wait, alt.string won't work if there are nested tags, let's use alt.text or find('w:t')
            pass
        
        # better: just check if 'mst_' in str(alt)
        alt_str = str(alt)
        if 'mst_' in alt_str:
            match = re.search(r'mst_(\d+)_(\d+)', alt_str)
            if match:
                g, idx = match.groups()
                # Create the replacement element
                # <w:r><w:rPr><w:bdr w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:rPr><w:t> {{ mst_g_idx }} </w:t></w:r>
                replacement_xml = f'<w:r><w:rPr><w:bdr w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:rPr><w:t> {{{{ mst_{g}_{idx} }}}} </w:t></w:r>'
                replacement_soup = BeautifulSoup(replacement_xml, 'xml')
                alt.replace_with(replacement_soup.find('w:r'))
                replaced += 1
                
    if replaced > 0:
        new_xml = str(soup)
        # BeautifulSoup might add xml declaration, let's make sure it's valid
        if new_xml.startswith('<?xml'):
            pass # Usually fine
        
        with zipfile.ZipFile(doc_path + ".temp", 'w') as zout:
            with zipfile.ZipFile(doc_path, 'r') as zin:
                for item in zin.infolist():
                    if item.filename == 'word/document.xml':
                        zout.writestr(item, new_xml.encode('utf-8'))
                    else:
                        zout.writestr(item, zin.read(item.filename))
        
        os.replace(doc_path + ".temp", doc_path)
        print(f"Patched {replaced} mst_ variables successfully.")
    else:
        print("No matching mc:AlternateContent found.")

if __name__ == "__main__":
    patch_template("backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx")
