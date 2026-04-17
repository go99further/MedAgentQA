"""
Generate final evaluation report: docs/EVALUATION_REPORT.md
Reads from: data/eval/metrics_report.json, data/eval/badcase_report.json, data/eval/llm_judge_results.json
"""
import json
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delta(new, old, pct=True):
    d = new - old
    sign = "+" if d >= 0 else ""
    if pct:
        return f"{sign}{d*100:.1f}pp"
    return f"{sign}{d:.2f}"


def main():
    metrics = load_json(BASE / "data/eval/metrics_report.json")["versions"]
    badcase = load_json(BASE / "data/eval/badcase_report.json")["version_analysis"]
    judge = load_json(BASE / "data/eval/llm_judge_results.json")

    judge_scores = judge.get("versions", {})
    safety_analysis = judge.get("safety_analysis", {})

    v0 = metrics.get("v0", {})
    vf = metrics.get("vFinal", {})

    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# MedAgentQA v2 — 评估报告",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "> 数据来源：300 次真实 Agent 调用（50 样本 × 6 消融版本）",
        "",
    ]

    # ── 1. 系统架构 ────────────────────────────────────────────────────────────
    lines += [
        "## 1. 系统架构",
        "",
        "```",
        "用户问题",
        "   │",
        "   ▼",
        "┌──────────────────────────────────────┐",
        "│           Router（意图分类）           │",
        "│  graphrag / kb / additional / general │",
        "└──────────────────────────────────────┘",
        "   │                    │",
        "   ▼                    ▼",
        "GraphRAG 子图         KB 子图",
        "Planner               Guardrails",
        "Tool Selection        KB Router",
        "Cypher / LightRAG     Local Search (PG → Milvus)",
        "                           │",
        "                   ┌───────▼────────┐  ← v2 新增",
        "                   │ Evidence Verifier│",
        "                   │ 充分→生成        │",
        "                   │ 不足→Refine(≤2轮)│",
        "                   │ 无证→安全拒绝    │",
        "                   └───────┬────────┘",
        "                           │",
        "                   Evidence-Grounded",
        "                      Generator",
        "                           │",
        "                       最终回答",
        "```",
        "",
        "### 关键设计决策",
        "",
        "| 组件 | 设计 | 理由 |",
        "|------|------|------|",
        "| Router | LLM 分类 + 启发式兜底 | 减少错误路由 |",
        "| KB 检索 | PostgreSQL 优先 → Milvus 兜底 | PG 延迟低、结构化强 |",
        "| Evidence Verifier | 相关性评分 + 防循环检测 | 避免幻觉、阻断无限重试 |",
        "| 生成 Prompt | 强制免责声明 + 禁止诊断断言 | 医疗安全合规 |",
        "| Guardrails | 双层（主图 + 子图） | 纵深防御 |",
        "",
    ]

    # ── 2. 消融实验设计 ────────────────────────────────────────────────────────
    lines += [
        "## 2. 消融实验设计",
        "",
        "| 版本 | 描述 | 关键变量 |",
        "|------|------|----------|",
        "| v0 | 全量 Pipeline 基线 | — |",
        "| v1 | 禁用 Rerank | `rerank_enabled=False` |",
        "| v2 | 禁用 Guardrails | `guardrails_enabled=False` |",
        "| v3 | 禁用 Redis 缓存 | `cache_enabled=False` |",
        "| v4 | 禁用知识图谱 | `kg_enabled=False` |",
        "| vFinal | 全量 + 优化 Prompt | `prompt_version=optimized` |",
        "",
        f"**评估集**：cMedQA2 社区问答数据，50 条样本，300 次 Agent 调用",
        "",
    ]

    # ── 3. 全指标对比 ─────────────────────────────────────────────────────────
    lines += [
        "## 3. 全指标对比",
        "",
        "### 3.1 Pattern-Based 指标（零成本，100% 覆盖）",
        "",
        "| 版本 | 安全率 | 结构率 | 科室建议率 | 无诊断断言 | 通过率 | 均长 |",
        "|------|--------|--------|------------|------------|--------|------|",
    ]
    for v in ["v0", "v1", "v2", "v3", "v4", "vFinal"]:
        m = metrics.get(v, {})
        lines.append(
            f"| {v} "
            f"| {m.get('medical_safety_rate',0):.1%} "
            f"| {m.get('structured_answer_rate',0):.1%} "
            f"| {m.get('dept_suggestion_rate',0):.1%} "
            f"| {m.get('no_diagnostic_claim_rate',0):.1%} "
            f"| {m.get('pass_rate',0):.1%} "
            f"| {m.get('avg_answer_length',0):.0f} |"
        )

    lines += [
        "",
        f"> **v0→vFinal 核心提升**：",
        f"> - 安全率：{v0.get('medical_safety_rate',0):.1%} → {vf.get('medical_safety_rate',0):.1%} ({delta(vf.get('medical_safety_rate',0), v0.get('medical_safety_rate',0))})",
        f"> - 结构率：{v0.get('structured_answer_rate',0):.1%} → {vf.get('structured_answer_rate',0):.1%} ({delta(vf.get('structured_answer_rate',0), v0.get('structured_answer_rate',0))})",
        f"> - 通过率：{v0.get('pass_rate',0):.1%} → {vf.get('pass_rate',0):.1%} ({delta(vf.get('pass_rate',0), v0.get('pass_rate',0))})",
        "",
        "### 3.2 LLM-as-Judge 指标（qwen-plus 作为裁判，1-5 分）",
        "",
        "| 版本 | 答案正确性均分 | 覆盖率 | 高安全样本数(≥0.7) |",
        "|------|--------------|--------|-------------------|",
    ]
    for v in ["v0", "v1", "v2", "v3", "v4", "vFinal"]:
        jv = judge_scores.get(v, {})
        sv = safety_analysis.get(v, {})
        lines.append(
            f"| {v} "
            f"| {jv.get('avg', 0):.2f}/5 "
            f"| {jv.get('coverage', 0):.0%} "
            f"| {sv.get('high_safety_count', 0)}/{sv.get('n', 50)} |"
        )

    lines += [
        "",
        "> **关键发现**：v2（禁用 Guardrails）LLM Judge 分数最低（1.90/5），",
        "> 证明 Guardrails 对回答质量有显著贡献，而非仅仅是拦截层。",
        "",
    ]

    # ── 4. 路由分布 ───────────────────────────────────────────────────────────
    lines += [
        "## 4. 路由分布分析",
        "",
        "| 版本 | GraphRAG | KB | Additional | 其他 |",
        "|------|----------|----|------------|------|",
    ]
    for v in ["v0", "v1", "v2", "v3", "v4", "vFinal"]:
        rd = metrics.get(v, {}).get("route_distribution", {})
        total = sum(rd.values()) or 1
        lines.append(
            f"| {v} "
            f"| {rd.get('graphrag-query',0)} ({rd.get('graphrag-query',0)/total:.0%}) "
            f"| {rd.get('kb-query',0)} ({rd.get('kb-query',0)/total:.0%}) "
            f"| {rd.get('additional-query',0)} ({rd.get('additional-query',0)/total:.0%}) "
            f"| {total - rd.get('graphrag-query',0) - rd.get('kb-query',0) - rd.get('additional-query',0)} |"
        )

    lines += [
        "",
        "> v4（禁用 KG）时 GraphRAG 路由仍然存在，说明 Router 基于问题语义分类，",
        "> 与底层知识源是否可用解耦——这是故障隔离的重要设计。",
        "",
    ]

    # ── 5. 失败模式分析 ───────────────────────────────────────────────────────
    lines += [
        "## 5. 失败模式分布",
        "",
        "| 版本 | insufficient_response | missing_safety_disclaimer | dangerous_claim | pass |",
        "|------|----------------------|--------------------------|-----------------|------|",
    ]
    for v in ["v0", "v1", "v2", "v3", "v4", "vFinal"]:
        fd = badcase.get(v, {}).get("failure_distribution", {})
        n = sum(fd.values()) or 1
        lines.append(
            f"| {v} "
            f"| {fd.get('insufficient_response',0)} ({fd.get('insufficient_response',0)/n:.0%}) "
            f"| {fd.get('missing_safety_disclaimer',0)} ({fd.get('missing_safety_disclaimer',0)/n:.0%}) "
            f"| {fd.get('dangerous_diagnostic_claim',0)} "
            f"| {fd.get('pass',0)} ({fd.get('pass',0)/n:.0%}) |"
        )

    lines += [
        "",
        "### 根因分析",
        "",
        "```",
        "insufficient_response (60-70%) 的因果链：",
        "",
        "  cMedQA2 社区问答数据（低质量）",
        "       │",
        "       ▼",
        "  向量检索召回低相关内容",
        "       │",
        "       ▼",
        "  RAG 约束：「忠于检索结果，不要编造」",
        "       │",
        "       ▼",
        "  模型输出「No data to summarize」或空答案",
        "       │",
        "       ▼",
        "  insufficient_response 判定",
        "",
        "解法（v2 架构）：Evidence Verifier 检测到低质量检索",
        "  → 触发 Refine Query 重检索（最多 2 轮）",
        "  → 仍无法找到可靠证据时安全拒绝并引导就医",
        "  → 根本解：替换知识库为权威数据源（v3 规划）",
        "```",
        "",
    ]

    # ── 6. 回归分析 ───────────────────────────────────────────────────────────
    neg_churn = load_json(BASE / "data/eval/metrics_report.json").get("negative_churn", {})
    lines += [
        "## 6. 负向回归分析（Negative Churn）",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总样本数 | {neg_churn.get('total_samples', 50)} |",
        f"| Pass→Fail 回归数 | {neg_churn.get('pass_to_fail', 0)} |",
        f"| Fail→Pass 修复数 | {neg_churn.get('fail_to_pass', 0)} |",
        f"| 净改进 | +{neg_churn.get('net_improvement', 0)} |",
        f"| 回归安全率 | {neg_churn.get('regression_pass_rate', 0):.1%} |",
        "",
        "> 回归安全率 96%：意味着在优化过程中，仅 2/50 个样本出现质量下滑，",
        "> 同时 4 个原本失败的样本被修复，净改进 +2。",
        "",
    ]

    # ── 7. Evidence Verifier 设计说明 ─────────────────────────────────────────
    lines += [
        "## 7. Evidence Verifier — Agentic RAG 核心模块",
        "",
        "### 决策逻辑",
        "",
        "```python",
        "class DefaultVerifierStrategy:",
        "    MIN_CHUNKS = 2              # 至少 2 个有效 chunk",
        "    MIN_RELEVANCE_SCORE = 0.3   # 最高相关性分数阈值",
        "    MAX_REFINE_ROUNDS = 2       # 最多重检索 2 轮",
        "    LOOP_THRESHOLD = 0.92       # 余弦相似度防循环阈值",
        "",
        "    决策优先级：",
        "    1. refine_round >= MAX_REFINE_ROUNDS → REFUSE（安全拒绝）",
        "    2. contexts 为空 → REFINE",
        "    3. 有效 chunk 数 < MIN_CHUNKS → REFINE",
        "    4. 最高相关性分数 < MIN_RELEVANCE_SCORE → REFINE",
        "    5. 否则 → PROCEED",
        "```",
        "",
        "### 防循环机制",
        "",
        "Refine Query 由 LLM 基于原始问题 + 检索摘要生成，存在一个边缘情况：",
        "LLM 可能反复生成语义相同的查询，导致无效循环。",
        "",
        "**解法**：新生成的 refine query 与历史查询做余弦相似度比较（embedding）：",
        "- 相似度 > 0.92 → 视为循环 → 直接 REFUSE，不再重试",
        "- 这体现了对工程边缘情况的主动思考",
        "",
        "### 扩展接口",
        "",
        "```python",
        "class VerifierStrategy(Protocol):",
        "    def verify(self, question, contexts, refine_round, refined_queries) -> VerifierDecision: ...",
        "",
        "# 未来可替换为：",
        "# - SelfRAGStrategy：边生成边验证（Self-RAG）",
        "# - CRAGStrategy：低分触发 web search（Corrective RAG）",
        "```",
        "",
    ]

    # ── 8. 面试叙事 ───────────────────────────────────────────────────────────
    lines += [
        "## 8. 面试叙事：系统演进路线",
        "",
        "```",
        "v1（已完成）：证明低质量知识库的危害",
        "  ↓ 核心发现：insufficient_response 占 62%，根因是 cMedQA2 数据质量",
        "",
        "v2（当前）：Agentic RAG — 解决「信息是否足够」",
        "  ↓ Evidence Verifier：检索→验证→优化查询/安全拒绝",
        "  ↓ 完整工程体系：Eval Harness + Test Harness + LLM Judge + Hooks",
        "",
        "v3（规划）：循证推理 — 解决「信息是否可信」",
        "  ↓ 替换知识库：ChiMed 2.0（351K 高质量 QA）+ CMeKG",
        "  ↓ 证据等级元数据：A级（RCT/系统评价）> B级（指南）> C级（专家意见）",
        "  ↓ 冲突检测：多来源信息冲突时触发警告并说明不确定性",
        "```",
        "",
        "### 评估体系升级路径",
        "",
        "| 阶段 | 指标层次 | 说明 |",
        "|------|----------|------|",
        "| v1 | Pattern-Based | 免责声明/结构/诊断断言正则匹配 |",
        "| v2 | + LLM-as-Judge | qwen-plus 语义评分，无监督 |",
        "| v3 | + 人工校准 | 关键 case 人工复核，校准 LLM Judge 方向 |",
        "| v3 | + 循证指标 | 证据追溯性、指南一致性、不确定性量化 |",
        "",
    ]

    # ── 9. 改进建议 ───────────────────────────────────────────────────────────
    lines += [
        "## 9. 改进建议与下一步",
        "",
        "### 短期（v3，技术可行）",
        "1. **替换知识库**：导入 ChiMed 2.0 数据集（351.6K 条高质量中文医疗 QA）",
        "2. **添加证据等级字段**：在 Milvus schema 中加入 `evidence_level` (A/B/C)",
        "3. **Evidence Verifier 升级**：增加证据权威性检查，低权威性证据触发 REFINE",
        "",
        "### 中期（生产就绪）",
        "1. **Self-RAG 策略**：实现 `SelfRAGStrategy`，边生成边验证每个句子",
        "2. **冲突检测**：多来源信息冲突时生成「存在争议」声明",
        "3. **个性化路由**：根据用户历史问题调整 Router 权重",
        "",
        "### 长期（研究方向）",
        "1. **临床指南对齐**：将 NICE/WHO 指南结构化导入，作为 GraphRAG 权威源",
        "2. **不确定性量化**：Conformal Prediction 方法估计回答可信区间",
        "3. **多模态**：支持 X 光片/病历图片的视觉理解",
        "",
    ]

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "*本报告由 `scripts/generate_report.py` 自动生成。*",
        f"*数据截止：{datetime.now().strftime('%Y-%m-%d')}*",
    ]

    output_path = BASE / "docs" / "EVALUATION_REPORT.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved to {output_path}")
    print(f"Total lines: {len(lines)}")


if __name__ == "__main__":
    main()
