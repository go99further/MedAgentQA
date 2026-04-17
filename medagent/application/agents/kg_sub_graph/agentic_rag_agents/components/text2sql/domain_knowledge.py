"""
Domain knowledge for the medical knowledge graph SQL schema.

These descriptions surface context about the actual tables, columns, and
relationships available in the medical knowledge database to the LLM prompts.
"""

from typing import Dict, List, Tuple

# Table level descriptions used to enrich schema prompts.
TABLE_DESCRIPTIONS: Dict[str, str] = {
    "diseases": (
        "疾病主表，记录疾病的基础信息、ICD编码、严重程度、是否传染病等属性。"
        "主键 id，关联科室的外键为 department_id。"
    ),
    "symptoms": (
        "症状信息表，包含症状名称、描述、严重程度分级等属性。"
    ),
    "disease_symptoms": (
        "疾病与症状的关联表，记录某疾病可能出现的症状及出现频率。"
        "通过 disease_id 连接疾病，symptom_id 连接症状。"
    ),
    "drugs": (
        "药物信息表，包含药物名称、分类、剂型、规格等基础信息。"
    ),
    "drug_indications": (
        "药物适应症关联表，记录药物用于治疗哪些疾病。"
        "通过 drug_id 连接药物，disease_id 连接疾病。"
    ),
    "departments": (
        "科室信息表，存储各科室名称、职能描述及常见疾病范围。"
    ),
    "treatments": (
        "治疗方案表，记录针对某种疾病的治疗方法、疗程和预期效果。"
    ),
}

# Column level descriptions
COLUMN_DESCRIPTIONS: Dict[Tuple[str, str], str] = {
    ("diseases", "name"): "疾病名称（唯一）。",
    ("diseases", "icd_code"): "国际疾病分类编码（ICD-10）。",
    ("diseases", "description"): "疾病简介或背景说明。",
    ("diseases", "severity"): "疾病严重程度，取值为 mild/moderate/severe/critical。",
    ("diseases", "is_contagious"): "是否传染病，布尔值。",
    ("diseases", "department_id"): "关联科室 departments.id 的外键。",
    ("symptoms", "name"): "症状名称（唯一）。",
    ("symptoms", "description"): "症状的详细描述。",
    ("symptoms", "severity_level"): "症状严重程度分级，1-5分。",
    ("disease_symptoms", "disease_id"): "关联疾病 diseases.id 的外键。",
    ("disease_symptoms", "symptom_id"): "关联症状 symptoms.id 的外键。",
    ("disease_symptoms", "frequency"): "该症状在此疾病中出现的频率，取值 common/occasional/rare。",
    ("drugs", "name"): "药物通用名（唯一）。",
    ("drugs", "category"): "药物分类（如 抗生素、降压药、降糖药）。",
    ("drugs", "dosage_form"): "剂型（如 片剂、注射剂、胶囊）。",
    ("drugs", "specification"): "规格（如 500mg、10ml）。",
    ("departments", "name"): "科室名称（唯一）。",
    ("departments", "description"): "科室职能描述。",
    ("treatments", "disease_id"): "关联疾病 diseases.id 的外键。",
    ("treatments", "method"): "治疗方法描述。",
    ("treatments", "duration"): "疗程（天）。",
}


RELATIONSHIP_FACTS: List[Dict[str, str]] = [
    {
        "source_table": "diseases",
        "source_column": "department_id",
        "target_table": "departments",
        "target_column": "id",
        "relationship_type": "many-to-one",
        "description": "每种疾病隶属于一个主要科室，未指定时可为空。",
    },
    {
        "source_table": "disease_symptoms",
        "source_column": "disease_id",
        "target_table": "diseases",
        "target_column": "id",
        "relationship_type": "many-to-one",
        "description": "一种疾病可有多种症状，通过 disease_symptoms 关联。",
    },
    {
        "source_table": "disease_symptoms",
        "source_column": "symptom_id",
        "target_table": "symptoms",
        "target_column": "id",
        "relationship_type": "many-to-one",
        "description": "一种症状可出现在多种疾病中。",
    },
    {
        "source_table": "drug_indications",
        "source_column": "drug_id",
        "target_table": "drugs",
        "target_column": "id",
        "relationship_type": "many-to-one",
        "description": "药物适应症关联，一种药可用于多种疾病。",
    },
    {
        "source_table": "drug_indications",
        "source_column": "disease_id",
        "target_table": "diseases",
        "target_column": "id",
        "relationship_type": "many-to-one",
        "description": "疾病可有多种药物治疗方案。",
    },
]


DOMAIN_SUMMARY = """
- 数据库为医疗知识管理场景，核心实体包含疾病 (diseases)、症状 (symptoms)、药物 (drugs)、科室 (departments)、治疗方案 (treatments)。
- diseases.department_id -> departments.id；disease_symptoms.disease_id -> diseases.id；disease_symptoms.symptom_id -> symptoms.id；
  drug_indications.drug_id -> drugs.id；drug_indications.disease_id -> diseases.id。
- diseases.severity 的取值限定为 mild/moderate/severe/critical；disease_symptoms.frequency 的取值限定为 common/occasional/rare。
- 所有查询均应围绕真实存在的表与字段展开，避免凭空构造表名或字段。
- 医疗查询结果仅供参考，不构成诊断依据。
""".strip()
