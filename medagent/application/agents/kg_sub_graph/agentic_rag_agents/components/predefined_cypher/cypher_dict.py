"""
预定义医疗知识图谱 Cypher 查询字典
基于医疗 KG schema（Disease、Symptom、Drug、Department、Treatment）设计
对应 descriptions.py 中 5 大类查询描述
"""
from typing import Dict

predefined_cypher_dict: Dict[str, str] = {
    # ==================== 1. 疾病属性查询 ====================

    "disease_symptoms": """
MATCH (d:Disease {name: $disease_name})-[:HAS_SYMPTOM]->(s:Symptom)
RETURN d.name AS 疾病, collect(s.name) AS 症状列表
""",

    "disease_causes": """
MATCH (d:Disease {name: $disease_name})
RETURN d.name AS 疾病, d.cause AS 病因, d.description AS 描述
""",

    "disease_treatments": """
MATCH (d:Disease {name: $disease_name})
OPTIONAL MATCH (d)-[:TREATED_BY]->(dr:Drug)
OPTIONAL MATCH (d)-[:HAS_TREATMENT]->(t:Treatment)
RETURN d.name AS 疾病,
       collect(DISTINCT dr.name) AS 药物治疗,
       collect(DISTINCT t.method) AS 治疗方案
""",

    "disease_complications": """
MATCH (d:Disease {name: $disease_name})-[:MAY_CAUSE]->(c:Disease)
RETURN d.name AS 疾病, collect(c.name) AS 并发症
""",

    "disease_complete_info": """
MATCH (d:Disease {name: $disease_name})
OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[:TREATED_BY]->(dr:Drug)
OPTIONAL MATCH (d)-[:BELONGS_TO]->(dep:Department)
OPTIONAL MATCH (d)-[:MAY_CAUSE]->(c:Disease)
RETURN d.name AS 疾病,
       d.description AS 描述,
       collect(DISTINCT s.name) AS 症状,
       collect(DISTINCT dr.name) AS 药物,
       collect(DISTINCT dep.name) AS 就诊科室,
       collect(DISTINCT c.name) AS 并发症
""",

    # ==================== 2. 药物相关查询 ====================

    "drug_indications": """
MATCH (dr:Drug {name: $drug_name})-[:TREATS]->(d:Disease)
RETURN dr.name AS 药物, collect(d.name) AS 适应症
""",

    "drug_contraindications": """
MATCH (dr:Drug {name: $drug_name})
RETURN dr.name AS 药物, dr.contraindications AS 禁忌症
""",

    "drug_side_effects": """
MATCH (dr:Drug {name: $drug_name})-[:SIDE_EFFECT]->(s:Symptom)
RETURN dr.name AS 药物, collect(s.name) AS 不良反应
""",

    "drug_interactions": """
MATCH (dr1:Drug {name: $drug_name})-[:CONTRADICTS]->(dr2:Drug)
RETURN dr1.name AS 药物, collect(dr2.name) AS 相互作用禁忌
""",

    "drug_dosage": """
MATCH (dr:Drug {name: $drug_name})
RETURN dr.name AS 药物, dr.dosage AS 用法用量, dr.dosage_form AS 剂型, dr.specification AS 规格
""",

    # ==================== 3. 症状相关查询 ====================

    "symptom_related_diseases": """
MATCH (s:Symptom {name: $symptom_name})<-[:HAS_SYMPTOM]-(d:Disease)
RETURN s.name AS 症状, collect(d.name) AS 可能疾病 LIMIT 10
""",

    "symptom_severity": """
MATCH (s:Symptom {name: $symptom_name})
RETURN s.name AS 症状, s.severity_level AS 严重程度, s.description AS 描述
""",

    # ==================== 4. 科室相关查询 ====================

    "disease_department": """
MATCH (d:Disease {name: $disease_name})-[:BELONGS_TO]->(dep:Department)
RETURN d.name AS 疾病, dep.name AS 就诊科室
""",

    "department_diseases": """
MATCH (dep:Department {name: $department_name})<-[:BELONGS_TO]-(d:Disease)
RETURN dep.name AS 科室, collect(d.name) AS 常见疾病 LIMIT 20
""",

    # ==================== 5. 统计分析查询 ====================

    "disease_prevalence": """
MATCH (d:Disease)
WHERE d.prevalence IS NOT NULL
RETURN d.name AS 疾病, d.prevalence AS 患病率
ORDER BY d.prevalence DESC LIMIT 10
""",

    "drug_usage_count": """
MATCH (dr:Drug {name: $drug_name})-[:TREATS]->(d:Disease)
WITH count(DISTINCT d) AS 适应症数量
RETURN 适应症数量
""",

    "symptom_frequency": """
MATCH (s:Symptom {name: $symptom_name})<-[:HAS_SYMPTOM]-(d:Disease)
WITH count(DISTINCT d) AS 相关疾病数
RETURN 相关疾病数
""",
}
