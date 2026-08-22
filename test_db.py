import asyncio
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        for u in result.scalars():
            print(f"ID: {u.id} | Email: {u.email} | Name: {u.full_name} | Role: {u.role}")

asyncio.run(main())
