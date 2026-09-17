"""Rebuild a fresh Qdrant collection from persisted PostgreSQL chunks.

This recovery tool is for a broken or incompatible Qdrant storage volume.  It
never reads, modifies or deletes the legacy Qdrant volume; only PostgreSQL is
read and a new target collection is written.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, engine
from backend.app.document_processing.chunker import DocumentChunk as VectorChunk
from backend.app.embedding.embedding_model import EmbeddingModel
from backend.app.embedding.vector_store import VectorStore
from backend.app.models.document import Document, DocumentChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _to_vector_chunk(chunk: DocumentChunk, document: Document, index: int) -> VectorChunk:
    return VectorChunk(
        chunk_id=chunk.id,
        text=chunk.text,
        token_estimate=len(chunk.text.split()),
        source_file=Path(document.file_path).name if document.file_path else document.source_name,
        source_name=document.source_name,
        group_type=document.group_type,
        procedure_type=document.procedure_type,
        article=chunk.article or "",
        clause=chunk.clause or "",
        field_type=chunk.field_type or "general",
        chunk_index=index,
        validity_status=document.validity_status or "Còn hiệu lực",
    )


async def rebuild(target_collection: str, replace_target: bool) -> None:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(DocumentChunk, Document)
                .join(Document, DocumentChunk.document_id == Document.id)
                .order_by(Document.source_name, DocumentChunk.id)
            )
        ).all()

    if not rows:
        raise RuntimeError("PostgreSQL không có document_chunks để rebuild Qdrant")

    store = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=target_collection,
        embedding_dim=settings.embedding_dimension,
    )
    collections = {item.name for item in store.client.get_collections().collections}
    if target_collection in collections:
        if not replace_target:
            raise RuntimeError(
                f"Collection '{target_collection}' đã tồn tại. Dùng --replace-target "
                "chỉ khi muốn xóa collection mới chưa hoàn tất."
            )
        store.client.delete_collection(target_collection)
        logger.warning("Đã xóa target collection để rebuild lại: %s", target_collection)
    store.create_collection_if_not_exists()

    model = EmbeddingModel(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
        cpu_threads=settings.embedding_cpu_threads,
    )
    vector_chunks = [_to_vector_chunk(chunk, document, index) for index, (chunk, document) in enumerate(rows)]
    completed = 0
    for start in range(0, len(vector_chunks), 50):
        batch = vector_chunks[start : start + 50]
        vectors = model.encode([chunk.text for chunk in batch])
        if any(len(vector) != settings.embedding_dimension for vector in vectors):
            raise RuntimeError("Kích thước vector không khớp EMBEDDING_DIMENSION")
        store.upsert_chunks(batch, vectors)
        completed += len(batch)
        logger.info("Đã rebuild %s/%s chunks", completed, len(vector_chunks))

    info = store.get_collection_info()
    if info["points_count"] != len(vector_chunks):
        raise RuntimeError(
            f"Xác minh thất bại: PostgreSQL={len(vector_chunks)}, Qdrant={info['points_count']}"
        )
    logger.info("Hoàn tất an toàn: %s chunks trong %s", info["points_count"], target_collection)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Qdrant from PostgreSQL chunks")
    parser.add_argument("--target-collection", required=True)
    parser.add_argument("--replace-target", action="store_true")
    args = parser.parse_args()
    async def _run() -> None:
        try:
            await rebuild(args.target_collection, args.replace_target)
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
