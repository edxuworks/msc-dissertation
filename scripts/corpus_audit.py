"""
Corpus Audit Script
===================
Runs every EPD PDF through PyMuPDF + Docling to characterise the corpus
across the complexity dimensions needed for gold standard stratification.

Output: data/corpus_audit/audit.csv

Complexity tier rules:
  Hard   — scanned OR docling failed OR non-English OR page_count > 15
  Medium — page_count > 8 OR table_count > 4 OR non-English (if readable)
  Simple — everything else
"""

import json
import csv
import time
import signal
from pathlib import Path
from contextlib import contextmanager

import fitz  # pymupdf
from langdetect import detect, LangDetectException
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from tqdm import tqdm
from loguru import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EPD_DIR      = PROJECT_ROOT / "EPDs"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "corpus_audit"
GOLD_JSON    = PROJECT_ROOT / "epd_extraction.json"
OUTPUT_CSV   = OUTPUT_DIR / "audit.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Minimum characters per page to consider a PDF native (not scanned)
SCAN_CHAR_THRESHOLD = 80

# Per-document Docling timeout in seconds (skip if exceeded)
DOCLING_TIMEOUT = 120


@contextmanager
def time_limit(seconds):
    def handler(signum, frame):
        raise TimeoutError(f"Docling exceeded {seconds}s timeout")
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_gold_filenames(gold_path: Path) -> set[str]:
    """Return the set of file_name values from the ground truth JSON."""
    with open(gold_path) as f:
        records = json.load(f)
    return {r.get("file_name", "") for r in records if r.get("file_name")}


def normalise_name(name: str) -> str:
    """Strip punctuation variants so fuzzy filename matching works."""
    return name.replace(":", "").replace("/", "").replace(" ", "").lower()


def match_to_gold(pdf_name: str, gold_names: set[str]) -> str:
    """Try to find this PDF's name in the gold standard set."""
    if pdf_name in gold_names:
        return pdf_name
    norm_pdf = normalise_name(pdf_name)
    for gn in gold_names:
        if normalise_name(gn) == norm_pdf:
            return gn
    return ""


def check_tagged(pdf_path: Path) -> bool:
    """Return True if the PDF has a MarkInfo entry (tagged/accessible PDF)."""
    try:
        doc = fitz.open(str(pdf_path))
        catalog_xref = doc.pdf_catalog()
        catalog_str  = doc.xref_object(catalog_xref)
        doc.close()
        return "/MarkInfo" in catalog_str
    except Exception:
        return False


def pymupdf_audit(pdf_path: Path) -> dict:
    """Extract basic properties using PyMuPDF (fast, no ML)."""
    result = {
        "page_count": 0,
        "text_length": 0,
        "chars_per_page": 0.0,
        "native_vs_scanned": "unknown",
        "tagged": False,
        "language": "unknown",
        "pymupdf_error": "",
    }
    try:
        doc = fitz.open(str(pdf_path))
        result["page_count"] = len(doc)
        result["tagged"]     = check_tagged(pdf_path)

        full_text = "".join(page.get_text() for page in doc)
        doc.close()

        result["text_length"]    = len(full_text)
        result["chars_per_page"] = len(full_text) / max(result["page_count"], 1)

        # Native vs scanned: if average chars per page is very low, assume scanned
        result["native_vs_scanned"] = (
            "native" if result["chars_per_page"] >= SCAN_CHAR_THRESHOLD else "scanned"
        )

        # Language detection on first 2000 chars of meaningful text
        sample = full_text[:2000].strip()
        if len(sample) > 50:
            try:
                result["language"] = detect(sample)
            except LangDetectException:
                result["language"] = "unknown"
        else:
            result["language"] = "insufficient_text"

    except Exception as e:
        result["pymupdf_error"] = str(e)

    return result


def docling_audit(pdf_path: Path, converter: DocumentConverter) -> dict:
    """Extract table and structure information using Docling."""
    result = {
        "docling_success": False,
        "table_count": 0,
        "docling_table_text_len": 0,
        "docling_text_len": 0,
        "docling_error": "",
        "docling_seconds": 0.0,
    }
    try:
        t0 = time.time()
        with time_limit(DOCLING_TIMEOUT):
            conv_result = converter.convert(str(pdf_path))
        result["docling_seconds"] = round(time.time() - t0, 1)

        doc = conv_result.document
        result["docling_success"] = True

        # Full markdown export length
        md_text = doc.export_to_markdown()
        result["docling_text_len"] = len(md_text)

        # Tables — pass doc to avoid deprecation warning
        tables = doc.tables
        result["table_count"] = len(tables)

        table_text = ""
        for tbl in tables:
            try:
                table_text += tbl.export_to_markdown(doc)
            except Exception:
                try:
                    table_text += tbl.export_to_markdown()
                except Exception:
                    pass
        result["docling_table_text_len"] = len(table_text)

    except TimeoutError as e:
        result["docling_error"] = str(e)
        result["docling_seconds"] = DOCLING_TIMEOUT
    except Exception as e:
        result["docling_error"] = str(e)[:200]

    return result


def assign_complexity_tier(row: dict) -> str:
    """
    Rule-based complexity tier assignment.
      Hard   — scanned, or Docling failed, or non-English, or >15 pages
      Medium — >8 pages, or >4 tables, or non-English but readable
      Simple — short native English document with clean table extraction
    """
    is_scanned   = row["native_vs_scanned"] == "scanned"
    docling_fail = not row["docling_success"]
    non_english  = row["language"] not in ("en", "unknown", "insufficient_text")
    many_pages   = row["page_count"] > 15
    med_pages    = row["page_count"] > 8
    many_tables  = row["table_count"] > 4

    if is_scanned or docling_fail or many_pages:
        return "Hard"
    if non_english:
        return "Hard"
    if med_pages or many_tables:
        return "Medium"
    return "Simple"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info(f"Scanning EPDs in: {EPD_DIR}")

    # Collect unique PDFs from the top-level EPDs directory only
    all_pdfs = sorted(
        p for p in EPD_DIR.iterdir()
        if p.suffix.lower() == ".pdf" and p.is_file()
    )
    logger.info(f"Found {len(all_pdfs)} PDFs")

    gold_names = load_gold_filenames(GOLD_JSON)
    logger.info(f"Gold standard has {len(gold_names)} file references")

    # Initialise Docling with OCR disabled — PDFs are native so OCR is wasteful
    # and causes RapidOCR to spin on every embedded image (~10x slower)
    logger.info("Initialising Docling converter (OCR disabled for native PDFs)...")
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    logger.info("Docling ready")

    fieldnames = [
        "filename",
        "page_count",
        "text_length",
        "chars_per_page",
        "native_vs_scanned",
        "tagged",
        "language",
        "docling_success",
        "table_count",
        "docling_table_text_len",
        "docling_text_len",
        "docling_seconds",
        "complexity_tier",
        "gold_standard_match",
        "pymupdf_error",
        "docling_error",
    ]

    # Load already-completed rows so we can resume after a kill
    completed = set()
    rows = []
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                completed.add(r["filename"])
        logger.info(f"Resuming — {len(completed)} PDFs already done")

    remaining = [p for p in all_pdfs if p.name not in completed]

    # Open CSV in append mode; write header only if starting fresh
    write_header = not OUTPUT_CSV.exists() or len(completed) == 0
    csv_file = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    try:
        for pdf_path in tqdm(remaining, desc="Auditing PDFs"):
            logger.info(f"Processing: {pdf_path.name}")
            row = {"filename": pdf_path.name}

            # PyMuPDF pass (fast)
            row.update(pymupdf_audit(pdf_path))

            # Docling pass (ML table detection, OCR disabled)
            row.update(docling_audit(pdf_path, converter))

            # Derived fields
            row["complexity_tier"]     = assign_complexity_tier(row)
            row["gold_standard_match"] = match_to_gold(pdf_path.name, gold_names)

            rows.append(row)

            # Write immediately so progress survives a kill
            writer.writerow(row)
            csv_file.flush()

            logger.info(
                f"  {pdf_path.name}: {row['native_vs_scanned']} | "
                f"tagged={row['tagged']} | lang={row['language']} | "
                f"pages={row['page_count']} | tables={row['table_count']} | "
                f"tier={row['complexity_tier']} | "
                f"docling={'OK' if row['docling_success'] else 'FAIL'} "
                f"({row['docling_seconds']}s)"
            )
    finally:
        csv_file.close()

    logger.success(f"Audit complete. Results written to: {OUTPUT_CSV}")

    # Print summary statistics
    n_total    = len(rows)
    n_scanned  = sum(1 for r in rows if r["native_vs_scanned"] == "scanned")
    n_tagged   = sum(1 for r in rows if str(r["tagged"]) == "True")
    n_non_en   = sum(1 for r in rows if r["language"] not in ("en", "unknown", "insufficient_text"))
    n_docling_fail = sum(1 for r in rows if str(r["docling_success"]) != "True")
    tiers      = {t: sum(1 for r in rows if r["complexity_tier"] == t) for t in ("Simple", "Medium", "Hard")}

    print("\n" + "="*60)
    print(f"CORPUS AUDIT SUMMARY  ({n_total} PDFs)")
    print("="*60)
    print(f"  Native:          {n_total - n_scanned}/{n_total}")
    print(f"  Scanned:         {n_scanned}/{n_total}")
    print(f"  Tagged:          {n_tagged}/{n_total}")
    print(f"  Non-English:     {n_non_en}/{n_total}")
    print(f"  Docling failed:  {n_docling_fail}/{n_total}")
    print(f"  Complexity tiers: Simple={tiers['Simple']}  Medium={tiers['Medium']}  Hard={tiers['Hard']}")
    print("="*60)
    print(f"\nFull results: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
