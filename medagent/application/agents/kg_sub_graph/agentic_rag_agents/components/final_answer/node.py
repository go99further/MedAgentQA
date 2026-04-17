from typing import Any, Callable, Coroutine

from ...components.state import OverallState

_SAFE_REFUSAL = (
    "抱歉，未能从知识图谱中检索到足够可靠的信息来回答您的问题。"
    "建议您咨询专业医生或医疗机构获取准确的医疗建议。"
    "以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。"
)


def create_final_answer_node() -> (
    Callable[[OverallState], Coroutine[Any, Any, dict[str, Any]]]
):
    """
    Create a final_answer node for a LangGraph workflow.

    Returns
    -------
    Callable[[OverallState], OutputState]
        The LangGraph node.
    """

    async def final_answer(state: OverallState) -> dict[str, Any]:
        """
        Construct a final answer. Handles Evidence Verifier REFUSE decision.
        """
        verifier_decision = state.get("verifier_decision", "")
        if verifier_decision == "safe_refusal":
            answer = _SAFE_REFUSAL
        else:
            answer = state.get("summary", " ")

        history_record = {
            "question": state.get("question", ""),
            "answer": answer,
            "cyphers": [
                {
                    "task": c.task if hasattr(c, "task") else c.get("task", ""),
                    "records": c.records if hasattr(c, "records") else c.get("records", {}),
                }
                for c in state.get("cyphers", list())
            ],
        }

        return {
            "answer": answer,
            "steps": ["final_answer"],
            "history": [history_record],
        }

    return final_answer
