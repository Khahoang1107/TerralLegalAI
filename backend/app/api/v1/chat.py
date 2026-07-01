"""
TerraLegalAI — Chat API Endpoints
POST /api/v1/chat — Gửi câu hỏi, nhận câu trả lời RAG
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Request
import asyncio

from backend.app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Request / Response schemas ───────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, description="Câu hỏi của người dùng")
    conversation_id: Optional[str] = Field(None, description="ID cuộc hội thoại (để giữ context)")
    procedure_filter: Optional[str] = Field(
        None,
        description="Filter theo thủ tục: chuyen_nhuong | cap_doi",
        pattern="^(chuyen_nhuong|cap_doi)$",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Sang tên sổ đỏ cần giấy tờ gì?",
                "procedure_filter": "chuyen_nhuong",
            }
        }
    }


class CitationSchema(BaseModel):
    source_name: str
    article: str = ""
    clause: str = ""
    text_snippet: str = ""
    relevance_score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationSchema]
    confidence: float
    intent: str
    procedure_type: str
    conversation_id: Optional[str]
    message_id: Optional[str]
    latency_ms: int
    is_fallback: bool = False


# ─── Dependency: RAG Pipeline ─────────────────────────────────────

def get_rag_pipeline(request: Request):
    """
    Dependency injection cho RAG pipeline.
    Lấy pipeline singleton đã được khởi tạo từ app.state trong lifespan.
    """
    if not hasattr(request.app.state, "rag_pipeline"):
        raise HTTPException(status_code=500, detail="RAG Pipeline is not initialized")
    return request.app.state.rag_pipeline


# ─── Endpoints ────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Gửi câu hỏi và nhận câu trả lời từ RAG pipeline.
    
    - Câu hỏi được tìm kiếm trong kho tài liệu đất đai Vĩnh Long
    - Trả lời kèm trích dẫn nguồn cụ thể (điều, khoản, văn bản)
    - Hỗ trợ filter theo loại thủ tục
    """
    import uuid

    logger.info(f"Chat request: '{request.question[:80]}...'")

    try:
        pipeline = get_rag_pipeline(req)
        # Chạy pipeline.query đồng bộ trong một thread pool để không block event loop
        rag_response = await asyncio.to_thread(
            pipeline.query,
            question=request.question,
            procedure_filter=request.procedure_filter,
        )

        return ChatResponse(
            answer=rag_response.answer,
            citations=[
                CitationSchema(
                    source_name=c.source_name,
                    article=c.article,
                    clause=c.clause,
                    text_snippet=c.text_snippet,
                    relevance_score=c.relevance_score,
                )
                for c in rag_response.citations
            ],
            confidence=rag_response.confidence,
            intent=rag_response.intent,
            procedure_type=rag_response.procedure_type,
            conversation_id=request.conversation_id or str(uuid.uuid4()),
            message_id=str(uuid.uuid4()),
            latency_ms=rag_response.latency_ms,
            is_fallback=rag_response.is_fallback,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý câu hỏi: {str(e)}",
        )


@router.get("/chat/suggestions")
async def get_suggestions(procedure: Optional[str] = None):
    """Gợi ý câu hỏi phổ biến theo loại thủ tục."""
    suggestions = {
        "chuyen_nhuong": [
            "Hồ sơ chuyển nhượng quyền sử dụng đất gồm những gì?",
            "Chuyển nhượng đất mất bao lâu?",
            "Nộp hồ sơ chuyển nhượng ở đâu?",
            "Điều kiện để chuyển nhượng quyền sử dụng đất là gì?",
            "Tôi bán đất cho người khác thì thủ tục thế nào?",
        ],
        "cap_doi": [
            "Cấp đổi Giấy chứng nhận cần giấy tờ gì?",
            "Sổ đỏ bị rách thì làm thủ tục gì?",
            "Cấp đổi sổ đỏ mất bao lâu?",
            "Nộp hồ sơ cấp đổi GCN ở đâu?",
            "Lệ phí cấp đổi Giấy chứng nhận là bao nhiêu?",
        ],
        "all": [
            "Sang tên sổ đỏ cần giấy tờ gì?",
            "Ba mẹ cho tôi đất thì cần làm thủ tục gì?",
            "Sổ đỏ bị hỏng thì xin cấp đổi thế nào?",
            "Chuyển nhượng đất mất bao lâu?",
            "Nộp hồ sơ đất đai ở đâu tại Vĩnh Long?",
        ],
    }
    key = procedure if procedure in suggestions else "all"
    return {"suggestions": suggestions[key]}
