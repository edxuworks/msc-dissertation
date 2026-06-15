"""
Docling preprocessing pipeline: PDF → structured text + table markdown.

Patterns inherited from scripts/corpus_audit.py:
  - do_ocr=False: all corpus PDFs confirmed native (corpus audit, 2026-06-14)
  - signal.SIGALRM 120s per-document timeout
  - Resumable: JSON sidecar per PDF in output_dir; skip if already present

Output per PDF (data/preprocessed/<stem>.json):
  {
    "filename": str,
    "success": bool,
    "text": str,        # full Docling markdown export
    "tables": [{"index": int, "markdown": str}, ...],
    "page_count": int,
    "processing_time_s": float,
    "error": str        # empty string on success
  }
"""

import json
import time
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EPD_DIR = PROJECT_ROOT / "EPDs"
OUTPUT_DIR = PROJECT_ROOT / "data" / "preprocessed"
DOCLING_TIMEOUT = 120


@contextmanager
def time_limit(seconds: int):
    def _handler(signum, frame):
        raise TimeoutError(f"Docling exceeded {seconds}s timeout")
    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def make_converter(do_ocr: bool = False) -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = do_ocr
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def process_pdf(pdf_path: Path, converter: DocumentConverter, timeout: int = DOCLING_TIMEOUT) -> dict:
    result = {
        "filename": pdf_path.name,
        "success": False,
        "text": "",
        "tables": [],
        "page_count": 0,
        "processing_time_s": 0.0,
        "error": "",
    }
    t0 = time.time()
    try:
        with time_limit(timeout):
            conv = converter.convert(str(pdf_path))
        doc = conv.document

        result["text"] = doc.export_to_markdown()
        result["page_count"] = len(doc.pages) if hasattr(doc, "pages") else 0

        tables = []
        for idx, tbl in enumerate(doc.tables):
            try:
                md = tbl.export_to_markdown(doc)
            except Exception:
                try:
                    md = tbl.export_to_markdown()
                except Exception:
                    md = ""
            tables.append({"index": idx, "markdown": md})

        result["tables"] = tables
        result["success"] = True

    except TimeoutError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)[:300]

    result["processing_time_s"] = round(time.time() - t0, 1)
    return result


def run_pipeline(
    pdf_dir: Path = EPD_DIR,
    output_dir: Path = OUTPUT_DIR,
    do_ocr: bool = False,
    timeout: int = DOCLING_TIMEOUT,
    pdf_filter: Optional[list[str]] = None,
) -> list[dict]:
    """
    Process all PDFs in pdf_dir, writing one JSON sidecar per PDF to output_dir.
    Skips PDFs whose sidecar already exists (resumable).
    Returns list of result dicts for completed PDFs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in pdf_dir.iterdir() if p.suffix.lower() == ".pdf" and p.is_file())
    if pdf_filter:
        pdfs = [p for p in pdfs if p.name in pdf_filter]

    logger.info(f"Found {len(pdfs)} PDFs in {pdf_dir}")
    converter = make_converter(do_ocr=do_ocr)

    results = []
    for pdf_path in pdfs:
        out_path = output_dir / (pdf_path.stem + ".json")
        if out_path.exists():
            logger.debug(f"Skip (sidecar exists): {pdf_path.name}")
            continue

        logger.info(f"Processing: {pdf_path.name}")
        result = process_pdf(pdf_path, converter, timeout=timeout)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        status = "OK" if result["success"] else f"FAIL ({result['error'][:60]})"
        logger.info(
            f"  {pdf_path.name}: {status} | "
            f"{result['processing_time_s']}s | "
            f"{len(result['tables'])} tables | "
            f"{len(result['text'])} chars"
        )
        results.append(result)

    n_ok = sum(1 for r in results if r["success"])
    n_fail = len(results) - n_ok
    logger.info(f"Done — {n_ok} succeeded, {n_fail} failed (of {len(results)} processed this run)")
    return results


if __name__ == "__main__":
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def main(
        pdf_dir: Path = typer.Argument(EPD_DIR, help="Directory of EPD PDFs to preprocess"),
        output_dir: Path = typer.Argument(OUTPUT_DIR, help="Directory for JSON sidecar output"),
        do_ocr: bool = typer.Option(False, "--do-ocr", help="Enable OCR (not needed for native PDFs)"),
        timeout: int = typer.Option(DOCLING_TIMEOUT, "--timeout", help="Per-document timeout in seconds"),
        only: Optional[str] = typer.Option(None, "--only", help="Comma-separated PDF filenames to process (skip others)"),
    ):
        """Preprocess EPD PDFs with Docling: extract full text and table markdown."""
        pdf_filter = [f.strip() for f in only.split(",")] if only else None
        run_pipeline(pdf_dir=pdf_dir, output_dir=output_dir, do_ocr=do_ocr, timeout=timeout, pdf_filter=pdf_filter)

    app()
