# 数据飞轮方法论

## 1. 什么是数据飞轮？为什么它至关重要？

数据飞轮（Data Flywheel）是一种**持续自我强化的数据优化机制**。在医疗问答系统中，模型的每一次推理都会产生新的数据——包括成功案例和失败案例。通过系统化地收集、分析和利用这些数据，我们可以不断改善系统的准确性和鲁棒性。

### 传统方法的问题

| 维度 | 传统评测 | 数据飞轮 |
|------|---------|---------|
| 数据来源 | 静态测试集 | 动态收集 + 静态测试集 |
| 反馈周期 | 手动分析，周期长 | 自动化分析，持续迭代 |
| 优化方向 | 靠经验判断 | 数据驱动，有据可依 |
| 回归检测 | 通常缺失 | 内置负面翻转检测 |
| 可持续性 | 一次性投入 | 持续积累，越转越快 |

### 核心理念

> 每一次错误都是改进的机会，每一次改进都必须经过验证。

飞轮的本质是一个**正反馈循环**：更多的数据带来更好的分析，更好的分析带来更精准的优化，更精准的优化带来更高的准确率，更高的准确率吸引更多的使用，更多的使用产生更多的数据。

---

## 2. 五步循环详解

### Step 1: Collect（收集）

**目标**：从多个渠道系统性地收集评测数据。

**数据来源**：
- **查询日志**：用户在生产环境中的真实查询记录
- **人工标注**：领域专家构造的测试用例（如 `text2sql_test_set.jsonl`）
- **对抗样本**：通过变异已有问题生成的边界测试用例
- **用户反馈**：用户标记的错误回答

**收集规范**：
```json
{
  "question": "哪个科室的疾病最多？",
  "gold_sql": "SELECT d.name, COUNT(*) AS cnt FROM departments d JOIN ... GROUP BY d.name ORDER BY cnt DESC LIMIT 1",
  "difficulty": "medium",
  "sql_type": "JOIN",
  "source": "expert_annotation",
  "created_at": "2025-01-15"
}
```

**关键原则**：
- 保证覆盖所有 SQL 类型（COUNT、GROUP_BY、JOIN、ORDER_BY、HAVING、SUBQUERY、AGGREGATE）
- 保证覆盖所有难度等级（easy / medium / hard）
- 定期从生产日志中挖掘新的查询模式

---

### Step 2: Evaluate（评测）

**目标**：用标准化指标衡量系统在各维度上的表现。

**核心指标**：

| 指标 | 计算方式 | 适用场景 |
|------|---------|---------|
| EX（Execution Accuracy） | 执行生成的 SQL 与 gold SQL，比较结果集是否一致 | Text2SQL |
| EM（Exact Match） | 生成的 SQL 与 gold SQL 的字符串精确匹配率 | Text2SQL |
| Recall@K | 在检索结果的前 K 个中，相关文档的召回率 | RAG |
| MRR（Mean Reciprocal Rank） | 第一个相关文档排名的倒数的均值 | RAG |
| F1 | 精确率和召回率的调和平均值 | KG 推理 |

**评测流程**：
```
输入测试集 → 模型推理 → 结果收集 → 指标计算 → 报告生成
                                         ↓
                                   按维度切片分析
                                   (难度 / SQL类型 / 科室)
```

**切片分析的价值**：整体 EX 为 75% 并不意味着所有类型都是 75%。切片分析可能揭示：
- Easy: 95%, Medium: 72%, Hard: 45%
- COUNT: 98%, SUBQUERY: 35%

这种差异化的洞察是优化的基础。

---

### Step 3: Discover（发现）

**目标**：从评测结果中识别系统性的失败模式。

**Badcase 分析方法论**：

对所有失败用例进行分类，归入四大失败模式（详见第 4 节）。通过聚类分析发现共性问题：

```
失败用例集合
    ├── 按 sql_type 分组 → 发现 SUBQUERY 类型错误率最高
    ├── 按 difficulty 分组 → 发现 hard 难度准确率骤降
    ├── 按错误模式分组 → 发现 70% 的错误源于 JOIN 条件错误
    └── 按时间分组 → 发现某次优化后新增了回归错误
```

**产出物**：
- 失败模式分布报告
- 高频错误 SQL 模式列表
- 优先修复建议（按影响面排序）

---

### Step 4: Optimize（优化）

**目标**：根据 Discover 阶段的发现，针对性地改进系统。

**优化手段**：

| 优化类型 | 适用场景 | 示例 |
|---------|---------|------|
| Prompt 优化 | 模型理解偏差 | 增加 few-shot 示例覆盖 SUBQUERY 场景 |
| Schema 增强 | 模型选错表或列 | 在 schema 描述中增加字段中文注释 |
| 数据增强 | 训练数据不足 | 对现有问题进行同义改写扩充 |
| 后处理规则 | 模型输出格式错误 | 添加 SQL 语法校验和自动修复 |
| 检索优化 | RAG 召回率低 | 调整 chunk 大小和 embedding 模型 |

**优化原则**：
1. **单变量控制**：每次只改变一个因素，确保效果可归因
2. **可回滚**：所有优化都通过版本管理，可随时回退
3. **有假设**：每次优化都基于明确的假设，优化后验证假设是否成立

---

### Step 5: Verify（验证）

**目标**：确保优化有效且未引入回归。

**验证三板斧**：

1. **全量回归测试**：在完整测试集上重新评测，确认整体指标提升
2. **负面翻转检测**：检查优化前正确但优化后错误的用例（详见第 5 节）
3. **新增用例测试**：用 Discover 阶段发现的新 badcase 构造测试用例，确认这些用例被修复

**验证通过标准**：
- 目标指标有显著提升
- 负面翻转率 < 2%
- 无新增的系统性失败模式

验证通过后，优化合入主分支；验证不通过则回退并重新分析。

---

## 3. 消融实验设计（Version Ladder）

消融实验通过逐步叠加优化手段来量化每个组件的贡献。

### 版本阶梯设计

| 版本 | 配置 | 目的 |
|------|------|------|
| V0 - Baseline | 原始 prompt + 原始 schema | 建立基线 |
| V1 - Schema Enhanced | 原始 prompt + 增强 schema（中文注释） | 量化 schema 增强的贡献 |
| V2 - Few-shot | few-shot prompt + 增强 schema | 量化 few-shot 示例的贡献 |
| V3 - Full Pipeline | few-shot prompt + 增强 schema + 后处理 | 量化后处理的贡献 |
| V4 - Flywheel Round 1 | V3 + 第一轮飞轮优化数据 | 量化数据飞轮的贡献 |

### 实验矩阵

```
              Easy    Medium    Hard    Overall
V0 Baseline    --       --       --       --
V1 +Schema     --       --       --       --
V2 +Few-shot   --       --       --       --
V3 +PostProc   --       --       --       --
V4 +Flywheel   --       --       --       --
```

### 分析维度

- **按难度**：观察每个优化对不同难度级别的影响是否一致
- **按 SQL 类型**：识别哪些优化对哪类 SQL 最有效
- **按成本**：记录每个版本的 token 消耗和延迟，评估性价比

---

## 4. Badcase 分析方法论（四大失败模式）

### 失败模式 1：SQL 生成错误（Generation Error）

**定义**：模型生成的 SQL 语法正确但语义错误。

**常见子类型**：
- **JOIN 条件错误**：使用了错误的关联字段
- **聚合遗漏**：缺少 GROUP BY 或使用了错误的聚合函数
- **过滤条件错误**：WHERE 子句逻辑不正确
- **排序方向错误**：ASC/DESC 搞反

**示例**：
```
问题：哪个科室的疾病最多？
预期：... ORDER BY cnt DESC LIMIT 1
生成：... ORDER BY cnt ASC LIMIT 1  ← 排序方向错误
```

---

### 失败模式 2：Schema 映射错误（Schema Mapping Error）

**定义**：模型选择了错误的表或列。

**常见子类型**：
- **表名混淆**：使用了不存在的表名
- **列名混淆**：将 `disease_id` 错写为 `diseases_id`
- **关系误判**：使用了错误的关联路径（如跳过中间表）

**示例**：
```
问题：每个科室有多少种疾病？
预期：... FROM departments d JOIN disease_department_mapping ddm ON d.id = ddm.department_id
生成：... FROM departments d JOIN diseases dis ON d.id = dis.department_id  ← 跳过了映射表
```

---

### 失败模式 3：语义理解错误（Semantic Error）

**定义**：模型对自然语言问题的理解与真实意图不符。

**常见子类型**：
- **数量词误读**："两个及以上" 被理解为 "恰好两个"
- **限定词忽略**："没有症状的疾病" 被理解为 "有症状的疾病"
- **隐含条件遗漏**：问题中有隐含的去重要求但未 DISTINCT

**示例**：
```
问题：列出同时属于两个及以上科室的疾病
预期：... HAVING COUNT(DISTINCT ddm.department_id) >= 2
生成：... HAVING COUNT(ddm.department_id) = 2  ← >= 被理解为 =
```

---

### 失败模式 4：执行环境错误（Runtime Error）

**定义**：SQL 语法或语义正确，但在目标数据库上执行失败。

**常见子类型**：
- **方言不兼容**：使用了 MySQL 语法但目标是 PostgreSQL
- **数据类型不匹配**：字符串与数字的隐式转换失败
- **空值处理**：未考虑 NULL 值导致结果不完整

---

### Badcase 分析流程

```
1. 收集所有失败用例
2. 对每个失败用例进行根因分类（四大模式）
3. 统计各模式占比
4. 对占比最高的模式进行深入分析
5. 在该模式内按子类型二次分组
6. 针对高频子类型设计优化方案
7. 将分析结果和新发现的边界用例加入测试集
```

---

## 5. 风险缓解措施

### 5.1 Ground Truth 验证

**问题**：如果测试集的 gold SQL 本身有错误，评测结论不可靠。

**缓解措施**：
- **双人审核**：每条 gold SQL 由至少两名标注者独立验证
- **执行验证**：在真实数据库上执行 gold SQL，确认结果集合理
- **交叉验证**：用不同 SQL 写法实现相同语义，验证结果一致性

```bash
# 执行验证脚本示例
python scripts/validate_gold_sql.py \
  --test-set data/eval/text2sql_test_set.jsonl \
  --db-uri "mysql://user:pass@localhost/medqa"
```

---

### 5.2 数据源质量追踪

**问题**：不同来源的测试数据质量参差不齐。

**缓解措施**：
- **来源标记**：每条数据记录来源（expert_annotation / production_log / augmentation）
- **来源指标**：分来源统计模型准确率，识别低质量数据源
- **定期清洗**：对来源质量低于阈值的数据进行人工复审

```
数据来源质量报告：
┌─────────────────────┬───────┬──────────┬───────────┐
│ 来源                │ 条数  │ 模型EX   │ 标注争议率│
├─────────────────────┼───────┼──────────┼───────────┤
│ expert_annotation   │  50   │  78%     │   2%      │
│ production_log      │ 120   │  65%     │   8%      │
│ augmentation        │  80   │  82%     │   5%      │
└─────────────────────┴───────┴──────────┴───────────┘
```

---

### 5.3 负面翻转检测（Negative Churn Detection）

**问题**：每轮优化可能修复了一些问题但同时破坏了另一些之前正确的用例。

**定义**：
- **正面翻转（Positive Flip）**：之前错 -> 现在对
- **负面翻转（Negative Flip）**：之前对 -> 现在错
- **负面翻转率** = 负面翻转数 / 之前正确的用例总数

**缓解措施**：
- **逐用例对比**：每轮评测都保存逐用例结果，自动对比前后两轮
- **红线机制**：负面翻转率超过 2% 时自动阻断优化合入
- **翻转报告**：自动生成所有翻转用例的详细对比

```python
# 负面翻转检测伪代码
def detect_negative_churn(prev_results, curr_results):
    negative_flips = []
    for case_id in prev_results:
        if prev_results[case_id] == "correct" and curr_results[case_id] == "incorrect":
            negative_flips.append(case_id)

    churn_rate = len(negative_flips) / sum(1 for v in prev_results.values() if v == "correct")

    if churn_rate > 0.02:
        raise RegressionAlert(f"负面翻转率 {churn_rate:.1%} 超过阈值 2%")

    return negative_flips, churn_rate
```

---

## 6. 如何运行评测流水线

### 环境准备

```bash
# 1. 启动依赖服务
docker compose up -d mysql neo4j

# 2. 初始化数据库和导入知识图谱
python scripts/init_db.py
python scripts/import_kg.py

# 3. 验证 gold SQL 的正确性
python scripts/validate_gold_sql.py \
  --test-set data/eval/text2sql_test_set.jsonl \
  --db-uri "mysql://user:pass@localhost/medqa"
```

### 运行评测

```bash
# 运行 Text2SQL 评测
python scripts/run_eval.py \
  --test-set data/eval/text2sql_test_set.jsonl \
  --agent text2sql \
  --output results/text2sql_v1/

# 运行全量评测（Text2SQL + RAG + KG）
python scripts/run_eval.py \
  --test-set data/eval/ \
  --agent all \
  --output results/full_v1/
```

### 生成报告

```bash
# 生成评测报告
python scripts/report.py \
  --input results/text2sql_v1/ \
  --format markdown \
  --output reports/text2sql_v1_report.md

# 负面翻转检测
python scripts/churn_detect.py \
  --prev results/text2sql_v0/ \
  --curr results/text2sql_v1/ \
  --threshold 0.02
```

### 消融实验

```bash
# 运行版本阶梯实验
for version in v0_baseline v1_schema v2_fewshot v3_postproc v4_flywheel; do
  python scripts/run_eval.py \
    --test-set data/eval/text2sql_test_set.jsonl \
    --config configs/${version}.yaml \
    --output results/${version}/
done

# 汇总对比
python scripts/ablation_report.py \
  --versions v0_baseline v1_schema v2_fewshot v3_postproc v4_flywheel \
  --output reports/ablation_report.md
```

### 一键执行完整飞轮周期

```bash
# 完整飞轮：评测 → 发现 → 优化 → 验证
python scripts/flywheel.py \
  --test-set data/eval/text2sql_test_set.jsonl \
  --prev-results results/text2sql_v0/ \
  --output results/text2sql_v1/ \
  --churn-threshold 0.02
```

---

> **注意**：本文档是 MedAgentQA 项目数据飞轮方法论的完整说明。所有流程设计均遵循"数据驱动、可量化、可回滚"的原则，确保系统优化过程科学、可控、可追溯。
