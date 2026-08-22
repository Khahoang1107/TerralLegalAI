import re, sys
from zipfile import ZipFile

# Test what Jinja2 vars are in the template for a given form
template_dir = r'd:\TerraLegalAI\backend\data\templates'
import os, glob

var_pat = re.compile(r'\{\{\s*(\w+)\s*\}\}')

for f in glob.glob(os.path.join(template_dir, '*.docx')):
    found = set()
    try:
        with ZipFile(f) as z:
            for name in z.namelist():
                if name.endswith('.xml'):
                    content = z.read(name).decode('utf-8', errors='ignore')
                    for m in var_pat.finditer(content):
                        v = m.group(1)
                        if not v.startswith('_'):
                            found.add(v)
    except Exception as e:
        print(f"ERR {f}: {e}")
        continue
    
    print(f"{os.path.basename(f)}: {sorted(found)[:5]} ... ({len(found)} total)")
