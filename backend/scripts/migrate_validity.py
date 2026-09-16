"""
Migration Đợt 1: Thêm cột document_number + cập nhật Qdrant payload validity_status

Chạy: python -m backend.scripts.migrate_validity
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import text
from backend.app.core.database import engine
from backend.app.core.config import settings


async def migrate_postgresql():
    """Thêm cột document_number nếu chưa có."""
    print("── PostgreSQL Migration ──")
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_number VARCHAR(100);"
        ))
        print("✅ Đã kiểm tra/thêm cột document_number")

    print("PostgreSQL migration hoàn tất.")


def migrate_qdrant():
    """
    Cập nhật tất cả vector points hiện có:
    - Thêm validity_status = "Còn hiệu lực" cho những point chưa có.
    """
    print("\n── Qdrant Migration ──")
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    collection = settings.qdrant_collection_name

    # Kiểm tra collection tồn tại
    try:
        info = client.get_collection(collection)
        total_points = info.points_count
        print(f"Collection '{collection}': {total_points} points")
    except Exception as e:
        print(f"⚠️  Không tìm thấy collection '{collection}': {e}")
        return

    if total_points == 0:
        print("Không có points nào để cập nhật.")
        return

    # Set validity_status cho TẤT CẢ points (idempotent — ghi đè nếu đã có)
    try:
        # Qdrant set_payload hỗ trợ cập nhật tất cả points khi không có filter
        # Nhưng để an toàn, dùng scroll + batch set
        offset = None
        updated = 0
        batch_ids = []

        while True:
            points, offset = client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=["validity_status"],
                with_vectors=False,
            )

            for point in points:
                existing_status = (point.payload or {}).get("validity_status")
                if not existing_status:
                    batch_ids.append(point.id)

            # Batch update khi đủ 500 hoặc hết pages
            if len(batch_ids) >= 500 or (offset is None or not points):
                if batch_ids:
                    client.set_payload(
                        collection_name=collection,
                        payload={"validity_status": "Còn hiệu lực"},
                        points=batch_ids,
                    )
                    updated += len(batch_ids)
                    print(f"  Cập nhật {updated} points...")
                    batch_ids = []

            if offset is None or not points:
                break

        print(f"✅ Đã cập nhật validity_status cho {updated}/{total_points} points (bỏ qua {total_points - updated} đã có)")

    except Exception as e:
        print(f"❌ Lỗi cập nhật Qdrant: {e}")


async def main():
    print("=" * 60)
    print("TerraLegalAI — Migration Đợt 1: Validity Status")
    print("=" * 60)

    await migrate_postgresql()
    migrate_qdrant()

    print("\n✅ Migration hoàn tất!")


if __name__ == "__main__":
    asyncio.run(main())
