"""
TerraLegalAI — RAGAS Evaluator
Đánh giá chất lượng RAG bằng thư viện RAGAS (nếu có API key Gemini).
Tính 4 metrics chuẩn: Faithfulness, Answer Relevancy, Context Precision, Context Recall.

Cách dùng:
    evaluator = RAGASEvaluator(gemini_api_key="...")
    results = evaluator.evaluate(samples)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RAGASEvaluator:
    """
    Wrapper cho RAGAS evaluation framework.
    Fallback sang heuristic evaluation nếu RAGAS không khả dụng.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key
        self._ragas_available = self._check_ragas()

    def _check_ragas(self) -> bool:
        """Kiểm tra xem RAGAS có được cài đặt không."""
        try:
            import ragas  # noqa
            return True
        except ImportError:
            logger.warning("RAGAS không được cài đặt. Dùng `pip install ragas` để cài.")
            return False

    def evaluate(self, samples: list[dict]) -> dict:
        """
        Đánh giá danh sách samples bằng RAGAS metrics.

        Args:
            samples: List[dict] mỗi item có keys:
                - question: str
                - answer: str (câu trả lời từ RAG)
                - contexts: List[str] (các chunks đã retrieve)
                - ground_truth: str (câu trả lời mong đợi)

        Returns:
            dict với: faithfulness, answer_relevancy, context_precision, context_recall
        """
        if self._ragas_available:
            return self._evaluate_with_ragas(samples)
        else:
            logger.warning("Dùng heuristic evaluation vì RAGAS không khả dụng")
            return self._evaluate_heuristic(samples)

    def _evaluate_with_ragas(self, samples: list[dict]) -> dict:
        """Đánh giá dùng RAGAS library chính thức."""
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

            # Setup LLM và embeddings cho RAGAS
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=self.gemini_api_key,
            )
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=self.gemini_api_key,
            )

            dataset = Dataset.from_list(samples)
            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=llm,
                embeddings=embeddings,
            )

            return {
                "faithfulness": float(result["faithfulness"]),
                "answer_relevancy": float(result["answer_relevancy"]),
                "context_precision": float(result["context_precision"]),
                "context_recall": float(result["context_recall"]),
                "evaluation_type": "ragas",
            }

        except Exception as e:
            logger.error(f"RAGAS evaluation thất bại: {e}. Fallback sang heuristic.")
            return self._evaluate_heuristic(samples)

    def _evaluate_heuristic(self, samples: list[dict]) -> dict:
        """
        Heuristic evaluation không cần API.
        - faithfulness: tỉ lệ context words xuất hiện trong answer
        - answer_relevancy: token overlap với ground truth
        - context_precision: tỉ lệ context có content (non-empty)
        - context_recall: estimated từ overlap
        """
        import re

        def tokenize(text: str) -> set[str]:
            return set(re.findall(r"\b\w+\b", text.lower()))

        faithfulness_scores = []
        relevancy_scores = []
        precision_scores = []
        recall_scores = []

        for s in samples:
            answer = s.get("answer", "")
            contexts = s.get("contexts", [])
            ground_truth = s.get("ground_truth", "")

            answer_tokens = tokenize(answer)
            gt_tokens = tokenize(ground_truth)
            context_tokens = tokenize(" ".join(contexts))

            # Faithfulness: bao nhiêu từ trong answer có trong context
            if answer_tokens and context_tokens:
                faith = len(answer_tokens & context_tokens) / len(answer_tokens)
                faithfulness_scores.append(min(faith, 1.0))

            # Answer relevancy: overlap với ground truth
            if answer_tokens and gt_tokens:
                union = answer_tokens | gt_tokens
                relevancy = len(answer_tokens & gt_tokens) / len(union) if union else 0
                relevancy_scores.append(relevancy)

            # Context precision: tỉ lệ context non-empty
            if contexts:
                non_empty = sum(1 for c in contexts if c.strip())
                precision_scores.append(non_empty / len(contexts))

            # Context recall: overlap giữa context và ground truth
            if context_tokens and gt_tokens:
                recall = len(context_tokens & gt_tokens) / len(gt_tokens) if gt_tokens else 0
                recall_scores.append(min(recall, 1.0))

        def avg(lst: list[float]) -> Optional[float]:
            return round(sum(lst) / len(lst), 3) if lst else None

        return {
            "faithfulness": avg(faithfulness_scores),
            "answer_relevancy": avg(relevancy_scores),
            "context_precision": avg(precision_scores),
            "context_recall": avg(recall_scores),
            "evaluation_type": "heuristic",
            "note": "Dùng heuristic token overlap — cài ragas để có kết quả chính xác hơn",
        }

    def prepare_sample(
        self,
        question: str,
        answer: str,
        retrieved_chunks: list[dict],
        expected_answer: str,
    ) -> dict:
        """
        Chuẩn bị một sample theo format RAGAS.
        """
        contexts = [chunk.get("text", "") for chunk in retrieved_chunks if chunk.get("text")]
        return {
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": expected_answer,
        }
