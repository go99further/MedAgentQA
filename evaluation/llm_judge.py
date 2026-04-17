"""
LLM-as-Judge 指标 — 可插拔 MetricFn 实现

3 个 Judge 函数，均实现 evaluation/harness.py 中的 MetricFn 协议：
- answer_correctness_judge  : 1-5 分，对比 reference_answer
- context_relevance_judge   : 每个 chunk 相关/不相关
- evidence_traceability_judge: 主张是否可追溯到上下文

用法：
    from evaluation.llm_judge import answer_correctness_judge
    harness = EvaluationHarness(graph, metrics=[answer_correctness_judge])
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List

from medagent.infrastructure.core.logger import get_logger

judge_logger = get_logger(service="llm-judge")

# ---------------------------------------------------------------------------
# LLM client (DashScope / OpenAI-compatible)
# ---------------------------------------------------------------------------

def _get_llm_client():
    """Lazy-init OpenAI-compatible client pointing at DashScope."""
    try:
        from openai import AsyncOpenAI
        return AsyncOpenAI(
            api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    except ImportError:
        raise RuntimeError("openai package required for LLM-as-Judge. pip install openai")


_JUDGE_MODEL = "qwen-plus"
_CONCURRENCY = 5


async def _call_judge(client, prompt: str) -> Dict[str, Any]:
    """单次 LLM judge 调用，返回解析后的 JSON dict。"""
    try:
        resp = await client.chat.completions.create(
            model=_JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256,
        )
        raw = resp.choices[0].message.content.strip()
        # 提取 JSON（可能被 markdown 包裹）
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as exc:
        judge_logger.warning("Judge call failed: {}", exc)
        return {}


# ---------------------------------------------------------------------------
# 1. answer_correctness_judge
# ---------------------------------------------------------------------------

_CORRECTNESS_PROMPT = """\
你是医学专家评审员。请对比以下生成回答与参考答案，从以下维度评分(1-5)：
- 医学信息准确性：关键症状、用药、诊疗方案是否正确
- 信息完整性：参考答案中的要点是否被覆盖
- 安全性：是否包含必要的免责声明和就医建议

用户问题：{question}
生成回答：{answer}
参考答案：{reference}

只输出 JSON，格式：{{"score": 1-5, "reason": "简短理由"}}"""


async def _correctness_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    client = _get_llm_client()
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(r: Dict) -> Dict:
        if not r.get("success") or not r.get("reference_answer"):
            return {"score": None, "reason": "skipped"}
        prompt = _CORRECTNESS_PROMPT.format(
            question=r.get("question", ""),
            answer=r.get("answer", "")[:800],
            reference=r.get("reference_answer", "")[:400],
        )
        async with sem:
            result = await _call_judge(client, prompt)
        return result

    return await asyncio.gather(*[_one(r) for r in records])


def answer_correctness_judge(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MetricFn: LLM-as-Judge answer correctness (1-5 scale)."""
    results = asyncio.get_event_loop().run_until_complete(_correctness_batch(records))
    scores = [r.get("score") for r in results if r.get("score") is not None]
    avg = sum(scores) / len(scores) if scores else 0.0
    dist = {str(i): scores.count(i) for i in range(1, 6)}
    return {
        "answer_correctness_avg": round(avg, 3),
        "answer_correctness_dist": dist,
        "answer_correctness_coverage": round(len(scores) / len(records), 3) if records else 0,
    }


# ---------------------------------------------------------------------------
# 2. context_relevance_judge
# ---------------------------------------------------------------------------

_RELEVANCE_PROMPT = """\
判断以下检索片段是否与用户问题相关。

用户问题：{question}
检索片段：{chunk}

只输出 JSON，格式：{{"relevant": true/false, "reason": "一句话"}}"""


async def _relevance_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    client = _get_llm_client()
    sem = asyncio.Semaphore(_CONCURRENCY)
    per_record = []

    async def _one_chunk(question: str, chunk: str) -> bool:
        prompt = _RELEVANCE_PROMPT.format(question=question, chunk=chunk[:400])
        async with sem:
            result = await _call_judge(client, prompt)
        return bool(result.get("relevant", False))

    for r in records:
        contexts = r.get("contexts") or []
        if not contexts or not r.get("success"):
            per_record.append({"relevant_count": 0, "total_count": 0, "relevance_rate": 0.0})
            continue
        tasks = [_one_chunk(r.get("question", ""), str(c)[:400]) for c in contexts[:5]]
        flags = await asyncio.gather(*tasks)
        rel = sum(flags)
        per_record.append({
            "relevant_count": rel,
            "total_count": len(flags),
            "relevance_rate": round(rel / len(flags), 3) if flags else 0.0,
        })

    return per_record


def context_relevance_judge(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MetricFn: LLM-as-Judge context relevance per chunk."""
    per_record = asyncio.get_event_loop().run_until_complete(_relevance_batch(records))
    rates = [r["relevance_rate"] for r in per_record if r["total_count"] > 0]
    avg = sum(rates) / len(rates) if rates else 0.0
    return {
        "context_relevance_avg": round(avg, 3),
        "context_relevance_coverage": round(len(rates) / len(records), 3) if records else 0,
    }


# ---------------------------------------------------------------------------
# 3. evidence_traceability_judge
# ---------------------------------------------------------------------------

_TRACEABILITY_PROMPT = """\
你是医学信息核查员。检查以下回答中的关键医学主张是否能在检索上下文中找到支撑。

用户问题：{question}
生成回答：{answer}
检索上下文：{contexts}

请判断：
1. 回答中有哪些关键医学主张（最多3条）
2. 每条主张是否在上下文中有依据

只输出 JSON，格式：
{{"traceability_score": 0.0-1.0, "unsupported_claims": ["主张1", ...], "reason": "简短说明"}}"""


async def _traceability_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    client = _get_llm_client()
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(r: Dict) -> Dict:
        if not r.get("success") or not r.get("answer"):
            return {"traceability_score": None}
        contexts = r.get("contexts") or []
        ctx_text = "\n".join(str(c)[:200] for c in contexts[:3]) or "（无检索上下文）"
        prompt = _TRACEABILITY_PROMPT.format(
            question=r.get("question", ""),
            answer=r.get("answer", "")[:600],
            contexts=ctx_text,
        )
        async with sem:
            result = await _call_judge(client, prompt)
        return result

    return await asyncio.gather(*[_one(r) for r in records])


def evidence_traceability_judge(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MetricFn: LLM-as-Judge evidence traceability (0-1 scale)."""
    results = asyncio.get_event_loop().run_until_complete(_traceability_batch(records))
    scores = [r.get("traceability_score") for r in results if r.get("traceability_score") is not None]
    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        "evidence_traceability_avg": round(avg, 3),
        "evidence_traceability_coverage": round(len(scores) / len(records), 3) if records else 0,
    }
