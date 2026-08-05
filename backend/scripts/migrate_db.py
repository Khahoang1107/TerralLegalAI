import asyncio
import os
import sys

# Thêm thư mục gốc vào path để import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from backend.app.core.database import engine, init_db

async def migrate():
    print("Bắt đầu migrate dữ liệu...")
    
    # Chạy create_all để tạo bảng mới (system_settings, form_schemas) nếu chưa có
    await init_db()
    
    async with engine.begin() as conn:
        print("Kiểm tra và thêm cột cho bảng documents...")
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN validity_status VARCHAR(50) DEFAULT 'Còn hiệu lực';"))
            print("Đã thêm validity_status")
        except Exception as e:
            print(f"Cột validity_status có thể đã tồn tại: {e}")
            
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN promulgation_date DATE;"))
            print("Đã thêm promulgation_date")
        except Exception as e:
            pass
            
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN effective_date DATE;"))
            print("Đã thêm effective_date")
        except Exception as e:
            pass
            
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN issuing_agency VARCHAR(255);"))
            print("Đã thêm issuing_agency")
        except Exception as e:
            pass
            
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN related_documents JSONB;"))
            print("Đã thêm related_documents")
        except Exception as e:
            pass

        print("Kiểm tra và thêm cột cho bảng conversations...")
        try:
            await conn.execute(text("ALTER TABLE conversations ADD COLUMN state JSONB;"))
            print("Đã thêm state")
        except Exception as e:
            print(f"Cột state có thể đã tồn tại: {e}")
            
    print("Hoàn tất migrate!")

if __name__ == "__main__":
    asyncio.run(migrate())
