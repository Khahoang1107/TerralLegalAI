import sys, psycopg2
from docxtpl import DocxTemplate, RichText
import re
from zipfile import ZipFile

sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()
cur.execute("SELECT fields FROM form_schemas WHERE id = 'b7413cfd-1b21-4a18-a524-f5206ba9726b'")
fields_list = cur.fetchone()[0]
conn.close()

template_path = 'd:\\TerraLegalAI\\backend\\data\\templates\\b7413cfd-1b21-4a18-a524-f5206ba9726b.docx'
_var_pat = re.compile(r'\{\{\s*(\w+)\s*\}\}')
_SKIP = {'True', 'False', 'None', 'loop', 'range', 'lipsum'}
template_vars = set()
with ZipFile(template_path) as _zf:
    for _zname in _zf.namelist():
        if _zname.endswith('.xml'):
            _xml = _zf.read(_zname).decode('utf-8', errors='ignore')
            for _m in _var_pat.finditer(_xml):
                _v = _m.group(1)
                if not _v.startswith('_') and _v not in _SKIP:
                    template_vars.add(_v)

_tvar_to_label = {}
for _f in (fields_list or []):
    _fkey = _f.get('key', '')
    _fname = _f.get('name', '')
    if _fkey: _tvar_to_label[_fkey] = _fname or _fkey

preview_data = {}
for _tvar in template_vars:
    _label = _tvar_to_label.get(_tvar, _tvar)
    preview_data[_tvar] = RichText(f'[{_label}]', highlight='yellow')

print('Sample preview data:')
for k, v in list(preview_data.items())[:3]:
    print(k, '->', v)
    print(k, '-> XML ->', v.xml)
