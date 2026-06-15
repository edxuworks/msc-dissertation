# GROUND TRUTH HANDOFF — gold standard cleaned (working set)

**Date:** 2026-06-14   **For:** Claude Code session continuation
**Status:** Working set ready for pipeline development. FULL HAND-VERIFICATION STILL PENDING.

---

## TL;DR
The 43-record normalised gold standard has been audited and split:
- `epd_gold_clean.json` — 18 records. **Use this as the working ground truth.**
- `epd_gold_quarantine.json` — 25 records cut (9 UNVERIFIED + 8 contaminated + 5 duplicate + 3 empty). Each record
  carries a `_quarantine_reason` and `_orig_index` field.
- `gold_standard_manifest.csv` — all 43 records: bucket + reason + GWP A1-A3 sanity value.

These 18 are a DEVELOPMENT set, not final truth. The 9 UNVERIFIED records have been moved
to quarantine (decision 2026-06-15) — they can be promoted back once hand-verified against PDFs.

Normalisation was checked and is loss-free: 0 non-trivial values were dropped converting
`epd_extraction.json` -> `epd_gold_normalised.json` (pure key-renaming). Clean file is derived
from the normalised file with benign leaked sub-keys stripped.

---

## What was cut, and why (16 records)

**CONTAMINATED** — BRE/Altro `000xxx` docs. Each has full prompt-instruction sentences leaked in
as JSON keys (e.g. the entire PENRT instruction string) plus a malformed `"C2 "` key:
  - idx  9  000393                 Altro Wood adhesive-free / Altro Canta
  - idx 10  000255                 Altro Classic 25
  - idx 11  000338                 Altro Fortis Titanium PVCu Walls Sheet
  - idx 12  000601                 Altro Screed
  - idx 13  000338                 Altro Whiterock Chameleon
  - idx 14  000263                 Altro Wood Safety Comfort
  - idx 15  000252                 Altro adhesive free products
  - idx 16  000260                 Altro Debolon R300.1, Altro Operetta, 

**EMPTY / NEAR-EMPTY** — Sherwin-Williams products issued under NSF; LCA matrix essentially blank
(likely ISO 21930 stage notation the prompt didn't handle):
  - idx 36  EPD10557               B65W1301 Acrylic Polyurethane
  - idx 37  EPD10558               Duraplate 301W N02301W10 Primer
  - idx 38  EPD10567               M770GLOSS - UD Water-based Finish

**DUPLICATE** — exact copies and redundant second extraction passes:
  - idx 23  4791540199.103.1       CQUEST™ BIO MODULAR CARPET TILE
  - idx 24  4791540199.102.1       CQUEST™ BIO MODULAR CARPET TILE WITH S
  - idx 25  4791540199.101.1       SOUND CHOICE+ MODULAR RESILIENT FLOORI
  - idx 28  SCS-EPD-06707          Van Gogh Luxury Vinyl
  - idx 29  SCS-EPD-06707          Van Gogh Luxury Vinyl

---

## UNVERIFIED records (moved to quarantine 2026-06-15)
These 9 records were previously VERIFY-flagged in the clean set. Decision 2026-06-15: move them
to quarantine (UNVERIFIED) so only the 18 confident records are used for eval/fine-tuning.
They can be promoted once hand-verified — see `data/gold_standard/GROUND_TRUTH_HANDOFF.md` for
instructions and the promotion workflow.
  - idx  1  SCS-EPD-08784          Era 140 & 170
  - idx 19  417/2023               3-LAYER WOODEN FLOORBOARD PUREPLANK
  - idx 20  4791540199.103.1       CQUEST™ BIO MODULAR CARPET TILE
  - idx 26  SCS-EPD-06707          Knight Tile Luxury Vinyl Flooring
  - idx 27  SCS-EPD-06707          Van Gogh Luxury Vinyl
  - idx 31  SCS-EPD-06708          Karndean Looselay Vinyl Flooring
  - idx 33  EPD 20223-...-DE-System  SCHÜCO FWS 50 B X H (German EPD)
  - idx 39  ReTHiNK-65667          Capri Drapery Fabric
  - idx 42  000623                 Aruba Mineral Ceiling Tile

---

## Canonical schema (normalised)
Each record = flat metadata + 12 nested LCA indicator objects.
- Indicators: GWP-TOTAL, GWP-FOSSIL, GWP-BIOGENIC, FRESH WATER, ACIDIFICATION, EUTROFICATION,
  PERT, PENRT, PERE, PERM, PENRE, PENRM
- Each indicator dict: A1, A2, A3, A1-A3, A4, A5, A4-A5, B1..B7, B1-B7, C1..C4, C1-C4, D1, D2, D, Unit
- Benign leaked sub-keys (`Description`, `Indicator Name`) have been STRIPPED from the clean file.
- Provenance fields retained and useful for PDF verification: `LCA Table Page Range`,
  `Material Composition Table Page Range`, `LCA Table Context`.
- N/A is a VALID value across the matrix (~88 of the indicator x stage cells are validly N/A).
  Do NOT score a model that returns N/A everywhere as accurate — disaggregate F1 by populated vs N/A.

## Known data issues to design the pipeline around
1. **Multi-product EPDs** — SCS-EPD-06707 covers Knight Tile + Van Gogh variants; production emitted
   one distinct record + an identical triplicate. Pipeline must split products without
   cross-contamination and emit one record per product.
2. **Extraction non-determinism** — UL doc 4791540199 was run twice and the passes disagreed
   (different fill and values). Relevant to the confidence / calibration work.
3. **Units** — a fully-populated record can still be wrong if the functional unit differs
   (record 33, German EPD, GWP A1-A3 ~= 952.88). Build a unit-outlier check into validation.
4. **Scientific notation** — confirm `E-1` / `E+00` survive extraction intact (record 39).
5. **Schema provenance** — the gold JSON came from a 4-call production pipeline
   (Material / LCA table / Product info x2), NOT the single-call notebook in the repo.
   The notebook (`epd_sample.ipynb`) is an older, simplified version — don't treat it as the
   current production schema. (Also: its hardcoded Gemini API key should be rotated.)

## Log updates to make
PROJECT_LOG.md and CLAUDE.md still list schema-normalisation as the next task. It is DONE. Record:
- normalisation complete (loss-free), gold-standard audit complete
- working set = 18 clean / 25 quarantined; 9 UNVERIFIED moved to quarantine 2026-06-15
- failure-taxonomy seeds: BRE/Altro prompt-leak contamination, Sherwin-Williams/NSF ISO-21930
  empties, multi-product split failure (SCS-06707), UL extraction non-determinism

## Next pipeline steps (per project plan)
1. `src/preprocessing/docling_pipeline.py` — PDF -> structured text + table markdown
2. Evaluation harness — per-field accuracy (exact-match categorical, tolerance numeric),
   F1 disaggregated by field category and populated/N-A, schema validity, plus unit-outlier
   and sci-notation sanity checks
3. Baseline C — zero-shot Phi-4-Mini on the clean working set
