"""
TerraLegalAI — Script Chạy Đánh Giá RAG Định Kỳ
Chạy bộ test cases và in kết quả ra console + lưu vào DB.

Cách dùng:
  python scripts/run_evaluation.py               # Chạy toàn bộ test cases
  python scripts/run_evaluation.py --group chuyen_nhuong  # Chỉ một nhóm thủ tục
  python scripts/run_evaluation.py --level 1     # Chỉ câu hỏi mức độ 1
  python scripts/run_evaluation.py --max 20      # Tối đa 20 câu hỏi
  python scripts/run_evaluation.py --json        # Xuất kết quả dạng JSON
"""
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_evaluation(
    procedure_group: str | None = None,
    level: int | None = None,
    max_questions: int = 50,
    output_json: bool = False,
):
    """Chạy đánh giá RAG và in kết quả."""
    from backend.app.core.config import settings
    from backend.app.core.database import AsyncSessionLocal, init_db
    from backend.app.models.evaluation import TestCase, EvaluationRun
    from backend.app.rag.pipeline import RAGPipeline
    from backend.app.embedding.embedding_model import EmbeddingModel
    from backend.app.embedding.vector_store import VectorStore
    from backend.app.evaluation.test_runner import TestRunner
    from sqlalchemy import select
    from google import genai
    import uuid

    await init_db()

    async with AsyncSessionLocal() as session:
        # Lấy test cases
        stmt = select(TestCase)
        if procedure_group:
            stmt = stmt.where(TestCase.procedure_group == procedure_group)
        if level:
            stmt = stmt.where(TestCase.level == level)
        stmt = stmt.limit(max_questions)

        result = await session.execute(stmt)
        test_cases = result.scalars().all()

        if not test_cases:
            logger.error("Không có test cases. Chạy `python scripts/build_test_dataset.py --load` trước.")
            return

        logger.info(f"🧪 Chạy {len(test_cases)} test cases...")
        tc_dicts = [
            {
                "id": tc.id,
                "question": tc.question,
                "expected_answer": tc.expected_answer,
                "procedure_group": tc.procedure_group,
            }
            for tc in test_cases
        ]

    # Khởi tạo pipeline
    vs = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection_name,
        embedding_dim=settings.embedding_dimension,
    )
    emb = EmbeddingModel(model_name=settings.embedding_model_name)
    client = genai.Client(api_key=settings.gemini_api_key)

    pipeline = RAGPipeline(
        vector_store=vs,
        embedding_model=emb,
        gemini_client=client,
        gemini_model=settings.gemini_model,
    )

    runner = TestRunner(pipeline=pipeline)
    results_dict = runner.run(tc_dicts)

    # Lưu vào DB
    async with AsyncSessionLocal() as session:
        notes = f"CLI run | group={procedure_group or 'all'} | level={level or 'all'}"
        run = EvaluationRun(
            id=str(uuid.uuid4()),
            faithfulness=results_dict.get("faithfulness"),
            answer_relevancy=results_dict.get("answer_relevancy"),
            context_precision=results_dict.get("context_precision"),
            context_recall=results_dict.get("context_recall"),
            total_questions=results_dict.get("total_questions"),
            passed_questions=results_dict.get("passed_questions"),
            notes=notes,
        )
        session.add(run)
        await session.commit()
        logger.info(f"✅ Đã lưu kết quả với run_id: {run.id}")

    # In kết quả
    if output_json:
        print(json.dumps(results_dict, ensure_ascii=False, indent=2))
    else:
        _print_results(results_dict)


def _print_results(results: dict):
    """In kết quả dạng bảng đẹp."""
    print(f"\n{'='*60}")
    print(f"📊 KẾT QUẢ ĐÁNH GIÁ RAG — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*60}")
    print(f"  Tổng câu hỏi    : {results.get('total_questions', 0)}")
    print(f"  Câu đạt ngưỡng  : {results.get('passed_questions', 0)}")
    print()

    metrics = [
        ("Faithfulness (độ trung thực)", results.get("faithfulness"), 0.85),
        ("Answer Relevancy (độ liên quan)", results.get("answer_relevancy"), 0.80),
        ("Context Precision (độ chính xác)", results.get("context_precision"), 0.75),
        ("Context Recall (độ đầy đủ)", results.get("context_recall"), 0.80),
    ]

    for name, value, target in metrics:
        if value is None:
            status = "⚪ N/A"
        elif value >= target:
            status = "✅ ĐẠT"
        elif value >= target * 0.85:
            status = "🟡 GẦN ĐẠT"
        else:
            status = "🔴 CHƯA ĐẠT"

        val_str = f"{value:.3f}" if value is not None else "  N/A"
        print(f"  {name:<35}: {val_str} (target >{target}) {status}")

    print()
    print(f"  Avg Confidence  : {results.get('avg_confidence', 0):.3f}")
    print(f"  Avg Latency     : {results.get('avg_latency_ms', 0):.0f}ms")
    print(f"  Fallback Rate   : {results.get('fallback_rate', 0):.1%}")
    print(f"  Citation Rate   : {results.get('citation_rate', 0):.1%}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="TerraLegalAI — Chạy đánh giá RAG")
    parser.add_argument("--group", help="Nhóm thủ tục: chuyen_nhuong | cap_doi | all")
    parser.add_argument("--level", type=int, choices=[1, 2, 3, 4], help="Mức độ câu hỏi (1-4)")
    parser.add_argument("--max", type=int, default=50, help="Số câu hỏi tối đa (default: 50)")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả dạng JSON")
    args = parser.parse_args()

    asyncio.run(run_evaluation(
        procedure_group=args.group,
        level=args.level,
        max_questions=args.max,
        output_json=args.json,
    ))


if __name__ == "__main__":
    main()
