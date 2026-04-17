from langchain_core.prompts import ChatPromptTemplate


def create_summarization_prompt_template() -> ChatPromptTemplate:
    “””
    Create a prompt template tailored for summarising medical knowledge graph results.
    “””

    return ChatPromptTemplate.from_messages(
        [
            (
                “system”,
                (
                    “你是一位专业的医疗健康咨询助手。你擅长把医疗知识图谱的查询结果整理成清晰易懂的健康建议，”
                    “帮助用户理解相关医疗信息。保持专业、严谨的语气，避免做出确定性诊断。”
                ),
            ),
            (
                “human”,
                (
                    “事实信息：{results}\n\n”
                    “用户问题：{question}\n\n”
                    “请根据上述事实信息生成医疗健康解读，并遵循以下要求：\n”
                    “* 当事实信息不为空时，仅依据这些内容组织回答，绝不编造。\n”
                    “* 使用简洁段落或条目概括关键要点，可包含：疾病概述、症状说明、治疗建议、注意事项。\n”
                    “* 若涉及多个疾病或多个方面，请分条说明，使用清晰的小标题或编号。\n”
                    “* 如果事实信息为空，请说明暂未查询到相关医疗信息，并建议用户咨询专业医生。\n”
                    “* 若事实缺失某个关键内容，可礼貌提示未知，不要猜测。\n”
                    “* 【必须】结尾包含免责声明：以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。”
                ),
            ),
        ]
    )
