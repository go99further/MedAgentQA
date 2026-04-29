#!/usr/bin/env python3
"""
构建严格的心血管-内分泌评估集（50 条）

改进：
1. 必须包含核心疾病实体（不仅仅是症状/检查）
2. 问题主题必须是心血管或内分泌
3. 答案必须足够长（>80字）
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

CORE_DISEASES = {
    "DISEASE_001", "DISEASE_002", "DISEASE_003", "DISEASE_004",
    "DISEASE_005", "DISEASE_006", "DISEASE_007", "DISEASE_008",
    "DISEASE_009", "DISEASE_010",
}

CORE_DRUGS = {
    "DRUG_001", "DRUG_002", "DRUG_003", "DRUG_004", "DRUG_005",
    "DRUG_006", "DRUG_007", "DRUG_008", "DRUG_009", "DRUG_010",
    "DRUG_011", "DRUG_012", "DRUG_013", "DRUG_014", "DRUG_015",
    "DRUG_016", "DRUG_017", "DRUG_018", "DRUG_019", "DRUG_020",
    "DRUG_021", "DRUG_022",
}

# 领域外关键词（排除）
EXCLUDE_KEYWORDS = [
    "肺炎", "肺癌", "肝癌", "胃癌", "乳腺癌", "宫颈癌",
    "骨折", "腰椎", "颈椎", "关节", "痔疮", "痘痘",
    "皮肤", "湿疹", "荨麻疹", "白癜风", "脱发",
    "近视", "耳鸣", "鼻炎", "咽炎", "扁桃体",
    "怀孕", "月经", "不孕", "前列腺",
    "抑郁", "焦虑", "失眠",
    "烟雾病", "脑膜瘤", "脑出血", "蛛网膜",
]

def is_cardio_endo(question, answer, entity_ids):
    """严格判断是否为心血管-内分泌领域"""
    # 必须包含至少 1 个核心疾病或核心药物
    has_core = any(eid in CORE_DISEASES or eid in CORE_DRUGS for eid in entity_ids)
    if not has_core:
        return False

    # 排除领域外关键词
    text = question + answer
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return False

    return True

def main():
    mapping = load_entity_mapping("data/entity_standard_id_mapping.json")
    id_to_name = mapping['id_to_name']

    with open("data/filtered/huatuogpt_sft_cardio_endo_final.jsonl", "r", encoding="utf-8") as f:
        all_samples = [json.loads(line) for line in f]

    print(f"总样本数: {len(all_samples)}")

    # 严格筛选
    candidates = []
    for s in all_samples:
        entity_ids = s.get("entity_ids", [])
        question = s.get("question", "")
        answer = s.get("answer", "")

        if len(answer) < 80:
            continue
        if len(question) < 10:
            continue
        if not is_cardio_endo(question, answer, entity_ids):
            continue

        candidates.append(s)

    print(f"严格筛选后: {len(candidates)} 条")

    # 按疾病分组
    by_disease = {}
    for c in candidates:
        diseases = [eid for eid in c["entity_ids"] if eid in CORE_DISEASES]
        for d in diseases:
            if d not in by_disease:
                by_disease[d] = []
            by_disease[d].append(c)

    print("\n按疾病分布:")
    for d, samples in sorted(by_disease.items()):
        print(f"  {id_to_name.get(d, d)}: {len(samples)} 条")

    # 均衡采样：每种疾病 5 条，共 50 条
    random.seed(42)
    eval_set = []
    per_disease = max(1, 50 // len(by_disease))

    for d in sorted(by_disease.keys()):
        samples = by_disease[d]
        n = min(per_disease, len(samples))
        selected = random.sample(samples, n)
        for s in selected:
            if s not in eval_set:
                eval_set.append(s)

    # 如果不够 50 条，从剩余中补充
    if len(eval_set) < 50:
        remaining = [c for c in candidates if c not in eval_set]
        random.shuffle(remaining)
        eval_set.extend(remaining[:50 - len(eval_set)])

    eval_set = eval_set[:50]
    print(f"\n最终评估集: {len(eval_set)} 条")

    # 统计
    disease_counts = Counter()
    for s in eval_set:
        for eid in s["entity_ids"]:
            if eid in CORE_DISEASES:
                disease_counts[id_to_name.get(eid, eid)] += 1

    print("\n评估集疾病分布:")
    for name, count in disease_counts.most_common():
        print(f"  {name}: {count} 条")

    # 保存
    output = Path("data/eval/phase14_eval_50_strict.jsonl")
    with open(output, "w", encoding="utf-8") as f:
        for s in eval_set:
            f.write(json.dumps({
                "question": s["question"],
                "answer": s["answer"],
                "entity_ids": s["entity_ids"],
            }, ensure_ascii=False) + "\n")

    print(f"\n[OK] 严格评估集已保存: {output}")

    # 预览
    print("\n样本预览:")
    for i, s in enumerate(eval_set[:5], 1):
        names = [id_to_name.get(eid, eid) for eid in s["entity_ids"]]
        print(f"  [{i}] Q: {s['question'][:50]}...")
        print(f"      实体: {names}")

if __name__ == "__main__":
    main()
