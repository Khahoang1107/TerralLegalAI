from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name = Column(String(255), nullable=False, unique=True, index=True)
    file_path = Column(String(500), nullable=True)
    group_type = Column(String(50), nullable=False, index=True)
    procedure_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default="indexed")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(255), primary_key=True) # ID từ chunker, e.g., QD_1085_chunk_0
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    article = Column(String(50), nullable=True)
    clause = Column(String(50), nullable=True)
    field_type = Column(String(50), nullable=True)
    
    document = relationship("Document", back_populates="chunks")
