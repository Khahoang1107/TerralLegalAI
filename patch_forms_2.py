import os

filepath = r"d:\TerraLegalAI\backend\app\api\v1\forms.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Modify analyze-docx
old_cleanup = """
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
"""
new_cleanup = """
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
        }
"""
content = content.replace(old_cleanup, new_cleanup)

# Update FormVisualCreate to accept temp_id and mapping
old_visual_create = """class FormVisualCreate(BaseModel):
    name: str
    procedure_type: str
    description: str = ""
    legal_basis: str | None = None
    html_template: str
    fields: list[FormField]"""

new_visual_create = """class FormVisualCreate(BaseModel):
    name: str
    procedure_type: str
    description: str = ""
    legal_basis: str | None = None
    temp_id: str
    mapping: dict[str, str]
    fields: list[FormField]"""
content = content.replace(old_visual_create, new_visual_create)

# Modify create_visual_form
old_create = """@router.post("/create-visual")
async def create_visual_form(
    data: FormVisualCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    form_fields = []
    for f in data.fields:
        form_fields.append({
            "key": f.key,
            "name": f.name,
            "description": f.description,
            "type": f.type,
            "required": f.required,
        })

    form = FormSchema(
        name=data.name,
        procedure_type=data.procedure_type,
        fields=form_fields,
        html_template=data.html_template,
        description=data.description,
        legal_basis=data.legal_basis,
        created_by=str(current_user.id),
    )

    db.add(form)
    await db.commit()
    await db.refresh(form)

    return {"message": "Tạo biểu mẫu thành công", "form_id": str(form.id)}"""

new_create = """@router.post("/create-visual")
async def create_visual_form(
    data: FormVisualCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    form_fields = []
    for f in data.fields:
        form_fields.append({
            "key": f.key,
            "name": f.name,
            "description": f.description,
            "type": f.type,
            "required": f.required,
        })

    form = FormSchema(
        name=data.name,
        procedure_type=data.procedure_type,
        fields=form_fields,
        html_template="",  # Không dùng nữa, PDF gen on the fly hoặc load qua _final.pdf
        description=data.description,
        legal_basis=data.legal_basis,
        mapping=data.mapping,
        created_by=str(current_user.id),
    )

    db.add(form)
    await db.commit()
    await db.refresh(form)

    # Lấy raw_path từ temp_id, bơm mapping vào DOCX và lưu thành {form_id}.docx
    temp_dir = os.path.join("data", "uploaded")
    raw_path = os.path.join(temp_dir, f"{data.temp_id}_raw.docx")
    
    if not os.path.exists(raw_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file DOCX tạm. Vui lòng tải lên lại.")
        
    template_dir = "backend/data/templates"
    os.makedirs(template_dir, exist_ok=True)
    template_path = os.path.join(template_dir, f"{form.id}.docx")
    
    # Copy raw sang template path
    import shutil
    shutil.copy2(raw_path, template_path)
    
    # Bơm tags vào template path
    if data.mapping:
        _inject_jinja_tags(template_path, data.mapping)
        
    # Xoá raw_path và final PDF
    os.remove(raw_path)
    final_pdf = os.path.join(temp_dir, f"{data.temp_id}_final.pdf")
    if os.path.exists(final_pdf):
        os.remove(final_pdf)

    return {"message": "Tạo biểu mẫu thành công", "form_id": str(form.id)}"""
content = content.replace(old_create, new_create)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched create_visual_form in forms.py")
