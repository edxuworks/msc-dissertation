# Skills, Best Practices & Reference Inspirations
## For: Frugal AI EPD Extraction Pipeline (MSc Dissertation)

This file captures distilled best practices, code patterns, and methodological inspiration drawn from the literature and reference implementations explored during the project. Each entry is sourced and cross-referenced. Update this file whenever a new technique is adopted, validated, or ruled out.

---

## Table of Contents
1. [Constrained / Guided Generation](#1-constrained--guided-generation)
2. [PDF Parsing & Document Cleaning](#2-pdf-parsing--document-cleaning)
3. [Chunking & Context Window Strategy](#3-chunking--context-window-strategy)
4. [Fine-Tuning (QLoRA)](#4-fine-tuning-qlora)
5. [Prompting Strategy Hierarchy](#5-prompting-strategy-hierarchy)
6. [Evaluation Methodology](#6-evaluation-methodology)
7. [Vision-Language Models (VLMs)](#7-vision-language-models-vlms)
8. [Cascade & Routing Architecture](#8-cascade--routing-architecture)
9. [Agents for Extraction](#9-agents-for-extraction)
10. [Cost & Energy Tracking](#10-cost--energy-tracking)

---

## 1. Constrained / Guided Generation

### Core principle
Force structured output at the token level so every response is schema-valid JSON — eliminating parse errors and format repair overhead.

### Best practice: Pydantic schema first
Define the extraction target as a `pydantic.BaseModel` before writing any prompt. The schema IS the specification.

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class LifecycleStages(BaseModel):
    A1: Optional[str] = None
    A2: Optional[str] = None
    A3: Optional[str] = None
    A1_A3: Optional[str] = Field(None, alias="A1-A3")
    A4: Optional[str] = None
    C1_C4: Optional[str] = None
    D: Optional[str] = None

class EPDExtraction(BaseModel):
    product_name: str
    gwp_total: LifecycleStages
    gwp_fossil: LifecycleStages
    acidification: LifecycleStages
    # ... etc
```

### Library options
| Library | Mechanism | When to use |
|---|---|---|
| `instructor` | Wraps OpenAI/Anthropic function-calling; enforces Pydantic model | Cloud API calls (Baselines A & B) |
| `XGrammar` (via vLLM) | Grammar-constrained token masking; up to 100× faster than earlier approaches | Local inference (SLM tier) |
| `outlines` | Alternative grammar-constrained generation | Fallback if XGrammar unavailable |

### Critical warning: constraints + fine-tuning interaction
> ⚠️ **Fine-tuned models should NOT use few-shot prompts.** Matextract found that adding few-shot examples to a fine-tuned model *degraded* F1 from 0.9654 → 0.9604 because the model sees a prompt format different from training. Use fine-tuned models in zero-shot + constrained mode only.

**Sources:**
- matextract.pub §7 Constrained Generation — `instructor` library, Pydantic pattern
- matextract.pub §4 Fine-tuning — few-shot degradation finding
- Dong et al. XGrammar (arXiv:2411.15100) — cited in interim report [35]
- Tam et al. (arXiv:2408.02442) — format restrictions can hurt accuracy [52]

---

## 2. PDF Parsing & Document Cleaning

### Tool selection guide
| Document type | Recommended tool | Notes |
|---|---|---|
| Modern native PDF, table-heavy | **Docling** (IBM, primary choice) or **marker** | Docling integrates TableFormer (98.5% TED simple, 95% complex tables) |
| Scanned / image PDF | **Tesseract** (fallback) or **PaddleOCR** | Must detect scan before attempting text extraction |
| Multi-language PDF | Docling + language detection | Flags non-English EPDs for routing decision |
| Very old / complex tables | **Vision model** (VLM path) | Rule: if Docling table extraction fails, escalate to VLM |

### Silent failure trap (critical for EPD pipeline)
PyMuPDF silently returns empty strings on scanned PDFs without raising an error. **Always check** if extracted text length is suspiciously low — if so, assume scan and trigger OCR fallback.

```python
import fitz  # pymupdf

def extract_or_flag_scan(pdf_path: str) -> tuple[str, bool]:
    doc = fitz.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    is_scanned = len(text.strip()) < 100  # threshold to tune
    return text, is_scanned
```

### Document cleaning pipeline (post-parse)
1. **Regex first pass** — remove page numbers, headers/footers, references sections, licensing text
2. **Collapse excessive whitespace** — normalize newlines
3. **Table isolation** — extract tables as separate chunks before sending to LLM (improves extraction quality)
4. **LLM-assisted cleaning** — only if regex pass insufficient (adds latency + cost)

```python
import re

def clean_document(text: str) -> str:
    # Remove everything before Introduction and after Acknowledgements/References
    text = re.sub(r'\n{3,}', '\n\n', text)        # collapse excess newlines
    text = re.sub(r'Page \d+ of \d+', '', text)   # remove page markers
    return text.strip()
```

### Reviewing conversion quality is non-negotiable
> ⚠️ Matextract: "reviewing the quality and accuracy of the conversion at least partially afterward is crucial" regardless of tool. Build a spot-check step into the corpus audit.

**Sources:**
- matextract.pub §2.1 Document Parsing — docTR, nougat, marker comparison
- matextract.pub §2.2 Document Cleaning — regex patterns, LLM cleaning
- matextract.pub §10 Biomass case study — `marker` chosen for tables
- Docling technical report (arXiv:2408.09869) [47] — interim report primary reference
- PyMuPDF silent failure — interim report [25]

---

## 3. Chunking & Context Window Strategy

### Rule: always isolate tables into their own chunks
> Matextract biomass case study: "tables were isolated into individual chunks to improve extraction quality." For EPDs, where the 168-cell indicator×stage matrix IS the core payload, this is essential.

### Chunking strategy for EPDs
EPDs have a predictable structure — metadata upfront, LCA tables in the middle, supporting info at the end. Use structure-aware chunking rather than fixed-size:

```
Chunk 1: Product metadata (name, manufacturer, dates, scope)
Chunk 2: LCA indicator table — GWP, AP, EP, FW (A1-A3, A4-A5)
Chunk 3: LCA indicator table — B stages, C stages, D
Chunk 4: Resource use table (PERT, PENRT, PERE, PERM, etc.)
Chunk 5: Material composition + physical properties
```

This maps directly to S1 (Prompt Adaptation) schema chunking.

### Overlapping chunks for continuity
When tables span pages, use 15–20% overlap between adjacent chunks to avoid losing cross-page header context.

### RAG for large corpora (stretch goal)
For the full Firstplanit corpus (beyond the 43-document gold standard), RAG with vector embeddings (ChromaDB or FAISS) allows retrieval of only the relevant section before prompting — reducing token cost per document.

**Sources:**
- matextract.pub §3 Context Window — four chunking approaches, overlapping chunks, RAG
- matextract.pub §10 Biomass case study — table isolation finding
- Interim report §4.1.1 Strategy 1: Prompt Adaptation

---

## 4. Fine-Tuning (QLoRA)

### Validated configuration (from matextract.pub case study)
```python
# QLoRA config — validated on A100 40GB
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",       # nf4 for normally distributed weights
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

lora_config = LoraConfig(
    r=32,                             # rank — higher = more params but better fit
    lora_alpha=64,                    # alpha = 2×rank is standard
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

training_args = TrainingArguments(
    per_device_train_batch_size=2,    # max on 40GB A100
    gradient_accumulation_steps=8,   # effective batch = 16
    num_train_epochs=3,
    learning_rate=2e-4,
    fp16=True,
    ...
)
```

### Performance benchmarks from literature
| Approach | Model | F1 Score | Notes |
|---|---|---|---|
| Zero-shot | Llama-3 8B | 0.878 | Baseline |
| Few-shot (+1 example) | Llama-3 8B | 0.947 | +7% gain |
| QLoRA fine-tuned, zero-shot | Llama-3 8B | **0.965** | Best |
| QLoRA fine-tuned, few-shot | Llama-3 8B | 0.960 | ↓ worse than fine-tuned zero-shot |
| Zero-shot | GPT-4o | 0.902 | Frontier reference |
| Few-shot (+1 example) | GPT-4o | 0.958 | |

*(Source: matextract.pub §4, chemical reaction extraction domain)*

Also from Strata [18] (clinical domain):
- QLoRA fine-tuned Llama-3.1 8B → 90.0 ± 1.7 exact-match (human-level) with <100 training examples

### Key lessons
1. Fine-tuning beats few-shot prompting of the same base model
2. Fine-tuned models should be used zero-shot, not few-shot (format mismatch degrades performance)
3. `nf4` quant type preferred for normally distributed model weights
4. LoRA rank=32, alpha=64 is a solid starting point for structured extraction
5. <100 examples sufficient for domain adaptation (Strata); 5000 used in matextract (more complex task)
6. Hardware: A100 40GB + ~10 hours for matextract example; Imperial GPU cluster required

**Sources:**
- matextract.pub §4 Choosing the learning paradigm — benchmarks, config
- Liu et al. Strata (Scientific Reports 2025) [18] — <100 examples finding
- Hu et al. LoRA (ICLR 2022) [16]; Dettmers et al. QLoRA (arXiv:2305.14314) [17]

---

## 5. Prompting Strategy Hierarchy

### Tested strategies (from matextract biomass case study)
Ordered from simplest to most powerful for structured extraction:

| Strategy | Expected F1 | Cost | When to use |
|---|---|---|---|
| Naive zero-shot | Lowest | Lowest | Initial sanity check only |
| Zero-shot + detailed schema | ↑ | Low | Always include schema description |
| Zero-shot + constrained decoding | ↑↑ | Low | **Default for all runs** |
| Few-shot (2–4 examples) | ↑↑↑ | Medium | Non-fine-tuned models only |
| Chain of Thought (CoT) | ↑↑↑ | Higher | Complex multi-step reasoning |
| CoT + self-consistency | Highest | Highest | Difficult documents; also generates confidence signal |

### Self-consistency as confidence signal
CoT + self-consistency sampling (sample N completions, check agreement) serves dual purpose: improves accuracy AND produces a natural confidence signal for the cascade escalation decision.

```python
def self_consistency_extract(prompt, model, n_samples=5):
    responses = [model.generate(prompt) for _ in range(n_samples)]
    # Measure agreement across responses → confidence
    # Return majority vote + agreement score
    ...
```

### Schema description best practice
Always include field-level descriptions in the prompt schema, not just field names. For EPDs, this means explaining what each lifecycle stage means (A1=raw material supply, A2=transport to manufacturer, etc.).

**Sources:**
- matextract.pub §10 Biomass case study — 7-strategy comparison
- Wang et al. self-consistency (ICLR 2023) [53] — interim report reference
- matextract.pub §3 Context Window — chunking before prompting

---

## 6. Evaluation Methodology

### Primary metrics
Always report all three, disaggregated by field category:
- **Precision** = correctly extracted fields / all extracted fields
- **Recall** = correctly extracted fields / all ground truth fields  
- **F1** = harmonic mean

### Critical: disaggregate by field category
EPD evaluation must split fields into at minimum:
1. **Metadata fields** (product name, dates, operator) — exact match
2. **Numeric LCA fields** (GWP, AP, EP values) — tolerance-based match (±1% or ±0.001)
3. **N/A fields** — ~88/168 indicator×stage cells are validly N/A; report separately to avoid inflating accuracy
4. **Text/description fields** — fuzzy/semantic match

> ⚠️ A model returning N/A everywhere scores misleadingly high on naive accuracy. Always report metrics on the non-N/A subset separately.

### Handling nested structures: leaf-node counting
For nested dicts like `{"GWP-TOTAL": {"A1-A3": "4.39", "A4": "1.02", ...}}`, count leaf nodes (deepest values) for metric computation — not top-level keys.

```python
def count_leaf_nodes(d, count=0):
    if isinstance(d, dict):
        for v in d.values():
            count = count_leaf_nodes(v, count)
    elif isinstance(d, list):
        for item in d:
            count = count_leaf_nodes(item, count)
    else:
        count += 1
    return count
```

### Matching predictions to ground truth: DeepDiff + Hungarian algorithm
When multiple predicted records must be matched to ground truth (e.g. multi-product EPDs):
- **DeepDiff**: measures structural similarity between two dicts, normalized to [0,1]
- **Kuhn-Munkres (Hungarian algorithm)**: O(n³) optimal assignment — finds best pairing of predicted records to gold records

```python
from deepdiff import DeepDiff
from scipy.optimize import linear_sum_assignment

def match_predictions_to_gold(predictions, gold_records):
    # Build cost matrix using DeepDiff similarity
    n = len(predictions)
    m = len(gold_records)
    cost_matrix = np.zeros((n, m))
    for i, pred in enumerate(predictions):
        for j, gold in enumerate(gold_records):
            diff = DeepDiff(gold, pred, ignore_order=True)
            similarity = 1 - len(diff) / max(count_leaf_nodes(gold), 1)
            cost_matrix[i, j] = 1 - similarity  # cost = 1 - similarity
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return list(zip(row_ind, col_ind))
```

### Additional metrics (beyond matextract)
Per interim report §4.1.7:
- **Schema validity rate** — % outputs that are parseable JSON conforming to schema
- **Cost per document** — cloud API spend or amortised GPU-hour cost
- **p50 / p95 latency**
- **Energy use** — via `codecarbon`
- **Confidence calibration** — does stated confidence correlate with actual accuracy?

### LLM-as-judge: use cautiously
Matextract cautions: "the evaluator model has all the problems of the LLM used for extraction." Use human evaluation as primary ground truth; LLM-as-judge only as supplementary signal.

**Sources:**
- matextract.pub §8 Evaluations — precision/recall/F1, leaf-node counting, DeepDiff, Hungarian algorithm
- Interim report §4.1.7 Evaluation Framework
- deepdiff library: `pip install deepdiff`
- scipy.optimize.linear_sum_assignment (already installed)

---

## 7. Vision-Language Models (VLMs)

### When to use the VLM path
Standard LLMs + Docling is the default. Switch to VLM when:
- Docling table extraction returns garbled/empty output
- Document is scanned with complex table layout
- OCR produces obviously corrupted scientific notation

### Image preprocessing before VLM
```python
from PIL import Image
import base64, io

def prepare_page_image(page_img: Image.Image, max_size=2048) -> str:
    # 1. Correct orientation (use tesseract OSD or edge detection)
    # 2. Resize to max dimension
    ratio = max_size / max(page_img.size)
    if ratio < 1:
        page_img = page_img.resize([int(d * ratio) for d in page_img.size])
    # 3. Encode as base64 JPEG
    buf = io.BytesIO()
    page_img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()
```

### VLM options
| Model | Type | Notes |
|---|---|---|
| Qwen2.5-VL 3B/7B | Open-weight local | Primary choice for local VLM tier; deployable on consumer GPU |
| GPT-4o | Cloud | Frontier reference for VLM path |
| DeepSeek-VL | Open-weight | Alternative if Qwen unavailable |
| Claude (vision) | Cloud | Anthropic; strong on document understanding |

### Known limitation
Even VLMs fail on complex structured tables containing reaction schemes or highly nested data. Agentic approaches needed for worst cases.

**Sources:**
- matextract.pub §5 Beyond Text — VLM pipeline, orientation correction, GPT-4o/DeepSeek-VL
- Bai et al. Qwen2.5-VL (arXiv:2502.13923) [33] — interim report reference

---

## 8. Cascade & Routing Architecture

### FrugalGPT cascade loop pattern (from source code)
The core escalation loop from `llmcascade.py`:

```python
def get_completion(self, query, budget):
    while True:
        service_name, score_threshold = llm_chain.next_api_and_score()
        if service_name is None:
            break  # exhausted all tiers
        response = call_model(service_name, query)
        confidence = self.scorers[service_name].get_score(response)
        if confidence > (1 - score_threshold):
            break  # accept this response
        # else: continue to next tier
    return response
```

### Three-tier cascade for this project
```
Tier 1: Fine-tuned Phi-4-Mini (local, ~0 marginal cost)
    ↓ if confidence < threshold_1
Tier 2: Untuned mid-tier model (Qwen 2.5 7B, local)
    ↓ if confidence < threshold_2  
Tier 3: Frontier cloud (Claude / Gemini 2.5 Pro)
    → always accept
```

### Confidence signals to compare (empirical study in this project)
| Signal | How computed | Cost | Reliability |
|---|---|---|---|
| Token-level log-probability | Mean log-prob of output tokens | ~0 | Overconfident; well-studied |
| Self-consistency | Agreement across N=5 samples | 5× inference | More reliable; also improves accuracy |
| Semantic entropy | Entropy over semantic clusters of N samples | 5× inference | Best calibrated; complex to implement |

### Threshold optimisation (FrugalGPT optimizer pattern)
Use `scipy.optimize.brute` to sweep thresholds over the gold standard:

```python
from scipy.optimize import brute, fmin

def objective(thresholds, cost_matrix, loss_matrix, budget):
    # Simulate cascade with given thresholds
    # Return negative accuracy (minimise = maximise accuracy)
    total_cost = compute_cascade_cost(thresholds, cost_matrix)
    if total_cost > budget:
        return 0  # constraint violated
    return -compute_cascade_accuracy(thresholds, loss_matrix)

result = brute(objective, ranges, args=(C_mat, L_mat, budget), finish=fmin)
```

### Pareto frontier visualisation
Always plot cost vs accuracy across threshold sweeps — this IS the primary dissertation contribution, not just a single operating point.

**Sources:**
- FrugalGPT `llmcascade.py`, `optimizer.py`, `llmchain.py` (stanford-futuredata/FrugalGPT)
- Chen et al. FrugalGPT (arXiv:2305.05176) [5]
- Wang et al. self-consistency [53]; Kuhn et al. semantic uncertainty [54]; Farquhar et al. [55]
- Interim report §4.1.3 Strategy 3

---

## 9. Agents for Extraction

### When agents are worth the cost
- Matextract: agents "proved to improve vanilla models by far" for domain-specific data
- But: multiple sequential API calls → higher cost and latency
- Verdict for this project: agents are a **stretch goal** for the worst-case EPD tier (oldest scanned multi-product); not the primary path

### ReAct pattern (if implemented)
```
Thought: "This is a multi-product EPD. I need to identify which column belongs to product X."
Action: extract_table_column(product_id="X")
Observation: [column data]
Thought: "Now I can fill the GWP fields."
Action: fill_schema_fields(data=...)
```

**Sources:**
- matextract.pub §6 Agents — ReAct framework, LangChain tools

---

## 10. Cost & Energy Tracking

### Track from day one with codecarbon
```python
from codecarbon import EmissionsTracker

tracker = EmissionsTracker(project_name="epd_extraction", output_dir="data/results/")
tracker.start()
# ... run extraction ...
emissions = tracker.stop()  # returns kg CO2 equivalent
```

### Cost per document formula
```
Cloud cost = (input_tokens × input_price + output_tokens × output_price)
Local cost = GPU_hours × amortised_hardware_cost_per_hour
Cascade cost = weighted_average(tier_costs × tier_routing_fraction)
```

### Report cost AND energy, not just accuracy
Per Frugal AI framing: frugal claims must be made *net of implementation overhead* (the cascade router itself has a cost — include it).

**Sources:**
- codecarbon library (already installed)
- Interim report §4.1.7 Evaluation Framework — cost, latency, energy metrics
- Frugal AI Hub white papers [3,4] — interim report references

---

## Quick Reference: Key Numbers from Literature

| Finding | Value | Source |
|---|---|---|
| FrugalGPT cost reduction | Up to 98% vs GPT-4 at same quality | Chen et al. [5] |
| RouteLLM cost reduction | >2× at maintained quality | Ong et al. [6] |
| SATER cascade latency reduction | >80% | Shen et al. [19] |
| Strata accuracy (clinical fine-tune) | 90.0 ± 1.7 EM with <100 examples | Liu et al. [18] |
| matextract zero-shot Llama-3 8B | F1 = 0.878 | matextract.pub §4 |
| matextract few-shot (+1) Llama-3 8B | F1 = 0.947 (+7.9%) | matextract.pub §4 |
| matextract QLoRA fine-tuned Llama-3 8B | F1 = 0.965 | matextract.pub §4 |
| matextract zero-shot GPT-4o | F1 = 0.902 | matextract.pub §4 |
| Docling TableFormer (simple tables) | TED = 98.5% | Auer et al. [47] |
| Docling TableFormer (complex tables) | TED = 95% | Auer et al. [47] |
| XGrammar speedup vs earlier grammar tools | Up to 100× | Dong et al. [35] |

---

*Last updated: 2026-06-14*  
*Update this file whenever a new technique is adopted, benchmarked, or ruled out.*
