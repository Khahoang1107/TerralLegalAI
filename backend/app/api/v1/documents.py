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
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.document import Document, DocumentChunk
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

    model_config = {"from_attributes": True}


class ReindexResponse(BaseModel):
    document_id: str
    status: str
    message: str


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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload tài liệu mới và tự động index vào Qdrant.

    - File được lưu vào `data/uploaded/`
    - Indexing chạy nền (async background task)
    - Trả về ngay `document_id` + `status: indexing`
    - Kiểm tra trạng thái qua `GET /documents/{id}`
    """
    # Chỉ admin mới được upload
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được upload tài liệu")

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

    # Tạo record Document trong PostgreSQL
    doc = Document(
        id=uuid.UUID(doc_id),
        source_name=source_name,
        file_path=str(save_path),
        group_type=group_type,
        procedure_type=procedure_type,
        status="pending",
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
        "message": "Tài liệu đã được nhận và đang được xử lý. Kiểm tra trạng thái qua GET /documents/{id}",
    }


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    group_type: Optional[str] = None,
    procedure_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách tài liệu đã được index, có thể filter theo nhóm/thủ tục/trạng thái."""
    stmt = select(Document)
    if group_type:
        stmt = stmt.where(Document.group_type == group_type)
    if procedure_type:
        stmt = stmt.where(Document.procedure_type == procedure_type)
    if status:
        stmt = stmt.where(Document.status == status)
    stmt = stmt.order_by(Document.created_at.desc())

    result = await db.execute(stmt)
    docs = result.scalars().all()

    response = []
    for doc in docs:
        # Đếm số chunks
        chunk_count = await db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
        )
        response.append(
            DocumentResponse(
                id=str(doc.id),
                source_name=doc.source_name,
                file_path=doc.file_path,
                group_type=doc.group_type,
                procedure_type=doc.procedure_type,
                status=doc.status,
                chunk_count=chunk_count or 0,
                created_at=doc.created_at.isoformat(),
            )
        )
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
    return DocumentResponse(
        id=str(doc.id),
        source_name=doc.source_name,
        file_path=doc.file_path,
        group_type=doc.group_type,
        procedure_type=doc.procedure_type,
        status=doc.status,
        chunk_count=chunk_count or 0,
        created_at=doc.created_at.isoformat(),
    )


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
