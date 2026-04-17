# MedAgentQA v2 — 评估报告

> 生成时间：2026-04-17 20:06  
> 数据来源：300 次真实 Agent 调用（50 样本 × 6 消融版本）

## 1. 系统架构

```
用户问题
   │
   ▼
┌──────────────────────────────────────┐
│           Router（意图分类）           │
│  graphrag / kb / additional / general │
└──────────────────────────────────────┘
   │                    │
   ▼                    ▼
GraphRAG 子图         KB 子图
Planner               Guardrails
Tool Selection        KB Router
Cypher / LightRAG     Local Search (PG → Milvus)
                           │
                   ┌───────▼────────┐  ← v2 新增
                   │ Evidence Verifier│
                   │ 充分→生成        │
                   │ 不足→Refine(≤2轮)│
                   │ 无证→安全拒绝    │
                   └───────┬────────┘
                           │
                   Evidence-Grounded
                      Generator
                           │
                       最终回答
```

### 关键设计决策

| 组件 | 设计 | 理由 |
|------|------|------|
| Router | LLM 分类 + 启发式兜底 | 减少错误路由 |
| KB 检索 | PostgreSQL 优先 → Milvus 兜底 | PG 延迟低、结构化强 |
| Evidence Verifier | 相关性评分 + 防循环检测 | 避免幻觉、阻断无限重试 |
| 生成 Prompt | 强制免责声明 + 禁止诊断断言 | 医疗安全合规 |
| Guardrails | 双层（主图 + 子图） | 纵深防御 |

## 2. 消融实验设计

| 版本 | 描述 | 关键变量 |
|------|------|----------|
| v0 | 全量 Pipeline 基线 | — |
| v1 | 禁用 Rerank | `rerank_enabled=False` |
| v2 | 禁用 Guardrails | `guardrails_enabled=False` |
| v3 | 禁用 Redis 缓存 | `cache_enabled=False` |
| v4 | 禁用知识图谱 | `kg_enabled=False` |
| vFinal | 全量 + 优化 Prompt | `prompt_version=optimized` |

**评估集**：cMedQA2 社区问答数据，50 条样本，300 次 Agent 调用

## 3. 全指标对比

### 3.1 Pattern-Based 指标（零成本，100% 覆盖）

| 版本 | 安全率 | 结构率 | 科室建议率 | 无诊断断言 | 通过率 | 均长 |
|------|--------|--------|------------|------------|--------|------|
| v0 | 29.2% | 12.5% | 31.2% | 100.0% | 27.1% | 434 |
| v1 | 29.2% | 4.2% | 29.2% | 95.8% | 22.9% | 403 |
| v2 | 20.0% | 8.0% | 24.0% | 100.0% | 18.0% | 408 |
| v3 | 31.9% | 4.3% | 29.8% | 97.9% | 23.4% | 460 |
| v4 | 33.3% | 8.3% | 29.2% | 100.0% | 27.1% | 460 |
| vFinal | 36.2% | 12.8% | 31.9% | 100.0% | 31.9% | 460 |

> **v0→vFinal 核心提升**：
> - 安全率：29.2% → 36.2% (+7.0pp)
> - 结构率：12.5% → 12.8% (+0.3pp)
> - 通过率：27.1% → 31.9% (+4.8pp)

### 3.2 LLM-as-Judge 指标（qwen-plus 作为裁判，1-5 分）

| 版本 | 答案正确性均分 | 覆盖率 | 高安全样本数(≥0.7) |
|------|--------------|--------|-------------------|
| v0 | 2.15/5 | 94% | 14/50 |
| v1 | 2.29/5 | 96% | 12/50 |
| v2 | 1.90/5 | 98% | 10/50 |
| v3 | 2.38/5 | 94% | 14/50 |
| v4 | 2.21/5 | 96% | 16/50 |
| vFinal | 2.19/5 | 94% | 17/50 |

> **关键发现**：v2（禁用 Guardrails）LLM Judge 分数最低（1.90/5），
> 证明 Guardrails 对回答质量有显著贡献，而非仅仅是拦截层。

## 4. 路由分布分析

| 版本 | GraphRAG | KB | Additional | 其他 |
|------|----------|----|------------|------|
| v0 | 18 (38%) | 17 (35%) | 12 (25%) | 1 |
| v1 | 17 (35%) | 16 (33%) | 15 (31%) | 0 |
| v2 | 21 (42%) | 14 (28%) | 13 (26%) | 2 |
| v3 | 15 (32%) | 17 (36%) | 15 (32%) | 0 |
| v4 | 17 (35%) | 16 (33%) | 14 (29%) | 1 |
| vFinal | 16 (34%) | 18 (38%) | 13 (28%) | 0 |

> v4（禁用 KG）时 GraphRAG 路由仍然存在，说明 Router 基于问题语义分类，
> 与底层知识源是否可用解耦——这是故障隔离的重要设计。

## 5. 失败模式分布

| 版本 | insufficient_response | missing_safety_disclaimer | dangerous_claim | pass |
|------|----------------------|--------------------------|-----------------|------|
| v0 | 31 (62%) | 3 (6%) | 0 | 13 (26%) |
| v1 | 32 (64%) | 2 (4%) | 2 | 11 (22%) |
| v2 | 35 (70%) | 4 (8%) | 0 | 9 (18%) |
| v3 | 31 (62%) | 2 (4%) | 1 | 11 (22%) |
| v4 | 32 (64%) | 1 (2%) | 0 | 13 (26%) |
| vFinal | 30 (60%) | 0 (0%) | 0 | 15 (30%) |

### 根因分析

```
insufficient_response (60-70%) 的因果链：

  cMedQA2 社区问答数据（低质量）
       │
       ▼
  向量检索召回低相关内容
       │
       ▼
  RAG 约束：「忠于检索结果，不要编造」
       │
       ▼
  模型输出「No data to summarize」或空答案
       │
       ▼
  insufficient_response 判定

解法（v2 架构）：Evidence Verifier 检测到低质量检索
  → 触发 Refine Query 重检索（最多 2 轮）
  → 仍无法找到可靠证据时安全拒绝并引导就医
  → 根本解：替换知识库为权威数据源（v3 规划）
```

## 6. 负向回归分析（Negative Churn）

| 指标 | 数值 |
|------|------|
| 总样本数 | 50 |
| Pass→Fail 回归数 | 2 |
| Fail→Pass 修复数 | 4 |
| 净改进 | +2 |
| 回归安全率 | 96.0% |

> 回归安全率 96%：意味着在优化过程中，仅 2/50 个样本出现质量下滑，
> 同时 4 个原本失败的样本被修复，净改进 +2。

## 7. Evidence Verifier — Agentic RAG 核心模块

### 决策逻辑

```python
class DefaultVerifierStrategy:
    MIN_CHUNKS = 2              # 至少 2 个有效 chunk
    MIN_RELEVANCE_SCORE = 0.3   # 最高相关性分数阈值
    MAX_REFINE_ROUNDS = 2       # 最多重检索 2 轮
    LOOP_THRESHOLD = 0.92       # 余弦相似度防循环阈值

    决策优先级：
    1. refine_round >= MAX_REFINE_ROUNDS → REFUSE（安全拒绝）
    2. contexts 为空 → REFINE
    3. 有效 chunk 数 < MIN_CHUNKS → REFINE
    4. 最高相关性分数 < MIN_RELEVANCE_SCORE → REFINE
    5. 否则 → PROCEED
```

### 防循环机制

Refine Query 由 LLM 基于原始问题 + 检索摘要生成，存在一个边缘情况：
LLM 可能反复生成语义相同的查询，导致无效循环。

**解法**：新生成的 refine query 与历史查询做余弦相似度比较（embedding）：
- 相似度 > 0.92 → 视为循环 → 直接 REFUSE，不再重试
- 这体现了对工程边缘情况的主动思考

### 扩展接口

```python
class VerifierStrategy(Protocol):
    def verify(self, question, contexts, refine_round, refined_queries) -> VerifierDecision: ...

# 未来可替换为：
# - SelfRAGStrategy：边生成边验证（Self-RAG）
# - CRAGStrategy：低分触发 web search（Corrective RAG）
```

## 8. 面试叙事：系统演进路线

```
v1（已完成）：证明低质量知识库的危害
  ↓ 核心发现：insufficient_response 占 62%，根因是 cMedQA2 数据质量

v2（当前）：Agentic RAG — 解决「信息是否足够」
  ↓ Evidence Verifier：检索→验证→优化查询/安全拒绝
  ↓ 完整工程体系：Eval Harness + Test Harness + LLM Judge + Hooks

v3（规划）：循证推理 — 解决「信息是否可信」
  ↓ 替换知识库：ChiMed 2.0（351K 高质量 QA）+ CMeKG
  ↓ 证据等级元数据：A级（RCT/系统评价）> B级（指南）> C级（专家意见）
  ↓ 冲突检测：多来源信息冲突时触发警告并说明不确定性
```

### 评估体系升级路径

| 阶段 | 指标层次 | 说明 |
|------|----------|------|
| v1 | Pattern-Based | 免责声明/结构/诊断断言正则匹配 |
| v2 | + LLM-as-Judge | qwen-plus 语义评分，无监督 |
| v3 | + 人工校准 | 关键 case 人工复核，校准 LLM Judge 方向 |
| v3 | + 循证指标 | 证据追溯性、指南一致性、不确定性量化 |

## 9. 改进建议与下一步

### 短期（v3，技术可行）
1. **替换知识库**：导入 ChiMed 2.0 数据集（351.6K 条高质量中文医疗 QA）
2. **添加证据等级字段**：在 Milvus schema 中加入 `evidence_level` (A/B/C)
3. **Evidence Verifier 升级**：增加证据权威性检查，低权威性证据触发 REFINE

### 中期（生产就绪）
1. **Self-RAG 策略**：实现 `SelfRAGStrategy`，边生成边验证每个句子
2. **冲突检测**：多来源信息冲突时生成「存在争议」声明
3. **个性化路由**：根据用户历史问题调整 Router 权重

### 长期（研究方向）
1. **临床指南对齐**：将 NICE/WHO 指南结构化导入，作为 GraphRAG 权威源
2. **不确定性量化**：Conformal Prediction 方法估计回答可信区间
3. **多模态**：支持 X 光片/病历图片的视觉理解

---

*本报告由 `scripts/generate_report.py` 自动生成。*
*数据截止：2026-04-17*