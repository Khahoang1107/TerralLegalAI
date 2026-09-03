"""
Tests cho RAG Retriever và Pipeline.
Chạy: pytest backend/tests/ -v
"""
import pytest
from unittest.mock import MagicMock, patch


class TestRAGPipeline:
    """Unit tests cho RAGPipeline."""

    def _make_pipeline(self):
        """Tạo pipeline với mock dependencies."""
        from backend.app.rag.pipeline import RAGPipeline

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            {
                "text": "Hồ sơ chuyển nhượng gồm: 1. Đơn đăng ký...",
                "score": 0.92,
                "source_name": "QĐ 1085/QĐ-UBND",
                "article": "Điều 3",
                "clause": "Khoản 2",
                "field_type": "thanh_phan_ho_so",
                "procedure_type": "chuyen_nhuong",
            }
        ]

        mock_embedding_model = MagicMock()
        mock_embedding_model.encode_single.return_value = [0.1] * 1024

        mock_gemini_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Để chuyển nhượng đất, bạn cần chuẩn bị hồ sơ gồm..."
        mock_gemini_client.models.generate_content.return_value = mock_response

        pipeline = RAGPipeline(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            gemini_client=mock_gemini_client,
            gemini_model="gemini-1.5-flash",
        )
        return pipeline, mock_vector_store, mock_embedding_model, mock_gemini_client

    def test_query_basic(self):
        """Test query cơ bản — trả về RAGResponse hợp lệ."""
        pipeline, _, _, _ = self._make_pipeline()
        response = pipeline.query("Sang tên sổ đỏ cần giấy tờ gì?")

        assert response is not None
        assert response.answer
        assert response.confidence >= 0.0
        assert response.intent
        assert not response.is_fallback

    def test_query_with_procedure_filter(self):
        """Test query với procedure filter."""
        pipeline, mock_vs, _, _ = self._make_pipeline()
        pipeline.query("Hồ sơ cần gì?", procedure_filter="chuyen_nhuong")

        # Kiểm tra vector store được gọi đúng
        mock_vs.search.assert_called_once()
        call_kwargs = mock_vs.search.call_args.kwargs
        assert call_kwargs.get("procedure_type") is not None

    def test_query_fallback_when_no_results(self):
        """Test fallback khi không tìm thấy chunk nào."""
        pipeline, mock_vs, _, _ = self._make_pipeline()
        mock_vs.search.return_value = []  # Không có kết quả

        response = pipeline.query("Câu hỏi không liên quan gì cả")

        assert response.is_fallback
        assert response.confidence == 0.0
        assert "chưa tìm thấy" in response.answer.lower() or "liên hệ" in response.answer.lower()

    def test_detect_intent(self):
        """Test nhận dạng intent từ câu hỏi."""
        pipeline, _, _, _ = self._make_pipeline()

        assert pipeline._detect_intent("hồ sơ cần gì?") == "hoi_ho_so"
        assert pipeline._detect_intent("mất bao lâu?") == "hoi_thoi_han"
        assert pipeline._detect_intent("lệ phí là bao nhiêu?") == "hoi_le_phi"
        assert pipeline._detect_intent("nộp ở đâu?") == "hoi_co_quan"
        assert pipeline._detect_intent("câu hỏi khác") == "general"

    def test_expand_query(self):
        """Test mở rộng query với từ đồng nghĩa pháp lý."""
        pipeline, _, _, _ = self._make_pipeline()

        expanded = pipeline._expand_query("sang tên sổ đỏ")
        assert "chuyển nhượng" in expanded.lower()

        expanded2 = pipeline._expand_query("sổ hồng")
        assert "giấy chứng nhận" in expanded2.lower()

    def test_query_with_chat_history(self):
        """Test query với lịch sử hội thoại."""
        pipeline, _, _, mock_gemini = self._make_pipeline()
        chat_history = [
            {"role": "user", "content": "Tôi muốn bán đất"},
            {"role": "assistant", "content": "Để bán đất, bạn cần..."},
        ]

        pipeline.query("Cần bao nhiêu ngày?", chat_history=chat_history)

        # Kiểm tra LLM được gọi
        mock_gemini.models.generate_content.assert_called_once()

    def test_citations_extracted(self):
        """Test citations được trích xuất đúng từ chunks."""
        pipeline, _, _, _ = self._make_pipeline()
        response = pipeline.query("Hồ sơ gồm gì?")

        assert len(response.citations) > 0
        citation = response.citations[0]
        assert citation.source_name == "QĐ 1085/QĐ-UBND"
        assert citation.article == "Điều 3"
        assert citation.clause == "Khoản 2"

    def test_confidence_score(self):
        """Test confidence score tính đúng."""
        pipeline, _, _, _ = self._make_pipeline()
        response = pipeline.query("Hồ sơ gồm gì?")

        assert 0.0 <= response.confidence <= 1.0

    def test_hybrid_retrieval_keeps_exact_legal_keyword_hit(self):
        """BM25 can recover a legal identifier missed by semantic candidates."""
        pipeline, mock_vs, _, _ = self._make_pipeline()
        mock_vs.scroll_chunks.return_value = [
            {
                "text": "Mẫu số 09/ĐK dùng để đăng ký biến động đất đai.",
                "source_name": "QĐ 1085",
                "source_file": "qd1085.pdf",
                "chunk_index": 1,
                "article": "",
                "clause": "",
                "field_type": "mau_don",
                "procedure_type": "dang_ky_bien_dong",
            },
            {
                "text": "Thời hạn giải quyết hồ sơ cấp đổi giấy chứng nhận.",
                "source_name": "QĐ khác",
                "source_file": "other.pdf",
                "chunk_index": 2,
                "article": "",
                "clause": "",
                "field_type": "thoi_han",
                "procedure_type": "dang_ky_bien_dong",
            },
        ]
        results = pipeline._hybrid_retrieve(
            "Mẫu số 09/ĐK là gì?",
            vector_results=[],
            procedure_type="dang_ky_bien_dong",
            top_k=3,
        )
        assert results
        assert "09/ĐK" in results[0]["text"]

    def test_citations_prefer_passages_supporting_answer(self):
        pipeline, _, _, _ = self._make_pipeline()
        from backend.app.rag.pipeline import RetrievedChunk
        citations = pipeline._extract_citations([
            RetrievedChunk("Hồ sơ chuyển nhượng gồm đơn đăng ký biến động.", 0.9, "QĐ 1085"),
            RetrievedChunk("Lệ phí cấp đổi được áp dụng theo nghị quyết.", 0.8, "NQ phí"),
        ], "Hồ sơ chuyển nhượng cần đơn đăng ký biến động.")
        assert [citation.source_name for citation in citations] == ["QĐ 1085"]


class TestTextCleaner:
    """Unit tests cho TextCleaner."""

    def test_remove_page_numbers(self):
        from backend.app.document_processing.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        text = "Nội dung văn bản\n- 5 -\nTiếp theo"
        cleaned = cleaner.clean(text)
        assert "- 5 -" not in cleaned
        assert "Nội dung văn bản" in cleaned

    def test_normalize_legal_patterns(self):
        from backend.app.document_processing.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        text = "Điều3 quy định về hồ sơ"
        cleaned = cleaner._normalize_legal_patterns(text)
        assert "Điều 3" in cleaned

    def test_empty_text(self):
        from backend.app.document_processing.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean("") == ""
        assert cleaner.clean("   ") == ""


class TestMetadataExtractor:
    """Unit tests cho MetadataExtractor."""

    def test_extract_article(self):
        from backend.app.document_processing.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor()
        metadata = extractor.extract("Điều 3. Thành phần hồ sơ gồm:")
        assert metadata.article == "Điều 3"

    def test_extract_clause(self):
        from backend.app.document_processing.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor()
        metadata = extractor.extract("Khoản 2 quy định về thời hạn")
        assert metadata.clause == "Khoản 2"

    def test_detect_field_type_ho_so(self):
        from backend.app.document_processing.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor()
        metadata = extractor.extract("Thành phần hồ sơ gồm: đơn đăng ký, giấy chứng nhận")
        assert metadata.field_type == "thanh_phan_ho_so"

    def test_detect_field_type_thoi_han(self):
        from backend.app.document_processing.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor()
        metadata = extractor.extract("Thời hạn giải quyết: không quá 10 ngày làm việc")
        assert metadata.field_type == "thoi_han"

    def test_detect_procedure_type(self):
        from backend.app.document_processing.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor()
        metadata = extractor.extract("Hợp đồng chuyển nhượng quyền sử dụng đất")
        assert metadata.procedure_type == "chuyen_nhuong"
