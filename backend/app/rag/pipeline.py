"""
TerraLegalAI — RAG Pipeline (Core)
Orchestrates toàn bộ luồng: Retrieve → Rerank → Prompt → LLM → Response

Luồng:
1. Nhận câu hỏi từ user
2. Query expansion (tùy chọn)
3. Embed câu hỏi
4. Hybrid retrieval từ Qdrant
5. Rerank top results
6. Build prompt với context
7. Gọi LLM (GPT-4o)
8. Parse response + extract citations
9. Trả về answer + sources
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Chunk được retrieve từ vector store."""
    text: str
    score: float
    source_name: str
    article: str = ""
    clause: str = ""
    field_type: str = ""
    procedure_type: str = ""


@dataclass
class Citation:
    """Trích dẫn nguồn trong câu trả lời."""
    source_name: str
    article: str = ""
    clause: str = ""
    text_snippet: str = ""
    relevance_score: float = 0.0


@dataclass
class RAGResponse:
    """Kết quả đầy đủ từ RAG pipeline."""
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    confidence: float
    intent: str
    procedure_type: str
    latency_ms: int = 0
    is_fallback: bool = False  # True nếu không tìm được thông tin


# ─── System Prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = """Bạn là TerraLegal AI — trợ lý tư vấn thủ tục đất đai tại tỉnh Vĩnh Long, Việt Nam.

NHIỆM VỤ của bạn:
- Trả lời câu hỏi của người dân về thủ tục đất đai dựa CHÍNH XÁC vào tài liệu được cung cấp
- Sử dụng ngôn ngữ đơn giản, dễ hiểu, thân thiện (như giải thích cho người dân bình thường)
- Trích dẫn nguồn cụ thể sau mỗi thông tin quan trọng

QUY TẮC bắt buộc:
1. CHỈ trả lời dựa trên nội dung trong phần [TÀI LIỆU THAM KHẢO] bên dưới
2. KHÔNG bịa hoặc suy đoán thông tin không có trong tài liệu
3. Nếu không tìm thấy thông tin: nói rõ "Tôi chưa tìm thấy thông tin này trong tài liệu hiện có"
4. Sau mỗi thông tin quan trọng, ghi rõ nguồn: [Nguồn: <tên văn bản>, <điều khoản>]
5. Khi liệt kê hồ sơ/giấy tờ: dùng danh sách số thứ tự rõ ràng

PHONG CÁCH trả lời:
- Bắt đầu bằng câu trả lời trực tiếp
- Sau đó mới đưa chi tiết (trình tự, hồ sơ, thời hạn...)
- Kết thúc bằng gợi ý liên hệ nếu cần hỗ trợ thêm"""


FALLBACK_RESPONSE = """Xin lỗi, tôi chưa tìm thấy thông tin chính xác về câu hỏi của bạn trong cơ sở dữ liệu hiện tại.

👉 Bạn có thể:
- **Liên hệ trực tiếp**: Văn phòng Đăng ký Đất đai tỉnh Vĩnh Long
- **Đặt câu hỏi theo cách khác**: Ví dụ, cho biết rõ hơn bạn muốn làm thủ tục gì (chuyển nhượng, tặng cho, cấp đổi sổ...)
- **Tra cứu trực tuyến**: Cổng dịch vụ công tỉnh Vĩnh Long

Tôi có thể giúp bạn về các thủ tục: **chuyển nhượng đất**, **tặng cho đất**, và **cấp đổi Giấy chứng nhận**."""


class RAGPipeline:
    """
    RAG Pipeline chính của TerraLegalAI.
    
    Usage:
        pipeline = RAGPipeline(vector_store, embedding_model, openai_client)
        response = pipeline.query("Sang tên sổ đỏ cần giấy tờ gì?")
    """

    def __init__(
        self,
        vector_store,
        embedding_model,
        gemini_client: genai.Client,
        gemini_model: str = "gemini-1.5-flash",
        top_k: int = 10,
        reranker_top_k: int = 3,
        similarity_threshold: float = 0.65,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.gemini_client = gemini_client
        self.gemini_model = gemini_model
        self.top_k = top_k
        self.reranker_top_k = reranker_top_k
        self.similarity_threshold = similarity_threshold
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query(
        self,
        question: str,
        procedure_filter: Optional[str] = None,
        chat_history: Optional[list[dict]] = None,
    ) -> RAGResponse:
        """
        Thực hiện toàn bộ RAG pipeline cho một câu hỏi.
        
        Args:
            question: Câu hỏi của người dùng
            procedure_filter: Filter theo thủ tục ("chuyen_nhuong" / "cap_doi")
            chat_history: Lịch sử hội thoại [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            RAGResponse với answer, citations, confidence
        """
        import time
        start_time = time.time()

        logger.info(f"🔍 Query: {question[:100]}...")

        # ── Step 1: Detect intent & expand query ─────────────────────
        intent = self._detect_intent(question)
        expanded_query = self._expand_query(question)

        # ── Step 2: Embed query ───────────────────────────────────────
        query_vector = self.embedding_model.encode_single(expanded_query)

        # ── Step 3: Retrieve ──────────────────────────────────────────
        search_proc_type = procedure_filter
        if procedure_filter in ["chuyen_nhuong", "tang_cho"]:
            search_proc_type = [procedure_filter, "dang_ky_bien_dong"]

        raw_results = self.vector_store.search(
            query_vector=query_vector,
            top_k=self.top_k,
            procedure_type=search_proc_type,
            score_threshold=self.similarity_threshold,
        )

        retrieved_chunks = [
            RetrievedChunk(
                text=r["text"],
                score=r["score"],
                source_name=r["source_name"],
                article=r["article"],
                clause=r["clause"],
                field_type=r["field_type"],
                procedure_type=r["procedure_type"],
            )
            for r in raw_results
        ]

        # ── Step 4: Kiểm tra nếu không tìm thấy gì ───────────────────
        if not retrieved_chunks:
            logger.warning(f"Không tìm thấy chunk nào cho query: {question}")
            return RAGResponse(
                answer=FALLBACK_RESPONSE,
                citations=[],
                retrieved_chunks=[],
                confidence=0.0,
                intent=intent,
                procedure_type=procedure_filter or "unknown",
                latency_ms=int((time.time() - start_time) * 1000),
                is_fallback=True,
            )

        # ── Step 5: Rerank (simple score-based, upgrade sang cross-encoder sau) ──
        top_chunks = self._rerank(question, retrieved_chunks)

        # ── Step 6: Build context + prompt ───────────────────────────
        context_text = self._build_context(top_chunks)
        messages = self._build_messages(
            question=question,
            context=context_text,
            chat_history=chat_history or [],
        )

        # ── Step 7: Call LLM ──────────────────────────────────────────
        llm_response = self._call_llm(messages)

        # ── Step 8: Parse citations ───────────────────────────────────
        citations = self._extract_citations(top_chunks)
        confidence = self._calculate_confidence(top_chunks, llm_response)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"✅ Query done in {latency_ms}ms | confidence={confidence:.2f}")

        return RAGResponse(
            answer=llm_response,
            citations=citations,
            retrieved_chunks=top_chunks,
            confidence=confidence,
            intent=intent,
            procedure_type=procedure_filter or self._detect_procedure(top_chunks),
            latency_ms=latency_ms,
            is_fallback=False,
        )

    def _detect_intent(self, question: str) -> str:
        """Nhận dạng ý định câu hỏi từ từ khoá."""
        q = question.lower()
        intent_keywords = {
            "hoi_ho_so": ["hồ sơ", "giấy tờ", "cần gì", "cần có gì", "chuẩn bị gì"],
            "hoi_trinh_tu": ["trình tự", "các bước", "làm thế nào", "thủ tục", "làm sao"],
            "hoi_thoi_han": ["mất bao lâu", "bao nhiêu ngày", "thời hạn", "thời gian"],
            "hoi_le_phi": ["lệ phí", "phí", "tiền", "chi phí", "tốn bao nhiêu"],
            "hoi_co_quan": ["nộp ở đâu", "cơ quan", "văn phòng", "ở đâu"],
            "hoi_dieu_kien": ["điều kiện", "yêu cầu", "có được không", "có thể không"],
            "hoi_mau_don": ["mẫu đơn", "mẫu số", "tờ khai", "biểu mẫu"],
        }
        for intent, keywords in intent_keywords.items():
            if any(kw in q for kw in keywords):
                return intent
        return "general"

    def _expand_query(self, question: str) -> str:
        """
        Mở rộng câu hỏi với các từ đồng nghĩa pháp lý.
        Ví dụ: "sang tên sổ đỏ" → thêm "chuyển nhượng quyền sử dụng đất"
        """
        expansions = {
            "sang tên sổ đỏ": "chuyển nhượng quyền sử dụng đất đăng ký biến động",
            "sổ đỏ": "giấy chứng nhận quyền sử dụng đất",
            "sổ hồng": "giấy chứng nhận quyền sử dụng đất",
            "bán đất": "chuyển nhượng quyền sử dụng đất",
            "cho đất": "tặng cho quyền sử dụng đất",
            "cấp đổi sổ": "cấp đổi giấy chứng nhận quyền sử dụng đất",
            "đổi sổ": "cấp đổi giấy chứng nhận",
        }
        expanded = question
        for informal, formal in expansions.items():
            if informal in question.lower():
                expanded = f"{question} {formal}"
                break
        return expanded

    def _rerank(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        top_k: int = None,
    ) -> list[RetrievedChunk]:
        """
        Rerank chunks theo relevance score.
        MVP: dùng vector score. Phase 2: upgrade sang cross-encoder.
        """
        top_k = top_k or self.reranker_top_k
        sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
        return sorted_chunks[:top_k]

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Ghép chunks thành context block cho prompt."""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_ref = f"[{chunk.source_name}"
            if chunk.article:
                source_ref += f", {chunk.article}"
            if chunk.clause:
                source_ref += f", {chunk.clause}"
            source_ref += "]"
            parts.append(f"--- Tài liệu {i} {source_ref} ---\n{chunk.text}")
        return "\n\n".join(parts)

    def _build_messages(
        self,
        question: str,
        context: str,
        chat_history: list[dict],
    ) -> list[dict]:
        """Build message list cho OpenAI API."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Thêm lịch sử hội thoại (tối đa 6 tin nhắn gần nhất)
        if chat_history:
            messages.extend(chat_history[-6:])

        # Thêm context + câu hỏi
        user_content = f"""[TÀI LIỆU THAM KHẢO]
{context}

[CÂU HỎI CỦA NGƯỜI DÂN]
{question}

Hãy trả lời câu hỏi trên dựa vào tài liệu tham khảo. Trích dẫn nguồn cụ thể."""

        messages.append({"role": "user", "content": user_content})
        return messages

    def _call_llm(self, messages: list[dict]) -> str:
        """Gọi Gemini API và trả về text response."""
        system_instruction = ""
        gemini_contents = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
            elif msg["role"] == "assistant":
                gemini_contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        
        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=gemini_contents,
            config=config,
        )
        return response.text

    def _extract_citations(self, chunks: list[RetrievedChunk]) -> list[Citation]:
        """Tạo danh sách citations từ top chunks."""
        return [
            Citation(
                source_name=c.source_name,
                article=c.article,
                clause=c.clause,
                text_snippet=c.text[:200],
                relevance_score=c.score,
            )
            for c in chunks
        ]

    def _calculate_confidence(
        self,
        chunks: list[RetrievedChunk],
        answer: str,
    ) -> float:
        """
        Tính confidence score dựa trên:
        - Similarity score của top chunk
        - Có tìm thấy fallback phrase không
        """
        if not chunks:
            return 0.0

        top_score = chunks[0].score if chunks else 0.0
        fallback_phrases = ["chưa tìm thấy", "không có thông tin", "ngoài phạm vi"]
        has_fallback = any(p in answer.lower() for p in fallback_phrases)

        if has_fallback:
            return min(top_score * 0.5, 0.4)
        return min(top_score, 0.99)

    def _detect_procedure(self, chunks: list[RetrievedChunk]) -> str:
        """Detect loại thủ tục từ retrieved chunks."""
        if not chunks:
            return "unknown"
        proc_types = [c.procedure_type for c in chunks if c.procedure_type]
        if not proc_types:
            return "unknown"
        return max(set(proc_types), key=proc_types.count)
