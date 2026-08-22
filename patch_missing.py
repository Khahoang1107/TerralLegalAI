with open('backend/app/api/v1/forms.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    idx = i + 1
    if idx == 321:
        new_lines.append('''
    try:
        doc = DocxTemplate(template_path)
        
        if isinstance(payload, str):
            import json
            try: payload_dict = json.loads(payload)
            except: payload_dict = {}
        else:
            payload_dict = payload
            
        doc.render(payload_dict)
        
        temp_id = f"export_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "exports")
        os.makedirs(temp_dir, exist_ok=True)
        
        output_docx = os.path.join(temp_dir, f"{temp_id}.docx")
        doc.save(output_docx)
        
        submission = FormSubmission(
            form_id=form_id,
            user_id=str(current_user.id),
            data=payload_dict
        )
        db.add(submission)
        await db.commit()
        
        if format.lower() == "pdf":
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", 
                 "--outdir", temp_dir, output_docx],
                check=True, timeout=60,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            output_pdf = os.path.join(temp_dir, f"{temp_id}.pdf")
            if os.path.exists(output_pdf):
                return FileResponse(
                    output_pdf,
                    media_type="application/pdf",
                    filename=f"{form.name}.pdf"
                )
            else:
                raise Exception("Loi tao PDF")
                
        return FileResponse(
            output_docx,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{form.name}.docx"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-docx")
async def analyze_docx(file: UploadFile = File(...)):
    """
''')
    elif 322 <= idx <= 379:
        pass # skip
    elif idx == 581:
        new_lines.append('''
    """
    Xem lịch sử các lần người dùng xuất đơn từ biểu mẫu này.
    """
    result = await db.execute(
        select(FormSubmission)
        .where(
            FormSubmission.form_id == form_id,
            FormSubmission.user_id == str(current_user.id),
        )
        .order_by(FormSubmission.created_at.desc())
    )
    submissions = result.scalars().all()
    return submissions
''')
    elif 582 <= idx <= 589:
        pass # skip
    else:
        new_lines.append(line)

with open('backend/app/api/v1/forms.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
