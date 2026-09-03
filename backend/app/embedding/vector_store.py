"""
TerraLegalAI — Qdrant Vector Store
Wrapper cho Qdrant client: tạo collection, upsert chunks, search.
"""
import logging
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    MatchAny,
    PointStruct,
    VectorParams,

)

from backend.app.document_processing.chunker import DocumentChunk

logger = logging.getLogger(__name__)

# Tên collection trong Qdrant
COLLECTION_NAME = "land_law_chunks"


class VectorStore:
    """
    Qdrant vector store cho TerraLegalAI.
    
    Schema mỗi point:
    {
      id: uuid,
      vector: [float x 1024],
      payload: {
        chunk_id, text, source_name, source_file,
        group_type, procedure_type, article, clause,
        field_type, chunk_index, token_estimate
      }
    }
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = COLLECTION_NAME,
        embedding_dim: int = 1024,
    ):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.client = QdrantClient(host=host, port=port)
        logger.info(f"Connected to Qdrant at {host}:{port}")

    def create_collection_if_not_exists(self):
        """Tạo Qdrant collection nếu chưa có."""
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            logger.info(f"Collection '{self.collection_name}' đã tồn tại.")
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"✅ Đã tạo collection: {self.collection_name}")

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> int:
        """
        Lưu chunks + vectors vào Qdrant.
        
        Args:
            chunks: Danh sách DocumentChunk
            vectors: Embedding vectors tương ứng (cùng thứ tự)
            
        Returns:
            Số lượng points đã upsert thành công
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) và vectors ({len(vectors)}) không khớp số lượng"
            )

        points = []
        for chunk, vector in zip(chunks, vectors):
            point = PointStruct(
                id=str(uuid.uuid4()),  # Qdrant point ID
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "source_name": chunk.source_name,
                    "group_type": chunk.group_type,
                    "procedure_type": chunk.procedure_type,
                    "article": chunk.article,
                    "clause": chunk.clause,
                    "field_type": chunk.field_type,
                    "chunk_index": chunk.chunk_index,
                    "token_estimate": chunk.token_estimate,
                },
            )
            points.append(point)

        # Upsert theo batch (1000 points/lần)
        batch_size = 100
        upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            upserted += len(batch)
            logger.info(f"  Upserted {upserted}/{len(points)} points...")

        logger.info(f"✅ Đã upsert {upserted} points vào '{self.collection_name}'")
        return upserted

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        procedure_type: Optional[str] = None,
        group_type: Optional[str] = None,
        field_type: Optional[str] = None,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """
        Tìm kiếm chunks liên quan nhất với query vector.
        
        Args:
            query_vector: Vector của câu hỏi
            top_k: Số kết quả trả về
            procedure_type: Filter theo loại thủ tục (chuyen_nhuong/cap_doi)
            group_type: Filter theo nhóm tài liệu
            field_type: Filter theo loại trường (thanh_phan_ho_so/thoi_han...)
            score_threshold: Điểm similarity tối thiểu
            
        Returns:
            List[dict] với keys: text, score, source_name, article, clause, ...
        """
        # Build filter conditions
        conditions = []
        if procedure_type:
            if isinstance(procedure_type, list):
                conditions.append(
                    FieldCondition(key="procedure_type", match=MatchAny(any=procedure_type))
                )
            else:
                conditions.append(
                    FieldCondition(key="procedure_type", match=MatchValue(value=procedure_type))
                )
        if group_type:
            conditions.append(
                FieldCondition(key="group_type", match=MatchValue(value=group_type))
            )
        if field_type:
            conditions.append(
                FieldCondition(key="field_type", match=MatchValue(value=field_type))
            )

        query_filter = Filter(must=conditions) if conditions else None

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            {
                "text": r.payload.get("text", ""),
                "score": r.score,
                "source_name": r.payload.get("source_name", ""),
                "source_file": r.payload.get("source_file", ""),
                "article": r.payload.get("article", ""),
                "clause": r.payload.get("clause", ""),
                "field_type": r.payload.get("field_type", ""),
                "procedure_type": r.payload.get("procedure_type", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
            }
            for r in results.points
        ]

    def scroll_chunks(
        self,
        procedure_type: Optional[str | list[str]] = None,
        limit: int = 10000,
    ) -> list[dict]:
        """Read indexed chunks for the local lexical (BM25) side of hybrid search.

        This is read-only and paginated so it stays correct when the collection
        grows beyond a single Qdrant scroll page.
        """
        conditions = []
        if procedure_type:
            match = MatchAny(any=procedure_type) if isinstance(procedure_type, list) else MatchValue(value=procedure_type)
            conditions.append(FieldCondition(key="procedure_type", match=match))
        query_filter = Filter(must=conditions) if conditions else None
        records: list[dict] = []
        offset = None
        while len(records) < limit:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=min(256, limit - len(records)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            records.extend({
                "text": point.payload.get("text", ""),
                "score": 0.0,
                "source_name": point.payload.get("source_name", ""),
                "source_file": point.payload.get("source_file", ""),
                "article": point.payload.get("article", ""),
                "clause": point.payload.get("clause", ""),
                "field_type": point.payload.get("field_type", ""),
                "procedure_type": point.payload.get("procedure_type", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
            } for point in points)
            if offset is None or not points:
                break
        return records

    def get_collection_info(self) -> dict:
        """Thông tin collection (số points, trạng thái...)."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": str(info.status),
            "vector_size": info.config.params.vectors.size,
        }

    def delete_by_source(self, source_file: str) -> int:
        """Xóa tất cả points từ một file nguồn (dùng khi re-index)."""
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            ),
        )
        logger.info(f"Đã xóa points từ source: {source_file}")
        return result.status
