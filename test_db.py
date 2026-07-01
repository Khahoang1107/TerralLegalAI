import asyncio
from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text('SELECT id, title FROM conversations;'))
        print(res.fetchall())
        
asyncio.run(main())
