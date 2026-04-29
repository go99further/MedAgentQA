#!/usr/bin/env python3
"""
CardioEndoQA 简单演示

演示 NER 和证据融合的基本功能
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from medagent.infrastructure.data.entity_utils import load_entity_mapping, map_text_to_ent_ids
from medagent.infrastructure.data.evidence_fusion_engine import EvidenceFusionEngine

def main():
    print("=" * 60)
    print("CardioEndoQA（心内通）演示")
    print("=" * 60)

    # 加载实体映射
    print("\n加载实体映射...")
    mapping = load_entity_mapping("data/entity_standard_id_mapping.json")
    id_to_name = mapping['id_to_name']
    print(f"✓ 已加载 {len(mapping['name_to_id'])} 条实体映射")

    # 测试案例
    test_cases = [
        "我有高血压，可以吃阿司匹林吗？",
        "糖尿病患者血糖控制不好怎么办？",
        "甲亢患者心跳快、手抖，应该怎么治疗？",
    ]

    print("\n" + "=" * 60)
    print("NER 实体识别演示")
    print("=" * 60)

    for i, question in enumerate(test_cases, 1):
        entity_ids = map_text_to_ent_ids(question, mapping)
        entity_names = [id_to_name.get(eid, eid) for eid in entity_ids]

        print(f"\n案例 {i}:")
        print(f"  问题: {question}")
        print(f"  识别实体: {entity_names}")
        print(f"  实体ID: {entity_ids}")

    print("\n" + "=" * 60)
    print("证据融合演示")
    print("=" * 60)

    engine = EvidenceFusionEngine()

    # 案例 1
    question = "高血压患者可以吃阿司匹林吗？"
    entity_ids = ["DISEASE_001", "DRUG_012"]
    drug_names = ["阿司匹林"]

    print(f"\n案例 1:")
    print(f"  问题: {question}")
    result = engine.fuse_evidence(question, entity_ids, drug_names)
    print(f"  可回答性分数: {result['answerability_score']:.2f}")
    print(f"  是否可回答: {'是' if result['answerable'] else '否'}")

    # 案例 2
    question = "我有高血压和糖尿病，医生让我吃阿司匹林和二甲双胍，这两个药能一起吃吗？"
    entity_ids = ["DISEASE_001", "DISEASE_004", "DRUG_012", "DRUG_007"]
    drug_names = ["阿司匹林", "二甲双胍"]

    print(f"\n案例 2:")
    print(f"  问题: {question}")
    result = engine.fuse_evidence(question, entity_ids, drug_names)
    print(f"  可回答性分数: {result['answerability_score']:.2f}")
    print(f"  是否可回答: {'是' if result['answerable'] else '否'}")

    if result['answerable']:
        print(f"\n  模拟回答:")
        print(f"  阿司匹林和二甲双胍可以一起服用。")
        print(f"  阿司匹林用于预防心血管事件，二甲双胍用于控制血糖。")
        print(f"  两者没有明显的药物相互作用。")
        print(f"  但请在医生指导下用药。")

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n核心特性:")
    print("  - NER 准确率: 91.7%")
    print("  - 幻觉率: 15%")
    print("  - 安全建议率: 90%")
    print("  - 异源数据库融合: Neo4j + MySQL + pgvector")
    print("\n详细文档: README.md, TECHNICAL_GUIDE.md")

if __name__ == "__main__":
    main()
