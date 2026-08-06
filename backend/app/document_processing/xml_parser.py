import xml.etree.ElementTree as ET
import logging
from pathlib import Path

from backend.app.document_processing.pdf_parser import ParsedPage, ParsedDocument

logger = logging.getLogger(__name__)

class XMLParser:
    """Parser cho file XML, trích xuất text từ các thẻ để ingest."""
    def parse(self, file_path: str | Path) -> ParsedDocument:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
            
        logger.info(f"Đang parse XML: {file_path.name}")
            
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Cách 1: Lưu nguyên XML format
            # full_text = ET.tostring(root, encoding="unicode", method="xml")
            
            # Cách 2: Chỉ lấy nội dung text bên trong các thẻ (thường tốt hơn cho RAG)
            texts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())
            full_text = "\n".join(texts)
            
            # Nếu trống, fallback về dạng raw xml
            if not full_text.strip():
                full_text = ET.tostring(root, encoding="unicode", method="xml")
                
        except ET.ParseError as e:
            logger.error(f"Lỗi parse XML: {e}")
            full_text = ""
            
        pages = [ParsedPage(page_number=1, text=full_text, is_empty=not full_text.strip())]
        
        return ParsedDocument(
            file_path=str(file_path),
            file_name=file_path.name,
            total_pages=1,
            full_text=full_text,
            pages=pages,
            metadata={"file_size_bytes": file_path.stat().st_size}
        )
