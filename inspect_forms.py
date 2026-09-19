import asyncio, json, os, sys
sys.path.insert(0, '/app')
os.chdir('/app')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

async def main():
    db_url = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@postgres/terralegal')
    engine = create_async_engine(db_url)
    async with AsyncSession(engine) as session:
        result = await session.execute(text("SELECT id, name, fields FROM forms LIMIT 5"))
        for row in result:
            print(f'ID: {row[0]}, Name: {row[1]}')
            fields = row[2] or []
            if isinstance(fields, list):
                for f in fields[:10]:
                    print(f'  {json.dumps(f, ensure_ascii=False)}')

asyncio.run(main())
