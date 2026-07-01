"""
TerraLegalAI — OCR Module
Xử lý PDF dạng ảnh scan bằng Tesseract OCR + tiếng Việt.

Quy trình:
PDF → Render từng trang thành ảnh (PyMuPDF) → OCR (Tesseract vie) → Text

Yêu cầu:
- Tesseract v5+ đã cài với language pack 'vie'
- pytesseract (pip wrapper)
- PyMuPDF để render PDF thành ảnh
"""
import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Kết quả OCR toàn bộ file PDF."""
    file_path: str
    file_name: str
    total_pages: int
    full_text: str
    pages_text: list[str] = field(default_factory=list)
    ocr_confidence: float = 0.0  # Trung bình confidence score


class PDFOCRProcessor:
    """
    OCR processor cho PDF ảnh scan tiếng Việt.
    Sử dụng Tesseract v5 với model tiếng Việt.
    
    Tesseract cần được cài trước:
    - Windows: https://github.com/UB-Mannheim/tesseract/wiki
    - Đảm bảo 'vie' language pack đã có
    
    Kiểm tra: tesseract --list-langs | grep vie
    """

    def __init__(
        self,
        lang: str = "vie+eng",
        dpi: int = 300,
        tesseract_cmd: Optional[str] = None,
    ):
        """
        Args:
            lang: Ngôn ngữ OCR ("vie" hoặc "vie+eng")
            dpi: DPI render ảnh từ PDF (cao hơn = chính xác hơn, chậm hơn)
            tesseract_cmd: Đường dẫn tesseract nếu không trong PATH
        """
        self.lang = lang
        self.dpi = dpi
        self._setup_tesseract(tesseract_cmd)

    def _setup_tesseract(self, tesseract_cmd: Optional[str]):
        """Cấu hình pytesseract."""
        try:
            import pytesseract
            self.pytesseract = pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            # Test tesseract có hoạt động không
            pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OK, lang={self.lang}, dpi={self.dpi}")
        except ImportError:
            logger.error(
                "pytesseract chưa cài. Chạy: pip install pytesseract"
            )
            raise
        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            raise

    def process(self, file_path: str | Path) -> OCRResult:
        """
        OCR toàn bộ file PDF.
        
        Args:
            file_path: Đường dẫn đến PDF ảnh scan
            
        Returns:
            OCRResult với full_text từng trang
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        logger.info(f"Bat dau OCR: {file_path.name} (lang={self.lang}, dpi={self.dpi})")

        doc = fitz.open(str(file_path))
        total_pages = len(doc)
        pages_text = []
        confidences = []

        for page_num in range(total_pages):
            logger.info(f"  OCR trang {page_num + 1}/{total_pages}...")
            page = doc[page_num]

            # Render trang thành ảnh với DPI cao
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert sang PIL Image
            import io
            from PIL import Image
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))

            # OCR với Tesseract
            try:
                # Lấy text
                text = self.pytesseract.image_to_string(
                    img,
                    lang=self.lang,
                    config="--oem 3 --psm 3",  # OEM 3=LSTM, PSM 3=auto layout
                )

                # Lấy confidence (optional, chậm hơn)
                # data = self.pytesseract.image_to_data(img, lang=self.lang, output_type=Output.DICT)

                pages_text.append(text.strip())
                logger.info(f"    -> {len(text)} ký tự")

            except Exception as e:
                logger.error(f"  OCR error page {page_num + 1}: {e}")
                pages_text.append("")

        doc.close()

        full_text = "\n\n".join(p for p in pages_text if p)
        full_text = self._post_process(full_text)

        logger.info(
            f"OCR xong: {file_path.name} | "
            f"{total_pages} trang | "
            f"{len(full_text):,} ky tu"
        )

        return OCRResult(
            file_path=str(file_path),
            file_name=file_path.name,
            total_pages=total_pages,
            full_text=full_text,
            pages_text=pages_text,
        )

    def _post_process(self, text: str) -> str:
        """
        Hậu xử lý text OCR:
        - Sửa các lỗi OCR tiếng Việt phổ biến
        - Normalize khoảng trắng
        """
        import re

        # Fix lỗi phổ biến Tesseract với tiếng Việt
        replacements = {
            # Dấu bị nhận nhầm
            "ôi.": "ối",   # Thường gặp khi OCR chữ nghiêng
            " ,": ",",
            " .": ".",
            "( ": "(",
            " )": ")",
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)

        # Normalize khoảng trắng
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


def ocr_pdf(
    file_path: str,
    output_txt: Optional[str] = None,
    lang: str = "vie+eng",
    dpi: int = 300,
) -> str:
    """
    Convenience function: OCR một file PDF và trả về text.
    
    Args:
        file_path: Đường dẫn PDF
        output_txt: Nếu có, lưu text ra file này
        lang: Ngôn ngữ OCR
        dpi: DPI render
        
    Returns:
        Chuỗi text đã OCR
    """
    processor = PDFOCRProcessor(lang=lang, dpi=dpi)
    result = processor.process(file_path)

    if output_txt:
        Path(output_txt).write_text(result.full_text, encoding="utf-8")
        logger.info(f"Da luu text vao: {output_txt}")

    return result.full_text


# ─── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python ocr_processor.py <path_to_pdf> [output.txt]")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    text = ocr_pdf(input_pdf, output_txt=output_file)
    print(f"\n--- 500 ky tu dau tien ---")
    print(text[:500])
