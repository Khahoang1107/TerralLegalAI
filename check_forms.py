import asyncio
from backend.app.core.database import SessionLocal
from backend.app.models.form_schema import FormSchema
from sqlalchemy import select
import json

async def check():
    async with SessionLocal() as db:
        result = await db.execute(select(FormSchema))
        forms = result.scalars().all()
        for form in forms:
            print(f"Form ID: {form.id}")
            print(f"Name: {form.name}")
            print(f"Fields:")
            print(json.dumps(form.fields, indent=2, ensure_ascii=False))
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check())
