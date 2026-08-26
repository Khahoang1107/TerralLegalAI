from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional
import json
import asyncio
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
    group_key: str | None = None
    digit_index: int | None = None
    depends_on: Any | None = None
    require_one_of_group: str | None = None

class FormVisualCreate(BaseModel):
    name: str
    procedure_type: str
    description: str = ""
    html_template: str = ""
    temp_id: str = ""
    mapping: Dict[str, str] = {}
    fields: List[FormVisualField]

class SaveMappingRequest(BaseModel):
    """Lưu ánh xạ số thứ tự vùng trống trên UI -> field key."""
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
    # Detect: ASCII dots/underscores (3+), tabs, checkbox ☐/□,
    # Unicode ellipsis (U+2026 …), repeated ellipsis (2+ consecutive),
    # and en/em dash sequences (–—)
    blank_pattern = re.compile(
        r'(?:[\._ ](?:&nbsp;|\s)*){3,}'     # ASCII dots/underscores 3+
        r'|\t+'                             # tabs
        r'|[\u2610\u25a1]'                  # checkbox ☐ or □
        r'|(?:\u2026){1,}'                  # Unicode ellipsis … (1+ repeated)
        r'|(?:\u2025){1,}'                  # Two-dot leader ‥
        r'|(?:[\u2013\u2014]){2,}'          # EN/EM dash sequences –– ——
    )
    doc = docx.Document(template_path)
    blank_idx = [1]  # Dùng list để nonlocal hoạt động trong nested func
    CHECKBOX_CHARS = ('\u2610', '\u25a1')  # ☐ or □

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
                    if matched in CHECKBOX_CHARS:
                        # Checkbox: dùng Jinja2 if, luôn dùng [x] hoặc [ ] để tránh lỗi font
                        new_text += f"{{% if {key} %}}[x]{{% else %}}[ ]{{% endif %}}"
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
                if not cell.text.strip():
                    key = mapping.get(str(blank_idx[0]))
                    if key:
                        if not cell.paragraphs:
                            p = cell.add_paragraph()
                        else:
                            p = cell.paragraphs[0]
                        p.add_run(f"{{{{ {key} }}}}")
                    blank_idx[0] += 1
                else:
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
    "label": "Kỳ khai năm",
    "description": "Năm kê khai thuế",
    "confidence": 0.95,
    "section": "nguoi_nop_thue"
  }}
]

Lưu ý:
- "label": tiếng Việt có dấu, viết hoa chữ cái đầu, tuyệt đối KHÔNG dùng snake_case (VD: Họ và tên, Ngày sinh, Nơi cấp, Trường hợp miễn giảm). Nhãn này sẽ hiển thị trực tiếp cho người dùng cuối.
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
    """Xóa file export tạm sau khi đã trả về cho người dùng."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"Error cleaning up file {path}: {e}")

def prepare_render_payload(form: FormSchema, payload_dict: dict) -> dict:
    """Chuẩn hóa giá trị boolean và tách chuỗi cho digit_group."""
    print("DEBUG PAYLOAD_DICT:", payload_dict)
    TRUE_VALUES = {"có", "co", "yes", "true", "1", "x", "☑"}
    
    field_types = {}
    if form and isinstance(form.fields, list):
        for f in form.fields:
            if isinstance(f, dict):
                field_types[f.get("name")] = f.get("type")
                if f.get("key"):
                    field_types[f.get("key")] = f.get("type")
                    
    normalized = {}
    for k, v in payload_dict.items():
        is_boolean = field_types.get(k) == "boolean"
        
        if isinstance(v, str) and v == "__SKIPPED__":
            normalized[k] = ""
        elif is_boolean and isinstance(v, str) and v.strip().lower() in TRUE_VALUES:
            normalized[k] = "✓"
        elif is_boolean and isinstance(v, str) and v.strip().lower() in {"không", "khong", "no", "false", "0", "☐"}:
            normalized[k] = ""
        elif isinstance(v, bool):
            normalized[k] = "✓" if v else ""
        else:
            normalized[k] = v

    if form and isinstance(form.fields, list):
        digit_groups_counter = {}
        
        for field in form.fields:
            if field.get("type") == "digit_group":
                gk = field.get("group_key") or field.get("name")
                fkey = field.get("key")
                idx = field.get("digit_index")
                
                # Giá trị người dùng nhập có thể nằm trong normalized[gk], normalized[fkey]
                val = normalized.get(gk, "")
                if not val:
                    val = normalized.get(fkey, "")
                if not val:
                    # Hoặc nằm trong normalized[field["name"]] nếu fallback
                    val = normalized.get(field.get("name", ""), "")
                
                if isinstance(val, str) and val:
                    if idx is not None:
                        # Trích xuất ký tự tại vị trí idx
                        if idx < len(val):
                            normalized[fkey] = val[idx]
                        else:
                            normalized[fkey] = " "
                    else:
                        normalized[fkey] = val
                        
                    # Hardcode alias cho 'ma_so_thue' để xử lý logic bên dưới
                    if field.get("name") == "ma_so_thue" or field.get("name") == "ma_so_thue_dai_ly_thue":
                        normalized[field.get("name")] = val

    # ── Fill mst_N_I variables for templates with digit-box MST fields ──────────
    # Group 1,3 = ma_so_thue (người nộp thuế)
    # Group 2,4 = mst_dai_ly / ma_so_thue_dai_ly_thue (đại lý thuế)
    # Some templates use all 6 groups for both, so we fill all permutations.

    def _fill_mst_groups(mst_str: str, *group_nums):
        digits = (mst_str or "").strip().ljust(13)
        for g in group_nums:
            for i in range(13):
                ch = digits[i] if i < len(digits) else " "
                normalized[f"mst_{g}_{i}"] = ch.strip()

    # Source 1: ma_so_thue (NNT) → groups 1, 3, 5
    mst_nnt = normalized.get("ma_so_thue") or normalized.get("mst_nnt") or ""
    if mst_nnt and isinstance(mst_nnt, str):
        _fill_mst_groups(mst_nnt, 1, 3, 5)
        normalized["ma_so_thue"] = ""  # hide raw string from template

    # Source 2: mst_dai_ly / ma_so_thue_dai_ly_thue → groups 2, 4, 6
    mst_dl = (normalized.get("mst_dai_ly") or
              normalized.get("ma_so_thue_dai_ly_thue") or
              normalized.get("mst_dl") or "")
    if mst_dl and isinstance(mst_dl, str):
        _fill_mst_groups(mst_dl, 2, 4, 6)
        for k in ("mst_dai_ly", "ma_so_thue_dai_ly_thue", "mst_dl"):
            if k in normalized:
                normalized[k] = ""

    print("DEBUG NORMALIZED:", normalized)
    return normalized



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

@router.put("/{form_id}/template")
async def update_form_template(
    form_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ghi đè file DOCX mẫu mới cho biểu mẫu đã có."""
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận định dạng .docx")
    
    result = await db.execute(select(FormSchema).where(FormSchema.id == form_id))
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy biểu mẫu")

    template_dir = "backend/data/templates"
    os.makedirs(template_dir, exist_ok=True)
    template_path = os.path.join(template_dir, f"{form.id}.docx")
    
    content = await file.read()
    with open(template_path, "wb") as f:
        f.write(content)
        
    return {"message": "Đã cập nhật file Word mẫu", "form_id": str(form.id)}


from docxtpl import DocxTemplate
from fastapi.responses import StreamingResponse
import io

class GenerateFormRequest(BaseModel):
    data: dict

@router.post("/{form_id}/generate")
async def generate_form(
    form_id: str,
    payload: GenerateFormRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    form = await db.scalar(select(FormSchema).where(FormSchema.id == form_id))
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy biểu mẫu")
        
    template_path = os.path.join("backend", "data", "templates", f"{form.id}.docx")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file DOCX gốc")
        
    try:
        doc = DocxTemplate(template_path)
        
        # Prepare payload with boolean normalization and digit_group splitting
        normalized_payload = prepare_render_payload(form, payload.data)
        doc.render(normalized_payload)
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        headers = {
            'Content-Disposition': f'attachment; filename="{form.name.replace(" ", "_")}.docx"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
        return StreamingResponse(
            file_stream, 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error generating DOCX: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi tạo văn bản")

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
        # Track which group_keys have already been checked to avoid duplicate errors
        _checked_groups: set = set()
        missing = []
        for f in form.fields:
            if not f.get("required", False):
                continue
            ftype = f.get("type", "text")
            if ftype == "digit_group":
                # For digit_group, check group_key OR field name (not individual slot key)
                gk = f.get("group_key") or f.get("name", "")
                if gk in _checked_groups:
                    continue
                _checked_groups.add(gk)
                has_value = bool(payload.get(gk) or payload.get(f.get("key", "")))
                if not has_value:
                    missing.append(f.get("name", f.get("key", "?")))
            else:
                # Normal field: check by key OR name
                has_value = bool(
                    payload.get(f.get("key", ""))
                    or payload.get(f.get("name", ""))
                )
                if not has_value:
                    missing.append(f.get("name", f.get("key", "?")))
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
        
        # Prepare payload with boolean normalization and digit_group splitting
        payload_dict = prepare_render_payload(form, payload_dict)
            
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
    mode: str = Query("user"),
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
        from docxtpl import DocxTemplate, RichText
        import re as _re
        from zipfile import ZipFile as _ZipFile

        # Prepare payload with boolean normalization and digit_group splitting
        normalized = prepare_render_payload(form, payload)

        # ── Step 1: Scan template XML to find ALL actual Jinja2 variable names ──
        _var_pat = _re.compile(r'\{\{\s*(\w+)\s*\}\}')
        _SKIP = {'True', 'False', 'None', 'loop', 'range', 'lipsum'}
        template_vars: set = set()
        try:
            with _ZipFile(template_path) as _zf:
                for _zname in _zf.namelist():
                    if _zname.endswith('.xml'):
                        _xml = _zf.read(_zname).decode('utf-8', errors='ignore')
                        for _m in _var_pat.finditer(_xml):
                            _v = _m.group(1)
                            if not _v.startswith('_') and _v not in _SKIP:
                                template_vars.add(_v)
        except Exception:
            pass

        # ── Step 2: Build reverse lookup: template_var → friendly display label ──
        # form.fields may have { "name": "ngay_viet_don", "key": "field_9003" }
        # If key != name, the template uses "key" (e.g. field_9003) but we want
        # to show the friendly "name" (ngay_viet_don) in the highlight label.
        fields_list = form.fields or []
        _tvar_to_label: dict = {}  # field_9003 → ngay_viet_don
        _friendly_to_tvar: dict = {}  # ngay_viet_don → field_9003
        for _f in fields_list:
            _fkey  = _f.get('key',  '') if isinstance(_f, dict) else getattr(_f, 'key',  '')
            _fname = _f.get('name', '') if isinstance(_f, dict) else getattr(_f, 'name', '')
            if _fkey:
                _tvar_to_label[_fkey] = _fname or _fkey
            if _fname and _fkey and _fkey != _fname:
                _friendly_to_tvar[_fname] = _fkey

        # ── Step 3: Build explicit context ────────────────────────────────────────
        preview_data: dict = {}

        for _tvar in template_vars:
            _label = _tvar_to_label.get(_tvar, _tvar)  # e.g. ngay_viet_don
            # Accept value by template var name OR by friendly name
            _val = normalized.get(_tvar) or normalized.get(_label) or ''
            if _val not in ('', None, False):
                preview_data[_tvar] = _val
            else:
                if mode == "template":
                    preview_data[_tvar] = f"[[ {_label} ]]"
                else:
                    preview_data[_tvar] = "............"

        # Carry over any remaining normalized values not handled above
        for _k, _v in normalized.items():
            _tk = _friendly_to_tvar.get(_k, _k)
            if _tk not in preview_data and _k not in preview_data:
                preview_data[_k] = _v

        # ── Step 4: Render ────────────────────────────────────────────────────────
        doc = DocxTemplate(template_path)
        print("DEBUG PREVIEW DATA:", preview_data)
        print("DEBUG TEMPLATE VARS:", template_vars)
        doc.render(preview_data)

        temp_id = f"preview_{uuid.uuid4().hex}"
        temp_dir = os.path.join("data", "exports")
        os.makedirs(temp_dir, exist_ok=True)

        output_docx = os.path.join(temp_dir, f"{temp_id}.docx")
        output_pdf  = os.path.join(temp_dir, f"{temp_id}.pdf")
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
                detail="Không tìm thấy LibreOffice. Vui lòng kiểm tra cài đặt container."
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"LibreOffice lỗi: {e.stderr.decode()[:300]}")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Timeout khi tạo PDF preview")

        if not os.path.exists(output_pdf):
            raise HTTPException(status_code=500, detail="LibreOffice không tạo được file PDF")

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
            r'|[\u2610\u25a1]'                  # checkbox ☐ or □
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
            
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    if not cell.text.strip():
                        # Empty cell blank
                        idx = blank_idx[0]
                        blank_types[idx] = 'text'
                        
                        g_val = idx // 256
                        b_val = idx % 256
                        
                        p = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()
                        r_blank = p.add_run(" " * 5)
                        r_blank.font.color.rgb = docx.shared.RGBColor(254, g_val, b_val)
                        if r_blank._r.rPr is not None:
                            for c in r_blank._r.rPr.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color'):
                                c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeColor', None)
                                c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeTint', None)
                                c.attrib.pop('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}themeShade', None)
                                
                        ai_full_text_parts.append(f" [[{idx}]] ")
                        blank_idx[0] += 1
                    else:
                        for p in cell.paragraphs:
                            process_paragraph(p)

        # ── Digit group: detect consecutive blank patterns in same paragraph ──────
        # Nếu 1 paragraph có >= 2 blank liên tiếp (vd: ____ ____ ____) → digit_group
        # Chúng ta chạy lại sau khi process_paragraph đã đánh số xong
        # blank_idx đã tăng, ta dùng ai_full_text_parts để phát hiện pattern
        # Approach: group các blank_types liên tiếp trong cùng 1 text part
        _par_digit_groups: dict[int, str] = {}  # idx → group_key (paragraph level)
        for _part in ai_full_text_parts:
            _blanks_in_part = [int(m.group(1)) for m in re.finditer(r'\[\[(\d+)\]\]', _part)]
            # Lấy nhãn ngữ cảnh bên trái cho group (text trước [[N]] đầu tiên)
            _ctx_match = re.search(r'(.{0,40})\s*\[\[', _part)
            _ctx_label = _ctx_match.group(1).strip().strip(':.,-\t') if _ctx_match else ''
            _ctx_label = re.sub(r'\[+\d+\]+', '', _ctx_label).strip()  # bỏ [06] v.v.
            if len(_blanks_in_part) >= 2:
                # Kiểm tra chúng liên tiếp (idx tăng dần và liền nhau)
                _consecutive = all(
                    _blanks_in_part[i+1] == _blanks_in_part[i] + 1
                    for i in range(len(_blanks_in_part) - 1)
                )
                if _consecutive:
                    # Tạo group_key từ context label hoặc fallback
                    _gkey = re.sub(r'\s+', '_', _ctx_label.lower())[:30] or f"group_{_blanks_in_part[0]}"
                    for _bidx in _blanks_in_part:
                        blank_types[_bidx] = 'digit_group'
                        _par_digit_groups[_bidx] = _gkey

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
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
        page_dimensions = []
        total_blanks = blank_idx[0] - 1

        for page_num, page in enumerate(pdf_doc):
            page_dimensions.append({
                "page": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height
            })
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
        predictions = {}
        
        # EXTRACT FALLBACK LABELS
        fallback_labels = {}
        for part in ai_full_text_parts:
            matches = list(re.finditer(r'\[\[(\d+)\]\]', part))
            for i, m in enumerate(matches):
                idx = m.group(1)
                start_search = matches[i-1].end() if i > 0 else 0
                text_before = part[start_search:m.start()].strip()
                if text_before:
                    label = text_before.strip(" :.-,\t\n")
                    snippets = re.split(r'[\n\t\[\]]', label)
                    label = snippets[-1].strip()
                    if label:
                        fallback_labels[idx] = label

        # Merge AI predictions vào zones, kèm field_type + confidence + section
        # Tính digit_index per group_key cho digit_group zones
        _group_key_counter: dict[str, int] = {}

        for z in zones:
            ftype = blank_types.get(z["idx"], "text")
            z["field_type"] = ftype
            z["fallback_name"] = fallback_labels.get(str(z["idx"]), "")
            pred = predictions.get(str(z["idx"]))
            if pred:
                z["suggested_label"] = pred["label"]
                z["suggested_description"] = pred["description"]
                z["confidence"] = pred.get("confidence", 0.5)
                z["section"] = pred.get("section", "khac")
            else:
                z["confidence"] = 0.0
                z["section"] = "khac"

            # Gán group_key + digit_index cho digit_group
            if ftype == "digit_group":
                # Ưu tiên group_key từ paragraph detect, fallback sang fallback_name
                gk = _par_digit_groups.get(z["idx"]) or z["fallback_name"] or f"group_{z['idx']}"
                gk = re.sub(r'[^\w]', '_', gk.lower()).strip('_')[:30]
                digit_idx = _group_key_counter.get(gk, 0)
                _group_key_counter[gk] = digit_idx + 1
                z["group_key"] = gk
                z["digit_index"] = digit_idx

        # Render m i trang th nh  nh (PNG) thay v  tr  v  PDF    tr nh l i react-pdf
        page_images = []
        for page_num, page in enumerate(pdf_doc):
            pix = page.get_pixmap(dpi=150)
            img_filename = f"{temp_id}_page_{page_num+1}.png"
            img_path = os.path.join("data", "uploaded", img_filename)
            pix.save(img_path)
            page_images.append(f"/api/v1/forms/preview/{img_filename}")
            
        # Clean up file r c
        for p in [marked_docx_path]:
            if os.path.exists(p):
                os.remove(p)
                
        return {
            "preview_url": page_images[0] if page_images else "",
            "page_images": page_images,
            "zones": zones,
            "text_blocks": text_blocks,
            "page_dimensions": page_dimensions,
            "total_blanks": total_blanks,
            "temp_id": temp_id,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích DOCX bằng PDF: {str(e)}")


class AiPredictRequest(BaseModel):
    temp_id: str
    zones: List[Dict[str, Any]]
    user_labels: Optional[Dict[str, str]] = None


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

        
        if body.user_labels:
            user_ctx = "\n\n--- THÔNG TIN NGƯỜI DÙNG ĐÃ CHỈNH SỬA ---\n"
            for idx, label in body.user_labels.items():
                if label.strip():
                    user_ctx += f"[[{idx}]]: {label}\n"
            full_text += user_ctx

        # Xử lý các vùng vẽ tay (manual zones) có idx rất lớn (Date.now())
        pdf_path = os.path.join("data", "uploaded", f"{body.temp_id}_marked.pdf")
        if os.path.exists(pdf_path):
            import fitz
            doc = fitz.open(pdf_path)
            manual_additions = []
            for z in body.zones:
                try:
                    idx_val = int(z.get("idx", 0))
                    if idx_val > 1000000:  # Manual zone
                        p_num = z.get("page", 1) - 1
                        x, y, w, h = z.get("x", 0), z.get("y", 0), z.get("width", 0), z.get("height", 0)
                        if 0 <= p_num < len(doc):
                            page = doc[p_num]
                            # Lấy text bên trái (max 300px)
                            rect_left = fitz.Rect(max(0, x - 300), max(0, y - 10), x + w/2, y + h + 10)
                            text_left = page.get_textbox(rect_left).strip()
                            # Lấy text bên trên (max 50px)
                            rect_up = fitz.Rect(max(0, x - 20), max(0, y - 50), x + w + 20, y + h/2)
                            text_up = page.get_textbox(rect_up).strip()
                            
                            combined = f"{text_up} {text_left}".strip()
                            if combined:
                                # Tạo ngữ cảnh giả lập cho AI đoán
                                manual_additions.append(f"{combined} [[{idx_val}]]")
                except ValueError:
                    pass
            doc.close()
            
            if manual_additions:
                full_text += "\n\n--- CÁC VÙNG BỔ SUNG ---\n" + "\n".join(manual_additions)

        predictions = await asyncio.to_thread(_predict_labels, full_text)

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
            "group_key": f.group_key,
            "digit_index": f.digit_index,
            "depends_on": getattr(f, "depends_on", None),
            "require_one_of_group": getattr(f, "require_one_of_group", None),
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
        import os
        temp_dir = os.path.join("data", "uploaded")
        raw_path = os.path.join(temp_dir, f"{data.temp_id}_raw.docx")
        
        if os.path.exists(raw_path):
            template_dir = "backend/data/templates"
            os.makedirs(template_dir, exist_ok=True)
            template_path = os.path.join(template_dir, f"{form.id}.docx")
            
            import shutil
            shutil.copy2(raw_path, template_path)
            
            # Auto-patch TerraLegal square shapes to support mst_ jinja tags
            try:
                import zipfile, re
                out_path = template_path + '.tmp'
                with zipfile.ZipFile(template_path, 'r') as zin:
                    with zipfile.ZipFile(out_path, 'w') as zout:
                        for item in zin.infolist():
                            content = zin.read(item.filename)
                            if item.filename == 'word/document.xml':
                                xml = content.decode('utf-8')
                                xml = xml.replace('{{ field_9007 }}', '')
                                state_patch = {'count': 0}
                                def make_text_para(group, idx):
                                    return (
                                        f'<w:p><w:pPr><w:jc w:val="center"/>'
                                        f'<w:spacing w:before="0" w:after="0"/></w:pPr>'
                                        f'<w:r><w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>'
                                        f'<w:t>{{{{ mst_{group}_{idx} }}}}</w:t></w:r></w:p>'
                                    )
                                def next_slot():
                                    c = state_patch['count']
                                    g = (c // 13) + 1
                                    i = c % 13
                                    state_patch['count'] += 1
                                    return g, i
                                def patch_wps_alt(m):
                                    alt = m.group(0)
                                    if '17.35pt' not in alt and 'cx="220345"' not in alt:
                                        return alt
                                    g, i = next_slot()
                                    tp = make_text_para(g, i)
                                    def patch_choice(cm):
                                        c = cm.group(0)
                                        c = re.sub(r'<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>', '<a:noFill/>', c)
                                        c = re.sub(r'<w:txbxContent>.*?</w:txbxContent>', f'<w:txbxContent>{tp}</w:txbxContent>', c, flags=re.DOTALL)
                                        return c
                                    alt = re.sub(r'<mc:Choice.*?</mc:Choice>', patch_choice, alt, flags=re.DOTALL)
                                    def patch_fallback_rect(rm):
                                        r = rm.group(0)
                                        r = re.sub(r'\bfillcolor="[^"]*"', '', r)
                                        r = re.sub(r'\bfilled="[^"]*"', '', r)
                                        r = r.replace('<v:rect ', '<v:rect filled="f" ')
                                        r = re.sub(r'<w:txbxContent>.*?</w:txbxContent>', f'<w:txbxContent>{tp}</w:txbxContent>', r, flags=re.DOTALL)
                                        return r
                                    alt = re.sub(r'<v:rect\b.*?</v:rect>', patch_fallback_rect, alt, flags=re.DOTALL)
                                    return alt
                                def patch_naked_rect(m):
                                    r = m.group(0)
                                    if '17.35pt' not in r:
                                        return r
                                    g, i = next_slot()
                                    tp = make_text_para(g, i)
                                    r = re.sub(r'\bfillcolor="[^"]*"', '', r)
                                    r = re.sub(r'\bfilled="[^"]*"', '', r)
                                    r = r.replace('<v:rect ', '<v:rect filled="f" ')
                                    if '<v:textbox' in r:
                                        r = re.sub(r'<w:txbxContent>.*?</w:txbxContent>', f'<w:txbxContent>{tp}</w:txbxContent>', r, flags=re.DOTALL)
                                    else:
                                        r = r.replace('</v:rect>', f'<v:textbox inset="0,0,0,0"><w:txbxContent>{tp}</w:txbxContent></v:textbox></v:rect>')
                                    return r
                                xml = re.sub(r'<mc:AlternateContent>.*?</mc:AlternateContent>', patch_wps_alt, xml, flags=re.DOTALL)
                                xml = re.sub(r'<v:rect\b.*?</v:rect>', patch_naked_rect, xml, flags=re.DOTALL)
                                content = xml.encode('utf-8')
                            zout.writestr(item, content)
                os.replace(out_path, template_path)
            except Exception as e:
                print(f"Failed to auto-patch squares: {e}")
            
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


