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
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "và", "là", "của", "cho", "có", "cần", "tôi", "bạn", "về", "ở", "được", "các", "một", "những",
    "thì", "khi", "nào", "bao", "nhiêu", "để", "theo", "với", "trong", "này", "đó", "không", "gì",
}


def _tokens(text: str) -> list[str]:
    """Stable Vietnamese-friendly tokens for lexical retrieval and evidence checks."""
    normalised = unicodedata.normalize("NFC", text or "").lower()
    return [token for token in re.findall(r"[\wđ]{2,}", normalised, flags=re.UNICODE) if token not in _STOP_WORDS]


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
    validity_status: str = "active"


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
- Tổng hợp đầy đủ nội dung cần thiết vào phần trả lời chính; không bắt người dùng phải mở trích dẫn mới hiểu được câu trả lời

QUY TẮC bắt buộc:
1. CHỈ trả lời dựa trên nội dung trong phần [TÀI LIỆU THAM KHẢO] bên dưới
2. KHÔNG bịa hoặc suy đoán thông tin không có trong tài liệu
3. Nếu không tìm thấy thông tin: nói rõ "Tôi chưa tìm thấy thông tin này trong tài liệu hiện có"
4. KHÔNG ghi nguồn chen giữa câu trả lời. Hệ thống giao diện sẽ tự hiển thị các nguồn tham khảo ở cuối câu trả lời
5. Khi liệt kê hồ sơ/giấy tờ: dùng danh sách số thứ tự rõ ràng và liệt kê đầy đủ các mục tìm thấy trong tài liệu
6. Diễn giải lại bằng lời của bạn, không chép nguyên văn các đoạn dài từ tài liệu

PHONG CÁCH trả lời:
- Bắt đầu bằng câu trả lời trực tiếp
- Sau đó mới đưa chi tiết (trình tự, hồ sơ, thời hạn...)
- Trả lời thành một nội dung hoàn chỉnh, không rút gọn vì đã có khung trích dẫn bên dưới
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
        reranker_model_name: str = "BAAI/bge-reranker-v2-m3",
        reranker_enabled: bool = False,
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
        self.reranker_model_name = reranker_model_name
        self.reranker_enabled = reranker_enabled
        self.similarity_threshold = similarity_threshold
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._cross_encoder = None
        self._cross_encoder_failed = False
        self._lexical_cache: dict[str, tuple[float, object, list[dict], list[list[str]]]] = {}

    def query(
        self,
        question: str,
        procedure_filter: Optional[str] = None,
        chat_history: Optional[list[dict]] = None,
        on_token: Optional[Callable[[str], None]] = None,
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
        start_time = time.time()
        stage_started = time.perf_counter()

        logger.info(f"🔍 Query: {question[:100]}...")

        # ── Step 1: Detect intent & expand query ─────────────────────
        intent = self._detect_intent(question)
        expanded_query = self._expand_query(question)

        # ── Step 2: Embed query ───────────────────────────────────────
        query_vector = self.embedding_model.encode_single(expanded_query)
        embedding_ms = int((time.perf_counter() - stage_started) * 1000)
        stage_started = time.perf_counter()

        # ── Step 3: Retrieve ──────────────────────────────────────────
        search_proc_type = procedure_filter
        if procedure_filter in ["chuyen_nhuong", "tang_cho"]:
            search_proc_type = [procedure_filter, "dang_ky_bien_dong"]

        vector_results = self.vector_store.search(
            query_vector=query_vector,
            # Retrieve a broader semantic candidate set before hybrid fusion.
            top_k=max(self.top_k * 3, self.reranker_top_k * 4),
            procedure_type=search_proc_type,
            score_threshold=self.similarity_threshold,
        )

        raw_results = self._hybrid_retrieve(
            question=expanded_query,
            vector_results=vector_results,
            procedure_type=search_proc_type,
            top_k=self.top_k,
        )
        retrieval_ms = int((time.perf_counter() - stage_started) * 1000)
        stage_started = time.perf_counter()

        retrieved_chunks = [
            RetrievedChunk(
                text=r["text"],
                score=r["score"],
                source_name=r["source_name"],
                article=r["article"],
                clause=r["clause"],
                field_type=r["field_type"],
                procedure_type=r["procedure_type"],
                validity_status=r.get("validity_status", "active"),
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
        rerank_ms = int((time.perf_counter() - stage_started) * 1000)
        stage_started = time.perf_counter()

        # ── Step 6: Build context + prompt ───────────────────────────
        context_text = self._build_context(top_chunks)
        messages = self._build_messages(
            question=question,
            context=context_text,
            chat_history=chat_history or [],
        )

        # ── Step 7: Call LLM ──────────────────────────────────────────
        # Gemini is an external dependency. A transient timeout/quota/network
        # failure must not turn a successful legal search into HTTP 500.
        first_token_ms: Optional[int] = None

        def emit_token(piece: str) -> None:
            nonlocal first_token_ms
            if first_token_ms is None:
                first_token_ms = int((time.time() - start_time) * 1000)
                logger.info("⚡ First streamed token in %sms", first_token_ms)
            if on_token is not None:
                on_token(piece)

        try:
            llm_response = self._call_llm(
                messages,
                on_token=emit_token if on_token is not None else None,
            )
        except Exception as exc:
            logger.error("LLM generation failed; returning retrieved legal context: %s", exc, exc_info=True)
            citations = self._extract_citations(top_chunks, "")
            excerpts = "\n\n".join(
                f"• {chunk.text.strip()[:900]}"
                for chunk in top_chunks[:2]
                if chunk.text.strip()
            )
            answer = (
                "Hệ thống đã tìm được tài liệu liên quan nhưng dịch vụ AI đang tạm thời "
                "không thể diễn giải câu trả lời. Nội dung tham khảo gần nhất là:\n\n"
                f"{excerpts}\n\n"
                "Bạn có thể gửi lại câu hỏi sau ít phút; các nguồn đối chiếu vẫn được hiển thị bên dưới."
            )
            latency_ms = int((time.time() - start_time) * 1000)
            return RAGResponse(
                answer=answer,
                citations=citations,
                retrieved_chunks=top_chunks,
                confidence=0.0,
                intent=intent,
                procedure_type=procedure_filter or self._detect_procedure(top_chunks),
                latency_ms=latency_ms,
                is_fallback=True,
            )
        llm_ms = int((time.perf_counter() - stage_started) * 1000)

        # ── Step 8: Parse citations ───────────────────────────────────
        citations = self._extract_citations(top_chunks, llm_response)
        confidence = self._calculate_confidence(top_chunks, llm_response, citations)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "✅ Query done in %sms | ttft=%s | embed=%sms retrieve=%sms rerank=%sms llm=%sms | confidence=%.2f",
            latency_ms,
            f"{first_token_ms}ms" if first_token_ms is not None else "n/a",
            embedding_ms,
            retrieval_ms,
            rerank_ms,
            llm_ms,
            confidence,
        )

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
        """Rerank hybrid candidates with a cross-encoder when available."""
        top_k = top_k or self.reranker_top_k
        if self.reranker_enabled and not self._cross_encoder_failed:
            try:
                if self._cross_encoder is None:
                    from sentence_transformers import CrossEncoder
                    self._cross_encoder = CrossEncoder(self.reranker_model_name, max_length=512)
                scores = self._cross_encoder.predict([(question, chunk.text) for chunk in chunks])
                low, high = min(scores), max(scores)
                span = high - low
                for chunk, score in zip(chunks, scores):
                    cross_score = (float(score) - low) / span if span else 1.0
                    # Keep a small hybrid prior for tied or short passages.
                    chunk.score = 0.80 * cross_score + 0.20 * chunk.score
            except Exception as exc:
                self._cross_encoder_failed = True
                logger.warning("Cross-encoder reranker unavailable; using hybrid retrieval score: %s", exc)
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]

    @staticmethod
    def _chunk_key(chunk: dict) -> tuple:
        return (chunk.get("source_file", ""), chunk.get("chunk_index", 0), chunk.get("text", "")[:120])

    def _lexical_candidates(self, question: str, procedure_type, top_k: int) -> list[dict]:
        """BM25 retrieval over Qdrant payloads; cache is short to allow re-indexing."""
        cache_key = ",".join(procedure_type) if isinstance(procedure_type, list) else (procedure_type or "all")
        now = time.time()
        cached = self._lexical_cache.get(cache_key)
        # Building BM25 requires scrolling every indexed chunk from Qdrant.
        # Keep it hot for an hour; application restart/re-index naturally
        # refreshes it, while avoiding a rebuild every few chat requests.
        if not cached or now - cached[0] > 3600:
            try:
                from rank_bm25 import BM25Okapi
                documents = self.vector_store.scroll_chunks(procedure_type=procedure_type)
                tokenized = [_tokens(f"{d.get('source_name', '')} {d.get('article', '')} {d.get('text', '')}") for d in documents]
                cached = (now, BM25Okapi(tokenized), documents, tokenized)
                self._lexical_cache[cache_key] = cached
            except Exception as exc:
                logger.warning("Lexical retrieval unavailable; semantic retrieval only: %s", exc)
                return []
        _, bm25, documents, _ = cached
        query_tokens = _tokens(question)
        if not query_tokens or not documents:
            return []
        scores = bm25.get_scores(query_tokens)
        # BM25's IDF is zero for a one-document/same-term corpus. A small
        # deterministic overlap fallback keeps exact legal identifiers usable.
        if max((float(score) for score in scores), default=0.0) <= 0:
            query_terms = set(query_tokens)
            scores = [len(query_terms & set(tokens)) / len(query_terms) for tokens in cached[3]]
        ranked = sorted(range(len(documents)), key=lambda index: scores[index], reverse=True)[:top_k]
        best = max((float(scores[index]) for index in ranked), default=0.0)
        return [{**documents[index], "lexical_score": float(scores[index]) / best if best > 0 else 0.0} for index in ranked if scores[index] > 0]

    def _hybrid_retrieve(self, question: str, vector_results: list[dict], procedure_type, top_k: int) -> list[dict]:
        """Fuse dense and BM25 rankings, so legal identifiers survive semantic misses."""
        lexical_results = self._lexical_candidates(question, procedure_type, max(self.top_k * 3, 20))
        merged: dict[tuple, dict] = {}
        max_vector = max((float(item.get("score", 0)) for item in vector_results), default=0.0)
        for item in vector_results:
            merged[self._chunk_key(item)] = {**item, "semantic_score": float(item.get("score", 0)) / max_vector if max_vector else 0.0, "lexical_score": 0.0}
        for item in lexical_results:
            key = self._chunk_key(item)
            current = merged.get(key, {**item, "semantic_score": 0.0})
            current["lexical_score"] = item.get("lexical_score", 0.0)
            merged[key] = current
        for item in merged.values():
            # Dense retrieval carries intent; BM25 protects exact law/form numbers.
            item["score"] = 0.65 * item["semantic_score"] + 0.35 * item["lexical_score"]
        return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:max(top_k, self.reranker_top_k)]

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Ghép chunks thành context block cho prompt."""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_ref = f"[{chunk.source_name}"
            if chunk.article:
                source_ref += f", {chunk.article}"
            if chunk.clause:
                source_ref += f", {chunk.clause}"
            status_label = {
                "active": "Còn hiệu lực",
                "amended": "Đã sửa đổi một phần",
                "superseded": "Đã bị thay thế",
                "repealed": "Hết hiệu lực",
            }.get(chunk.validity_status, chunk.validity_status or "Còn hiệu lực")
            source_ref += f" — {status_label}]"
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

Hãy trả lời câu hỏi trên dựa vào tài liệu tham khảo.
Nếu một nguồn được đánh dấu “Đã sửa đổi bổ sung” hoặc “Đã sửa đổi một phần”, không được khẳng định riêng
nội dung của nguồn đó còn nguyên hiệu lực; phải ưu tiên văn bản mới hơn trong
context và nêu rõ cần đối chiếu văn bản sửa đổi khi phạm vi sửa đổi chưa rõ.
Yêu cầu quan trọng: viết đầy đủ nội dung trả lời trong phần chính, không ghi nguồn chen giữa câu trả lời, không yêu cầu người dùng bấm mở trích dẫn để xem tiếp nội dung.
Hãy tóm tắt và diễn giải lại nội dung pháp lý bằng lời dễ hiểu, tránh chép nguyên văn các đoạn dài trong tài liệu."""

        messages.append({"role": "user", "content": user_content})
        return messages

    def _call_llm(
        self,
        messages: list[dict],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
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
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        
        if on_token is not None:
            pieces: list[str] = []
            finish_reason = None
            for chunk in self.gemini_client.models.generate_content_stream(
                model=self.gemini_model,
                contents=gemini_contents,
                config=config,
            ):
                piece = chunk.text or ""
                if piece:
                    pieces.append(piece)
                    on_token(piece)
                if getattr(chunk, "candidates", None):
                    finish_reason = getattr(chunk.candidates[0], "finish_reason", finish_reason)
            answer = "".join(pieces)
            logger.info("Gemini finish_reason=%s | response_chars=%s", finish_reason, len(answer))
            return answer

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=gemini_contents,
            config=config,
        )
        finish_reason = None
        if getattr(response, "candidates", None):
            finish_reason = getattr(response.candidates[0], "finish_reason", None)
        logger.info("Gemini finish_reason=%s | response_chars=%s", finish_reason, len(response.text or ""))
        return response.text

    def _extract_citations(self, chunks: list[RetrievedChunk], answer: str) -> list[Citation]:
        """Return only source passages with lexical evidence in the generated answer."""
        answer_terms = set(_tokens(answer))
        supported = []
        for chunk in chunks:
            chunk_terms = set(_tokens(chunk.text))
            support = len(answer_terms & chunk_terms) / max(len(answer_terms), 1)
            if support >= 0.08:
                supported.append((chunk, support))
        # Keep one provenance item when the answer is a very short paraphrase.
        if not supported and chunks:
            supported = [(chunks[0], 0.0)]
        return [
            Citation(
                source_name=c.source_name,
                article=c.article,
                clause=c.clause,
                # A citation is already a bounded document chunk. Keep the
                # complete chunk so the expandable source does not end in the
                # middle of a sentence (the old 200-character slice did).
                text_snippet=c.text.strip(),
                relevance_score=round(0.7 * c.score + 0.3 * support, 3),
            )
            for c, support in supported
        ]

    def _calculate_confidence(
        self,
        chunks: list[RetrievedChunk],
        answer: str,
        citations: list[Citation],
    ) -> float:
        """
        Tính confidence score dựa trên:
        - Similarity score của top chunk
        - Có tìm thấy fallback phrase không
        """
        if not chunks:
            return 0.0

        top_score = chunks[0].score
        fallback_phrases = ["chưa tìm thấy", "không có thông tin", "ngoài phạm vi"]
        has_fallback = any(p in answer.lower() for p in fallback_phrases)

        if has_fallback:
            return min(top_score * 0.5, 0.4)
        answer_terms = set(_tokens(answer))
        evidence_terms = set().union(*(set(_tokens(c.text_snippet)) for c in citations)) if citations else set()
        grounding = len(answer_terms & evidence_terms) / max(len(answer_terms), 1)
        citation_coverage = len(citations) / max(len(chunks), 1)
        return round(min(0.99, 0.55 * top_score + 0.35 * grounding + 0.10 * citation_coverage), 3)

    def _detect_procedure(self, chunks: list[RetrievedChunk]) -> str:
        """Detect loại thủ tục từ retrieved chunks."""
        if not chunks:
            return "unknown"
        proc_types = [c.procedure_type for c in chunks if c.procedure_type]
        if not proc_types:
            return "unknown"
        return max(set(proc_types), key=proc_types.count)
