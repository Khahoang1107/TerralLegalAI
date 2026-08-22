import sys
from docxtpl import DocxTemplate
doc = DocxTemplate('backend/data/templates/83e2efc7-6e5d-46b0-8a62-e70aeb311d5e.docx')
context = {f"mst_{g}_{i}": str((i+g)%10) for g in range(1,4) for i in range(13)}
doc.render(context)
doc.save('test_rendered.docx')
print("Saved test_rendered.docx")
