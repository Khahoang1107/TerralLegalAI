import asyncio, json
from backend.app.db.session import SessionLocal
from backend.app.models.form_schema import FormSchema
from sqlalchemy import select

async def main():
    async with SessionLocal() as db:
        res = await db.execute(select(FormSchema))
        form = res.scalars().first()
        if form:
            print(json.dumps(form.fields))

asyncio.run(main())
