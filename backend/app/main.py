"""
TerraLegalAI — FastAPI Backend
Entry point cho API server.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.security import get_current_user
from backend.app.api.v1 import (
    settings as app_settings,
    auth,
    chat,
    conversations,
    documents,
    evaluation,
    forms,
    health,
    reports,
    users,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("🚀 TerraLegalAI API starting up...")
    
    # Khởi tạo RAG Pipeline Singleton
    logger.info("📦 Initializing RAG Pipeline...")
    from backend.app.rag.pipeline import RAGPipeline
    from backend.app.embedding.embedding_model import EmbeddingModel
    from backend.app.embedding.vector_store import VectorStore
    from backend.app.core.database import init_db

    # Khởi tạo Database (SQLAlchemy)
    logger.info("📦 Initializing Database schema...")
    await init_db()
    
    vs = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection_name,
    )
    # Model sẽ load một lần duy nhất tại đây
    emb = EmbeddingModel(model_name=settings.embedding_model_name)
    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)

    app.state.rag_pipeline = RAGPipeline(
        vector_store=vs,
        embedding_model=emb,
        gemini_client=client,
        gemini_model=settings.gemini_model,
        top_k=settings.retrieval_top_k,
        reranker_top_k=settings.reranker_top_k,
        reranker_model_name=settings.reranker_model_name,
        reranker_enabled=settings.reranker_enabled,
        similarity_threshold=settings.similarity_threshold,
        temperature=settings.gemini_temperature,
        max_tokens=settings.gemini_max_tokens,
    )
    logger.info("✅ RAG Pipeline initialized successfully.")

    from backend.app.rag.agent import FormAgent
    app.state.form_agent = FormAgent()
    logger.info("✅ Form Agent initialized successfully.")

    yield
    
    logger.info("👋 TerraLegalAI API shutting down...")


app = FastAPI(
    title="TerraLegalAI API",
    description="Chatbot tư vấn thủ tục đất đai tỉnh Vĩnh Long",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"], dependencies=[Depends(get_current_user)])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"], dependencies=[Depends(get_current_user)])
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"], dependencies=[Depends(get_current_user)])
app.include_router(evaluation.router, prefix="/api/v1", tags=["Evaluation"], dependencies=[Depends(get_current_user)])
app.include_router(app_settings.router, prefix="/api/v1", tags=["Settings"], dependencies=[Depends(get_current_user)])
app.include_router(forms.router, prefix="/api/v1", tags=["Forms"], dependencies=[Depends(get_current_user)])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"], dependencies=[Depends(get_current_user)])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"], dependencies=[Depends(get_current_user)])


@app.get("/")
async def root():
    return {
        "app": "TerraLegalAI",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check_root():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
