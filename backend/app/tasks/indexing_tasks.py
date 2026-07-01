"""
TerraLegalAI — Celery Async Indexing Tasks
Xử lý indexing tài liệu bất đồng bộ qua Celery + Redis.

Cách chạy worker:
  celery -A backend.app.tasks.indexing_tasks worker --loglevel=info -Q indexing

Cách gọi task:
  from backend.app.tasks.indexing_tasks import index_document_task
  result = index_document_task.delay(document_id, file_path, source_name, ...)
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_celery_app():
    """Lazy init Celery app (tránh import lỗi nếu Redis không chạy)."""
    try:
        from celery import Celery
        from backend.app.core.config import settings

        app = Celery(
            "terralegal_tasks",
            broker=settings.redis_url,
            backend=settings.redis_url,
        )
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            result_expires=3600,            # Kết quả task hết hạn sau 1 giờ
            task_track_started=True,
            worker_prefetch_multiplier=1,   # Tránh một worker giữ quá nhiều task
            task_acks_late=True,            # Chỉ ack sau khi task xong
        )
        return app
    except ImportError:
        logger.warning("Celery không được cài đặt. Dùng `pip install celery` để cài.")
        return None


# Khởi tạo app (None nếu Celery chưa cài)
celery_app = get_celery_app()


def index_document_task(
    document_id: str,
    file_path: str,
    source_name: str,
    group_type: str,
    procedure_type: str,
):
    """
    Task index tài liệu — có thể gọi trực tiếp (sync) hoặc qua Celery (async).

    Nếu Celery khả dụng: gọi qua .delay() để chạy bất đồng bộ.
    Nếu không có Celery: chạy đồng bộ trong thread (fallback).
    """
    if celery_app:
        return _celery_index_task.delay(
            document_id=document_id,
            file_path=file_path,
            source_name=source_name,
            group_type=group_type,
            procedure_type=procedure_type,
        )
    else:
        # Fallback: chạy đồng bộ
        import threading
        from backend.app.api.v1.documents import _index_document_sync
        from backend.app.core.config import settings

        t = threading.Thread(
            target=_index_document_sync,
            kwargs={
                "document_id": document_id,
                "file_path": file_path,
                "source_name": source_name,
                "group_type": group_type,
                "procedure_type": procedure_type,
                "db_url": settings.database_url,
            },
            daemon=True,
        )
        t.start()
        return None


if celery_app:
    @celery_app.task(
        name="terralegal.index_document",
        bind=True,
        max_retries=3,
        default_retry_delay=60,
        queue="indexing",
        soft_time_limit=600,   # 10 phút
        time_limit=660,
    )
    def _celery_index_task(
        self,
        document_id: str,
        file_path: str,
        source_name: str,
        group_type: str,
        procedure_type: str,
    ):
        """
        Celery task thực thi indexing.
        Tự retry tối đa 3 lần nếu gặp lỗi.
        """
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from backend.app.core.config import settings

        logger.info(f"🔄 [Celery] Bắt đầu index document {document_id}: {source_name}")
        self.update_state(state="PROGRESS", meta={"status": "indexing", "document_id": document_id})

        try:
            from backend.app.api.v1.documents import _index_document_sync
            import threading, queue

            result_queue = queue.Queue()
            error_queue = queue.Queue()

            def _run():
                try:
                    _index_document_sync(
                        document_id=document_id,
                        file_path=file_path,
                        source_name=source_name,
                        group_type=group_type,
                        procedure_type=procedure_type,
                        db_url=settings.database_url,
                    )
                    result_queue.put("ok")
                except Exception as e:
                    error_queue.put(e)

            t = threading.Thread(target=_run)
            t.start()
            t.join(timeout=580)

            if not error_queue.empty():
                raise error_queue.get()

            logger.info(f"✅ [Celery] Document {document_id} indexed successfully")
            return {"status": "indexed", "document_id": document_id}

        except Exception as exc:
            logger.error(f"❌ [Celery] Indexing failed for {document_id}: {exc}")
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "error", "document_id": document_id, "error": str(exc)}
