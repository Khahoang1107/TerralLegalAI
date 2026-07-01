import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.rag.pipeline import RAGPipeline
from backend.app.embedding.embedding_model import EmbeddingModel
from backend.app.embedding.vector_store import VectorStore
from backend.app.core.config import settings
from google import genai

async def test():
    vs = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection_name,
    )
    emb = EmbeddingModel(model_name=settings.embedding_model_name)
    client = genai.Client(api_key=settings.gemini_api_key)

    pipeline = RAGPipeline(
        vector_store=vs,
        embedding_model=emb,
        gemini_client=client,
        gemini_model=settings.gemini_model,
        top_k=settings.retrieval_top_k,
        similarity_threshold=settings.similarity_threshold,
        temperature=settings.gemini_temperature,
        max_tokens=settings.gemini_max_tokens,
    )
    
    resp = pipeline.query("Sổ đỏ bị hỏng thì xin cấp đổi thế nào?")
    with open("test_rag_out.txt", "w", encoding="utf-8") as f:
        f.write(resp.answer)
    print("DONE")

if __name__ == "__main__":
    asyncio.run(test())
