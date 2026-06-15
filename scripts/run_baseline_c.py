"""
Baseline C: zero-shot EPD extraction with a local SLM.

Loads a HuggingFace instruction-tuned model (default: Phi-4-mini-instruct),
runs zero-shot JSON extraction on each preprocessed EPD, scores with the eval harness,
and appends a Pareto row to data/results/pareto.csv.

Usage:
    python scripts/run_baseline_c.py                          # full run (14 records)
    python scripts/run_baseline_c.py --only "EPD-IES-0003985:002.pdf"  # smoke test
    python scripts/run_baseline_c.py --model "Qwen/Qwen2.5-3B-Instruct"  # alternate model
"""

import csv
import json
import re
import time
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.evaluation.harness import evaluate_dataset
from src.evaluation.metrics import LCA_INDICATORS, SKIP_FIELDS
from src.evaluation.report import print_summary, to_csv, to_summary_row
from src.evaluation.utils import resolve_pdf_stem

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "microsoft/Phi-4-mini-instruct"
DEFAULT_PREPROCESSED = PROJECT_ROOT / "data" / "preprocessed"
DEFAULT_GOLD = PROJECT_ROOT / "data" / "gold_standard" / "epd_gold_clean.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "results" / "baseline_c"
PARETO_CSV = PROJECT_ROOT / "data" / "results" / "pareto.csv"

LCA_STAGES = [
    "A1", "A2", "A3", "A1-A3",
    "A4", "A5", "A4-A5",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B1-B7",
    "C1", "C2", "C3", "C4", "C1-C4",
    "D", "Unit",
]


def get_flat_fields(gold_records: list[dict]) -> list[str]:
    """Collect ordered flat field names across all gold records (skip provenance + LCA dicts)."""
    seen: set[str] = set()
    fields: list[str] = []
    for rec in gold_records:
        for k in rec:
            if k not in seen and k not in SKIP_FIELDS and k not in LCA_INDICATORS:
                seen.add(k)
                fields.append(k)
    return fields


def build_prompt(flat_fields: list[str], doc_text: str, tables: list[dict]) -> str:
    field_lines = "\n".join(f'  "{f}": "..."' for f in flat_fields)
    lca_stage_str = ", ".join(LCA_STAGES)
    lca_ind_str = ", ".join(sorted(LCA_INDICATORS))
    tables_md = (
        "\n\n".join(t["markdown"] for t in tables if t.get("markdown"))
        if tables else "(no tables extracted)"
    )

    return (
        "Extract all fields from the EPD document below.\n\n"
        "Return a JSON object with EXACTLY these flat string fields "
        "(use \"N/A\" for any field not found in the document):\n"
        f"{{\n{field_lines}\n}}\n\n"
        f"Also include these 12 nested LCA indicator objects ({lca_ind_str}),\n"
        f"each containing lifecycle stage keys: {lca_stage_str}\n"
        "(use \"N/A\" for stages not reported; Unit should be the exact string from the document).\n\n"
        f"EPD DOCUMENT:\n{doc_text}\n\n"
        f"TABLE DATA:\n{tables_md}\n\n"
        "Respond with ONLY the JSON object, no markdown fences or explanation."
    )


def extract_json(text: str) -> dict | None:
    """Extract the outermost JSON object from a model response."""
    # Try ```json ... ``` blocks first
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Fall back to first {...} in the response
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def append_pareto_row(row: dict, path: Path) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


app = typer.Typer(add_completion=False)


@app.command()
def main(
    model: str = typer.Option(DEFAULT_MODEL, help="HuggingFace model id"),
    preprocessed_dir: Path = typer.Option(DEFAULT_PREPROCESSED, help="Preprocessed JSON sidecars dir"),
    gold_path: Path = typer.Option(DEFAULT_GOLD, help="Gold standard JSON"),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT, help="Per-record prediction output dir"),
    max_new_tokens: int = typer.Option(8192, help="Max tokens to generate per record"),
    load_in_4bit: bool = typer.Option(True, "--load-in-4bit/--no-4bit", help="4-bit quantisation"),
    only: Optional[str] = typer.Option(None, help="Comma-separated file_names to run (smoke test)"),
) -> None:
    """Baseline C — zero-shot local SLM extraction on the 18-record gold set."""
    load_dotenv(PROJECT_ROOT / ".env")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load gold
    all_gold: list[dict] = json.loads(gold_path.read_text())
    flat_fields = get_flat_fields(all_gold)

    gold = all_gold
    if only:
        only_set = {f.strip() for f in only.split(",")}
        gold = [r for r in all_gold if r.get("file_name") in only_set]
        logger.info(f"Filtered to {len(gold)} record(s): {only_set}")

    # Load model
    logger.info(f"Loading {model} (4-bit={load_in_4bit})")
    bnb_config = BitsAndBytesConfig(load_in_4bit=True) if load_in_4bit else None
    tokenizer = AutoTokenizer.from_pretrained(model)
    llm = AutoModelForCausalLM.from_pretrained(
        model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype="auto",
    )
    llm.eval()
    logger.info("Model ready.")

    predictions: list[dict] = []
    attempted_fnames: set[str] = set()
    skipped_fnames: set[str] = set()
    total_time = 0.0

    for gold_rec in gold:
        fname = gold_rec.get("file_name", "")
        stem = resolve_pdf_stem(fname, preprocessed_dir)

        if stem is None:
            logger.warning(f"No sidecar for {fname!r} — skipping (PDF missing or not preprocessed)")
            skipped_fnames.add(fname)
            continue

        sidecar: dict = json.loads((preprocessed_dir / f"{stem}.json").read_text())
        if not sidecar.get("success"):
            logger.warning(f"Sidecar for {fname!r} has success=False ({sidecar.get('error','')[:80]}) — skipping")
            skipped_fnames.add(fname)
            continue

        user_msg = build_prompt(flat_fields, sidecar["text"], sidecar.get("tables", []))
        messages = [
            {
                "role": "system",
                "content": "You are an expert EPD data extraction assistant. "
                           "Extract structured data from EPD documents and return valid JSON only.",
            },
            {"role": "user", "content": user_msg},
        ]

        input_ids = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(llm.device)
        n_input = input_ids.shape[1]
        logger.info(f"Generating for {fname!r} ({n_input} input tokens)...")

        t0 = time.time()
        output_ids = llm.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        elapsed = round(time.time() - t0, 1)
        total_time += elapsed

        raw_text = tokenizer.decode(output_ids[0][n_input:], skip_special_tokens=True)
        (output_dir / f"{stem}_raw.txt").write_text(raw_text, encoding="utf-8")

        parsed = extract_json(raw_text)
        if parsed is None:
            logger.warning(f"  JSON parse failed for {fname!r} — will score as all-MISSING")
            parsed = {}

        parsed["file_name"] = fname
        (output_dir / f"{stem}.json").write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        predictions.append(parsed)
        attempted_fnames.add(fname)
        logger.info(f"  {fname!r}: done in {elapsed}s")

    if skipped_fnames:
        logger.warning(f"Skipped {len(skipped_fnames)}: {sorted(skipped_fnames)}")

    if not predictions:
        logger.error("No predictions generated.")
        raise typer.Exit(1)

    # Evaluate against only the records we attempted
    gold_for_eval = [r for r in gold if r.get("file_name") in attempted_fnames]
    scores = evaluate_dataset(predictions, gold_for_eval)

    short_name = model.split("/")[-1].lower().replace("-instruct", "") + "-zero-shot"
    print_summary(scores, short_name)

    scores_csv = output_dir / "scores.csv"
    to_csv(scores, scores_csv, short_name)
    logger.info(f"Per-record scores → {scores_csv}")

    row = to_summary_row(scores, short_name, cost_usd=0.0, latency_s=total_time)
    PARETO_CSV.parent.mkdir(parents=True, exist_ok=True)
    append_pareto_row(row, PARETO_CSV)
    logger.info(f"Pareto row → {PARETO_CSV}")
    logger.info(f"Total inference time: {total_time:.1f}s for {len(predictions)} records")


if __name__ == "__main__":
    app()
