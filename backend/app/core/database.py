from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from backend.app.core.config import settings

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
    """FastAPI Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Khởi tạo database schema nếu cần."""
    from backend.app.models.base import Base
    import backend.app.models.document      # noqa
    import backend.app.models.conversation  # noqa
    import backend.app.models.user          # noqa
    import backend.app.models.evaluation    # noqa
    import backend.app.models.setting       # noqa
    import backend.app.models.form_schema   # noqa
    import backend.app.models.form_submission  # noqa — bảng lịch sử tạo đơn

    async with engine.begin() as conn:
        # Trong production nên dùng Alembic, ở đây tạo bảng tạm cho Phase 1
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight forward-compatible schema addition for the per-case RAG
        # evidence introduced after the initial evaluation table existed.
        await conn.execute(text("ALTER TABLE evaluation_case_results ADD COLUMN IF NOT EXISTS retrieved_contexts JSONB"))
        # Chunk-level legal validity. PostgreSQL remains the source of truth;
        # Qdrant payloads are a derived search index.
        await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS point VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS validity_status VARCHAR(30) NOT NULL DEFAULT 'active'"))
        await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS effective_from DATE"))
        await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS effective_to DATE"))
        await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS validity_note TEXT"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_validity ON document_chunks(validity_status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_document_article ON document_chunks(document_id, article, clause)"))
