import docx, sys
sys.stdout.reconfigure(encoding='utf-8')
from docxtpl import DocxTemplate, RichText

template_path = 'd:\\TerraLegalAI\\backend\\data\\templates\\b7413cfd-1b21-4a18-a524-f5206ba9726b.docx'
doc = DocxTemplate(template_path)
ctx = {'truong_1': RichText('HELLO_WORLD', highlight='yellow')}
doc.render(ctx)
doc.save('d:\\TerraLegalAI\\test_docx.docx')

d = docx.Document('d:\\TerraLegalAI\\test_docx.docx')
found = False
for p in d.paragraphs[:10]:
    if 'HELLO_WORLD' in p.text:
        print("FOUND:", p.text)
        found = True
if not found:
    print("NOT FOUND!")
