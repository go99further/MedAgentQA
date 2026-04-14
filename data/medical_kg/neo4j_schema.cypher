// ============================================================
// 医学知识图谱 Neo4j Schema - Medical Knowledge Graph
// ============================================================

// ------------------------------------------------------------
// 1. 约束与索引
// ------------------------------------------------------------
CREATE CONSTRAINT disease_name_unique IF NOT EXISTS
FOR (d:Disease) REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT symptom_name_unique IF NOT EXISTS
FOR (s:Symptom) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT drug_name_unique IF NOT EXISTS
FOR (dr:Drug) REQUIRE dr.name IS UNIQUE;

CREATE CONSTRAINT department_name_unique IF NOT EXISTS
FOR (dep:Department) REQUIRE dep.name IS UNIQUE;

CREATE INDEX disease_icd_index IF NOT EXISTS
FOR (d:Disease) ON (d.icd_code);

CREATE INDEX drug_name_index IF NOT EXISTS
FOR (dr:Drug) ON (dr.name);

CREATE INDEX symptom_name_index IF NOT EXISTS
FOR (s:Symptom) ON (s.name);

// ------------------------------------------------------------
// 2. 科室节点 (15个)
// ------------------------------------------------------------
CREATE (:Department {name: '内科'});
CREATE (:Department {name: '外科'});
CREATE (:Department {name: '妇产科'});
CREATE (:Department {name: '儿科'});
CREATE (:Department {name: '皮肤科'});
CREATE (:Department {name: '中医科'});
CREATE (:Department {name: '骨科'});
CREATE (:Department {name: '神经内科'});
CREATE (:Department {name: '心血管内科'});
CREATE (:Department {name: '消化内科'});
CREATE (:Department {name: '呼吸内科'});
CREATE (:Department {name: '泌尿外科'});
CREATE (:Department {name: '眼科'});
CREATE (:Department {name: '耳鼻喉科'});
CREATE (:Department {name: '精神科'});

// ------------------------------------------------------------
// 3. 疾病节点 (30个)
// ------------------------------------------------------------
CREATE (:Disease {name: '高血压', icd_code: 'I10'});
CREATE (:Disease {name: '糖尿病', icd_code: 'E11'});
CREATE (:Disease {name: '冠心病', icd_code: 'I25'});
CREATE (:Disease {name: '肺炎', icd_code: 'J18'});
CREATE (:Disease {name: '胃炎', icd_code: 'K29'});
CREATE (:Disease {name: '抑郁症', icd_code: 'F32'});
CREATE (:Disease {name: '哮喘', icd_code: 'J45'});
CREATE (:Disease {name: '脑卒中', icd_code: 'I63'});
CREATE (:Disease {name: '慢性肾病', icd_code: 'N18'});
CREATE (:Disease {name: '肝硬化', icd_code: 'K74'});
CREATE (:Disease {name: '骨质疏松', icd_code: 'M81'});
CREATE (:Disease {name: '类风湿关节炎', icd_code: 'M06'});
CREATE (:Disease {name: '甲状腺功能亢进', icd_code: 'E05'});
CREATE (:Disease {name: '慢性阻塞性肺疾病', icd_code: 'J44'});
CREATE (:Disease {name: '心力衰竭', icd_code: 'I50'});
CREATE (:Disease {name: '胃溃疡', icd_code: 'K25'});
CREATE (:Disease {name: '痛风', icd_code: 'M10'});
CREATE (:Disease {name: '帕金森病', icd_code: 'G20'});
CREATE (:Disease {name: '癫痫', icd_code: 'G40'});
CREATE (:Disease {name: '湿疹', icd_code: 'L30'});
CREATE (:Disease {name: '银屑病', icd_code: 'L40'});
CREATE (:Disease {name: '过敏性鼻炎', icd_code: 'J30'});
CREATE (:Disease {name: '青光眼', icd_code: 'H40'});
CREATE (:Disease {name: '前列腺增生', icd_code: 'N40'});
CREATE (:Disease {name: '子宫肌瘤', icd_code: 'D25'});
CREATE (:Disease {name: '小儿肺炎', icd_code: 'J18.9'});
CREATE (:Disease {name: '腰椎间盘突出', icd_code: 'M51'});
CREATE (:Disease {name: '偏头痛', icd_code: 'G43'});
CREATE (:Disease {name: '焦虑症', icd_code: 'F41'});
CREATE (:Disease {name: '肾结石', icd_code: 'N20'});

// ------------------------------------------------------------
// 4. 症状节点 (50个)
// ------------------------------------------------------------
CREATE (:Symptom {name: '头痛'});
CREATE (:Symptom {name: '发热'});
CREATE (:Symptom {name: '咳嗽'});
CREATE (:Symptom {name: '胸闷'});
CREATE (:Symptom {name: '腹痛'});
CREATE (:Symptom {name: '失眠'});
CREATE (:Symptom {name: '心悸'});
CREATE (:Symptom {name: '恶心'});
CREATE (:Symptom {name: '呕吐'});
CREATE (:Symptom {name: '腹泻'});
CREATE (:Symptom {name: '便秘'});
CREATE (:Symptom {name: '乏力'});
CREATE (:Symptom {name: '头晕'});
CREATE (:Symptom {name: '气短'});
CREATE (:Symptom {name: '水肿'});
CREATE (:Symptom {name: '胸痛'});
CREATE (:Symptom {name: '关节痛'});
CREATE (:Symptom {name: '肌肉酸痛'});
CREATE (:Symptom {name: '食欲减退'});
CREATE (:Symptom {name: '体重下降'});
CREATE (:Symptom {name: '多饮'});
CREATE (:Symptom {name: '多尿'});
CREATE (:Symptom {name: '视力模糊'});
CREATE (:Symptom {name: '皮疹'});
CREATE (:Symptom {name: '瘙痒'});
CREATE (:Symptom {name: '咳痰'});
CREATE (:Symptom {name: '咯血'});
CREATE (:Symptom {name: '吞咽困难'});
CREATE (:Symptom {name: '腹胀'});
CREATE (:Symptom {name: '黄疸'});
CREATE (:Symptom {name: '尿频'});
CREATE (:Symptom {name: '尿急'});
CREATE (:Symptom {name: '尿痛'});
CREATE (:Symptom {name: '血尿'});
CREATE (:Symptom {name: '腰痛'});
CREATE (:Symptom {name: '手抖'});
CREATE (:Symptom {name: '麻木'});
CREATE (:Symptom {name: '抽搐'});
CREATE (:Symptom {name: '情绪低落'});
CREATE (:Symptom {name: '焦虑不安'});
CREATE (:Symptom {name: '记忆力减退'});
CREATE (:Symptom {name: '耳鸣'});
CREATE (:Symptom {name: '鼻塞'});
CREATE (:Symptom {name: '流涕'});
CREATE (:Symptom {name: '喷嚏'});
CREATE (:Symptom {name: '眼压升高'});
CREATE (:Symptom {name: '月经不调'});
CREATE (:Symptom {name: '骨痛'});
CREATE (:Symptom {name: '出汗异常'});
CREATE (:Symptom {name: '口渴'});

// ------------------------------------------------------------
// 5. 药物节点 (30个)
// ------------------------------------------------------------
CREATE (:Drug {name: '阿司匹林', category: '解热镇痛药'});
CREATE (:Drug {name: '二甲双胍', category: '降糖药'});
CREATE (:Drug {name: '阿莫西林', category: '抗生素'});
CREATE (:Drug {name: '硝苯地平', category: '钙通道阻滞剂'});
CREATE (:Drug {name: '奥美拉唑', category: '质子泵抑制剂'});
CREATE (:Drug {name: '氯沙坦', category: 'ARB类降压药'});
CREATE (:Drug {name: '阿托伐他汀', category: '他汀类降脂药'});
CREATE (:Drug {name: '氨氯地平', category: '钙通道阻滞剂'});
CREATE (:Drug {name: '美托洛尔', category: 'β受体阻滞剂'});
CREATE (:Drug {name: '氢氯噻嗪', category: '利尿剂'});
CREATE (:Drug {name: '布洛芬', category: '非甾体抗炎药'});
CREATE (:Drug {name: '头孢克肟', category: '抗生素'});
CREATE (:Drug {name: '左氧氟沙星', category: '喹诺酮类抗生素'});
CREATE (:Drug {name: '沙丁胺醇', category: '支气管扩张剂'});
CREATE (:Drug {name: '布地奈德', category: '糖皮质激素'});
CREATE (:Drug {name: '氟西汀', category: '选择性5-HT再摄取抑制剂'});
CREATE (:Drug {name: '地西泮', category: '苯二氮卓类'});
CREATE (:Drug {name: '左旋多巴', category: '抗帕金森药'});
CREATE (:Drug {name: '卡马西平', category: '抗癫痫药'});
CREATE (:Drug {name: '别嘌醇', category: '降尿酸药'});
CREATE (:Drug {name: '甲氨蝶呤', category: '免疫抑制剂'});
CREATE (:Drug {name: '胰岛素', category: '降糖药'});
CREATE (:Drug {name: '华法林', category: '抗凝药'});
CREATE (:Drug {name: '氯雷他定', category: '抗组胺药'});
CREATE (:Drug {name: '噻托溴铵', category: '抗胆碱能药'});
CREATE (:Drug {name: '螺内酯', category: '醛固酮拮抗剂'});
CREATE (:Drug {name: '坦索罗辛', category: 'α受体阻滞剂'});
CREATE (:Drug {name: '阿仑膦酸钠', category: '双膦酸盐'});
CREATE (:Drug {name: '甲巯咪唑', category: '抗甲状腺药'});
CREATE (:Drug {name: '拉坦前列素', category: '前列腺素类似物'});

// ============================================================
// 6. 关系
// ============================================================

// ------------------------------------------------------------
// 6.1 疾病-症状关系 (HAS_SYMPTOM) — 至少80条
// ------------------------------------------------------------

// 高血压
MATCH (d:Disease {name:'高血压'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'高血压'}), (s:Symptom {name:'头晕'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'高血压'}), (s:Symptom {name:'心悸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'高血压'}), (s:Symptom {name:'胸闷'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'高血压'}), (s:Symptom {name:'视力模糊'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 糖尿病
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'多饮'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'多尿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'体重下降'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'视力模糊'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'糖尿病'}), (s:Symptom {name:'口渴'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 冠心病
MATCH (d:Disease {name:'冠心病'}), (s:Symptom {name:'胸痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'冠心病'}), (s:Symptom {name:'胸闷'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'冠心病'}), (s:Symptom {name:'心悸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'冠心病'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'冠心病'}), (s:Symptom {name:'出汗异常'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 肺炎
MATCH (d:Disease {name:'肺炎'}), (s:Symptom {name:'发热'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肺炎'}), (s:Symptom {name:'咳嗽'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肺炎'}), (s:Symptom {name:'咳痰'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肺炎'}), (s:Symptom {name:'胸痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肺炎'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 胃炎
MATCH (d:Disease {name:'胃炎'}), (s:Symptom {name:'腹痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃炎'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃炎'}), (s:Symptom {name:'呕吐'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃炎'}), (s:Symptom {name:'腹胀'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃炎'}), (s:Symptom {name:'食欲减退'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 抑郁症
MATCH (d:Disease {name:'抑郁症'}), (s:Symptom {name:'情绪低落'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'抑郁症'}), (s:Symptom {name:'失眠'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'抑郁症'}), (s:Symptom {name:'食欲减退'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'抑郁症'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'抑郁症'}), (s:Symptom {name:'记忆力减退'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 哮喘
MATCH (d:Disease {name:'哮喘'}), (s:Symptom {name:'咳嗽'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'哮喘'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'哮喘'}), (s:Symptom {name:'胸闷'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 脑卒中
MATCH (d:Disease {name:'脑卒中'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'脑卒中'}), (s:Symptom {name:'头晕'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'脑卒中'}), (s:Symptom {name:'麻木'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'脑卒中'}), (s:Symptom {name:'呕吐'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 慢性肾病
MATCH (d:Disease {name:'慢性肾病'}), (s:Symptom {name:'水肿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性肾病'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性肾病'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性肾病'}), (s:Symptom {name:'尿频'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 肝硬化
MATCH (d:Disease {name:'肝硬化'}), (s:Symptom {name:'腹胀'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肝硬化'}), (s:Symptom {name:'黄疸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肝硬化'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肝硬化'}), (s:Symptom {name:'食欲减退'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肝硬化'}), (s:Symptom {name:'水肿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 骨质疏松
MATCH (d:Disease {name:'骨质疏松'}), (s:Symptom {name:'骨痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'骨质疏松'}), (s:Symptom {name:'腰痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'骨质疏松'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 类风湿关节炎
MATCH (d:Disease {name:'类风湿关节炎'}), (s:Symptom {name:'关节痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'类风湿关节炎'}), (s:Symptom {name:'肌肉酸痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'类风湿关节炎'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'类风湿关节炎'}), (s:Symptom {name:'发热'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 甲状腺功能亢进
MATCH (d:Disease {name:'甲状腺功能亢进'}), (s:Symptom {name:'心悸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (s:Symptom {name:'手抖'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (s:Symptom {name:'出汗异常'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (s:Symptom {name:'体重下降'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (s:Symptom {name:'失眠'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 慢性阻塞性肺疾病
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (s:Symptom {name:'咳嗽'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (s:Symptom {name:'咳痰'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (s:Symptom {name:'胸闷'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 心力衰竭
MATCH (d:Disease {name:'心力衰竭'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'心力衰竭'}), (s:Symptom {name:'水肿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'心力衰竭'}), (s:Symptom {name:'乏力'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'心力衰竭'}), (s:Symptom {name:'心悸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'心力衰竭'}), (s:Symptom {name:'咳嗽'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 胃溃疡
MATCH (d:Disease {name:'胃溃疡'}), (s:Symptom {name:'腹痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃溃疡'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃溃疡'}), (s:Symptom {name:'呕吐'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'胃溃疡'}), (s:Symptom {name:'腹胀'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 痛风
MATCH (d:Disease {name:'痛风'}), (s:Symptom {name:'关节痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'痛风'}), (s:Symptom {name:'水肿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'痛风'}), (s:Symptom {name:'发热'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 帕金森病
MATCH (d:Disease {name:'帕金森病'}), (s:Symptom {name:'手抖'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'帕金森病'}), (s:Symptom {name:'肌肉酸痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'帕金森病'}), (s:Symptom {name:'失眠'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'帕金森病'}), (s:Symptom {name:'便秘'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 癫痫
MATCH (d:Disease {name:'癫痫'}), (s:Symptom {name:'抽搐'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'癫痫'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'癫痫'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'癫痫'}), (s:Symptom {name:'记忆力减退'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 湿疹
MATCH (d:Disease {name:'湿疹'}), (s:Symptom {name:'皮疹'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'湿疹'}), (s:Symptom {name:'瘙痒'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 银屑病
MATCH (d:Disease {name:'银屑病'}), (s:Symptom {name:'皮疹'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'银屑病'}), (s:Symptom {name:'瘙痒'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'银屑病'}), (s:Symptom {name:'关节痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 过敏性鼻炎
MATCH (d:Disease {name:'过敏性鼻炎'}), (s:Symptom {name:'鼻塞'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'过敏性鼻炎'}), (s:Symptom {name:'流涕'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'过敏性鼻炎'}), (s:Symptom {name:'喷嚏'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'过敏性鼻炎'}), (s:Symptom {name:'瘙痒'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 青光眼
MATCH (d:Disease {name:'青光眼'}), (s:Symptom {name:'眼压升高'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'青光眼'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'青光眼'}), (s:Symptom {name:'视力模糊'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'青光眼'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 前列腺增生
MATCH (d:Disease {name:'前列腺增生'}), (s:Symptom {name:'尿频'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'前列腺增生'}), (s:Symptom {name:'尿急'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'前列腺增生'}), (s:Symptom {name:'尿痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 子宫肌瘤
MATCH (d:Disease {name:'子宫肌瘤'}), (s:Symptom {name:'腹痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'子宫肌瘤'}), (s:Symptom {name:'月经不调'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'子宫肌瘤'}), (s:Symptom {name:'腰痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 小儿肺炎
MATCH (d:Disease {name:'小儿肺炎'}), (s:Symptom {name:'发热'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'小儿肺炎'}), (s:Symptom {name:'咳嗽'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'小儿肺炎'}), (s:Symptom {name:'气短'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'小儿肺炎'}), (s:Symptom {name:'咳痰'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 腰椎间盘突出
MATCH (d:Disease {name:'腰椎间盘突出'}), (s:Symptom {name:'腰痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'腰椎间盘突出'}), (s:Symptom {name:'麻木'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'腰椎间盘突出'}), (s:Symptom {name:'肌肉酸痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 偏头痛
MATCH (d:Disease {name:'偏头痛'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'偏头痛'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'偏头痛'}), (s:Symptom {name:'视力模糊'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'偏头痛'}), (s:Symptom {name:'呕吐'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 焦虑症
MATCH (d:Disease {name:'焦虑症'}), (s:Symptom {name:'焦虑不安'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'焦虑症'}), (s:Symptom {name:'失眠'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'焦虑症'}), (s:Symptom {name:'心悸'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'焦虑症'}), (s:Symptom {name:'头痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// 肾结石
MATCH (d:Disease {name:'肾结石'}), (s:Symptom {name:'腰痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肾结石'}), (s:Symptom {name:'血尿'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肾结石'}), (s:Symptom {name:'恶心'}) CREATE (d)-[:HAS_SYMPTOM]->(s);
MATCH (d:Disease {name:'肾结石'}), (s:Symptom {name:'尿痛'}) CREATE (d)-[:HAS_SYMPTOM]->(s);

// ------------------------------------------------------------
// 6.2 疾病-药物关系 (TREATED_BY) — 至少50条
// ------------------------------------------------------------

// 高血压
MATCH (d:Disease {name:'高血压'}), (dr:Drug {name:'硝苯地平'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'高血压'}), (dr:Drug {name:'氯沙坦'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'高血压'}), (dr:Drug {name:'氨氯地平'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'高血压'}), (dr:Drug {name:'美托洛尔'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'高血压'}), (dr:Drug {name:'氢氯噻嗪'}) CREATE (d)-[:TREATED_BY]->(dr);

// 糖尿病
MATCH (d:Disease {name:'糖尿病'}), (dr:Drug {name:'二甲双胍'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'糖尿病'}), (dr:Drug {name:'胰岛素'}) CREATE (d)-[:TREATED_BY]->(dr);

// 冠心病
MATCH (d:Disease {name:'冠心病'}), (dr:Drug {name:'阿司匹林'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'冠心病'}), (dr:Drug {name:'阿托伐他汀'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'冠心病'}), (dr:Drug {name:'美托洛尔'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'冠心病'}), (dr:Drug {name:'硝苯地平'}) CREATE (d)-[:TREATED_BY]->(dr);

// 肺炎
MATCH (d:Disease {name:'肺炎'}), (dr:Drug {name:'阿莫西林'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'肺炎'}), (dr:Drug {name:'头孢克肟'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'肺炎'}), (dr:Drug {name:'左氧氟沙星'}) CREATE (d)-[:TREATED_BY]->(dr);

// 胃炎
MATCH (d:Disease {name:'胃炎'}), (dr:Drug {name:'奥美拉唑'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'胃炎'}), (dr:Drug {name:'阿莫西林'}) CREATE (d)-[:TREATED_BY]->(dr);

// 抑郁症
MATCH (d:Disease {name:'抑郁症'}), (dr:Drug {name:'氟西汀'}) CREATE (d)-[:TREATED_BY]->(dr);

// 哮喘
MATCH (d:Disease {name:'哮喘'}), (dr:Drug {name:'沙丁胺醇'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'哮喘'}), (dr:Drug {name:'布地奈德'}) CREATE (d)-[:TREATED_BY]->(dr);

// 脑卒中
MATCH (d:Disease {name:'脑卒中'}), (dr:Drug {name:'阿司匹林'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'脑卒中'}), (dr:Drug {name:'阿托伐他汀'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'脑卒中'}), (dr:Drug {name:'华法林'}) CREATE (d)-[:TREATED_BY]->(dr);

// 慢性肾病
MATCH (d:Disease {name:'慢性肾病'}), (dr:Drug {name:'氯沙坦'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'慢性肾病'}), (dr:Drug {name:'螺内酯'}) CREATE (d)-[:TREATED_BY]->(dr);

// 肝硬化
MATCH (d:Disease {name:'肝硬化'}), (dr:Drug {name:'螺内酯'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'肝硬化'}), (dr:Drug {name:'奥美拉唑'}) CREATE (d)-[:TREATED_BY]->(dr);

// 骨质疏松
MATCH (d:Disease {name:'骨质疏松'}), (dr:Drug {name:'阿仑膦酸钠'}) CREATE (d)-[:TREATED_BY]->(dr);

// 类风湿关节炎
MATCH (d:Disease {name:'类风湿关节炎'}), (dr:Drug {name:'甲氨蝶呤'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'类风湿关节炎'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);

// 甲状腺功能亢进
MATCH (d:Disease {name:'甲状腺功能亢进'}), (dr:Drug {name:'甲巯咪唑'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (dr:Drug {name:'美托洛尔'}) CREATE (d)-[:TREATED_BY]->(dr);

// 慢性阻塞性肺疾病
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (dr:Drug {name:'噻托溴铵'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (dr:Drug {name:'沙丁胺醇'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (dr:Drug {name:'布地奈德'}) CREATE (d)-[:TREATED_BY]->(dr);

// 心力衰竭
MATCH (d:Disease {name:'心力衰竭'}), (dr:Drug {name:'美托洛尔'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'心力衰竭'}), (dr:Drug {name:'螺内酯'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'心力衰竭'}), (dr:Drug {name:'氢氯噻嗪'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'心力衰竭'}), (dr:Drug {name:'氯沙坦'}) CREATE (d)-[:TREATED_BY]->(dr);

// 胃溃疡
MATCH (d:Disease {name:'胃溃疡'}), (dr:Drug {name:'奥美拉唑'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'胃溃疡'}), (dr:Drug {name:'阿莫西林'}) CREATE (d)-[:TREATED_BY]->(dr);

// 痛风
MATCH (d:Disease {name:'痛风'}), (dr:Drug {name:'别嘌醇'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'痛风'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);

// 帕金森病
MATCH (d:Disease {name:'帕金森病'}), (dr:Drug {name:'左旋多巴'}) CREATE (d)-[:TREATED_BY]->(dr);

// 癫痫
MATCH (d:Disease {name:'癫痫'}), (dr:Drug {name:'卡马西平'}) CREATE (d)-[:TREATED_BY]->(dr);

// 湿疹
MATCH (d:Disease {name:'湿疹'}), (dr:Drug {name:'氯雷他定'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'湿疹'}), (dr:Drug {name:'布地奈德'}) CREATE (d)-[:TREATED_BY]->(dr);

// 银屑病
MATCH (d:Disease {name:'银屑病'}), (dr:Drug {name:'甲氨蝶呤'}) CREATE (d)-[:TREATED_BY]->(dr);

// 过敏性鼻炎
MATCH (d:Disease {name:'过敏性鼻炎'}), (dr:Drug {name:'氯雷他定'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'过敏性鼻炎'}), (dr:Drug {name:'布地奈德'}) CREATE (d)-[:TREATED_BY]->(dr);

// 青光眼
MATCH (d:Disease {name:'青光眼'}), (dr:Drug {name:'拉坦前列素'}) CREATE (d)-[:TREATED_BY]->(dr);

// 前列腺增生
MATCH (d:Disease {name:'前列腺增生'}), (dr:Drug {name:'坦索罗辛'}) CREATE (d)-[:TREATED_BY]->(dr);

// 子宫肌瘤
MATCH (d:Disease {name:'子宫肌瘤'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);

// 小儿肺炎
MATCH (d:Disease {name:'小儿肺炎'}), (dr:Drug {name:'阿莫西林'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'小儿肺炎'}), (dr:Drug {name:'头孢克肟'}) CREATE (d)-[:TREATED_BY]->(dr);

// 腰椎间盘突出
MATCH (d:Disease {name:'腰椎间盘突出'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);

// 偏头痛
MATCH (d:Disease {name:'偏头痛'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'偏头痛'}), (dr:Drug {name:'阿司匹林'}) CREATE (d)-[:TREATED_BY]->(dr);

// 焦虑症
MATCH (d:Disease {name:'焦虑症'}), (dr:Drug {name:'地西泮'}) CREATE (d)-[:TREATED_BY]->(dr);
MATCH (d:Disease {name:'焦虑症'}), (dr:Drug {name:'氟西汀'}) CREATE (d)-[:TREATED_BY]->(dr);

// 肾结石
MATCH (d:Disease {name:'肾结石'}), (dr:Drug {name:'布洛芬'}) CREATE (d)-[:TREATED_BY]->(dr);

// ------------------------------------------------------------
// 6.3 疾病-科室关系 (BELONGS_TO) — 全部30个疾病
// ------------------------------------------------------------
MATCH (d:Disease {name:'高血压'}), (dep:Department {name:'心血管内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'糖尿病'}), (dep:Department {name:'内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'冠心病'}), (dep:Department {name:'心血管内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'肺炎'}), (dep:Department {name:'呼吸内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'胃炎'}), (dep:Department {name:'消化内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'抑郁症'}), (dep:Department {name:'精神科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'哮喘'}), (dep:Department {name:'呼吸内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'脑卒中'}), (dep:Department {name:'神经内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'慢性肾病'}), (dep:Department {name:'内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'肝硬化'}), (dep:Department {name:'消化内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'骨质疏松'}), (dep:Department {name:'骨科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'类风湿关节炎'}), (dep:Department {name:'中医科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'甲状腺功能亢进'}), (dep:Department {name:'内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'慢性阻塞性肺疾病'}), (dep:Department {name:'呼吸内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'心力衰竭'}), (dep:Department {name:'心血管内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'胃溃疡'}), (dep:Department {name:'消化内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'痛风'}), (dep:Department {name:'内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'帕金森病'}), (dep:Department {name:'神经内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'癫痫'}), (dep:Department {name:'神经内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'湿疹'}), (dep:Department {name:'皮肤科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'银屑病'}), (dep:Department {name:'皮肤科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'过敏性鼻炎'}), (dep:Department {name:'耳鼻喉科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'青光眼'}), (dep:Department {name:'眼科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'前列腺增生'}), (dep:Department {name:'泌尿外科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'子宫肌瘤'}), (dep:Department {name:'妇产科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'小儿肺炎'}), (dep:Department {name:'儿科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'腰椎间盘突出'}), (dep:Department {name:'骨科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'偏头痛'}), (dep:Department {name:'神经内科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'焦虑症'}), (dep:Department {name:'精神科'}) CREATE (d)-[:BELONGS_TO]->(dep);
MATCH (d:Disease {name:'肾结石'}), (dep:Department {name:'泌尿外科'}) CREATE (d)-[:BELONGS_TO]->(dep);

// ------------------------------------------------------------
// 6.4 药物-副作用关系 (SIDE_EFFECT) — 至少20条
// ------------------------------------------------------------

// 阿司匹林 — 胃肠道刺激、出血倾向
MATCH (dr:Drug {name:'阿司匹林'}), (s:Symptom {name:'腹痛'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'阿司匹林'}), (s:Symptom {name:'恶心'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 二甲双胍 — 胃肠道反应
MATCH (dr:Drug {name:'二甲双胍'}), (s:Symptom {name:'腹泻'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'二甲双胍'}), (s:Symptom {name:'恶心'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'二甲双胍'}), (s:Symptom {name:'腹痛'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 阿莫西林 — 过敏反应
MATCH (dr:Drug {name:'阿莫西林'}), (s:Symptom {name:'皮疹'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'阿莫西林'}), (s:Symptom {name:'腹泻'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 硝苯地平 — 血管扩张相关
MATCH (dr:Drug {name:'硝苯地平'}), (s:Symptom {name:'头痛'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'硝苯地平'}), (s:Symptom {name:'水肿'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'硝苯地平'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 奥美拉唑 — 长期使用副作用
MATCH (dr:Drug {name:'奥美拉唑'}), (s:Symptom {name:'头痛'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'奥美拉唑'}), (s:Symptom {name:'腹泻'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 美托洛尔 — β阻滞剂副作用
MATCH (dr:Drug {name:'美托洛尔'}), (s:Symptom {name:'乏力'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'美托洛尔'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'美托洛尔'}), (s:Symptom {name:'失眠'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 氟西汀 — SSRI副作用
MATCH (dr:Drug {name:'氟西汀'}), (s:Symptom {name:'恶心'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'氟西汀'}), (s:Symptom {name:'失眠'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'氟西汀'}), (s:Symptom {name:'头痛'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 甲氨蝶呤 — 免疫抑制剂副作用
MATCH (dr:Drug {name:'甲氨蝶呤'}), (s:Symptom {name:'恶心'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'甲氨蝶呤'}), (s:Symptom {name:'乏力'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'甲氨蝶呤'}), (s:Symptom {name:'食欲减退'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 华法林 — 抗凝副作用
MATCH (dr:Drug {name:'华法林'}), (s:Symptom {name:'血尿'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 卡马西平 — 抗癫痫副作用
MATCH (dr:Drug {name:'卡马西平'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'卡马西平'}), (s:Symptom {name:'皮疹'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 地西泮 — 镇静副作用
MATCH (dr:Drug {name:'地西泮'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'地西泮'}), (s:Symptom {name:'乏力'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 氢氯噻嗪 — 利尿剂副作用
MATCH (dr:Drug {name:'氢氯噻嗪'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'氢氯噻嗪'}), (s:Symptom {name:'乏力'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// 左旋多巴 — 抗帕金森副作用
MATCH (dr:Drug {name:'左旋多巴'}), (s:Symptom {name:'恶心'}) CREATE (dr)-[:SIDE_EFFECT]->(s);
MATCH (dr:Drug {name:'左旋多巴'}), (s:Symptom {name:'头晕'}) CREATE (dr)-[:SIDE_EFFECT]->(s);

// ------------------------------------------------------------
// 6.5 药物-禁忌联用关系 (CONTRADICTS) — 至少8条
// ------------------------------------------------------------

// 华法林与阿司匹林 — 出血风险叠加
MATCH (a:Drug {name:'华法林'}), (b:Drug {name:'阿司匹林'}) CREATE (a)-[:CONTRADICTS {reason: '出血风险显著增加'}]->(b);

// 甲氨蝶呤与布洛芬 — 甲氨蝶呤排泄减少致毒性增加
MATCH (a:Drug {name:'甲氨蝶呤'}), (b:Drug {name:'布洛芬'}) CREATE (a)-[:CONTRADICTS {reason: 'NSAIDs减少甲氨蝶呤肾排泄，增加毒性'}]->(b);

// 地西泮与氟西汀 — 中枢抑制叠加
MATCH (a:Drug {name:'地西泮'}), (b:Drug {name:'氟西汀'}) CREATE (a)-[:CONTRADICTS {reason: '中枢神经抑制作用叠加'}]->(b);

// 氯沙坦与螺内酯 — 高钾血症风险
MATCH (a:Drug {name:'氯沙坦'}), (b:Drug {name:'螺内酯'}) CREATE (a)-[:CONTRADICTS {reason: '联用可致严重高钾血症'}]->(b);

// 硝苯地平与美托洛尔 — 低血压/心动过缓
MATCH (a:Drug {name:'硝苯地平'}), (b:Drug {name:'美托洛尔'}) CREATE (a)-[:CONTRADICTS {reason: '联用可致严重低血压和心动过缓'}]->(b);

// 卡马西平与华法林 — 卡马西平加速华法林代谢
MATCH (a:Drug {name:'卡马西平'}), (b:Drug {name:'华法林'}) CREATE (a)-[:CONTRADICTS {reason: '卡马西平诱导CYP酶加速华法林代谢，降低抗凝效果'}]->(b);

// 甲巯咪唑与华法林 — 影响凝血功能
MATCH (a:Drug {name:'甲巯咪唑'}), (b:Drug {name:'华法林'}) CREATE (a)-[:CONTRADICTS {reason: '甲巯咪唑影响维生素K代谢，增强华法林抗凝作用'}]->(b);

// 阿司匹林与布洛芬 — NSAIDs竞争性拮抗
MATCH (a:Drug {name:'阿司匹林'}), (b:Drug {name:'布洛芬'}) CREATE (a)-[:CONTRADICTS {reason: '布洛芬竞争性阻断阿司匹林的抗血小板作用'}]->(b);

// 二甲双胍与左氧氟沙星 — 低血糖风险
MATCH (a:Drug {name:'二甲双胍'}), (b:Drug {name:'左氧氟沙星'}) CREATE (a)-[:CONTRADICTS {reason: '喹诺酮类可致血糖异常波动'}]->(b);

// 氢氯噻嗪与布洛芬 — 降低利尿降压效果
MATCH (a:Drug {name:'氢氯噻嗪'}), (b:Drug {name:'布洛芬'}) CREATE (a)-[:CONTRADICTS {reason: 'NSAIDs减弱利尿剂降压效果并增加肾损伤风险'}]->(b);
