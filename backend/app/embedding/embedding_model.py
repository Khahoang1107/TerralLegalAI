"""
TerraLegalAI — Embedding Model Wrapper
Sử dụng BAAI/bge-m3 (multilingual, tốt cho tiếng Việt).
Hỗ trợ batch encoding và caching.
"""
import logging
import os
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
        cpu_threads: int | None = None,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.use_fp16 = use_fp16
        self.cpu_threads = cpu_threads
        self._model = None
        self._query_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._query_cache_lock = Lock()
        self._query_cache_size = 256

    def _load_model(self):
        """Lazy load model.

        - Model bắt đầu bằng 'BAAI/bge-m3' → dùng FlagEmbedding (nếu có).
        - Mọi model khác (multilingual-e5-*, paraphrase-*, ...) → sentence-transformers.
        """
        if self._model is not None:
            return
        # The production VPS runs one backend worker to avoid loading the
        # embedding model twice. Explicitly give that worker both CPU cores.
        # This is safe for local development too: a missing torch install is
        # handled by the model import below.
        if self.cpu_threads and self.cpu_threads > 0:
            try:
                import torch
                torch.set_num_threads(self.cpu_threads)
                torch.set_num_interop_threads(1)
                logger.info("Embedding CPU threads configured: %s", self.cpu_threads)
            except (ImportError, RuntimeError) as exc:
                logger.warning("Could not configure embedding CPU threads: %s", exc)
        logger.info(f"🔄 Loading embedding model: {self.model_name}")
        is_bge_m3 = "bge-m3" in self.model_name.lower()
        if is_bge_m3:
            try:
                from FlagEmbedding import BGEM3FlagModel
                self._model = BGEM3FlagModel(
                    self.model_name,
                    use_fp16=self.use_fp16,
                )
                self._use_flag = True
                logger.info(f"✅ Model loaded (FlagEmbedding): {self.model_name}")
                return
            except ImportError:
                logger.warning("FlagEmbedding không tìm thấy, fallback sang sentence-transformers")
        # sentence-transformers fallback (hoặc model nhẹ như multilingual-e5-small)
        from sentence_transformers import SentenceTransformer
        # Use the persistent production cache configured through HF_HOME.
        # Without an explicit cache folder, an image rebuild can make the
        # first public chat download the multi-GB model and hit a gateway
        # timeout before the answer is generated.
        self._model = SentenceTransformer(
            self.model_name,
            cache_folder=os.getenv("SENTENCE_TRANSFORMERS_HOME") or os.getenv("HF_HOME"),
        )
        self._use_flag = False
        logger.info(f"✅ Model loaded (sentence-transformers): {self.model_name}")

    def encode(self, texts: list[str]) -> list[list[float]]:
        """
        Encode danh sách texts thành vectors.
        
        Args:
            texts: Danh sách chuỗi văn bản cần encode
            
        Returns:
            List of vectors, mỗi vector có 1024 chiều
        """
        return self._encode(texts, is_query=False)

    def _encode(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        """Encode texts, adding E5's required query/passage instruction."""
        self._load_model()

        if not texts:
            return []

        # E5 models were trained with distinct prefixes.  Applying them is
        # essential: legal chunks are passages, while a citizen message is a
        # query.  BGE and other existing models keep their current behaviour.
        if "e5" in self.model_name.lower():
            prefix = "query: " if is_query else "passage: "
            texts = [
                text if text.startswith(("query: ", "passage: ")) else prefix + text
                for text in texts
            ]

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

        # Keep this call through ``encode`` so callers/tests can provide an
        # inexpensive encoder replacement.  E5 sees the explicit query
        # prefix, while document indexing continues to receive passage.
        query_text = f"query: {text}" if "e5" in self.model_name.lower() else text
        results = self.encode([query_text])
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
        """Số chiều của vector output (lấy từ config, không hardcode)."""
        from backend.app.core.config import settings
        return settings.embedding_dimension


# ─── Singleton instance ───────────────────────────────────────────
@lru_cache(maxsize=1)
def get_embedding_model() -> EmbeddingModel:
    """Return cached singleton EmbeddingModel."""
    from backend.app.core.config import settings
    return EmbeddingModel(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
        cpu_threads=settings.embedding_cpu_threads,
    )
