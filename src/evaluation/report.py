"""Console summary and CSV export for evaluation results."""

from __future__ import annotations

import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.evaluation.harness import RecordScore

console = Console()


def print_summary(scores: list[RecordScore], model_name: str) -> None:
    """Print a rich table with per-record F1 breakdown and dataset averages."""
    table = Table(title=f"Evaluation results — {model_name}", show_footer=True)

    cols = [
        ("file_name", "left"),
        ("F1 overall", "right"),
        ("F1 populated", "right"),
        ("F1 N/A", "right"),
        ("F1 metadata", "right"),
        ("F1 LCA", "right"),
        ("schema ✓", "center"),
    ]

    def avg(vals: list[float]) -> str:
        return f"{sum(vals)/len(vals):.3f}" if vals else "—"

    f1_overall   = [s.f1_overall   for s in scores]
    f1_populated = [s.f1_populated for s in scores]
    f1_na        = [s.f1_na        for s in scores]
    f1_metadata  = [s.f1_metadata  for s in scores]
    f1_lca       = [s.f1_lca       for s in scores]
    schema_ok    = [s.schema_valid  for s in scores]

    footers = [
        "AVERAGE",
        avg(f1_overall),
        avg(f1_populated),
        avg(f1_na),
        avg(f1_metadata),
        avg(f1_lca),
        f"{sum(schema_ok)}/{len(schema_ok)}",
    ]

    for (header, justify), footer in zip(cols, footers):
        table.add_column(header, justify=justify, footer=footer)

    for s in scores:
        table.add_row(
            s.file_name or str(s.orig_index),
            f"{s.f1_overall:.3f}",
            f"{s.f1_populated:.3f}",
            f"{s.f1_na:.3f}",
            f"{s.f1_metadata:.3f}",
            f"{s.f1_lca:.3f}",
            "✓" if s.schema_valid else "✗",
        )

    console.print(table)


def to_csv(scores: list[RecordScore], path: Path, model_name: str) -> None:
    """Write per-record scores to a CSV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model", "file_name", "orig_index",
        "f1_overall", "f1_populated", "f1_na", "f1_metadata", "f1_lca",
        "schema_valid",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in scores:
            writer.writerow({
                "model": model_name,
                "file_name": s.file_name,
                "orig_index": s.orig_index,
                "f1_overall": round(s.f1_overall, 4),
                "f1_populated": round(s.f1_populated, 4),
                "f1_na": round(s.f1_na, 4),
                "f1_metadata": round(s.f1_metadata, 4),
                "f1_lca": round(s.f1_lca, 4),
                "schema_valid": s.schema_valid,
            })


def to_summary_row(
    scores: list[RecordScore],
    model_name: str,
    cost_usd: float = 0.0,
    latency_s: float = 0.0,
) -> dict:
    """
    Return a single summary row for appending to data/results/pareto.csv.
    cost_usd and latency_s are totals across the dataset (caller provides these).
    """
    def avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    n = len(scores)
    return {
        "model": model_name,
        "n_records": n,
        "f1_overall": round(avg([s.f1_overall for s in scores]), 4),
        "f1_populated": round(avg([s.f1_populated for s in scores]), 4),
        "f1_na": round(avg([s.f1_na for s in scores]), 4),
        "f1_metadata": round(avg([s.f1_metadata for s in scores]), 4),
        "f1_lca": round(avg([s.f1_lca for s in scores]), 4),
        "schema_valid_pct": round(sum(s.schema_valid for s in scores) / n * 100, 1) if n else 0.0,
        "cost_usd_total": round(cost_usd, 6),
        "cost_usd_per_record": round(cost_usd / n, 6) if n else 0.0,
        "latency_s_total": round(latency_s, 2),
        "latency_s_per_record": round(latency_s / n, 2) if n else 0.0,
    }
