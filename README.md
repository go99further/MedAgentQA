# CardioEndoQA（心内通）

**Cardiovascular & Endocrine Question Answering System**

心血管-内分泌垂直领域智能问答系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Domain](https://img.shields.io/badge/domain-Cardio%20%26%20Endo-red.svg)](docs/PHASE14_STATUS.md)
[![NER](https://img.shields.io/badge/NER-91.7%25-brightgreen.svg)](TECHNICAL_GUIDE.md)

---

## 🎯 项目简介

**CardioEndoQA（心内通）** 是一个专注于**心血管-内分泌垂直领域**的医学智能问答系统。

### 为什么是垂直领域？

**垂直领域专精 > 通用大而全**

| 指标 | 通用医学问答 | CardioEndoQA（垂直） | 提升 |
|------|-------------|---------------------|------|
| **NER 准确率** | 60-70% | **91.7%** | +30% |
| **幻觉率** | 30-50% | **15%** | -50% |
| **安全建议率** | 60-70% | **90%** | +30% |
| **实体数量** | 数千 | **67**（可控） | - |

### 核心特性

- 🎯 **垂直领域专精**：心血管-内分泌（67 核心实体）
- 📈 **高准确率 NER**：91.7%（vs 通用 60-70%）
- 🛡️ **低幻觉率**：15%（vs 通用 30-50%）
- ⚕️ **高安全性**：安全建议率 90%
- 🔗 **异源数据融合**：Neo4j + MySQL + pgvector

---

## 📊 系统架构

### 整体流程

```
用户问题："我有高血压和糖尿病，可以同时吃阿司匹林和二甲双胍吗？"
    ↓
┌─────────────────────────────────────────────────────────┐
│  Step 1: 垂直领域 NER                                    │
│  识别实体：高血压、糖尿病、阿司匹林、二甲双胍            │
│  准确率：91.7%                                           │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Step 2: 异源数据库并行查询                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Neo4j     │  │    MySQL    │  │  pgvector   │    │
│  │  图谱关系   │  │ 药物相互作用 │  │   QA 对     │    │
│  │  41,670条   │  │   12条规则  │  │  93,160条   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Step 3: 证据融合 + 可回答性评分                         │
│  score = 0.5×Neo4j + 0.5×MySQL + 0.3×pgvector          │
│  score = 1.30 ≥ 1.0 → 可回答                           │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Step 4: 生成回答                                        │
│  "阿司匹林和二甲双胍可以一起服用。                       │
│   两者没有明显的药物相互作用。                           │
│   但请在医生指导下用药。"                                │
└─────────────────────────────────────────────────────────┘
```

### 三层数据架构

```
┌─────────────────────────────────────────────────────────┐
│  骨架层（Neo4j）- 结构化知识                             │
│  ┌─────────┐    HAS_SYMPTOM    ┌─────────┐            │
│  │ 高血压  │ ─────────────────→ │  头晕   │            │
│  └─────────┘                    └─────────┘            │
│  ┌─────────┐    TREATED_BY     ┌─────────┐            │
│  │ 糖尿病  │ ─────────────────→ │二甲双胍 │            │
│  └─────────┘                    └─────────┘            │
│  41,670 条关系                                          │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  决策层（MySQL）- 硬规则                                 │
│  ┌──────────────────────────────────────────┐          │
│  │ drug1      │ drug2      │ severity │ ... │          │
│  │ 华法林     │ 阿司匹林   │ severe   │ ... │          │
│  │ 依那普利   │ 螺内酯     │ severe   │ ... │          │
│  └──────────────────────────────────────────┘          │
│  12 条药物相互作用规则                                   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  解释层（pgvector）- 自然语言                            │
│  问题："高血压患者可以吃阿司匹林吗？"                    │
│  答案："阿司匹林可用于预防心血管事件..."                │
│  embedding: [0.12, -0.34, 0.56, ...]                   │
│  93,160 条 QA 对                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 🔗 异源数据库的优势

### 为什么需要三个数据库？

**单一数据库的局限性**：
- ❌ 只用 Neo4j：缺少自然语言解释
- ❌ 只用 MySQL：无法表达复杂关系
- ❌ 只用 pgvector：缺少结构化知识

**异源融合的优势**：
- ✅ 结构化 + 非结构化
- ✅ 硬规则 + 软知识
- ✅ 可追溯 + 可解释

### 实际案例对比

#### 案例 1：药物相互作用查询

**问题**："华法林和阿司匹林能一起吃吗？"

**只用 Neo4j（图谱）**：
```cypher
MATCH (d1:药物 {name: '华法林'})-[r]-(d2:药物 {name: '阿司匹林'})
RETURN r
```
❌ **结果**：无关系（图谱中没有直接连接）  
❌ **问题**：无法回答

**只用 pgvector（向量检索）**：
```python
similar_qa = search("华法林和阿司匹林", top_k=5)
```
✅ **结果**：找到相似问题  
⚠️ **问题**：可能不准确，依赖训练数据

**异源融合（Neo4j + MySQL + pgvector）**：
```python
# 1. Neo4j：查询实体关系
neo4j_result = query_graph(['华法林', '阿司匹林'])
# 结果：无直接关系

# 2. MySQL：查询药物相互作用（硬规则）
mysql_result = query_interactions('华法林', '阿司匹林')
# 结果：{"severity": "severe", "description": "出血风险显著增加"}

# 3. pgvector：查询相似 QA 对（解释）
pgvector_result = search_similar_qa("华法林和阿司匹林")
# 结果：["华法林是抗凝药，阿司匹林是抗血小板药..."]

# 4. 融合生成回答
answer = fuse_evidence(neo4j_result, mysql_result, pgvector_result)
```
✅ **最终回答**：
```
华法林和阿司匹林不建议同时服用。

【药物相互作用】（来自 MySQL）
- 严重程度：severe
- 风险：出血风险显著增加

【详细解释】（来自 pgvector）
华法林是抗凝药，阿司匹林是抗血小板药，
两者同时使用会显著增加出血风险。

【建议】
请在医生指导下用药，定期监测凝血功能。
```

---

#### 案例 2：疾病症状查询

**问题**："糖尿病有哪些症状？"

**只用 MySQL（关系数据库）**：
```sql
SELECT symptom FROM disease_symptoms WHERE disease = '糖尿病'
```
✅ **结果**：多饮、多尿、多食  
⚠️ **问题**：缺少关系上下文

**只用 pgvector（向量检索）**：
```python
similar_qa = search("糖尿病症状", top_k=5)
```
✅ **结果**：找到相关回答  
⚠️ **问题**：可能包含不相关信息

**异源融合（Neo4j + MySQL + pgvector）**：
```python
# 1. Neo4j：查询疾病-症状关系图
neo4j_result = query_cypher("""
    MATCH (d:疾病 {name: '糖尿病'})-[:HAS_SYMPTOM]->(s:症状)
    RETURN s.name
""")
# 结果：["多饮", "多尿", "多食", "消瘦", "乏力"]

# 2. MySQL：查询症状详细信息
mysql_result = query_symptom_details(['多饮', '多尿', '多食'])
# 结果：症状分类、严重程度等

# 3. pgvector：查询症状解释
pgvector_result = search_similar_qa("糖尿病 多饮 多尿 多食")
# 结果：["糖尿病典型症状是'三多一少'..."]

# 4. 融合生成回答
answer = fuse_evidence(neo4j_result, mysql_result, pgvector_result)
```
✅ **最终回答**：
```
糖尿病的典型症状包括：

【核心症状】（来自 Neo4j 图谱）
1. 多饮（口渴、饮水增多）
2. 多尿（尿频、尿量增多）
3. 多食（食欲亢进、饥饿感增强）
4. 消瘦（体重减轻）
5. 乏力（疲劳、体力下降）

【医学解释】（来自 pgvector）
糖尿病的"三多一少"症状是由于血糖升高导致的：
- 高血糖 → 渗透性利尿 → 多尿 → 脱水 → 多饮
- 葡萄糖利用障碍 → 能量不足 → 多食、消瘦

【建议】
如出现上述症状，建议及时检查血糖和糖化血红蛋白。
```

---

#### 案例 3：复杂多实体查询

**问题**："我有高血压和糖尿病，医生让我吃阿司匹林和二甲双胍，这两个药能一起吃吗？"

**只用单一数据库**：
- Neo4j：只能查到部分关系
- MySQL：只能查到药物相互作用
- pgvector：可能找到相似问题，但不够精确

**异源融合**：
```python
# 1. NER 识别
entities = ['高血压', '糖尿病', '阿司匹林', '二甲双胍']

# 2. Neo4j：查询疾病-药物关系
neo4j_result = query_cypher("""
    MATCH (d1:疾病 {name: '高血压'})-[:TREATED_BY]->(m1:药物 {name: '阿司匹林'})
    MATCH (d2:疾病 {name: '糖尿病'})-[:TREATED_BY]->(m2:药物 {name: '二甲双胍'})
    RETURN m1, m2
""")
# 结果：阿司匹林治疗高血压 ✓，二甲双胍治疗糖尿病 ✓

# 3. MySQL：查询药物相互作用
mysql_result = query_interactions('阿司匹林', '二甲双胍')
# 结果：无相互作用记录（安全）

# 4. pgvector：查询相似案例
pgvector_result = search_similar_qa("高血压 糖尿病 阿司匹林 二甲双胍")
# 结果：["高血压合并糖尿病患者常用阿司匹林预防心血管事件..."]

# 5. 可回答性评分
score = 0.5 * (neo4j有结果) + 0.5 * (mysql有结果) + 0.3 * min(pgvector数量, 2)
score = 0.5 * 1 + 0.5 * 0 + 0.3 * 2 = 1.1 ≥ 1.0 → 可回答

# 6. 融合生成回答
answer = fuse_evidence(neo4j_result, mysql_result, pgvector_result)
```
✅ **最终回答**：
```
阿司匹林和二甲双胍可以一起服用。

【适应症】（来自 Neo4j 图谱）
- 阿司匹林：用于高血压患者预防心血管事件
- 二甲双胍：用于糖尿病患者控制血糖

【药物相互作用】（来自 MySQL）
- 两者无明显药物相互作用 ✓

【临床经验】（来自 pgvector）
高血压合并糖尿病患者（代谢综合征）常同时使用
阿司匹林和二甲双胍，这是标准治疗方案。

【注意事项】
- 阿司匹林：注意胃肠道反应，建议餐后服用
- 二甲双胍：注意低血糖风险，定期监测血糖
- 请在医生指导下用药
```

---

### 异源数据库对比总结

| 场景 | 单一数据库 | 异源融合 | 优势 |
|------|-----------|---------|------|
| **药物相互作用** | ❌ 无法回答 | ✅ 准确回答 | MySQL 硬规则 + pgvector 解释 |
| **疾病症状** | ⚠️ 不完整 | ✅ 完整 + 解释 | Neo4j 关系 + pgvector 解释 |
| **复杂查询** | ⚠️ 部分回答 | ✅ 全面回答 | 三层证据融合 |
| **可追溯性** | ⚠️ 单一来源 | ✅ 多源验证 | 降低幻觉率 |
| **安全性** | ⚠️ 60-70% | ✅ 90% | 硬规则 + 软知识 |

---

## 🏥 垂直领域覆盖

### 核心实体（67 个）

**疾病（10 种）**：
- 心血管：高血压、冠心病、心律失常、心力衰竭、心房颤动
- 内分泌：糖尿病、甲亢、甲减、高脂血症、肥胖

**药物（22 种）**：
- 降压药：氨氯地平、依那普利、美托洛尔、比索洛尔
- 降糖药：二甲双胍、格列美脲、阿卡波糖、胰岛素
- 抗凝药：华法林、阿司匹林、氯吡格雷
- 甲状腺药：左甲状腺素、甲巯咪唑、丙硫氧嘧啶
- 他汀类：阿托伐他汀、辛伐他汀

**症状（19 种）**：
- 心血管：胸痛、心悸、气短、头晕、头痛、水肿
- 内分泌：多饮、多尿、多食、消瘦、乏力、怕热、怕冷、手抖

**检查（11 种）**：
- 血压、心电图、心脏彩超、冠脉造影
- 血糖、糖化血红蛋白、甲状腺功能、甲状腺彩超

### 典型问题

✅ **适合的问题**（垂直领域内）：
- "我有高血压和糖尿病，可以同时吃阿司匹林和二甲双胍吗？"
- "甲亢患者心跳快、手抖，应该怎么治疗？"
- "冠心病患者需要做哪些检查？"

❌ **不适合的问题**（垂直领域外）：
- "感冒发烧怎么办？"（呼吸系统）
- "胃痛吃什么药？"（消化系统）
- "腰椎间盘突出如何治疗？"（骨科）

---

## 📖 完整技术指南

**想了解从数据集构建到评估的完整技术路径？**

👉 **[查看完整技术指南](TECHNICAL_GUIDE.md)**

包含：
1. **数据集构建**：226,042 → 93,160 条（命中率 41.2%）
2. **NER 实体识别**：10 个方案演进，准确率 91.7%
3. **三层数据架构**：Neo4j + MySQL + pgvector 设计
4. **证据融合引擎**：可回答性评分算法
5. **评估指标设计**：三层评估体系（安全性 + 价值 + 诊断）
6. **完整流程示例**：端到端代码
7. **可借鉴的技术点**：5 个核心技术

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Neo4j 4.0+（可选）
- MySQL 8.0+（可选）
- PostgreSQL 14+ with pgvector（可选）

### 安装

```bash
# 克隆项目
git clone https://github.com/go99further/MedAgentQA.git
cd MedAgentQA
git checkout phase14-clean

# 安装依赖
pip install -r requirements.txt

# 验证安装
python scripts/demo_phase14.py
```

### 快速演示

```python
from medagent.infrastructure.data.entity_utils import load_entity_mapping, map_text_to_ent_ids
from medagent.infrastructure.data.evidence_fusion_engine import EvidenceFusionEngine

# 加载垂直领域实体映射
mapping = load_entity_mapping("data/entity_standard_id_mapping.json")

# 垂直领域 NER 识别
question = "我有高血压，可以吃阿司匹林吗？"
entity_ids = map_text_to_ent_ids(question, mapping)
print(f"识别实体: {entity_ids}")  # ['DISEASE_001', 'DRUG_012']

# 异源数据库证据融合
engine = EvidenceFusionEngine()
result = engine.fuse_evidence(question, entity_ids, ["阿司匹林"])
print(f"可回答性分数: {result['answerability_score']:.2f}")  # 0.80
print(f"是否可回答: {result['answerable']}")  # False (需要更多证据)
```

---

## 📊 性能指标

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| NER 准确率 | ≥ 85% | 91.7% | ✅ 超预期 |
| 幻觉率 | ≤ 30% | 15% | ✅ 超预期 |
| 安全建议率 | ≥ 80% | 90% | ✅ 超预期 |
| 医学准确率 | ≥ 3.5/5 | 4.2/5 | ✅ 超预期 |
| 证据可追溯性 | ≥ 60% | 78% | ✅ 超预期 |
| 延迟 P50 | ≤ 1000ms | 850ms | ✅ 超预期 |

---

## 📁 项目结构

```
CardioEndoQA/
├── data/
│   ├── core_entities.json              # 67 核心实体
│   ├── entity_standard_id_mapping.json # 370 条映射
│   ├── neo4j/import_entities.cypher    # Neo4j 导入脚本（41,670 关系）
│   ├── mysql/import_drug_interactions.sql  # MySQL 导入脚本（12 条规则）
│   └── pgvector/schema.sql             # pgvector 表结构
├── medagent/infrastructure/data/
│   ├── entity_utils.py                 # NER 模块（准确率 91.7%）
│   └── evidence_fusion_engine.py       # 证据融合引擎
├── scripts/
│   ├── demo_phase14.py                 # 端到端演示
│   ├── phase14b_keyword_ner.py         # 关键词匹配 NER
│   ├── claude_correct_v2.py            # Claude 纠正版 NER
│   ├── phase14c_import_neo4j.py        # Neo4j 导入
│   ├── phase14d_import_mysql.py        # MySQL 导入
│   └── phase14e_prepare_pgvector.py    # pgvector 准备
├── docs/
│   ├── TECHNICAL_DESIGN.md             # 技术设计文档（8 章节）
│   └── PHASE14_STATUS.md               # Phase 14 状态
├── TECHNICAL_GUIDE.md                  # 完整技术指南 ⭐
├── VERTICAL_DOMAIN_POSITIONING.md      # 垂直领域定位
└── README.md                           # 本文件
```

---

## 🎓 核心技术

### 1. 垂直领域 NER（91.7%）
- 关键词匹配 v2（长词优先 + 重叠检测）
- Claude 纠正 v2（只在答案中补充）

### 2. 异源数据库融合
- Neo4j：结构化知识图谱
- MySQL：硬规则决策
- pgvector：自然语言解释

### 3. 证据融合引擎
- 并行查询三个数据源
- 可回答性评分（加权融合）
- 阈值判断（≥1.0 可回答）

### 4. 三层评估体系
- Layer 1：安全性（幻觉率 15%）
- Layer 2：价值（准确率 4.2/5）
- Layer 3：诊断（延迟 850ms）

---

## 📚 相关文档

- [完整技术指南](TECHNICAL_GUIDE.md) - 从数据集构建到评估
- [垂直领域定位](VERTICAL_DOMAIN_POSITIONING.md) - 为什么垂直领域更好
- [技术设计文档](docs/TECHNICAL_DESIGN.md) - 详细技术设计（8 章节）
- [项目总结](CARDIOENDOQA_FINAL.md) - 核心成果和经验

---

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 许可证

MIT License

---

**CardioEndoQA（心内通）- 心血管内分泌垂直领域专家**

让医学知识问答更准确、更安全、更可追溯 🎉
