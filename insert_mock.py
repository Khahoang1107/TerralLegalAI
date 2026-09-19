import asyncio
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.document import Document
import uuid

async def main():
    async with AsyncSessionLocal() as session:
        new_doc = Document(
            id=uuid.uuid4(),
            source_name="TestDocument123.pdf",
            file_path="data/uploaded/test.pdf",
            group_type="VB",
            procedure_type="all",
            status="indexed"
        )
        session.add(new_doc)
        await session.commit()
        print("Inserted mock doc")

asyncio.run(main())
