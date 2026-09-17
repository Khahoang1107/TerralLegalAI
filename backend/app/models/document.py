from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text, Float
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
    
    # Metadata hiệu lực văn bản
    document_number = Column(String(100), nullable=True)  # Số/ký hiệu: "1085/QĐ-UBND"
    validity_status = Column(String(50), default="Còn hiệu lực")
    promulgation_date = Column(Date, nullable=True)
    effective_date = Column(Date, nullable=True)
    issuing_agency = Column(String(255), nullable=True)
    # Quan hệ văn bản: [{"document_id": "...", "relation": "amends"|"amended_by"|"replaces"|"replaced_by", "effective_date": "..."}]
    related_documents = Column(JSONB, nullable=True, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(255), primary_key=True) # ID từ chunker, e.g., QD_1085_chunk_0
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    article = Column(String(50), nullable=True)
    clause = Column(String(50), nullable=True)
    point = Column(String(50), nullable=True)
    field_type = Column(String(50), nullable=True)
    validity_status = Column(String(30), nullable=False, default="active", index=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    validity_note = Column(Text, nullable=True)
    
    document = relationship("Document", back_populates="chunks")


class AmendmentAnalysis(Base):
    """Persistent, reviewable result of a rule/AI amendment analysis."""
    __tablename__ = "amendment_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft")
    method = Column(String(20), nullable=False, default="rules")
    changes = Column(JSONB, nullable=False, default=list)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)


class ProvisionEffect(Base):
    """Audited legal effect confirmed by an administrator."""
    __tablename__ = "provision_effects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("amendment_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_chunk_id = Column(String(255), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    replacement_chunk_id = Column(String(255), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    effect_type = Column(String(30), nullable=False)
    effective_from = Column(Date, nullable=True)
    evidence_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    confirmed_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    confirmed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
