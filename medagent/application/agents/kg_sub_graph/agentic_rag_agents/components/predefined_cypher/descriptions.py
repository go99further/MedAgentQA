"""医疗知识图谱预定义 Cypher 查询的描述信息.

该模块为医疗 KG 图谱准备的固定查询提供语义描述，用于帮助 LLM 根据用户提问快速匹配合适的查询。
描述应覆盖查询意图、适用场景以及可能的自然语言问法提示。
"""

# 疾病属性相关查询描述
DISEASE_PROPERTY_QUERY_DESCRIPTIONS = {
    "disease_symptoms": "查询指定疾病的症状列表，适用于用户想了解某种疾病有哪些临床表现。",
    "disease_causes": "查询疾病的病因信息，适用于用户询问某种疾病是由什么原因引起的。",
    "disease_treatments": "查询疾病的治疗方案，适用于用户想了解某种疾病的治疗方法或用药建议。",
    "disease_complications": "查询疾病可能引发的并发症，适用于用户关注疾病进展风险的场景。",
    "disease_complete_info": "汇总疾病的症状、病因、治疗和并发症等综合信息，适用于需要全面了解某种疾病的场景。",
}

# 药物相关查询描述
DRUG_QUERY_DESCRIPTIONS = {
    "drug_indications": "查询药物的适应症，适用于用户想了解某种药物用于治疗哪些疾病。",
    "drug_contraindications": "查询药物的禁忌症，适用于用户想了解哪些情况下不能使用该药物。",
    "drug_side_effects": "查询药物的不良反应，适用于用户关注用药安全的场景。",
    "drug_interactions": "查询药物相互作用，适用于用户同时使用多种药物时的安全性查询。",
    "drug_dosage": "查询药物的常规用法用量，适用于用户询问药物如何服用。",
}

# 症状相关查询描述
SYMPTOM_QUERY_DESCRIPTIONS = {
    "symptom_related_diseases": "根据症状反查可能的疾病，适用于用户描述症状想了解可能是什么疾病。",
    "symptom_severity": "查询症状的严重程度分级，适用于用户想了解某症状是否需要紧急就医。",
}

# 科室相关查询描述
DEPARTMENT_QUERY_DESCRIPTIONS = {
    "disease_department": "查询某种疾病应该挂哪个科室，适用于用户不知道去哪个科室就诊的场景。",
    "department_diseases": "查询某科室常见的疾病列表，适用于用户想了解某科室诊治范围。",
}

# 统计分析查询描述
STATS_QUERY_DESCRIPTIONS = {
    "disease_prevalence": "统计某类疾病的发病率或患病人数，适用于流行病学相关查询。",
    "drug_usage_count": "统计某种药物在多少种疾病治疗中被使用，适用于评估药物用途广度。",
    "symptom_frequency": "统计某症状在多少种疾病中出现，适用于了解症状的诊断价值。",
}

# 合并所有查询描述
QUERY_DESCRIPTIONS = {}
QUERY_DESCRIPTIONS.update(DISEASE_PROPERTY_QUERY_DESCRIPTIONS)
QUERY_DESCRIPTIONS.update(DRUG_QUERY_DESCRIPTIONS)
QUERY_DESCRIPTIONS.update(SYMPTOM_QUERY_DESCRIPTIONS)
QUERY_DESCRIPTIONS.update(DEPARTMENT_QUERY_DESCRIPTIONS)
QUERY_DESCRIPTIONS.update(STATS_QUERY_DESCRIPTIONS)
