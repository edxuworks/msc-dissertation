"""
Normalise epd_extraction.json to a canonical schema.

The JSON contains three field-naming conventions across 43 records.
The majority (34-35 records) is treated as canonical.
Minority fields are remapped to their canonical equivalents.

Output: data/gold_standard/epd_gold_normalised.json
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT  = PROJECT_ROOT / "epd_extraction.json"
OUTPUT = PROJECT_ROOT / "data" / "gold_standard" / "epd_gold_normalised.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# ── Rename maps ───────────────────────────────────────────────────────────────
# Each entry: old_name → canonical_name
# Only covers fields that diverge; fields already in canonical form are untouched.

# 1-record EPD International schema → canonical
EPD_INTL_MAP = {
    "Embodied Carbon (GWP Total)":          "GWP-TOTAL",
    "Embodied Carbon (GWP Fossil)":         "GWP-FOSSIL",
    "Embodied Carbon (GWP Biogenic)":       "GWP-BIOGENIC",
    "Embodied Energy (PERT - Renewable)":   "PERT",
    "Embodied Energy (PENRT - Non-Renewable)": "PENRT",
    "Freshwater Use (FW)":                  "FRESH WATER",
    "Eutrophication Potential (EP)":        "EUTROFICATION",
    "Acidification Potential (AP)":         "ACIDIFICATION",
    # metadata
    "Name of products":                     "Product Name",
    "Epd product name":                     "Product Name",
    "Expiry Date yyyy-mm-dd":               "Expiry Date",
    "Durable Data Value: Life Expectancy":  "Durbale Data Value: Life Expectancy",
    "Durable Data Value: Warranty":         "Durbale Data Value: Warranty",
    "Acoustic (Impact) Value":              "Acoustic (Impact) Value (in dB)",
    "Acoustic (Airborne) Value":            "Acoustic (Airborne) Value (in dB)",
}

# 8-record BRE schema → canonical
# NOTE: BRE records store LCA indicators as flat A1-A3 values, not nested dicts.
# We remap field names but leave values as-is (they're near-empty anyway).
BRE_MAP = {
    "Name of Product":                      "Product Name",
    "EPD Number":                           "EPD Document No",
    "EPD Program Operator":                 "EPD Certification Body /Publisher/Program operator",
    "Verification Method":                  "EPD Verification Method",
    "Functional Unit/Declared Unit":        "Functional Unit",
    "EPD Type":                             "EPD Certificated Type",
    "GWP Total / Global Warming":           "GWP-TOTAL",
    "GWP-fossil":                           "GWP-FOSSIL",
    "GWP Biogenic":                         "GWP-BIOGENIC",
    "Net use of fresh water(FW)":           "FRESH WATER",
    "Eutrophication Potential(EP)":         "EUTROFICATION",
    "Acidification Potential(AP)":          "ACIDIFICATION",
    "Fire Class":                           "Fire class",
}


def detect_schema(record: dict) -> str:
    """Identify which schema variant a record uses."""
    if "Embodied Carbon (GWP Total)" in record:
        return "epd_intl"
    if "GWP Total / Global Warming" in record or "Name of Product" in record:
        return "bre"
    return "canonical"


def normalise(record: dict, rename_map: dict) -> dict:
    """Apply a rename map to a record, merging into existing canonical keys if needed."""
    out = {}
    for k, v in record.items():
        canonical_key = rename_map.get(k, k)
        # If canonical key already exists (shouldn't happen but be safe), skip duplicate
        if canonical_key not in out:
            out[canonical_key] = v
    return out


def main():
    with open(INPUT) as f:
        records = json.load(f)

    normalised = []
    counts = {"canonical": 0, "epd_intl": 0, "bre": 0}

    for r in records:
        schema = detect_schema(r)
        counts[schema] += 1
        if schema == "epd_intl":
            r = normalise(r, EPD_INTL_MAP)
        elif schema == "bre":
            r = normalise(r, BRE_MAP)
        normalised.append(r)

    with open(OUTPUT, "w") as f:
        json.dump(normalised, f, indent=2)

    print(f"Normalised {len(normalised)} records → {OUTPUT}")
    print(f"  Schema variants found: {counts}")
    print(f"\nVerification — unique field counts across normalised records:")

    from collections import Counter
    field_counts = Counter(k for r in normalised for k in r)
    # Show the key LCA fields
    lca_fields = ["GWP-TOTAL","GWP-FOSSIL","GWP-BIOGENIC","FRESH WATER",
                  "ACIDIFICATION","EUTROFICATION","PERT","PENRT","PERE","PERM","PENRE","PENRM"]
    for f in lca_fields:
        print(f"  {f}: {field_counts[f]}/43")


if __name__ == "__main__":
    main()
