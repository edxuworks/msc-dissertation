# MSc Project Log
## Industry Application of Frugal AI to Tabular Data Extraction from PDFs
### A Cloud-to-Local Cascade Framework for Environmental Product Declarations

**Author:** Edward Xu — MSc Computing, Imperial College London  
**Supervisor:** Dr Thomas Heinis  
**Industrial Partner:** Firstplanit  
**Dissertation deadline:** ~September 2026  

---

## Table of Contents
1. [Project Context](#1-project-context)
2. [Technical Architecture](#2-technical-architecture)
3. [Data Inventory](#3-data-inventory)
4. [Environment](#4-environment)
5. [Progress Log](#5-progress-log)
6. [Current Status](#6-current-status)
7. [Next Steps](#7-next-steps)
8. [Open Questions](#8-open-questions)
9. [Known Issues & Observations](#9-known-issues--observations)

---

## 1. Project Context

### Problem
Firstplanit's production EPD ingestion pipeline relies on a single frontier cloud model (Gemini 2.5 Flash) to extract ~210 structured fields from heterogeneous PDF documents. This creates cost-scaling, vendor lock-in, and data-governance risks.

### Research Question
Can a frugal, cloud-to-local cascade strategy match the extraction quality of the frontier-only baseline at materially lower cost, energy, and vendor dependency?

### Three FrugalGPT Strategies Under Evaluation
| Strategy | Description |
|---|---|
| **S1 — Prompt Adaptation** | Schema chunking + guided decoding (XGrammar via vLLM) to reduce tokens per query |
| **S2 — LLM Approximation** | QLoRA fine-tuning of Phi-4-Mini (3.8B) on the EPD gold standard |
| **S3 — LLM Cascade** | Route: fine-tuned SLM → mid-tier local → frontier cloud, escalating on low confidence |

All three are evaluated individually and combined (S1+S2, S1+S3, S2+S3, S1+S2+S3 full pipeline).

### Baselines
| Baseline | Description |
|---|---|
| **A** | Firstplanit production (Gemini 2.5 Flash) — realistic comparison |
| **B** | Frontier cloud reference (Claude Sonnet / GPT / Gemini 2.5 Pro) — upper bound |
| **C** | Zero-shot local SLM (Phi-4-Mini, Qwen 2.5 3B, Gemma 4 4B) — no domain adaptation |

### Success Criteria
1. **Empirical:** Defensible cost-quality Pareto frontier; at least one frugal configuration improves on the baseline along ≥1 axis (cost, latency, governance) at ≥0.95 accuracy threshold
2. **Technical:** Working reproducible pipeline with at least one QLoRA fine-tuned EPD model
3. **Methodological:** Failure-mode taxonomy + critical reflection on frugal deployment in startup context

---

## 2. Technical Architecture

### Pipeline Stages
```
PDF → [Stage 1: Preprocessing] → [Stage 2: SLM Extraction] → [Stage 3: Cascade Decision] → [Stage 4: Validation & Output]
```

**Stage 1 — Preprocessing**
- Native PDF inspection: tag detection (tagged vs untagged), language detection
- OCR fallback for scanned documents: Tesseract or PaddleOCR
- Layout-aware table extraction: **Docling** (IBM, integrates TableFormer)
- Output: structured text / markdown representation of document

**Stage 2 — SLM Tier Extraction**
- Fine-tuned local SLM with guided decoding (XGrammar via vLLM)
- Produces schema-valid JSON + confidence signal
- Models: Phi-4-Mini 3.8B (primary), Qwen2.5-VL 3B/7B (vision path for complex tables)

**Stage 3 — Cascade Decision**
- Confidence signals under comparison: token-level probability, self-consistency sampling, semantic entropy
- Accept if confidence ≥ threshold; escalate otherwise
- Tier order: fine-tuned SLM → mid-tier local (Qwen 2.5 7B / Phi-4) → frontier cloud

**Stage 4 — Validation & Output**
- Schema validity check (JSON conformance)
- Internal consistency checks (e.g. A1-A3 ≈ A1 + A2 + A3 where both reported)
- Write to Firstplanit MongoDB schema (or simulation thereof)

### Key Tool Choices
| Component | Tool | Rationale |
|---|---|---|
| PDF preprocessing | Docling | SOTA open-source, integrates TableFormer (98.5% TED on simple tables) |
| Local inference | vLLM + XGrammar | Up to 100× speedup over earlier grammar-constrained approaches |
| Fine-tuning | QLoRA (4-bit) | Enables multi-billion param fine-tuning on single consumer GPU |
| Base SLM | Phi-4-Mini 3.8B | Strong reasoning at small scale; precedent from Strata (8B Llama → human-level) |
| Vision path | Qwen2.5-VL 3B/7B | Bypasses OCR bottleneck for table-heavy/scanned documents |
| Constrained decoding | XGrammar | Default backend for vLLM and SGLang; guarantees schema-valid JSON output |

---

## 3. Data Inventory

### Ground Truth: `epd_extraction.json`
- **Location:** `/home/edwardxu/MSc_Project/epd_extraction.json`
- **Records:** 43 EPDs
- **Fields:** 109 per record (Firstplanit production schema)
- **Source:** Firstplanit's production Gemini 2.5 Flash extractions (to be verified / used as baseline)

#### Records by Programme Operator
| Operator | Country | Count | Notes |
|---|---|---|---|
| EPD International AB | Sweden | 1 | Well-structured |
| SCS Global Services | USA | 7 | Multi-product EPDs (SCS-EPD-06707 appears 4×) |
| BRE Global / BRE Global Ltd | UK | 3 | `000xxx.pdf` format — 8 records with near-empty fields |
| Stichting MRPI® (NEN) | Netherlands | 5 | Dulux/Sikkens/AkzoNobel products |
| UL Solutions / UL Environment | USA | 5 | Carpet and resilient flooring |
| Institut Bauen und Umwelt (IBU) | Germany | 2 | One German-language EPD |
| NSF International / NSF Certification | USA | 3 | Paints/coatings |
| ReTHiNK (Vescom BV) | Netherlands | 3 | Fabric/wallcovering |
| Multicert Sp. z o.o. | Poland | 1 | Polish operator |
| Instytut Techniki Budowlanej | Poland | 1 | Polish operator |

#### Schema Structure
The 109 fields cover:
- **Product metadata:** name, manufacturer, dates, programme operator, certifications
- **LCA indicator matrices** (nested dicts keyed by lifecycle stage A1/A2/A3/A1-A3/A4/A5/B1-B7/C1-C4/D):
  - GWP-TOTAL, GWP-FOSSIL, GWP-BIOGENIC
  - ACIDIFICATION, EUTROFICATION (also EP, AP variants)
  - FRESH WATER (FW)
  - PERT, PENRT, PERE, PERM, PENRE, PENRM
- **Physical/material properties:** density, dimensions, weight, composition
- **Certifications and compliance**
- **Descriptions:** short, long, application, advantages

### EPD PDFs
- **Location:** `/home/edwardxu/MSc_Project/EPDs/`
- **Count:** 43 PDFs (mirrored in nested `MSc Project/EPDs/` subfolder — same files)
- **Formats encountered:** native digital, likely some scanned; multi-language (German EPD present)

---

## 4. Environment

### System
- **OS:** WSL Ubuntu on Windows 11
- **Python:** 3.14.4 (system install)
- **GPU:** Quadro RTX 4000 with Max-Q (8GB VRAM) — confirmed 2026-06-15; `torch.cuda.is_available()=True`, CUDA 13.1, Driver 591.86
- **Project path:** `/home/edwardxu/MSc_Project/`

### Installed (as of 2026-06-14) ✅
All packages installed and verified in `.venv` virtual environment:

| Package group | Packages |
|---|---|
| PDF preprocessing | `pymupdf`, `pytesseract`, `docling` (incl. TableFormer, torch, torchvision) |
| HuggingFace ML stack | `transformers`, `accelerate`, `peft`, `bitsandbytes`, `trl`, `datasets`, `evaluate` |
| Cloud API clients | `anthropic`, `openai`, `google-generativeai` |
| Data & evaluation | `pandas`, `numpy`, `scipy`, `scikit-learn`, `jsonschema`, `pydantic` |
| Energy tracking | `codecarbon` |
| Visualisation | `matplotlib`, `seaborn` |
| Utilities | `rich`, `loguru`, `typer`, `python-dotenv`, `tqdm` |

**Deferred (require GPU machine / CUDA):**
- `vllm` — install on Imperial GPU node (requires CUDA toolkit); used for local inference + XGrammar guided decoding
- `paddleocr` — install when needed as OCR fallback alternative to Tesseract
- `outlines` — alternative to XGrammar for structured generation; defer until inference stack chosen

Activate environment: `source /home/edwardxu/MSc_Project/.venv/bin/activate`  
Verify: `python3 scripts/check_install.py`

---

## 5. Progress Log

### 2026-06-15 — Session 8: Preprocessing Complete; Baseline B Designed ✅

**GPU confirmed:** Quadro RTX 4000 Max-Q (8GB VRAM), CUDA 13.1 — available locally in WSL. `torch.cuda.is_available()=True`. Phi-4-Mini 4-bit (~2.5GB) fits comfortably. Imperial node still needed for QLoRA fine-tuning (larger batch sizes).

**Docling preprocessing pipeline — full run complete** (17:13–17:28, ~15 min):

| Result | Count | Notes |
|---|---|---|
| OK | 40 | All with extractable text and table markdown |
| FAIL (timeout) | 2 | `000623.pdf` (122p, 124.1s), `SCS-EPD-06707.pdf` (72p, 123.8s) — expected |
| Skipped (sidecar exists) | 1 | `EPD-IES-0003985002.pdf` — from previous run |

Notable outputs: `255.pdf` (54s, 41 tables, 237k chars), `SCS-EPD-10447.pdf` (51s, 37 tables, 181k chars), `EPD-P 05.11.2025.pdf` (39s, 51 tables, 88k chars) — largest documents in corpus.

**Usable records for Baseline C/B: 14 of 18 clean gold records**

| Status | Count | Detail |
|---|---|---|
| Sidecar OK | 14 | All `success=True` |
| PDF missing from corpus | 4 | `1.1.00527.2024.pdf`, `1.1.00639.2024.pdf`, `4789796942.142.1.pdf`, `4789796942.144.1.pdf` — these 4 PDFs are not in `EPDs/` folder; gold records exist but source PDFs were never provided |

The 4 missing PDFs need to be obtained from Firstplanit before all 18 records can be evaluated. Baseline C and B will run on the 14 available records in the interim.

**Methodological concern identified — Docling as confound:**
All frugal pipelines (C, S1/S2/S3) use Docling preprocessing; Baseline A (Gemini 2.5 Flash) is natively multimodal and bypasses Docling. Any accuracy gap between A and our pipelines conflates model capability with preprocessing quality. Decision: **Baseline B will run in two modes** — `text` (Docling-preprocessed, same path as frugal pipelines) and `native` (raw PDF to model multimodal API, same path as Baseline A). The delta isolates Docling's contribution.

**NVIDIA blog (developer.nvidia.com/blog/approaches-to-pdf-data-extraction-for-information-retrieval/) assessed:**
Not applicable as an additional benchmark — their task is information retrieval (Recall@5), not structured extraction. Their VLM failure modes (hallucinations, incomplete table rows, misread labels) are relevant to the failure-mode taxonomy chapter. No new experiments to add.

**Baseline B design (implementation deferred to next session):**
Script: `scripts/run_baseline_b.py`
- `--model`: `claude-sonnet` | `gpt-4o` | `gemini-2.5-pro`
- `--mode`: `text` | `native` | `both`
- Native PDF delivery: Claude via `document` API content block; Gemini via Files API; GPT-4o via PyMuPDF page-image rendering (base64 vision input)
- Cost tracking from API usage metadata; appends two Pareto rows per `--mode both` run
- Reuses all existing eval harness functions unchanged
- API keys needed: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` (add to `.env`)
- Full plan at `/home/edwardxu/.claude/plans/zesty-dancing-sutton.md`

**Next session start:** Add API keys to `.env`, implement `scripts/run_baseline_b.py`, run smoke test on one record in both modes.

---

### 2026-06-15 — Session 7: Evaluation Harness ✅ COMPLETE

**Files created:**
- `src/evaluation/metrics.py` — `parse_numeric()`, `normalise_string()`, `match_numeric()` (±1% rtol + 1e-4 atol), `match_string()`, `match_list()` (set-based F1)
- `src/evaluation/harness.py` — `FieldScore`, `RecordScore` dataclasses; `evaluate_record()`, `evaluate_dataset()` (matched by `file_name`)
- `src/evaluation/report.py` — `print_summary()` (rich table), `to_csv()`, `to_summary_row()` (Pareto frontier row)
- `requirements.txt` — added `deepdiff>=6.7.0`

**Design decisions:**
- All numerics parsed from strings; scientific notation (`"8.66E-02"`) and `"N/A"` handled
- Disaggregated F1: overall / populated (gold != N/A) / N/A / metadata / LCA
- LCA stage keys `D1`/`D2` skipped (Firstplanit-custom, always N/A)
- `"Standard List"` and `"Tags List"` use set-based F1
- Unit strings normalised via NFKD unicode (CO₂ vs CO2, m³ vs m3)
- Schema validity requires all 12 LCA indicator keys; record 0 (EPD-IES) legitimately fails — missing some indicators in gold standard itself

**Verification passed:**
- Self-score: all 18 records F1=1.0 overall, populated, N/A, metadata, LCA
- Empty pred: f1_overall=0.0, schema_valid=False
- All-N/A pred: f1_na=1.0, f1_populated=0.0 (confirms N/A inflation protection)

---

### 2026-06-15 — Session 6: Gold Standard Trimmed to 18 Confident Records

**Decision:** The 9 VERIFY-flagged records (orig indices 1, 19, 20, 26, 27, 31, 33, 39, 42) that required PDF hand-verification have been moved from the clean set to quarantine with `_quarantine_reason = "UNVERIFIED"`. Working set is now 18 records (clean) + 25 quarantine.

**Rationale:** Rather than blocking pipeline development on manual verification, use only records we are confident about. The 9 unverified records are preserved in quarantine and can be promoted individually once verified — re-run `scripts/create_gold_standard.py` after adjusting index sets.

**Files changed:**
- `scripts/create_gold_standard.py` — removed `VERIFY_INDICES`, updated `CLEAN_INDICES` (27 → 18), added UNVERIFIED entries to `QUARANTINE_REASONS`, updated asserts
- `data/gold_standard/epd_gold_clean.json` — regenerated (18 records, no `_verify` flags)
- `data/gold_standard/epd_gold_quarantine.json` — regenerated (25 records; new UNVERIFIED category)
- `data/gold_standard/gold_standard_manifest.csv` — regenerated (43 rows; 18 CLEAN, 25 QUARANTINE)
- `CLAUDE.md`, `PROJECT_LOG.md`, `data/gold_standard/GROUND_TRUTH_HANDOFF.md`, `GROUND_TRUTH_HANDOFF.md` — updated throughout

---

### 2026-06-14 — Session 1: Project Familiarisation & Setup

**Done:**
- Read and internalized interim report (all chapters)
- Explored full project directory structure in WSL
- Audited `epd_extraction.json`:
  - 43 records confirmed
  - 109 fields per record identified and catalogued
  - Identified schema inconsistencies (field naming diverges between records — see §9)
  - Identified data quality gaps (records 10–17, BRE `000xxx` format, are near-empty)
  - Identified multi-product EPD case (SCS-EPD-06707 appears 4 times)
- Confirmed no code exists yet — clean implementation slate
- Created this project log
- Saved project context to Claude's persistent memory for continuity across sessions

### 2026-06-14 — Session 5: Gold Standard Audit & Preprocessing Pipeline ✅ COMPLETE

**What and why:**
With the corpus audited and schema normalised, the next step was to determine which of the 43 normalised records are trustworthy enough to use as ground truth for evaluation and fine-tuning. This session ran a record-by-record audit of `epd_gold_normalised.json`, split it into a 27-record clean set (later trimmed to 18 confident records — see Session 6) and a 16-record quarantine set, and wrote the Docling preprocessing pipeline.

**Gold standard split:**

| Bucket | Count | Criteria |
|---|---|---|
| CLEAN | 27 | Plausible LCA values, correct schema, no duplicates; 9 flagged for PDF hand-verification |
| CONTAMINATED | 8 | BRE/Altro `000xxx` EPDs — Gemini prompt instructions leaked as JSON keys |
| EMPTY | 3 | Sherwin-Williams/NSF EPDs — ISO 21930 stage notation, LCA matrix all N/A in EN 15804 schema |
| DUPLICATE | 5 | Redundant extraction passes (UL Interface ×3, Van Gogh ×2) |

**Failure-taxonomy seeds (first concrete cases):**
1. **BRE/Altro prompt-leak contamination** — Gemini extraction prompt instructions appeared as JSON keys; root cause is BRE using EN 15804+A1:2013 with different indicator names that the prompt didn't handle, causing the extractor to echo the prompt rather than extract values
2. **Sherwin-Williams/NSF ISO-21930 empties** — EPDs conforming to ISO 21930 (Stage 1–4 notation) rather than EN 15804 (A1/A2/A3 modules) were correctly identified by the extractor as not mappable — all N/A returned
3. **Multi-product split failure (SCS-EPD-06707)** — 4 extractions from 1 PDF; 2 clean (Knight Tile, Van Gogh), 2 quarantined as exact duplicates of Van Gogh — suggests non-determinism in the production pipeline's product-column detection
4. **UL extraction non-determinism** — UL Interface records 23–25 are second passes of records 20–22; slight value divergences between runs suggest temperature > 0 or variable chunking in production

**VERIFY-flagged records (9 — moved to quarantine in Session 6, 2026-06-15):**
Records at original indices 1, 19, 20, 26, 27, 31, 33, 39, 42 were flagged for PDF cross-check. Decision: moved to quarantine (UNVERIFIED) rather than blocking pipeline development.

**Output files created:**
- `scripts/create_gold_standard.py` — reproducible split script; re-running regenerates all output files
- `data/gold_standard/epd_gold_clean.json` — 27 clean records at time of creation; trimmed to 18 in Session 6
- `data/gold_standard/epd_gold_quarantine.json` — 16 quarantined records at time of creation; grown to 25 in Session 6
- `data/gold_standard/gold_standard_manifest.csv` — 43-row audit manifest
- `data/gold_standard/GROUND_TRUTH_HANDOFF.md` — canonical reference for future sessions
- `src/preprocessing/docling_pipeline.py` — Docling PDF → text + tables; `do_ocr=False`, 120s timeout, resumable

### 2026-06-14 — Session 4: Corpus Audit ✅ COMPLETE

**What and why:**
Before any extraction or evaluation code can be written, we need to understand what we're actually dealing with across the 43 EPD PDFs. The corpus audit script (`scripts/corpus_audit.py`) runs every PDF through PyMuPDF + Docling and records per-document properties to `data/corpus_audit/audit.csv`. This CSV becomes the foundation for:
- Stratifying the gold standard (ensuring the 50–100 hand-verified EPDs cover all complexity tiers)
- Understanding why the 8 BRE records failed in the production Gemini pipeline
- Confirming the routing hypothesis (complex docs need escalation; simple ones don't)

**What the script measures per PDF:**

| Field | How detected | Why it matters |
|---|---|---|
| `native_vs_scanned` | PyMuPDF text length per page < threshold | Determines if OCR fallback needed |
| `tagged` | PDF catalog MarkInfo entry via PyMuPDF | Tagged PDFs have logical structure — easier to parse |
| `page_count` | PyMuPDF | Proxy for document size/complexity |
| `language` | langdetect on extracted text | Flags non-English EPDs for routing |
| `table_count` | Docling TableItem objects | Core difficulty signal |
| `text_length` | Character count of PyMuPDF extraction | Catches silent scanned-PDF failures |
| `docling_success` | Whether Docling completed without error | Identifies documents needing VLM fallback |
| `docling_table_text_len` | Total char length of all Docling tables | Quality of table extraction |
| `complexity_tier` | Rule-based: Simple / Medium / Hard | Feeds gold standard stratification |
| `gold_standard_match` | Filename match to epd_extraction.json | Links audit results to existing ground truth |

**Technical issues encountered and resolved:**
1. First run killed by SIGTERM — Docling was running RapidOCR on every embedded image even for native PDFs; `000623.pdf` alone took 6 minutes
2. Fix: `pipeline_options.do_ocr = False` — eliminates RapidOCR; subsequent run completed in 15 min 17 sec for all 43 PDFs
3. Added `signal.SIGALRM`-based 120s per-document timeout to prevent any single PDF from blocking the run
4. Added incremental CSV writing (flush after each PDF) so a kill mid-run doesn't lose completed work
5. Fixed deprecated Docling API: `tbl.export_to_markdown()` → `tbl.export_to_markdown(doc)`

**Corpus audit results (2026-06-14, 15m 17s for 43 PDFs):**

```
CORPUS AUDIT SUMMARY  (43 PDFs)
════════════════════════════════════════════════════════════
  Native:          43/43   ← all PDFs have extractable text; ZERO are scanned
  Scanned:          0/43
  Tagged:          27/43   ← PDF accessibility structure (helps Docling)
  Non-English:      1/43   ← German EPD: EPD 20223-...-DE-System.pdf
  Docling failed:   2/43   ← 000623.pdf (122p) + SCS-EPD-06707.pdf (72p) — timeouts
  Complexity tiers: Simple=0  Medium=22  Hard=21
════════════════════════════════════════════════════════════
```

**Hard PDFs (>15 pages OR Docling fail OR non-English):**

| PDF | Pages | Tables | Docling | Note |
|---|---|---|---|---|
| 000623.pdf | 122 | — | FAIL | Timeout at 120s |
| SCS-EPD-06707.pdf | 72 | — | FAIL | Timeout at 120s; the multi-product EPD (4 records in gold standard) |
| 255.pdf | 46 | 41 | OK | Large BRE variant |
| EPD-P 05.11.2025.pdf | 40 | 51 | OK | Most tables of any doc |
| SCS-EPD-10447.pdf | 38 | 37 | OK | |
| 263.pdf | 30 | 27 | OK | |
| SCS-EPD-06708.pdf | 28 | 22 | OK | |
| … (14 more 16–22p docs) | — | — | OK | |
| EPD 20223-...-DE-System.pdf | 12 | 12 | OK | **German** |

**Medium PDFs (9–15 pages OR >4 tables):**

All 22 Medium PDFs are native English; range 5–15 pages, 8–16 tables. Includes all BRE `000xxx.pdf` files (8–14 pages).

**Key findings and implications:**

1. **BRE `000xxx.pdf` failure root cause IDENTIFIED:** All BRE files are native (not scanned), 8–14 pages, English, and Docling succeeds on all of them. The near-empty records 10–17 in `epd_extraction.json` are therefore a **production extraction failure**, not a PDF quality problem. Likely causes: BRE layout, column structure, or different field naming that the Gemini prompt didn't handle. This is a direct case for the failure-mode taxonomy.

2. **No Simple-tier EPDs exist in this corpus.** All 43 are Medium or Hard. This means (a) the cascade is always relevant, and (b) the gold standard stratification becomes Medium vs Hard rather than Simple/Medium/Hard.

3. **Two PDFs need special handling beyond Docling:** `000623.pdf` (122p) and `SCS-EPD-06707.pdf` (72p) both hit the 120s timeout. These will need either a longer timeout, chunked processing, or a vision-language model fallback. `SCS-EPD-06707.pdf` is also the multi-product EPD that generates 4 gold standard records.

4. **13 PDFs in the folder have no gold standard match.** These are: the un-prefixed series (`252.pdf`, `255.pdf`, `263.pdf`, `338.pdf`, `393.pdf`, `433.pdf`, `438.pdf`, `601.pdf`), plus `000338 - 1.pdf`, two ShawEPD files, and `EPD-MIL-20230039-CBA1-EN.pdf`. These may be additional EPDs provided by Firstplanit that haven't been extracted yet, or variant versions of existing docs.

5. **Gold standard match rate: 30/43 PDFs.** The 13 unmatched PDFs suggest the corpus has grown since the initial Firstplanit extraction run.

**Output:** `data/corpus_audit/audit.csv` — 43 rows, 16 columns. Resumable: re-running the script will skip already-completed PDFs.

### 2026-06-14 — Session 3: matextract.pub Deep Read & Skills File

- Read entire matextract.pub site (8 workflow sections + biomass case study): constrained generation, PDF parsing, chunking, fine-tuning, prompting hierarchy, evaluation, VLMs, agents
- Created `SKILLS_AND_REFERENCES.md` — distilled best practices, code patterns, and benchmarks with full source references
- Key findings added to skills file:
  - **Do not combine few-shot prompting with a fine-tuned model** — matextract showed this degrades F1 (0.965 → 0.960)
  - Tables must be isolated into their own chunks (not mixed with prose)
  - Leaf-node counting + DeepDiff + Hungarian algorithm for evaluating nested JSON predictions
  - QLoRA config: nf4 4-bit, rank=32, alpha=64, batch=2, grad_accum=8
  - `instructor` library for constrained cloud extraction; XGrammar/vLLM for local
  - PyMuPDF silent failure on scanned PDFs — always check text length before assuming native

### 2026-06-14 — Session 2: FrugalGPT Repo Review & Environment Setup
- Explored FrugalGPT GitHub repo (stanford-futuredata/FrugalGPT): read `llmcascade.py`, `scoring.py`, `optimizer.py`, `llmchain.py`, `evaluate.py` — see §9 for detailed notes on what is and isn't reusable
- Created full project directory structure: `src/{preprocessing,extraction,finetuning,cascade,evaluation,utils}`, `data/{gold_standard,corpus_audit,results,cache}`, `configs/`, `notebooks/`, `scripts/`, `figures/`
- Created `requirements.txt` with all dependencies documented and annotated
- Installed all 21 packages into `.venv` — 0 failures (see §4 for full list)
- Deferred: `vllm` (needs CUDA/Imperial GPU node), `paddleocr`, `outlines`
- Created `scripts/check_install.py` for future verification

**Observations of note:**
- `epd_extraction.json` appears to be Firstplanit's *production output* (Gemini 2.5 Flash extractions), not a hand-verified gold standard. It will serve as Baseline A but needs verification before use as ground truth.
- Field naming is inconsistent across the 43 records — suggests the extraction schema evolved over time or different prompt versions were used (see §9 for detail)
- 8 records with BRE `000xxx.pdf` filenames are almost entirely null — these are failure cases that warrant investigation (scanned? complex layout?)

---

## 6. Current Status

| Area | Status | Notes |
|---|---|---|
| Literature review | ✅ Complete | Written up in interim report Ch.3 |
| **Corpus audit** | **✅ Complete** | `data/corpus_audit/audit.csv` — 43 PDFs, 0 scanned, 21 Hard / 22 Medium / 0 Simple |
| **Schema normalisation** | **✅ Complete** | `epd_gold_normalised.json` — 43 records, loss-free key-renaming; 3 schema variants unified |
| **Gold standard construction** | **✅ Complete** | 18 clean / 25 quarantined (9 UNVERIFIED + 16 known-bad); see `GROUND_TRUTH_HANDOFF.md` |
| Dev environment setup | ✅ Complete | `.venv` + 21 packages; vLLM deferred to GPU node |
| **Preprocessing pipeline (Docling)** | **✅ Complete** | 40/42 PDFs OK; 2 timeout (000623, SCS-EPD-06707); 14/18 gold records runnable |
| **Evaluation harness** | **✅ Complete** | `src/evaluation/` — per-field F1 disaggregated by category + populated/N/A; self-test passes |
| Baseline A (Firstplanit / Gemini 2.5 Flash) | ⏳ Not started | Need to re-run on verified gold standard |
| Baseline B (frontier cloud reference) | 🔄 Designed | `scripts/run_baseline_b.py` — text + native PDF modes; API keys needed; implement next session |
| Baseline C (zero-shot local SLM) | 🔄 Ready to run | `scripts/run_baseline_c.py` written; GPU confirmed (RTX 4000); 14 records have sidecars |
| S1 — Prompt adaptation | ⏳ Not started | — |
| S2 — QLoRA fine-tuning (Phi-4-Mini) | ⏳ Not started | — |
| S3 — Cascade implementation | ⏳ Not started | — |
| Full S1+S2+S3 pipeline | ⏳ Not started | — |
| Failure-mode taxonomy | 🔄 Seeds identified | BRE prompt-leak, ISO 21930 empties, multi-product non-determinism, UL duplicate runs |
| Industrial reflection chapter | ⏳ Not started | — |
| Dissertation write-up | ⏳ Not started | — |

---

## 7. Next Steps

### Immediate (Week 1–2 of project timeline)
- [x] ~~Set up Python environment~~ — `.venv` + 21 packages installed
- [x] ~~Corpus audit script~~ — `scripts/corpus_audit.py` complete
- [x] ~~Corpus audit results~~ — `data/corpus_audit/audit.csv` (43 PDFs, 16 fields each)
- [x] ~~Resolve schema inconsistency~~ — `epd_gold_normalised.json` (43 records, canonical field names)
- [x] ~~Gold standard construction~~ — 18 clean / 25 quarantined; `epd_gold_clean.json` is working ground truth
- [x] ~~Clarify 13 unmatched PDFs~~ — Decision: ignore; treat `epd_extraction.json` as source
- [x] ~~Docling preprocessing pipeline~~ — `src/preprocessing/docling_pipeline.py` written
### Short term (Week 3–4) — immediate next session
- [x] ~~Evaluation harness~~ — `src/evaluation/` complete; self-test passes
- [ ] **Baseline B** — implement `scripts/run_baseline_b.py`; add `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` to `.env`; run smoke test; full run on 14 records in text + native modes
- [ ] **Baseline C** — run `scripts/run_baseline_c.py` on 14 records with GPU (RTX 4000, 4-bit Phi-4-Mini); obtain remaining 4 PDFs from Firstplanit

### Medium term (Weeks 5–9)
- [ ] QLoRA fine-tuning of Phi-4-Mini on training split
- [ ] Cascade implementation + confidence threshold sweep
- [ ] Baselines A and B

### Stretch goals (Weeks 10–11)
- [ ] Mid-tier fine-tuning (Qwen 2.5 7B)
- [ ] Upfront complexity-aware routing vs confidence-based routing comparison
- [ ] Additional model-size ablations

---

## 8. Open Questions

Carried forward from interim report §4.5:

1. **Project framing** — Frugal AI as umbrella vs EPD extraction problem as primary lens
2. **Upfront routing** — document feature routing (tagged/language/operator) before SLM invocation as complement to confidence-based cascade
3. **Gold standard size** — 50 vs 100 hand-verified EPDs (rate-limiting step is verification time)
4. **openEPD/ECO Platform as baseline** — machine-readable EPDs as "perfect extraction" reference or sanity check only
5. **Complete extraction failures** — flag-for-human-review vs partial extraction vs hard failure policy; need Firstplanit input
6. **Confidence calibration** — separate held-out calibration set vs using cascade-escalation patterns on gold standard
7. **Project scope** — is FrugalGPT + fine-tuned SLM sufficient novelty, or should a complexity-aware routing framework be proposed?

**New questions arising from data audit (2026-06-14):**

8. **Schema versioning** — the inconsistent field naming in `epd_extraction.json` suggests multiple extraction runs with different prompts/schema versions. Which version is canonical? Need to confirm with Firstplanit.
9. **BRE `000xxx` failures** — why are records 10–17 nearly empty? Are these scanned PDFs that defeated the current Gemini pipeline? This could be a key data point for the failure-mode taxonomy.
10. **Multi-product EPD handling** — SCS-EPD-06707.pdf produces 4 records. Is the pipeline currently splitting by product column in the table, or is this a manual step? This affects how the extraction schema handles multi-product documents.

---

## 9. Known Issues & Observations

### Schema field naming inconsistency
The `epd_extraction.json` shows two different field naming conventions across records:

| Record group | GWP field name | Energy field names |
|---|---|---|
| Record 1 (EPD International) | `Embodied Carbon (GWP Total)` | `Embodied Energy (PERT - Renewable)` |
| Records 2–43 (SCS, UL, etc.) | `GWP-TOTAL` | `PERT`, `PENRT`, `PERE`, `PERM` |

**Implication:** The JSON is not a single unified schema — it is the concatenated output of at least two different extraction runs. Before any evaluation can be done, a canonical schema must be defined and all records normalised to it.

### Near-empty BRE records (records 10–17) — root cause identified
Files `000252.pdf`, `000255.pdf`, `000260.pdf`, `000263.pdf`, `000338.pdf` (×2), `000393.pdf`, `000601.pdf`, `000623.pdf` have almost no extracted data in the ground truth JSON.

**Corpus audit finding (2026-06-14):** ALL of these PDFs are native (not scanned), English, and Docling succeeds on all except `000623.pdf` (which times out due to 122 pages — a size issue, not a scan issue). The BRE extraction failures are therefore a **production pipeline failure** — the Gemini extraction prompt or schema definition failed to capture data from these documents. Most likely causes:
- BRE layout uses non-standard table structure or column labelling
- Field names in BRE EPDs don't match the extraction schema's expected terminology
- `000623.pdf` is simply too large (122 pages, all-indicator multi-product document) for the current approach

This is the **first concrete case** for the failure-mode taxonomy: layout-induced extraction failure on a fully text-accessible PDF.

### Two PDFs exceed Docling 120s timeout
`000623.pdf` (122 pages) and `SCS-EPD-06707.pdf` (72 pages) both timeout Docling's `StandardPdfPipeline`. Docling fails silently with "Pipeline StandardPdfPipeline failed" (timeout signal converted internally). These documents will require either:
- Chunked Docling processing (process 20 pages at a time)
- Vision-language model (VLM) fallback — Qwen2.5-VL could handle large table-heavy PDFs
- Page-range selection (only process the LCA indicator pages, not the full document)

### FrugalGPT repo — what's reusable and what isn't

**Repo:** `github.com/stanford-futuredata/FrugalGPT` (Apache 2.0, 92% Jupyter notebooks)

| File | What it does | Verdict for this project |
|---|---|---|
| `llmcascade.py` | Sequential model querying; breaks when score > (1−threshold) | **Direct template** — adopt the cascade loop pattern |
| `optimizer.py` | `scipy.optimize.brute` over model orderings + thresholds subject to budget cap; produces cost/loss matrices | **Direct use** — threshold sweep + Pareto frontier generation |
| `llmchain.py` | Stores trained config (model order, thresholds) to JSON; enumerates permutations | **Adopt** — good practice for reproducibility |
| `scoring.py` | DistilBERT binary classifier trained on query+answer→correct/incorrect | **Different signal needed** — their scorer assumes a single-answer QA task; our confidence comes from token-level log-probs or self-consistency across 168 fields |
| `evaluate.py` | Exact Match (EM) + mean cost per sample via pandas `.apply()` | **Extend** — their EM is a single string; need per-field F1 disaggregated by field type/category |
| `data/` | COQA, HEADLINES (NLP benchmarks) | **Not usable** — building own gold standard |

**Key architectural difference:** FrugalGPT cascades between cloud APIs; this project's first tier is a locally fine-tuned SLM. The optimizer and cascade loop transfer directly; the scorer and evaluation layer need to be rebuilt for structured JSON extraction.

### Multi-product EPD case
`SCS-EPD-06707.pdf` generates 4 records (Knight Tile LVF, Van Gogh Luxury Vinyl ×3). The pipeline must:
- Detect that a PDF contains multiple products
- Extract each product column independently without cross-contamination
- Produce one output record per product, not per PDF

### Duplicate PDF storage
All 43 PDFs appear twice: in `/home/edwardxu/MSc_Project/EPDs/` and in `/home/edwardxu/MSc_Project/EPDs/MSc Project/EPDs/`. Use the top-level path as canonical; the nested copy appears to be a sync artifact.

---

*Log maintained by Claude Code (claude-sonnet-4-6) in collaboration with Edward Xu.*  
*Update this file at the start and end of each working session.*
