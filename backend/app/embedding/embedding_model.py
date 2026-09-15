"""
TerraLegalAI — Embedding Model Wrapper
Sử dụng BAAI/bge-m3 (multilingual, tốt cho tiếng Việt).
Hỗ trợ batch encoding và caching.
"""
import logging
from functools import lru_cache
from collections import OrderedDict
from threading import Lock

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Wrapper cho BAAI/bge-m3 embedding model.
    
    Đặc điểm bge-m3:
    - Multilingual (100+ ngôn ngữ, bao gồm tiếng Việt)
    - Output dimension: 1024
    - Hỗ trợ cả dense embedding và sparse (BM25-style)
    - Miễn phí, chạy local (không cần API key)
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        batch_size: int = 32,
        max_length: int = 512,
        use_fp16: bool = True,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.use_fp16 = use_fp16
        self._model = None
        self._query_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._query_cache_lock = Lock()
        self._query_cache_size = 256

    def _load_model(self):
        """Lazy load model (chỉ load khi cần, tránh load lúc khởi động)."""
        if self._model is None:
            logger.info(f"🔄 Loading embedding model: {self.model_name}")
            try:
                from FlagEmbedding import BGEM3FlagModel
                self._model = BGEM3FlagModel(
                    self.model_name,
                    use_fp16=self.use_fp16,
                )
                logger.info(f"✅ Model loaded: {self.model_name}")
            except ImportError:
                # Fallback sang sentence-transformers nếu FlagEmbedding không có
                logger.warning(
                    "FlagEmbedding không tìm thấy, dùng sentence-transformers fallback"
                )
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._use_flag = False
                return
            self._use_flag = True

    def encode(self, texts: list[str]) -> list[list[float]]:
        """
        Encode danh sách texts thành vectors.
        
        Args:
            texts: Danh sách chuỗi văn bản cần encode
            
        Returns:
            List of vectors, mỗi vector có 1024 chiều
        """
        self._load_model()

        if not texts:
            return []

        logger.info(f"Encoding {len(texts)} texts (batch_size={self.batch_size})")

        all_embeddings = []

        # Xử lý theo batch
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            if self._use_flag:
                result = self._model.encode(
                    batch,
                    batch_size=self.batch_size,
                    max_length=self.max_length,
                    return_dense=True,
                    return_sparse=False,  # Chỉ dense cho Qdrant
                    return_colbert_vecs=False,
                )
                batch_vectors = result["dense_vecs"].tolist()
            else:
                # sentence-transformers fallback
                batch_vectors = self._model.encode(
                    batch,
                    batch_size=self.batch_size,
                    normalize_embeddings=True,
                ).tolist()

            all_embeddings.extend(batch_vectors)

        logger.info(f"✅ Encoded {len(all_embeddings)} vectors (dim={len(all_embeddings[0])})")
        return all_embeddings

    def encode_single(self, text: str) -> list[float]:
        """Encode một text đơn lẻ (dùng cho query embedding)."""
        cache_key = " ".join((text or "").casefold().split())
        with self._query_cache_lock:
            cached = self._query_cache.get(cache_key)
            if cached is not None:
                self._query_cache.move_to_end(cache_key)
                logger.debug("Query embedding cache hit")
                return list(cached)

        results = self.encode([text])
        vector = results[0] if results else []
        if vector:
            with self._query_cache_lock:
                self._query_cache[cache_key] = tuple(vector)
                self._query_cache.move_to_end(cache_key)
                while len(self._query_cache) > self._query_cache_size:
                    self._query_cache.popitem(last=False)
        return vector

    @property
    def dimension(self) -> int:
        """Số chiều của vector output."""
        return 1024  # bge-m3 default


# ─── Singleton instance ───────────────────────────────────────────
@lru_cache(maxsize=1)
def get_embedding_model() -> EmbeddingModel:
    """Return cached singleton EmbeddingModel."""
    from backend.app.core.config import settings
    return EmbeddingModel(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
    )
