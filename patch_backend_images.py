import os
import re

filepath = r"d:\TerraLegalAI\backend\app\api\v1\forms.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace analyze_docx PDF response with Images response
old_block = """        # Lưu file PDF hoàn thiện
        final_pdf_path = os.path.join(temp_dir, f"{temp_id}_final.pdf")
        pdf_doc.save(final_pdf_path)
        pdf_doc.close()
        
        # Clean up file rác (KHÔNG xóa raw_path để create-visual dùng lại)
        for p in [marked_docx_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)
                
        preview_url = f"/api/v1/forms/preview/{temp_id}_final.pdf"
        
        return {
            "preview_url": preview_url,
            "zones": zones,
            "total_blanks": total_blanks,
            "temp_id": temp_id,
        }"""

new_block = """        # Render mỗi trang thành ảnh (PNG) thay vì trả về PDF để tránh lỗi react-pdf
        page_images = []
        for page_num, page in enumerate(pdf_doc):
            pix = page.get_pixmap(dpi=150)
            img_filename = f"{temp_id}_page_{page_num+1}.png"
            img_path = os.path.join("data", "uploaded", img_filename)
            pix.save(img_path)
            page_images.append(f"/api/v1/forms/preview/{img_filename}")
            
        pdf_doc.close()
        
        # Clean up file rác
        for p in [marked_docx_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)
                
        return {
            "preview_url": page_images[0] if page_images else "",
            "page_images": page_images,
            "zones": zones,
            "total_blanks": total_blanks,
            "temp_id": temp_id,
        }"""

content = content.replace(old_block, new_block)

# Update preview endpoint to support png
old_preview = """@router.get("/preview/{filename}")
async def get_preview_pdf(filename: str):
    file_path = os.path.join("data", "uploaded", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return FileResponse(file_path, media_type="application/pdf")"""

new_preview = """@router.get("/preview/{filename}")
async def get_preview_pdf(filename: str):
    file_path = os.path.join("data", "uploaded", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")
    media_type = "image/png" if filename.endswith(".png") else "application/pdf"
    return FileResponse(file_path, media_type=media_type)"""

content = content.replace(old_preview, new_preview)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
