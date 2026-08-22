import zipfile
import glob
import xml.etree.ElementTree as ET

docx_files = glob.glob("data/uploaded/*.docx")
if not docx_files:
    print("No docx files found!")
else:
    file_path = docx_files[-1]  # Get the latest uploaded file
    print(f"Reading {file_path}...")
    with zipfile.ZipFile(file_path) as docx:
        xml_content = docx.read("word/document.xml")
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        
        # Iterate over first 20 paragraphs
        for i, p in enumerate(root.findall('.//w:p', namespaces)[:20]):
            print(f"--- Paragraph {i+1} ---")
            # Get paragraph properties
            pPr = p.find('w:pPr', namespaces)
            if pPr is not None:
                jc = pPr.find('w:jc', namespaces)
                if jc is not None:
                    print(f"Alignment (w:jc): {jc.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')}")
                pStyle = pPr.find('w:pStyle', namespaces)
                if pStyle is not None:
                    print(f"Style (w:pStyle): {pStyle.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')}")
                tabs = pPr.find('w:tabs', namespaces)
                if tabs is not None:
                    print("Custom tabs defined!")
            
            # Print text and tabs
            text_parts = []
            for run in p.findall('.//w:r', namespaces):
                for child in run:
                    if child.tag.endswith('t'):
                        text_parts.append(f"TEXT('{child.text}')")
                    elif child.tag.endswith('tab'):
                        text_parts.append("TAB")
            print("Content:", " ".join(text_parts))
