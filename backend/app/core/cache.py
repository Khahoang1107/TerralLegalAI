"""Best-effort Redis cache for context-free RAG responses.

Redis is an optimisation only: a connection failure must never prevent a
citizen from receiving a response from the RAG pipeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "rag:response:v1:"
_TTL_SECONDS = 6 * 60 * 60
_client: redis.Redis | None = None


def _cache_key(question: str, procedure_filter: str | None) -> str:
    normalized_question = " ".join(question.casefold().split())
    payload = f"{normalized_question}|{procedure_filter or 'all'}"
    return _PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def get_cached_response(question: str, procedure_filter: str | None) -> dict[str, Any] | None:
    """Return a cached response, or ``None`` when absent/unavailable."""
    try:
        raw = await _get_client().get(_cache_key(question, procedure_filter))
        return json.loads(raw) if raw else None
    except (redis.RedisError, json.JSONDecodeError) as exc:
        logger.warning("RAG cache read skipped: %s", exc)
        return None


async def set_cached_response(
    question: str, procedure_filter: str | None, response_data: dict[str, Any]
) -> None:
    """Cache a context-free response; failures are intentionally non-fatal."""
    try:
        payload = json.dumps(response_data, ensure_ascii=False, separators=(",", ":"))
        await _get_client().setex(_cache_key(question, procedure_filter), _TTL_SECONDS, payload)
    except (redis.RedisError, TypeError, ValueError) as exc:
        logger.warning("RAG cache write skipped: %s", exc)


async def get_cache_stats() -> dict[str, Any]:
    """Return compact cache diagnostics without exposing cached legal content."""
    try:
        client = _get_client()
        info = await client.info("memory")
        keys = 0
        async for _ in client.scan_iter(match=f"{_PREFIX}*", count=100):
            keys += 1
        return {"available": True, "entries": keys, "memory": info.get("used_memory_human", "unknown")}
    except redis.RedisError as exc:
        logger.warning("RAG cache stats unavailable: %s", exc)
        return {"available": False}
