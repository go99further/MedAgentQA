"""
MedAgentQA Baseline Evaluation Runner (Simplified)

This script runs a simplified evaluation without the full agent infrastructure.
It uses the LLM directly to answer medical questions, simulating a baseline
where no retrieval or routing optimization has been applied.

Usage:
    python scripts/run_baseline_eval.py --n-samples 30 --version v0
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from openai import OpenAI


def load_eval_set(path: str, n_samples: int = 30) -> List[Dict[str, Any]]:
    """Load evaluation set, optionally limiting to n_samples."""
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))
            if len(samples) >= n_samples:
                break
    return samples


def run_llm_baseline(question: str, client: OpenAI, model: str) -> str:
    """Run a simple LLM call without retrieval (baseline)."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个医疗健康助手。请根据你的医学知识回答用户的问题。注意：本回答仅供参考，不构成医疗诊断建议。"},
            {"role": "user", "content": question}
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content


def run_evaluation(samples: List[Dict], client: OpenAI, model: str, version: str):
    """Run evaluation on samples and compute metrics."""
    results = []
    total = len(samples)

    print(f"\n{'='*60}")
    print(f"Running {version} evaluation on {total} samples...")
    print(f"{'='*60}\n")

    start_time = time.time()

    for i, sample in enumerate(samples):
        question = sample["question"]
        reference = sample["reference_answer"]

        try:
            answer = run_llm_baseline(question, client, model)
            results.append({
                "question_id": sample["question_id"],
                "question": question,
                "answer": answer,
                "reference_answer": reference,
                "contexts": [answer[:200]],  # Simplified: use answer as context for RAGAS
                "success": True,
            })
            print(f"  [{i+1}/{total}] OK - Q: {question[:40]}...")
        except Exception as e:
            results.append({
                "question_id": sample["question_id"],
                "question": question,
                "answer": f"Error: {str(e)}",
                "reference_answer": reference,
                "contexts": [],
                "success": False,
            })
            print(f"  [{i+1}/{total}] ERROR - {str(e)[:50]}")

        # Rate limiting
        time.sleep(0.5)

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])

    print(f"\n{'='*60}")
    print(f"Evaluation complete: {success_count}/{total} successful ({elapsed:.1f}s)")
    print(f"{'='*60}")

    return results


def compute_simple_metrics(results: List[Dict]) -> Dict[str, float]:
    """Compute simplified metrics without full RAGAS (for quick baseline)."""
    successful = [r for r in results if r["success"]]
    if not successful:
        return {"error": "no successful results"}

    # Simple metrics we can compute without RAGAS LLM judge
    avg_answer_length = sum(len(r["answer"]) for r in successful) / len(successful)
    has_disclaimer = sum(1 for r in successful if "仅供参考" in r["answer"] or "建议" in r["answer"]) / len(successful)

    return {
        "total_samples": len(results),
        "successful": len(successful),
        "avg_answer_length": round(avg_answer_length, 1),
        "disclaimer_rate": round(has_disclaimer, 3),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run MedAgentQA baseline evaluation")
    parser.add_argument("--n-samples", type=int, default=30, help="Number of samples to evaluate")
    parser.add_argument("--version", type=str, default="v0", help="Version label")
    parser.add_argument("--eval-set", type=str, default="data/eval/eval_set_500.jsonl")
    args = parser.parse_args()

    # Setup client
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen-plus")

    if not api_key:
        print("ERROR: No API key found. Set LLM_API_KEY or OPENAI_API_KEY")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f"Using model: {model} at {base_url}")

    # Load eval set
    samples = load_eval_set(args.eval_set, args.n_samples)
    print(f"Loaded {len(samples)} evaluation samples")

    # Run evaluation
    results = run_evaluation(samples, client, model, args.version)

    # Compute metrics
    metrics = compute_simple_metrics(results)
    print(f"\nMetrics ({args.version}):")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    # Save results
    output_path = f"data/eval/results_{args.version}.json"
    output = {
        "version": args.version,
        "model": model,
        "n_samples": len(samples),
        "metrics": metrics,
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
