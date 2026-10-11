"""
TerraLegalAI — Documents Management API
Xử lý upload, index, quản lý tài liệu PDF/DOCX.

Endpoints:
  POST   /api/v1/documents/upload       — Upload + auto index tài liệu
  GET    /api/v1/documents              — Danh sách tài liệu
  GET    /api/v1/documents/{id}         — Chi tiết tài liệu
  DELETE /api/v1/documents/{id}         — Xóa tài liệu + vectors
  PUT    /api/v1/documents/{id}/reindex — Tái index tài liệu
  GET    /api/v1/documents/stats        — Thống kê hệ thống
"""
import logging
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.document import Document, DocumentChunk, AmendmentAnalysis, ProvisionEffect
from backend.app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# Thư mục lưu file upload
UPLOAD_DIR = Path("data/uploaded")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB


# ─── Schemas ──────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    source_name: str
    file_path: Optional[str]
    group_type: str
    procedure_type: str
    status: str
    chunk_count: Optional[int] = 0
    created_at: str
    # Metadata hiệu lực
    document_number: Optional[str] = None
    validity_status: str = "Còn hiệu lực"
    promulgation_date: Optional[str] = None
    effective_date: Optional[str] = None
    issuing_agency: Optional[str] = None
    related_documents: Optional[list] = None

    model_config = {"from_attributes": True}


class ReindexResponse(BaseModel):
    document_id: str
    status: str
    message: str


class ChunkResponse(BaseModel):
    id: str
    text: str
    article: Optional[str] = None
    clause: Optional[str] = None
    field_type: Optional[str] = None
    validity_status: str = "active"
    validity_note: Optional[str] = None
    has_table: bool = False
    table_type: Optional[str] = None


class ConfirmAmendmentsRequest(BaseModel):
    confirmed_change_ids: list[str] = Field(default_factory=list)


class ChunkValidityRequest(BaseModel):
    validity_status: str
    validity_note: str = ""


class AffectedProvision(BaseModel):
    """Một điều/khoản/điểm cụ thể bị tác động."""
    article: str                    # VD: "Điều 5"
    clause: Optional[str] = None   # VD: "Khoản 2"
    point: Optional[str] = None    # VD: "Điểm a"
    action: str = "amend"          # amend | repeal | add


# ─── Action hợp lệ ─────────────────────────────────────────────────
# new           → Văn bản hoàn toàn mới
# amend         → Sửa đổi, bổ sung (còn hiệu lực một phần hoặc toàn bộ các điều khác)
# replace       → Thay thế toàn bộ (văn bản cũ hết hiệu lực)
# partial_repeal → Bãi bỏ một phần (một số Điều/Khoản bị bãi bỏ, còn lại vẫn có hiệu lực)
VALID_DOCUMENT_ACTIONS = {"new", "amend", "replace", "partial_repeal"}


def _build_doc_response(doc: Document, chunk_count: int = 0) -> DocumentResponse:
    """Helper: tạo DocumentResponse nhất quán từ Document ORM object."""
    return DocumentResponse(
        id=str(doc.id),
        source_name=doc.source_name,
        file_path=doc.file_path,
        group_type=doc.group_type,
        procedure_type=doc.procedure_type,
        status=doc.status,
        chunk_count=chunk_count,
        created_at=doc.created_at.isoformat(),
        document_number=doc.document_number,
        validity_status=doc.validity_status or "Còn hiệu lực",
        promulgation_date=doc.promulgation_date.isoformat() if doc.promulgation_date else None,
        effective_date=doc.effective_date.isoformat() if doc.effective_date else None,
        issuing_agency=doc.issuing_agency,
        related_documents=doc.related_documents,
    )


# ─── Background Task: Index Document ─────────────────────────────

def _index_document_sync(
    document_id: str,
    file_path: str,
    source_name: str,
    group_type: str,
    procedure_type: str,
    db_url: str,
):
    """
    Đồng bộ index một tài liệu (chạy trong background thread).
    Parse → Chunk → Embed → Upsert vào Qdrant → Cập nhật PostgreSQL.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    async def _run():
        from backend.app.document_processing.pdf_parser import PDFParser
        from backend.app.document_processing.docx_parser import DOCXParser
        from backend.app.document_processing.chunker import DocumentChunker
        from backend.app.embedding.embedding_model import EmbeddingModel
        from backend.app.embedding.vector_store import VectorStore

        engine = create_async_engine(db_url, echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            # Cập nhật status = indexing
            doc = await session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
            if not doc:
                logger.error(f"Document {document_id} not found in DB")
                return

            doc.status = "indexing"
            await session.commit()

            try:
                file_path_obj = Path(file_path)
                suffix = file_path_obj.suffix.lower()

                # Parse
                if suffix == ".pdf":
                    parser = PDFParser()
                elif suffix in (".docx", ".doc"):
                    parser = DOCXParser()
                else:
                    raise ValueError(f"Unsupported file type: {suffix}")

                parsed = parser.parse(file_path, source_name=f"{source_name} {doc.document_number or ''}")
                logger.info(f"Parsed {file_path}: {len(parsed.full_text):,} chars")

                # Chunk
                chunker = DocumentChunker()

                # v4: Dùng chunk_from_segments() nếu parser có segments (table-aware)
                segments = getattr(parsed, "segments", [])
                if segments and len(segments) > 1:
                    # Parser v2 trả về segments có bảng → dùng chiến lược table-aware
                    chunks = chunker.chunk_from_segments(
                        segments=segments,
                        source_file=file_path_obj.name,
                        source_name=source_name,
                        group_type=group_type,
                        procedure_type=procedure_type,
                    )
                else:
                    # Fallback: text thuần (PDF scan, parser cũ)
                    chunks = chunker.chunk(
                        text=parsed.full_text,
                        source_file=file_path_obj.name,
                        source_name=source_name,
                        group_type=group_type,
                        procedure_type=procedure_type,
                    )
                logger.info(f"Created {len(chunks)} chunks")
                if not chunks:
                    raise ValueError(f"Không thể trích xuất đoạn văn bản từ file {file_path_obj.name} (file có thể là bản scan ảnh không có chữ hoặc chưa được OCR).")

                # Lưu chunks vào PostgreSQL
                for c in chunks:
                    chunk_record = DocumentChunk(
                        id=c.chunk_id,
                        document_id=uuid.UUID(document_id),
                        text=c.text,
                        article=c.article,
                        clause=c.clause,
                        field_type=c.field_type,
                        has_table=getattr(c, "has_table", False),
                        table_type=getattr(c, "table_type", None),
                    )
                    session.add(chunk_record)

                # Embed
                emb_model = EmbeddingModel(model_name=settings.embedding_model_name)
                texts = [c.text for c in chunks]
                vectors = emb_model.encode(texts)

                # Upsert vào Qdrant
                vs = VectorStore(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port,
                    collection_name=settings.qdrant_collection_name,
                    embedding_dim=settings.embedding_dimension,
                )
                vs.create_collection_if_not_exists()
                count = vs.upsert_chunks(chunks, vectors)

                # Cập nhật status = indexed
                doc.status = "indexed"
                await session.commit()
                logger.info(f"✅ Document {document_id} indexed: {count} vectors")

            except Exception as e:
                logger.error(f"❌ Indexing failed for {document_id}: {e}", exc_info=True)
                await session.rollback()
                # Re-fetch doc after rollback since session state was cleared
                doc = await session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
                if doc:
                    doc.status = "error"
                    await session.commit()

        await engine.dispose()

    asyncio.run(_run())


def _extract_document_metadata(file_bytes: bytes, filename: str) -> dict:
    """
    Auto-extract metadata từ file PDF/DOCX và tên file.
    Trả về dict: source_name, document_number, promulgation_date, effective_date,
    issuing_agency, group_type, procedure_type, document_action, parent_hint,
    doc_type (loại văn bản: quyet_dinh | nghi_quyet | nghi_dinh | thong_tu | chi_thi | cong_van | luat).
    """
    import io
    import re
    text = ""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for p in pdf.pages[:3]:
                    t = p.extract_text()
                    if t:
                        text += "\n" + t
        except Exception as e:
            logger.warning(f"PDF metadata extraction failed: {e}")
    elif ext in (".docx", ".doc"):
        try:
            from docx import Document as DocxDoc
            doc = DocxDoc(io.BytesIO(file_bytes))
            for p in doc.paragraphs[:40]:
                if p.text.strip():
                    text += "\n" + p.text.strip()
        except Exception as e:
            logger.warning(f"DOCX metadata extraction failed: {e}")

    meta = {}
    fn_upper = filename.upper()
    first_lines = text[:300].upper()

    # ── 0. Nhận diện LOẠI văn bản ──────────────────────────────────
    # Thứ tự ưu tiên: Nghị quyết > Nghị định > Thông tư > Chỉ thị > Công văn > Quyết định > Luật
    DOC_TYPE_PATTERNS = [
        # (loại, ký_hiệu_chuẩn, nhóm, cơ_quan_mặc_định, regex_filename, regex_text_header)
        ("nghi_quyet",   "NQ",  "luat",       "Hội đồng nhân dân",
         re.compile(r'(?:NGHỊ\s*QUYẾT|NQ)[^A-Z0-9]', re.I),
         re.compile(r'(?:NGHỊ QUYẾT|NQ)\s*(?:SỐ|:)', re.I)),
        ("nghi_dinh",    "NĐ",  "luat",       "Chính phủ",
         re.compile(r'(?:NGHỊ\s*ĐỊNH|N[ĐD]-CP|ND-CP)[^A-Z0-9]?', re.I),
         re.compile(r'(?:NGHỊ ĐỊNH|NĐ-CP|ND-CP)\s*(?:SỐ|:)', re.I)),
        ("thong_tu",     "TT",  "luat",       "Bộ",
         re.compile(r'(?:THÔNG\s*TƯ|TT-[A-Z]{2,6})[^A-Z0-9]?', re.I),
         re.compile(r'(?:THÔNG TƯ|TT-)\s*(?:SỐ|:)', re.I)),
        ("chi_thi",      "CT",  "quyet_dinh", "Ủy ban nhân dân tỉnh Vĩnh Long",
         re.compile(r'(?:CHỈ\s*THỊ|CT-UBND)[^A-Z0-9]?', re.I),
         re.compile(r'(?:CHỈ THỊ|CT-UBND)\s*(?:SỐ|:)', re.I)),
        ("cong_van",     "CV",  "faq",        "Ủy ban nhân dân tỉnh Vĩnh Long",
         re.compile(r'(?:CÔNG\s*VĂN|CV-)[^A-Z0-9]?', re.I),
         re.compile(r'(?:CÔNG VĂN|CV)\s*(?:SỐ|:)', re.I)),
        ("luat",         "L",   "luat",       "Quốc hội",
         re.compile(r'(?:^|[\s_\-.])LUẬT[\s_\-.]', re.I),
         re.compile(r'^LUẬT\s+', re.I)),
        ("quyet_dinh",   "QĐ",  "quyet_dinh", "Ủy ban nhân dân tỉnh Vĩnh Long",
         re.compile(r'(?:QUYẾT\s*ĐỊNH|QĐ|QD)[^A-Z0-9]?', re.I),
         re.compile(r'(?:QUYẾT ĐỊNH|QĐ|QD)\s*(?:SỐ|:)', re.I)),
    ]

    detected_type = "quyet_dinh"
    detected_symbol = "QĐ"
    detected_group = "quyet_dinh"
    detected_agency = "Ủy ban nhân dân tỉnh Vĩnh Long"

    for doc_type, symbol, group, agency, fn_re, txt_re in DOC_TYPE_PATTERNS:
        if fn_re.search(fn_upper) or txt_re.search(first_lines):
            detected_type = doc_type
            detected_symbol = symbol
            detected_group = group
            detected_agency = agency
            break

    meta["doc_type"] = detected_type
    meta["issuing_agency"] = detected_agency

    # ── 1. Số / ký hiệu văn bản (tổng quát theo loại) ───────────────
    # Pattern chung: <số>/<năm>/<ký_hiệu>-<cơ_quan>  hoặc  <số>/<ký_hiệu>-<cơ_quan>
    SYMBOL_RE = r'(?:QĐ|QD|NQ|NĐ|ND|TT|CT|CV|TB|L)'
    AGENCY_RE = r'(?:UBND|HĐND|BTC|BTNMT|CP|BCT|BNN|BGDĐT|BVHTTDL|BXD|BCA|BTP|[A-ZĐ]{2,8})'
    # Tên tệp thường thay dấu / bằng _ hoặc - (VD: 12_2026_ND-CP.pdf).
    # Tách từng phần rồi chuẩn hóa lại về số hiệu pháp lý có dấu /.
    m_full = re.search(
        rf'(\d{{1,5}})(?:[\/_-](\d{{4}}))?[\/_-]({SYMBOL_RE})(?:[\-_]?({AGENCY_RE}))?',
        filename, re.IGNORECASE,
    )
    if m_full:
        sequence, year, symbol, agency = m_full.groups()
        meta["document_number"] = (
            f"{sequence}{f'/{year}' if year else ''}/{symbol.upper()}"
            f"-{agency.upper()}" if agency else f"{sequence}{f'/{year}' if year else ''}/{symbol.upper()}"
        )
    else:
        # Bóc từ nội dung văn bản
        m_num = re.search(
            rf'Số[:\s]+([0-9]+(?:/[0-9]{{4}})?/(?:{SYMBOL_RE})[\-A-ZĐa-zđ0-9_]*)',
            text, re.IGNORECASE
        )
        if m_num:
            meta["document_number"] = m_num.group(1).strip().upper()
        else:
            # Fallback legacy QĐ-UBND
            m_qd = re.search(r'([0-9]{2,5})/(?:QĐ|QD)-UBND', text, re.IGNORECASE)
            if m_qd:
                meta["document_number"] = f"{m_qd.group(1)}/QĐ-UBND"
    # Không suy đoán số hiệu khi không có bằng chứng trong tệp. Một số hiệu
    # bịa ra sẽ khiến quan hệ hiệu lực pháp lý bị sai nghiêm trọng hơn là để
    # trống để người quản trị nhập lại.
    doc_num = meta.get("document_number", "")

    # ── 2. Ngày ban hành & Ngày hiệu lực ────────────────────────────
    m_vl_date = re.search(r'(?:Vĩnh Long|Hà Nội|TP\.HCM|[A-ZĐ][a-zđ]+),\s*ngày\s+(\d+)\s*tháng\s+(\d{1,2})\s*năm\s+(\d{4})', text, re.IGNORECASE)
    if m_vl_date:
        d, m, y = m_vl_date.group(1).strip(), m_vl_date.group(2).strip(), m_vl_date.group(3).strip()
        if d:
            meta["promulgation_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
        else:
            meta["promulgation_date"] = f"{y}-{int(m):02d}-01"

    m_eff = re.search(r'có hiệu lực (?:thi hành )?(?:kể )?từ ngày\s+(\d{1,2})[/\s+tháng\s+]+(\d{1,2})[/\s+năm\s+]+(\d{4})', text)
    if m_eff:
        d, m, y = m_eff.group(1), m_eff.group(2), m_eff.group(3)
        meta["effective_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

    # ── 3. Tên nguồn, group_type, action, parent_hint ───────────────
    DOC_TYPE_LABELS = {
        "quyet_dinh":  "Quyết định",
        "nghi_quyet":  "Nghị quyết",
        "nghi_dinh":   "Nghị định",
        "thong_tu":    "Thông tư",
        "chi_thi":     "Chỉ thị",
        "cong_van":    "Công văn",
        "luat":        "Luật",
    }
    label = DOC_TYPE_LABELS.get(detected_type, "Văn bản")
    meta["group_type"] = detected_group

    if "PHỤ LỤC II" in fn_upper or first_lines.startswith("PHỤ LỤC II"):
        meta["source_name"] = f"Phụ lục II - Quy trình nội bộ 38 TTHC{f' (kèm {doc_num})' if doc_num else ''}"
        meta["procedure_type"] = "all"
        meta["document_action"] = "replace"
        meta["parent_hint"] = "1467"
    elif "PHỤ LỤC I" in fn_upper or first_lines.startswith("PHỤ LỤC I"):
        meta["source_name"] = f"Phụ lục I - 38 TTHC đặc thù{f' (kèm {doc_num})' if doc_num else ''}"
        meta["procedure_type"] = "all"
        meta["document_action"] = "replace"
        meta["parent_hint"] = "1085"
    else:
        meta["source_name"] = f"{label} {doc_num}".strip()
        meta["procedure_type"] = "all"
        meta["document_action"] = "new"
        meta["parent_hint"] = None

    # Suy đoán action từ nội dung ("thay thế", "sửa đổi", "bãi bỏ")
    if re.search(r'thay\s*thế\s+(?:toàn\s*bộ|quyết\s*định)', text, re.I):
        meta["document_action"] = "replace"
    elif re.search(r'(?:sửa\s*đổi|bổ\s*sung).*(?:điều|khoản|điểm)', text, re.I) and re.search(r'bãi\s*bỏ.*(?:điều|khoản)', text, re.I):
        meta["document_action"] = "partial_repeal"   # Vừa sửa vừa bãi bỏ một phần
    elif re.search(r'(?:sửa\s*đổi|bổ\s*sung).*(?:điều|khoản|điểm)', text, re.I):
        meta["document_action"] = "amend"
    elif re.search(r'bãi\s*bỏ.*(?:điều|khoản)', text, re.I):
        meta["document_action"] = "partial_repeal"

    return meta


@router.post("/documents/extract-metadata")
async def extract_document_metadata_endpoint(
    file: UploadFile = File(..., description="File PDF hoặc DOCX để trích xuất metadata"),
    current_user: User = Depends(get_current_user),
):
    """
    Auto-extract metadata từ file tải lên trước khi người dùng submit.
    Hỗ trợ auto-fill tên nguồn, số hiệu, ngày ban hành, ngày hiệu lực, cơ quan ban hành, loại cập nhật.
    """
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thực hiện")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 200MB)")

    metadata = _extract_document_metadata(content, file.filename or "")
    return metadata


# ─── Endpoints ────────────────────────────────────────────────────

@router.post("/documents/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File PDF hoặc DOCX"),
    source_name: str = Form(..., description="Tên nguồn tài liệu, VD: QĐ 1085/QĐ-UBND"),
    group_type: str = Form(..., description="Nhóm: quyet_dinh | nghi_quyet | nghi_dinh | thong_tu | chi_thi | cong_van | luat | bieu_mau | faq"),
    procedure_type: str = Form(..., description="Thủ tục: chuyen_nhuong | cap_doi | all"),
    # ── Metadata hiệu lực ──
    document_action: str = Form("new", description="Hành động: new | amend | replace | partial_repeal"),
    document_number: Optional[str] = Form(None, description="Số/ký hiệu VB, VD: 1085/QĐ-UBND"),
    promulgation_date: Optional[str] = Form(None, description="Ngày ban hành (YYYY-MM-DD)"),
    effective_date: Optional[str] = Form(None, description="Ngày hiệu lực (YYYY-MM-DD)"),
    issuing_agency: Optional[str] = Form(None, description="Cơ quan ban hành"),
    parent_document_id: Optional[str] = Form(None, description="ID văn bản gốc đơn lẻ (tương thích ngược)"),
    parent_document_ids: Optional[str] = Form(None, description="Danh sách ID văn bản gốc phân tách bởi dấu phẩy"),
    # ── Phạm vi tác động (amend / partial_repeal) ──
    amendment_scope: str = Form("full", description="Phạm vi: full | partial"),
    affected_provisions: Optional[str] = Form(None, description='JSON array điều/khoản bị tác động, VD: [{"article":"Điều 5","clause":"Khoản 2","action":"amend"}]'),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload tài liệu mới / sửa đổi bổ sung / thay thế toàn bộ / bãi bỏ một phần.
    Hỗ trợ khai báo rõ Điều/Khoản/Điểm bị tác động qua affected_provisions.
    """
    import json as _json

    # Chỉ admin mới được upload
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được upload tài liệu")

    # Validate document_action
    if document_action not in VALID_DOCUMENT_ACTIONS:
        raise HTTPException(status_code=400, detail=f"document_action không hợp lệ: {document_action}. Chấp nhận: {', '.join(sorted(VALID_DOCUMENT_ACTIONS))}")

    # Parse affected_provisions
    parsed_provisions: list[dict] = []
    if affected_provisions:
        try:
            parsed_provisions = _json.loads(affected_provisions)
            if not isinstance(parsed_provisions, list):
                raise ValueError("Phải là mảng JSON")
        except (ValueError, _json.JSONDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"affected_provisions không hợp lệ: {e}")

        allowed_provision_actions = {"amend", "repeal", "add"}
        for index, provision in enumerate(parsed_provisions, start=1):
            if not isinstance(provision, dict) or not str(provision.get("article", "")).strip():
                raise HTTPException(status_code=400, detail=f"affected_provisions dòng {index} phải có trường article")
            if provision.get("action", "repeal") not in allowed_provision_actions:
                raise HTTPException(status_code=400, detail=f"affected_provisions dòng {index} có action không hợp lệ")

    # amendment_scope
    if amendment_scope not in ("full", "partial"):
        amendment_scope = "full"

    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không hỗ trợ. Chấp nhận: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate group_type và procedure_type
    valid_groups = {
        "quyet_dinh", "nghi_quyet", "nghi_dinh", "thong_tu",
        "chi_thi", "cong_van", "luat", "bieu_mau", "faq",
    }
    valid_procedures = {"chuyen_nhuong", "cap_doi", "tang_cho", "all"}
    if group_type not in valid_groups:
        raise HTTPException(status_code=400, detail=f"group_type không hợp lệ: {group_type}. Chấp nhận: {', '.join(sorted(valid_groups))}")
    if procedure_type not in valid_procedures:
        raise HTTPException(status_code=400, detail=f"procedure_type không hợp lệ: {procedure_type}")

    # Validate parent_document_ids khi amend/replace/partial_repeal
    parent_docs = []
    if document_action in ("amend", "replace", "partial_repeal"):
        target_ids = []
        if parent_document_ids:
            target_ids.extend([x.strip() for x in parent_document_ids.split(",") if x.strip()])
        if parent_document_id and parent_document_id.strip() not in target_ids:
            target_ids.append(parent_document_id.strip())

        if not target_ids:
            raise HTTPException(status_code=400, detail="Phải chọn ít nhất một văn bản gốc khi sửa đổi/thay thế.")

        for pid in target_ids:
            try:
                parent_uuid = uuid.UUID(pid)
            except ValueError:
                continue
            doc_found = await db.scalar(select(Document).where(Document.id == parent_uuid))
            if doc_found:
                parent_docs.append(doc_found)

        if not parent_docs:
            raise HTTPException(status_code=404, detail="Không tìm thấy văn bản gốc được chỉ định.")

    # Parse dates
    parsed_promulgation = None
    parsed_effective = None
    try:
        if promulgation_date:
            parsed_promulgation = date.fromisoformat(promulgation_date)
        if effective_date:
            parsed_effective = date.fromisoformat(effective_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ngày không hợp lệ (định dạng: YYYY-MM-DD)")

    # Kiểm tra duplicate source_name
    existing = await db.scalar(select(Document).where(Document.source_name == source_name))
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Tài liệu với source_name '{source_name}' đã tồn tại (id: {existing.id}). Dùng /reindex nếu muốn cập nhật.",
        )

    # Lưu file lên disk
    doc_id = str(uuid.uuid4())
    save_filename = f"{doc_id}{suffix}"
    save_path = UPLOAD_DIR / save_filename

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 200MB)")

    save_path.write_bytes(content)
    logger.info(f"Saved upload: {save_path} ({len(content) / 1024:.1f} KB)")

    # ── Xử lý quan hệ văn bản ────────────────────────────────────
    new_related: list[dict] = []
    effective_date_str = parsed_effective.isoformat() if parsed_effective else None

    # ── Hàm helper tạo entry related_documents ───────────────────
    def _make_relation_entry(relation: str) -> dict:
        entry: dict = {
            "relation": relation,
            "effective_date": effective_date_str,
        }
        if amendment_scope == "partial" or parsed_provisions:
            entry["scope"] = "partial"
            entry["affected_provisions"] = parsed_provisions
        else:
            entry["scope"] = "full"
        return entry

    affected_chunk_ids: set[uuid.UUID] = set()

    if document_action == "amend" and parent_docs:
        for p_doc in parent_docs:
            p_doc.validity_status = "Đã sửa đổi bổ sung"
            parent_related = list(p_doc.related_documents or [])
            parent_related.append({
                "document_id": doc_id,
                "source_name": source_name,
                **_make_relation_entry("amended_by"),
            })
            p_doc.related_documents = parent_related

            new_related.append({
                "document_id": str(p_doc.id),
                "source_name": p_doc.source_name,
                **_make_relation_entry("amends"),
            })
            logger.info(f"Amend: {p_doc.source_name} → Đã sửa đổi bổ sung bởi {source_name}")

    elif document_action == "replace" and parent_docs:
        for p_doc in parent_docs:
            p_doc.validity_status = "Hết hiệu lực"
            await db.execute(
                update(DocumentChunk)
                .where(DocumentChunk.document_id == p_doc.id)
                .values(
                    validity_status="repealed",
                    effective_to=parsed_effective,
                    validity_note=f"Bị thay thế toàn bộ bởi {source_name}",
                )
            )
            parent_related = list(p_doc.related_documents or [])
            parent_related.append({
                "document_id": doc_id,
                "source_name": source_name,
                **_make_relation_entry("replaced_by"),
            })
            p_doc.related_documents = parent_related

            new_related.append({
                "document_id": str(p_doc.id),
                "source_name": p_doc.source_name,
                **_make_relation_entry("replaces"),
            })
            logger.info(f"Replace: {p_doc.source_name} → Hết hiệu lực do bị thay thế toàn bộ bởi {source_name}")

    elif document_action == "partial_repeal" and parent_docs:
        # Bãi bỏ một phần: chỉ các Điều/Khoản trong affected_provisions bị bãi bỏ
        # Văn bản gốc chuyển sang "Hết hiệu lực một phần" — các điều khác vẫn còn giá trị
        for p_doc in parent_docs:
            p_doc.validity_status = "Hết hiệu lực một phần"

            if parsed_provisions:
                # Chỉ mark các chunks khớp với điều/khoản bị ảnh hưởng
                target_chunks = (await db.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == p_doc.id)
                )).scalars().all()

                for prov in parsed_provisions:
                    article_key = prov.get("article", "").strip().lower()
                    clause_key = (prov.get("clause") or "").strip().lower()
                    prov_action = prov.get("action", "repeal")

                    for chunk in target_chunks:
                        chunk_article = (chunk.article or "").strip().lower()
                        chunk_clause = (chunk.clause or "").strip().lower()

                        # Khớp theo Điều (bắt buộc) và Khoản (nếu có)
                        article_match = article_key and article_key in chunk_article
                        clause_match = (not clause_key) or (clause_key in chunk_clause) or (clause_key in chunk.text.lower())

                        if article_match and clause_match:
                            if prov_action == "repeal":
                                chunk.validity_status = "repealed"
                                chunk.effective_to = parsed_effective
                                chunk.validity_note = f"Bị bãi bỏ bởi {source_name} ({prov.get('article','')} {prov.get('clause','')})".strip()
                                affected_chunk_ids.add(chunk.id)
                            elif prov_action == "amend":
                                chunk.validity_status = "amended"
                                chunk.effective_to = parsed_effective
                                chunk.validity_note = f"Bị sửa đổi bởi {source_name} ({prov.get('article','')} {prov.get('clause','')})".strip()
                                affected_chunk_ids.add(chunk.id)
            # Khi chưa có Điều/Khoản cụ thể, chỉ đánh dấu trạng thái văn bản.
            # Không được suy rộng sang toàn bộ chunk vì phạm vi bãi bỏ chưa xác định.

            parent_related = list(p_doc.related_documents or [])
            parent_related.append({
                "document_id": doc_id,
                "source_name": source_name,
                **_make_relation_entry("partially_repealed_by"),
            })
            p_doc.related_documents = parent_related

            new_related.append({
                "document_id": str(p_doc.id),
                "source_name": p_doc.source_name,
                **_make_relation_entry("partially_repeals"),
            })
            logger.info(f"PartialRepeal: {p_doc.source_name} → Hết hiệu lực một phần bởi {source_name} ({len(parsed_provisions)} điều/khoản)")

    # Chỉ thay thế toàn bộ mới làm toàn bộ vector của văn bản cũ hết hiệu lực.
    if document_action == "replace" and parent_docs:
        try:
            from backend.app.embedding.vector_store import VectorStore
            vs = VectorStore(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                collection_name=settings.qdrant_collection_name,
            )
            for p_doc in parent_docs:
                vs.update_validity_status(
                    source_name=p_doc.source_name,
                    new_status="repealed",
                )
        except Exception as e:
            logger.warning(f"Không thể cập nhật Qdrant payload cho văn bản cũ: {e}")

    # Sau partial_repeal: cũng cập nhật Qdrant cho các chunks bị đánh dấu
    if document_action == "partial_repeal" and parent_docs:
        try:
            from backend.app.embedding.vector_store import VectorStore
            vs = VectorStore(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                collection_name=settings.qdrant_collection_name,
            )
            if affected_chunk_ids:
                affected_chunks = (await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id.in_(affected_chunk_ids))
                )).scalars().all()
                for ck in affected_chunks:
                    try:
                        vs.update_chunk_validity([ck.id], ck.validity_status, ck.validity_note or "")
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Không thể cập nhật Qdrant chunks sau partial_repeal: {e}")

    # ── Tạo record Document mới ──────────────────────────────────
    doc = Document(
        id=uuid.UUID(doc_id),
        source_name=source_name,
        file_path=str(save_path),
        group_type=group_type,
        procedure_type=procedure_type,
        status="pending",
        document_number=document_number.strip() if document_number else None,
        validity_status="Còn hiệu lực",
        promulgation_date=parsed_promulgation,
        effective_date=parsed_effective,
        issuing_agency=issuing_agency.strip() if issuing_agency else None,
        related_documents=new_related if new_related else None,
    )
    db.add(doc)
    await db.commit()

    # Chạy indexing ở background
    background_tasks.add_task(
        _index_document_sync,
        document_id=doc_id,
        file_path=str(save_path),
        source_name=source_name,
        group_type=group_type,
        procedure_type=procedure_type,
        db_url=settings.database_url,
    )

    return {
        "document_id": doc_id,
        "source_name": source_name,
        "status": "indexing",
        "document_action": document_action,
        "amendment_scope": amendment_scope,
        "affected_provisions_count": len(parsed_provisions),
        "parent_document_ids": [str(p.id) for p in parent_docs],
        "message": "Tài liệu đã được nhận và đang được xử lý. Kiểm tra trạng thái qua GET /documents/{id}",
    }


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    group_type: Optional[str] = None,
    procedure_type: Optional[str] = None,
    status: Optional[str] = None,
    validity_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách tài liệu, có thể filter theo nhóm/thủ tục/trạng thái/hiệu lực."""
    stmt = select(Document)
    if group_type:
        stmt = stmt.where(Document.group_type == group_type)
    if procedure_type:
        stmt = stmt.where(Document.procedure_type == procedure_type)
    if status:
        stmt = stmt.where(Document.status == status)
    if validity_status:
        stmt = stmt.where(Document.validity_status == validity_status)
    stmt = stmt.order_by(Document.created_at.desc())

    result = await db.execute(stmt)
    docs = result.scalars().all()

    response = []
    for doc in docs:
        chunk_count = await db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
        )
        response.append(_build_doc_response(doc, chunk_count or 0))
    return response


@router.get("/documents/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    req: Request = None,
):
    """Thống kê hệ thống: tài liệu, chunks, vector store."""
    total_docs = await db.scalar(select(func.count(Document.id)))
    total_chunks = await db.scalar(select(func.count(DocumentChunk.id)))
    indexed_docs = await db.scalar(
        select(func.count(Document.id)).where(Document.status == "indexed")
    )

    # Lấy thông tin từ Qdrant
    qdrant_info = {}
    try:
        pipeline = req.app.state.rag_pipeline if req else None
        if pipeline and hasattr(pipeline, "vector_store"):
            qdrant_info = pipeline.vector_store.get_collection_info()
    except Exception:
        qdrant_info = {"error": "Không thể kết nối Qdrant"}

    return {
        "total_documents": total_docs or 0,
        "indexed_documents": indexed_docs or 0,
        "total_chunks_db": total_chunks or 0,
        "qdrant": qdrant_info,
        "collections": [settings.qdrant_collection_name],
    }


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chi tiết một tài liệu."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="document_id không hợp lệ")

    doc = await db.scalar(select(Document).where(Document.id == doc_uuid))
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    chunk_count = await db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    )
    return _build_doc_response(doc, chunk_count or 0)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkResponse])
async def list_document_chunks(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Inspect source chunks before deciding whether to replace or re-index a document."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="document_id không hợp lệ")
    chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_uuid).order_by(DocumentChunk.id))).scalars().all()
    
    def _detect_table_status(chunk: DocumentChunk) -> tuple[bool, Optional[str]]:
        has_tbl = bool(getattr(chunk, "has_table", False))
        t_type = getattr(chunk, "table_type", None)
        text = chunk.text or ""
        if not has_tbl and ("[Bảng" in text or ("|" in text and "\n| ---" in text)):
            has_tbl = True
            if not t_type:
                t_type = chunk.field_type or "table"
        return has_tbl, t_type

    res = []
    for chunk in chunks:
        has_tbl, t_type = _detect_table_status(chunk)
        res.append(
            ChunkResponse(
                id=chunk.id,
                text=chunk.text,
                article=chunk.article,
                clause=chunk.clause,
                field_type=chunk.field_type,
                validity_status=chunk.validity_status or "active",
                validity_note=chunk.validity_note,
                has_table=has_tbl,
                table_type=t_type,
            )
        )
    return res


@router.post("/documents/{document_id}/analyze-amendments")
async def analyze_amendments(
    document_id: str,
    parent_document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a persistent rule-based draft; never changes legal status."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được phân tích hiệu lực")
    try:
        source_id, target_id = uuid.UUID(document_id), uuid.UUID(parent_document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID văn bản không hợp lệ")
    source = await db.scalar(select(Document).where(Document.id == source_id))
    target = await db.scalar(select(Document).where(Document.id == target_id))
    if not source or not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy văn bản nguồn hoặc văn bản gốc")
    if source.status != "indexed" or target.status != "indexed":
        raise HTTPException(status_code=409, detail="Hai văn bản phải index xong trước khi phân tích")

    from backend.app.document_processing.article_mapper import ArticleMapper, normalize_label
    source_chunks = (await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == source_id)
    )).scalars().all()
    target_chunks = (await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == target_id)
    )).scalars().all()
    extracted = ArticleMapper().extract_changes("\n\n".join(chunk.text for chunk in source_chunks))
    changes: list[dict] = []
    for change in extracted:
        for chunk in target_chunks:
            if normalize_label(chunk.article) != normalize_label(change.article):
                continue
            if change.clause:
                clause_matches = normalize_label(chunk.clause) == normalize_label(change.clause)
                text_matches = normalize_label(change.clause) in normalize_label(chunk.text)
                if not (clause_matches or text_matches):
                    continue
            changes.append({
                "id": str(uuid.uuid4()),
                **change.as_dict(),
                "target_chunk_id": chunk.id,
                "target_text_preview": chunk.text[:500],
                "replacement_chunk_id": None,
                "method": "rules",
            })

    analysis = AmendmentAnalysis(
        source_document_id=source_id,
        target_document_id=target_id,
        method="rules",
        changes=changes,
        created_by=str(current_user.id),
    )
    db.add(analysis)
    await db.commit()
    return {
        "analysis_id": str(analysis.id),
        "status": analysis.status,
        "source_document": source.source_name,
        "target_document": target.source_name,
        "changes": changes,
        "summary": {
            "detected_references": len(extracted),
            "mapped_changes": len(changes),
            "target_chunks": len(target_chunks),
        },
    }


@router.get("/documents/amendment-analyses/{analysis_id}")
async def get_amendment_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        analysis_uuid = uuid.UUID(analysis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="analysis_id không hợp lệ")
    analysis = await db.scalar(select(AmendmentAnalysis).where(AmendmentAnalysis.id == analysis_uuid))
    if not analysis:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản phân tích")
    return {"analysis_id": str(analysis.id), "status": analysis.status, "changes": analysis.changes}


@router.post("/documents/amendment-analyses/{analysis_id}/confirm")
async def confirm_amendments(
    analysis_id: str,
    payload: ConfirmAmendmentsRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply only explicitly selected draft items and record an audit trail."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xác nhận hiệu lực")
    try:
        analysis_uuid = uuid.UUID(analysis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="analysis_id không hợp lệ")
    analysis = await db.scalar(select(AmendmentAnalysis).where(AmendmentAnalysis.id == analysis_uuid))
    if not analysis:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản phân tích")
    if analysis.status != "draft":
        raise HTTPException(status_code=409, detail="Bản phân tích đã được xử lý")
    selected = set(payload.confirmed_change_ids)
    available = {item["id"] for item in analysis.changes}
    if not selected.issubset(available):
        raise HTTPException(status_code=400, detail="Có thay đổi không thuộc bản phân tích")

    source = await db.scalar(select(Document).where(Document.id == analysis.source_document_id))
    qdrant_updates: dict[tuple[str, str], list[str]] = {}
    applied = 0
    for item in analysis.changes:
        if item["id"] not in selected:
            continue
        chunk = await db.scalar(select(DocumentChunk).where(DocumentChunk.id == item["target_chunk_id"]))
        if not chunk:
            continue
        effect_type = item["action"]
        new_status = {
            "repeal": "repealed",
            "replace": "superseded",
            "amend": "amended",
            "replace_text": "amended",
        }.get(effect_type, "active")
        note = f"{item['evidence_text']} — nguồn: {source.source_name if source else analysis.source_document_id}"
        # Adding a new provision does not invalidate the existing article.
        if effect_type != "add":
            chunk.validity_status = new_status
            chunk.effective_to = source.effective_date if source else None
            chunk.validity_note = note
            qdrant_updates.setdefault((new_status, note), []).append(chunk.id)
        db.add(ProvisionEffect(
            analysis_id=analysis.id,
            source_document_id=analysis.source_document_id,
            target_document_id=analysis.target_document_id,
            target_chunk_id=chunk.id,
            replacement_chunk_id=item.get("replacement_chunk_id"),
            effect_type=effect_type,
            effective_from=source.effective_date if source else None,
            evidence_text=item["evidence_text"],
            confidence=float(item.get("confidence", 0)),
            confirmed_by=str(current_user.id),
        ))
        applied += 1
    analysis.status = "confirmed"
    analysis.confirmed_at = datetime.utcnow()
    await db.commit()

    vector_store = req.app.state.rag_pipeline.vector_store
    for (status_value, note), chunk_ids in qdrant_updates.items():
        try:
            vector_store.update_chunk_validity(chunk_ids, status_value, note)
        except Exception as exc:
            logger.error("Qdrant chunk validity sync failed: %s", exc)
    req.app.state.rag_pipeline._lexical_cache.clear()
    return {"analysis_id": analysis_id, "status": "confirmed", "applied": applied}


@router.patch("/documents/chunks/{chunk_id}/validity")
async def patch_chunk_validity(
    chunk_id: str,
    payload: ChunkValidityRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được sửa hiệu lực")
    allowed = {"active", "amended", "superseded", "repealed"}
    if payload.validity_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Trạng thái hợp lệ: {', '.join(sorted(allowed))}")
    chunk = await db.scalar(select(DocumentChunk).where(DocumentChunk.id == chunk_id))
    if not chunk:
        raise HTTPException(status_code=404, detail="Không tìm thấy chunk")
    chunk.validity_status = payload.validity_status
    chunk.validity_note = payload.validity_note or None
    await db.commit()
    req.app.state.rag_pipeline.vector_store.update_chunk_validity(
        [chunk_id], payload.validity_status, payload.validity_note
    )
    req.app.state.rag_pipeline._lexical_cache.clear()
    return {"chunk_id": chunk_id, "validity_status": chunk.validity_status}


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xóa tài liệu:
    - Xóa record trong PostgreSQL (cascade xóa chunks)
    - Xóa vectors trong Qdrant theo source_file
    - Xóa file upload khỏi disk
    """
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xóa tài liệu")

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="document_id không hợp lệ")

    doc = await db.scalar(select(Document).where(Document.id == doc_uuid))
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    # Xóa vectors trong Qdrant
    try:
        from backend.app.embedding.vector_store import VectorStore
        vs = VectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name,
        )
        if doc.file_path:
            vs.delete_by_source(Path(doc.file_path).name)
    except Exception as e:
        logger.warning(f"Không thể xóa vectors từ Qdrant: {e}")

    # Xóa file upload khỏi disk
    if doc.file_path:
        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Không thể xóa file {doc.file_path}: {e}")

    # Xóa khỏi PostgreSQL (cascade xóa chunks)
    await db.delete(doc)
    await db.commit()
    logger.info(f"Đã xóa tài liệu {document_id} ({doc.source_name})")


@router.put("/documents/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tái index tài liệu (xóa vectors cũ và index lại từ file đã upload)."""
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được reindex")

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="document_id không hợp lệ")

    doc = await db.scalar(select(Document).where(Document.id == doc_uuid))
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    if not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(status_code=400, detail="File gốc không còn tồn tại, không thể reindex")

    # Xóa chunks cũ trong PostgreSQL
    old_chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc_uuid)
    old_chunks = (await db.execute(old_chunks_stmt)).scalars().all()
    for chunk in old_chunks:
        await db.delete(chunk)

    # Xóa vectors cũ trong Qdrant
    try:
        from backend.app.embedding.vector_store import VectorStore
        vs = VectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name,
        )
        vs.delete_by_source(Path(doc.file_path).name)
    except Exception as e:
        logger.warning(f"Xóa vectors cũ thất bại: {e}")

    doc.status = "pending"
    await db.commit()

    # Re-index ở background
    background_tasks.add_task(
        _index_document_sync,
        document_id=document_id,
        file_path=doc.file_path,
        source_name=doc.source_name,
        group_type=doc.group_type,
        procedure_type=doc.procedure_type,
        db_url=settings.database_url,
    )

    return ReindexResponse(
        document_id=document_id,
        status="indexing",
        message="Đang tái index tài liệu. Kiểm tra trạng thái qua GET /documents/{id}",
    )
