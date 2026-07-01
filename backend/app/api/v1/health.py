"""Health check endpoints."""
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "TerraLegalAI",
        "version": "0.1.0",
        "env": settings.app_env,
    }
