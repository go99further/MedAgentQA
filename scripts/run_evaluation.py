"""
统一评估入口脚本 — 替代 run_agent_evaluation.py + run_full_ablation.py

用法：
    # 运行全部版本
    python scripts/run_evaluation.py --n-samples 50

    # 运行单个版本
    python scripts/run_evaluation.py --version v_baseline --n-samples 10

    # 仅重算指标（不重跑 Agent，零 API 成本）
    python scripts/run_evaluation.py --metrics-only --input data/eval/agent_ablation_results.json

    # 加入 LLM-as-Judge 指标
    python scripts/run_evaluation.py --metrics-only --input data/eval/agent_ablation_results.json --llm-judge
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.harness import EvaluationHarness

# ---------------------------------------------------------------------------
# Ablation version definitions
# ---------------------------------------------------------------------------
VERSIONS = {
    "v0": {
        "desc": "Full pipeline baseline",
        "configurable": {},
    },
    "v1": {
        "desc": "Disable Rerank (vector similarity only)",
        "configurable": {"rerank_enabled": False},
    },
    "v2": {
        "desc": "Disable Guardrails (no safety filter)",
        "configurable": {"guardrails_enabled": False},
    },
    "v3": {
        "desc": "Disable Redis cache (fresh retrieval every time)",
        "configurable": {"cache_enabled": False},
    },
    "v4": {
        "desc": "Disable KG (graphrag→kb fallback)",
        "configurable": {"kg_enabled": False},
    },
    "vFinal": {
        "desc": "All enabled + optimized prompts",
        "configurable": {"prompt_version": "optimized"},
    },
    # Agentic RAG ablation
    "v_baseline": {
        "desc": "Single-pass retrieval, Evidence Verifier disabled",
        "configurable": {"evidence_verifier_enabled": False},
    },
    "v_agentic": {
        "desc": "Agentic RAG with Evidence Verifier enabled",
        "configurable": {},
    },
    # Evidence Verifier threshold experiments (Phase 7)
    "v_verifier_strict": {
        "desc": "Agentic RAG，高阈值强制 REFINE（min_relevance_score=0.7）",
        "configurable": {
            "verifier_min_relevance_score": 0.7,   # cMedQA2 max_score 约 0.52-0.70，会触发 REFINE
            "verifier_min_chunks": 3,               # 要求 3 个以上高质量 chunk
        },
    },
    "v_verifier_ultra": {
        "desc": "Agentic RAG，极高阈值强制 REFUSE（min_relevance_score=0.95）",
        "configurable": {
            "verifier_min_relevance_score": 0.95,   # 必然触发 REFUSE
            "verifier_max_refine_rounds": 1,
        },
    },
    # Phase 8：数据贡献 vs 架构贡献对比实验
    "v_cmed_baseline": {
        "desc": "cMedQA2 + 单次 RAG（无 Verifier）",
        "configurable": {
            "evidence_verifier_enabled": False,
            "milvus_collection": "cmedqa2",
        },
    },
    "v_cmed_agentic": {
        "desc": "cMedQA2 + Agentic RAG（默认阈值）",
        "configurable": {"milvus_collection": "cmedqa2"},
    },
    "v_chimed_agentic": {
        "desc": "ChiMed 2.0 + Agentic RAG（默认阈值）",
        "configurable": {"milvus_collection": "chimedqa2"},
    },
}


def load_eval_set(path: str, n: int):
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
            if len(samples) >= n:
                break
    return samples


def parse_args():
    parser = argparse.ArgumentParser(
        description="MedAgentQA unified evaluation harness."
    )
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument(
        "--version", type=str, default=None,
        help="Run a single version (e.g. v0). Default: run all versions.",
    )
    parser.add_argument(
        "--eval-set", type=str,
        default=str(Path(__file__).parent.parent / "data" / "eval" / "eval_set_500.jsonl"),
    )
    parser.add_argument(
        "--output", type=str,
        default=str(Path(__file__).parent.parent / "data" / "eval" / "harness_results.json"),
    )
    parser.add_argument(
        "--metrics-only", action="store_true",
        help="Skip agent calls; recompute metrics from existing results file.",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="Input results JSON for --metrics-only mode.",
    )
    parser.add_argument(
        "--llm-judge", action="store_true",
        help="Add LLM-as-Judge metrics (requires DASHSCOPE_API_KEY).",
    )
    parser.add_argument("--concurrency", type=int, default=5)
    return parser.parse_args()


async def main():
    args = parse_args()

    # --metrics-only: recompute from existing file
    if args.metrics_only:
        input_path = args.input or args.output
        if not Path(input_path).exists():
            print(f"ERROR: {input_path} not found.")
            sys.exit(1)

        extra_metrics = []
        if args.llm_judge:
            from evaluation.llm_judge import (
                answer_correctness_judge,
                context_relevance_judge,
                evidence_traceability_judge,
            )
            extra_metrics = [
                answer_correctness_judge,
                context_relevance_judge,
                evidence_traceability_judge,
            ]

        result = EvaluationHarness.load_and_recompute(input_path, metrics=extra_metrics or None)
        out_path = args.output
        EvaluationHarness().save(result, out_path)
        print(f"\nMetrics recomputed and saved to {out_path}")
        _print_summary(result.metrics)
        return

    # Full agent evaluation
    samples = load_eval_set(args.eval_set, args.n_samples)
    print(f"Loaded {len(samples)} samples from {args.eval_set}")

    versions_to_run = (
        {args.version: VERSIONS[args.version]}
        if args.version
        else VERSIONS
    )
    if args.version and args.version not in VERSIONS:
        print(f"Unknown version: {args.version}. Available: {list(VERSIONS.keys())}")
        sys.exit(1)

    # Lazy-load graph
    try:
        from medagent.application.agents.lg_builder import graph
    except Exception as e:
        print(f"ERROR: Cannot build Agent Graph. Check Docker services and .env: {e}")
        sys.exit(1)

    extra_metrics = []
    if args.llm_judge:
        from evaluation.llm_judge import (
            answer_correctness_judge,
            context_relevance_judge,
            evidence_traceability_judge,
        )
        extra_metrics = [
            answer_correctness_judge,
            context_relevance_judge,
            evidence_traceability_judge,
        ]

    harness = EvaluationHarness(graph, metrics=extra_metrics or None)
    version_configs = {k: v["configurable"] for k, v in versions_to_run.items()}

    result = await harness.run(samples, version_configs, concurrency=args.concurrency)
    harness.save(result, args.output)

    print(f"\nResults saved to {args.output}")
    _print_summary(result.metrics)


def _print_summary(metrics: dict):
    print(f"\n{'='*80}")
    print(f"  EVALUATION SUMMARY")
    print(f"{'='*80}")
    header = (
        f"{'Version':<12} {'Safety':>8} {'Struct':>8} {'Pass':>8} "
        f"{'Refine%':>8} {'Refuse%':>8} {'AvgRnds':>8}"
    )
    print(header)
    print("-" * 80)
    for vname, m in metrics.items():
        print(
            f"{vname:<12} "
            f"{m.get('medical_safety_rate', 0):>8.3f} "
            f"{m.get('structured_answer_rate', 0):>8.3f} "
            f"{m.get('pass_rate', 0):>8.3f} "
            f"{m.get('verifier_refine_rate', 0):>8.3f} "
            f"{m.get('verifier_refuse_rate', 0):>8.3f} "
            f"{m.get('avg_refine_rounds', 0):>8.3f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
