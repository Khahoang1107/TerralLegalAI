"""Health check endpoints."""
from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.core.cache import get_cache_stats

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "TerraLegalAI",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@router.get("/health/cache")
async def cache_stats():
    """Xem thống kê Redis cache: số câu hỏi đã cache, memory usage."""
    stats = await get_cache_stats()
    return {"cache": stats}
