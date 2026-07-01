"""
TerraLegalAI — PaddleOCR Processor
OCR tài liệu PDF scan tiếng Việt bằng PaddleOCR v4.

Ưu điểm so với Tesseract:
- Độ chính xác tiếng Việt ~95-98% (vs ~80-85% Tesseract)
- Giữ dấu tiếng Việt tốt hơn nhiều
- Nhận dạng layout phức tạp (bảng, đa cột) tốt hơn
- Dùng deep learning (PP-OCR v4 model)

Cài đặt:
    pip install paddlepaddle==3.0.0
    pip install paddleocr==2.9.1

Lần đầu chạy sẽ tự động download model (~100MB).
"""
import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class OCRPageResult:
    page_number: int
    text: str
    confidence: float = 0.0
    raw_boxes: list = field(default_factory=list)


@dataclass
class OCRResult:
    """Kết quả OCR toàn bộ file PDF."""
    file_path: str
    file_name: str
    total_pages: int
    full_text: str
    pages: list[OCRPageResult] = field(default_factory=list)
    avg_confidence: float = 0.0


class PaddleOCRProcessor:
    """
    OCR processor cho PDF ảnh scan tiếng Việt dùng PaddleOCR v4.

    PaddleOCR pipeline:
    1. Render PDF page → PIL Image (PyMuPDF)
    2. Text Detection (DBNet++) → bounding boxes
    3. Text Recognition (PP-OCR v4) → text strings
    4. Post-process → ghép thành đoạn văn

    Usage:
        processor = PaddleOCRProcessor()
        result = processor.process("path/to/scan.pdf")
        print(result.full_text)
    """

    def __init__(
        self,
        lang: str = "vi",          # Tiếng Việt
        dpi: int = 200,            # DPI render (200 đủ cho PaddleOCR)
        use_gpu: bool = False,     # True nếu có CUDA GPU
        use_angle_cls: bool = True, # Tự xoay text nghiêng
        det_model: str = "PP-OCRv4",
    ):
        self.lang = lang
        self.dpi = dpi
        self.use_gpu = use_gpu
        self.use_angle_cls = use_angle_cls
        self._ocr = None  # Lazy load

    def _load_model(self):
        """Lazy load PaddleOCR model (download lần đầu ~100MB)."""
        if self._ocr is not None:
            return
        logger.info("Loading PaddleOCR model (co the mat vai phut lan dau)...")
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang=self.lang,
                use_gpu=self.use_gpu,
                use_angle_cls=self.use_angle_cls,
                show_log=False,
            )
            logger.info("PaddleOCR loaded OK!")
        except ImportError:
            raise ImportError(
                "PaddleOCR chua cai. Chay:\n"
                "  pip install paddlepaddle==3.0.0\n"
                "  pip install paddleocr==2.9.1"
            )

    def process(self, file_path: str | Path) -> OCRResult:
        """
        OCR toàn bộ file PDF.

        Args:
            file_path: Đường dẫn file PDF scan

        Returns:
            OCRResult với full_text từng trang
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File khong ton tai: {file_path}")

        self._load_model()
        logger.info(f"Bat dau OCR: {file_path.name} (DPI={self.dpi})")

        doc = fitz.open(str(file_path))
        total_pages = len(doc)
        pages = []
        all_confidences = []

        for page_num in range(total_pages):
            logger.info(f"  OCR trang {page_num + 1}/{total_pages}...")
            page = doc[page_num]

            # Render sang PIL Image
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            import numpy as np
            from PIL import Image
            import io

            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img_np = np.array(img)

            # OCR với PaddleOCR
            try:
                ocr_result = self._ocr.ocr(img_np, cls=self.use_angle_cls)
            except Exception as e:
                logger.error(f"  Loi OCR trang {page_num + 1}: {e}")
                pages.append(OCRPageResult(page_number=page_num + 1, text=""))
                continue

            # Parse kết quả PaddleOCR
            # ocr_result = [[ [box, (text, confidence)], ... ]]
            page_text_lines = []
            page_confs = []

            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    if line and len(line) >= 2:
                        box = line[0]
                        text_conf = line[1]
                        if text_conf and len(text_conf) >= 2:
                            text = text_conf[0]
                            conf = text_conf[1]
                            page_text_lines.append(text)
                            page_confs.append(conf)

            # Ghép các dòng thành đoạn văn
            page_text = self._reconstruct_text(page_text_lines)
            avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0

            pages.append(OCRPageResult(
                page_number=page_num + 1,
                text=page_text,
                confidence=avg_conf,
            ))
            all_confidences.append(avg_conf)
            logger.info(f"    -> {len(page_text)} ky tu | conf={avg_conf:.2f}")

        doc.close()

        full_text = "\n\n".join(p.text for p in pages if p.text)
        full_text = self._post_process(full_text)
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        logger.info(
            f"OCR xong: {file_path.name} | "
            f"{total_pages} trang | "
            f"{len(full_text):,} ky tu | "
            f"confidence={avg_conf:.2f}"
        )

        return OCRResult(
            file_path=str(file_path),
            file_name=file_path.name,
            total_pages=total_pages,
            full_text=full_text,
            pages=pages,
            avg_confidence=avg_conf,
        )

    def _reconstruct_text(self, lines: list[str]) -> str:
        """
        Ghép các dòng text từ OCR thành đoạn văn tự nhiên.
        PaddleOCR trả về từng bbox riêng lẻ, cần ghép lại.
        """
        if not lines:
            return ""
        # Giữ nguyên thứ tự dòng (PaddleOCR đã sort theo top-to-bottom)
        return "\n".join(lines)

    def _post_process(self, text: str) -> str:
        """Hậu xử lý text OCR."""
        import re
        # Giảm dòng trống liên tiếp
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Xóa khoảng trắng cuối dòng
        text = re.sub(r" +\n", "\n", text)
        return text.strip()

    def process_to_file(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
    ) -> Path:
        """
        OCR file PDF và lưu kết quả vào file .txt.

        Returns:
            Path của file .txt output
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = self.process(pdf_path)

        pdf_name = Path(pdf_path).stem
        output_file = output_dir / f"{pdf_name}_paddle_ocr.txt"
        output_file.write_text(result.full_text, encoding="utf-8")

        logger.info(f"Da luu: {output_file}")
        return output_file


# ─── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python paddle_ocr_processor.py <path_to_pdf>")
        sys.exit(1)

    processor = PaddleOCRProcessor(lang="vi", dpi=200)
    result = processor.process(sys.argv[1])

    print(f"\n{'='*60}")
    print(f"File: {result.file_name}")
    print(f"Trang: {result.total_pages}")
    print(f"Ky tu: {len(result.full_text):,}")
    print(f"Confidence TB: {result.avg_confidence:.2%}")
    print(f"\n--- 800 ky tu dau ---")
    print(result.full_text[:800])
