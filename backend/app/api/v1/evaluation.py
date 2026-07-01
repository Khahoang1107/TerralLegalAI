"""
TerraLegalAI — Evaluation API Endpoints
Quản lý bộ test cases và chạy đánh giá RAG.

Endpoints:
  GET    /api/v1/evaluation/test-cases        — Danh sách test cases
  POST   /api/v1/evaluation/test-cases        — Thêm test case mới
  DELETE /api/v1/evaluation/test-cases/{id}   — Xóa test case
  POST   /api/v1/evaluation/run               — Chạy đánh giá RAGAS
  GET    /api/v1/evaluation/results           — Kết quả đánh giá
  GET    /api/v1/evaluation/results/{id}      — Chi tiết một lần đánh giá
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.evaluation import EvaluationRun, TestCase
from backend.app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Schemas ──────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    question: str = Field(..., min_length=5, description="Câu hỏi kiểm thử")
    expected_answer: str = Field(..., min_length=5, description="Câu trả lời mong đợi (ground truth)")
    procedure_group: Optional[str] = Field(None, description="Nhóm thủ tục: chuyen_nhuong | cap_doi | all")
    intent: Optional[str] = Field(None, description="Loại intent: hoi_ho_so | hoi_trinh_tu | ...")
    source_doc: Optional[str] = Field(None, description="Tài liệu nguồn: VD 'QĐ 1085/QĐ-UBND'")
    field_type: Optional[str] = Field(None, description="Loại nội dung: thanh_phan_ho_so | thoi_han | ...")
    level: Optional[int] = Field(None, ge=1, le=4, description="Mức độ khó: 1=dễ, 4=khó")


class TestCaseResponse(BaseModel):
    id: str
    question: str
    expected_answer: str
    procedure_group: Optional[str]
    intent: Optional[str]
    source_doc: Optional[str]
    field_type: Optional[str]
    level: Optional[int]
    created_at: str

    model_config = {"from_attributes": True}


class EvaluationRunResponse(BaseModel):
    id: str
    run_date: str
    faithfulness: Optional[float]
    answer_relevancy: Optional[float]
    context_precision: Optional[float]
    context_recall: Optional[float]
    total_questions: Optional[int]
    passed_questions: Optional[int]
    notes: Optional[str]

    model_config = {"from_attributes": True}


class EvaluationRunRequest(BaseModel):
    max_questions: int = Field(20, ge=1, le=100, description="Số câu hỏi tối đa trong lần chạy này")
    procedure_group: Optional[str] = Field(None, description="Chỉ đánh giá một nhóm thủ tục")
    level: Optional[int] = Field(None, ge=1, le=4, description="Chỉ đánh giá câu hỏi ở mức độ nhất định")
    notes: Optional[str] = Field(None, description="Ghi chú cho lần đánh giá này")


# ─── Background: Run Evaluation ───────────────────────────────────

def _run_evaluation_sync(
    run_id: str,
    test_cases: list[dict],
    db_url: str,
    gemini_api_key: str,
    qdrant_host: str,
    qdrant_port: int,
    qdrant_collection: str,
    embedding_model_name: str,
    gemini_model: str,
    notes: str = "",
):
    """
    Chạy đánh giá RAG và lưu kết quả (chạy trong background thread).
    Tính 4 metrics: faithfulness, answer_relevancy, context_precision, context_recall.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    async def _run():
        from backend.app.rag.pipeline import RAGPipeline
        from backend.app.embedding.embedding_model import EmbeddingModel
        from backend.app.embedding.vector_store import VectorStore
        from backend.app.evaluation.test_runner import TestRunner
        from google import genai

        engine = create_async_engine(db_url, echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            # Cập nhật trạng thái
            run = await session.scalar(select(EvaluationRun).where(EvaluationRun.id == run_id))
            if not run:
                return

            try:
                # Khởi tạo pipeline
                vs = VectorStore(host=qdrant_host, port=qdrant_port, collection_name=qdrant_collection)
                emb = EmbeddingModel(model_name=embedding_model_name)
                client = genai.Client(api_key=gemini_api_key)

                pipeline = RAGPipeline(
                    vector_store=vs,
                    embedding_model=emb,
                    gemini_client=client,
                    gemini_model=gemini_model,
                )

                # Chạy test runner
                runner = TestRunner(pipeline=pipeline)
                results = runner.run(test_cases)

                # Cập nhật kết quả
                run.faithfulness = results.get("faithfulness")
                run.answer_relevancy = results.get("answer_relevancy")
                run.context_precision = results.get("context_precision")
                run.context_recall = results.get("context_recall")
                run.total_questions = results.get("total_questions", len(test_cases))
                run.passed_questions = results.get("passed_questions", 0)
                run.notes = notes
                await session.commit()

                logger.info(f"✅ Evaluation run {run_id} completed: {results}")

            except Exception as e:
                logger.error(f"❌ Evaluation run {run_id} failed: {e}", exc_info=True)
                run.notes = f"ERROR: {str(e)}"
                await session.commit()

        await engine.dispose()

    asyncio.run(_run())


# ─── Endpoints ────────────────────────────────────────────────────

@router.get("/evaluation/test-cases", response_model=list[TestCaseResponse])
async def list_test_cases(
    procedure_group: Optional[str] = None,
    level: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách test cases, có thể filter theo nhóm thủ tục và mức độ."""
    stmt = select(TestCase)
    if procedure_group:
        stmt = stmt.where(TestCase.procedure_group == procedure_group)
    if level:
        stmt = stmt.where(TestCase.level == level)
    stmt = stmt.order_by(TestCase.created_at.desc())

    result = await db.execute(stmt)
    cases = result.scalars().all()
    return [
        TestCaseResponse(
            id=tc.id,
            question=tc.question,
            expected_answer=tc.expected_answer,
            procedure_group=tc.procedure_group,
            intent=tc.intent,
            source_doc=tc.source_doc,
            field_type=tc.field_type,
            level=tc.level,
            created_at=tc.created_at.isoformat(),
        )
        for tc in cases
    ]


@router.post("/evaluation/test-cases", response_model=TestCaseResponse, status_code=201)
async def create_test_case(
    payload: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Thêm test case mới vào bộ kiểm thử."""
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được thêm test case")

    tc = TestCase(
        id=str(uuid.uuid4()),
        question=payload.question,
        expected_answer=payload.expected_answer,
        procedure_group=payload.procedure_group,
        intent=payload.intent,
        source_doc=payload.source_doc,
        field_type=payload.field_type,
        level=payload.level,
    )
    db.add(tc)
    await db.commit()
    await db.refresh(tc)

    return TestCaseResponse(
        id=tc.id,
        question=tc.question,
        expected_answer=tc.expected_answer,
        procedure_group=tc.procedure_group,
        intent=tc.intent,
        source_doc=tc.source_doc,
        field_type=tc.field_type,
        level=tc.level,
        created_at=tc.created_at.isoformat(),
    )


@router.delete("/evaluation/test-cases/{test_case_id}", status_code=204)
async def delete_test_case(
    test_case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa một test case."""
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xóa test case")

    tc = await db.scalar(select(TestCase).where(TestCase.id == test_case_id))
    if not tc:
        raise HTTPException(status_code=404, detail="Không tìm thấy test case")

    await db.delete(tc)
    await db.commit()


@router.post("/evaluation/run", status_code=202)
async def run_evaluation(
    payload: EvaluationRunRequest,
    background_tasks: BackgroundTasks,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chạy đánh giá RAGAS.
    Kết quả sẽ được lưu vào bảng evaluation_runs khi hoàn thành.
    """
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được chạy đánh giá")

    # Lấy test cases
    stmt = select(TestCase)
    if payload.procedure_group:
        stmt = stmt.where(TestCase.procedure_group == payload.procedure_group)
    if payload.level:
        stmt = stmt.where(TestCase.level == payload.level)
    stmt = stmt.limit(payload.max_questions)

    result = await db.execute(stmt)
    test_cases = result.scalars().all()

    if not test_cases:
        raise HTTPException(status_code=404, detail="Không có test cases. Thêm test cases trước.")

    # Tạo EvaluationRun record
    run_id = str(uuid.uuid4())
    run = EvaluationRun(
        id=run_id,
        total_questions=len(test_cases),
        notes=payload.notes or "Đang chạy...",
    )
    db.add(run)
    await db.commit()

    # Chuẩn bị test cases cho background task
    tc_dicts = [
        {
            "id": tc.id,
            "question": tc.question,
            "expected_answer": tc.expected_answer,
            "procedure_group": tc.procedure_group,
        }
        for tc in test_cases
    ]

    from backend.app.core.config import settings
    background_tasks.add_task(
        _run_evaluation_sync,
        run_id=run_id,
        test_cases=tc_dicts,
        db_url=settings.database_url,
        gemini_api_key=settings.gemini_api_key,
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        qdrant_collection=settings.qdrant_collection_name,
        embedding_model_name=settings.embedding_model_name,
        gemini_model=settings.gemini_model,
        notes=payload.notes or "",
    )

    return {
        "run_id": run_id,
        "total_questions": len(test_cases),
        "status": "running",
        "message": "Đang chạy đánh giá. Kiểm tra kết quả qua GET /evaluation/results/{run_id}",
    }


@router.get("/evaluation/results", response_model=list[EvaluationRunResponse])
async def list_evaluation_results(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách kết quả các lần đánh giá gần nhất."""
    stmt = select(EvaluationRun).order_by(EvaluationRun.run_date.desc()).limit(limit)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        EvaluationRunResponse(
            id=r.id,
            run_date=r.run_date.isoformat(),
            faithfulness=r.faithfulness,
            answer_relevancy=r.answer_relevancy,
            context_precision=r.context_precision,
            context_recall=r.context_recall,
            total_questions=r.total_questions,
            passed_questions=r.passed_questions,
            notes=r.notes,
        )
        for r in runs
    ]


@router.get("/evaluation/results/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_result(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chi tiết kết quả một lần đánh giá."""
    run = await db.scalar(select(EvaluationRun).where(EvaluationRun.id == run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Không tìm thấy evaluation run")

    return EvaluationRunResponse(
        id=run.id,
        run_date=run.run_date.isoformat(),
        faithfulness=run.faithfulness,
        answer_relevancy=run.answer_relevancy,
        context_precision=run.context_precision,
        context_recall=run.context_recall,
        total_questions=run.total_questions,
        passed_questions=run.passed_questions,
        notes=run.notes,
    )
