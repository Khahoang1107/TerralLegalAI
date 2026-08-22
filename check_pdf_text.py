import PyPDF2

pdf_path = 'd:\\TerraLegalAI\\backend\\data\\exports\\debug_preview.pdf'
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ''
    for page in reader.pages:
        text += page.extract_text() + '\n'

if '▶' in text or '◀' in text or '[' in text:
    lines_with_mark = [l.strip() for l in text.split('\n') if '[' in l or '▶' in l]
    print(f"Found {len(lines_with_mark)} marked lines. Examples:")
    for l in lines_with_mark[:10]:
        print(l)
else:
    print("NO marks found in PDF text.")
