import asyncio
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.document import Document

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document))
        docs = result.scalars().all()
        for doc in docs:
            print(doc.id, doc.status, doc.file_path)

asyncio.run(main())
