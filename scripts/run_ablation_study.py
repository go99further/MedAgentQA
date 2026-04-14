"""
run_ablation_study.py
=====================
Ablation study runner for MedAgentQA.

Defines six ablation versions that progressively enable system features,
runs the full RAGAS evaluation for each, and produces a comparison table.

Versions
--------
* **v0_baseline**     -- vanilla LLM, no retrieval, no routing, no prompts
* **v1_prompt**       -- + optimised medical prompts
* **v2_retrieval**    -- + vector-store retrieval (LightRAG / FAISS)
* **v3_router**       -- + intent-based query router
* **v4_rag_constraint** -- + RAG grounding constraints (hallucination guard)
* **vFinal_all**      -- all features enabled (production config)

Usage::

    python -m scripts.run_ablation_study [--max-concurrency 4] [--dry-run]
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("run_ablation_study")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "eval"
ABLATION_OUTPUT = RESULTS_DIR / "ablation_results.json"

# ---------------------------------------------------------------------------
# Ablation configuration
# ---------------------------------------------------------------------------

ABLATION_VERSIONS: List[Dict[str, Any]] = [
    {
        "version": "v0_baseline",
        "description": "Vanilla LLM -- no retrieval, no routing, no optimised prompts",
        "config": {
            "enable_retrieval": False,
            "enable_router": False,
            "enable_medical_prompts": False,
            "enable_rag_constraint": False,
            "enable_kg_lookup": False,
            "enable_reranker": False,
        },
    },
    {
        "version": "v1_prompt",
        "description": "Baseline + optimised medical system/user prompts",
        "config": {
            "enable_retrieval": False,
            "enable_router": False,
            "enable_medical_prompts": True,
            "enable_rag_constraint": False,
            "enable_kg_lookup": False,
            "enable_reranker": False,
        },
    },
    {
        "version": "v2_retrieval",
        "description": "v1 + vector-store retrieval (FAISS / LightRAG)",
        "config": {
            "enable_retrieval": True,
            "enable_router": False,
            "enable_medical_prompts": True,
            "enable_rag_constraint": False,
            "enable_kg_lookup": False,
            "enable_reranker": True,
        },
    },
    {
        "version": "v3_router",
        "description": "v2 + intent-based query router (kb / graphrag / general)",
        "config": {
            "enable_retrieval": True,
            "enable_router": True,
            "enable_medical_prompts": True,
            "enable_rag_constraint": False,
            "enable_kg_lookup": True,
            "enable_reranker": True,
        },
    },
    {
        "version": "v4_rag_constraint",
        "description": "v3 + RAG grounding constraints (hallucination guardrail)",
        "config": {
            "enable_retrieval": True,
            "enable_router": True,
            "enable_medical_prompts": True,
            "enable_rag_constraint": True,
            "enable_kg_lookup": True,
            "enable_reranker": True,
        },
    },
    {
        "version": "vFinal_all",
        "description": "All features enabled -- production configuration",
        "config": {
            "enable_retrieval": True,
            "enable_router": True,
            "enable_medical_prompts": True,
            "enable_rag_constraint": True,
            "enable_kg_lookup": True,
            "enable_reranker": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Markdown table generation
# ---------------------------------------------------------------------------


def _build_comparison_table(
    version_summaries: List[Dict[str, Any]],
) -> str:
    """Build a markdown comparison table from version summaries.

    Each summary should contain ``version``, ``description``, and
    ``ragas`` (dict with metric names -> float scores).
    """
    metric_names = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ]

    # Header
    header = "| Version | Description | " + " | ".join(metric_names) + " | Cost (USD) |"
    sep = "|" + "|".join(["---"] * (len(metric_names) + 3)) + "|"

    rows: List[str] = []
    for s in version_summaries:
        version = s.get("version", "?")
        desc = s.get("description", "")[:40]
        ragas = s.get("ragas", {})
        metrics = [str(ragas.get(m, "N/A")) for m in metric_names]
        cost = s.get("cost", {}).get("estimated_cost_usd", "N/A")
        row = f"| {version} | {desc} | " + " | ".join(metrics) + f" | {cost} |"
        rows.append(row)

    # Best-in-column markers
    best_row_parts = ["| **Best** | |"]
    for m in metric_names:
        values = []
        for s in version_summaries:
            v = s.get("ragas", {}).get(m)
            if v is not None:
                values.append((float(v), s["version"]))
        if values:
            best_val, best_ver = max(values, key=lambda x: x[0])
            best_row_parts.append(f" **{best_val}** ({best_ver}) |")
        else:
            best_row_parts.append(" N/A |")
    best_row_parts.append(" |")
    best_row = "".join(best_row_parts)

    return "\n".join([header, sep] + rows + [sep, best_row])


def _build_delta_table(
    version_summaries: List[Dict[str, Any]],
) -> str:
    """Build a delta table showing metric changes relative to baseline."""
    if len(version_summaries) < 2:
        return "(Not enough versions for delta comparison)"

    metric_names = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ]
    baseline = version_summaries[0].get("ragas", {})

    header = "| Version | " + " | ".join(f"d_{m}" for m in metric_names) + " |"
    sep = "|" + "|".join(["---"] * (len(metric_names) + 1)) + "|"

    rows: List[str] = []
    for s in version_summaries[1:]:
        version = s.get("version", "?")
        ragas = s.get("ragas", {})
        deltas: List[str] = []
        for m in metric_names:
            cur = ragas.get(m)
            base = baseline.get(m)
            if cur is not None and base is not None:
                d = float(cur) - float(base)
                sign = "+" if d >= 0 else ""
                deltas.append(f"{sign}{d:.4f}")
            else:
                deltas.append("N/A")
        row = f"| {version} | " + " | ".join(deltas) + " |"
        rows.append(row)

    return "\n".join([header, sep] + rows)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run_ablation_study(
    *,
    max_concurrency: int = 4,
    versions: Optional[List[Dict[str, Any]]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute the full ablation study.

    Parameters
    ----------
    max_concurrency:
        Passed through to ``ragas_eval.run_evaluation``.
    versions:
        Override the default ``ABLATION_VERSIONS`` list.
    dry_run:
        If True, skip actual agent evaluation and produce a skeleton report.

    Returns
    -------
    dict with ``summaries``, ``comparison_table``, ``delta_table``, and
    ``output_path``.
    """
    from evaluation.ragas_eval import run_evaluation

    versions = versions or ABLATION_VERSIONS
    summaries: List[Dict[str, Any]] = []

    for idx, v in enumerate(versions):
        version_name = v["version"]
        config = v["config"]
        description = v.get("description", "")

        logger.info(
            "=== Ablation [%d/%d]: %s ===",
            idx + 1,
            len(versions),
            version_name,
        )
        logger.info("Config: %s", json.dumps(config))

        if dry_run:
            logger.info("[DRY RUN] Skipping actual evaluation.")
            summary = {
                "version": version_name,
                "description": description,
                "ragas": {
                    "faithfulness": None,
                    "answer_relevancy": None,
                    "context_precision": None,
                    "context_recall": None,
                },
                "cost": {"estimated_cost_usd": 0},
                "n_samples": 0,
            }
        else:
            try:
                summary = await run_evaluation(
                    version=version_name,
                    max_concurrency=max_concurrency,
                    ablation_config=config,
                )
                summary["description"] = description
            except Exception as exc:
                logger.error("Ablation %s failed: %s", version_name, exc)
                summary = {
                    "version": version_name,
                    "description": description,
                    "error": str(exc),
                    "ragas": {},
                    "cost": {},
                }

        summaries.append(summary)

    # Build comparison tables
    comparison_table = _build_comparison_table(summaries)
    delta_table = _build_delta_table(summaries)

    logger.info("\n\n%s\n", comparison_table)
    logger.info("\n\n%s\n", delta_table)

    # Assemble final output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_versions": len(summaries),
        "summaries": summaries,
        "comparison_table": comparison_table,
        "delta_table": delta_table,
    }

    # Persist
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ABLATION_OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    logger.info("Ablation results saved to %s", ABLATION_OUTPUT)

    # Also write the markdown tables to a separate file for easy reading
    table_path = RESULTS_DIR / "ablation_comparison.md"
    with open(table_path, "w", encoding="utf-8") as fh:
        fh.write("# MedAgentQA Ablation Study\n\n")
        fh.write(f"Generated: {output['generated_at']}\n\n")
        fh.write("## Absolute Scores\n\n")
        fh.write(comparison_table + "\n\n")
        fh.write("## Delta vs Baseline\n\n")
        fh.write(delta_table + "\n")
    logger.info("Markdown tables saved to %s", table_path)

    return output


# ---------------------------------------------------------------------------
# Regression analysis across ablation versions
# ---------------------------------------------------------------------------


async def run_ablation_with_regression_analysis(
    *,
    max_concurrency: int = 4,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run ablation study and then perform pairwise regression analysis.

    Compares each successive version pair (v0->v1, v1->v2, ...) for
    regressions using ``badcase_analyzer.version_diff_analysis``.
    """
    from evaluation.badcase_analyzer import (
        generate_badcase_report,
        version_diff_analysis,
    )

    ablation_output = await run_ablation_study(
        max_concurrency=max_concurrency,
        dry_run=dry_run,
    )

    # Pairwise regression analysis
    summaries = ablation_output["summaries"]
    pairwise_diffs: List[Dict[str, Any]] = []

    for i in range(len(summaries) - 1):
        old_ver = summaries[i]["version"]
        new_ver = summaries[i + 1]["version"]

        old_path = RESULTS_DIR / f"results_{old_ver}.json"
        new_path = RESULTS_DIR / f"results_{new_ver}.json"

        if old_path.exists() and new_path.exists():
            try:
                report_path = generate_badcase_report(
                    new_path,
                    prev_results_path=old_path,
                )
                logger.info(
                    "Badcase report for %s -> %s saved to %s",
                    old_ver,
                    new_ver,
                    report_path,
                )
                pairwise_diffs.append(
                    {
                        "old": old_ver,
                        "new": new_ver,
                        "report_path": str(report_path),
                    }
                )
            except Exception as exc:
                logger.error(
                    "Regression analysis for %s -> %s failed: %s",
                    old_ver,
                    new_ver,
                    exc,
                )
        else:
            logger.warning(
                "Skipping regression analysis for %s -> %s (missing result files).",
                old_ver,
                new_ver,
            )

    ablation_output["pairwise_regression_reports"] = pairwise_diffs
    return ablation_output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run ablation study for MedAgentQA."
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Max concurrent agent invocations per version (default: 4).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual evaluation; produce skeleton report only.",
    )
    parser.add_argument(
        "--with-regression",
        action="store_true",
        help="Run pairwise regression analysis after ablation.",
    )
    args = parser.parse_args()

    if args.with_regression:
        asyncio.run(
            run_ablation_with_regression_analysis(
                max_concurrency=args.max_concurrency,
                dry_run=args.dry_run,
            )
        )
    else:
        asyncio.run(
            run_ablation_study(
                max_concurrency=args.max_concurrency,
                dry_run=args.dry_run,
            )
        )


if __name__ == "__main__":
    main()
