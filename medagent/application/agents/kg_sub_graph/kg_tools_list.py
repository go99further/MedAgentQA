“””
医疗知识图谱工具定义
基于 medical_kg 模块的问题分类和 Neo4j 医疗图谱模型
“””
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class cypher_query(BaseModel):
    “””医疗知识图谱 Cypher 查询工具

    当用户询问关于疾病、症状、药物、诊疗方案、科室等医疗信息时，使用此工具生成 Cypher 查询语句。

    适用场景包括：
    - 疾病属性查询（病因、症状、并发症、治疗方案等）
    - 药物信息查询（适应症、禁忌症、用法用量等）
    - 症状关联查询（某症状可能对应哪些疾病）
    - 科室导诊查询（某类疾病应去哪个科室）
    - 诊疗流程查询（检查项目、治疗步骤等）
    - 基于属性的疾病筛选（如：所有慢性病、所有传染病等）

    此工具会利用 LLM 生成符合医疗图谱结构的 Cypher 查询语句。
    “””

    task: str = Field(..., description=”医疗相关的查询任务描述，LLM 会根据此任务生成 Cypher 查询语句”)


class predefined_cypher(BaseModel):
    “””预定义医疗 Cypher 查询工具

    此工具包含预定义的 Cypher 查询语句，用于快速响应常见的医疗查询需求。

    根据用户问题类型，可以选择以下类别的查询：

    1. 疾病属性查询 (disease_property)：
       - disease_symptoms: 查询疾病的主要症状
       - disease_causes: 查询疾病的病因
       - disease_treatment: 查询疾病的治疗方案
       - disease_complications: 查询疾病的并发症
       - disease_complete_info: 查询疾病的完整信息

    2. 药物信息查询 (drug_info)：
       - drug_indications: 查询药物的适应症
       - drug_contraindications: 查询药物的禁忌症
       - drug_dosage: 查询药物的用法用量
       - drug_interactions: 查询药物相互作用

    3. 症状关联查询 (symptom_query)：
       - diseases_by_symptom: 根据症状查询可能的疾病
       - symptoms_of_disease: 查询疾病的所有症状

    4. 科室导诊查询 (department_query)：
       - department_by_disease: 查询疾病对应的科室
       - diseases_by_department: 查询某科室常见疾病

    5. 统计分析查询：
       - disease_count_by_type: 统计各类型疾病数量
       - most_common_symptoms: 查询最常见症状

    请根据用户的问题选择最合适的查询，并提供必要的参数。
    “””

    query: str = Field(..., description=”预定义查询的标识符，对应 cypher_dict 中的键”)
    parameters: dict = Field(..., description=”查询所需的参数字典，如 {'disease_name': '糖尿病', 'symptom_name': '多饮多尿'}”)


class microsoft_graphrag_query(BaseModel):
    “””GraphRAG 医疗知识推理工具

    当用户提出需要深度推理、多跳查询或复杂分析的医疗问题时，使用此工具。

    适用场景包括：
    - 需要综合多种疾病信息进行鉴别诊断的问题
    - 复杂的医疗知识推理（如：根据多个症状推断可能的疾病组合）
    - 跨领域的医疗建议（需要结合疾病、药物、科室等多维度信息）
    - 需要对医疗知识进行总结、归纳的问题
    - 开放式的健康咨询和诊疗建议

    此工具利用 Microsoft GraphRAG 技术进行图谱推理和知识生成。
    “””
    query: str = Field(..., description=”需要通过 GraphRAG 进行深度推理的复杂医疗问题”)


class text2sql_query(BaseModel):
    “””结构化数据库查询工具

    当用户提出”问数””统计””报表”类问题，需要访问关系型数据库（如 MySQL、PostgreSQL）时使用。

    适用场景：
    - 患者数量、就诊记录、药物库存等结构化数据统计
    - 基于表字段的筛选、聚合、排序
    - 多表关联、分组统计、趋势分析

    工具参数可选地提供数据库连接信息；若为空，则使用系统默认连接。
    “””

    task: str = Field(..., description=”需要执行的结构化数据库查询任务描述”)
    connection_id: Optional[int] = Field(
        default=None,
        description=”数据库连接配置 ID，留空则使用默认连接”,
    )
    db_type: str = Field(
        default=”MySQL”,
        description=”数据库类型，例如 MySQL、PostgreSQL 等”,
    )
    max_rows: int = Field(
        default=1000,
        description=”结果预览的最大返回行数”,
    )
    connection_string: Optional[str] = Field(
        default=None,
        description=”直接传入的数据库连接字符串，存在时优先级高于 connection_id”,
    )

