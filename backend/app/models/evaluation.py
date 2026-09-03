"""
TerraLegalAI — Evaluation Models
SQLAlchemy models cho TestCase và EvaluationRun.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Float, SmallInteger, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.models.base import Base


class TestCase(Base):
    """Bộ câu hỏi kiểm thử (ground truth)."""
    __tablename__ = "test_cases"

    id = Column(String(36), primary_key=True)
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    procedure_group = Column(String(50), nullable=True)   # chuyen_nhuong / cap_doi / all
    intent = Column(String(100), nullable=True)           # hoi_ho_so / hoi_trinh_tu / ...
    source_doc = Column(String(300), nullable=True)       # VD: "QĐ 1085/QĐ-UBND"
    field_type = Column(String(100), nullable=True)       # thanh_phan_ho_so / thoi_han / ...
    level = Column(SmallInteger, nullable=True)           # 1/2/3/4 — độ khó
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluationRun(Base):
    """Kết quả một lần chạy đánh giá RAG."""
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    faithfulness = Column(Float, nullable=True)         # 0–1, target > 0.85
    answer_relevancy = Column(Float, nullable=True)     # 0–1, target > 0.80
    context_precision = Column(Float, nullable=True)    # 0–1, target > 0.75
    context_recall = Column(Float, nullable=True)       # 0–1, target > 0.80
    total_questions = Column(Integer, nullable=True)
    passed_questions = Column(Integer, nullable=True)   # số câu đạt ngưỡng
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluationCaseResult(Base):
    """One immutable automatic result plus the auditor's controlled verdict."""
    __tablename__ = "evaluation_case_results"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    test_case_id = Column(String(36), ForeignKey("test_cases.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    actual_answer = Column(Text, nullable=True)
    answer_similarity = Column(Float, nullable=True)
    grounding_score = Column(Float, nullable=True)
    retrieved_contexts = Column(JSONB, nullable=True, default=list)
    is_fallback = Column(String(10), nullable=True)
    auto_status = Column(String(20), nullable=False, default="review")
    manual_status = Column(String(20), nullable=False, default="pending")  # pending/pass/fail
    manual_note = Column(Text, nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
