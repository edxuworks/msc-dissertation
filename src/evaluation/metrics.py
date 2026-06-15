"""Primitive field-level matching functions for EPD extraction evaluation."""

import unicodedata

SKIP_FIELDS = {"_orig_index", "file_name", "_verify", "_quarantine_reason"}

LCA_INDICATORS = {
    "GWP-TOTAL", "GWP-FOSSIL", "GWP-BIOGENIC",
    "FRESH WATER", "ACIDIFICATION", "EUTROFICATION",
    "PERT", "PENRT", "PERE", "PERM", "PENRE", "PENRM",
}

# Firstplanit-custom stages not in EN 15804 — always N/A, excluded from scoring
LCA_SKIP_STAGES = {"D1", "D2"}

LIST_FIELDS = {"Standard List", "Tags List"}


def parse_numeric(s: str) -> float | None:
    """Parse a string value to float; return None for N/A or unparseable input."""
    if not isinstance(s, str) or s.strip().upper() == "N/A" or s.strip() == "":
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None


def normalise_string(s: str) -> str:
    """Lowercase, strip, collapse whitespace, NFKD-normalise (handles CO₂→CO2, m³→m3)."""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())


def match_numeric(pred: str, gold: str, rtol: float = 0.01, atol: float = 1e-4) -> bool:
    """
    Tolerance-based numeric match: |pred - gold| <= atol + rtol * |gold|.
    Falls back to exact string match when either value is N/A (both must be N/A to match).
    """
    g = parse_numeric(gold)
    p = parse_numeric(pred)
    if g is None or p is None:
        # At least one is N/A — require both to be N/A
        return normalise_string(str(pred)) == normalise_string(str(gold))
    return abs(p - g) <= atol + rtol * abs(g)


def match_string(pred: str, gold: str) -> bool:
    """Exact match after unicode normalisation and case folding."""
    return normalise_string(str(pred)) == normalise_string(str(gold))


def match_list(pred: object, gold: list) -> tuple[float, float, float]:
    """
    Set-based precision, recall, F1 for list fields (order-insensitive).
    Returns (precision, recall, f1).
    """
    if not isinstance(pred, list):
        pred = [pred] if pred and str(pred).strip().upper() != "N/A" else []
    pred_set = {normalise_string(str(x)) for x in pred}
    gold_set = {normalise_string(str(x)) for x in gold}
    if not gold_set and not pred_set:
        return 1.0, 1.0, 1.0
    tp = len(pred_set & gold_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gold_set) if gold_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return precision, recall, f1
