# CLAUDE.md — Session Context for Claude Code

This file is read automatically at the start of every session. It keeps Claude up to date
on the project without needing a long briefing.

---

## What this project is

MSc Computing dissertation (Imperial College London, Edward Xu, supervisor Dr Thomas Heinis).
Industrial partner: Firstplanit.

**Goal:** Evaluate FrugalGPT's three strategies against Firstplanit's production EPD extraction
pipeline (Gemini 2.5 Flash), producing a cost-quality Pareto frontier.

An EPD (Environmental Product Declaration) is a sustainability document governed by EN 15804.
Each EPD contains ~210 structured fields — primarily an LCA indicator × lifecycle stage matrix
(GWP, PERT, PENRT, etc. across stages A1, A2, A3, A1-A3, A4, A5, B1-B7, C1-C4, D).

**Three FrugalGPT strategies under evaluation:**
- S1 — Prompt adaptation (schema chunking + guided decoding via XGrammar/vLLM)
- S2 — LLM approximation (QLoRA fine-tuning of Phi-4-Mini 3.8B)
- S3 — LLM cascade (fine-tuned SLM → mid-tier local → frontier cloud, routed on confidence)

**Baselines:**
- A: Firstplanit production (Gemini 2.5 Flash) — the comparison target
- B: Frontier cloud reference (Claude / GPT-4o / Gemini 2.5 Pro) — upper bound
- C: Zero-shot local SLM (Phi-4-Mini) — no domain adaptation

**NDA constraint:** Do not disclose Firstplanit's full field list, full pipeline details, or
complete datasets. Aggregated findings and comparative results are reportable.

---

## Environment

- **OS:** WSL Ubuntu on Windows 11
- **Python:** 3.14.4 in `.venv` — activate with `source .venv/bin/activate`
- **Verify packages:** `python3 scripts/check_install.py` (21 packages, 0 missing as of 2026-06-14)
- **GPU:** TBC — Imperial computing node for vLLM + QLoRA (vLLM not yet installed)
- **All commands run in WSL**, launched from PowerShell via `wsl -e bash -c "..."`

---

## Key file locations

| File/Dir | What it is |
|---|---|
| `epd_extraction.json` | Source: original 43-record Firstplanit Gemini 2.5 Flash extractions — **not** working ground truth |
| `data/gold_standard/epd_gold_clean.json` | **Working ground truth** — 27 clean records; use this for all pipeline/eval work |
| `data/gold_standard/epd_gold_quarantine.json` | 16 quarantined records with `_quarantine_reason` and `_orig_index` fields |
| `data/gold_standard/gold_standard_manifest.csv` | 43-row manifest: orig_idx, bucket, file_name, product_name, gwp_a1a3, notes |
| `data/gold_standard/GROUND_TRUTH_HANDOFF.md` | **Read this first** — full audit rationale, schema reference, known issues |
| `data/gold_standard/epd_gold_normalised.json` | Intermediate: 43 records with canonical field names (parent of clean/quarantine) |
| `EPDs/` | 43 PDF files (top-level only — ignore `EPDs/MSc Project/EPDs/` duplicate) |
| `data/corpus_audit/audit.csv` | Per-PDF audit: pages, tables, tier, language, Docling success |
| `data/preprocessed/` | Docling output: one JSON sidecar per PDF (text + table markdown) |
| `scripts/corpus_audit.py` | Audit script (resumable — skips already-processed PDFs) |
| `scripts/create_gold_standard.py` | Reproducible script that generates clean/quarantine split from normalised JSON |
| `scripts/check_install.py` | Package verification |
| `src/preprocessing/docling_pipeline.py` | PDF → structured text + table markdown (Docling, do_ocr=False, resumable) |
| `PROJECT_LOG.md` | Full project log — read this for detailed session history |
| `SKILLS_AND_REFERENCES.md` | Best practices from matextract.pub + FrugalGPT repo |
| `requirements.txt` | Annotated dependencies |
| `configs/` | Model and pipeline configs (not yet written) |

---

## What has been done (as of 2026-06-14)

1. **Environment setup** — `.venv` + 21 packages installed; structure created
2. **FrugalGPT repo reviewed** — `llmcascade.py`, `optimizer.py`, `scoring.py` analysed; cascade loop + scipy.optimize.brute threshold sweep are directly reusable; scorer and evaluator need rebuilding for structured JSON extraction
3. **matextract.pub read** — best practices extracted into `SKILLS_AND_REFERENCES.md`; key finding: do NOT combine few-shot prompting with a fine-tuned model (degrades F1)
4. **Corpus audit complete** — `data/corpus_audit/audit.csv` produced:
   - 43/43 PDFs are native (not scanned)
   - 21 Hard / 22 Medium / 0 Simple
   - 2 Docling timeouts: `000623.pdf` (122p) and `SCS-EPD-06707.pdf` (72p)
   - 1 German EPD: `EPD 20223-202209-20220929135748-DE-System.pdf`
   - BRE `000xxx.pdf` failures in gold standard are **extraction failures** (not scan failures) — PDF text is accessible
5. **Schema normalisation complete** — `data/gold_standard/epd_gold_normalised.json` (43 records); loss-free key-renaming only; three schema variants unified to canonical
6. **Gold standard audit complete** — working set = 27 clean / 16 quarantined:
   - `data/gold_standard/epd_gold_clean.json` — 27 records; 9 VERIFY-flagged (need PDF cross-check)
   - `data/gold_standard/epd_gold_quarantine.json` — 16 records with `_quarantine_reason`
   - Failure-taxonomy seeds: BRE/Altro prompt-leak contamination (8), Sherwin-Williams/NSF ISO-21930 empties (3), multi-product split UL non-determinism (5 duplicates)
7. **Docling preprocessing pipeline written** — `src/preprocessing/docling_pipeline.py`; `do_ocr=False`, 120s timeout, resumable via JSON sidecar in `data/preprocessed/`

---

## Known issues and decisions

- **Schema normalisation done:** `epd_extraction.json` had three field-naming variants; all mapped to canonical in `epd_gold_normalised.json`. See `scripts/normalise_schema.py` for the rename maps.
- **13 unmatched PDFs:** PDFs in `EPDs/` folder with no entry in `epd_extraction.json`. Decision: ignore — treat `epd_extraction.json` as the authoritative source.
- **SCS-EPD-06707.pdf (multi-product EPD):** Records 26 (Knight Tile) and 27 (Van Gogh) are in the clean set; records 28–29 (Van Gogh duplicates) are quarantined. Evaluation of multi-product EPDs will need Hungarian algorithm matching (see `SKILLS_AND_REFERENCES.md §6`).
- **BRE `000xxx.pdf` records quarantined (CONTAMINATED):** Gemini prompt instructions leaked as JSON keys; schema entirely non-compliant. Root cause: BRE EPDs use EN 15804+A1:2013 (older standard, different indicator names). These 8 records are in `epd_gold_quarantine.json`.
- **Sherwin-Williams/NSF records quarantined (EMPTY):** ISO 21930 stage notation (Stage 1–4) doesn't map to EN 15804 modules; LCA matrix all N/A. These 3 records are in `epd_gold_quarantine.json`.
- **D1/D2 fields always N/A:** Firstplanit-custom schema fields not in EN 15804. Do not penalise extraction models for returning N/A here.
- **9 VERIFY-flagged clean records:** Need PDF cross-check by Edward. Indices (original): 1, 19, 20, 26, 27, 31, 33, 39, 42. Marked with `"_verify": true` in `epd_gold_clean.json`.
- **Docling timeouts:** `000623.pdf` (122p) and `SCS-EPD-06707.pdf` (72p) exceed 120s. Preprocessing pipeline will need page-range chunking or VLM fallback for these.

---

## Immediate next tasks

1. **Evaluation harness** — per-field F1 (exact-match categorical, tolerance-based numeric), disaggregated by field category AND by populated vs N/A; schema validity; unit-outlier check. **Confirm design with Edward before implementing.**
2. **Baseline C** — zero-shot Phi-4-Mini on the 27-record clean working set (requires local model setup)
3. **Hand-verify 9 VERIFY-flagged records** — Edward's task: cross-check orig indices 1, 19, 20, 26, 27, 31, 33, 39, 42 against source PDFs

---

## Style notes for this project

- Log every significant decision and finding in `PROJECT_LOG.md` (dated session entries)
- Keep `SKILLS_AND_REFERENCES.md` updated with new best-practice discoveries
- All scripts go in `scripts/` (one-off tools) or `src/` (pipeline components)
- Output data goes in `data/` subdirectories — never write to `EPDs/` or overwrite source files
