"""
TerraLegalAI — DOCX Parser
Parse file DOCX (biểu mẫu, văn bản Word) thành text thuần.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """Kết quả parse một file DOCX."""
    file_path: str
    full_text: str
    total_paragraphs: int = 0
    tables: list[list[list[str]]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DOCXParser:
    """
    Parser cho file DOCX dùng python-docx.
    Hỗ trợ: văn bản thường, bảng, heading.
    """

    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse file DOCX thành ParsedDocument.

        Args:
            file_path: Đường dẫn file DOCX

        Returns:
            ParsedDocument với full_text và metadata
        """
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise RuntimeError("Cần cài python-docx: pip install python-docx")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        logger.info(f"Parsing DOCX: {file_path.name}")
        doc = DocxDocument(str(file_path))

        text_parts = []
        tables_data = []

        # Extract paragraphs (giữ cấu trúc heading)
        para_count = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            para_count += 1

            # Detect heading level
            style_name = para.style.name if para.style else ""
            if "Heading" in style_name or style_name.startswith("Title"):
                text_parts.append(f"\n\n{text}\n")
            else:
                text_parts.append(text)

        # Extract tables
        for table in doc.tables:
            table_rows = []
            table_text_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(row_cells)
                table_text_rows.append(" | ".join(c for c in row_cells if c))
            tables_data.append(table_rows)
            # Thêm table vào text
            table_text = "\n".join(r for r in table_text_rows if r)
            if table_text:
                text_parts.append(f"\n[Bảng]\n{table_text}\n")

        full_text = self._clean_text("\n".join(text_parts))

        logger.info(
            f"DOCX parsed: {para_count} đoạn văn, {len(tables_data)} bảng, "
            f"{len(full_text):,} ký tự"
        )

        return ParsedDocument(
            file_path=str(file_path),
            full_text=full_text,
            total_paragraphs=para_count,
            tables=tables_data,
            metadata={
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
            },
        )

    def _clean_text(self, text: str) -> str:
        """Làm sạch text: bỏ khoảng trắng thừa, normalize."""
        import re
        # Loại bỏ dòng trắng liên tiếp (giữ tối đa 2 dòng trắng)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Loại bỏ khoảng trắng thừa trong cùng một dòng
        text = re.sub(r"[ \t]+", " ", text)
        # Trim từng dòng
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()
