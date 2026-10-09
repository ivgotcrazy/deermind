# DeerMind Development Roadmap v0.3

> **中文名称**：DeerMind 开发总路线图<br>
> **版本**：v0.3<br>
> **文档性质**：项目级全生命周期开发路线图 / Development Roadmap<br>
> **状态**：阶段基线<br>
> **上位基线**：`DeerMind_Product_Thesis_v1.0.md`、`DeerMind_Product_Constitution_v1.0.md`、`DeerMind_Concept_Architecture_v1.1.md`、四份 Space Design v1.1、`DeerMind_AI_Native_Architecture_Principles_v0.2.md`<br>
> **专项路线图**：`DeerMind_System_Design_Roadmap_v0.6.md`<br>
> **写作规范**：`DeerMind_Design_Document_Standard_v1.0.md`<br>
> **更新时间**：2026-10-09（G3 与当前状态同步；阶段顺序不变）<br>
> **版本说明**：v0.3 保留 v0.2 的全生命周期阶段、G0–G9 Evidence Gate、Reopen 机制以及“通用学习架构 + 小学首个 Product Context”的项目定位，不改变 Architecture Validation Build、MVP Definition、Product & Domain Foundation、MVP Engineering、Internal Alpha、Controlled Pilot、Production Candidate 与 Productionization 的总体顺序。本版本初次修订对齐当时 System Design Roadmap v0.5 的阶段执行语义；现行阶段路线图为 v0.6，执行顺序保持：System Design 内部采用 **MVCL → P0 / 横切机制语义闭合 → Integrated Pre-Validation Candidate → §3.2–§3.7 Focused Design Closure → §3.8 Cross-Cutting Coverage → Consolidated Architecture Spike → Evidence Review / Design Revision → Gate E / Gate F → System Design Baseline v1.0**；六个 Focused Design 是必须完成的设计责任，是否独立成文由复杂度决定。同时再次明确 Core System Design 只冻结 Product Context / Context Constitution 的通用接入与 enforcement contract，首个小学 Product Context 的 guardian authority、consent、儿童数据、家长可见性、学校现实与具体 retention 规则仍由后续 MVP Definition / Product & Domain Foundation 阶段实例化。

---

## 1. 文档定位：从“系统应该是什么”走到“可以承担生产责任”

DeerMind 已经完成 Concept Architecture、Learning / Evaluation / Interaction / Evolution 四份 Space Design，并建立 AI-Native Architecture Principles。当前项目已经能够较清晰地回答：系统需要维护哪些语义责任、哪些认识可以开放、哪些权力必须受控、系统如何允许自己的认识被现实证据修正。

但从架构基线到第一个正式上线版本，中间并不是简单的“System Design → 写代码 → 发布”。DeerMind Core 是面向真实学习过程的一般 AI 原生学习系统，而第一个 Product Context 是小学学习。项目因此必须同时解决通用架构可实现性、产品价值、领域初始化、AI 行为质量与长期可观测性，并在进入首发产品阶段后进一步落实未成年人保护、guardian authority、学校现实、安全隐私和生产运营责任。市场进入边界不能反向成为 Core Architecture boundary；任何一层没有建立最低可信度，都不应该通过扩大用户规模来替代验证。

因此本文档把项目最终目标定义为：

> **交付 DeerMind 第一个能够面向明确目标用户提供完整核心价值，并能够对真实用户、真实儿童数据、AI 行为和持续运行承担生产责任的 Production Release。**

“Production Release”不等于系统可以启动，也不等于 MVP 功能开发完成。它至少意味着：目标用户与核心价值明确；真实学习闭环能够完成；AI 行为达到已定义的最低质量门槛；儿童数据、安全与隐私边界可执行；系统能够被监控、停止、降级、回滚和恢复；上线前已获得有限真实用户证据，并且已知重大风险具有明确处置路径。

### 1.1 Development Roadmap 与 System Design Roadmap 的关系

`DeerMind_System_Design_Roadmap_v0.6.md` 只负责项目生命周期中的 **System Design 阶段**。它回答如何把已经冻结的 Architecture Semantics 转化为 Architecture-Executable Specification，并进一步规定 System Design 内部的 Work Package、Phase、Focused Design Closure、横切覆盖、Consolidated Architecture Spike、Evidence Review 与 Gate E / Gate F。

本文档位于更高一层，覆盖：

```text
Architecture Baseline
        ↓
System Design
        ↓
Architecture Validation Build
        ↓
MVP Definition
        ↓
Product & Domain Foundation
        ↓
MVP Engineering
        ↓
Internal Alpha & Evaluation
        ↓
Controlled Pilot
        ↓
Production Candidate
        ↓
Productionization & Launch
        ↓
Post-Launch Stabilization
```

System Design Roadmap 是本路线图的专项子路线，不被本文档替代。Development Roadmap 只定义“System Design 完成后项目可以进入什么阶段”，System Design Roadmap 则定义“System Design 本身如何形成、验证和冻结”。

两份 Roadmap 共同保持一个重要边界：

> **Core System Design 冻结 Product Context / Context Constitution 的接入与 enforcement 能力；具体小学 Product Context 的 guardian authority、consent、child-data、家长可见性、学校现实与 retention 规则，由后续 MVP Definition / Product & Domain Foundation 阶段实例化。**

后续 Product、Pilot、Production 等阶段如果复杂度足够，也可以形成各自的专项计划。

### 1.2 Roadmap 不是 Schedule

本文档冻结的是阶段、依赖、产物、证据门槛和 Reopen Condition，而不是具体月份、Sprint 数量或发布日期。

当前阶段仍存在大量必须通过 Architecture Validation 和真实用户 Pilot 才能得到答案的不确定性。现在给出精确日期会把尚未验证的假设伪装成确定计划。因此：

> **Roadmap 决定下一步为什么可以开始；Delivery Plan 才决定下一步何时完成。**

真正的交付排期应在 Architecture Validation Build 与 MVP Definition 后，基于已经知道的产品范围、工程复杂度、团队配置和外部约束形成。

---

## 2. 总体开发模型：每一阶段都用证据换取下一阶段承诺

DeerMind 不采用单向的 `Design → Coding → Testing → Launch` 模型。项目本身应遵循与 DeerMind Evolution 一致的证据驱动方式：先形成当前最好判断，再通过最低成本但足够有力的验证取得证据，然后决定是否扩大下一阶段投入。

统一开发循环是：

\[
Design
\rightarrow
Validation
\rightarrow
Evidence
\rightarrow
Decision
\rightarrow
NextCommitment
\]

这里的 `NextCommitment` 不仅是代码提交，而是项目对更高成本、更大用户暴露和更高运营责任的承诺。

### 2.1 四类证据不能互相替代

整个 Development Roadmap 至少使用四种不同证据：

| 证据类型 | 主要回答的问题 | 典型方式 |
|---|---|---|
| Conceptual Evidence | 理论和语义边界是否自洽 | 逻辑推导、反例、Architecture Review、Failure Analysis |
| Engineering Evidence | 架构机制是否可实现、可组合 | Architecture Spike、Reference Build、Benchmark、Failure Injection |
| Empirical Evidence | 教育与产品假设在真实用户中是否成立 | Controlled Pilot、真实学习行为、延迟评估、访谈、观察 |
| Operational Evidence | 系统是否可以承担生产运行责任 | Load / Resilience / Security Test、Monitoring、Rollback Drill、Incident Readiness |

代码不能证明教育理论成立，Pilot 也不能替代架构一致性；四种证据对应不同问题。

### 2.2 Gate 是证据门槛，不是日历节点

每个阶段都有 Exit Gate。Gate 的作用不是宣布“阶段结束了”，而是回答：

> **我们现在是否拥有足够证据，使下一阶段更高成本、更高风险的投入成为合理决定？**

如果答案是否定的，正确行为是停留、修改或回到上游阶段，而不是通过赶进度把未知带到生产环境。

### 2.3 Reopen 是正常机制，不是设计失败

任何阶段的新证据都可能重新打开前一阶段的决定。例如 Architecture Validation Build 可能证明某个 System Design 机制组合后不可行；Controlled Pilot 可能证明 KC 粒度、Observation semantics 或 Interaction Policy 在真实学习中不成立。

因此：

> **Frozen 表示“没有新证据时按当前版本执行”，不表示“以后禁止被现实否定”。**

Reopen 必须发生在对应责任层级。产品问题不应通过偷偷修改 Concept Architecture 解决；架构问题也不应通过 UX workaround 掩盖。

---

## 3. Phase 0–2：从架构基线到经过组合验证的可运行系统

前三个阶段解决的是“DeerMind 应该是什么系统”“如何实现这个系统”以及“这些机制组合在一起是否真的成立”。它们仍然不是产品市场验证。

### 3.1 Phase 0 — Architecture Baseline

**目标**：冻结 DeerMind 当前最合理的顶层语义、认识论、责任边界和 AI-native execution doctrine，使后续实现有明确的不可绕过约束。

当前主要产物包括：

- `DeerMind_Concept_Architecture_v1.1.md`；
- `DeerMind_Learning_Space_Design_v1.1.md`；
- `DeerMind_Evaluation_Space_Design_v1.1.md`；
- `DeerMind_Interaction_Space_Design_v1.1.md`；
- `DeerMind_Evolution_Space_Design_v1.1.md`；
- `DeerMind_AI_Native_Architecture_Principles_v0.2.md`；
- `DeerMind_Design_Document_Standard_v1.0.md`。

**Architecture Baseline Gate**：四个 Space 的 semantic ownership、全局 Event contract、Product Constitution、Governance、Evolution Contract 和 AI-native Invariants 之间不存在已知一级矛盾；后续问题已经可以进入 System Design 而不需要重新发明顶层语义责任。 Target Definition / Binding / Assessment、Context Authority、Authority Directive 与 typed invalidation 已完成跨文档 Freeze Gate，不再留给实现阶段重新决定 owner。

**Reopen Condition**：后续 System Design、Architecture Validation 或真实用户证据证明现有 Architecture Invariant 无法表达重要现实、产生不可接受自相矛盾，或必须依赖长期违规 workaround 才能实现。

当前状态：**已完成并冻结，作为后续阶段的上位基线。**

### 3.2 Phase 1 — System Design

**目标**：把 Architecture Semantics 转化为 Architecture-Executable Specification，使工程实现者不需要在编码阶段重新决定 Event、Observation、Evidence、Belief、Policy、Candidate、Commit、Version、Replay、Authority 等核心语义如何工作。

该阶段由 `DeerMind_System_Design_Roadmap_v0.6.md` 专门规划。它不是“一份 System Design 文档写完就结束”，而是一个包含总体设计、六个核心 Focused Work Package、横切覆盖与统一架构验证的阶段。当前正式执行顺序为：

```text
MVCL Design
    ↓
P0 Runtime Mechanism + Cross-Cutting Semantic Closure
    ↓
Integrated Pre-Validation System Design Candidate (v0.x)
    ↓
§3.2–§3.7 Focused Design Closure
    +
§3.8 Cross-Cutting Coverage
    ↓
Consolidated Architecture Spike
    ↓
Architecture Evidence Review
    ↓
Design Revision / ADR / Architecture Reopen if required
    ↓
Gate E
    ↓
Gate F
    ↓
System Design Baseline v1.0
```

其中六个 Focused Work Package 是 System Design **必须完成的设计责任**。`Complexity Must Earn Its Keep` 只决定专项是否值得独立成文，不决定该责任是否可以跳过。若独立成文，则 Pre-Validation 阶段使用 `v0.x`，吸收验证证据并满足冻结条件后再形成相应 `v1.0`。

§3.8 的 Privacy / Data Authority、Observability / Audit、Security / Trust Boundary、Lifecycle / Recovery 属于横切责任，默认由总体设计和各 Focused Design 共同承载，不新增第七个对称 Runtime。Core System Design 必须冻结 Product Context integration contract 与 Observability Minimum Contract，但不实例化首个小学 Product Context 的具体 guardian / consent / child-data 规则。

核心产物包括：

- `DeerMind_System_Design_v0.x.md` → `DeerMind_System_Design_v1.0.md`；
- 必要的 Focused System Design `v0.x` → `v1.0`；
- Architecture Assumption / System Invariant Registry；
- ADR；
- Consolidated Architecture Spike 代码与 Validation Evidence；
- Architecture Validation Report / Evidence Review 结果。

具体独立文档数量由设计复杂度决定，不以文档数量作为完成标准；**Work Package Closure、Document Packaging 与 Capability Staging 是三个不同维度。**

**System Design Exit Gate**：满足 System Design Roadmap Gate F。至少意味着：总体 System Design 与必要 Focused Design 已达到 Architecture-Executable Specification；六个核心专项责任和横切责任不存在需要实现者临时发明的核心语义；Consolidated Architecture Spike 已对高风险 Architecture Assumption 提供真实工程证据；Evidence 已被吸收到设计、ADR 或受治理的 Reopen；Gate E 与 Gate F 均通过。此时才能进入 Architecture Validation Build。

**Reopen Condition**：Architecture Validation Build 证明 Consolidated Spike 中成立的局部假设在真实组合运行中失败，或后续产品 / 真实用户场景暴露 System Design 无法表达的核心 runtime requirement。若问题来自更上层 semantic ownership / invariant，则继续回到 Space Design / Concept Architecture，而不是在实现中长期打补丁。

当前状态：**Phase 1 System Design 已完成；Gate E/F 与项目 G1 满足，准入 Phase 2 Architecture Validation Build。** 原 Spike 的 A2 否定、E1/X5 未决保留，正式处置及当前范围见 §8.2。

### 3.3 Phase 2 — Architecture Validation Build

System Design v1.0 完成后不直接进入产品 MVP。首先构建一个极薄但真实端到端运行的 **Architecture Validation Build**。

它的目标不是证明产品有人喜欢，而是验证：

> **前面分别设计的机制在一个真实 AI-native learning system 中组合运行时仍然成立。**

Validation Build 可以只有一个 learner、一个数学 Task Family、少量 KC、一个 Solve 场景、极少 Action 类型、简化 Policy 和非常粗糙的界面，但必须真实经过：

```text
Event History
→ Context Package
→ Reasoning Protocol
→ Candidate
→ Validation / Commit
→ Observation / Decision / ActionOccurrence
→ Evidence / Learner Belief
→ Dependency / Invalidation
→ Historical Reconstruction
```

它重点验证 Consolidated Architecture Spike 仍无法充分证明的 composition / operability risk，例如：Context 与 Policy 组合后是否过重、reasoning latency 是否破坏交互、dependency fan-out 是否失控、current view 是否长期 stale、Version Context 是否难以操作、Exposure Lineage 是否真实可维护、Reasoning Execution Record 是否造成不可接受复杂度。

**主要产物**：Reference implementation、Architecture Validation Report、必要的 ADR / design revision、已知 capability staging 清单。

**Architecture Validation Gate** 至少要求：

- 一条完整纵向闭环在真实代码中按设计运行；
- Architecture Invariant 没有通过隐藏 bypass 才得以“实现”；
- 核心失败、stale、correction 和 replay 路径至少被实际触发验证；
- P0 组合风险不存在已知阻断，或已有明确可接受设计修订；
- latency、complexity、observability、recompute 与 reasoning behavior 已获得第一批实际测量；
- 团队已经知道当前架构真实能提供什么能力、哪些能力成本过高或必须 staged。

**Reopen Condition**：发现组合层 architecture failure。问题应回到 System Design；若证据说明责任划分本身错误，则继续上溯到 Space Design / Concept Architecture，而不是在 Validation Build 中长期打补丁。

通过该 Gate 后，项目第一次具备在真实能力约束下定义产品 MVP 的条件。

---

## 4. Phase 3–4：把系统能力收敛为第一个真实产品

Architecture Validation 解决“机器能不能按设计工作”，但没有回答“第一版产品为谁解决什么问题”。产品范围应在了解系统真实能力、成本与限制后再正式冻结。

### 4.1 Phase 3 — MVP Definition

**目标**：定义 DeerMind 第一个需要被真实用户验证的完整产品价值闭环，而不是从架构能力列表中随意挑功能。

MVP Definition 至少需要回答：

- 首批目标 learner / family 是谁；
- 学科、年级和内容范围是什么；
- 第一核心学习场景是什么；
- 哪类 Task 被支持；
- learner 为什么主动进入 DeerMind；
- parent 为什么愿意信任并持续使用；
- 第一版必须具备哪些能力，哪些明确不做；
- 交互入口与主要输入方式是什么；
- 需要采集哪些数据才能形成最低有效 learner evidence；
- 首个 Product Context（小学）如何把 guardian / school reality、consent 与 authority scope 映射到冻结 Core，而不改写 Core semantic ownership；
- 产品价值如何表达，而不退化为“更快给答案”；
- 成功、失败与需要停止 Pilot 的条件是什么。

这里需要特别保持一个边界：MVP Definition 可以在已有 architecture capability 中选择和 staged 能力，但不能为了产品方便关闭 Architecture Invariant。

**主要产物**可以包括 MVP Scope / PRD、Target User & Scenario、Core Value Proposition、Product Success Criteria、Pilot Hypothesis Draft、Capability Matrix。文档名称可以后续统一，不在本 Roadmap 提前强制格式。

**MVP Definition Gate**：目标用户、核心场景、价值主张、产品边界、最低成功指标和关键验证假设已经明确；产品团队、领域设计与工程团队可以基于同一范围继续工作，不需要边开发边重新决定“第一个产品到底是什么”。

**Reopen Condition**：Product / Domain Foundation 发现核心使用路径不可实施，或 Pilot 证据证明目标用户、场景、价值主张不成立。

### 4.2 Phase 4 — Product & Domain Foundation

这一阶段除 UX、领域内容和首发 Task / Target bootstrap 外，还要形成首个 Product Context 所需的 Context Constitution / authority mapping：谁可以提出 Request、Constraint、Obligation 或 Authority Directive，其 scope、终止条件和与 learner agency 的边界如何执行。

DeerMind 与普通 SaaS 的显著区别是：软件开发完成并不意味着系统已经拥有可运行的“学习世界”。第一版还必须初始化 Learning Space，并把架构能力转换成孩子和家长真正能使用的产品交互。

这一阶段包含两条并行但必须收敛的工作流。

**产品基础**负责：learner journey、parent journey、onboarding、Solve interaction、输入方式、AI intervention presentation、Hint / AskForExplanation UX、uncertainty 与 correction 表达、report / trust interface、关键 failure recovery。

**领域基础**负责：首版 curriculum scope、Task Families / Task Instances、Solution Strategies、初始 KC model、Task–Solution–KC grounding、初始 validation / benchmark set，以及 canonical domain semantics 的最小 governance 流程。

首版已将基础领域演化纳入必要能力。Phase 4 在领域与产品基础中共同明确管理员发起或选择处理、AI 辅助评估与候选、有限验证、单人审核发布和生效后检查，聚焦 KC、Task Family、Solution 与教材映射的必要新增和局部修正。初始建模保留建设入口，复用检查与发布；其他既定维护需求不因演化聚焦而删除。范围与责任见[MVP Definition §7](../mvp/DeerMind_MVP_Definition_v0.1.md#7-模型管理与运行可观察性)，具体行为和后续详细设计责任见[需求规格 §7.1](../mvp/DeerMind_MVP_Requirements_and_Acceptance_v0.1.md#71-基础领域演化的最小行为合同)。

AI 可以大量辅助 Task / Solution / KC 的拆分、评估和候选生成，但首版 canonical domain model 仍必须受 Learning Space 与 Governance 约束，不能把“模型能生成内容”误当成“领域模型已经可靠”。

**主要产物**：核心 UX / Product Flow、Domain Bootstrap Package、初始 benchmark / evaluation set、内容与领域质量审查规则、MVP 数据与 consent flow 设计。

**Product & Domain Foundation Gate**：核心用户旅程和第一版 canonical domain scope 已经足够稳定，工程团队可以开发而不需要临时发明产品交互与领域语义；输入输出和必要数据采集在产品体验上可行；不存在显著违反认知所有权、attention ownership 或 child-data 原则的路径。

**Reopen Condition**：工程实现证明交互路径与 architecture mechanism 严重冲突，或 Internal Alpha / Pilot 表明内容粒度、Task/KC grounding、用户理解和数据可得性不能支撑产品假设。

---

## 5. Phase 5–6：构建 MVP，并证明它有资格进入真实儿童 Pilot

MVP Engineering 的目标不是把所有 DeerMind 能力实现，而是实现 Phase 3 冻结的第一产品价值闭环。Implementation Capability 可以 staged，但 Architecture Invariant、Child Safety Boundary 与可审计性不能 staged 掉。

### 5.1 Phase 5 — MVP Engineering

**目标**：交付一个真正可由目标用户完整使用的产品版本，并把 Architecture Validation Build 中的参考机制提升为可维护的软件系统。

工作至少覆盖三类实现：

**AI / Cognitive Runtime**：Reasoning Protocol execution、Context Assembly、Model Adapter / Routing、Candidate / Validation、Execution Record、Tool / Authority boundary、failure semantics、最小 reasoning benchmark 与 regression harness。

**Core Platform**：identity / account、session / episode、event history、semantic state、version / dependency、async jobs、API、authorization、audit、configuration、observability，以及所需客户端能力。

**Product Capability**：MVP user journey、学习输入、Action presentation、correction、parent-facing trust / report experience、consent / privacy experience、domain content delivery。

MVP 可以保留大量 staged capability，例如 Evolution 主要人工发起、Governance UI 很轻、Replay 只保留有限窗口、Policy Action 类型有限、部署形态简单。staged 的是能力成熟度，不是语义纪律。

对当前 MVP，Evolution 的最低交付为人工主导、AI 辅助的基础领域演化真实流程。Phase 5 完成记录与接口、LLM 任务、有限验证、授权提交、生效及影响恢复的详细设计与实现，并评估实际新增工作量；Phase 6 按[验证方案 §2.1](../mvp/DeerMind_MVP_Validation_Plan_v0.1.md#21-基础领域演化的有限验收)统一验收。持续自动发现、通用实验编排、跨模型自动修订和大规模多版本平台后置，不另开 Evolution Spike。基础扩展须有成功与后续使用证据，非成功结果同样可查；不能以空流程、模拟结论或版本号变化替代实际能力，也不要求每个候选成功后才能结束本阶段。

**MVP Feature Complete Gate**：Phase 3 定义的 MVP 核心价值链端到端可用；核心 AI / data / architecture path 使用真实实现而不是测试旁路；已知缺失能力明确记录；可以进入系统化质量验证，而不再进行大范围功能定义。

**Reopen Condition**：实现发现某项 MVP 能力只有违反 System Design 才能完成，或者成本 / latency / complexity 远超 Architecture Validation 结论并改变产品可行性。

### 5.2 Phase 6 — Internal Alpha & Evaluation

`Feature Complete` 不等于 `Pilot Ready`。在真实孩子使用前，DeerMind 必须先在内部和受控测试环境中证明：软件、AI 和产品交互没有已知的基础性失控风险。

Internal Alpha 至少覆盖三层验证。

**软件正确性**：核心 Event / State / Version / Dependency / Commit 路径、数据一致性、迁移、failure recovery、客户端错误处理。

**AI 行为质量**：Protocol compliance、grounding、Unmapped / UNKNOWN、authority escape、prompt injection、model failure、decision consistency、reasoning variability、unsafe output、stale-context rejection。

**产品可用性**：核心 journey 是否可理解、响应时延是否可接受、提示和不干预是否被正确理解、孩子能否纠正系统、parent-facing information 是否产生误导。

这一阶段还应形成第一版 AI / System Evaluation Infrastructure，包括 benchmark、regression set、quality metrics、observability dashboard 和问题分级机制。

**Pilot Readiness Gate**：

- 没有已知会导致儿童受到明显不当交互、数据越权或系统失控的 P0 问题；
- 核心软件路径可稳定完成并可诊断；
- AI 关键行为达到预先定义的最低 benchmark / policy compliance 门槛；
- 重要 failure 可以降级、停止或转为 UNKNOWN，而不是被静默掩盖；
- Pilot 期间需要的日志、evidence、consent、人工观察和停止机制已经准备好；
- Pilot 的范围足够小，风险与未知能够被人工监督。

**Reopen Condition**：Internal Alpha 暴露 architecture-level failure、产品核心 journey 不可理解，或 AI behavior 无法在当前 Protocol / validation architecture 下达到最低安全质量。

通过该 Gate 后，MVP 才第一次有资格进入真实用户验证。

---

## 6. Phase 7–9：让现实审查产品，再承担 Production 责任

从 Controlled Pilot 开始，项目面对的是前面所有理论、设计和内部测试都无法替代的现实证据。此后每一次阶段推进都意味着更大的真实用户暴露和运营责任。

### 6.1 Phase 7 — Controlled Pilot

Controlled Pilot 不是“小流量正式上线”，而是**实验性真实运行**。首轮可以只有极少 learner、有限数学内容和有限周期，并保留较强人工观察。

Pilot 要验证的不是系统是否能启动，而是关键教育与产品假设是否真实成立，包括：

- learner 的真实过程是否足够可观察；
- Observation 在真实学习中是否有可接受可靠性；
- Assistance Exposure 是否足以解释 Evidence contamination；
- Learner Belief 是否表现出校准价值，而不是漂亮但无效的模型状态；
- Task / KC granularity 是否能被真实行为区分；
- learner 是否愿意提供系统需要的过程信号；
- Active Assessment 是否造成不可接受负担；
- Interaction Policy 是否过度干预或过早替代认知工作；
- parent 是否理解并信任 DeerMind 的独立教育判断；
- removable scaffold / fade-out 是否至少在早期迹象上成立；
- 哪些此前未知的 failure mode 会在家庭真实环境中出现。

**主要产物**：Pilot Plan、Pilot Dataset / Evidence、Pilot Findings、Product / Architecture / Domain Change Proposals，以及需要重新验证的假设清单。

**Pilot Exit Gate** 不是“用户反馈不错”，而是至少满足：核心产品价值出现可信正向证据；没有不可接受的儿童安全或系统性负面行为；主要失败模式已知且可治理；可观测性足以支持后续判断；现有目标用户 / 场景仍值得继续投入；需要修改的架构、领域和产品问题已经显式进入 Revision Plan。

如果关键假设失败，正确结果可以是回到 MVP Definition、Product Foundation、System Design，甚至更上层架构，而不是宣布 Pilot “成功”。

### 6.2 Phase 8 — Production Candidate

Pilot 后不能直接上线。真实证据通常会触发产品、Policy、Domain Model、Protocol、Evaluation 和运行机制的修订。因此需要一个独立的 **Production Candidate** 阶段，把 Pilot 学到的东西真正吸收进系统。

该阶段主要完成：

```text
Pilot Evidence
→ Change Assessment
→ Architecture / Product / Domain Revision
→ Regression / Revalidation
→ Release Candidate
```

如果 Pilot 触发 System Design v1.1、Protocol 新版本、KC / Task model 更新或重要 UX 变化，应完成相应版本化、migration / reinterpretation 与 regression，而不是在 Productionization 阶段继续改变核心产品行为。

**Release Candidate Gate**：目标产品 scope 已基本稳定；Pilot 阻断问题已关闭或明确不进入首版；核心 architecture / AI / product regression 全部通过；domain 与 protocol 版本已确定；Productionization 不再需要大范围修改产品语义和用户价值闭环。

**Reopen Condition**：修订后 regression 失败、Pilot 结论无法被修订版本保持，或 Productionization 发现必须改变核心产品语义才能达到运行要求。

### 6.3 Phase 9 — Productionization & Launch

Productionization 不是 MVP 开发末尾的一份 checklist，而是把“可用产品”转换成“可承担持续运行责任的生产系统”。

至少包含三类责任。

**系统运行责任**：部署与 release pipeline、capacity / scaling、backup、disaster recovery、migration、monitoring、alerting、tracing、incident response、feature flag、rollback、data integrity、operational ownership。

**AI 运行责任**：model outage / fallback、protocol rollback、semantic version rollback、reasoning drift、quality monitoring、cost anomaly、provider dependency、unsafe behavior containment、AI-specific incident classification。

**儿童产品责任**：consent、privacy、retention / deletion、access control、purpose limitation、content safety、abuse / misuse、human escalation、audit、地区上线所需的合规与运营流程。

具体合规要求取决于首发地区、产品形态和数据路径，应在 MVP Definition 后根据真实上线范围进行专项确认；本文档不提前假设某个司法辖区的最终要求。

**Launch Readiness Gate** 至少从五个维度审查：

| Gate 维度 | 必须回答的问题 |
|---|---|
| Architecture | Production implementation 是否仍遵守 Architecture Invariants，是否存在隐藏 bypass |
| Product | 目标用户是否能够完整获得第一版承诺价值，关键 UX 是否稳定 |
| AI Quality | reasoning / grounding / decision / safety 是否达到上线门槛，模型失败是否可控 |
| Child Safety & Privacy | 儿童数据、consent、retention、authority、安全处置是否达到首发范围要求 |
| Operations | 故障能否被发现、停止、降级、回滚、恢复，并具有明确 on-call / incident ownership |

只有五类 Gate 同时通过，才进入 **V1 Production Release**。

### 6.4 Post-Launch Stabilization

第一个正式 Release 不是项目终点，而是 DeerMind 第一次进入持续真实运行。上线初期应设置明确 Stabilization window，优先观察 reasoning drift、unexpected learner behavior、false belief、policy failure、latency、cost、incident、parent feedback 与数据质量。

生产数据开始进入 Evolution，但不应因为“系统可以演化”而绕过正式 change / validation / governance path。首版上线后的第一目标是建立可控运行基线，而不是立即扩大增长。

当 Production behavior 稳定、关键指标具有可解释趋势、P0/P1 incident rate 与 AI quality 在目标范围内，并且 Evolution / Release loop 实际可运行时，项目才正式从“首版交付”进入长期 Evidence-Driven Evolution。

---

## 7. 跨阶段 Gate、Reopen 与产物关系

### 7.1 项目级 Gate 总览

| Gate | 允许进入的下一阶段 | 核心证据 |
|---|---|---|
| G0 Architecture Baseline | System Design | Conceptual consistency / semantic closure |
| G1 System Design Exit | Architecture Validation Build | Architecture-Executable Specification + Focused Design Closure + Consolidated Architecture Spike evidence |
| G2 Architecture Validation | MVP Definition | End-to-end engineering / composition evidence |
| G3 MVP Definition | Product & Domain Foundation | Product hypothesis / scope clarity |
| G4 Product & Domain Foundation | MVP Engineering | Implementable UX + canonical domain bootstrap |
| G5 MVP Feature Complete | Internal Alpha | End-to-end product implementation |
| G6 Pilot Readiness | Controlled Pilot | Software / AI / safety internal evidence |
| G7 Pilot Exit | Production Candidate | Real-user empirical evidence |
| G8 Release Candidate | Productionization | Revised product + full regression |
| G9 Launch Readiness | V1 Production Release | Operational / AI / privacy / safety readiness |

任何 Gate 都不允许用“开发过程中再解决”代替未知。可以 staged 的能力必须证明其缺失不会破坏 Architecture Invariant、产品核心价值或当前阶段安全边界。

### 7.2 Reopen 路径必须指向真正的问题来源

项目默认允许以下回流：

```text
Architecture Validation Failure
    → System Design / Space Design / Concept Architecture

Product Foundation Failure
    → MVP Definition / System Design

Internal Alpha Failure
    → MVP Engineering / Product Foundation / System Design

Pilot Evidence Failure
    → Product Definition / Domain Model / Policy / Evaluation / System Design

Production Readiness Failure
    → Production Candidate / Engineering / System Design
```

如果现实证据只是否定某个 Implementation Capability，不应轻易重新打开 Architecture Invariant；反之，如果只能靠不断特殊处理才能维持上位设计，也不能因为文档已经“冻结”而拒绝 architecture reopen。

### 7.3 文档与软件产物的角色不同

整个生命周期大致会形成四类正式产物：

- **Architecture / System Design**：说明系统为什么这样构成、关键机制怎样工作；
- **ADR / Validation Report / Pilot Report**：记录关键决定和支持它的证据；
- **Product / Domain Specification**：定义目标用户价值、用户旅程、内容与领域范围；
- **Reference / MVP / Production Software**：验证并承载已经被确认的能力。

代码不是文档的替代品，文档也不是运行证据。重要项目结论必须能够追溯到它所依赖的设计与证据。

---

## 8. 执行纪律与当前项目位置

### 8.1 项目级执行纪律

1. **先证明下一阶段值得做，再扩大投入。** Gate 是投资与风险扩大的前提。
2. **Architecture Invariant 与 Implementation Capability 分离。** 能力可以 staged，核心边界不能为了赶版本临时关闭。
3. **理论、代码和真实用户证据各自回答不同问题。** 不用 Prototype 证明教育理论，也不用用户反馈替代架构纪律。
4. **先 Validation Build，后 MVP Definition。** 第一产品范围建立在已验证的真实系统能力上，而不是未经验证的工程假设上。
5. **MVP 与 Production Release 分离。** 能给少量用户用，不等于能够承担公开生产责任。
6. **Controlled Pilot 是实验，不是小流量增长。** 首要目标是验证教育、可观测性和产品假设。
7. **Pilot 后必须形成 Production Candidate。** 真实证据必须被吸收和 regression 后才能 Productionization。
8. **Child Safety / Privacy / Authority 从设计期开始存在，但 Core 与 Product Context 分层。** Core System Design 冻结可执行的 Authority / Data Authority / Privacy / Safety 接入与 enforcement；首个小学场景的 guardian / consent / child-data 具体规则由后续 Product Context 实例化，不能作为上线前附加检查，也不能反向改写 Core。
9. **Reopen 是受治理的正常机制。** 新证据有权挑战旧判断，但必须回到正确责任层级。
10. **Roadmap 不伪装成 Schedule。** 在证据不足时不承诺虚假的确定日期。

### 8.2 当前项目位置

**2026-10-09，项目 G3 PASS，MVP Definition 已冻结，当前进入 Development Phase 4 Product & Domain Foundation。** [MVP Definition §11](../mvp/DeerMind_MVP_Definition_v0.1.md#11-g3-评审与阶段完成条件)记录逐项评审与重开条件；[需求与验收规格](../mvp/DeerMind_MVP_Requirements_and_Acceptance_v0.1.md)和[验证方案](../mvp/DeerMind_MVP_Validation_Plan_v0.1.md)共同构成交付。该结论确认产品范围与验证假设清楚，不表示 MVP 已实现、质量达标或获准 Pilot。

Phase 0 Architecture Baseline、System Design 内部 Phase 6 和项目 G1 保持原结论。2026-10-08 Build 退出的 G2 PASS 是此前进入 Definition 的依据：真实机制组合与最低纠错路径已有局部证据，语义质量和完整维护仍待工程验收。原 R2 的 14/24、EVAL-02/04 未满足及原条件 HOLD，R3/R4 失败全部保留。依据与限制见[Build Validation Report §9](../system-design/build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md#9-build退出评审与能力分期决定)。

现行系统设计为总体及六项专项 v1.0。A2 原否定、E1/X5 原未决和旧 9/17 保留；当时G1准入依据撤回错误保证、明确能力分期和完整合同，详见[Phase 6 证据评审](../system-design/DeerMind_System_Design_Evidence_Review_v1.0.md)。该文件同时给出下一阶段工作和停止条件；[统一 Spike Validation Report](../system-design/spike/DeerMind_Architecture_Validation_Report_v0.1.md)继续保存原实验结果。

Phase 4 下一步交付三类角色的核心 UX/流程、Domain Bootstrap Package、初始评测集、内容与领域质量审查规则，以及数据、authority mapping 和 consent flow。优先设计纲内新题从帮助、入库、评价到 Evolution 评估、候选验证和单人审核发布的组合路径；具体教材允许随后补齐，但实际课程大纲与初始领域内容不能省略后通过 G4。G4 后才进入 MVP Engineering，之后完成 Internal Alpha 与 G6 Pilot Readiness。Build 的 R5 未启动，仍是后续工程候选输入；STG-01–04 的质量和维护责任由 MVP 三份文档承接，不保证后续必定达标。两级路线图的阶段顺序、核心责任和后续质量 Gate 不变。

当前 D09 已明确采用基础领域演化能力，作为系统维护和扩展领域模型的必要组成。[Phase 4 产品与领域基础设计草案](../mvp/foundation/DeerMind_MVP_Product_and_Domain_Foundation_v0.1.md)已展开纲内新题的当下帮助、题目保存、适用评价、后台演化与发布后检查；三端完整 UX、实际领域包、数据授权及参考评测仍需完成。G4 尚未评审，工程详细设计、实现和运行验证按 Phase 5–6 推进；G3 准入继续成立，不回到已关闭的 Spike 或 Build 追加实验。

### 8.3 当前明确不提前冻结的事项

Definition 已确定首个六年级数学场景、校内与校外两空间完全隔离、五个学习场景、学生和家长独立 Android APK 及管理员电脑 Web；首轮种子观察为一名孩子、四周、每天全部使用最多 30 分钟。这些决定以 MVP Definition 为准，不再列作产品形态或首轮周期待决。以下内容仍需对应阶段的约束与证据：

- 实际教材、两空间大纲、首批领域内容及具体任务覆盖；
- 三端详细交互、告知与授权数据流程、完整实机环境；
- PostgreSQL / MySQL / 图数据库 / 向量数据库等具体技术；
- Kafka / RabbitMQ / workflow engine；
- 单体 / 微服务 / Kubernetes；
- Go / Python / Java 的最终职责边界；
- 具体 LLM 供应商、模型与 Agent framework；
- 首轮 Pilot 的实际日期、问题纳入和参考材料，以及后续扩大用户或地域的安排；
- 正式 Production Release 日期；
- 商业增长与规模化策略。

这些决定应在本 Roadmap 对应阶段由真实约束和证据逐步收敛，而不是反过来改变上位架构。

---

## 附录 A：DeerMind 从架构到生产上线的全生命周期视图

```text
Phase 0  Architecture Baseline
    Concept Architecture v1.1
    + Four Space Design v1.1
    + AI-Native Principles v0.2
        │
        ▼ G0
Phase 1  System Design
    MVCL
    → P0 / Cross-Cutting Semantic Closure
    → Integrated Pre-Validation System Design v0.x
    → Focused Design Closure §3.2–§3.7
    + Cross-Cutting Coverage §3.8
    → Consolidated Architecture Spike
    → Evidence Review / Design Revision
    → Gate E + Gate F
    → System Design Baseline v1.0
        │
        ▼ G1
Phase 2  Architecture Validation Build
    Thin End-to-End Reference System
        │
        ▼ G2
Phase 3  MVP Definition
    Target User / Scenario / Value / Scope / Success Criteria
    + First Product Context Definition
        │
        ▼ G3
Phase 4  Product & Domain Foundation
    UX / Journey
    + Context Constitution / Guardian / Consent Mapping
    + Task / Solution / KC Bootstrap
        │
        ▼ G4
Phase 5  MVP Engineering
    Product + Core Platform + AI Runtime
        │
        ▼ G5
Phase 6  Internal Alpha & Evaluation
    Software / AI / Product / Safety Validation
        │
        ▼ G6
Phase 7  Controlled Pilot
    Real Learner / Family Evidence
        │
        ▼ G7
Phase 8  Production Candidate
    Evidence-driven Revision + Regression + RC
        │
        ▼ G8
Phase 9  Productionization & Launch
    Operations + AI Reliability + Child Safety / Privacy
        │
        ▼ G9
    V1 Production Release
        │
        ▼
Post-Launch Stabilization
        │
        ▼
Evidence-Driven Evolution
```

## 附录 B：阶段边界的三个关键非等价关系

为避免后续项目管理重新混淆，以下三个关系作为本 Roadmap 的长期边界：

\[
ArchitectureValidationBuild \neq MVP
\]

Architecture Validation Build 验证架构组合是否成立；MVP 验证第一个真实用户价值闭环。

\[
MVPFeatureComplete \neq PilotReady
\]

MVP 功能做完以后，仍然需要 Internal Alpha、AI quality、failure / safety 与 Pilot monitoring 准备。

\[
ControlledPilot \neq ProductionLaunch
\]

Pilot 是受控真实实验；Production Launch 意味着系统开始承担持续的用户、数据、安全和运营责任。

这三个边界不因项目进度压力而改变。
