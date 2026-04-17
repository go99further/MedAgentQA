"""Medical domain Cypher example retriever for Neo4j KG queries."""

import re
from typing import ClassVar, Dict, List
from medagent.application.agents.kg_sub_graph.agentic_rag_agents.retrievers.cypher_examples.base import BaseCypherExampleRetriever


class MedicalCypherRetriever(BaseCypherExampleRetriever):
    """
    医疗场景的Cypher示例检索器。
    基于关键词匹配为LLM提供医疗领域的Cypher查询示例。
    """

    MEDICAL_EXAMPLES: ClassVar[Dict[str, List[Dict[str, str]]]] = {
        "symptom_disease": [
            {
                "question": "头痛可能是什么病？",
                "cypher": "MATCH (s:Symptom {name: '头痛'})<-[:HAS_SYMPTOM]-(d:Disease) RETURN d.name AS disease LIMIT 10"
            },
            {
                "question": "感冒有哪些症状？",
                "cypher": "MATCH (d:Disease {name: '感冒'})-[:HAS_SYMPTOM]->(s:Symptom) RETURN s.name AS symptom"
            },
        ],
        "drug_query": [
            {
                "question": "治疗高血压用什么药？",
                "cypher": "MATCH (d:Disease {name: '高血压'})-[:TREATED_BY]->(dr:Drug) RETURN dr.name AS drug"
            },
            {
                "question": "阿莫西林有什么副作用？",
                "cypher": "MATCH (dr:Drug {name: '阿莫西林'})-[:SIDE_EFFECT]->(s:Symptom) RETURN s.name AS side_effect"
            },
        ],
        "department_query": [
            {
                "question": "头痛应该挂什么科？",
                "cypher": "MATCH (s:Symptom {name: '头痛'})<-[:HAS_SYMPTOM]-(d:Disease)-[:BELONGS_TO]->(dep:Department) RETURN DISTINCT dep.name AS department"
            },
            {
                "question": "心血管内科看什么病？",
                "cypher": "MATCH (dep:Department {name: '心血管内科'})<-[:BELONGS_TO]-(d:Disease) RETURN d.name AS disease"
            },
        ],
        "drug_interaction": [
            {
                "question": "哪些药物有禁忌？",
                "cypher": "MATCH (d1:Drug)-[:CONTRADICTS]->(d2:Drug) RETURN d1.name AS drug1, d2.name AS drug2 LIMIT 10"
            },
        ],
    }

    KEYWORD_MAP: ClassVar[Dict[str, List[str]]] = {
        "symptom_disease": ["症状", "表现", "可能是", "什么病", "得了"],
        "drug_query": ["药", "治疗", "用药", "副作用", "禁忌"],
        "department_query": ["科", "挂号", "看什么科", "就诊"],
        "drug_interaction": ["禁忌", "冲突", "不能一起", "相互作用"],
    }

    def get_examples(self, query: str, k: int = 5) -> str:
        # Score each category by keyword overlap
        scores = {}
        for cat, keywords in self.KEYWORD_MAP.items():
            scores[cat] = sum(1 for kw in keywords if kw in query)

        # Collect examples, prioritizing matched categories
        selected = []
        for cat, score in sorted(scores.items(), key=lambda x: -x[1]):
            if score > 0:
                selected.extend(self.MEDICAL_EXAMPLES.get(cat, []))

        # Add general examples if not enough
        if len(selected) < k:
            for cat, examples in self.MEDICAL_EXAMPLES.items():
                for ex in examples:
                    if ex not in selected:
                        selected.append(ex)

        selected = selected[:k]

        return "\n\n".join(
            f"Question: {ex['question']}\nCypher: {ex['cypher']}"
            for ex in selected
        )
