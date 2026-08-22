import fitz
import sys
import os

pdf_path = r"d:\TerraLegalAI\backend\data\uploaded\temp_7638240953ea4188aa0b8379dedc55bf_marked.pdf"

if not os.path.exists(pdf_path):
    print("Not found")
    sys.exit(1)

doc = fitz.open(pdf_path)

# Let's say user drew a box at 100, 100 with width 100, height 20
x, y, w, h = 100, 100, 100, 20
p_num = 0

if 0 <= p_num < len(doc):
    page = doc[p_num]
    # Lấy text bên trái (max 300px)
    rect_left = fitz.Rect(max(0, x - 300), max(0, y - 10), x + w/2, y + h + 10)
    text_left = page.get_textbox(rect_left).strip()
    # Lấy text bên trên (max 50px)
    rect_up = fitz.Rect(max(0, x - 20), max(0, y - 50), x + w + 20, y + h/2)
    text_up = page.get_textbox(rect_up).strip()
    
    combined = f"{text_up} {text_left}".strip()
    print("TEXT LEFT:", repr(text_left))
    print("TEXT UP:", repr(text_up))
    print("COMBINED:", repr(combined))

doc.close()
