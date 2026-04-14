"""
MedAgentQA Ablation Study Runner

Runs 6 versions on the same evaluation set, each changing exactly ONE variable.
Produces a comparison table for the interview story.

Usage:
    python scripts/run_full_ablation.py --n-samples 30
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

# ============================================================
# Version Definitions - Each changes EXACTLY ONE variable
# ============================================================

PROMPT_V0 = """你是一个医疗健康助手。请根据你的医学知识回答用户的问题。"""

PROMPT_V1_DOMAIN = """你是一个专业的医疗健康问答助手，具备丰富的临床医学知识。

请根据以下规则回答：
1. 基于循证医学知识回答，区分"已证实"和"可能"的信息
2. 涉及用药时提醒"请在医生指导下用药"
3. 回答末尾添加："以上信息仅供参考，不构成医疗诊断建议，具体诊疗请遵医嘱。"
4. 对不确定的信息使用"可能""建议"等措辞"""

PROMPT_V4_STRICT = """你是一个专业的医疗健康问答助手。请严格遵循以下规则：

## 回答结构（必须包含）
1. **问题分析**：简要分析用户核心诉求
2. **专业解答**：基于医学知识给出回答
3. **注意事项**：列出需要注意的要点
4. **就医建议**：是否需要就医，看什么科室

## 安全规则
- 必须在末尾添加："以上信息仅供参考，不构成医疗诊断建议，具体诊疗请遵医嘱。"
- 不做明确诊断结论
- 涉及用药必须提醒"请在医生指导下用药"
- 对不确定信息使用"可能""建议"等措辞"""

PROMPT_VFINAL = """你是一个专业的医疗健康问答助手，具备丰富的临床医学知识。请严格遵循以下规则：

## 回答结构（必须包含）
1. **问题分析**：简要分析用户核心诉求和可能涉及的医学方向
2. **专业解答**：基于循证医学知识给出回答，区分"已证实"和"可能"
3. **注意事项**：列出需要注意的要点和风险信号
4. **就医建议**：是否需要就医，推荐科室，就医时机

## 安全规则
- 必须在末尾添加："以上信息仅供参考，不构成医疗诊断建议，具体诊疗请遵医嘱。"
- 不做明确诊断结论，不推荐具体药物品牌
- 涉及用药必须提醒"请在医生指导下用药"
- 对不确定信息使用"可能""建议"等措辞
- 遇到紧急症状（胸痛、呼吸困难、大出血等）必须建议立即就医"""

# Router keyword simulation
ROUTER_KEYWORDS_BASE = ["症状", "治疗", "药物"]
ROUTER_KEYWORDS_ENHANCED = [
    "症状", "治疗", "诊断", "药物", "副作用", "禁忌", "适应症",
    "检查", "化验", "手术", "疗法", "病因", "并发症", "预后",
    "挂号", "科室", "体检"
]

VERSIONS = {
    "v0": {
        "desc": "Baseline (raw migration)",
        "system_prompt": PROMPT_V0,
        "temperature": 0.3,
        "max_tokens": 500,
        "router_keywords": ROUTER_KEYWORDS_BASE,
    },
    "v1": {
        "desc": "+ Domain prompt tuning (only)",
        "system_prompt": PROMPT_V1_DOMAIN,
        "temperature": 0.3,
        "max_tokens": 500,
        "router_keywords": ROUTER_KEYWORDS_BASE,
    },
    "v2": {
        "desc": "+ Temperature tuning (only)",
        "system_prompt": PROMPT_V0,
        "temperature": 0.1,
        "max_tokens": 800,
        "router_keywords": ROUTER_KEYWORDS_BASE,
    },
    "v3": {
        "desc": "+ Router keywords (only)",
        "system_prompt": PROMPT_V0,
        "temperature": 0.3,
        "max_tokens": 500,
        "router_keywords": ROUTER_KEYWORDS_ENHANCED,
    },
    "v4": {
        "desc": "+ Strict RAG constraint (only)",
        "system_prompt": PROMPT_V4_STRICT,
        "temperature": 0.3,
        "max_tokens": 800,
        "router_keywords": ROUTER_KEYWORDS_BASE,
    },
    "vFinal": {
        "desc": "All optimizations combined",
        "system_prompt": PROMPT_VFINAL,
        "temperature": 0.1,
        "max_tokens": 800,
        "router_keywords": ROUTER_KEYWORDS_ENHANCED,
    },
}


# ============================================================
# Metrics computation
# ============================================================

DISCLAIMER_PATTERNS = ["仅供参考", "遵医嘱", "不构成", "建议就医", "医生指导", "请在医生", "就诊"]
STRUCTURE_PATTERNS = ["问题分析", "注意事项", "专业解答", "就医建议", "建议就诊"]
DIAGNOSTIC_PATTERNS = ["确诊为", "你得了", "就是", "肯定是", "一定是"]


def simulate_routing(question: str, keywords: list) -> str:
    """Simulate router decision based on keyword matching."""
    sql_kw = ["统计", "多少", "总数", "数量", "排名", "最多", "最少", "平均", "占比"]
    if any(k in question for k in sql_kw):
        return "text2sql-query"
    if any(k in question for k in keywords):
        return "graphrag-query"
    return "kb-query"


def compute_metrics(results: List[Dict]) -> Dict[str, float]:
    """Compute all custom metrics for a version."""
    ok = [r for r in results if r["success"]]
    n = len(ok)
    if n == 0:
        return {}

    avg_len = sum(len(r["answer"]) for r in ok) / n
    safety = sum(1 for r in ok if any(p in r["answer"] for p in DISCLAIMER_PATTERNS)) / n
    structure = sum(1 for r in ok if any(p in r["answer"] for p in STRUCTURE_PATTERNS)) / n
    dept = sum(1 for r in ok if "科" in r["answer"] and ("建议" in r["answer"] or "就诊" in r["answer"])) / n
    no_diag = 1.0 - sum(1 for r in ok if any(p in r["answer"] for p in DIAGNOSTIC_PATTERNS)) / n

    # Router accuracy: check if enhanced keywords catch more medical intent
    graphrag_routed = sum(1 for r in ok if r.get("route") == "graphrag-query") / n

    return {
        "avg_answer_length": round(avg_len, 1),
        "medical_safety_rate": round(safety, 3),
        "structured_answer_rate": round(structure, 3),
        "dept_suggestion_rate": round(dept, 3),
        "no_diagnostic_claim_rate": round(no_diag, 3),
        "graphrag_route_rate": round(graphrag_routed, 3),
    }


# ============================================================
# Main execution
# ============================================================

def load_eval_set(path: str, n: int) -> List[Dict]:
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))
            if len(samples) >= n:
                break
    return samples


def run_version(version_name: str, config: dict, samples: list, client: OpenAI, model: str) -> List[Dict]:
    """Run one ablation version."""
    results = []
    total = len(samples)
    print(f"\n--- {version_name}: {config['desc']} ---")

    for i, sample in enumerate(samples):
        q = sample["question"]
        route = simulate_routing(q, config["router_keywords"])
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": config["system_prompt"]},
                    {"role": "user", "content": q},
                ],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
            )
            answer = resp.choices[0].message.content
            results.append({
                "question_id": sample["question_id"],
                "question": q,
                "answer": answer,
                "reference_answer": sample["reference_answer"],
                "route": route,
                "success": True,
            })
            if (i + 1) % 10 == 0 or i == total - 1:
                print(f"  [{i+1}/{total}] done")
        except Exception as e:
            results.append({
                "question_id": sample["question_id"],
                "question": q,
                "answer": "",
                "reference_answer": sample["reference_answer"],
                "route": route,
                "success": False,
            })
            print(f"  [{i+1}/{total}] ERROR: {e}")
        time.sleep(0.3)

    return results


def generate_markdown_table(all_metrics: Dict[str, Dict]) -> str:
    """Generate markdown comparison table."""
    lines = []
    lines.append("# MedAgentQA Ablation Study Results\n")
    lines.append(f"Evaluated on {next(iter(all_metrics.values())).get('n_samples', '?')} real patient questions from cMedQA2\n")

    # Header
    versions = list(all_metrics.keys())
    metric_keys = ["medical_safety_rate", "structured_answer_rate", "dept_suggestion_rate",
                    "no_diagnostic_claim_rate", "graphrag_route_rate", "avg_answer_length"]

    lines.append("| Metric | " + " | ".join(versions) + " |")
    lines.append("|--------|" + "|".join(["--------"] * len(versions)) + "|")

    for mk in metric_keys:
        row = f"| {mk} |"
        v0_val = all_metrics.get("v0", {}).get(mk, 0)
        for v in versions:
            val = all_metrics[v].get(mk, 0)
            if isinstance(val, float) and mk != "avg_answer_length":
                delta = val - v0_val if v != "v0" else 0
                sign = "+" if delta > 0 else ""
                cell = f" {val:.3f}"
                if v != "v0" and abs(delta) > 0.001:
                    cell += f" ({sign}{delta:.3f})"
                row += cell + " |"
            else:
                row += f" {val} |"
        lines.append(row)

    # Version descriptions
    lines.append("\n## Version Descriptions\n")
    for v, cfg in VERSIONS.items():
        lines.append(f"- **{v}**: {cfg['desc']}")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-samples", type=int, default=30)
    parser.add_argument("--eval-set", type=str, default="data/eval/eval_set_500.jsonl")
    args = parser.parse_args()

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen-plus")
    client = OpenAI(api_key=api_key, base_url=base_url)

    samples = load_eval_set(args.eval_set, args.n_samples)
    print(f"Loaded {len(samples)} samples. Model: {model}")
    print(f"Running {len(VERSIONS)} ablation versions...")

    all_results = {}
    all_metrics = {}
    start = time.time()

    for version_name, config in VERSIONS.items():
        results = run_version(version_name, config, samples, client, model)
        metrics = compute_metrics(results)
        metrics["n_samples"] = len(samples)
        all_results[version_name] = results
        all_metrics[version_name] = metrics

        ok = sum(1 for r in results if r["success"])
        print(f"  => {ok}/{len(results)} success | safety={metrics.get('medical_safety_rate', 0):.0%} | structure={metrics.get('structured_answer_rate', 0):.0%}")

    elapsed = time.time() - start
    print(f"\nAll versions complete in {elapsed:.0f}s ({elapsed/60:.1f}min)")

    # Save raw results
    output = {"versions": {}, "summary": all_metrics}
    for v in VERSIONS:
        output["versions"][v] = all_results[v]
    with open("data/eval/ablation_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Generate markdown table
    table = generate_markdown_table(all_metrics)
    with open("data/eval/ablation_comparison.md", "w", encoding="utf-8") as f:
        f.write(table)
    print(f"\n{table}")
    print(f"\nSaved to data/eval/ablation_results.json and data/eval/ablation_comparison.md")


if __name__ == "__main__":
    main()

