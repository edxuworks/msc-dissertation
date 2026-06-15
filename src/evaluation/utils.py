"""Shared utilities for the evaluation pipeline."""

from pathlib import Path


def resolve_pdf_stem(gold_file_name: str, preprocessed_dir: Path) -> str | None:
    """
    Map a gold standard file_name to the JSON sidecar stem in preprocessed_dir.

    Handles known mismatches between Firstplanit's file_name field and actual PDF filenames:
      1. Exact stem match
      2. Colon stripped  (e.g. "EPD-IES-0003985:002.pdf" → "EPD-IES-0003985002")
      3. Leading zeros stripped (e.g. "000438.pdf" → "438")

    Returns the stem string if a sidecar is found, None otherwise.
    """
    preprocessed_dir = Path(preprocessed_dir)

    # Derive stem from gold file_name — use Path to handle path separators safely
    gold_stem = Path(gold_file_name).stem

    candidates = [
        gold_stem,
        gold_stem.replace(":", ""),
        gold_stem.lstrip("0") or "0",
    ]

    for candidate in candidates:
        if (preprocessed_dir / f"{candidate}.json").exists():
            return candidate

    return None
