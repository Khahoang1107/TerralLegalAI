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
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.evaluation import EvaluationRun, TestCase, EvaluationCaseResult
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
    test_case_ids: Optional[list[str]] = Field(None, description="Danh sách các test case id cụ thể muốn chạy")
    max_questions: int = Field(200, ge=1, le=200, description="Số câu hỏi tối đa trong lần chạy này")
    procedure_group: Optional[str] = Field(None, description="Chỉ đánh giá một nhóm thủ tục")
    level: Optional[int] = Field(None, ge=1, le=4, description="Chỉ đánh giá câu hỏi ở mức độ nhất định")
    notes: Optional[str] = Field(None, description="Ghi chú cho lần đánh giá này")
    use_ragas: bool = True


class TestCaseUpdate(TestCaseCreate):
    pass


class ManualReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(pass|fail|pending)$")
    note: str = Field("", max_length=4000)


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
    use_ragas: bool = True,
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

                if use_ragas:
                    from backend.app.evaluation.ragas_evaluator import RAGASEvaluator
                    samples = [{"question": d["question"], "answer": d["actual_answer"], "contexts": d.get("retrieved_contexts", []), "ground_truth": d["expected_answer"]} for d in results.get("details", [])]
                    metrics = RAGASEvaluator(gemini_api_key=gemini_api_key).evaluate(samples)
                    for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
                        if metrics.get(key) is not None:
                            results[key] = metrics[key]
                    notes = f"{notes}\nAutomatic evaluation: {metrics.get('evaluation_type', 'heuristic')}".strip()

                # Cập nhật kết quả
                run.faithfulness = results.get("faithfulness")
                run.answer_relevancy = results.get("answer_relevancy")
                run.context_precision = results.get("context_precision")
                run.context_recall = results.get("context_recall")
                run.total_questions = results.get("total_questions", len(test_cases))
                run.passed_questions = results.get("passed_questions", 0)
                run.notes = notes
                for detail in results.get("details", []):
                    score = detail.get("answer_similarity") or 0.0
                    session.add(EvaluationCaseResult(
                        id=str(uuid.uuid4()), run_id=run_id, test_case_id=detail["test_case_id"],
                        question=detail["question"], expected_answer=detail["expected_answer"], actual_answer=detail.get("actual_answer") or "",
                        answer_similarity=score, grounding_score=detail.get("grounding_score") or 0.0,
                        is_fallback=str(bool(detail.get("is_fallback"))).lower(), retrieved_contexts=detail.get("retrieved_contexts", []), auto_status="pass" if score >= TestRunner.PASS_THRESHOLD and not detail.get("is_fallback") else "review",
                    ))
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


@router.delete("/evaluation/test-cases", status_code=200)
async def clear_all_test_cases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa tất cả test cases và các lần chạy đánh giá."""
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xóa test cases")
    from sqlalchemy import delete
    await db.execute(delete(EvaluationCaseResult))
    await db.execute(delete(EvaluationRun))
    result = await db.execute(delete(TestCase))
    await db.commit()
    return {"message": "Đã xóa toàn bộ test cases và lịch sử đánh giá", "deleted": result.rowcount}


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


@router.put("/evaluation/test-cases/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(test_case_id: str, payload: TestCaseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được sửa test case")
    tc = await db.scalar(select(TestCase).where(TestCase.id == test_case_id))
    if not tc:
        raise HTTPException(status_code=404, detail="Không tìm thấy test case")
    for field, value in payload.model_dump().items():
        setattr(tc, field, value)
    await db.commit(); await db.refresh(tc)
    return TestCaseResponse(id=tc.id, question=tc.question, expected_answer=tc.expected_answer, procedure_group=tc.procedure_group, intent=tc.intent, source_doc=tc.source_doc, field_type=tc.field_type, level=tc.level, created_at=tc.created_at.isoformat())


@router.post("/evaluation/test-cases/import")
async def import_test_cases(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được nhập test case")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ CSV UTF-8")
    rows = csv.DictReader(io.StringIO((await file.read()).decode("utf-8-sig")))
    created, errors = 0, []
    for line, row in enumerate(rows, 2):
        question, expected = (row.get("question") or "").strip(), (row.get("expected_answer") or "").strip()
        if len(question) < 5 or len(expected) < 5:
            errors.append({"line": line, "error": "question và expected_answer là bắt buộc"}); continue
        level = int(row["level"]) if (row.get("level") or "").isdigit() else None
        db.add(TestCase(id=str(uuid.uuid4()), question=question, expected_answer=expected, procedure_group=row.get("procedure_group") or None, intent=row.get("intent") or None, source_doc=row.get("source_doc") or None, field_type=row.get("field_type") or None, level=level)); created += 1
    await db.commit()
    return {"created": created, "errors": errors}


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
    if payload.test_case_ids:
        stmt = stmt.where(TestCase.id.in_(payload.test_case_ids))
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
        use_ragas=payload.use_ragas,
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


@router.get("/evaluation/results/{run_id}/cases")
async def list_evaluation_case_results(run_id: str, status: Optional[str] = None, page: int = 1, page_size: int = 25, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(EvaluationCaseResult).where(EvaluationCaseResult.run_id == run_id)
    if status:
        stmt = stmt.where(EvaluationCaseResult.manual_status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(EvaluationCaseResult.created_at.desc()).offset((max(page, 1)-1)*min(max(page_size, 10), 100)).limit(min(max(page_size, 10), 100)))).scalars().all()
    return {"items": [{"id": row.id, "question": row.question, "expected_answer": row.expected_answer, "actual_answer": row.actual_answer, "answer_similarity": row.answer_similarity, "grounding_score": row.grounding_score, "retrieved_contexts": row.retrieved_contexts or [], "auto_status": row.auto_status, "manual_status": row.manual_status, "manual_note": row.manual_note} for row in rows], "total": total}


@router.put("/evaluation/results/cases/{result_id}/review")
async def review_evaluation_case(result_id: str, payload: ManualReviewRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được chấm thủ công")
    row = await db.scalar(select(EvaluationCaseResult).where(EvaluationCaseResult.id == result_id))
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả")
    row.manual_status, row.manual_note, row.reviewed_by, row.reviewed_at = payload.status, payload.note, str(current_user.id), datetime.utcnow()
    await db.commit()
    return {"id": row.id, "manual_status": row.manual_status, "manual_note": row.manual_note}


@router.get("/evaluation/results/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_result(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chi tiết một lần đánh giá. Đặt sau route /cases để tránh bắt nhầm path."""
    run = await db.scalar(select(EvaluationRun).where(EvaluationRun.id == run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Không tìm thấy evaluation run")
    return EvaluationRunResponse(
        id=run.id, run_date=run.run_date.isoformat(), faithfulness=run.faithfulness,
        answer_relevancy=run.answer_relevancy, context_precision=run.context_precision,
        context_recall=run.context_recall, total_questions=run.total_questions,
        passed_questions=run.passed_questions, notes=run.notes,
    )
