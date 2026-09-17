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


class ConfirmAmendmentsRequest(BaseModel):
    confirmed_change_ids: list[str] = Field(default_factory=list)


class ChunkValidityRequest(BaseModel):
    validity_status: str
    validity_note: str = ""


VALID_DOCUMENT_ACTIONS = {"new", "amend", "replace"}


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

                parsed = parser.parse(file_path)
                logger.info(f"Parsed {file_path}: {len(parsed.full_text):,} chars")

                # Chunk
                chunker = DocumentChunker()
                chunks = chunker.chunk(
                    text=parsed.full_text,
                    source_file=file_path_obj.name,
                    source_name=source_name,
                    group_type=group_type,
                    procedure_type=procedure_type,
                )
                logger.info(f"Created {len(chunks)} chunks")

                # Lưu chunks vào PostgreSQL
                for c in chunks:
                    chunk_record = DocumentChunk(
                        id=c.chunk_id,
                        document_id=uuid.UUID(document_id),
                        text=c.text,
                        article=c.article,
                        clause=c.clause,
                        field_type=c.field_type,
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


# ─── Endpoints ────────────────────────────────────────────────────

@router.post("/documents/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File PDF hoặc DOCX"),
    source_name: str = Form(..., description="Tên nguồn tài liệu, VD: QĐ 1085/QĐ-UBND"),
    group_type: str = Form(..., description="Nhóm: quyet_dinh | luat | bieu_mau | faq"),
    procedure_type: str = Form(..., description="Thủ tục: chuyen_nhuong | cap_doi | all"),
    # ── Metadata hiệu lực (Đợt 1) ──
    document_action: str = Form("new", description="Hành động: new | amend | replace"),
    document_number: Optional[str] = Form(None, description="Số/ký hiệu VB, VD: 1085/QĐ-UBND"),
    promulgation_date: Optional[str] = Form(None, description="Ngày ban hành (YYYY-MM-DD)"),
    effective_date: Optional[str] = Form(None, description="Ngày hiệu lực (YYYY-MM-DD)"),
    issuing_agency: Optional[str] = Form(None, description="Cơ quan ban hành"),
    parent_document_id: Optional[str] = Form(None, description="ID văn bản gốc (khi amend/replace)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload tài liệu mới / sửa đổi bổ sung / thay thế toàn bộ.

    document_action:
      - "new":     Văn bản hoàn toàn mới, validity = "Còn hiệu lực"
      - "amend":   Sửa đổi bổ sung — bản gốc chuyển "Đã sửa đổi bổ sung", bản mới "Còn hiệu lực"
      - "replace": Thay thế toàn bộ — bản cũ chuyển "Hết hiệu lực", bản mới "Còn hiệu lực"

    Khi amend/replace, parent_document_id bắt buộc. Hệ thống tự động:
      1. Cập nhật validity_status của bản gốc
      2. Lưu quan hệ hai chiều vào related_documents (amends ↔ amended_by, replaces ↔ replaced_by)
      3. Cập nhật payload trong Qdrant (khi replace)
    """
    # Chỉ admin mới được upload
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được upload tài liệu")

    # Validate document_action
    if document_action not in VALID_DOCUMENT_ACTIONS:
        raise HTTPException(status_code=400, detail=f"document_action không hợp lệ: {document_action}. Chấp nhận: {', '.join(VALID_DOCUMENT_ACTIONS)}")

    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không hỗ trợ. Chấp nhận: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate group_type và procedure_type
    valid_groups = {"quyet_dinh", "luat", "bieu_mau", "faq"}
    valid_procedures = {"chuyen_nhuong", "cap_doi", "tang_cho", "all"}
    if group_type not in valid_groups:
        raise HTTPException(status_code=400, detail=f"group_type không hợp lệ: {group_type}")
    if procedure_type not in valid_procedures:
        raise HTTPException(status_code=400, detail=f"procedure_type không hợp lệ: {procedure_type}")

    # Validate parent_document_id khi amend/replace
    parent_doc = None
    if document_action in ("amend", "replace"):
        if not parent_document_id:
            raise HTTPException(status_code=400, detail="Phải chọn văn bản gốc khi sửa đổi/thay thế.")
        try:
            parent_uuid = uuid.UUID(parent_document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="parent_document_id không hợp lệ")
        parent_doc = await db.scalar(select(Document).where(Document.id == parent_uuid))
        if not parent_doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy văn bản gốc")

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

    if document_action == "amend" and parent_doc:
        # Bản gốc → "Đã sửa đổi bổ sung"
        parent_doc.validity_status = "Đã sửa đổi bổ sung"

        # Liên kết bản gốc → bản mới (amended_by)
        parent_related = list(parent_doc.related_documents or [])
        parent_related.append({
            "document_id": doc_id,
            "source_name": source_name,
            "relation": "amended_by",
            "effective_date": effective_date_str,
        })
        parent_doc.related_documents = parent_related

        # Liên kết bản mới → bản gốc (amends)
        new_related.append({
            "document_id": str(parent_doc.id),
            "source_name": parent_doc.source_name,
            "relation": "amends",
            "effective_date": effective_date_str,
        })

        # Provision payloads remain active until an administrator confirms the
        # exact affected Điều/Khoản in the amendment review workflow.

        logger.info(f"Amend: {parent_doc.source_name} → Đã sửa đổi bổ sung bởi {source_name}")

    elif document_action == "replace" and parent_doc:
        # Bản gốc → "Hết hiệu lực"
        parent_doc.validity_status = "Hết hiệu lực"
        await db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.document_id == parent_doc.id)
            .values(
                validity_status="repealed",
                effective_to=parsed_effective,
                validity_note=f"Bị thay thế toàn bộ bởi {source_name}",
            )
        )

        # Liên kết bản gốc → bản mới (replaced_by)
        parent_related = list(parent_doc.related_documents or [])
        parent_related.append({
            "document_id": doc_id,
            "source_name": source_name,
            "relation": "replaced_by",
            "effective_date": effective_date_str,
        })
        parent_doc.related_documents = parent_related

        # Liên kết bản mới → bản gốc (replaces)
        new_related.append({
            "document_id": str(parent_doc.id),
            "source_name": parent_doc.source_name,
            "relation": "replaces",
            "effective_date": effective_date_str,
        })

        # Cập nhật Qdrant payload của bản cũ
        try:
            from backend.app.embedding.vector_store import VectorStore
            vs = VectorStore(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                collection_name=settings.qdrant_collection_name,
            )
            vs.update_validity_status(
                source_name=parent_doc.source_name,
                new_status="repealed",
            )
        except Exception as e:
            logger.warning(f"Không thể cập nhật Qdrant payload cho văn bản cũ: {e}")

        logger.info(f"Replace: {parent_doc.source_name} → Hết hiệu lực, thay bởi {source_name}")

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
        "parent_document_id": parent_document_id,
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
    return [ChunkResponse(id=chunk.id, text=chunk.text, article=chunk.article, clause=chunk.clause, field_type=chunk.field_type, validity_status=chunk.validity_status or "active", validity_note=chunk.validity_note) for chunk in chunks]


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
