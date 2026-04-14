"""
MedAgentQA v1 Optimized Evaluation Runner

This version adds medical-specific prompt constraints to improve answer quality:
- Stronger evidence-based answering requirement
- Explicit disclaimer enforcement
- Structured answer format
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from openai import OpenAI

V1_SYSTEM_PROMPT = """你是一个专业的医疗健康问答助手。请严格遵循以下规则回答用户问题：

## 回答规则
1. 仅基于已知的医学知识回答，不要编造不确定的信息
2. 回答必须包含以下结构：
   - 问题分析：简要分析用户的核心诉求
   - 专业解答：基于医学知识给出回答
   - 注意事项：列出需要注意的要点
   - 就医建议：是否需要就医，看什么科室
3. 必须在回答末尾添加免责声明："以上信息仅供参考，不构成医疗诊断建议，具体诊疗请遵医嘱。"
4. 对于不确定的信息，使用"可能"、"建议"等措辞，避免绝对化表述
5. 涉及用药时，必须提醒"请在医生指导下用药"

## 禁止行为
- 不要做出明确的诊断结论
- 不要推荐具体的药物品牌
- 不要给出具体的用药剂量（除非是常识性信息）
"""


def load_eval_set(path: str, n_samples: int = 30) -> List[Dict[str, Any]]:
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))
            if len(samples) >= n_samples:
                break
    return samples


def run_llm_v1(question: str, client: OpenAI, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": V1_SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return response.choices[0].message.content


def run_evaluation(samples, client, model, version):
    results = []
    total = len(samples)
    print(f"\nRunning {version} evaluation on {total} samples...")
    start_time = time.time()

    for i, sample in enumerate(samples):
        try:
            answer = run_llm_v1(sample["question"], client, model)
            results.append({
                "question_id": sample["question_id"],
                "question": sample["question"],
                "answer": answer,
                "reference_answer": sample["reference_answer"],
                "contexts": [answer[:200]],
                "success": True,
            })
            print(f"  [{i+1}/{total}] OK")
        except Exception as e:
            results.append({
                "question_id": sample["question_id"],
                "question": sample["question"],
                "answer": f"Error: {str(e)}",
                "reference_answer": sample["reference_answer"],
                "contexts": [],
                "success": False,
            })
            print(f"  [{i+1}/{total}] ERROR - {str(e)[:50]}")
        time.sleep(0.5)

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    print(f"Done: {success_count}/{total} successful ({elapsed:.1f}s)")
    return results


def compute_metrics(results):
    successful = [r for r in results if r["success"]]
    if not successful:
        return {"error": "no successful results"}

    avg_len = sum(len(r["answer"]) for r in successful) / len(successful)
    has_disclaimer = sum(1 for r in successful if "仅供参考" in r["answer"] or "遵医嘱" in r["answer"]) / len(successful)
    has_structure = sum(1 for r in successful if "问题分析" in r["answer"] or "注意事项" in r["answer"]) / len(successful)
    has_dept_suggestion = sum(1 for r in successful if "科" in r["answer"] and "建议" in r["answer"]) / len(successful)

    return {
        "total_samples": len(results),
        "successful": len(successful),
        "avg_answer_length": round(avg_len, 1),
        "disclaimer_rate": round(has_disclaimer, 3),
        "structured_answer_rate": round(has_structure, 3),
        "dept_suggestion_rate": round(has_dept_suggestion, 3),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-samples", type=int, default=30)
    parser.add_argument("--version", type=str, default="v1")
    parser.add_argument("--eval-set", type=str, default="data/eval/eval_set_500.jsonl")
    args = parser.parse_args()

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen-plus")

    if not api_key:
        print("ERROR: No API key found")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)
    samples = load_eval_set(args.eval_set, args.n_samples)

    results = run_evaluation(samples, client, model, args.version)
    metrics = compute_metrics(results)

    print(f"\nMetrics ({args.version}):")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    output_path = f"data/eval/results_{args.version}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"version": args.version, "model": model, "metrics": metrics, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
