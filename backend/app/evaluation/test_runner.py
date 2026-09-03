"""
TerraLegalAI — Test Runner
Chạy bộ test cases qua RAG pipeline và tính các metrics đơn giản.
Dùng heuristic-based evaluation khi RAGAS không khả dụng.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Kết quả một test case."""
    test_case_id: str
    question: str
    expected_answer: str
    actual_answer: str
    procedure_group: Optional[str]
    # Scores
    answer_similarity: float = 0.0   # Token overlap với expected answer
    grounding_score: float = 0.0     # Answer token coverage by retrieved context
    context_recall_score: float = 0.0  # Expected-answer coverage by context
    retrieved_contexts: list[str] = field(default_factory=list)
    has_citation: bool = False        # Có citation không
    is_fallback: bool = False         # RAG trả về fallback không
    confidence: float = 0.0
    latency_ms: int = 0
    error: Optional[str] = None


@dataclass
class EvaluationResults:
    """Tổng hợp kết quả evaluation."""
    total_questions: int = 0
    passed_questions: int = 0
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    fallback_rate: float = 0.0
    citation_rate: float = 0.0
    details: list[TestResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_questions": self.total_questions,
            "passed_questions": self.passed_questions,
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "avg_confidence": round(self.avg_confidence, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 0),
            "fallback_rate": round(self.fallback_rate, 3),
            "citation_rate": round(self.citation_rate, 3),
            "details": [
                {
                    "test_case_id": item.test_case_id,
                    "question": item.question,
                    "expected_answer": item.expected_answer,
                    "actual_answer": item.actual_answer,
                    "answer_similarity": item.answer_similarity,
                    "grounding_score": item.grounding_score,
                    "retrieved_contexts": item.retrieved_contexts,
                    "is_fallback": item.is_fallback,
                    "error": item.error,
                }
                for item in self.details
            ],
        }


class TestRunner:
    """
    Chạy bộ test cases qua RAG pipeline.

    Metrics heuristic (không cần RAGAS API, dùng để regression chứ không thay RAGAS):
    - answer_relevancy: Token overlap giữa answer và expected_answer
    - faithfulness: token coverage của câu trả lời bởi context đã retrieve
    - context_precision: citation có phần trùng với câu trả lời
    - confidence_avg: Average confidence score từ pipeline
    """

    PASS_THRESHOLD = 0.4  # Ngưỡng tối thiểu để tính "passed"

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self, test_cases: list[dict]) -> dict:
        """
        Chạy toàn bộ test cases và trả về dict metrics.

        Args:
            test_cases: List[dict] với keys: question, expected_answer, procedure_group, id

        Returns:
            dict với các metrics chính
        """
        logger.info(f"🧪 Bắt đầu chạy {len(test_cases)} test cases...")
        results: list[TestResult] = []

        for i, tc in enumerate(test_cases, 1):
            logger.info(f"  [{i}/{len(test_cases)}] Q: {tc['question'][:60]}...")
            result = self._run_single(tc)
            results.append(result)

        return self._aggregate(results).to_dict()

    def _run_single(self, tc: dict) -> TestResult:
        """Chạy một test case."""
        start = time.time()
        try:
            response = self.pipeline.query(
                question=tc["question"],
                procedure_filter=tc.get("procedure_group"),
            )
            latency_ms = int((time.time() - start) * 1000)

            similarity = self._token_overlap(
                response.answer, tc["expected_answer"]
            )
            contexts = [chunk.text for chunk in response.retrieved_chunks]
            grounding = self._coverage(response.answer, " ".join(contexts))
            context_recall = self._coverage(tc["expected_answer"], " ".join(contexts))

            return TestResult(
                test_case_id=tc.get("id", "unknown"),
                question=tc["question"],
                expected_answer=tc["expected_answer"],
                actual_answer=response.answer,
                procedure_group=tc.get("procedure_group"),
                answer_similarity=similarity,
                grounding_score=grounding,
                context_recall_score=context_recall,
                retrieved_contexts=contexts,
                has_citation=bool(response.citations),
                is_fallback=response.is_fallback,
                confidence=response.confidence,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"  ❌ Lỗi test case {tc.get('id')}: {e}")
            return TestResult(
                test_case_id=tc.get("id", "unknown"),
                question=tc["question"],
                expected_answer=tc["expected_answer"],
                actual_answer="",
                procedure_group=tc.get("procedure_group"),
                error=str(e),
                latency_ms=int((time.time() - start) * 1000),
            )

    def _token_overlap(self, answer: str, expected: str) -> float:
        """
        Tính độ tương đồng đơn giản: token overlap (Jaccard similarity).
        Dùng làm proxy cho answer_relevancy khi không có RAGAS.
        """
        if not answer or not expected:
            return 0.0

        def tokenize(text: str) -> set[str]:
            import re
            words = re.findall(r"\b\w+\b", text.lower())
            return set(words)

        a_tokens = tokenize(answer)
        e_tokens = tokenize(expected)

        if not a_tokens or not e_tokens:
            return 0.0

        intersection = len(a_tokens & e_tokens)
        union = len(a_tokens | e_tokens)
        return round(intersection / union, 3) if union > 0 else 0.0

    def _coverage(self, target: str, source: str) -> float:
        """How much of a target's meaningful vocabulary is present in a source."""
        if not target or not source:
            return 0.0
        import re
        target_tokens = set(re.findall(r"\b\w+\b", target.lower()))
        source_tokens = set(re.findall(r"\b\w+\b", source.lower()))
        return round(len(target_tokens & source_tokens) / len(target_tokens), 3) if target_tokens else 0.0

    def _aggregate(self, results: list[TestResult]) -> EvaluationResults:
        """Tổng hợp kết quả từ tất cả test cases."""
        if not results:
            return EvaluationResults()

        valid = [r for r in results if not r.error]
        if not valid:
            return EvaluationResults(total_questions=len(results))

        # Tính metrics
        non_fallback = [r for r in valid if not r.is_fallback]
        with_citation = [r for r in valid if r.has_citation]
        similarities = [r.answer_similarity for r in valid]
        passed = [r for r in valid if r.answer_similarity >= self.PASS_THRESHOLD]

        faithfulness = sum(r.grounding_score for r in valid) / len(valid) if valid else 0.0
        # Citation rate remains useful operationally; the score below is not
        # presented as legal proof and RAGAS is still recommended for releases.
        context_precision = len(with_citation) / len(valid) if valid else 0.0
        answer_relevancy = sum(similarities) / len(similarities) if similarities else 0.0
        avg_confidence = sum(r.confidence for r in valid) / len(valid) if valid else 0.0
        avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0.0

        return EvaluationResults(
            total_questions=len(results),
            passed_questions=len(passed),
            faithfulness=round(faithfulness, 3),
            answer_relevancy=round(answer_relevancy, 3),
            context_precision=round(context_precision, 3),
            context_recall=round(sum(r.context_recall_score for r in valid) / len(valid), 3),
            avg_confidence=avg_confidence,
            avg_latency_ms=avg_latency,
            fallback_rate=round(1 - faithfulness, 3),
            citation_rate=round(context_precision, 3),
            details=results,
        )
