from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.app.models.base import Base


class FormSubmission(Base):
    """Lich su moi lan nguoi dung tao/xuat don tu bieu mau."""

    __tablename__ = "form_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK -> form_schemas.id
    form_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # FK -> users.id (nguoi tao don)
    user_id = Column(String(36), nullable=False, index=True)

    # FK -> conversations.id (neu tao qua luong chat, co the null neu tao truc tiep)
    conversation_id = Column(String(36), nullable=True, index=True)

    # Toan bo data nguoi dung da dien vao, dung de tai tao lai don neu can
    filled_data = Column(JSONB, nullable=False, default=dict)

    # Ten file da sinh ra (dang: "<form_id>_<submission_id>.docx")
    output_filename = Column(String(512), nullable=True)

    # Dinh dang file xuat ra: "docx" hoac "pdf"
    output_format = Column(String(10), nullable=False, default="docx")

    created_at = Column(DateTime, default=datetime.utcnow)
