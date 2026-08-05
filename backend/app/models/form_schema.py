from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.app.models.base import Base


class FormSchema(Base):
    __tablename__ = "form_schemas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    procedure_type = Column(String(255), nullable=False, index=True)
    fields = Column(JSONB, nullable=False)
    html_template = Column(Text, nullable=True)

    # ── Nâng cấp v2 ─────────────────────────────────────────────
    # Lưu ánh xạ { "1": "ho_ten", "2": "cmnd" } sau khi admin gán nhãn
    mapping = Column(JSONB, nullable=True)

    # Ẩn/hiện form mà không xóa khỏi DB (soft delete)
    is_active = Column(Boolean, nullable=False, default=True)

    # Mô tả tóm tắt thủ tục cho người dùng đọc
    description = Column(Text, nullable=True)

    # Căn cứ pháp lý áp dụng (VD: "Thông tư 09/2021/TT-BTNMT")
    legal_basis = Column(String(255), nullable=True)

    # Phiên bản mẫu đơn (dùng khi có cập nhật thay thế mẫu cũ)
    version = Column(Integer, nullable=False, default=1)

    # Người upload mẫu (FK → users.id)
    created_by = Column(String(36), nullable=True)
    # ─────────────────────────────────────────────────────────────

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

