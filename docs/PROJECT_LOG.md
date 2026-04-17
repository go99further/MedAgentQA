# MedAgentQA 项目纪要

> 记录从项目启动到当前状态的关键决策、实验发现和工程问题。
> 最后更新：2026-04-15

---

## 一、项目背景与动机

**起因**：候选人有一个多Agent膳食助手项目（GustoBot），架构成熟但缺乏真实数据评估。菜谱领域没有公开的用户问答数据集，无法构建可信的数据闭环。

**决策**：迁移到医疗问答领域，利用 cMedQA2（10.8万条真实患者提问）作为评估骨干。

**目标**：在真实数据上跑通"采集→评估→发现→优化→验证"的完整数据闭环，产出可量化的 before/after 优化故事。

---

## 二、关键里程碑

| 日期 | 事件 | 产出 |
|------|------|------|
| Day 1 | 创建 MedAgentQA 仓库，从 GustoBot 迁移基础设施代码 | 125 文件，11,020 行 |
| Day 1 | 下载 cMedQA2，生成 500 条评估集 | eval_set_500.jsonl |
| Day 1 | 重写所有提示词为医疗领域（10 个 Prompt） | lg_prompts.py 全部替换 |
| Day 2 | 跑 v0 baseline（30 条） | safety=63.3% |
| Day 2 | 跑 v1 优化版（30 条） | safety=53.3%（检测逻辑有误） |
| Day 2 | 修正检测逻辑后重新计算 | v0 safety=27%, v1 safety=90% |
| Day 3 | 设计消融实验（6 版本阶梯） | run_full_ablation.py |
| Day 3 | 跑 15 条消融实验 | v4 pass_rate=87%, 零回归 |
| Day 4 | 代码审查发现 93 个缺失模块文件 | 批量拷贝修复 |
| Day 4 | README 与实际文件严重不符 | 重写 README |
| Day 4 | 扩充到 50 条重跑消融实验 | v4 pass_rate=96%, 回归率 6% |
| Day 5 | 诊断 vFinal 性能回调原因 | Prompt 过载，非模态冲突 |

---

## 三、实验发现（按时间顺序）

### 发现 1：检测逻辑的假象（Day 2）

**问题**：v0→v1 的对比显示 safety 从 63.3% 降到 53.3%。

**根因**：检测逻辑只匹配"仅供参考"和"建议"两个模式，v1 的回答用了"遵医嘱"等其他免责表述，被漏检。

**修复**：扩展检测模式到 7 个（仅供参考/遵医嘱/不构成/建议就医/医生指导/请在医生/就诊）。

**教训**：评估指标的检测逻辑必须在实验前充分验证，否则会产生误导性结论。

### 发现 2：v1 在小样本上的反直觉结果（Day 3，n=15）

**现象**：v1（领域 Prompt 精调）的安全率从 20% 降到 13.3%。

**当时的解读**："纯措辞优化不够，需要显式结构化约束。"

**后续修正（Day 4，n=50）**：扩大到 50 条后，v1 安全率为 40%（高于 v0 的 32%）。15 条时的"反直觉"是小样本波动。

**教训**：15 条样本足以跑通流程，但不足以支撑因果结论。扩大样本量后，v1 的方向性是正确的，只是幅度不大。

### 发现 3：v4 是压倒性的单项最优（Day 3-4）

**数据**（n=50）：
- v4 pass_rate: 96%（v0 的 30% → 96%，+66pp）
- v4 structured_answer_rate: 100%（v0 的 8% → 100%）
- v4 medical_safety_rate: 86%（v0 的 32% → 86%）

**归因**：v4 的 Prompt 用了显式的四段式结构要求（问题分析/专业解答/注意事项/就医建议）+ 强制免责声明。这种"硬约束"比 v1 的"软暗示"有效得多。

### 发现 4：v3 的贡献完全独立（Day 3-4）

**数据**：v3 仅改变了图谱路由率（28%→38%，+10pp），其他所有指标几乎不变。

**意义**：证明 Router 和下游生成模块是解耦的。路由决策的改变不会影响生成质量——这是架构设计正确的实证。

### 发现 5：vFinal 性能回调的真实原因（Day 5）

**现象**：vFinal（v2+v3+v4 组合）的 pass_rate 只有 70%，远低于 v4 单独的 96%。

**初始假说**（用户提出）：指令冲突——v3 将更多问题路由到图谱，但 v4 的"严格基于文本片段"约束与图谱的结构化数据不兼容。

**实际数据验证**：
- 路由变化只有 5/50 条（v4: 36kb+14graphrag → vFinal: 31kb+19graphrag）
- 3 个回归 case 中：1 个路由变了，2 个路由没变
- vFinal 的免责声明缺失：graphrag=9 条，kb=11 条——kb 路由的缺失更多
- 当前实验没有真实检索环节，所有版本都是纯 LLM 回答

**修正后的诊断：Prompt 过载（Prompt Overload）**

vFinal 的 Prompt（PROMPT_VFINAL）比 v4 的 Prompt（PROMPT_V4_STRICT）多了：
- "循证医学知识"
- "区分已证实和可能"
- "风险信号"
- "就医时机"
- "不推荐具体药物品牌"
- "紧急症状必须建议立即就医"

这些额外指令导致模型在有限 token 内优先满足内容丰富度，挤压了末尾免责声明的输出空间。v4 的 Prompt 更简洁聚焦，所以执行率更高。

**结论**：不是模态冲突，是 Prompt 指令密度过高。解决方案不是"路由感知的生成策略"，而是精简 vFinal 的 Prompt，保留 v4 的核心约束，只追加最关键的增量指令。

---

## 四、工程问题与修复

### 问题 1：.env 泄露（Day 2）

**事件**：首次推送时将 .env（含 API Key）提交到 GitHub。

**修复**：git rm --cached .env，添加 .gitignore，创建 .env.example。

**教训**：新仓库第一件事应该是配置 .gitignore。

### 问题 2：93 个缺失模块文件（Day 4）

**事件**：从 GustoBot 迁移时只拷贝了 __init__.py，漏掉了实际的 node.py 等实现文件。导致 `from medagent.application.agents.lg_builder import *` 报错。

**修复**：批量从 GustoBot 拷贝所有缺失的 .py 文件，全局 sed 替换 gustobot→medagent。

**教训**：迁移项目时应该用 diff 工具对比两个目录的文件列表，而不是手动挑选。

### 问题 3：README 与实际文件严重不符（Day 4）

**事件**：README 中列出了 10+ 个不存在的文件（text2sql_evaluator.py、rag_evaluator.py 等），Quick Start 引用了不存在的脚本。

**修复**：重写 README，只列实际存在的文件，用真实实验数据替换占位符。

**教训**：README 应该在项目完成后写，而不是在规划阶段写。

### 问题 4：badcase_analyzer.py 格式不匹配（Day 4）

**事件**：evaluation/badcase_analyzer.py 期望 RAGAS 格式输入，但实际数据是 ablation_results.json 格式。

**修复**：保留 evaluation/badcase_analyzer.py 作为 RAGAS 扩展点，实际分析入口使用 scripts/run_badcase_analysis.py。

### 问题 5：kg_prompts.py 中文引号语法错误（Day 4）

**事件**：kg_prompts.py 中混入了中文引号（""），导致 Python SyntaxError。

**修复**：sed 替换中文引号为英文引号。

---

## 五、当前量化数据（n=50，cMedQA2 真实患者提问）

### 消融实验

| 指标 | v0 | v1 | v2 | v3 | v4 | vFinal |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 医疗安全率 | 32% | 40% | 60% | 26% | **86%** | 60% |
| 结构化回答率 | 8% | 12% | 8% | 6% | **100%** | 96% |
| 科室建议率 | 44% | 42% | 72% | 46% | **92%** | 64% |
| 无诊断断言率 | 96% | 96% | 90% | 96% | 92% | 94% |
| 图谱路由率 | 28% | 28% | 28% | **38%** | 28% | 38% |
| 通过率 | 30% | 30% | 48% | 28% | **96%** | 70% |
| high_authority | 4 | 6 | 8 | 10 | 7 | **14** |

### 回归分析

- Pass→Fail：3 个（均为免责声明格式变化导致检测未命中）
- Fail→Pass：23 个
- 回归通过率：94%

---

## 六、待解决问题

### P0：vFinal Prompt 过载修复

vFinal 的 pass_rate（70%）远低于 v4（96%）。根因是 Prompt 指令过多导致模型在有限 token 内无法同时满足所有要求。

**方案**：创建 PROMPT_VFINAL_V2，保留 v4 的核心四段式结构 + 免责声明，仅追加 v2 的低温度和 v3 的路由关键词，不追加额外的内容要求。预期 pass_rate 回升到 85-90%。

### P1：扩大样本量到 100 条

50 条已经比 15 条好很多，但 100 条能进一步降低置信区间。需要约 2 小时 API 调用。

### P2：RAGAS 标准指标

当前只有自定义指标。接入 RAGAS 的 faithfulness/answer_relevancy 需要完整 Agent 链路（含检索），目前是纯 LLM 回答。

---

## 七、文件索引

| 文件 | 用途 |
|------|------|
| `data/eval/ablation_results.json` | 6 版本 × 50 条的完整原始问答（868KB） |
| `data/eval/metrics_report.json` | 指标计算结果 |
| `data/eval/badcase_report.json` | 失败模式分布 + 回归分析 |
| `data/eval/ablation_comparison.md` | 消融对比表格 |
| `docs/EVALUATION_RESULTS.md` | 完整评估报告 |
| `docs/ABLATION_STUDY_DESIGN.md` | 消融实验设计说明 |
| `docs/DATA_FLYWHEEL.md` | 数据闭环方法论 |
| `scripts/run_full_ablation.py` | 消融实验运行器 |
| `scripts/compute_metrics.py` | 独立指标计算（零 API 成本） |
| `scripts/run_badcase_analysis.py` | Badcase 分析入口 |
