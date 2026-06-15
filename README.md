# Frugal AI for Structured Data Extraction from Environmental Product Declarations

**MSc Computing Dissertation** · Imperial College London · 2026  
**Author:** Edward Xu  
**Supervisor:** Dr Thomas Heinis  
**Industrial Partner:** Firstplanit  

---

## Overview

Environmental Product Declarations (EPDs) are standardised sustainability documents containing life cycle assessment (LCA) data for construction materials, governed by EN 15804. Extracting structured data from EPDs at scale is a commercially important but technically challenging problem: documents are heterogeneous PDFs spanning dozens of pages, containing complex multi-column indicator tables, and produced by different programme operators with varying layouts.

This project evaluates three **FrugalGPT** cost-reduction strategies against a frontier cloud baseline (Firstplanit's production Gemini 2.5 Flash pipeline) on a gold-standard corpus of 18 verified EPD extractions. The goal is to produce a cost–quality Pareto frontier showing where local and frugal approaches can match frontier performance at materially lower cost and vendor dependency.

---

## Research Question

> Can a frugal, cloud-to-local cascade strategy match the extraction quality of a frontier-only baseline at lower cost, energy, and vendor dependency?

---

## Strategies Under Evaluation

| ID | Strategy | Description |
|---|---|---|
| **S1** | Prompt Adaptation | Schema chunking + guided decoding (XGrammar via vLLM) to reduce tokens per query |
| **S2** | LLM Approximation | QLoRA fine-tuning of Phi-4-Mini (3.8B) on the EPD gold standard |
| **S3** | LLM Cascade | Route queries through fine-tuned SLM → mid-tier local → frontier cloud based on confidence |

All three are evaluated individually and in combination.

## Baselines

| ID | Baseline | Purpose |
|---|---|---|
| **A** | Firstplanit production (Gemini 2.5 Flash) | Primary comparison target |
| **B** | Frontier cloud reference (Claude Sonnet / GPT-4o / Gemini 2.5 Pro) | Upper-bound reference; run in both text and native PDF modes to isolate preprocessing effects |
| **C** | Zero-shot local SLM (Phi-4-Mini 3.8B) | Lower-bound reference; no domain adaptation |

---

## Repository Structure

```
├── src/
│   ├── preprocessing/      # Docling PDF → structured text + table markdown
│   └── evaluation/         # Per-field F1 harness (metrics, harness, report, utils)
├── scripts/
│   ├── run_baseline_b.py   # Frontier cloud baselines (text + native PDF modes)
│   ├── run_baseline_c.py   # Zero-shot local SLM baseline
│   ├── create_gold_standard.py  # Reproducible clean/quarantine split
│   └── corpus_audit.py     # PDF complexity audit
├── data/
│   ├── gold_standard/      # 18 verified records (clean) + 25 quarantined
│   ├── preprocessed/       # Docling JSON sidecars (one per PDF)
│   ├── corpus_audit/       # Per-PDF complexity audit CSV
│   └── results/            # Baseline and strategy outputs; pareto.csv
├── configs/                # Model and pipeline configuration (forthcoming)
├── notebooks/              # Exploratory analysis
├── figures/                # Plots for dissertation
├── requirements.txt        # Annotated Python dependencies
└── PROJECT_LOG.md          # Full session-by-session development log
```

---

## Setup

**Requirements:** Python 3.10+, WSL or Linux recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify installation (21 packages):
```bash
python scripts/check_install.py
```

Copy `.env.example` to `.env` and add your API keys:
```
HF_TOKEN=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
```

**GPU note:** Local inference (Baseline C, S2, S3) requires a CUDA-capable GPU. Tested on Quadro RTX 4000 (8GB VRAM) with CUDA 13.1. Phi-4-Mini in 4-bit quantisation uses ~2.5GB VRAM.

---

## Running the Pipeline

### 1. Preprocess PDFs (Docling)

Converts all EPDs to structured text + table markdown. Resumable — skips already-processed files.

```bash
python src/preprocessing/docling_pipeline.py
```

Output: `data/preprocessed/<stem>.json` per PDF.

### 2. Baseline C — Zero-shot local SLM

```bash
# Full run (14 records with sidecars)
python scripts/run_baseline_c.py

# Smoke test on one record
python scripts/run_baseline_c.py --only "EPD-IES-0003985:002.pdf"

# Alternate model
python scripts/run_baseline_c.py --model "Qwen/Qwen2.5-3B-Instruct"
```

### 3. Baseline B — Frontier cloud reference

```bash
# Both text (Docling-preprocessed) and native PDF modes
python scripts/run_baseline_b.py --model claude-sonnet --mode both

# Single mode
python scripts/run_baseline_b.py --model gpt-4o --mode text
python scripts/run_baseline_b.py --model gemini-2.5-pro --mode native
```

Results and Pareto rows are written to `data/results/`.

---

## Evaluation

The harness in `src/evaluation/` computes per-field F1 disaggregated by:

- **Overall** — all fields
- **Populated** — fields where the gold value is not N/A (accuracy on real data)
- **N/A** — fields the model correctly identifies as not applicable
- **Metadata** — product and manufacturer fields
- **LCA** — the life cycle indicator matrix (GWP, PERT, PENRT, etc.)

Numeric fields are matched with ±1% relative tolerance. String fields are matched after Unicode normalisation (handles CO₂/CO2, m³/m3 variants). List fields (certifications, tags) use set-based F1.

---

## Data and Confidentiality

The EPD corpus and extraction schema were provided by Firstplanit under a research agreement. The full field schema, raw corpus, and production pipeline details are not disclosed in this repository. The gold standard (`data/gold_standard/`) contains 18 verified records used for evaluation and is shared in aggregated/anonymised form only.

See `data/gold_standard/GROUND_TRUTH_HANDOFF.md` for the full audit rationale and known data quality issues.

---

## Status

| Component | Status |
|---|---|
| Corpus audit (43 PDFs) | ✅ Complete |
| Gold standard construction | ✅ Complete — 18 clean / 25 quarantined |
| Docling preprocessing | ✅ Complete — 40/42 PDFs; 14/18 gold records runnable |
| Evaluation harness | ✅ Complete |
| Baseline B (frontier cloud) | 🔄 In progress |
| Baseline C (zero-shot SLM) | 🔄 In progress |
| Baseline A (Firstplanit re-run) | ⏳ Pending |
| S1 — Prompt adaptation | ⏳ Pending |
| S2 — QLoRA fine-tuning | ⏳ Pending |
| S3 — Cascade | ⏳ Pending |

---

## Citation

If referencing this work:

> Xu, E. (2026). *Frugal AI for Structured Data Extraction from Environmental Product Declarations*. MSc Computing Dissertation, Imperial College London.
