import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from backend.app.models.form_schema import FormSchema

async def main():
    engine = create_async_engine('postgresql+asyncpg://terralegal_user:terralegal_pass_dev@localhost:5432/terralegal')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        res = await session.execute(select(FormSchema).order_by(FormSchema.created_at.desc()).limit(1))
        form = res.scalars().first()
        if form:
            with open("form_fields.json", "w", encoding="utf-8") as f:
                json.dump(form.fields, f, ensure_ascii=False, indent=2)
            print("Dumped to form_fields.json")
        else:
            print('No form')

asyncio.run(main())
