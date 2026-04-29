#!/usr/bin/env python3
"""
构建 50 条评估集

策略：
1. 从 93,160 条中筛选高质量样本
2. 按实体数分层采样（1实体/2实体/3+实体）
3. 按领域均衡（心血管/内分泌/混合）
4. 排除低质量样本（答案太短、无实体）
"""
import json
import sys
import io
import random
from pathlib import Path
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from medagent.infrastructure.data.entity_utils import load_entity_mapping

def build_eval_set():
    mapping = load_entity_mapping("data/entity_standard_id_mapping.json")
    id_to_name = mapping['id_to_name']
    id_to_category = mapping['id_to_category']

    # 读取全部数据
    with open("data/filtered/huatuogpt_sft_cardio_endo_final.jsonl", "r", encoding="utf-8") as f:
        all_samples = [json.loads(line) for line in f]

    print(f"总样本数: {len(all_samples)}")

    # 筛选高质量样本
    candidates = []
    for s in all_samples:
        entity_ids = s.get("entity_ids", [])
        question = s.get("question", "")
        answer = s.get("answer", "")

        # 质量过滤
        if len(entity_ids) == 0:
            continue
        if len(answer) < 50:  # 答案太短
            continue
        if len(question) < 10:  # 问题太短
            continue

        # 判断领域
        categories = set()
        for eid in entity_ids:
            cat = id_to_category.get(eid, "")
            if cat in ("cardiovascular",):
                categories.add("cardio")
            elif cat in ("endocrine", "metabolic"):
                categories.add("endo")
            elif cat.startswith("DRUG") or cat.startswith("TEST"):
                pass  # 药物和检查不算领域

        domain = "mixed" if len(categories) > 1 else (list(categories)[0] if categories else "other")

        candidates.append({
            "question": question,
            "answer": answer,
            "entity_ids": entity_ids,
            "entity_count": len(entity_ids),
            "domain": domain,
            "answer_length": len(answer),
        })

    print(f"高质量候选: {len(candidates)}")

    # 按实体数分层
    by_entity_count = {1: [], 2: [], 3: []}  # 3 = 3+
    for c in candidates:
        key = min(c["entity_count"], 3)
        by_entity_count[key].append(c)

    print(f"实体数分布: 1={len(by_entity_count[1])}, 2={len(by_entity_count[2])}, 3+={len(by_entity_count[3])}")

    # 分层采样：1实体15条 + 2实体20条 + 3+实体15条 = 50条
    random.seed(42)
    eval_set = []
    eval_set.extend(random.sample(by_entity_count[1], min(15, len(by_entity_count[1]))))
    eval_set.extend(random.sample(by_entity_count[2], min(20, len(by_entity_count[2]))))
    eval_set.extend(random.sample(by_entity_count[3], min(15, len(by_entity_count[3]))))

    print(f"\n评估集: {len(eval_set)} 条")

    # 统计
    domain_counts = Counter(s["domain"] for s in eval_set)
    entity_counts = Counter(s["entity_count"] for s in eval_set)
    avg_answer_len = sum(s["answer_length"] for s in eval_set) / len(eval_set)

    print(f"领域分布: {dict(domain_counts)}")
    print(f"实体数分布: {dict(entity_counts)}")
    print(f"平均答案长度: {avg_answer_len:.0f} 字")

    # 保存
    output = Path("data/eval/phase14_eval_50.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for s in eval_set:
            f.write(json.dumps({
                "question": s["question"],
                "answer": s["answer"],
                "entity_ids": s["entity_ids"],
                "domain": s["domain"],
            }, ensure_ascii=False) + "\n")

    print(f"\n[OK] 评估集已保存: {output}")

    # 展示几条样本
    print("\n样本预览:")
    for i, s in enumerate(eval_set[:3], 1):
        names = [id_to_name.get(eid, eid) for eid in s["entity_ids"]]
        print(f"\n  [{i}] Q: {s['question'][:50]}...")
        print(f"      实体: {names}")
        print(f"      领域: {s['domain']}")

if __name__ == "__main__":
    build_eval_set()
