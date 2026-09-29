# DeerMind Design Document Standard v1.0

> **中文名称**：DeerMind 设计文档规范  
> **版本**：v1.0  
> **状态**：正式基线  
> **适用范围**：DeerMind Concept Architecture、Space Design、System Design、Protocol / Component Design 及其他长期维护的技术设计文档  
> **参考样例**：`DeerMind_Concept_Architecture_v0.7.md`  
> **写作标杆**：Amazon Builders’ Library 的工业级架构写作风格  
> **更新时间**：2026-09-26

---

## 1. 目的

本规范用于统一 DeerMind 设计文档的结构、语言、论证方式和维护方式。

它解决的不是“Markdown 怎么写”，而是一个更根本的问题：

> **如何把复杂设计思想表达成可理解、可质疑、可引用、可维护，并能够长期约束实现的正式工程文档。**

DeerMind 的设计文档不是讨论过程的存档，也不是术语、模型和规则的堆积。它首先是一条经过整理的设计论证：读者应该能够理解系统面对什么问题，这些问题为什么导出当前架构，设计如何运行，边界为什么这样划分，替代方案为什么没有被采用，以及哪些问题仍然保持开放。

因此：

\[
\boxed{
DesignDocument
\neq
DiscussionArchive
}
\]

而应当是：

\[
\boxed{
DesignDocument
=
StructuredArgument
+
SemanticContract
+
DecisionRationale
}
\]

---

## 2. 基本原则

### 2.1 设计文档首先是一条 Architecture Narrative

一篇成熟的设计文档应当有清晰、稳定的主叙事。默认逻辑顺序是：

\[
Problem
\rightarrow
Constraints
\rightarrow
DesignForces
\rightarrow
Architecture
\rightarrow
Runtime
\rightarrow
Contracts
\rightarrow
Tradeoffs
\rightarrow
Risks
\rightarrow
Handoff
\]

读者不应通过阅读几十个定义和规则后，自己拼接出系统为什么这样设计。

设计文档应主动完成这项工作。

### 2.2 先建立心智模型，再增加精度

设计文档的第一职责不是展示设计者知道多少，而是让读者形成正确的 mental model。

因此文档应遵循：

\[
Overview
\rightarrow
Structure
\rightarrow
Dynamics
\rightarrow
Boundaries
\rightarrow
Details
\]

而不是：

\[
Definitions
\rightarrow
Definitions
\rightarrow
Invariants
\rightarrow
Exceptions
\rightarrow
Architecture
\]

第一遍阅读应该能够理解系统的整体结构；第二遍阅读才进入语义边界和设计细节；实现者需要的完整规则可以进入附录或下位设计文档。

### 2.3 正文服务理解，附录服务完整性

正文不承担“保存所有信息”的责任。

正文只保留：

- 影响整体 mental model 的概念；
- 架构级设计决策；
- 关键运行闭环；
- 核心边界与契约；
- 重要 trade-off；
- 对实现具有长期约束力的核心 invariant。

以下内容通常应下沉：

- 完整 invariant registry；
- 历史版本迁移记录；
- 理论综述；
- 大量验证场景；
- 详细字段表；
- 实现检查表；
- 长篇术语索引；
- 设计讨论历史。

原则是：

> **正文追求理解密度，附录追求检索完整性。**

### 2.4 Complexity Must Earn Its Keep 也适用于文档

复杂系统不意味着复杂表达。

任何新增章节、公式、表格、图、术语、标题层级或 invariant 都必须证明它带来了新的解释价值。

如果一个内容只是：

- 重复前文；
- 换一种形式重述同一结论；
- 为了“显得完整”而加入；
- 只对极少数实现细节有意义；

则不应进入主叙事。

### 2.5 设计结论必须能够被解释，而不仅被宣布

重要设计选择不能只写：

> Observation 属于 Interaction Space。

还必须回答：

- 为什么需要这个边界；
- 有哪些替代方案；
- 替代方案的优点是什么；
- 为什么仍然选择当前方案；
- 当前选择带来了什么代价。

成熟设计文档的基本推导单位是：

\[
问题
\rightarrow
约束
\rightarrow
候选方案
\rightarrow
权衡
\rightarrow
选择
\rightarrow
结论
\]

---

## 3. 文档分层

DeerMind 使用多层设计文档。不同层级回答不同问题，不应相互替代。

### 3.1 Concept Architecture

回答：

> **系统为什么必须由这些不可约语义责任构成？**

关注：

- 系统目标；
- 第一性约束；
- 顶层语义空间；
- 全局运行闭环；
- 跨 Space 语义契约；
- Constitution；
- Governance；
- 核心 Architecture Decisions；
- 核心 Invariants；
- System Design Handoff。

不负责：

- 服务拆分；
- 存储结构；
- API；
- LLM 选型；
- 数据表；
- 异步任务机制；
- 部署拓扑；
- 具体算法。

Concept Architecture 不得因为后续实现方便而被偷偷重写。

### 3.2 Space Design

回答：

> **某个 Space 如何完整承担自己的语义责任？**

关注：

- Space 目标与边界；
- Core Models；
- Semantic Objects；
- Identity；
- Lifecycle；
- Relationships；
- Inputs / Outputs；
- Invariants；
- Falsifiability；
- Version / Provenance；
- Cross-Space Contracts；
- Open Questions。

Space Design 不应重新解释顶层架构，也不应复制其他 Space 的内部设计。

### 3.3 System Design

回答：

> **如何把已经冻结的概念架构实现成可运行系统？**

关注：

- Minimum Viable Closed Loop；
- 软件模块；
- 服务与进程；
- 数据流；
- 存储；
- API / Protocol；
- LLM / Rule / Statistical Model 分工；
- 版本管理；
- 依赖传播；
- 并发、一致性和事务边界；
- 可观测性；
- 性能；
- 安全；
- 部署；
- 运维；
- 数据生命周期；
- Governance workflow。

System Design 可以分阶段实现能力，但不能降低 Concept Architecture 的语义不变量。

\[
\boxed{
ArchitectureInvariant
\ remains\ mandatory
\qquad
ImplementationCapability
\ may\ be\ staged
}
\]

### 3.4 Protocol / Component Design

回答：

> **某个明确组件或协议如何工作？**

例如：

- Event Storage；
- Semantic Projection Protocol；
- Evidence Engine；
- Version Activation；
- Dependency Invalidation；
- Governance Approval Protocol；
- Replay Engine。

此类文档可以深入字段、状态机、接口和算法，但必须引用上位语义合同，不重新发明业务语义。

---

## 4. 推荐的主结构

不同文档可以调整章节名称，但长期维护的核心设计文档默认采用以下叙事骨架。

### 4.1 文档定位

回答：

- 这是什么文档；
- 它解决什么；
- 它不解决什么；
- 当前状态是什么；
- 它与其他正式文档是什么关系。

不要在开头堆完整架构细节。

### 4.2 问题与设计约束

先解释现实问题。

应明确：

- 为什么需要这个设计；
- 哪些现实条件不可消除；
- 哪些失败模式必须避免；
- 这些条件如何限制设计空间。

这一节应该让读者理解：

> **为什么后面的设计不是随意分类。**

### 4.3 Architecture / Solution Overview

在读者理解问题后，立即给出整体结构。

至少包含：

- 一张整体图或结构表；
- 核心组件 / Space；
- 每个部分一句职责；
- 关键关系；
- abstraction level 说明。

这一节只建立 mental model，不展开内部细节。

### 4.4 Responsibilities / Models

逐一解释核心部分。

推荐统一模板：

1. 它回答什么问题；
2. 它拥有什么；
3. 它不拥有什么；
4. 它的核心 Models / Components；
5. 为什么不能自然合并到相邻责任中；
6. 详细设计引用。

相同层级对象必须使用基本一致的结构。

### 4.5 Runtime / Dynamic View

静态结构之后必须解释系统如何运行。

只选真正 architecture-significant 的流程。

例如：

- Fast Loop；
- Evaluation Loop；
- Evolution Loop；
- Governed Change Loop。

不要试图覆盖所有业务场景。

### 4.6 Semantic Contracts / Cross-cutting Concerns

用于冻结真正需要长期保持的边界，例如：

- fact vs interpretation；
- ownership；
- single writer；
- versioning；
- provenance；
- replay；
- consistency；
- authority；
- privacy；
- invalidation。

同一条语义原则只在最合适的位置完整讲一次。

### 4.7 Decisions / Alternatives / Trade-offs

把真正重要的架构选择显式写出来。

每个关键 Decision 至少包含：

- Context；
- Decision；
- Alternatives；
- Why；
- Cost / Trade-off；
- Reopen Condition（必要时）。

### 4.8 Risks / Open Questions / Handoff

文档结尾必须告诉读者：

- 当前还有什么没解决；
- 哪些问题属于实证；
- 哪些问题属于实现；
- 哪些问题属于治理；
- 什么情况需要重新打开当前设计；
- 下一层文档必须继续解决什么。

---

## 5. 语言规范

### 5.1 默认使用现代工程中文

设计文档默认使用中文叙述。

目标不是“纯中文”，而是：

> **中文承担论证，英文承担稳定命名。**

应避免把普通工程概念无必要地写成英文。

例如：

不推荐：

> Interaction Policy 根据当前 Observation 和 Learner Belief 进行 policy decision。

推荐：

> 交互策略综合当前观察、学习者信念和运行状态，决定是否干预以及采取什么行动。

第一次正式定义可以写：

> 交互策略（Interaction Policy）

后续优先使用“交互策略”。

### 5.2 哪些英文可以保留

以下情况保留英文通常更合适：

- 正式架构名：Learning Space、Evaluation Space；
- 正式模型名：Observation Model、Evidence Model；
- 稳定枚举值：NoIntervention、NotIdentifiable；
- 难以准确翻译且业内高度稳定的术语；
- 数学 / 伪代码 / API 名称；
- 外部标准、理论或产品名称。

保留英文的理由必须是：

- 提高精度；
- 避免歧义；
- 保持系统命名一致；

而不是习惯。

### 5.3 禁止“中不中、洋不洋”的句子

避免：

> learner 的 runtime context 会影响 current policy。

应写：

> 学习者当前的运行条件会影响交互策略。

避免：

> canonical semantics change 后 old evidence 需要 replay。

应写：

> 规范语义发生变化后，旧证据必须重新解释或显式迁移。

### 5.4 使用完整句子

正式设计文档不应大量出现：

> 不是第五 Space。  
> 属于 Interaction。  
> 需要 replay。

应写：

> Global Event Model 不构成第五个 Space，因为它不拥有独立的认识对象，也不维护自己的信念或策略。

### 5.5 优先使用主动句

推荐：

> Evaluation Space 维护 Learner Belief。

少用：

> Learner Belief 被 Evaluation Space 所维护。

主动句更清晰，也更容易明确责任主体。

### 5.6 避免翻译腔

不推荐：

> 对于这一点而言，我们能够看到……

推荐：

> 这意味着……

不推荐：

> 这是由于这样一个事实，即……

推荐：

> 原因是……

### 5.7 结论必须精确但不堆术语

严谨不等于术语密度。

当普通中文足够准确时，不引入新术语。

---

## 6. 段落规范

### 6.1 段落是最基本的论证单位

一个正常段落应围绕一个完整论点展开。

推荐：

- 3–6 个完整句子；
- 一个明确中心；
- 有上下文；
- 有因果关系；
- 必要时以结论收束。

避免“一句话一段”成为常态。

### 6.2 先解释，再形式化

推荐节奏：

1. 自然语言说明问题；
2. 解释约束；
3. 给出例子；
4. 最后用公式或规则冻结结论。

不要让公式替代论证。

### 6.3 不把讨论过程写进最终文档

避免：

> 我们前面讨论过……
> 经过几轮讨论后……
> 一开始我们认为……
> 后来又发现……

正式文档应写当前结论：

> 当前架构采用……

历史演进如果有价值，进入 Design History 附录。

### 6.4 不重复同一原则

同一原则不应在：

- 定义；
- Contract；
- Invariant；
- Baseline；
- Summary；

中反复完整重述。

第一次完整定义，后续引用即可。

---

## 7. 标题与章节规范

### 7.1 一级标题表达论证阶段

一级标题应该回答：

> 这一章在整条论证链中承担什么作用？

例如：

- 设计问题与第一性约束；
- 顶层架构；
- 系统运行与反馈闭环；
- 跨 Space 语义契约；
- 架构决策与下一阶段。

不推荐把每个术语做成一级章节。

### 7.2 避免标题碎片化

如果一个章节拥有十几个二三级标题，通常意味着内容已经被过度索引化。

一个设计规则通常不需要单独标题。

例如：

- Single Writer；
- Condition Defaults to Evidence；
- Evaluation Does Not Decide Action；

可以自然写进 Evaluation Space 的完整论证中。

### 7.3 标题数量应克制

不是硬性数字，但长期架构文档应优先追求：

- 一级章节少；
- 二级章节表达主要问题；
- 三级标题仅用于真正独立的子问题。

超过三级通常需要重新审视结构。

---

## 8. 列表、表格、公式与图

### 8.1 列表

列表只用于真正并列的内容，例如：

- Goals / Non-Goals；
- 有限枚举；
- 输入 / 输出；
- 风险列表；
- 检查项；
- Options。

不要把可以形成逻辑段落的内容拆成十条 bullet。

### 8.2 表格

表格适合：

- 同层对象比较；
- responsibility matrix；
- ownership；
- change levels；
- alternatives；
- risk matrix；
- 状态 / 枚举。

表格不适合承载长篇解释。

### 8.3 公式

公式只应用于三类内容。

**定义**

\[
EvaluationSpace
=
LearnerStateModel
+
EvidenceModel
+
InferenceModel
\]

**不可违反的核心边界**

\[
Event
\neq
Observation
\neq
Evidence
\neq
Belief
\]

**关键闭环**

\[
Observation
\rightarrow
Evidence
\rightarrow
Belief
\]

其他普通设计规则优先使用自然语言。

### 8.4 避免公式滥用

不要因为一句话“重要”就使用 `\boxed{}`。

如果一篇文档所有结论都被视觉强调，最终没有任何结论真正突出。

### 8.5 图

一张图只回答一个问题。

推荐：

- 一张顶层架构图；
- 一张关键运行闭环图；
- 一张关键语义链；
- 一张必要的状态 / 版本图。

避免“万能架构图”。

图应标明 abstraction level。

### 8.6 图文关系

图不能代替正文。

正文必须能够独立解释：

- 图在表达什么；
- 哪些关系重要；
- 哪些关系没有表达。

---

## 9. Architecture Decision 规范

重要架构选择应显式记录。

推荐格式：

### Dn — Decision Title

**Context**

为什么出现这个问题。

**Decision**

当前选择。

**Alternatives**

真正考虑过的替代方案。

**Rationale**

为什么当前方案更适合当前约束。

**Trade-offs**

当前方案付出了什么代价。

**Reopen Condition**

什么证据出现时应该重新讨论。

不是每个实现细节都需要 ADR 化，只记录会长期影响：

- ownership；
- state；
- authority；
- data semantics；
- consistency；
- extensibility；
- system boundary；

的决定。

---

## 10. Invariant 与 Contract 规范

### 10.1 Invariant 不是“重要句子”

Invariant 必须满足：

- 长期有效；
- 实现必须遵守；
- 违反后系统语义会发生根本性错误；
- 可以被 review / test / audit。

如果只是当前偏好，不应写成 invariant。

### 10.2 正文只保留少量核心 Invariant

一篇架构文档通常只应要求读者记住少量核心规则。

完整规则可以进入附录。

推荐模式：

\[
CoreArchitectureInvariants
+
DerivedRules
\]

而不是几十条同等权重的不变量。

### 10.3 Contract 明确 owner 和 authority

任何跨模块 / Space contract 都必须能回答：

- 谁产生；
- 谁读取；
- 谁能修改；
- 什么是 source of truth；
- version 如何绑定；
- invalidation 如何传播；
- authority 到哪里终止。

---

## 11. Goals、Non-Goals 与边界

### 11.1 每份长期设计文档都应明确 Non-Goals

Non-Goals 不是“以后再做”，而是：

> 这个层级有意不解决什么。

这样可以防止文档不断膨胀。

### 11.2 不把下位问题抬升到上位架构

例如：

- 数据库字段不进入 Concept Architecture；
- RPC 形式不进入 Space Design；
- Prompt template 不进入 System Architecture；
- 服务划分不反向定义 semantic ownership。

### 11.3 不把上位语义下放到实现自由

例如：

- Single Writer；
- Evidence not Command；
- NoIntervention；
- Change Authority；

不能被实现层当作“可选优化”。

---

## 12. Open Questions 与风险

### 12.1 OPEN 必须分类

至少区分：

- Conceptual；
- Empirical；
- Implementation；
- Governance。

这能防止一个实现问题被误认为架构未完成。

### 12.2 OPEN 不等于必须解决

有些问题应该保持开放，直到真实数据出现。

设计文档应允许：

\[
UNKNOWN
\]

和：

\[
NotIdentifiable
\]

成为合法结论。

### 12.3 风险要写失败模式

不推荐：

> 系统可能比较复杂。

推荐：

> 如果 Observation taxonomy 扩张过快，Interaction State 可能退化成通用 Agent Memory，最终削弱 semantic ownership。

风险应包含：

- Failure Mode；
- Trigger；
- Consequence；
- Mitigation；
- Reopen Condition（必要时）。

---

## 13. 示例规范

抽象原则应尽量用最小真实例子解释。

例如：

> DeerMind 展示过除法竖式，不代表学习者已经掌握除法。教学行为首先是一个已经发生的 Action Event；只有后续独立作答、延迟保持或迁移表现，才可能形成支持掌握判断的 Evidence。

这种例子同时解释：

- Event；
- Action；
- Evidence；
- Learner Belief；
- Intervention Contamination。

好的例子应一次照亮多个概念，而不是再制造新的复杂度。

---

## 14. 术语规范

### 14.1 正式术语必须稳定

一旦正式采用：

- Learning Space；
- Learner Belief；
- Interaction Policy；

就不要在不同章节交替使用多个近义词。

### 14.2 第一次定义时中英文对齐

例如：

> 学习者信念（Learner Belief）

后续默认使用中文名称或正式代码名。

### 14.3 不为普通概念发明专有术语

如果“当前约束”足够准确，就不发明：

> Dynamic Context Restriction Envelope。

术语数量本身也是系统复杂度。

---

## 15. 版本与维护规范

### 15.1 新版本必须说明为什么升级

Version Note 应回答：

- 改变了什么；
- 为什么改变；
- 是否改变 semantic structure；
- 是否影响下游文档。

### 15.2 重构与语义变更分离

如果只是：

- 语言；
- 章节结构；
- 图表；
- 重复消除；

应明确说明：

> 不改变架构语义。

如果改变了：

- ownership；
- canonical object；
- invariant；
- authority；

则属于真正架构版本变化。

### 15.3 历史版本保留

重大重构不覆盖旧版本。

旧版本保留用于：

- semantic diff；
- design history；
- regression review。

### 15.4 下位文档引用正式版本

例如：

> 本文基于 DeerMind Concept Architecture v0.7。

避免只写：

> 基于最新架构。

---

## 16. 文档反模式

以下写法应主动避免。

### 16.1 Discussion Dump

把讨论过程按时间顺序整理成文档。

### 16.2 Definition Warehouse

大量定义彼此并列，但没有主叙事。

### 16.3 Invariant Inflation

任何“重要”结论都变成 invariant。

### 16.4 Formula Inflation

任何重要句子都用 boxed formula。

### 16.5 Bullet Wall

连续几十条 bullet，没有完整论证。

### 16.6 Heading Explosion

每一个术语都成为二三级标题。

### 16.7 English Leakage

中文语法中随意混入普通英文工程词。

### 16.8 Copy-down Architecture

Concept Architecture 复制 Space Design，Space Design 又复制 Component Design。

### 16.9 Hidden Decision

文档只写最终结构，不解释重要 alternative。

### 16.10 False Completeness

为了“完整”提前冻结没有证据支持的模型、字段或 taxonomy。

### 16.11 Implementation Leakage

因为数据库、服务或 LLM 实现方便，反向修改 semantic ownership。

### 16.12 Summary Duplication

结尾重新逐条复制全文，而不是总结真正的 architecture thesis。

---

## 17. 文档评审清单

正式进入 Freeze Candidate 前，至少检查以下问题。

### 17.1 结构

- [ ] 读者能否在前 10% 的篇幅内建立整体 mental model？
- [ ] 每个一级章节是否承担唯一叙事责任？
- [ ] 是否存在“定义—Contract—Invariant—Summary”重复？
- [ ] 是否把下位设计细节复制到了上位文档？
- [ ] 是否明确 Non-Goals？

### 17.2 论证

- [ ] 重要设计结论是否说明“为什么”？
- [ ] 是否记录过真正有竞争力的 alternative？
- [ ] Trade-off 是否真实，而不是只写优点？
- [ ] 是否区分事实、假设、选择和开放问题？
- [ ] 关键设计是否有 Reopen Condition？

### 17.3 语言

- [ ] 中文是否承担主要叙事？
- [ ] 是否存在无必要中英混排？
- [ ] 是否大量一句一段？
- [ ] 是否存在翻译腔？
- [ ] 句子是否明确 responsibility owner？

### 17.4 形式

- [ ] 每张图是否只回答一个问题？
- [ ] 公式是否只用于定义、关键边界和闭环？
- [ ] 列表是否真正并列？
- [ ] 表格是否用于比较而非长篇说明？
- [ ] 标题是否表达论证结构而非术语索引？

### 17.5 架构纪律

- [ ] Semantic owner 是否唯一或明确？
- [ ] Source of Truth 是否明确？
- [ ] Writer / Reader 权限是否明确？
- [ ] Version / Provenance 是否考虑？
- [ ] Authority boundary 是否明确？
- [ ] Invariant 是否真的不可违反？
- [ ] MVP 是否只是能力分阶段，而没有降低语义约束？

### 17.6 可维护性

- [ ] 新版本是否说明变化原因？
- [ ] 与上位 / 下位文档关系是否明确？
- [ ] OPEN 是否分类？
- [ ] 历史内容是否进入附录而非主叙事？
- [ ] 文档是否可以被未来新成员独立阅读，而无需了解全部讨论历史？

---

## 18. 推荐模板

下面是长期设计文档的通用骨架。实际文档应按内容裁剪，不机械复制。

```text
# <Document Title>

Metadata / Version / Status

## 1. 文档定位
- Purpose
- Scope
- Non-Goals
- Related Documents

## 2. 问题与设计约束
- Reality
- Design Forces
- Failure Modes

## 3. Architecture / Solution Overview
- Mental Model
- High-level Diagram
- Responsibility Table

## 4. Core Responsibilities / Models
- Responsibility A
- Responsibility B
- ...

## 5. Runtime / Dynamic View
- Canonical Flow A
- Canonical Flow B

## 6. Contracts / Boundaries
- Ownership
- Truth / Belief / State
- Version
- Consistency
- Authority

## 7. Key Decisions
- Alternatives
- Trade-offs

## 8. Risks / Open Questions / Handoff

Appendix A — Detailed Invariants
Appendix B — Validation Scenarios
Appendix C — References / Design History
```

模板的目标不是统一外观，而是保证主叙事完整。

---

## 19. 写作标杆

DeerMind 设计文档默认以 `DeerMind_Concept_Architecture_v0.7.md` 作为内部样例。

在外部工业文档中，主要参考 Amazon Builders’ Library 的写作纪律：

- 先解释现实问题；
- 从约束推导设计；
- 使用完整工程段落；
- 用真实案例解释抽象；
- 承认 trade-off；
- 控制标题和列表密度；
- 不把复杂性当作专业性的证明。

我们借鉴的是这种表达纪律，而不是复制其文章结构。

DeerMind 的目标风格可以概括为：

> **现代工程中文、问题驱动、论证完整、术语克制、边界清晰、形式化适度、长期可维护。**

---

## 20. 最终原则

一份优秀的 DeerMind 设计文档，读完之后应该让一个没有参与历史讨论的优秀工程师能够回答：

1. 系统到底在解决什么问题；
2. 为什么当前结构自然地从这些问题中产生；
3. 每个核心部分拥有什么责任；
4. 哪些边界不能越过；
5. 系统运行时怎样形成闭环；
6. 哪些选择存在 trade-off；
7. 哪些问题仍然开放；
8. 下一阶段应该继续解决什么。

如果读者只能“查到很多正确内容”，却无法复述设计为什么成立，那么文档仍然没有完成自己的任务。

最终应始终坚持：

\[
\boxed{
Clarity
>
Density
}
\]

\[
\boxed{
Reasoning
>
Terminology
}
\]

\[
\boxed{
ArchitectureNarrative
>
DiscussionHistory
}
\]

\[
\boxed{
SemanticPrecision
\neq
WritingComplexity
}
\]

设计可以复杂，文档不能混乱。  
严谨来自边界、证据和推理，而不是来自术语数量、公式数量或章节数量。
