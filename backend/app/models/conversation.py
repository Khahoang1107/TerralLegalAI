from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Boolean, SmallInteger, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)  # UUID string
    user_id = Column(String(36), nullable=True, index=True)
    title = Column(String(255), default="Cuộc trò chuyện mới")
    procedure_type = Column(String(50), nullable=True)  # chuyen_nhuong / cap_doi / all
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)  # UUID string
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True)          # detected intent (hoi_ho_so, hoi_trinh_tu, ...)
    retrieved_chunks = Column(JSONB, nullable=True)      # [{chunk_id, score, source_name}]
    citations = Column(JSONB, nullable=True)             # [{source_name, article, clause, text_snippet, relevance_score}]
    confidence = Column(Float, nullable=True)            # 0.0 – 1.0
    latency_ms = Column(Integer, nullable=True)
    is_fallback = Column(Boolean, default=False)
    feedback = Column(SmallInteger, nullable=True)       # 1 = thumbs up, -1 = thumbs down
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

