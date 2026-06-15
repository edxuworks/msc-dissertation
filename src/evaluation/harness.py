"""Record-level and dataset-level EPD extraction scoring."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from src.evaluation.metrics import (
    LCA_INDICATORS,
    LCA_SKIP_STAGES,
    LIST_FIELDS,
    SKIP_FIELDS,
    match_list,
    match_numeric,
    match_string,
)


@dataclass
class FieldScore:
    field: str       # e.g. "GWP-TOTAL.A1-A3" or "Product Name"
    category: str    # "metadata" | "lca_numeric" | "lca_unit" | "list"
    gold_value: str
    pred_value: str  # "MISSING" if key absent from prediction
    gold_is_na: bool
    match: float     # 0.0 or 1.0 for most fields; fractional for list fields


@dataclass
class RecordScore:
    orig_index: int
    file_name: str
    schema_valid: bool
    field_scores: list[FieldScore] = field(default_factory=list)

    def _f1(self, subset: list[FieldScore]) -> float:
        if not subset:
            return 0.0
        # Micro-averaged: each field contributes equally (TP=match, FP=1-match, FN=1-match)
        tp = sum(fs.match for fs in subset)
        fp = sum(1.0 - fs.match for fs in subset)
        fn = sum(1.0 - fs.match for fs in subset)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @property
    def f1_overall(self) -> float:
        return self._f1(self.field_scores)

    @property
    def f1_populated(self) -> float:
        return self._f1([fs for fs in self.field_scores if not fs.gold_is_na])

    @property
    def f1_na(self) -> float:
        return self._f1([fs for fs in self.field_scores if fs.gold_is_na])

    @property
    def f1_metadata(self) -> float:
        return self._f1([fs for fs in self.field_scores if fs.category == "metadata"])

    @property
    def f1_lca(self) -> float:
        return self._f1([
            fs for fs in self.field_scores
            if fs.category in {"lca_numeric", "lca_unit"}
        ])

    @property
    def f1_list(self) -> float:
        return self._f1([fs for fs in self.field_scores if fs.category == "list"])


def _check_schema_valid(pred: dict) -> bool:
    """All 12 LCA indicator keys must be present and each must be a dict with 'Unit'."""
    for indicator in LCA_INDICATORS:
        v = pred.get(indicator)
        if not isinstance(v, dict) or "Unit" not in v:
            return False
    return True


def evaluate_record(pred: dict, gold: dict) -> RecordScore:
    """Score one prediction dict against one gold dict."""
    orig_index = gold.get("_orig_index", -1)
    file_name = gold.get("file_name", "")
    schema_valid = _check_schema_valid(pred)
    scores: list[FieldScore] = []

    for key, gold_val in gold.items():
        if key in SKIP_FIELDS:
            continue

        if key in LCA_INDICATORS:
            if not isinstance(gold_val, dict):
                continue
            pred_indicator = pred.get(key, {})
            if not isinstance(pred_indicator, dict):
                pred_indicator = {}

            for stage, gold_stage_val in gold_val.items():
                if stage in LCA_SKIP_STAGES:
                    continue
                field_name = f"{key}.{stage}"
                pred_stage_val = pred_indicator.get(stage, "MISSING")
                gold_is_na = (str(gold_stage_val).strip().upper() == "N/A")

                if stage == "Unit":
                    m = match_string(str(pred_stage_val), str(gold_stage_val))
                    scores.append(FieldScore(
                        field=field_name, category="lca_unit",
                        gold_value=str(gold_stage_val), pred_value=str(pred_stage_val),
                        gold_is_na=gold_is_na, match=float(m),
                    ))
                else:
                    m = match_numeric(str(pred_stage_val), str(gold_stage_val))
                    scores.append(FieldScore(
                        field=field_name, category="lca_numeric",
                        gold_value=str(gold_stage_val), pred_value=str(pred_stage_val),
                        gold_is_na=gold_is_na, match=float(m),
                    ))

        elif key in LIST_FIELDS:
            pred_val = pred.get(key, [])
            gold_list = gold_val if isinstance(gold_val, list) else []
            _, _, f1 = match_list(pred_val, gold_list)
            gold_is_na = len(gold_list) == 0
            scores.append(FieldScore(
                field=key, category="list",
                gold_value=str(gold_val), pred_value=str(pred_val),
                gold_is_na=gold_is_na, match=f1,
            ))

        else:
            pred_val = pred.get(key, "MISSING")
            gold_is_na = (str(gold_val).strip().upper() == "N/A")
            m = match_string(str(pred_val), str(gold_val))
            scores.append(FieldScore(
                field=key, category="metadata",
                gold_value=str(gold_val), pred_value=str(pred_val),
                gold_is_na=gold_is_na, match=float(m),
            ))

    return RecordScore(
        orig_index=orig_index,
        file_name=file_name,
        schema_valid=schema_valid,
        field_scores=scores,
    )


def evaluate_dataset(predictions: list[dict], gold: list[dict]) -> list[RecordScore]:
    """
    Score a list of predictions against gold records, matched by file_name.
    Unmatched gold records are scored as all-MISSING (zero F1).
    """
    pred_by_file = {r.get("file_name", ""): r for r in predictions}
    scores = []
    for gold_rec in gold:
        fname = gold_rec.get("file_name", "")
        pred_rec = pred_by_file.get(fname)
        if pred_rec is None:
            warnings.warn(f"No prediction found for file_name={fname!r} — scoring as all-MISSING")
            pred_rec = {}
        scores.append(evaluate_record(pred_rec, gold_rec))

    unmatched = set(pred_by_file) - {g.get("file_name", "") for g in gold}
    for fname in unmatched:
        warnings.warn(f"Prediction for {fname!r} has no matching gold record — ignored")

    return scores
