"""
Fix: mark legal/auto-fill fields as required=False so the AI does not ask users about them.
Run once: python fix_legal_fields.py
"""
import asyncio
import sys
import unicodedata

sys.path.append("backend")
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.form_schema import FormSchema
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified


def remove_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


# Patterns that indicate a field is legal/auto-fill (should NOT ask user)
LEGAL_PATTERNS = [
    "noi nhan",      # Nơi nhận
    "noi nop",       # Nơi nộp
    "le phi",        # Lệ phí
    "thoi han",      # Thời hạn
    "can cu",        # Căn cứ pháp lý
    "co quan",       # Cơ quan
    "van phong dang ky",  # Văn phòng đăng ký
    "ket qua",       # Kết quả thực hiện
    "hinh thuc",     # Hình thức nhận
]


def is_legal_field(name: str) -> bool:
    n = remove_accents(name.lower())
    return any(pat in n for pat in LEGAL_PATTERNS)


async def main():
    async with AsyncSessionLocal() as db:
        forms = (
            await db.scalars(select(FormSchema).where(FormSchema.is_active == True))
        ).all()

        total_updated = 0
        for f in forms:
            updated = False
            new_fields = []
            for field in f.fields or []:
                field = dict(field)  # copy
                name = field.get("name", "")
                if is_legal_field(name) and field.get("required", False):
                    field["required"] = False
                    # Tag description so agent knows to auto-fill
                    desc = field.get("description", "")
                    if "[TU_DONG_DIEN]" not in desc:
                        field["description"] = desc + " [TU_DONG_DIEN]"
                    updated = True
                    total_updated += 1
                    print(f"  [FIXED] {f.name.encode('ascii','replace').decode()} -> {name.encode('ascii','replace').decode()}: required=True -> False")
                new_fields.append(field)

            if updated:
                f.fields = new_fields
                flag_modified(f, "fields")

        await db.commit()
        print(f"\nDone. Fixed {total_updated} fields across {len(forms)} forms.")


asyncio.run(main())
