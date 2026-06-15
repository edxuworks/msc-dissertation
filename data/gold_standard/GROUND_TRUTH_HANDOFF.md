# Ground Truth Handoff Brief
## EPD Gold Standard — Audit Complete 2026-06-14

This document is the authoritative record of what was done to the ground truth data and why.
Read this at the start of any session that touches evaluation or the gold standard.

---

## What is the working ground truth?

**`data/gold_standard/epd_gold_clean.json`** — 18 records.

Derived from `data/gold_standard/epd_gold_normalised.json` (43 records) by:
1. Removing 16 records that are contaminated, duplicated, or empty (see below)
2. Stripping two benign annotation sub-keys (`Description`, `Indicator Name`) from inside LCA indicator dicts — these were Firstplanit's internal schema comments, not extraction values; their removal is loss-free

Do NOT use `epd_extraction.json` (the original 43-record file) as ground truth — it has inconsistent field names, contaminated records, and duplicates.

Do NOT use the schema from `epd_sample.ipynb` — it is an older simplified version.

---

## Canonical schema

Each clean record has:

**Flat metadata fields** (all strings or "N/A"):
`No of products`, `Product Name`, `Product Type`, `Product Type Details`, `Functional Unit`, `Functional Unit Value`, `Functional Unit Type`, `EPD Document No`, `Company or Repository Name`, `Issue Date`, `Expiry Date`, `EPD Certification Body /Publisher/Program operator`, `EPD Verification Method`, `EPD Certificated Type`, `LCIA Methodology & Version Number`, `Life Cycle Scope Description`, `Building Component`, `LCA Standard`, `file_name` ...and ~60 more flat fields.

**12 nested LCA indicator objects** — each a dict keyed by lifecycle stage:
```
GWP-TOTAL, GWP-FOSSIL, GWP-BIOGENIC,
FRESH WATER, ACIDIFICATION, EUTROFICATION,
PERT, PENRT, PERE, PERM, PENRE, PENRM
```

Each indicator dict has these keys (values are numeric strings or "N/A"):
```
A1, A2, A3, A1-A3,
A4, A5, A4-A5,
B1, B2, B3, B4, B5, B6, B7, B1-B7,
C1, C2, C3, C4, C1-C4,
D1, D2, D,
Unit
```

`D1` and `D2` are Firstplanit-custom fields (not in EN 15804); they are always "N/A" in all records.

**Additional audit fields added by `create_gold_standard.py`:**
- `_orig_index` — original index in the 43-record normalised set (0-based)

---

## What was cut and why

### CONTAMINATED (8 records, orig indices 9–16)
BRE Global / Altro EPDs (`000252.pdf`, `000255.pdf`, `000260.pdf`, `000263.pdf`, `000338.pdf` ×2, `000393.pdf`, `000601.pdf`).

Root cause: the Gemini extraction prompt instructions leaked directly into the JSON keys. Example contaminated key:
```
" Total use of non renewable primary energy resources(PENRT) whose symbol is PENRT and get the all the stage value following the given format"
```
These records have zero valid LCA data in the canonical schema. Additionally, BRE EPDs use EN 15804+A1:2013 (older standard), which has different indicator names and AP in kg SO2 (not mol H⁺) — even a correct extraction would require a schema translation step.

### EMPTY / NEAR-EMPTY (3 records, orig indices 36–38)
Sherwin-Williams / NSF EPDs: `EPD10557`, `EPD10558`, `EPD10567`.

Root cause: these EPDs conform to ISO 21930, not EN 15804. ISO 21930 uses Stage 1–4 notation instead of A1/A2/A3 modules. The extractor returned all N/A in the canonical EN 15804 schema because no stage labels matched. The underlying data may be valid, but it requires a separate ISO 21930 schema to interpret.

### DUPLICATE (5 records, orig indices 23–25 and 28–29)
- **23–25**: Second extraction passes of records 20–22 (UL Environment Interface carpet products). Exact duplicates with slight non-determinism in some fields — evidence that the production pipeline has been run multiple times on the same PDFs.
- **28–29**: Exact duplicates of record 27 (Van Gogh Luxury Vinyl, SCS-EPD-06707). Record 27 is itself one of four products from that multi-product EPD.

---

## UNVERIFIED records (moved to quarantine 2026-06-15)

9 records that were previously VERIFY-flagged in the clean set have been moved to `epd_gold_quarantine.json` with `_quarantine_reason = "UNVERIFIED"`. Decision: use only the 18 confident records for evaluation and fine-tuning; promote these once hand-verified.

To promote a record: remove its index from `QUARANTINE_REASONS` and add it to `CLEAN_INDICES` in `scripts/create_gold_standard.py`, then re-run the script.

| orig_idx | File | Why unverified |
|---|---|---|
| 1 | EPD International record | Single EPD-INTL schema record; field names were remapped — check LCA values match PDF |
| 19 | UL Interface (20 oz) | Suspicious numeric values in B-stage fields |
| 20 | UL Interface (24 oz) | UL extraction non-determinism suspected |
| 26 | SCS Knight Tile LVF | Multi-product EPD column split — verify correct column was assigned |
| 27 | SCS Van Gogh LVF | Same multi-product EPD — verify D-module values |
| 31 | MRPI / NEN record | Check unit consistency for GWP indicators |
| 33 | IBU record | German EPD — verify language did not cause extraction artifacts |
| 39 | ReTHiNK / Vescom record | Check B-stage values are plausible for wallcovering |
| 42 | Polish ITB record | Multicert operator — check programme operator field mapping |

---

## Known data issues

1. **EN 15804 version split**: majority of EPDs use +A2:2019 (GWP-fossil/biogenic/luluc separate, AP in mol H⁺). BRE records use +A1:2013 (single GWP, AP in kg SO2). The quarantined BRE records illustrate this; any future BRE EPDs will need standard-version detection.

2. **Multi-product EPD (SCS-EPD-06707)**: Four products extracted from one PDF. Records 26 (Knight Tile) and 27 (Van Gogh) are in the clean set. Records 28–29 are duplicate Van Gogh extractions and are quarantined. Evaluation of multi-product EPDs requires Hungarian algorithm matching (see `SKILLS_AND_REFERENCES.md §6`).

3. **Docling timeouts on two PDFs**: `000623.pdf` (122 pages) and `SCS-EPD-06707.pdf` (72 pages) both exceeded the 120s Docling timeout in the corpus audit. The preprocessing pipeline will need page-range chunking or VLM fallback for these.

4. **UL extraction non-determinism**: The duplicate UL records (23–25 = copies of 20–22) show slight value divergences between runs. This suggests the production pipeline's Gemini extraction is temperature > 0 or the chunking varies between runs.

5. **D1/D2 always N/A**: These fields appear in the schema but are custom Firstplanit additions not in EN 15804. Evaluation should not penalise a model for returning N/A here.

---

## Log updates already applied (2026-06-14)

- `PROJECT_LOG.md`: Session 5 entry added; Current Status updated; Next Steps updated
- `CLAUDE.md`: Key file locations updated; completed tasks updated; immediate next tasks updated; known issues updated

---

## Next pipeline steps (in order)

1. **`src/preprocessing/docling_pipeline.py`** — PDF → structured text + table markdown  
   `do_ocr=False`, 120s SIGALRM timeout, resumable via JSON sidecar  
   *(written 2026-06-14)*

2. **Evaluation harness** — per-field accuracy (exact-match categorical, tolerance-based numeric),  
   F1 disaggregated by field category AND by populated vs N/A,  
   schema validity, unit-outlier check, scientific-notation sanity  
   *(confirm design with Edward before implementing)*

3. **Baseline C** — zero-shot Phi-4-Mini on the 18-record clean working set  
   *(requires local model setup — defer until eval harness complete)*

---

*Generated by `scripts/create_gold_standard.py` audit session, 2026-06-14.*
