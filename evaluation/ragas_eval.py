"""
ragas_eval.py
=============
RAGAS-based evaluation pipeline for MedAgentQA.

Loads the evaluation set (``eval_set_500.jsonl``), runs the multi-agent system
on every question, collects answers together with retrieved contexts, and
computes four RAGAS metrics:

* **faithfulness** -- is the answer grounded in the retrieved context?
* **answer_relevancy** -- does the answer address the question?
* **context_precision** -- are retrieved contexts relevant and well-ranked?
* **context_recall** -- do retrieved contexts cover the reference answer?

Usage::

    python -m evaluation.ragas_eval --version v0_baseline --max-concurrency 4
"""

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("ragas_eval")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_SET_PATH = PROJECT_ROOT / "data" / "eval" / "eval_set_500.jsonl"
RESULTS_DIR = PROJECT_ROOT / "data" / "eval"

# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------


@dataclass
class CostTracker:
    """Lightweight token / API-call counter for cost estimation."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_api_calls: int = 0
    _start_time: float = field(default_factory=time.monotonic)

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        api_calls: int = 1,
    ) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_api_calls += api_calls

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_api_calls": self.total_api_calls,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "estimated_cost_usd": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        """Rough estimate using GPT-4-turbo pricing as reference."""
        prompt_cost = self.total_prompt_tokens / 1_000_000 * 10.0
        completion_cost = self.total_completion_tokens / 1_000_000 * 30.0
        return round(prompt_cost + completion_cost, 4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_eval_set(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the evaluation JSONL file into a list of dicts.

    Each record must contain at least ``question_id``, ``question``,
    ``reference_answer``, and ``department``.
    """
    path = path or EVAL_SET_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation set not found at {path}. "
            "Run `python -m scripts.sample_eval_set` first."
        )
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed line %d: %s", lineno, exc)
    logger.info("Loaded %d evaluation records from %s", len(records), path)
    return records


# ---------------------------------------------------------------------------
# Agent runner (abstract interface)
# ---------------------------------------------------------------------------


@dataclass
class AgentResponse:
    """Container for one agent invocation result."""

    question_id: int
    question: str
    answer: str
    retrieved_contexts: List[str]
    ground_truth: str
    route_type: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


AgentCallable = Callable[[str, Dict[str, Any]], "asyncio.Future[AgentResponse]"]


async def _default_agent_fn(
    question: str,
    config: Dict[str, Any],
) -> AgentResponse:
    """Placeholder agent function.

    Replace with actual MedAgentQA invocation.  The real implementation
    should call the LangGraph workflow and extract the answer plus all
    retrieved document chunks.
    """
    # -- Import the real agent only when it is available --------------------
    try:
        from medagent.application.agents.lg_builder import build_graph

        graph = build_graph()
        from langchain_core.messages import HumanMessage

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": config},
        )
        answer_text = result.get("answer", "")
        contexts = result.get("documents", [])
        route_type = ""
        router = result.get("router")
        if router is not None:
            route_type = getattr(router, "type", str(router))
        return AgentResponse(
            question_id=config.get("question_id", 0),
            question=question,
            answer=answer_text,
            retrieved_contexts=contexts,
            ground_truth=config.get("ground_truth", ""),
            route_type=route_type,
        )
    except ImportError:
        logger.warning("Agent not available; returning stub response.")
        return AgentResponse(
            question_id=config.get("question_id", 0),
            question=question,
            answer="[stub] The agent is not configured.",
            retrieved_contexts=[],
            ground_truth=config.get("ground_truth", ""),
            route_type="unknown",
        )


# ---------------------------------------------------------------------------
# Batch runner with concurrency control
# ---------------------------------------------------------------------------


async def run_agent_batch(
    eval_records: List[Dict[str, Any]],
    agent_fn: Optional[AgentCallable] = None,
    *,
    max_concurrency: int = 4,
    ablation_config: Optional[Dict[str, Any]] = None,
) -> tuple[List[AgentResponse], CostTracker]:
    """Run the agent on every evaluation record with bounded concurrency.

    Parameters
    ----------
    eval_records:
        Output of :func:`load_eval_set`.
    agent_fn:
        Async callable ``(question, config) -> AgentResponse``.  Falls back
        to the built-in default if *None*.
    max_concurrency:
        Maximum number of concurrent agent invocations.
    ablation_config:
        Optional dict merged into every per-record config (used for ablation
        studies to toggle features).

    Returns
    -------
    tuple of (responses, cost_tracker)
    """
    agent_fn = agent_fn or _default_agent_fn
    ablation_config = ablation_config or {}
    tracker = CostTracker()
    semaphore = asyncio.Semaphore(max_concurrency)
    results: List[AgentResponse] = []

    async def _run_one(record: Dict[str, Any]) -> AgentResponse:
        async with semaphore:
            config = {
                "question_id": record["question_id"],
                "ground_truth": record.get("reference_answer", ""),
                "department": record.get("department", ""),
                **ablation_config,
            }
            t0 = time.monotonic()
            try:
                resp = await agent_fn(record["question"], config)
            except Exception as exc:
                logger.error(
                    "Agent failed on question %s: %s",
                    record["question_id"],
                    exc,
                )
                resp = AgentResponse(
                    question_id=record["question_id"],
                    question=record["question"],
                    answer=f"[ERROR] {exc}",
                    retrieved_contexts=[],
                    ground_truth=record.get("reference_answer", ""),
                )
            resp.latency_ms = (time.monotonic() - t0) * 1000
            tracker.record(
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
            )
            return resp

    tasks = [asyncio.create_task(_run_one(rec)) for rec in eval_records]
    done = 0
    for coro in asyncio.as_completed(tasks):
        resp = await coro
        results.append(resp)
        done += 1
        if done % 50 == 0 or done == len(tasks):
            logger.info("Progress: %d / %d", done, len(tasks))

    # Preserve original ordering
    results.sort(key=lambda r: r.question_id)
    return results, tracker


# ---------------------------------------------------------------------------
# RAGAS evaluation
# ---------------------------------------------------------------------------


def compute_ragas_metrics(
    responses: Sequence[AgentResponse],
) -> Dict[str, Any]:
    """Build a HuggingFace ``Dataset`` from agent responses and run RAGAS.

    Returns a dict with per-sample scores and aggregate means.
    """
    data = {
        "question": [r.question for r in responses],
        "answer": [r.answer for r in responses],
        "contexts": [r.retrieved_contexts for r in responses],
        "ground_truth": [r.ground_truth for r in responses],
    }
    ds = Dataset.from_dict(data)

    logger.info("Running RAGAS evaluation on %d samples ...", len(ds))
    ragas_result = evaluate(
        ds,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
    )

    # ragas_result is a dict-like with aggregate scores
    scores: Dict[str, Any] = {}
    for metric_name in (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ):
        value = ragas_result.get(metric_name)
        if value is not None:
            scores[metric_name] = round(float(value), 4)

    # Per-sample scores are in the underlying dataset
    per_sample: List[Dict[str, Any]] = []
    result_ds = ragas_result.to_pandas() if hasattr(ragas_result, "to_pandas") else None
    if result_ds is not None:
        for idx in range(len(result_ds)):
            row = result_ds.iloc[idx]
            sample: Dict[str, Any] = {"question_id": responses[idx].question_id}
            for col in result_ds.columns:
                val = row[col]
                try:
                    sample[col] = round(float(val), 4)
                except (TypeError, ValueError):
                    sample[col] = str(val)
            per_sample.append(sample)

    return {
        "aggregate": scores,
        "per_sample": per_sample,
    }


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------


def save_results(
    version: str,
    ragas_scores: Dict[str, Any],
    responses: Sequence[AgentResponse],
    cost: CostTracker,
    *,
    output_dir: Optional[Path] = None,
) -> Path:
    """Persist evaluation results to ``data/eval/results_{version}.json``."""
    output_dir = output_dir or RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"results_{version}.json"

    payload = {
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_samples": len(responses),
        "ragas": ragas_scores,
        "cost": cost.to_dict(),
        "responses": [
            {
                "question_id": r.question_id,
                "question": r.question,
                "answer": r.answer,
                "retrieved_contexts": r.retrieved_contexts,
                "ground_truth": r.ground_truth,
                "route_type": r.route_type,
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in responses
        ],
    }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    logger.info("Results saved to %s", path)
    return path


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


async def run_evaluation(
    version: str = "v0_baseline",
    eval_set_path: Optional[Path] = None,
    agent_fn: Optional[AgentCallable] = None,
    max_concurrency: int = 4,
    ablation_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """End-to-end evaluation: load data -> run agent -> compute RAGAS -> save.

    Parameters
    ----------
    version:
        A label for this evaluation run (used in the output filename).
    eval_set_path:
        Path to the JSONL evaluation set.
    agent_fn:
        Custom async agent callable. *None* uses the default agent.
    max_concurrency:
        Max concurrent agent calls.
    ablation_config:
        Feature toggles forwarded to every agent call.

    Returns
    -------
    dict with ``ragas``, ``cost``, and ``output_path`` keys.
    """
    records = load_eval_set(eval_set_path)

    responses, tracker = await run_agent_batch(
        records,
        agent_fn=agent_fn,
        max_concurrency=max_concurrency,
        ablation_config=ablation_config,
    )

    ragas_scores = compute_ragas_metrics(responses)
    result_path = save_results(version, ragas_scores, responses, tracker)

    summary = {
        "version": version,
        "n_samples": len(responses),
        "ragas": ragas_scores["aggregate"],
        "cost": tracker.to_dict(),
        "output_path": str(result_path),
    }
    logger.info("Evaluation complete: %s", json.dumps(summary, indent=2))
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation for MedAgentQA.")
    parser.add_argument(
        "--version",
        type=str,
        default="v0_baseline",
        help="Version label for this run.",
    )
    parser.add_argument(
        "--eval-set",
        type=str,
        default=None,
        help="Path to evaluation JSONL (default: data/eval/eval_set_500.jsonl).",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Max concurrent agent invocations (default: 4).",
    )
    args = parser.parse_args()

    eval_path = Path(args.eval_set) if args.eval_set else None
    asyncio.run(
        run_evaluation(
            version=args.version,
            eval_set_path=eval_path,
            max_concurrency=args.max_concurrency,
        )
    )


if __name__ == "__main__":
    main()
