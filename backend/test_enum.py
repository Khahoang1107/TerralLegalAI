from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io

doc = Document()
p = doc.add_paragraph("CENTERED TEXT")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER

print("Alignment is:", p.alignment)
print("Center Enum:", WD_ALIGN_PARAGRAPH.CENTER)
print("Right Enum:", WD_ALIGN_PARAGRAPH.RIGHT)
print("Justify Enum:", WD_ALIGN_PARAGRAPH.JUSTIFY)
