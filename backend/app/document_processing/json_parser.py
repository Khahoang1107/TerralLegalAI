import json
import logging
from pathlib import Path

from backend.app.document_processing.pdf_parser import ParsedPage, ParsedDocument

logger = logging.getLogger(__name__)

class JSONParser:
    """Parser cho file JSON, chuyển đổi cấu trúc thành text để ingest."""
    def parse(self, file_path: str | Path) -> ParsedDocument:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
            
        logger.info(f"Đang parse JSON: {file_path.name}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Chuyển JSON thành chuỗi có định dạng để dễ chunking
        full_text = json.dumps(data, indent=2, ensure_ascii=False)
        
        pages = [ParsedPage(page_number=1, text=full_text, is_empty=not full_text.strip())]
        
        return ParsedDocument(
            file_path=str(file_path),
            file_name=file_path.name,
            total_pages=1,
            full_text=full_text,
            pages=pages,
            metadata={"file_size_bytes": file_path.stat().st_size}
        )
