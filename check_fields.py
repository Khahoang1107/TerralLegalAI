import asyncio
from sqlalchemy.future import select
from backend.app.core.database import SessionLocal
from backend.app.models.form_schema import FormSchema

async def main():
    async with SessionLocal() as db:
        res = await db.execute(select(FormSchema).order_by(FormSchema.created_at.desc()).limit(1))
        form = res.scalars().first()
        print(f"Form ID: {form.id}")
        for idx, f in enumerate(form.fields):
            print(f"[{idx}] {f.get('name')}: {f.get('require_one_of_group')}")

if __name__ == "__main__":
    asyncio.run(main())
