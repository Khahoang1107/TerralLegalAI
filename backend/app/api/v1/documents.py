"""Documents management endpoints (stub)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/documents")
async def list_documents():
    """Danh sách tài liệu đã được index."""
    # TODO: Query từ PostgreSQL
    return {"documents": [], "total": 0}


@router.get("/documents/stats")
async def get_stats():
    """Thống kê hệ thống."""
    return {
        "total_documents": 0,
        "total_chunks": 0,
        "collections": ["land_law_chunks"],
    }
