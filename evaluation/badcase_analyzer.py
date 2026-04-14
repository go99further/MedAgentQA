"""
badcase_analyzer.py
===================
Failure-mode classification and cross-version regression detection for
MedAgentQA evaluations.

Classifies each evaluated sample into one of four failure modes:

1. **retrieval_failure** -- context_recall == 0 (nothing relevant retrieved)
2. **routing_failure**   -- expected route != actual route
3. **hallucination**     -- faithfulness < 0.5 (answer contradicts context)
4. **knowledge_gap**     -- key entities from the reference answer are absent
   from retrieved contexts

Additionally provides two cross-version analysis functions:

* **version_diff_analysis** -- find Pass -> Fail regressions (negative churn)
* **source_shift_detection** -- compare clinical vs community source ratios

Usage::

    python -m evaluation.badcase_analyzer \\
        --results data/eval/results_v0_baseline.json \\
        --prev-results data/eval/results_v1_prompt.json
"""

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("badcase_analyzer")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "eval"
BADCASE_DIR = RESULTS_DIR / "badcases"

# ---------------------------------------------------------------------------
# Route expectations  (mirrors custom_metrics._DEFAULT_ROUTE_MAP)
# ---------------------------------------------------------------------------
_DEFAULT_ROUTE_MAP: Dict[str, str] = {
    "internal_medicine": "kb-query",
    "surgery": "kb-query",
    "pediatrics": "kb-query",
    "obstetrics": "kb-query",
    "dermatology": "kb-query",
    "ophthalmology": "kb-query",
    "psychiatry": "kb-query",
    "oncology": "graphrag-query",
    "pharmacology": "graphrag-query",
    "general": "general-query",
    "unknown": "kb-query",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_results(path: Path) -> Dict[str, Any]:
    """Load a results JSON file produced by ``ragas_eval.save_results``."""
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _extract_entities(text: str) -> Set[str]:
    """Extract a rough set of medical-ish named entities from *text*.

    Uses simple heuristics: CJK token sequences of 2--6 chars that look like
    medical terms, plus Latin medical terms (capitalized multi-char words).
    This is intentionally lightweight; plug in a real NER model for production.
    """
    entities: Set[str] = set()

    # Chinese medical terms (2-6 character sequences)
    for m in re.finditer(r"[\u4e00-\u9fff]{2,6}", text):
        entities.add(m.group())

    # English medical terms (capitalized, 4+ chars, not common stop-words)
    _stopwords = {
        "This", "That", "With", "From", "Have", "Your", "What",
        "When", "Where", "Which", "About", "After", "Before",
        "Should", "Could", "Would", "Please", "These", "Those",
        "There", "Their", "Other",
    }
    for m in re.finditer(r"\b[A-Z][a-z]{3,}\b", text):
        word = m.group()
        if word not in _stopwords:
            entities.add(word)

    return entities


def _build_per_sample_index(
    results: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    """Index per-sample RAGAS scores by question_id for fast lookup."""
    index: Dict[int, Dict[str, Any]] = {}
    per_sample = results.get("ragas", {}).get("per_sample", [])
    for sample in per_sample:
        qid = sample.get("question_id")
        if qid is not None:
            index[int(qid)] = sample
    return index


# ---------------------------------------------------------------------------
# Failure mode classification
# ---------------------------------------------------------------------------


class FailureMode:
    RETRIEVAL_FAILURE = "retrieval_failure"
    ROUTING_FAILURE = "routing_failure"
    HALLUCINATION = "hallucination"
    KNOWLEDGE_GAP = "knowledge_gap"


def classify_failures(
    results: Dict[str, Any],
    *,
    route_map: Optional[Dict[str, str]] = None,
    faithfulness_threshold: float = 0.5,
    knowledge_gap_threshold: float = 0.3,
) -> Dict[str, Any]:
    """Classify each evaluated sample into failure modes.

    Parameters
    ----------
    results:
        Loaded results dict from ``ragas_eval.save_results``.
    route_map:
        Department -> expected route mapping.
    faithfulness_threshold:
        Samples with faithfulness below this are classified as hallucination.
    knowledge_gap_threshold:
        If fewer than this fraction of reference-answer entities appear in
        retrieved contexts, it is a knowledge gap.

    Returns
    -------
    dict with per-mode lists and summary counts.
    """
    route_map = route_map or _DEFAULT_ROUTE_MAP
    per_sample_scores = _build_per_sample_index(results)
    responses = results.get("responses", [])

    failures: Dict[str, List[Dict[str, Any]]] = {
        FailureMode.RETRIEVAL_FAILURE: [],
        FailureMode.ROUTING_FAILURE: [],
        FailureMode.HALLUCINATION: [],
        FailureMode.KNOWLEDGE_GAP: [],
    }
    pass_list: List[int] = []

    for resp in responses:
        qid = resp.get("question_id", 0)
        scores = per_sample_scores.get(qid, {})
        modes_hit: List[str] = []

        # 1. Retrieval failure
        ctx_recall = scores.get("context_recall")
        if ctx_recall is not None and float(ctx_recall) == 0.0:
            failures[FailureMode.RETRIEVAL_FAILURE].append(
                {
                    "question_id": qid,
                    "question": resp.get("question", ""),
                    "context_recall": 0.0,
                    "retrieved_contexts": resp.get("retrieved_contexts", []),
                }
            )
            modes_hit.append(FailureMode.RETRIEVAL_FAILURE)

        # 2. Routing failure
        dept = str(resp.get("department", resp.get("metadata", {}).get("department", "unknown")))
        dept_lower = dept.lower().strip()
        expected_route = route_map.get(dept_lower, "kb-query")
        actual_route = str(resp.get("route_type", "")).lower().strip()
        if actual_route and actual_route != expected_route:
            failures[FailureMode.ROUTING_FAILURE].append(
                {
                    "question_id": qid,
                    "question": resp.get("question", ""),
                    "department": dept,
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                }
            )
            modes_hit.append(FailureMode.ROUTING_FAILURE)

        # 3. Hallucination
        faith = scores.get("faithfulness")
        if faith is not None and float(faith) < faithfulness_threshold:
            failures[FailureMode.HALLUCINATION].append(
                {
                    "question_id": qid,
                    "question": resp.get("question", ""),
                    "answer": resp.get("answer", ""),
                    "faithfulness": round(float(faith), 4),
                }
            )
            modes_hit.append(FailureMode.HALLUCINATION)

        # 4. Knowledge gap
        ref_answer = resp.get("ground_truth", "")
        contexts = resp.get("retrieved_contexts", [])
        if ref_answer and contexts:
            ref_entities = _extract_entities(ref_answer)
            if ref_entities:
                context_text = " ".join(str(c) for c in contexts)
                context_entities = _extract_entities(context_text)
                covered = ref_entities & context_entities
                coverage = len(covered) / len(ref_entities)
                if coverage < knowledge_gap_threshold:
                    failures[FailureMode.KNOWLEDGE_GAP].append(
                        {
                            "question_id": qid,
                            "question": resp.get("question", ""),
                            "missing_entities": sorted(ref_entities - context_entities),
                            "entity_coverage": round(coverage, 4),
                        }
                    )
                    modes_hit.append(FailureMode.KNOWLEDGE_GAP)

        if not modes_hit:
            pass_list.append(qid)

    summary = {
        "total_samples": len(responses),
        "total_pass": len(pass_list),
        "total_fail": len(responses) - len(pass_list),
        "failure_counts": {mode: len(cases) for mode, cases in failures.items()},
    }

    return {
        "summary": summary,
        "failures": failures,
        "pass_ids": pass_list,
    }


# ---------------------------------------------------------------------------
# Cross-version analysis: negative churn (Pass -> Fail regression)
# ---------------------------------------------------------------------------


def version_diff_analysis(
    old_results: Dict[str, Any],
    new_results: Dict[str, Any],
    *,
    faithfulness_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Compare two versions and find Pass -> Fail regressions (negative churn).

    A sample is considered "pass" if faithfulness >= threshold AND
    context_recall > 0.

    Parameters
    ----------
    old_results / new_results:
        Results dicts from ``ragas_eval.save_results``.
    faithfulness_threshold:
        Threshold for the pass/fail boundary.

    Returns
    -------
    dict with ``regressions`` (Pass -> Fail), ``improvements`` (Fail -> Pass),
    ``stable_pass``, ``stable_fail``, and ``churn_rate``.
    """

    def _pass_set(results: Dict[str, Any]) -> Dict[int, bool]:
        """Return {question_id: is_pass} for every sample."""
        per_sample = _build_per_sample_index(results)
        verdicts: Dict[int, bool] = {}
        for resp in results.get("responses", []):
            qid = resp.get("question_id", 0)
            scores = per_sample.get(qid, {})
            faith = scores.get("faithfulness")
            recall = scores.get("context_recall")
            is_pass = True
            if faith is not None and float(faith) < faithfulness_threshold:
                is_pass = False
            if recall is not None and float(recall) == 0.0:
                is_pass = False
            verdicts[qid] = is_pass
        return verdicts

    old_verdicts = _pass_set(old_results)
    new_verdicts = _pass_set(new_results)

    common_ids = set(old_verdicts) & set(new_verdicts)

    regressions: List[int] = []  # Pass -> Fail
    improvements: List[int] = []  # Fail -> Pass
    stable_pass: List[int] = []
    stable_fail: List[int] = []

    for qid in sorted(common_ids):
        old_p = old_verdicts[qid]
        new_p = new_verdicts[qid]
        if old_p and not new_p:
            regressions.append(qid)
        elif not old_p and new_p:
            improvements.append(qid)
        elif old_p and new_p:
            stable_pass.append(qid)
        else:
            stable_fail.append(qid)

    n_common = len(common_ids)
    churn_rate = round(len(regressions) / n_common, 4) if n_common else 0.0

    # Build detailed regression records
    new_per_sample = _build_per_sample_index(new_results)
    old_per_sample = _build_per_sample_index(old_results)
    regression_details: List[Dict[str, Any]] = []
    for qid in regressions:
        old_scores = old_per_sample.get(qid, {})
        new_scores = new_per_sample.get(qid, {})
        regression_details.append(
            {
                "question_id": qid,
                "old_faithfulness": old_scores.get("faithfulness"),
                "new_faithfulness": new_scores.get("faithfulness"),
                "old_context_recall": old_scores.get("context_recall"),
                "new_context_recall": new_scores.get("context_recall"),
            }
        )

    return {
        "old_version": old_results.get("version", "unknown"),
        "new_version": new_results.get("version", "unknown"),
        "n_common": n_common,
        "n_regressions": len(regressions),
        "n_improvements": len(improvements),
        "n_stable_pass": len(stable_pass),
        "n_stable_fail": len(stable_fail),
        "negative_churn_rate": churn_rate,
        "regressions": regression_details,
        "improvement_ids": improvements,
    }


# ---------------------------------------------------------------------------
# Cross-version analysis: source shift detection
# ---------------------------------------------------------------------------


def source_shift_detection(
    old_results: Dict[str, Any],
    new_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare clinical vs community source ratios across two versions.

    Uses the lightweight chunk classifier from ``custom_metrics``.
    """
    # Import here to avoid circular dependency at module level
    from evaluation.custom_metrics import source_quality_score

    def _compute_ratios(results: Dict[str, Any]) -> Dict[str, Any]:
        responses = results.get("responses", [])
        sq = source_quality_score(responses)
        return {
            "mean_clinical_ratio": sq["mean_clinical_ratio"],
            "total_chunks": sq["total_chunks"],
            "total_clinical": sq["total_clinical"],
            "total_community": sq["total_community"],
        }

    old_ratios = _compute_ratios(old_results)
    new_ratios = _compute_ratios(new_results)

    delta = round(
        new_ratios["mean_clinical_ratio"] - old_ratios["mean_clinical_ratio"], 4
    )

    return {
        "old_version": old_results.get("version", "unknown"),
        "new_version": new_results.get("version", "unknown"),
        "old_source_ratios": old_ratios,
        "new_source_ratios": new_ratios,
        "clinical_ratio_delta": delta,
        "shift_direction": (
            "improved" if delta > 0.02
            else "degraded" if delta < -0.02
            else "stable"
        ),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_badcase_report(
    results_path: Path,
    *,
    prev_results_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    route_map: Optional[Dict[str, str]] = None,
) -> Path:
    """Generate a comprehensive badcase report and save to disk.

    Parameters
    ----------
    results_path:
        Path to the current version's results JSON.
    prev_results_path:
        Optional path to a previous version for regression analysis.
    output_dir:
        Where to write the report (default: ``data/eval/badcases/``).
    route_map:
        Custom department -> route mapping.

    Returns
    -------
    Path to the generated report file.
    """
    output_dir = output_dir or BADCASE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    results = _load_results(results_path)
    version = results.get("version", "unknown")

    # Classify failures
    failure_report = classify_failures(results, route_map=route_map)

    # Build full report
    report: Dict[str, Any] = {
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failure_analysis": failure_report,
    }

    # Cross-version analysis (if previous results provided)
    if prev_results_path is not None:
        try:
            prev_results = _load_results(prev_results_path)
            report["version_diff"] = version_diff_analysis(prev_results, results)
            report["source_shift"] = source_shift_detection(prev_results, results)
        except Exception as exc:
            logger.error("Cross-version analysis failed: %s", exc)
            report["version_diff_error"] = str(exc)

    # Write report
    report_path = output_dir / f"badcase_report_{version}.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    logger.info("Badcase report saved to %s", report_path)

    # Also write a human-readable summary
    summary_path = output_dir / f"badcase_summary_{version}.txt"
    _write_text_summary(report, summary_path)

    return report_path


def _write_text_summary(report: Dict[str, Any], path: Path) -> None:
    """Write a plain-text summary of the badcase report."""
    lines: List[str] = []
    lines.append(f"Badcase Analysis Report -- {report['version']}")
    lines.append(f"Generated: {report.get('generated_at', 'N/A')}")
    lines.append("=" * 60)

    fa = report.get("failure_analysis", {})
    summary = fa.get("summary", {})
    lines.append(f"\nTotal samples:  {summary.get('total_samples', 'N/A')}")
    lines.append(f"Total pass:     {summary.get('total_pass', 'N/A')}")
    lines.append(f"Total fail:     {summary.get('total_fail', 'N/A')}")
    lines.append("\nFailure breakdown:")
    for mode, count in summary.get("failure_counts", {}).items():
        lines.append(f"  {mode:25s} {count}")

    # Top examples per failure mode
    failures = fa.get("failures", {})
    for mode, cases in failures.items():
        if not cases:
            continue
        lines.append(f"\n--- {mode} (showing up to 5) ---")
        for case in cases[:5]:
            qid = case.get("question_id", "?")
            question = case.get("question", "")[:80]
            lines.append(f"  [Q{qid}] {question}")
            for k, v in case.items():
                if k not in ("question_id", "question"):
                    lines.append(f"         {k}: {v}")

    # Version diff
    vd = report.get("version_diff")
    if vd:
        lines.append("\n" + "=" * 60)
        lines.append(
            f"Version diff: {vd['old_version']} -> {vd['new_version']}"
        )
        lines.append(f"  Regressions (Pass->Fail): {vd['n_regressions']}")
        lines.append(f"  Improvements (Fail->Pass): {vd['n_improvements']}")
        lines.append(f"  Negative churn rate: {vd['negative_churn_rate']}")

    # Source shift
    ss = report.get("source_shift")
    if ss:
        lines.append(f"\nSource shift: {ss['shift_direction']}")
        lines.append(
            f"  Clinical ratio: "
            f"{ss['old_source_ratios']['mean_clinical_ratio']} -> "
            f"{ss['new_source_ratios']['mean_clinical_ratio']} "
            f"(delta={ss['clinical_ratio_delta']})"
        )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Text summary saved to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze evaluation badcases and detect regressions."
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="Path to the results JSON file.",
    )
    parser.add_argument(
        "--prev-results",
        type=str,
        default=None,
        help="Path to previous version's results JSON (for regression analysis).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for badcase reports.",
    )
    args = parser.parse_args()

    generate_badcase_report(
        results_path=Path(args.results),
        prev_results_path=Path(args.prev_results) if args.prev_results else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )


if __name__ == "__main__":
    main()
