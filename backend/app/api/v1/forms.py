from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional
import json
import os
import uuid
import re
import subprocess
from datetime import datetime
from fastapi.responses import FileResponse
from backend.app.core.database import get_db
from backend.app.models.form_schema import FormSchema
from backend.app.models.form_submission import FormSubmission
from backend.app.core.security import get_current_user
from backend.app.models.user import User
from pydantic import BaseModel
import mammoth
import docx
from docx.oxml.ns import qn
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from lxml import etree
from docxtpl import DocxTemplate
from google import genai
from google.genai import types
from backend.app.core.config import settings

router = APIRouter(prefix="/forms", tags=["Forms"])

class FormSchemaCreate(BaseModel):
    name: str
    procedure_type: str
    fields: List[Dict[str, Any]]
    html_template: str | None = None
    description: str | None = None
    legal_basis: str | None = None

class FormVisualField(BaseModel):
    name: str
    description: str = ""
    required: bool = True
    type: str = "string"
    key: str | None = None  # alias for name

class FormVisualCreate(BaseModel):
    name: str
    procedure_type: str
    description: str = ""
    html_template: str = ""
    temp_id: str = ""
    mapping: Dict[str, str] = {}
    fields: List[FormVisualField]

class SaveMappingRequest(BaseModel):
    """ nh x  s  th  t  v ng tr ng tr n UI   field key."""
    mapping: Dict[str, str]  # VD: { "1": "ho_ten", "2": "cmnd" }


@router.get("/")
async def get_all_forms(
    procedure_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """L y danh s ch bi u m u  ang ho t   ng. C  th  l c theo procedure_type."""
    stmt = select(FormSchema).where(FormSchema.is_active == True)
    if procedure_type:
        stmt = stmt.where(FormSchema.procedure_type == procedure_type)
    result = await db.execute(stmt)
    forms = result.scalars().all()
    return forms

@router.post("/upload")
async def upload_form(
    json_file: UploadFile = File(...),
    docx_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload bi u m u m i: JSON schema + file DOCX m u.
    N u JSON c  tr  ng 'mapping', backend s  t    ng b m tag Jinja2 v o DOCX.
    """
    try:
        content = await json_file.read()
        data = json.loads(content)

        # Ki m tra validation c  b n
        required_keys = {"name", "procedure_type", "fields"}
        if not required_keys.issubset(data.keys()):
            raise HTTPException(
                status_code=400,
                detail=f"Thi u c c tr  ng b t bu c: {required_keys - data.keys()}"
            )

        form = FormSchema(
            name=data["name"],
            procedure_type=data["procedure_type"],
            fields=data["fields"],
            html_template=data.get("html_template"),
            description=data.get("description"),
            legal_basis=data.get("legal_basis"),
            mapping=data.get("mapping"),
            created_by=str(current_user.id),
        )
        db.add(form)
        await db.commit()
        await db.refresh(form)

        # L u file DOCX g c v o th  m c templates
        template_dir = "backend/data/templates"
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, f"{form.id}.docx")
        docx_bytes = await docx_file.read()
        with open(template_path, "wb") as f:
            f.write(docx_bytes)

        # N u JSON    k m s n mapping   t    ng b m tag Jinja2 v o DOCX ngay
        if data.get("mapping"):
            _inject_jinja_tags(template_path, data["mapping"])

        return {
            "message": "T i l n bi u m u th nh c ng",
            "form_id": str(form.id),
            "has_mapping": bool(data.get("mapping")),
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="File JSON kh ng h p l ")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#     Helper: B m tag Jinja2 v o DOCX                              

def _inject_jinja_tags(template_path: str, mapping: Dict[str, str]) -> None:
    """
    M  file DOCX t i template_path, d ng regex thay th  c c d i d u ch m/g ch
    theo th  t  xu t hi n b ng tag Jinja2 t  ng  ng trong mapping.

    mapping = { "1": "ho_ten", "2": "cmnd" }
    D i d u ch m l n 1   {{ ho_ten }}, l n 2   {{ cmnd }}, ...
    """
    # Detect: ASCII dots/underscores (3+), tabs, checkbox ☐,
    # Unicode ellipsis (U+2026 …), repeated ellipsis (2+ consecutive),
    # and en/em dash sequences (–—)
    blank_pattern = re.compile(
        r'(?:[\._ ](?:&nbsp;|\s)*){3,}'  # ASCII dots/underscores 3+
        r'|\t+'                             # tabs
        r'|\u2610'                          # checkbox ☐
        r'|(?:\u2026){1,}'                  # Unicode ellipsis … (1+ repeated)
        r'|(?:\u2025){1,}'                  # Two-dot leader ‥
        r'|(?:[\u2013\u2014]){2,}'          # EN/EM dash sequences –– ——
    )
    doc = docx.Document(template_path)
    blank_idx = [1]  # Dùng list để nonlocal hoạt động trong nested func
    CHECKBOX_CHAR = '\u2610'  # ☐
    CHECKBOX_CHECKED_CHAR = '\u2611'  # ☑

    def process_runs(runs):
        for run in runs:
            if not blank_pattern.search(run.text):
                continue
            new_text = ""
            last_end = 0
            for match in blank_pattern.finditer(run.text):
                start, end = match.span()
                new_text += run.text[last_end:start]
                matched = run.text[start:end]
                key = mapping.get(str(blank_idx[0]))
                if key:
                    if matched == CHECKBOX_CHAR:
                        # Checkbox: dùng Jinja2 if
                        new_text += f"{{% if {key} %}}\u2611{{% else %}}\u2610{{% endif %}}"
                    else:
                        new_text += f"{{{{ {key} }}}}"
                else:
                    new_text += matched  # Giữ nguyên nếu chưa map
                blank_idx[0] += 1
                last_end = end
            new_text += run.text[last_end:]
            run.text = new_text  # Kế thừa nguyên vẹn formatting (bold/italic/font)

    for p in doc.paragraphs:
        process_runs(p.runs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    process_runs(p.runs)

    doc.save(template_path)


def _predict_labels(full_text: str) -> Dict[str, Dict[str, str]]:
    """Gọi Gemini API để suy luận nhãn cho các trường, kèm confidence và section."""
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = f"""
Bạn là chuyên gia số hóa biểu mẫu hành chính Việt Nam.
Dưới đây là nội dung của một biểu mẫu có chứa các chỗ trống cần điền. Mỗi chỗ trống đã được tôi thay thế bằng một đánh dấu có dạng [[1]], [[2]], [[3]], v.v. (trong đó số bên trong là ID của chỗ trống).
Nhiệm vụ của bạn là dựa vào ngữ cảnh xung quanh mỗi chỗ trống, đoán xem người dùng cần điền thông tin gì cho chỗ trống đó.

Trả về kết quả dạng mảng JSON gồm các object có cấu trúc:
[
  {{
    "idx": 1,
    "label": "ky_khai_nam",
    "description": "Năm kê khai thuế",
    "confidence": 0.95,
    "section": "nguoi_nop_thue"
  }}
]

Lưu ý:
- "label": tiếng Việt không dấu, snake_case (VD: ho_ten, ngay_sinh, so_gcn)
- "description": mô tả ngắn gọn, dễ hiểu để hướng dẫn người dùng nhập liệu (tiếng Việt có dấu)
- "confidence": float từ 0.0 đến 1.0 — mức độ chắc chắn của bạn về nhãn này
  + 0.9–1.0: rất chắc (có số hiệu rõ ràng, ngữ cảnh rõ)
  + 0.6–0.9: khá chắc
  + 0.0–0.6: không chắc (trường mơ hồ, bị lặp lại, thiếu ngữ cảnh)
- "section": phân loại phần của biểu mẫu:
  + "nguoi_nop_thue": phần người nộp thuế / người kê khai tự điền
  + "thong_tin_dat": thông tin thửa đất, tài sản
  + "tinh_thue": căn cứ tính thuế, diện tích tính thuế
  + "co_quan": phần CƠ QUAN CHỨC NĂNG hoặc CƠ QUAN THUẾ điền (KHÔNG phải người dùng)
  + "khac": các trường khác
- Phải trả về ĐÚNG định dạng JSON mảng, không thêm bất kỳ text nào khác.
- Nếu một trường là phần "II. PHẦN XÁC ĐỊNH CỦA CƠ QUAN CHỨC NĂNG" thì section = "co_quan"

--- NỘI DUNG BIỂU MẪU ---
{full_text}
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        result = {}
        for item in data:
            result[str(item["idx"])] = {
                "label": item.get("label", ""),
                "description": item.get("description", ""),
                "confidence": float(item.get("confidence", 0.5)),
                "section": item.get("section", "khac"),
            }
        return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Lỗi khi dự đoán nhãn bằng Gemini: {e}")
        return {}


def _cleanup_export_file(path: str) -> None:
    """X a file export t m sau khi    tr  v  cho ng  i d ng."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass  # Kh ng l m gi n  o n request n u x a th t b i


#     Endpoints                                                     

@router.get("/{form_id}")
async def get_form(
    form_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Lấy chi tiết một biểu mẫu theo ID."""
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy biểu mẫu")
    return form


@router.delete("/{form_id}")
async def delete_form(
    form_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete:   t is_active=False thay v  x a h n kh i DB."""
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Kh ng t m th y bi u m u")

    form.is_active = False
    await db.commit()
    return {"message": "Đã ẩn biểu mẫu (soft delete)", "form_id": form_id}


class FormUpdateRequest(BaseModel):
    name: str
    procedure_type: str
    description: str = ""
    fields: Optional[list] = None


@router.put("/{form_id}")
async def update_form(
    form_id: str,
    data: FormUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật tên, loại thủ tục, mô tả và các nhãn (fields) của biểu mẫu."""
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy biểu mẫu")

    form.name = data.name
    form.procedure_type = data.procedure_type
    form.description = data.description
    if data.fields is not None:
        form.fields = data.fields
    await db.commit()
    await db.refresh(form)
    return {"message": "Cập nhật thành công", "form_id": str(form.id)}


@router.post("/{form_id}/save-mapping")
async def save_mapping(
    form_id: str,
    body: SaveMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    L u  nh x  (blank_idx   field_key) sau khi admin g n nh n tr n UI.
    Backend t    ng b m tag Jinja2 v o file DOCX t  ng  ng.
    """
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Kh ng t m th y bi u m u")

    template_path = f"backend/data/templates/{form_id}.docx"
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Kh ng t m th y file DOCX m u")

    try:
        _inject_jinja_tags(template_path, body.mapping)
        form.mapping = body.mapping
        await db.commit()
        return {
            "message": "L u mapping th nh c ng v     b m tag v o DOCX",
            "form_id": form_id,
            "total_mapped": len(body.mapping),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"L i khi b m tag v o DOCX: {str(e)}")


@router.post("/export/{form_id}")
async def export_form(
    form_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    format: str = Query(default="docx", pattern="^(docx|pdf)$"),
):
    """
    Sinh file t  bi u m u v i d  li u ng  i d ng cung c p.
    - Validation: Ki m tra c c field required ph i    c  i n   .
    - Format: H  tr  ?format=docx (m c   nh) ho c ?format=pdf.
    - L u l ch s  xu t   n v o b ng form_submissions.
    - T    ng d n d p file t m sau khi tr  v .
    """
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Kh ng t m th y bi u m u")

    #    1. Validation: ki m tra c c tr  ng required               
    if isinstance(form.fields, list):
        missing = [
            f.get("name", f.get("key", "?"))
            for f in form.fields
            if f.get("required", False) and not payload.get(f.get("key", ""))
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Thi u c c tr  ng b t bu c: {', '.join(missing)}"
            )

    template_path = f"backend/data/templates/{form_id}.docx"
    if not os.path.exists(template_path):
        template_path = "backend/data/templates/default.docx"
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Không tìm thấy file DOCX mẫu")

    try:
        doc = DocxTemplate(template_path)
        
        if isinstance(payload, str):
            import json
            try: payload_dict = json.loads(payload)
            except: payload_dict = {}
        else:
            payload_dict = payload
        
        # Chuyển giá trị "có"/"có"/"yes"/"true"/"1" thành True (boolean) cho Jinja2 if
        TRUE_VALUES = {"có", "co", "yes", "true", "1", "x", "☑"}
        normalized = {}
        for k, v in payload_dict.items():
            if isinstance(v, str) and v.strip().lower() in TRUE_VALUES:
                normalized[k] = True
            elif isinstance(v, str) and v.strip().lower() in {"không", "khong", "no", "false", "0", "☐"}:
                normalized[k] = False
            else:
                normalized[k] = v
        payload_dict = normalized
            
        doc.render(payload_dict)
        
        temp_id = f"export_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "exports")
        os.makedirs(temp_dir, exist_ok=True)
        
        output_docx = os.path.join(temp_dir, f"{temp_id}.docx")
        doc.save(output_docx)
        
        submission = FormSubmission(
            form_id=form_id,
            user_id=str(current_user.id),
            filled_data=payload_dict
        )
        db.add(submission)
        await db.commit()
        
        if format.lower() == "pdf":
            output_pdf = os.path.join(temp_dir, f"{temp_id}.pdf")
            import subprocess
            try:
                subprocess.run([
                    "libreoffice", "--headless", "--convert-to", "pdf",
                    "--outdir", os.path.abspath(temp_dir),
                    os.path.abspath(output_docx)
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                raise HTTPException(status_code=500, detail="Không tìm thấy LibreOffice. Vui lòng cài đặt LibreOffice hoặc chạy qua Docker để dùng tính năng xuất PDF.")
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


@router.post("/preview-pdf/{form_id}")
async def preview_pdf_form(
    form_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Render DOCX template với dữ liệu người dùng, convert sang PDF và trả về
    binary PDF để hiển thị inline trên trình duyệt (không download).
    """
    from fastapi.responses import Response

    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy biểu mẫu")

    template_path = f"backend/data/templates/{form_id}.docx"
    if not os.path.exists(template_path):
        template_path = "backend/data/templates/default.docx"
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Không tìm thấy file DOCX mẫu")

    try:
        # Chuẩn hóa payload (boolean values)
        TRUE_VALUES = {"có", "co", "yes", "true", "1", "x", "☑"}
        normalized = {}
        for k, v in payload.items():
            if isinstance(v, str) and v.strip().lower() in TRUE_VALUES:
                normalized[k] = True
            elif isinstance(v, str) and v.strip().lower() in {"không", "khong", "no", "false", "0", "☐"}:
                normalized[k] = False
            else:
                normalized[k] = v

        doc = DocxTemplate(template_path)
        doc.render(normalized)

        temp_id = f"preview_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "exports")
        os.makedirs(temp_dir, exist_ok=True)

        output_docx = os.path.join(temp_dir, f"{temp_id}.docx")
        output_pdf = os.path.join(temp_dir, f"{temp_id}.pdf")
        doc.save(output_docx)

        # Convert sang PDF bằng LibreOffice
        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", os.path.abspath(temp_dir),
                os.path.abspath(output_docx)
            ], check=True, capture_output=True, timeout=30)
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail="Không tìm thấy LibreOffice trong container. Vui lòng kiểm tra cài đặt."
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Timeout khi tạo PDF preview")

        if not os.path.exists(output_pdf):
            raise HTTPException(status_code=500, detail="Lỗi tạo PDF preview")

        with open(output_pdf, "rb") as f:
            pdf_bytes = f.read()

        # Dọn dẹp file tạm
        for p in [output_docx, output_pdf]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo PDF preview: {str(e)}")


@router.post("/analyze-docx")
async def analyze_docx(file: UploadFile = File(...)):
    """
    d ng PyMuPDF b c t ch t a    X,Y,W,H v  x a tag  n tr n PDF.
    """

    try:
        temp_id = f"temp_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "uploaded")
        os.makedirs(temp_dir, exist_ok=True)
        raw_path = os.path.join(temp_dir, f"{temp_id}_raw.docx")
        
        with open(raw_path, "wb") as f:
            f.write(await file.read())
            
        doc = docx.Document(raw_path)
        # Detect: ASCII dots/underscores (3+), tabs, checkbox ☐,
        # Unicode ellipsis (U+2026 …), repeated ellipsis, en/em dash sequences
        blank_pattern = re.compile(
            r'(?:[\._ ](?:&nbsp;|\s)*){3,}'  # ASCII dots/underscores 3+
            r'|\t+'                             # tabs
            r'|\u2610'                          # checkbox ☐
            r'|(?:\u2026){1,}'                  # Unicode ellipsis … (1+ repeated)
            r'|(?:\u2025){1,}'                  # Two-dot leader ‥
            r'|(?:[\u2013\u2014]){2,}'          # EN/EM dash sequences –– ——
        )
        CHECKBOX_CHAR = '\u2610'
        
        blank_idx = [1]
        tag_map = {}
        blank_types = {}  # idx -> 'checkbox' or 'text'
        ai_full_text_parts = []
        import copy
        def process_paragraph(paragraph):
            ai_par_text = ""
            # We must snapshot the runs because we will add new runs to the paragraph
            for run in list(paragraph.runs):
                if not run.text:
                    continue
                matches = list(blank_pattern.finditer(run.text))
                if not matches:
                    ai_par_text += run.text
                    continue
                
                text = run.text
                last_end = 0
                new_runs = []
                for match in matches:
                    start, end = match.span()
                    if start > last_end:
                        ai_par_text += text[last_end:start]
                        r1 = paragraph.add_run()
                        if run._r.rPr is not None:
                            r1._r.append(copy.deepcopy(run._r.rPr))
                        r1.text = text[last_end:start]
                        new_runs.append(r1)
                        
                    # Blank run WITH UNIQUE COLOR AND SHADING
                    r_blank = paragraph.add_run()
                    if run._r.rPr is not None:
                        new_rpr = copy.deepcopy(run._r.rPr)
                        for c in new_rpr.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color'):
                            new_rpr.remove(c)
                        r_blank._r.append(new_rpr)
                    r_blank.text = text[start:end]
                        
                    idx = blank_idx[0]
                    matched_text = text[start:end]
                    is_checkbox = (matched_text == CHECKBOX_CHAR)
                    blank_types[idx] = 'checkbox' if is_checkbox else 'text'
                    
                    g_val = idx // 256
                    b_val = idx % 256
                    
                    # 1. Font color
                    r_blank.font.color.rgb = docx.shared.RGBColor(254, g_val, b_val)
                    
                    if r_blank._r.rPr is not None:
                        for c in r_blank._r.rPr.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color'):
                            c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeColor', None)
                            c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeTint', None)
                            c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeShade', None)
                            
                    new_runs.append(r_blank)
                    
                    ai_par_text += f" [[{idx}]] "
                    blank_idx[0] += 1
                    last_end = end
                    
                if last_end < len(text):
                    ai_par_text += text[last_end:]
                    r_last = paragraph.add_run()
                    if run._r.rPr is not None:
                        r_last._r.append(copy.deepcopy(run._r.rPr))
                    r_last.text = text[last_end:]
                    new_runs.append(r_last)
                    
                # Move all new runs right after the original run
                current_element = run._r
                for new_run in new_runs:
                    current_element.addnext(new_run._r)
                    current_element = new_run._r
                    
                # Remove the original run
                run._r.getparent().remove(run._r)
            
            if ai_par_text.strip():
                ai_full_text_parts.append(ai_par_text)

        for p in doc.paragraphs:
            process_paragraph(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Detect empty table cell
                    if not cell.text.strip():
                        idx = blank_idx[0]
                        blank_types[idx] = 'text'
                        g_val = idx // 256
                        b_val = idx % 256
                        
                        if not cell.paragraphs:
                            p = cell.add_paragraph()
                        else:
                            p = cell.paragraphs[0]
                        
                        r_blank = p.add_run("   ")
                        r_blank.font.color.rgb = docx.shared.RGBColor(254, g_val, b_val)
                        
                        ai_full_text_parts.append(f" [[{idx}]] ")
                        blank_idx[0] += 1
                    else:
                        for p in cell.paragraphs:
                            process_paragraph(p)
                        
        marked_docx_path = os.path.join(temp_dir, f"{temp_id}_marked.docx")
        doc.save(marked_docx_path)
        
        # Convert sang PDF bằng LibreOffice
        pdf_path = os.path.join(temp_dir, f"{temp_id}_marked.pdf")
        import subprocess
        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", os.path.abspath(temp_dir),
                os.path.abspath(marked_docx_path)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="Không tìm thấy LibreOffice. Vui lòng cài đặt LibreOffice hoặc chạy qua Docker để dùng tính năng này.")
        
        # Mở PDF bằng PyMuPDF — scan text spans để tìm màu ẩn
        import fitz
        pdf_doc = fitz.open(pdf_path)
        zones = []
        text_blocks = []
        total_blanks = blank_idx[0] - 1

        for page_num, page in enumerate(pdf_doc):
            text_dict = page.get_text("dict")  # 'dict' has 'text' and 'color' in spans
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_text_parts = []
                    line_bbox = line.get("bbox")
                    for span in line.get("spans", []):
                        color_val = span.get("color", 0)
                        # PyMuPDF color is sRGB: R << 16 | G << 8 | B
                        if isinstance(color_val, int):
                            r = (color_val >> 16) & 255
                            g = (color_val >> 8) & 255
                            b = color_val & 255
                            
                            if r == 254:  # Detected our hidden color marker!
                                idx = g * 256 + b
                                if 0 < idx <= total_blanks:
                                    x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                                    zones.append({
                                        "idx": idx,
                                        "page": page_num + 1,
                                        "x": x0,
                                        "y": y0,
                                        "width": x1 - x0,
                                        "height": y1 - y0
                                    })
                                    # Wipe the colored text with a white rect to hide it in the UI
                                    rect = fitz.Rect(x0, y0, x1, y1)
                                    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                            else:
                                line_text_parts.append(span.get("text", ""))
                        else:
                            line_text_parts.append(span.get("text", ""))
                    
                    line_text = "".join(line_text_parts).strip()
                    if line_text:
                        text_blocks.append({
                            "page": page_num + 1,
                            "x": line_bbox[0],
                            "y": line_bbox[1],
                            "width": line_bbox[2] - line_bbox[0],
                            "height": line_bbox[3] - line_bbox[1],
                            "text": line_text
                        })
                                    
        # Ensure zones are sorted by idx for consistent UI and AI mapping
        zones.sort(key=lambda z: z["idx"])
        
        # Save perfectly synced ai_full_text_parts for ai-predict
        ai_text_path = os.path.join(temp_dir, f"{temp_id}_ai_text.txt")
        with open(ai_text_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ai_full_text_parts))
        
        full_text = "\n".join(ai_full_text_parts)
        predictions = _predict_labels(full_text)
        
        # Merge AI predictions vào zones, kèm field_type + confidence + section
        for z in zones:
            z["field_type"] = blank_types.get(z["idx"], "text")
            pred = predictions.get(str(z["idx"]))
            if pred:
                z["suggested_label"] = pred["label"]
                z["suggested_description"] = pred["description"]
                z["confidence"] = pred.get("confidence", 0.5)
                z["section"] = pred.get("section", "khac")
            else:
                z["confidence"] = 0.0
                z["section"] = "khac"

        # Render m i trang th nh  nh (PNG) thay v  tr  v  PDF    tr nh l i react-pdf
        page_images = []
        for page_num, page in enumerate(pdf_doc):
            pix = page.get_pixmap(dpi=150)
            img_filename = f"{temp_id}_page_{page_num+1}.png"
            img_path = os.path.join("data", "uploaded", img_filename)
            pix.save(img_path)
            page_images.append(f"/api/v1/forms/preview/{img_filename}")
            
        
        # Clean up file r c
        for p in [marked_docx_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)
                
        return {
            "preview_url": page_images[0] if page_images else "",
            "page_images": page_images,
            "zones": zones,
            "text_blocks": text_blocks,
            "total_blanks": total_blanks,
            "temp_id": temp_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"L i ph n t ch DOCX b ng PDF: {str(e)}")


class AiPredictRequest(BaseModel):
    temp_id: str
    zones: List[Dict[str, Any]]


@router.post("/ai-predict")
async def ai_predict(body: AiPredictRequest):
    """
    Gọi AI dự đoán nhãn cho các zones dựa trên raw DOCX đã upload.
    Trả về predictions kèm confidence + section cho từng zone.
    """
    raw_path = os.path.join("data", "uploaded", f"{body.temp_id}_raw.docx")
    if not os.path.exists(raw_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file DOCX tạm. Vui lòng upload lại.")

    try:
        # Read the perfectly synced AI text generated during analyze-docx
        ai_text_path = os.path.join("data", "uploaded", f"{body.temp_id}_ai_text.txt")
        if os.path.exists(ai_text_path):
            with open(ai_text_path, "r", encoding="utf-8") as f:
                full_text = f.read()
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy file văn bản đồng bộ. Vui lòng upload lại file.")
        predictions = _predict_labels(full_text)

        # Gắn predictions vào từng zone
        enriched_zones = []
        for z in body.zones:
            z_copy = dict(z)
            pred = predictions.get(str(z["idx"]))
            if pred:
                z_copy["suggested_label"] = pred["label"]
                z_copy["suggested_description"] = pred["description"]
                z_copy["confidence"] = pred.get("confidence", 0.5)
                z_copy["section"] = pred.get("section", "khac")
            else:
                z_copy.setdefault("confidence", 0.0)
                z_copy.setdefault("section", "khac")
            enriched_zones.append(z_copy)

        return {
            "predictions": predictions,
            "zones": enriched_zones,
            "total": len(predictions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI predict: {str(e)}")


@router.get("/preview/{filename}")
async def get_preview_pdf(filename: str):
    file_path = os.path.join("data", "uploaded", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File kh ng t n t i")
    media_type = "image/png" if filename.endswith(".png") else "application/pdf"
    return FileResponse(file_path, media_type=media_type)


@router.post("/create-visual")
async def create_visual_form(
    data: FormVisualCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    form_fields = []
    for f in data.fields:
        field_key = f.key or f.name
        form_fields.append({
            "key": field_key,
            "name": f.name,
            "description": f.description,
            "type": f.type,
            "required": f.required,
        })

    form = FormSchema(
        name=data.name,
        procedure_type=data.procedure_type,
        fields=form_fields,
        html_template="",
        description=data.description,
        legal_basis="",
        mapping=data.mapping,
        created_by=str(current_user.id),
    )

    db.add(form)
    await db.commit()
    await db.refresh(form)

    # L y raw_path t  temp_id, b m mapping v o DOCX v  l u th nh {form_id}.docx
    if data.temp_id:
        temp_dir = os.path.join("data", "uploaded")
        raw_path = os.path.join(temp_dir, f"{data.temp_id}_raw.docx")
        
        if os.path.exists(raw_path):
            template_dir = "backend/data/templates"
            os.makedirs(template_dir, exist_ok=True)
            template_path = os.path.join(template_dir, f"{form.id}.docx")
            
            import shutil
            shutil.copy2(raw_path, template_path)
            
            if data.mapping:
                _inject_jinja_tags(template_path, data.mapping)
                
            os.remove(raw_path)
            final_pdf = os.path.join(temp_dir, f"{data.temp_id}_final.pdf")
            if os.path.exists(final_pdf):
                os.remove(final_pdf)

    return {"message": "T o bi u m u th nh c ng", "form_id": str(form.id), "id": str(form.id), "name": data.name}


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



@router.get("/{form_id}")
async def get_form_detail(
    form_id: str,
    db: AsyncSession = Depends(get_db),
):
    """L y chi ti t m t bi u m u theo ID."""
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Kh ng t m th y bi u m u")
    return form


