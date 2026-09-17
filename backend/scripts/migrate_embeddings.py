"""Build an E5 Qdrant collection from an existing embedding collection.

The source collection is read only.  This makes an embedding-model migration
reversible: switch the app only after this command reports that every source
point has been copied to the new collection.
"""
from __future__ import annotations

import argparse
import logging

from qdrant_client import QdrantClient

from backend.app.core.config import settings
from backend.app.document_processing.chunker import DocumentChunk
from backend.app.embedding.embedding_model import EmbeddingModel
from backend.app.embedding.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _chunk_from_payload(payload: dict, fallback_id: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=str(payload.get("chunk_id") or fallback_id),
        text=str(payload.get("text") or ""),
        token_estimate=int(payload.get("token_estimate") or 0),
        source_file=str(payload.get("source_file") or ""),
        source_name=str(payload.get("source_name") or ""),
        group_type=str(payload.get("group_type") or ""),
        procedure_type=str(payload.get("procedure_type") or "all"),
        article=str(payload.get("article") or ""),
        clause=str(payload.get("clause") or ""),
        field_type=str(payload.get("field_type") or "general"),
        chunk_index=int(payload.get("chunk_index") or 0),
        validity_status=str(payload.get("validity_status") or "Còn hiệu lực"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-index a Qdrant collection with the configured embedding model")
    parser.add_argument("--source-collection", default="land_law_chunks", help="Existing read-only BGE collection")
    parser.add_argument("--target-collection", required=True, help="New collection name, e.g. land_law_chunks_e5")
    parser.add_argument("--replace-target", action="store_true", help="Delete an incomplete target collection before starting")
    args = parser.parse_args()

    if args.source_collection == args.target_collection:
        parser.error("Source và target phải là hai collection khác nhau")

    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    existing = {item.name for item in client.get_collections().collections}
    if args.source_collection not in existing:
        parser.error(f"Không tìm thấy source collection: {args.source_collection}")
    if args.target_collection in existing:
        if not args.replace_target:
            parser.error("Target đã tồn tại. Kiểm tra kết quả hoặc dùng --replace-target để làm lại.")
        client.delete_collection(args.target_collection)
        logger.warning("Đã xóa target collection chưa hoàn tất: %s", args.target_collection)

    source_info = client.get_collection(args.source_collection)
    expected = source_info.points_count
    logger.info("Re-index %s points: %s -> %s", expected, args.source_collection, args.target_collection)

    model = EmbeddingModel(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
        cpu_threads=settings.embedding_cpu_threads,
    )
    target = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=args.target_collection,
        embedding_dim=settings.embedding_dimension,
    )
    target.create_collection_if_not_exists()

    offset = None
    migrated = 0
    while True:
        points, offset = client.scroll(
            collection_name=args.source_collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        chunks = [_chunk_from_payload(point.payload or {}, str(point.id)) for point in points]
        chunks = [chunk for chunk in chunks if chunk.text]
        if chunks:
            vectors = model.encode([chunk.text for chunk in chunks])
            if any(len(vector) != settings.embedding_dimension for vector in vectors):
                raise RuntimeError("Kích thước vector không khớp EMBEDDING_DIMENSION")
            target.upsert_chunks(chunks, vectors)
            migrated += len(chunks)
            logger.info("Đã migrate %s/%s chunks", migrated, expected)
        if offset is None:
            break

    target_count = client.get_collection(args.target_collection).points_count
    if target_count != expected:
        raise RuntimeError(f"Thiếu chunks: source={expected}, target={target_count}")
    logger.info("Hoàn tất an toàn: %s chunks trong %s", target_count, args.target_collection)


if __name__ == "__main__":
    main()
