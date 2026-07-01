import asyncio
import sys
import os

# Add the project root to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from backend.app.core.database import engine

async def alter_table():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE conversations ADD COLUMN title VARCHAR(255) DEFAULT 'Cuộc trò chuyện mới';"))
            print("Successfully added 'title' column to 'conversations' table.")
        except Exception as e:
            print(f"Error altering table (perhaps column already exists?): {e}")

if __name__ == "__main__":
    asyncio.run(alter_table())
