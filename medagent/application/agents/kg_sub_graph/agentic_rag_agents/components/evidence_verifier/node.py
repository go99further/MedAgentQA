"""
Evidence Verifier — Agentic RAG 核心模块

在检索结果和生成之间插入验证层：
  检索 → Evidence Verifier → 充分则生成 / 不足则 Refine Query 重检索（最多2轮）

扩展接口：VerifierStrategy Protocol，未来可替换为 Self-RAG / CRAG 策略。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from medagent.infrastructure.core.logger import get_logger

verifier_logger = get_logger(service="evidence-verifier")


class VerifierDecision(str, Enum):
    PROCEED = "proceed"       # 证据充分，直接生成
    REFINE = "refine_query"   # 证据不足，重新检索
    REFUSE = "safe_refusal"   # 无法找到可靠证据，安全拒绝


@runtime_checkable
class VerifierStrategy(Protocol):
    """扩展接口：未来可替换为 Self-RAG / CRAG 策略。"""

    def verify(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        refine_round: int,
        refined_queries: List[str],
    ) -> VerifierDecision:
        ...


@dataclass
class DefaultVerifierStrategy:
    """
    基础实现：相关性评分 + 覆盖度检查 + 防循环机制。

    判断逻辑：
    1. 检索结果为空 → REFINE
    2. 有效 chunk 数 < MIN_CHUNKS → REFINE
    3. 最高相关性分数 < MIN_RELEVANCE_SCORE → REFINE
    4. 已达 MAX_REFINE_ROUNDS 次 → REFUSE
    5. 否则 → PROCEED

    防循环：新 refine query 与历史查询余弦相似度 > LOOP_THRESHOLD → REFUSE
    """

    min_chunks: int = 2
    min_relevance_score: float = 0.3
    max_refine_rounds: int = 2
    loop_threshold: float = 0.92

    def verify(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        refine_round: int,
        refined_queries: List[str],
    ) -> VerifierDecision:
        if refine_round >= self.max_refine_rounds:
            verifier_logger.info(
                "Evidence Verifier: max refine rounds ({}) reached → REFUSE",
                self.max_refine_rounds,
            )
            return VerifierDecision.REFUSE

        if not contexts:
            verifier_logger.info("Evidence Verifier: no contexts → REFINE")
            return VerifierDecision.REFINE

        # 计算有效 chunk 数和最高相关性分数
        valid_chunks = [
            c for c in contexts
            if c.get("content") and str(c.get("content", "")).strip()
        ]
        if len(valid_chunks) < self.min_chunks:
            verifier_logger.info(
                "Evidence Verifier: only {} valid chunks (< {}) → REFINE",
                len(valid_chunks),
                self.min_chunks,
            )
            return VerifierDecision.REFINE

        scores = [
            float(c.get("score") or c.get("similarity") or c.get("rerank_score") or 0.0)
            for c in valid_chunks
        ]
        max_score = max(scores) if scores else 0.0
        if max_score < self.min_relevance_score:
            verifier_logger.info(
                "Evidence Verifier: max relevance score {:.3f} < {:.3f} → REFINE",
                max_score,
                self.min_relevance_score,
            )
            return VerifierDecision.REFINE

        verifier_logger.info(
            "Evidence Verifier: {} valid chunks, max_score={:.3f} → PROCEED",
            len(valid_chunks),
            max_score,
        )
        return VerifierDecision.PROCEED


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量的余弦相似度（用于防循环检测）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_REFINE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "你是医疗检索查询优化专家。根据原始问题和已检索到的不充分结果，"
            "生成一个更精确的检索查询，以获取更相关的医疗信息。\n"
            "要求：\n"
            "- 保留原始问题的核心医疗意图\n"
            "- 使用更具体的医学术语\n"
            "- 避免与原始查询完全相同\n"
            "- 只输出改进后的查询字符串，不要解释"
        ),
    ),
    (
        "human",
        (
            "原始问题：{question}\n\n"
            "已检索结果摘要（不充分）：\n{context_summary}\n\n"
            "历史改写查询（避免重复）：{prior_queries}\n\n"
            "请输出一个改进的检索查询："
        ),
    ),
])


async def _generate_refine_query(
    llm: BaseChatModel,
    question: str,
    contexts: List[Dict[str, Any]],
    refined_queries: List[str],
) -> str:
    """调用 LLM 生成改进的检索查询。"""
    snippets = []
    for c in contexts[:3]:
        content = str(c.get("content") or "").strip()[:200]
        if content:
            snippets.append(content)
    context_summary = "\n".join(snippets) if snippets else "（无检索结果）"
    prior = "、".join(refined_queries) if refined_queries else "（无）"

    try:
        messages = _REFINE_PROMPT.format_messages(
            question=question,
            context_summary=context_summary,
            prior_queries=prior,
        )
        response = await llm.ainvoke(messages)
        refined = getattr(response, "content", str(response)).strip()
        # 去掉可能的引号
        refined = refined.strip('"\'「」')
        return refined or question
    except Exception as exc:
        verifier_logger.warning("Refine query generation failed: {}", exc)
        return question


def create_evidence_verifier_node(
    llm: BaseChatModel,
    strategy: Optional[VerifierStrategy] = None,
    embedding_fn=None,
):
    """
    工厂函数：返回一个可插入 LangGraph StateGraph 的 evidence_verifier 节点函数。

    参数
    ----
    llm : BaseChatModel
        用于生成 refine query 的 LLM。
    strategy : VerifierStrategy, optional
        验证策略，默认使用 DefaultVerifierStrategy。
        若提供自定义策略则忽略 configurable 中的阈值参数。
    embedding_fn : callable, optional
        接受字符串返回 List[float] 的 embedding 函数，用于防循环相似度检测。
        若为 None，则跳过相似度检测。

    返回的节点函数签名
    ------------------
    async def evidence_verifier(state: dict, *, config: RunnableConfig) -> dict
        读取 state 中的 local_results / milvus_results / postgres_results，
        写入 verifier_decision、refined_question、refine_round、refined_queries。

    configurable 支持的键（通过 RunnableConfig 传入）
    -----------------------------------------------
    verifier_min_relevance_score : float  (default 0.3)
    verifier_min_chunks : int             (default 2)
    verifier_max_refine_rounds : int      (default 2)
    """
    _fixed_strategy = strategy  # None → build from configurable at call time

    async def evidence_verifier(state: Dict[str, Any], *, config: RunnableConfig = None) -> Dict[str, Any]:
        # 从 RunnableConfig 读取可覆盖的阈值
        cfg: Dict[str, Any] = {}
        if config is not None:
            if isinstance(config, dict):
                cfg = dict(config.get("configurable", {}) or {})
            else:
                cfg = dict(getattr(config, "configurable", {}) or {})

        if _fixed_strategy is not None:
            _strategy = _fixed_strategy
            _loop_threshold = getattr(_fixed_strategy, "loop_threshold", 0.92)
        else:
            _strategy = DefaultVerifierStrategy(
                min_relevance_score=cfg.get("verifier_min_relevance_score", 0.3),
                min_chunks=int(cfg.get("verifier_min_chunks", 2)),
                max_refine_rounds=int(cfg.get("verifier_max_refine_rounds", 2)),
            )
            _loop_threshold = _strategy.loop_threshold

        question = state.get("question", "")
        refine_round: int = state.get("refine_round", 0)
        refined_queries: List[str] = list(state.get("refined_queries") or [])

        # 收集所有检索结果
        contexts: List[Dict[str, Any]] = (
            state.get("local_results")
            or (state.get("milvus_results", []) + state.get("postgres_results", []))
            or state.get("cyphers", [])
            or []
        )

        decision = _strategy.verify(question, contexts, refine_round, refined_queries)

        if decision == VerifierDecision.REFINE:
            refined_q = await _generate_refine_query(llm, question, contexts, refined_queries)

            # 防循环检测：若 embedding_fn 可用，检查与历史查询的相似度
            if embedding_fn and refined_queries:
                try:
                    new_emb = embedding_fn(refined_q)
                    for prev_q in refined_queries:
                        prev_emb = embedding_fn(prev_q)
                        sim = _cosine_similarity(new_emb, prev_emb)
                        if sim > _loop_threshold:
                            verifier_logger.warning(
                                "Refine query loop detected (sim={:.3f} > {:.3f}), switching to REFUSE",
                                sim,
                                _loop_threshold,
                            )
                            decision = VerifierDecision.REFUSE
                            refined_q = question
                            break
                except Exception as exc:
                    verifier_logger.warning("Loop detection embedding failed: {}", exc)

            if decision == VerifierDecision.REFINE:
                refined_queries.append(refined_q)
                verifier_logger.info(
                    "Evidence Verifier: REFINE round {} → refined_q='{}'",
                    refine_round + 1,
                    refined_q[:80],
                )
                return {
                    "verifier_decision": VerifierDecision.REFINE,
                    "question": refined_q,
                    "refine_round": refine_round + 1,
                    "refined_queries": refined_queries,
                    "steps": ["evidence_verifier"],
                }

        if decision == VerifierDecision.REFUSE:
            verifier_logger.info("Evidence Verifier: REFUSE — no reliable evidence found")
            return {
                "verifier_decision": VerifierDecision.REFUSE,
                "question": question,
                "refine_round": refine_round,
                "refined_queries": refined_queries,
                "steps": ["evidence_verifier"],
            }

        # PROCEED
        verifier_logger.info("Evidence Verifier: PROCEED")
        return {
            "verifier_decision": VerifierDecision.PROCEED,
            "question": question,
            "refine_round": refine_round,
            "refined_queries": refined_queries,
            "steps": ["evidence_verifier"],
        }

    return evidence_verifier


def create_graphrag_evidence_verifier_node(
    llm: BaseChatModel,
    max_refine_rounds: int = 2,
):
    """
    GraphRAG 专用 Evidence Verifier。

    检查 summarize 节点产出的 summary 字段是否有实质内容：
    - 空 summary 或 "No data to summarize." → REFINE（重新规划查询）
    - 达到最大重试次数 → REFUSE（安全拒绝）
    - 否则 → PROCEED
    """

    async def graphrag_evidence_verifier(state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("question", "")
        refine_round: int = state.get("refine_round", 0)
        refined_queries: List[str] = list(state.get("refined_queries") or [])
        summary: str = state.get("summary", "").strip()

        NO_DATA_MARKERS = ("No data to summarize", "暂未查询到", "未查询到相关")

        if refine_round >= max_refine_rounds:
            verifier_logger.info("GraphRAG Verifier: max rounds reached → REFUSE")
            return {
                "verifier_decision": VerifierDecision.REFUSE,
                "question": question,
                "refine_round": refine_round,
                "refined_queries": refined_queries,
                "steps": ["evidence_verifier"],
            }

        if not summary or any(m in summary for m in NO_DATA_MARKERS):
            refined_q = await _generate_refine_query(llm, question, [], refined_queries)
            refined_queries.append(refined_q)
            verifier_logger.info(
                "GraphRAG Verifier: empty/no-data summary → REFINE round {} → '{}'",
                refine_round + 1,
                refined_q[:80],
            )
            return {
                "verifier_decision": VerifierDecision.REFINE,
                "question": refined_q,
                "refine_round": refine_round + 1,
                "refined_queries": refined_queries,
                "steps": ["evidence_verifier"],
            }

        verifier_logger.info("GraphRAG Verifier: summary has content → PROCEED")
        return {
            "verifier_decision": VerifierDecision.PROCEED,
            "question": question,
            "refine_round": refine_round,
            "refined_queries": refined_queries,
            "steps": ["evidence_verifier"],
        }

    return graphrag_evidence_verifier
