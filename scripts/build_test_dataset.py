"""
TerraLegalAI — Script Tạo Bộ Test Dataset
Tạo bộ câu hỏi kiểm thử (ground truth Q&A) và import vào DB.

Cách dùng:
  python scripts/build_test_dataset.py --load   # Load từ file JSON vào DB
  python scripts/build_test_dataset.py --export # Export từ DB ra file JSON
  python scripts/build_test_dataset.py --show   # Xem tất cả test cases trong DB
"""
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

TEST_CASES_FILE = Path("data/test_cases/test_questions.json")


async def load_to_db():
    """Load test cases từ JSON file vào PostgreSQL."""
    from backend.app.core.database import AsyncSessionLocal, init_db
    from backend.app.models.evaluation import TestCase
    import uuid

    if not TEST_CASES_FILE.exists():
        logger.error(f"File không tồn tại: {TEST_CASES_FILE}")
        return

    with open(TEST_CASES_FILE, encoding="utf-8") as f:
        test_cases = json.load(f)

    logger.info(f"Đọc được {len(test_cases)} test cases từ {TEST_CASES_FILE}")

    await init_db()

    async with AsyncSessionLocal() as session:
        added = 0
        skipped = 0
        from sqlalchemy import select
        for tc in test_cases:
            # Kiểm tra trùng lặp theo câu hỏi
            existing = await session.scalar(
                select(TestCase).where(TestCase.question == tc["question"])
            )
            if existing:
                skipped += 1
                continue

            record = TestCase(
                id=tc.get("id", str(uuid.uuid4())),
                question=tc["question"],
                expected_answer=tc["expected_answer"],
                procedure_group=tc.get("procedure_group"),
                intent=tc.get("intent"),
                source_doc=tc.get("source"),
                field_type=tc.get("field_type"),
                level=tc.get("level", 1),
            )
            session.add(record)
            added += 1

        await session.commit()
        logger.info(f"✅ Đã import: {added} mới, {skipped} bỏ qua (trùng)")


async def export_from_db():
    """Export test cases từ DB ra file JSON."""
    from backend.app.core.database import AsyncSessionLocal, init_db
    from backend.app.models.evaluation import TestCase
    from sqlalchemy import select

    await init_db()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TestCase).order_by(TestCase.created_at))
        cases = result.scalars().all()

    export_data = [
        {
            "id": tc.id,
            "question": tc.question,
            "expected_answer": tc.expected_answer,
            "procedure_group": tc.procedure_group,
            "intent": tc.intent,
            "source": tc.source_doc,
            "field_type": tc.field_type,
            "level": tc.level,
        }
        for tc in cases
    ]

    export_path = TEST_CASES_FILE.parent / "test_questions_export.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Exported {len(export_data)} test cases → {export_path}")


async def show_cases():
    """Xem danh sách test cases trong DB."""
    from backend.app.core.database import AsyncSessionLocal, init_db
    from backend.app.models.evaluation import TestCase
    from sqlalchemy import select

    await init_db()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TestCase).order_by(TestCase.procedure_group, TestCase.level)
        )
        cases = result.scalars().all()

    print(f"\n{'='*70}")
    print(f"📋 Bộ test cases ({len(cases)} câu hỏi):")
    print(f"{'='*70}")

    current_group = None
    for tc in cases:
        if tc.procedure_group != current_group:
            current_group = tc.procedure_group
            print(f"\n🏷️  Nhóm: {current_group}")

        print(f"\n  [{tc.level}] Q: {tc.question}")
        print(f"      Intent: {tc.intent} | Source: {tc.source_doc}")
        print(f"      A: {tc.expected_answer[:80]}...")


def main():
    parser = argparse.ArgumentParser(description="TerraLegalAI — Quản lý bộ test dataset")
    parser.add_argument("--load", action="store_true", help=f"Load test cases từ {TEST_CASES_FILE} vào DB")
    parser.add_argument("--export", action="store_true", help="Export test cases từ DB ra file JSON")
    parser.add_argument("--show", action="store_true", help="Xem tất cả test cases trong DB")
    args = parser.parse_args()

    if args.load:
        asyncio.run(load_to_db())
    elif args.export:
        asyncio.run(export_from_db())
    elif args.show:
        asyncio.run(show_cases())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
