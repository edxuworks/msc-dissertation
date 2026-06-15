"""
Create epd_gold_clean.json, epd_gold_quarantine.json, and gold_standard_manifest.csv
from the normalised ground truth (epd_gold_normalised.json).

Split rationale (from audit session, 2026-06-14; updated 2026-06-15):
  CLEAN        indices 0,2-8, 17-18,21-22, 30,32,34-35, 40-41  → 18 records
  UNVERIFIED   indices 1, 19, 20, 26, 27, 31, 33, 39, 42       → 9 records (quarantine, promotable)
  CONTAMINATED indices 9-16   → BRE/Altro prompt-leak (prompt instruction text as JSON keys)
  DUPLICATE    indices 23-25  → redundant second passes of records 20-22 (UL Interface)
  DUPLICATE    indices 28-29  → Van Gogh duplicates of record 27
  EMPTY        indices 36-38  → Sherwin-Williams/NSF ISO 21930 (non-EN-15804 stage notation)
"""

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT = PROJECT_ROOT / "data" / "gold_standard" / "epd_gold_normalised.json"
OUT_DIR = PROJECT_ROOT / "data" / "gold_standard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LCA_INDICATORS = [
    "GWP-TOTAL", "GWP-FOSSIL", "GWP-BIOGENIC",
    "FRESH WATER", "ACIDIFICATION", "EUTROFICATION",
    "PERT", "PENRT", "PERE", "PERM", "PENRE", "PENRM",
]

# Keys inside each indicator dict that are annotation fields, not stage values
BENIGN_SUBKEYS = {"Description", "Indicator Name"}

CLEAN_INDICES = set(
    [0] + list(range(2, 9)) +        # 0,2-8:  8 records  (1 moved to UNVERIFIED)
    [17, 18, 21, 22] +               # 17-18,21-22: 4 records  (19,20 moved to UNVERIFIED)
    [30, 32, 34, 35] +               # 30,32,34-35: 4 records  (31,33 moved to UNVERIFIED)
    [40, 41]                         # 40-41: 2 records  (26,27,39,42 moved to UNVERIFIED)
)  # total: 18

QUARANTINE_REASONS = {}
for i in [1, 19, 20, 26, 27, 31, 33, 39, 42]:
    QUARANTINE_REASONS[i] = "UNVERIFIED: record flagged for PDF cross-check; excluded from working set pending verification (decision 2026-06-15)"
for i in range(9, 17):
    QUARANTINE_REASONS[i] = "CONTAMINATED: BRE/Altro EPDs — Gemini prompt instruction text leaked as JSON keys; schema entirely non-compliant"
for i in [23, 24, 25]:
    QUARANTINE_REASONS[i] = "DUPLICATE: redundant second extraction pass of records 20-22 (UL Interface products)"
for i in [28, 29]:
    QUARANTINE_REASONS[i] = "DUPLICATE: Van Gogh Luxury Vinyl exact duplicates of record 27 (SCS-EPD-06707)"
for i in [36, 37, 38]:
    QUARANTINE_REASONS[i] = "EMPTY: Sherwin-Williams/NSF EPDs use ISO 21930 stage notation (Stage 1-4), not EN 15804 modules — LCA matrix entirely N/A in canonical schema"


def strip_benign_subkeys(record: dict) -> dict:
    """Remove annotation-only sub-keys from inside LCA indicator dicts."""
    out = {}
    for k, v in record.items():
        if k in LCA_INDICATORS and isinstance(v, dict):
            out[k] = {sk: sv for sk, sv in v.items() if sk not in BENIGN_SUBKEYS}
        else:
            out[k] = v
    return out


def main():
    with open(INPUT) as f:
        records = json.load(f)

    assert len(records) == 43, f"Expected 43 records, got {len(records)}"

    clean = []
    quarantine = []
    manifest_rows = []

    for orig_idx, rec in enumerate(records):
        fn = rec.get("file_name", "")
        prod = rec.get("Product Name", "")
        gwp = rec.get("GWP-TOTAL", {})
        gwp_a1a3 = gwp.get("A1-A3", "N/A") if isinstance(gwp, dict) else "N/A"

        if orig_idx in CLEAN_INDICES:
            r = strip_benign_subkeys(rec)
            r["_orig_index"] = orig_idx
            clean.append(r)
            manifest_rows.append({
                "orig_idx": orig_idx, "bucket": "CLEAN",
                "file_name": fn, "product_name": prod,
                "gwp_a1a3": gwp_a1a3, "notes": "",
            })
        else:
            reason = QUARANTINE_REASONS.get(orig_idx, "UNKNOWN")
            r = dict(rec)
            r["_orig_index"] = orig_idx
            r["_quarantine_reason"] = reason
            quarantine.append(r)
            manifest_rows.append({
                "orig_idx": orig_idx, "bucket": "QUARANTINE",
                "file_name": fn, "product_name": prod,
                "gwp_a1a3": "N/A", "notes": reason.split(":")[0],
            })

    assert len(clean) == 18, f"Expected 18 clean records, got {len(clean)}"
    assert len(quarantine) == 25, f"Expected 25 quarantine records, got {len(quarantine)}"
    assert len(manifest_rows) == 43

    clean_path = OUT_DIR / "epd_gold_clean.json"
    with open(clean_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

    quarantine_path = OUT_DIR / "epd_gold_quarantine.json"
    with open(quarantine_path, "w", encoding="utf-8") as f:
        json.dump(quarantine, f, indent=2, ensure_ascii=False)

    manifest_path = OUT_DIR / "gold_standard_manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["orig_idx", "bucket", "file_name", "product_name", "gwp_a1a3", "notes"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Clean:      {len(clean):>3} records → {clean_path}")
    print(f"Quarantine: {len(quarantine):>3} records → {quarantine_path}")
    print(f"Manifest:   {len(manifest_rows):>3} rows   → {manifest_path}")
    print()

    q_cats = {}
    for r in quarantine:
        cat = r["_quarantine_reason"].split(":")[0]
        q_cats[cat] = q_cats.get(cat, 0) + 1
    print("Quarantine breakdown:")
    for cat, n in q_cats.items():
        print(f"  {cat}: {n}")



if __name__ == "__main__":
    main()
