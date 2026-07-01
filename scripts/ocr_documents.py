"""
TerraLegalAI — Script OCR Tài Liệu (PaddleOCR)
Chạy PaddleOCR trên tất cả PDF scan và lưu kết quả thành .txt

Cách dùng:
  python scripts/ocr_documents.py --all         # OCR tất cả
  python scripts/ocr_documents.py --file path   # OCR một file
  python scripts/ocr_documents.py --compare     # So sánh Tesseract vs Paddle
"""
import sys
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OCR_OUTPUT_DIR = Path("data/processed/ocr_text")

# Danh sách PDF cần OCR
PDF_FILES = [
    {
        "file": "data/raw/nhom2_quyet_dinh/QĐ 1085. Ban hành bộ TTHC.pdf",
        "source_name": "QĐ 1085/QĐ-UBND",
        "group_type": "quyet_dinh",
        "procedure_type": "chuyen_nhuong",
    },
    {
        "file": "data/raw/nhom2_quyet_dinh/QĐ 1467.Quy trình nội bo_n.pdf",
        "source_name": "QĐ 1467/QĐ-UBND",
        "group_type": "quyet_dinh",
        "procedure_type": "all",
    },
]


def ocr_with_paddle(pdf_path: Path, output_dir: Path, dpi: int = 200) -> Path | None:
    """OCR bằng PaddleOCR — chất lượng tiếng Việt tốt nhất."""
    try:
        from backend.app.document_processing.paddle_ocr_processor import PaddleOCRProcessor

        processor = PaddleOCRProcessor(lang="vi", dpi=dpi, use_gpu=False)
        output_file = processor.process_to_file(pdf_path, output_dir)
        return output_file

    except ImportError as e:
        logger.error(f"PaddleOCR chua san sang: {e}")
        logger.info("Fallback sang Tesseract...")
        return ocr_with_tesseract_cli(pdf_path, output_dir, dpi=300)
    except Exception as e:
        logger.error(f"Loi PaddleOCR '{pdf_path.name}': {e}", exc_info=True)
        return None


def ocr_with_tesseract_cli(
    pdf_path: Path, output_dir: Path, dpi: int = 300, lang: str = "vie+eng"
) -> Path | None:
    """Fallback: OCR bằng Tesseract CLI."""
    import subprocess
    import fitz

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(pdf_path))
        tmp_dir = output_dir / "tmp_pages"
        tmp_dir.mkdir(exist_ok=True)

        all_text = []
        for page_num in range(len(doc)):
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = doc[page_num].get_pixmap(matrix=mat, alpha=False)
            tmp_png = tmp_dir / f"page_{page_num:04d}.png"
            pix.save(str(tmp_png))

            tmp_base = tmp_dir / f"page_{page_num:04d}"
            subprocess.run(
                ["tesseract", str(tmp_png), str(tmp_base), "-l", lang,
                 "--oem", "3", "--psm", "3", "txt"],
                capture_output=True,
            )
            txt = Path(str(tmp_base) + ".txt")
            if txt.exists():
                all_text.append(txt.read_text(encoding="utf-8", errors="ignore").strip())
                txt.unlink()
            tmp_png.unlink(missing_ok=True)

        doc.close()
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

        full_text = "\n\n".join(all_text)
        output_file = output_dir / (pdf_path.stem + "_tesseract_ocr.txt")
        output_file.write_text(full_text, encoding="utf-8")
        logger.info(f"Tesseract saved: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="TerraLegalAI - OCR PDF voi PaddleOCR"
    )
    parser.add_argument("--file", help="Duong dan file PDF can OCR")
    parser.add_argument("--all", action="store_true", help="OCR tat ca PDF trong manifest")
    parser.add_argument("--dpi", type=int, default=200, help="DPI render (default=200)")
    parser.add_argument(
        "--engine",
        choices=["paddle", "tesseract"],
        default="paddle",
        help="OCR engine (default=paddle)",
    )

    args = parser.parse_args()
    output_dir = OCR_OUTPUT_DIR

    ocr_fn = ocr_with_paddle if args.engine == "paddle" else (
        lambda p, o, d: ocr_with_tesseract_cli(p, o, dpi=300)
    )

    if args.file:
        pdf_path = Path(args.file)
        result = ocr_fn(pdf_path, output_dir, args.dpi)
        if result:
            logger.info(f"Xong: {result}")
            # Preview
            text = result.read_text(encoding="utf-8")
            print(f"\n--- Preview (600 chars) ---\n{text[:600]}")
        return

    if args.all:
        logger.info(f"OCR {len(PDF_FILES)} files voi {args.engine.upper()}...")
        success = 0
        for doc_info in PDF_FILES:
            pdf_path = Path(doc_info["file"])
            if not pdf_path.exists():
                logger.warning(f"File khong ton tai: {pdf_path}")
                continue
            result = ocr_fn(pdf_path, output_dir, args.dpi)
            if result:
                success += 1
        logger.info(f"Hoan thanh: {success}/{len(PDF_FILES)}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
