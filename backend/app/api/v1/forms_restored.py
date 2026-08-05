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
    blank_pattern = re.compile(r'(\.{3,})')
    doc = docx.Document(template_path)
    blank_idx = [1]  # D ng list    nonlocal ho t   ng trong nested func

    def process_runs(runs):
        for run in runs:
            if not blank_pattern.search(run.text):
                continue
            new_text = ""
            last_end = 0
            for match in blank_pattern.finditer(run.text):
                start, end = match.span()
                new_text += run.text[last_end:start]
                key = mapping.get(str(blank_idx[0]))
                if key:
                    new_text += f"{{{{ {key} }}}}"
                else:
                    new_text += run.text[start:end]  # Gi  nguy n n u ch a map
                blank_idx[0] += 1
                last_end = end
            new_text += run.text[last_end:]
            run.text = new_text  # K  th a nguy n v n formatting (bold/italic/font)

    for p in doc.paragraphs:
        process_runs(p.runs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    process_runs(p.runs)

    doc.save(template_path)


def _predict_labels(full_text: str) -> Dict[str, Dict[str, str]]:
    """G i Gemini API    suy lu n nh n cho c c tr  ng [[B1]], [[B2]] d a tr n ng  c nh."""
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = f"""
B n l  chuy n gia s  h a bi u m u h nh ch nh. 
D  i   y l  n i dung c a m t bi u m u c  ch a c c ch  tr ng    c   nh d u b ng tag [[B1]], [[B2]], v.v.
Nhi m v  c a b n l  d a v o ng  c nh xung quanh m i ch  tr ng, h y  o n xem ng  i d ng c n  i n th ng tin g  v o ch  tr ng   .
Tr  v  k t qu    d ng m ng JSON g m c c object c  c u tr c:
[
  {{"idx": 1, "label": "ho_ten", "description": "H  v  t n ng  i n p"}},
  {{"idx": 2, "label": "cmnd", "description": "S  CMND/CCCD"}}
]
L u  :
- "label" ph i vi t b ng ti ng Vi t kh ng d u, n i nhau b ng d u g ch d  i (snake_case).
- "description" l  m  t  ng n g n, d  hi u    h  ng d n ng  i d ng nh p li u.
- Ph i tr  v    NG   nh d ng JSON m ng, kh ng th m b t k  text n o kh c.

--- N I DUNG BI U M U ---
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
                "description": item.get("description", "")
            }
        return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"L i khi d   o n nh n b ng Gemini: {e}")
        return {}


def _cleanup_export_file(path: str) -> None:
    """X a file export t m sau khi    tr  v  cho ng  i d ng."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass  # Kh ng l m gi n  o n request n u x a th t b i


#     Endpoints                                                     

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
    return {"message": "    n bi u m u (soft delete)", "form_id": form_id}


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
        raise HTTPException(status_code=404, detail="Kh ng t m th y file DOCX m u")

# MISSING LINE 321
# MISSING LINE 322
# MISSING LINE 323
# MISSING LINE 324
# MISSING LINE 325
# MISSING LINE 326
# MISSING LINE 327
# MISSING LINE 328
# MISSING LINE 329
# MISSING LINE 330
# MISSING LINE 331
# MISSING LINE 332
# MISSING LINE 333
# MISSING LINE 334
# MISSING LINE 335
# MISSING LINE 336
# MISSING LINE 337
# MISSING LINE 338
# MISSING LINE 339
# MISSING LINE 340
# MISSING LINE 341
# MISSING LINE 342
# MISSING LINE 343
# MISSING LINE 344
# MISSING LINE 345
# MISSING LINE 346
# MISSING LINE 347
# MISSING LINE 348
# MISSING LINE 349
# MISSING LINE 350
# MISSING LINE 351
# MISSING LINE 352
# MISSING LINE 353
# MISSING LINE 354
# MISSING LINE 355
# MISSING LINE 356
# MISSING LINE 357
# MISSING LINE 358
# MISSING LINE 359
# MISSING LINE 360
# MISSING LINE 361
# MISSING LINE 362
# MISSING LINE 363
# MISSING LINE 364
# MISSING LINE 365
# MISSING LINE 366
# MISSING LINE 367
# MISSING LINE 368
# MISSING LINE 369
# MISSING LINE 370
# MISSING LINE 371
# MISSING LINE 372
# MISSING LINE 373
# MISSING LINE 374
# MISSING LINE 375
# MISSING LINE 376
# MISSING LINE 377
# MISSING LINE 378
# MISSING LINE 379
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
        # B t d u ch m, g ch d  i li n ti p HO C tab leader
        blank_pattern = re.compile(r'(?:[\._](?:&nbsp;|\s)*){3,}|\t+')
        
        blank_idx = [1]
        tag_map = {}
        def process_runs(runs):
            for run in runs:
                if not run.text:
                    continue
                new_text = ""
                last_end = 0
                for match in blank_pattern.finditer(run.text):
                    start, end = match.span()
                    original_len = end - start
                    
                    new_text += run.text[last_end:start]
                    # Ch n tag  n: VD [[B1]]
                    tag = f"[[B{blank_idx[0]}]]"
                    
                    # N u l  tab (tab leader), pad    d i (vd 25 k  t )    UI t o zone to d  b m
                    if '\t' in match.group(0):
                        tag = tag.ljust(25, '_')
                    elif original_len > len(tag):
                        tag = tag + "_" * (original_len - len(tag))
                    
                    tag_map[blank_idx[0]] = tag
                    new_text += tag
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
        
        # G i LibreOffice convert sang PDF
        pdf_dir = temp_dir
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", 
             "--outdir", pdf_dir, marked_docx_path],
            check=True, timeout=60,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        pdf_path = os.path.join(pdf_dir, f"{temp_id}_marked.pdf")
        
        # M  PDF b ng PyMuPDF
        import fitz
        pdf_doc = fitz.open(pdf_path)
        zones = []
        total_blanks = blank_idx[0] - 1
        total_blanks = blank_idx[0] - 1
        
        for page_num, page in enumerate(pdf_doc):
            for i in range(1, total_blanks + 1):
                search_tag = tag_map.get(i, f"[[B{i}]]")
                rects = page.search_for(search_tag)
                for rect in rects:
                    zones.append({
                        "idx": i,
                        "page": page_num + 1,
                        "x": rect.x0,
                        "y": rect.y0,
                        "width": rect.width,
                        "height": rect.height
                    })
                    # Xo  ch  n y (v  h nh ch  nh t tr ng    l n)
                    page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
        
        #   c text t  docx      nh d u    g i AI
        full_text_parts = []
        for p in doc.paragraphs:
            if p.text:
                full_text_parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if p.text:
                            full_text_parts.append(p.text)
        
        full_text = "\\n".join(full_text_parts)
        predictions = _predict_labels(full_text)
        
        # Merge AI predictions v o zones
        for z in zones:
            pred = predictions.get(str(z["idx"]))
            if pred:
                z["suggested_label"] = pred["label"]
                z["suggested_description"] = pred["description"]

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
            "total_blanks": total_blanks,
            "temp_id": temp_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"L i ph n t ch DOCX b ng PDF: {str(e)}")


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
        legal_basis=data.legal_basis,
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

# MISSING LINE 581
# MISSING LINE 582
# MISSING LINE 583
# MISSING LINE 584
# MISSING LINE 585
# MISSING LINE 586
# MISSING LINE 587
# MISSING LINE 588
# MISSING LINE 589
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


