import re
import os

filepath = r"d:\TerraLegalAI\backend\app\api\v1\forms.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern to find analyze_docx function
start_str = '@router.post("/analyze-docx")'
end_str = '@router.post("/create-visual")'

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx == -1 or end_idx == -1:
    print("Could not find bounds")
    exit(1)

new_analyze = '''@router.post("/analyze-docx")
async def analyze_docx(file: UploadFile = File(...)):
    """
    Phân tích DOCX, tạo tag ẩn, convert sang PDF bằng LibreOffice,
    dùng PyMuPDF bóc tách tọa độ X,Y,W,H và xóa tag ẩn trên PDF.
    """
    try:
        temp_id = f"temp_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "uploaded")
        os.makedirs(temp_dir, exist_ok=True)
        raw_path = os.path.join(temp_dir, f"{temp_id}_raw.docx")
        
        with open(raw_path, "wb") as f:
            f.write(await file.read())
            
        doc = docx.Document(raw_path)
        blank_pattern = re.compile(r'(?:\\.(?:&nbsp;| )*){3,}|(?:_(?:&nbsp;| )*){3,}|(?:-(?:&nbsp;| )*){5,}')
        
        blank_idx = [1]
        def process_runs(runs):
            for run in runs:
                if not run.text:
                    continue
                new_text = ""
                last_end = 0
                for match in blank_pattern.finditer(run.text):
                    start, end = match.span()
                    new_text += run.text[last_end:start]
                    # Chèn tag ẩn: VD [[B1]]
                    new_text += f"[[B{blank_idx[0]}]]"
                    blank_idx[0] += 1
                    last_end = end
                new_text += run.text[last_end:]
                run.text = new_text

        for p in doc.paragraphs:
            process_runs(p.runs)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        process_runs(p.runs)
                        
        marked_docx_path = os.path.join(temp_dir, f"{temp_id}_marked.docx")
        doc.save(marked_docx_path)
        
        # Gọi LibreOffice convert sang PDF
        pdf_dir = temp_dir
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", 
             "--outdir", pdf_dir, marked_docx_path],
            check=True, timeout=60,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        pdf_path = os.path.join(pdf_dir, f"{temp_id}_marked.pdf")
        
        # Mở PDF bằng PyMuPDF
        import fitz
        pdf_doc = fitz.open(pdf_path)
        zones = []
        total_blanks = blank_idx[0] - 1
        
        for page_num, page in enumerate(pdf_doc):
            for i in range(1, total_blanks + 1):
                rects = page.search_for(f"[[B{i}]]")
                for rect in rects:
                    zones.append({
                        "idx": i,
                        "page": page_num + 1,
                        "x": rect.x0,
                        "y": rect.y0,
                        "width": rect.width,
                        "height": rect.height
                    })
                    # Xoá chữ này (vẽ hình chữ nhật trắng đè lên)
                    page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
        
        # Lưu file PDF hoàn thiện
        final_pdf_path = os.path.join(temp_dir, f"{temp_id}_final.pdf")
        pdf_doc.save(final_pdf_path)
        pdf_doc.close()
        
        # Clean up file rác
        for p in [raw_path, marked_docx_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)
                
        preview_url = f"/api/v1/forms/preview/{temp_id}_final.pdf"
        
        return {
            "preview_url": preview_url,
            "zones": zones,
            "total_blanks": total_blanks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích DOCX bằng PDF: {str(e)}")


@router.get("/preview/{filename}")
async def get_preview_pdf(filename: str):
    file_path = os.path.join("data", "uploaded", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return FileResponse(file_path, media_type="application/pdf")


'''

new_content = content[:start_idx] + new_analyze + content[end_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Patch forms.py successfully")
