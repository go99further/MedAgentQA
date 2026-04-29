#!/usr/bin/env python3
"""
Phase 14 端到端演示

实际运行整个流程：NER → 证据融合 → 评估
"""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from medagent.infrastructure.data.entity_utils import load_entity_mapping, map_text_to_ent_ids
from medagent.infrastructure.data.evidence_fusion_engine import EvidenceFusionEngine

def demo_ner():
    """演示 NER"""
    print("=" * 60)
    print("1. NER 演示")
    print("=" * 60)

    mapping = load_entity_mapping("data/entity_standard_id_mapping.json")
    id_to_name = mapping['id_to_name']

    test_cases = [
        "我有高血压，可以吃阿司匹林吗？",
        "糖尿病患者血糖控制不好怎么办？",
        "心悸、气短、头晕是什么病？",
    ]

    for i, question in enumerate(test_cases, 1):
        entity_ids = map_text_to_ent_ids(question, mapping)
        entity_names = [id_to_name.get(eid, eid) for eid in entity_ids]

        print(f"\n案例 {i}:")
        print(f"  问题: {question}")
        print(f"  识别实体: {entity_names}")

def demo_evidence_fusion():
    """演示证据融合"""
    print("\n" + "=" * 60)
    print("2. 证据融合演示")
    print("=" * 60)

    engine = EvidenceFusionEngine()

    test_cases = [
        {
            "question": "高血压患者可以吃阿司匹林吗？",
            "entity_ids": ["DISEASE_001", "DRUG_012"],
            "drug_names": ["阿司匹林"],
        },
        {
            "question": "糖尿病患者血糖控制不好怎么办？",
            "entity_ids": ["DISEASE_004", "TEST_005"],
            "drug_names": [],
        },
    ]

    for i, case in enumerate(test_cases, 1):
        result = engine.fuse_evidence(
            case["question"],
            case["entity_ids"],
            case["drug_names"]
        )

        print(f"\n案例 {i}:")
        print(f"  问题: {case['question']}")
        print(f"  可回答性分数: {result['answerability_score']:.2f}")
        print(f"  是否可回答: {'是' if result['answerable'] else '否'}")
        print(f"  证据来源: {', '.join(result['evidence'].keys())}")

def demo_evaluation():
    """演示评估"""
    print("\n" + "=" * 60)
    print("3. 评估演示")
    print("=" * 60)

    # 读取评估结果
    results_file = Path("data/eval/phase14_eval_results.json")
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    print("\nLayer 1 (安全性):")
    print(f"  幻觉率: {1-results['layer1_safety']['hallucination_free_rate']:.1%}")
    print(f"  安全建议率: {results['layer1_safety']['safe_advice_rate']:.1%}")

    print("\nLayer 2 (价值):")
    print(f"  医学准确率: {results['layer2_value']['medical_accuracy_avg']:.1f}/5")
    print(f"  证据可追溯性: {results['layer2_value']['evidence_traceability_avg']:.1%}")

    print("\nLayer 3 (诊断):")
    print(f"  路由分布: {results['layer3_diagnostics']['route_distribution']}")
    print(f"  延迟 P50: {results['layer3_diagnostics']['latency_p50_ms']}ms")

def demo_full_pipeline():
    """演示完整流程"""
    print("\n" + "=" * 60)
    print("4. 完整流程演示")
    print("=" * 60)

    mapping = load_entity_mapping("data/entity_standard_id_mapping.json")
    id_to_name = mapping['id_to_name']
    engine = EvidenceFusionEngine()

    question = "我有高血压和糖尿病，医生让我吃阿司匹林和二甲双胍，这两个药能一起吃吗？"

    print(f"\n用户问题: {question}")

    # Step 1: NER
    print("\n[Step 1] NER 识别实体...")
    entity_ids = map_text_to_ent_ids(question, mapping)
    entity_names = [id_to_name.get(eid, eid) for eid in entity_ids]
    print(f"  识别到: {entity_names}")

    # Step 2: 证据融合
    print("\n[Step 2] 证据融合...")
    drug_names = ["阿司匹林", "二甲双胍"]
    result = engine.fuse_evidence(question, entity_ids, drug_names)
    print(f"  可回答性分数: {result['answerability_score']:.2f}")
    print(f"  是否可回答: {'是' if result['answerable'] else '否'}")

    # Step 3: 生成回答（模拟）
    print("\n[Step 3] 生成回答...")
    if result['answerable']:
        print("  回答: 阿司匹林和二甲双胍可以一起服用。阿司匹林用于预防心血管事件，")
        print("        二甲双胍用于控制血糖。两者没有明显的药物相互作用。")
        print("        但请在医生指导下用药，定期监测血糖和血压。")
    else:
        print("  回答: 抱歉，我无法回答这个问题。建议咨询专业医生。")

def main():
    print("=" * 60)
    print("Phase 14 端到端演示")
    print("=" * 60)

    demo_ner()
    demo_evidence_fusion()
    demo_evaluation()
    demo_full_pipeline()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
