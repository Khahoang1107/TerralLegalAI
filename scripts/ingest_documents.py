"""
TerraLegalAI — Script Ingest Tài Liệu (Batch Indexing)
Chạy script này để parse PDF → chunk → embed → lưu vào Qdrant

Cách dùng:
  python scripts/ingest_documents.py --file "data/QĐ 1085.pdf" --source-name "QĐ 1085/QĐ-UBND" --group quyet_dinh --procedure chuyen_nhuong
  python scripts/ingest_documents.py --all   # Ingest toàn bộ theo config
  python scripts/ingest_documents.py --list  # Xem danh sách tài liệu cần ingest
"""
import sys
import logging
import argparse
from pathlib import Path

# Thêm project root vào path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Danh sách tài liệu cần ingest ───────────────────────────────
DOCUMENT_MANIFEST = [
    # Nhóm 2: Quyết định UBND Vĩnh Long (ưu tiên)
    {
        "file": "data/raw/nhom2_quyet_dinh/QD_1085.pdf",
        "source_name": "QĐ 1085/QĐ-UBND ngày 03/09/2025",
        "group_type": "quyet_dinh",
        "procedure_type": "chuyen_nhuong",
        "description": "Bộ thủ tục hành chính đất đai Vĩnh Long",
    },
    {
        "file": "data/raw/nhom2_quyet_dinh/QĐ 1308.pdf",
        "source_name": "QĐ 1308/QĐ-UBND ngày 27/06/2025",
        "group_type": "quyet_dinh",
        "procedure_type": "all",
        "description": "Quyết định thủ tục hành chính đất đai",
    },
    {
        "file": "data/raw/nhom2_quyet_dinh/QĐ 1312.pdf",
        "source_name": "QĐ 1312/QĐ-UBND ngày 27/06/2025",
        "group_type": "quyet_dinh",
        "procedure_type": "cap_doi",
        "description": "Quyết định cấp đổi GCN",
    },
    {
        "file": "data/raw/nhom2_quyet_dinh/QD_1467.pdf",
        "source_name": "QĐ 1467/QĐ-UBND ngày 30/09/2025",
        "group_type": "quyet_dinh",
        "procedure_type": "all",
        "description": "Quy trình nội bộ đất đai",
    },
    # Nhóm 1: Văn bản pháp luật
    {
        "file": "data/raw/nhom1_luat/Luat_Dat_Dai_2024.pdf",
        "source_name": "Luật Đất đai 2024",
        "group_type": "luat",
        "procedure_type": "all",
        "description": "Luật Đất đai năm 2024",
    },
    {
        "file": "data/raw/nhom1_luat/ND_101_2024.pdf",
        "source_name": "Nghị định 101/2024/NĐ-CP",
        "group_type": "luat",
        "procedure_type": "all",
        "description": "Nghị định hướng dẫn Luật Đất đai",
    },
]


def ingest_one(
    file_path: str,
    source_name: str,
    group_type: str,
    procedure_type: str,
    dry_run: bool = False,
) -> bool:
    """
    Ingest một file PDF vào Qdrant.
    
    Returns:
        True nếu thành công, False nếu lỗi
    """
    from backend.app.document_processing.pdf_parser import PDFParser
    from backend.app.document_processing.chunker import DocumentChunker
    from backend.app.embedding.embedding_model import EmbeddingModel
    from backend.app.embedding.vector_store import VectorStore
    from backend.app.core.config import settings

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        logger.error(f"❌ File không tồn tại: {file_path}")
        return False

    logger.info(f"\n{'='*60}")
    logger.info(f"📂 Ingest: {file_path_obj.name}")
    logger.info(f"   Source: {source_name}")
    logger.info(f"   Group: {group_type} | Procedure: {procedure_type}")

    try:
        # Step 1: Parse PDF
        logger.info("  Step 1/4: Parsing PDF...")
        parser = PDFParser()
        parsed = parser.parse(file_path)
        logger.info(f"  → {parsed.total_pages} trang, {len(parsed.full_text):,} ký tự")

        # Step 2: Chunk
        logger.info("  Step 2/4: Chunking...")
        chunker = DocumentChunker()
        chunks = chunker.chunk(
            text=parsed.full_text,
            source_file=file_path_obj.name,
            source_name=source_name,
            group_type=group_type,
            procedure_type=procedure_type,
        )
        logger.info(f"  → {len(chunks)} chunks")

        if not chunks:
            logger.warning("  ⚠️ Không có chunk nào được tạo. Bỏ qua file này.")
            return False

        if dry_run:
            logger.info("  [DRY RUN] Dừng ở đây, không embed/upsert.")
            return True

        # Step 3: Embed
        logger.info("  Step 3/4: Embedding...")
        emb_model = EmbeddingModel(model_name=settings.embedding_model_name)
        texts = [c.text for c in chunks]
        vectors = emb_model.encode(texts)
        logger.info(f"  → {len(vectors)} vectors (dim={len(vectors[0])})")

        # Step 4: Upsert vào Qdrant
        logger.info("  Step 4/4: Upsert vào Qdrant...")
        vs = VectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name,
            embedding_dim=settings.embedding_dimension,
        )
        vs.create_collection_if_not_exists()
        count = vs.upsert_chunks(chunks, vectors)
        logger.info(f"  ✅ Done! {count} points upserted.")
        return True

    except Exception as e:
        logger.error(f"  ❌ Lỗi khi ingest {file_path}: {e}", exc_info=True)
        return False


def list_documents():
    """Liệt kê danh sách tài liệu cần ingest."""
    print(f"\n{'='*60}")
    print(f"📋 Danh sách tài liệu cần ingest ({len(DOCUMENT_MANIFEST)} files):")
    print(f"{'='*60}")
    for i, doc in enumerate(DOCUMENT_MANIFEST, 1):
        exists = "✅" if Path(doc["file"]).exists() else "❌ (chưa có)"
        print(f"\n{i}. {doc['description']} {exists}")
        print(f"   File: {doc['file']}")
        print(f"   Source: {doc['source_name']}")
        print(f"   Group: {doc['group_type']} | Procedure: {doc['procedure_type']}")


def main():
    parser = argparse.ArgumentParser(
        description="TerraLegalAI — Ingest tài liệu PDF vào Qdrant"
    )
    parser.add_argument("--file", help="Đường dẫn file PDF cần ingest")
    parser.add_argument("--source-name", help="Tên nguồn tài liệu (VD: QĐ 1085/QĐ-UBND)")
    parser.add_argument(
        "--group",
        choices=["quyet_dinh", "luat", "bieu_mau", "faq"],
        default="quyet_dinh",
        help="Nhóm tài liệu",
    )
    parser.add_argument(
        "--procedure",
        choices=["chuyen_nhuong", "cap_doi", "all"],
        default="all",
        help="Loại thủ tục",
    )
    parser.add_argument("--all", action="store_true", help="Ingest tất cả tài liệu trong manifest")
    parser.add_argument("--list", action="store_true", help="Liệt kê tài liệu cần ingest")
    parser.add_argument("--dry-run", action="store_true", help="Parse + chunk nhưng không embed/upsert")

    args = parser.parse_args()

    if args.list:
        list_documents()
        return

    if args.all:
        logger.info(f"🚀 Bắt đầu ingest {len(DOCUMENT_MANIFEST)} tài liệu...")
        success = 0
        for doc in DOCUMENT_MANIFEST:
            ok = ingest_one(
                file_path=doc["file"],
                source_name=doc["source_name"],
                group_type=doc["group_type"],
                procedure_type=doc["procedure_type"],
                dry_run=args.dry_run,
            )
            if ok:
                success += 1
        logger.info(f"\n🏁 Hoàn thành: {success}/{len(DOCUMENT_MANIFEST)} tài liệu thành công")
        return

    if args.file:
        if not args.source_name:
            parser.error("--source-name là bắt buộc khi dùng --file")
        ingest_one(
            file_path=args.file,
            source_name=args.source_name,
            group_type=args.group,
            procedure_type=args.procedure,
            dry_run=args.dry_run,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
