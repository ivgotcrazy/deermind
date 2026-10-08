# DeerMind Semantic Versioning, Replay & Migration Architecture v1.0

> **中文名称**：DeerMind 语义版本、重放与迁移架构<br>
> **版本**：v1.0<br>
> **文档性质**：System Design Baseline<br>
> **状态**：Gate E/F 评审通过后的实现合同基线<br>
> **上位基线**：`DeerMind_Product_Constitution_v1.0.md`、`DeerMind_Concept_Architecture_v1.1.md`、四份 Space Design v1.1、`DeerMind_AI_Native_Architecture_Principles_v0.2.md`、`DeerMind_System_Design_v1.0.md`<br>
> **阶段路线图**：`DeerMind_System_Design_Roadmap_v0.6.md`<br>
> **写作规范**：`DeerMind_Design_Document_Standard_v1.0.md`<br>
> **更新时间**：2026-10-08

本版本在 [DeerMind_Semantic_Version_Replay_Migration_Design_v0.1.md 历史副本](../../src/spike/reports/source-baseline-doc-version-cleanup-20261008/6-DeerMind_Semantic_Version_Replay_Migration_Design_v0.1.md.txt) 的合同基础上吸收 Phase 6 证据处置，统一当前验证状态和跨专项引用。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录 A2 否定、E1/X5 未决的正式后果、Gate E/F 依据和后续能力分期。v1.0 冻结的是实现合同，不是模型质量或生产可靠率。原实验与旧设计输入按其原始版本保留，见[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)。
---

## 1. 文档定位与设计命题

### 1.1 为什么需要独立 Version / Replay / Migration Architecture

DeerMind 不是一个“部署一次、语义长期不变”的软件系统。Learning Target、Task、Solution、Knowledge、Observation semantics、Claim / Evidence semantics、Inference semantics、Interaction Policy、Action semantics、Reasoning Protocol 都可能在长期运行中发生修订。

如果版本只被理解为代码发布号，系统会很快遇到四类无法接受的问题。

第一，**过去的认识会失去语境**。一个 Learner Belief 可能在当时的 Claim、Evidence semantics 与 Protocol 下完全合理，但如果未来只保留“最新语义”，系统就无法解释过去为什么形成该判断。

第二，**新版本会被错误地全局替换旧版本**。DeerMind 的不同 learner、scope、实验、验证和 rollout 可能同时使用不同 active version；要求所有对象在同一时刻切换到一个 `SystemSemanticVersion` 会把不相关的变化绑成全局事务。

第三，**历史重放会被混成重新执行**。重新调用模型、用新语义解释旧事实、重建当时真实 execution、评估一个没有发生的 alternative，是四种完全不同的操作。如果都叫 Replay，系统会制造假的历史确定性。

第四，**迁移会被错误地当成语义等价**。把旧记录搬到新 schema 不代表旧结论在新语义下仍然成立；反过来，语义重新解释也不意味着必须修改原始历史。

因此本专项的核心设计命题是：

\[
\boxed{
PerBoundaryVersionContext
+
MultiVersionCoexistence
+
ImmutableHistory
+
ExplicitReinterpretation
}
\]

并保持：

\[
\boxed{
NewUnderstanding \neq NewPast
}
\]

### 1.2 本文档解决什么

本文档负责定义：

- semantic identity、canonical version、derived revision、execution version 的边界；
- `RuntimeVersionContext` 的正式运行合同；
- `ComponentConsistencyBoundary` 与版本组合一致性；
- Version Resolution、Activation Resolution 与 Compatibility Resolution；
- `ApprovedVersion != CommittedVersion != ActiveVersion`；
- multi-version coexistence、scope-specific activation 与 version pinning；
- boundary 内 pinned semantics 与 effect 前 current eligibility 的关系；
- Target / Claim / Evidence / Binding / Authority 等变化的 typed version impact；
- Data Migration、Representation Migration 与 Semantic Reinterpretation 的边界；
- Historical Reconstruction；
- Reasoning Re-execution；
- Semantic Reinterpretation；
- Counterfactual Evaluation；
- rollback、retirement、deprecation 与 supersession；
- FULL / PARTIAL / UNAVAILABLE replay capability；
- replay capability、replay authorization 与 retention 的关系；
- 版本相关 failure / non-resolution、audit 与 cross-package contract。

### 1.3 本文档不解决什么

本文档不冻结：

- 版本号必须采用 SemVer、整数、自增序号还是内容哈希；
- Canonical Registry 使用何种数据库或服务；
- migration job 使用何种框架；
- backfill / replay worker 的并行度、分区与调度策略；
- shadow rollout、canary、A/B 平台的具体产品选择；
- Model Provider 是否暴露精确权重版本；
- Prompt repository、artifact registry、schema registry 的具体产品；
- 大规模历史重算的容量规划；
- 数据保留期限的具体法律数值；
- 生产级 multi-region rollout 实现。

这些实现可以演进，但不得改变本文档定义的版本语义。

### 1.4 与总体 System Design 的关系

当前总体 `DeerMind_System_Design_v1.0` 继续保持三个系统级合同：

1. DeerMind 不使用一个全局 `SystemSemanticVersion`；
2. runtime boundary 需要 coherent Version Context；
3. Historical Reconstruction、Reasoning Re-execution、Semantic Reinterpretation、Counterfactual Evaluation 必须分离。

本文档负责把这些结论深化到 Focused Design Closure，使实现者不需要在编码阶段重新决定：

> 哪个版本在什么时候生效、哪些版本可以组合、旧结果何时仍可使用、何时必须 reinterpret / reinfer、历史如何重建、回滚究竟改变什么。

---

## 2. Version Model：系统究竟在版本化什么

### 2.1 Version 不是一个字段，而是一组不同责任

DeerMind 至少区分以下概念：

```text
SemanticIdentity
CanonicalVersion
DerivedRevision
ExecutionVersion
ActivationState
Occurrence / Execution Identity
```

它们不能被压成统一 `version` 字段。

### 2.2 Semantic Identity 与 Canonical Version

Canonical semantic object 使用：

```text
SemanticIdentity + CanonicalVersion
```

例如：

```text
Task T42 @ v3
Claim C7 @ v2
InteractionPolicy P9 @ v5
ReasoningProtocol RP-Observation @ v4
```

Semantic Identity 回答“这是同一个被治理对象吗”；Canonical Version 回答“它的正式语义定义处于哪个版本”。

一个新版本默认意味着：

> **同一个 semantic identity 的正式定义发生了可追踪改变。**

如果改变已经使“它还是不是同一个东西”无法保持，则应创建新的 semantic identity，并通过 split / merge / replacement mapping 表达关系，而不是强行升级版本号。

### 2.3 Derived Revision 不是 Canonical Version

Observation、Evidence、Learner Belief、PolicyOutcome 等 Derived Formal State 使用 revision：

```text
DerivedIdentity + Revision
```

Revision 表示：

- grounding correction；
- dependency change；
- semantic reinterpretation；
- reinference；
- supersession；
- owner-specific recompute。

它不是 canonical definition 的版本。

因此：

\[
CanonicalVersion \neq DerivedRevision
\]

### 2.4 Execution Version 与 Semantic Version 分离

一次 AI / Tool / Runtime execution 还会涉及：

```text
ExecutionVersionBindings
├── Model / Provider Revision
├── ContextAssemblyVersion
├── ModelAdapterVersion
├── ToolVersion
├── RuntimeImplementationVersion
└── PromptArtifactVersion when retained
```

这些版本主要用于解释“这次计算如何发生”，默认属于 execution provenance。

它们不自动成为 semantic validity dependency。

例如模型供应商升级了底层模型：

```text
ModelVersion m1 → m2
```

不应自动得到：

```text
All Beliefs become invalid
```

只有当 Evaluation / Evolution 证明该执行版本变化会改变某类正式语义结果的兼容性要求时，相关版本才升级为该 boundary 的 semantic compatibility concern。

因此：

\[
ExecutionVersionChange
\not\Rightarrow
SemanticInvalidation
\]

### 2.5 Reasoning Protocol Version 具有特殊地位

Reasoning Protocol 虽由 AI Runtime 执行，但它定义：

- semantic role；
- allowed context；
- output candidate type；
- grounding；
- uncertainty；
- validation；
- failure semantics。

因此：

\[
ProtocolVersion \neq PromptVersion
\]

Prompt 可以只是 Protocol 的技术表达；Protocol 改变可能直接改变 Observation / Evidence / Policy 等正式语义如何形成。

所以 Reasoning Protocol 通常属于 **Semantic Version Binding**，而不是普通 execution provenance。

### 2.6 Versioned Object 的最小正式信息

一个重要 canonical object 至少应能够表达：

```text
CanonicalVersionRecord
├── SemanticIdentity
├── VersionIdentity
├── Parent / Base Version Ref(s)
├── SemanticDiff or ChangeSummary
├── Owner
├── CommitAuthorityBasis
├── CommitTime
├── CompatibilityMetadata
├── LifecycleState
├── ActivationEligibility
├── Provenance
└── HistoricalMapping / SplitMergeInfo when needed
```

本文档冻结这些语义责任，不冻结物理 schema。

### 2.7 不存在全局 SystemSemanticVersion

DeerMind 明确拒绝：

```text
SystemSemanticVersion = 2026.09.29
```

并要求所有 runtime object 同步依赖这个版本。

原因是不同语义对象变化频率、owner、scope 与 rollout boundary 不同。一次 Claim revision 不应强迫 Interaction Action ontology 同步升级；一个新的 Policy 也不应让历史 Target version 被重写。

因此：

\[
\boxed{
NoGlobalSystemSemanticVersion
}
\]

系统使用的是：

\[
\boxed{
PerBoundaryCoherentVersionContext
}
\]

---

## 3. RuntimeVersionContext 与 Compatibility

### 3.1 RuntimeVersionContext 的职责

每个正式 reasoning / effect boundary 必须拥有 coherent `RuntimeVersionContext`：

```text
RuntimeVersionContext
├── SemanticVersionBindings
│   ├── Learning semantics
│   ├── Evaluation semantics
│   ├── Interaction semantics
│   └── ReasoningProtocol
├── ExecutionVersionBindings
│   ├── Model / Provider Revision
│   ├── ContextAssemblyVersion
│   ├── ToolVersion
│   └── Runtime Adapter Version
├── ComponentConsistencyBoundary
├── CompatibilityResults
├── ResolutionProvenance
└── ActivationBasis
```

它回答的不是“系统现在是什么版本”，而是：

> **这一次正式判断或 effect 在什么语义版本组合下成立。**

### 3.2 ContextManifest、VersionContext 与 DependencySet 不可合并

三者职责不同：

```text
ContextManifest
    = 模型 / reasoning 实际看到了什么

VersionContext
    = 这些输入与规则在什么版本语义下被解释

DependencySet
    = 当前正式结果对哪些上游对象存在 provenance / validity 依赖
```

因此：

\[
ContextManifest
\neq
VersionContext
\neq
DependencySet
\]

一个 object 出现在 ContextManifest 中，不代表它自动成为 current-validity dependency；一个版本进入 ExecutionVersionBindings，也不代表模型版本变化一定使结果失效。

### 3.3 ComponentConsistencyBoundary

每个正式 boundary 必须声明自己的 `ComponentConsistencyBoundary`。

例如 Observation Interpretation 可能要求：

```text
TaskVersion
SolutionVersion
ObservationOntologyVersion
ReasoningProtocolVersion
```

彼此兼容。

Evidence Interpretation 可能要求：

```text
ObservationSemanticsVersion
ClaimVersion
EvidenceSemanticsVersion
ResponsibilityBoundaryVersion
InferenceContractVersion
```

Policy Decision 可能要求：

```text
TargetVersion
ActionSemanticsVersion
PolicyVersion
ReasoningProtocolVersion
ContextAuthorityVersion
```

这不意味着所有 DeerMind 组件必须共享同一个 generation。

### 3.4 “各自 Active”不等于“组合兼容”

假设：

```text
Claim C@v3     = Active
Evidence E@v5 = Active
Inference I@v2 = Active
```

仍然不能推出：

```text
(C@v3, E@v5, I@v2) is compatible
```

因此：

\[
IndividuallyActive
\not\Rightarrow
JointlyCompatible
\]

Compatibility 必须在 boundary 内显式解析。

### 3.5 Compatibility Resolution

Compatibility Resolver 的逻辑结果至少需要区分：

```text
COMPATIBLE
INCOMPATIBLE
UNKNOWN
```

其中：

\[
UnknownCompatibility \neq Compatible
\]

对于要求正式 effect 的 boundary，如果关键组合的兼容性是 UNKNOWN，不能默认为兼容。

系统可以：

- Defer；
- 请求明确 migration / compatibility mapping；
- 选择另一个已知兼容 version set；
- 返回 `VersionCompatibilityUnknown`。

但不能 silent fallback。

### 3.6 Compatibility 可以来自多种依据

兼容性依据可以包括：

- owner-declared compatibility；
- validated migration / equivalence mapping；
- formal schema / contract compatibility；
- Evolution Validation Evidence；
- explicit compatibility rule；
- scope-specific activation policy。

其中最重要的约束是：

> **兼容性本身必须有 provenance。**

不能只保存一个不可解释的 `compatible=true`。

### 3.7 Version Resolver 与 Current Resolver 的关系

版本解析不是 Current Resolver 的全部职责。

逻辑顺序可以表示为：

```text
Resolve Purpose / Scope
→ Resolve eligible canonical version(s)
→ Bind exact version refs
→ Check lifecycle eligibility
→ Check semantic current validity
→ Check authority / data authority
→ Check dependency coherence
→ Check version compatibility
→ Check security eligibility
→ Freeze boundary snapshot
```

Version Resolver 负责：

- 哪些 canonical version 对当前 scope / time / purpose eligible；
- 哪些 version 组合兼容。

Current Resolver 还需要组合：

- semantic validity；
- dependency；
- authority；
- data authority；
- lifecycle；
- security。

因此：

\[
VersionCompatible
\not\Rightarrow
CurrentUsable
\]

### 3.8 Boundary 内 pinning 与未来资格重验

一旦一个 reasoning boundary 开始执行，其 semantic meaning 必须稳定：

```text
BoundaryStart
→ pin exact semantic version refs
→ reasoning / computation
```

否则模型执行过程中语义规则变化，会形成 torn semantic snapshot。

但 pinned meaning 不能冻结未来权限：

\[
PinnedMeaning
+
CurrentCommitEligibility
\]

即：

- semantic refs 在本次 reasoning 内 pinned；
- Commit 前重新检查 critical dependency / authority / data authority / lifecycle / compatibility；
- effect-time Executor 再检查 effect-critical authority / security / preconditions。

因此：

\[
PinnedVersionContext
\neq
PermanentEligibility
\]

---

## 4. Commit、Activation、Multi-Version 与 Rollback

### 4.1 Canonical Version 的三个不同阶段

DeerMind 必须保持：

\[
\boxed{
ApprovedVersion
\neq
CommittedVersion
\neq
ActiveVersion
}
\]

它们分别回答：

**Approved**  
Governance 已经授权某个 exact candidate / proposal 可以被正式采用。

**Committed**  
对应 semantic owner 已经把该 canonical version 作为正式版本写入 Canonical Registry。

**Active**  
该版本当前已经对某个 scope / purpose / time boundary 生效，并参与 runtime resolution。

### 4.2 Canonical Change Chain

标准链路：

```text
RevisionCandidate
→ ValidationEvidence
→ ChangeProposal
→ GovernanceDecision
→ CanonicalChangeAuthorization
→ SemanticOwner CanonicalCommit
→ CommittedCanonicalVersion
→ ActivationAuthorization
→ ActivationRecord
→ ActiveResolution
```

任何环节不能被另一个环节“顺便完成”。

### 4.3 Governance Approval 必须绑定 exact base

GovernanceDecision 至少要绑定：

```text
CandidateRef
ProposalRef
BaseVersionRef
Scope
AuthorizationConditions
Expiry / Revocation Conditions when applicable
```

如果审批以后 base head 已变化：

```text
Base v4
→ approval for candidate based on v4
→ meanwhile v5 committed
```

旧 approval 不能自动 apply 到 v5。

应得到：

```text
CanonicalCommitConflict
or
ApprovalBaseStale
```

而不是自动 rebase。

### 4.4 Activation 是独立 concurrency domain

一个 Committed Version 可以：

- 尚未 Active；
- 只对某个 learner cohort Active；
- 只在 validation / shadow scope Active；
- 与旧版本并行 Active；
- 已 Deprecated 但仍在部分 scope Active；
- 已 Superseded，但历史 execution 仍引用它。

所以：

\[
Committed \neq Active
\]

### 4.5 Multi-Version Coexistence 是架构能力，不是部署技巧

DeerMind 必须支持至少三种合法共存：

**历史共存**  
过去 execution pinned 到旧版本，历史引用永远不能被 activation change 改写。

**In-Flight 共存**  
一个 Decision Cycle 在 v3 上开始时，即使 v4 中途激活，该 cycle 仍保持 v3 meaning，除非出现 explicit revocation / safety block。

**Scope 共存**  
不同 cohort / validation scope / product context 可以合法解析到不同 active version。

因此：

\[
MultiVersionCoexistence
\in
ArchitectureCapability
\]

而不是以后部署平台“有条件再支持”的优化。

### 4.6 Activation Resolution 是 scope-relative

`ActiveVersion` 不是一个全局布尔值。

逻辑上：

```text
ResolveActiveVersion(
  SemanticIdentity,
  Purpose,
  Scope,
  Time,
  ProductContext,
  ActivationPolicy
)
```

返回 exact version 或明确无可用版本。

同一个 version 可以：

```text
Active for cohort A
Inactive for cohort B
Retired for new decisions
Still historically resolvable
```

### 4.7 Version Activation 不能改变历史引用

激活新版本后：

```text
HistoricalDecision D1
    remains pinned to Policy@v2

NewDecision D2
    may resolve Policy@v3
```

禁止后台任务把 D1 的 version ref “升级”为 v3。

\[
ActivationChange
\not\Rightarrow
HistoricalReferenceRewrite
\]

### 4.8 Rollback 不是时间旅行

Rollback 的正确含义是：

> **创建新的未来 Activation Decision，使后续 resolution 再次解析到某个旧的、仍合法的 canonical version。**

例如：

```text
v2 active
→ v3 active
→ v3 shows severe issue
→ Governance authorizes rollback
→ new ActivationRecord makes v2 active again for future boundaries
```

这不会：

- 删除 v3；
- 把 v3 execution 改写成 v2；
- 删除 Governance / Activation history；
- 抹掉已经发生的 ActionOccurrence；
- 让过去“仿佛没有发布过 v3”。

因此：

\[
Rollback \neq HistoryRewrite
\]

### 4.9 Retirement、Deprecation、Supersession 与 Revocation

这些状态也必须分离。

**Deprecated**  
仍可能合法使用，但不再推荐用于新设计 / 新 scope。

**Superseded**  
存在语义上更新的版本，但旧版本历史 standing 仍存在。

**Retired**  
默认不再允许用于新的 active resolution。

**Revoked / Emergency Ineligible**  
明确阻止未来使用，可能立即影响 in-flight / commit eligibility。

因此：

\[
Retired \neq Deleted
\]

\[
Superseded \neq Wrong
\]

\[
Revoked \neq HistoricalNonexistence
\]

---

## 5. Replay：四种不同操作必须严格分开

### 5.1 为什么 “Replay” 必须拆开

DeerMind 的长期解释能力很容易被一个模糊词破坏：

```text
Replay
```

它可能被用来指：

- 重建过去；
- 再跑一次模型；
- 用新语义重新解释；
- 猜“如果当时做别的会怎样”。

四者具有不同的输入、authority、输出 standing 与可验证性。

所以本文档冻结四种正式 operation。

### 5.2 Historical Reconstruction

**目标：**

> 回答“当时真实记录下来的 execution 是什么？”

依赖：

- Event / Factual History；
- ReasoningExecutionRecord；
- ContextManifest；
- exact VersionContext；
- Tool Request / Result；
- Candidate；
- Validation result；
- Commit outcome；
- ActionIntent / ActionOccurrence；
- Governance / Activation history when relevant。

它不需要重新调用模型。

典型输出：

```text
HistoricalExecutionView
```

该 view 是历史解释投影，不创建新的 Observation / Evidence / Belief。

### 5.3 Historical Reconstruction 的核心原则

\[
HistoricalReconstruction
=
ReconstructRecordedPast
\]

而不是：

\[
RerunCurrentSystem
\]

如果某些历史记录已经删除，系统必须如实返回：

```text
PARTIAL
or
UNAVAILABLE
```

而不是用当前模型重新生成一个“看起来像当时”的结果。

### 5.4 Reasoning Re-execution

**目标：**

> 在尽可能相似的执行条件下重新执行一次 cognition，用于 regression、drift、stability、validation。

它产生的是：

```text
NewReasoningExecution
```

不是旧 execution 的替代记录。

即使使用相同：

```text
ProtocolVersion
Context refs
Model name
Parameters
```

也不能保证相同输出。

因此：

\[
ReasoningReexecution
\neq
HistoricalReconstruction
\]

### 5.5 Re-execution 必须记录自己的 provenance

一次 re-execution 至少要记录：

```text
NewExecutionId
ReexecutionOfExecutionRef
RequestedHistoricalVersionContext
ActuallyResolvedExecutionEnvironment
AvailabilityGaps
NewCandidate
NewValidationResult
```

如果 provider 无法提供原 model revision：

```text
Requested historical model = unavailable
```

应显式标记，而不是把当前模型冒充旧模型。

### 5.6 Semantic Reinterpretation

**目标：**

> 使用新的 semantic / protocol version，对已经保留的事实与 artifact 形成新的 derived semantics。

例如：

```text
Event E1
Artifact A1
Observation semantics v1
→ Observation O1

later:

Observation semantics v2
→ reinterpret(E1, A1)
→ Observation O2
```

O2 是新的 derived revision / identity relation。

O1 仍然保留，用于解释过去。

### 5.7 Reinterpretation 必须从合法 grounding 开始

正常原则：

```text
Historical Event / Artifact / admissible Context
→ New Semantic Version
→ New Reasoning
→ New Candidate
→ Validation / Commit
→ New Derived Revision
```

不应默认：

```text
Old Conclusion
→ rename version
→ New Conclusion
```

只有在存在经过验证的 semantic equivalence / migration contract 时，旧结论才可以被安全转换，而无需重新读取完整 grounding。

因此：

\[
Reinterpretation
\neq
VersionFieldRewrite
\]

### 5.8 Counterfactual Evaluation

**目标：**

> 回答“如果当时采用另一个 Action / Policy / Version，可能会发生什么？”

它需要：

- causal assumptions；
- simulation；
- experimental evidence；
- matched historical data；
- model-based estimation；
- 或其他明确的 counterfactual methodology。

它不能由 factual replay 单独证明。

因此：

\[
\boxed{
FactualReplay \neq CounterfactualEvaluation
}
\]

Counterfactual result 属于 Validation / Evolution evidence，而不是 Factual History。

### 5.9 四种 Operation 的对照

| Operation | 回答的问题 | 是否新执行 AI | 是否产生新正式语义 | 能否改写历史 |
|---|---|---:|---:|---:|
| Historical Reconstruction | 当时实际发生了什么 | 否 | 否 | 否 |
| Reasoning Re-execution | 如果重新跑同类 cognition 会怎样 | 是 | 默认仅新 execution；是否 commit 另行决定 | 否 |
| Semantic Reinterpretation | 新语义如何理解旧事实 | 通常是 | 可以形成新 Derived Revision | 否 |
| Counterfactual Evaluation | 未发生 alternative 可能怎样 | 可能 | 形成 Validation Evidence / Hypothesis evidence | 否 |

---

## 6. Data Migration 与 Semantic Reinterpretation

### 6.1 Migration 的第一原则

\[
\boxed{
DataMigration \neq SemanticReinterpretation
}
\]

Data Migration 可以只是：

- schema 变更；
- storage layout 变更；
- field rename；
- encoding 变更；
- index rebuild；
- representation normalization。

只要对象的正式语义没有改变，它不应制造新的 semantic standing。

### 6.2 Representation-Preserving Migration

若迁移被声明为 representation-preserving，必须有明确 contract：

```text
OldRepresentation
→ MigrationTransform
→ NewRepresentation
```

并保证：

```text
SemanticIdentity unchanged
SemanticMeaning unchanged
HistoricalProvenance preserved
```

理想情况下需要：

- checksum / equivalence validation；
- source / target count reconciliation；
- identity preservation；
- referential integrity；
- rollback / recovery path；
- migration audit。

### 6.3 “能迁移”不等于“语义等价”

如果旧字段：

```text
assisted = true/false
```

在新语义中被拆为：

```text
ActualDisclosure
CognitiveWorkSubstitution
ClaimRelativeContamination
```

就不能声称简单字段转换足以得到完整新语义。

旧数据可能只支持：

```text
PARTIAL reinterpretation
```

或者：

```text
NOT_IDENTIFIABLE
```

因此：

\[
RepresentationConvertible
\not\Rightarrow
SemanticallyEquivalent
\]

### 6.4 Semantic Migration 需要显式 Equivalence Basis

如果系统希望在不重新 reasoning 的情况下把旧 formal result 迁移成新版本，需要经过验证的：

```text
SemanticEquivalenceMapping
```

至少声明：

- source semantic version；
- target semantic version；
- applicable object class；
- exact transform；
- preconditions；
- information loss；
- validation evidence；
- validity scope；
- owner / governance authorization。

否则默认走 Semantic Reinterpretation，而不是 automatic migration。

### 6.5 Migration 不能创建不存在的历史

例如新版 Target Responsibility Boundary 要求 learner 独立完成策略选择，但旧历史中 learner 当时已经看到完整策略。

Migration 不能把这段旧历史转换成：

```text
IndependentPerformanceEvidence
```

因为过去没有该 evidence opportunity。

因此：

\[
Migration
\not\Rightarrow
HistoricalOpportunityCreation
\]

### 6.6 Split / Merge 不是简单版本升级

如果一个旧 KC 被拆成两个新 KC：

```text
KC-A@v3
→ KC-A1@v1 + KC-A2@v1
```

不能只通过版本号表达。

系统需要显式：

```text
SplitMapping
SourceIdentity
TargetIdentities
SemanticRelation
Migration / ReinterpretationPolicy
HistoricalTrace
```

Merge 同理。

### 6.7 Backfill 是计算任务，不是事实修正

用新版本对历史数据批量生成新的 Observation / Evidence / Belief：

```text
Historical grounding
→ reinterpretation batch
→ new derived revisions
```

这是 backfill / reinterpretation。

它不意味着过去的旧 derived state “从来不存在”。

因此：

\[
Backfill \neq HistoryCorrection
\]

---

## 7. Typed Version Impact 与 Invalidation

### 7.1 版本变化不能统一全量重算

不同 semantic version change 影响不同 downstream。

核心规则：

\[
VersionChange
\not\Rightarrow
InvalidateEverything
\]

必须执行 typed impact resolution。

### 7.2 Target Definition / Responsibility Boundary Revision

默认影响：

```text
Target revision
→ TargetAssessment stale / invalid
→ relevant Plan context stale
→ Policy Context reevaluation
```

默认不自动影响：

```text
LearnerBelief
Historical Event
Occurred Action
```

因此：

\[
TargetRevision
\Rightarrow
TargetAssessmentReevaluation
\]

但通常：

\[
TargetRevision
\not\Rightarrow
LearnerBeliefRevision
\]

### 7.3 Task / Claim / Evidence / Inference Semantic Revision

这类变化可能直接改变认识论解释。

典型路径：

```text
Claim / Evidence / Inference semantics revision
→ existing Evidence compatibility check
→ Evidence reinterpretation when required
→ Belief reinference
→ TargetAssessment reevaluation
→ future DecisionContext change
```

Historical Event 不被改写。

### 7.4 Observation Semantics Revision

Observation semantics 改变时：

```text
Event / Artifact grounding
→ new Observation interpretation
→ new Observation revision
→ downstream Evidence reevaluation
→ Belief reinference when needed
```

旧 Observation 仍保留用于 historical explanation。

### 7.5 Binding / Context Authority Revision

这类变化主要影响 runtime eligibility：

```text
Binding / Authority version change
→ current projection change
→ DecisionContext stale
→ Plan reevaluation
→ admissible action space change
→ ActionIntent eligibility recheck
```

默认不修改：

- Target Definition；
- Learner Belief；
- Historical Event；
- 已发生 ActionOccurrence。

因此：

\[
AuthorityChange \neq EpistemicChange
\]

### 7.6 Policy / Action Semantics Revision

Policy version change：

- 不重写过去 PolicyOutcome；
- 新 Decision Cycle 解析新 active Policy；
- in-flight cycle 保持 pinned policy meaning，除非 explicit revocation；
- Plan 是否 stale 由 dependency contract 决定。

Action semantics change：

- 新 ActionIntent 必须引用 compatible active Action semantics；
- 历史 ActionOccurrence 继续引用当时 Action version；
- 若新版本改变 Information Disclosure / Cognitive Work Substitution 解释，Evaluation 可以对历史 exposure lineage 做 semantic reinterpretation，但不能改变 occurrence。

### 7.7 Reasoning Protocol Revision

ReasoningProtocol revision 可能属于 semantic-impacting change。

默认规则：

```text
Old committed result remains historical
New executions resolve new active Protocol
```

是否需要对旧 derived state reinterpret，取决于：

- Protocol semantic role 是否变化；
- output contract 是否变化；
- grounding policy 是否变化；
- uncertainty / validation policy 是否影响 standing；
- Evolution 是否发现旧结果不可继续 current-use。

不能因为 Prompt 文案变化就自动全量 invalidate；也不能因为“只是 prompt”而忽略真正的 Protocol semantic change。

### 7.8 Model / Context Assembly / Tool Version Change

默认进入 execution provenance。

只有当 evidence 表明变化会影响某类正式结果的 semantic comparability，才通过 explicit policy 把它纳入 compatibility / validity dependency。

这保持：

\[
ProvenanceDependency \neq ValidityDependency
\]

---

## 8. Replay Capability、Retention 与 Authorization

### 8.1 ReplaySupport 不是永久保留承诺

DeerMind 必须支持历史解释，但：

\[
ReplaySupport \neq IndefiniteRetention
\]

Data Restraint、purpose limitation、合法删除、Product Context、外部服务保留策略都可能使历史重建能力下降。

### 8.2 Replay Capability 等级

本版本冻结三个最低等级：

```text
FULL
PARTIAL
UNAVAILABLE
```

**FULL**  
当前授权范围内，目标 operation 所需的关键 grounding、version、execution provenance 足够完整。

**PARTIAL**  
可以完成部分解释，但存在明确缺失，例如原 artifact 已删除、provider revision 不可恢复、某 Tool Result 不再存在。

**UNAVAILABLE**  
缺失关键依据，无法诚实完成目标 operation。

### 8.3 Capability 是针对 operation 的

同一历史对象可以同时：

```text
Historical Reconstruction = FULL
Reasoning Re-execution     = PARTIAL
Semantic Reinterpretation  = FULL
Counterfactual Evaluation  = UNAVAILABLE
```

不存在一个全局 `replayable=true`。

### 8.4 Replay Capability 与 Replay Authorization 分离

\[
\boxed{
ReplayCapability \neq ReplayAuthorization
}
\]

即使系统保留了完整数据，也不意味着当前 purpose 有权读取。

反过来，即使当前有 authority，如果数据已经合法删除，也不能假装 capability 仍然存在。

### 8.5 历史 Authorization Evidence 不能复用为当前权限

Historical record 可以证明：

> 当时这次 execution 是在什么 authority / data authority 下发生。

但：

\[
HistoricalAuthorizationEvidence
\neq
CurrentAuthorization
\]

任何新的 replay / reinterpretation / re-execution 都必须重新解析当前：

- purpose；
- data authority；
- disclosure restriction；
- destination；
- retention / legal status；
- security eligibility。

### 8.6 删除不自动使旧语义失效

如果合法删除 raw artifact：

```text
Artifact removed
```

并不自动得到：

```text
Belief invalid
```

可能出现：

```text
Belief semantic validity = still current
Replay capability        = PARTIAL
Grounding availability   = reduced
```

所以：

\[
Deletion \neq SemanticInvalidation
\]

但如果某类 Current Use contract 要求 grounding 必须可重新核验，那么 availability loss 可以通过 explicit dependency rule 使该用途不再 eligible。

---

## 9. Failure、Concurrency 与 Recovery

### 9.1 Version Failure 必须 typed

至少区分：

```text
VersionNotFound
NoActiveVersion
VersionIncompatible
VersionCompatibilityUnknown
ActivationConflict
ApprovalBaseStale
CanonicalCommitConflict
MigrationValidationFailed
ReplayPartial
ReplayUnavailable
HistoricalDependencyMissing
ProviderRevisionUnavailable
ReinterpretationNotIdentifiable
```

不能统一返回 `version error`。

### 9.2 No Active Version 是合法状态

如果某 semantic identity 对当前 scope 没有合法 Active Version：

```text
NoActiveVersion
```

系统不能：

- 自动使用 latest；
- 自动使用 retired；
- 自动跨 scope 借用版本；
- 自动 fallback 到“看起来最接近”的版本。

### 9.3 Activation 并发

两个 activation proposal 同时试图改变同一 scope：

```text
A: activate v3 based on activation-head h7
B: activate v4 based on activation-head h7
```

一个成功后，另一个必须得到：

```text
ActivationConflict
```

不得 Last-Write-Wins。

### 9.4 Canonical Commit 与 Activation Conflict 分离

可能：

```text
CanonicalCommit succeeds
Activation fails
```

这不是异常不一致。

结果是：

```text
Committed but not Active
```

同样：

```text
Activation conflict
```

不应回滚已经合法形成的 CanonicalVersion record。

### 9.5 In-Flight Boundary 与 Activation Change

如果：

```text
DecisionCycle D
pins Policy@v2
```

随后：

```text
Policy@v3 activated
```

D 默认继续按 v2 meaning 执行到 Candidate / Commit boundary。

Commit 前仍重验：

- current authority；
- data authority；
- explicit revocation；
- compatibility；
- declared critical version preconditions。

如果激活变化只是 future-boundary activation，则 D 不自动 stale。

如果 v2 被 explicit revoked for safety / illegality，则 D 可以因 `VersionIneligible` / `AuthorityStale` 失败。

### 9.6 Recovery 不能靠重新运行模型伪造历史

如果 ReasoningExecutionRecord 部分丢失：

- 可以声明 PARTIAL；
- 可以恢复剩余 execution metadata；
- 可以 re-execute 形成新 execution；
- 可以产生 Evolution issue。

不能：

```text
rerun LLM
→ pretend output was historical output
```

因此：

\[
Recovery \neq HistoricalFabrication
\]

### 9.7 Migration Recovery

迁移失败时必须能够区分：

```text
Source untouched
Target partially written
Target validated
Activation changed or not changed
```

Representation migration 的失败不能隐式触发 semantic activation。

推荐逻辑：

```text
prepare target representation
→ validate equivalence
→ commit migration result
→ switch storage / representation pointer if needed
```

如果语义版本也改变，则另走 canonical change / activation chain，不能混成一个事务语义。

---

## 10. 与相邻 Work Package 的运行契约

### 10.1 Runtime & Event Architecture

Event / Factual History 提供：

- immutable occurrence；
- correction relation；
- source / time provenance；
- ActionOccurrence；
- historical factual grounding。

本专项保证：

- semantic activation 不重写 Event；
- reinterpretation 从历史 Event / Artifact 形成新 derived state；
- rollback 不改变 occurrence history。

\[
HistoricalFact \neq LaterInterpretation
\]

### 10.2 AI Reasoning Runtime

AI Runtime 提供：

- ReasoningExecutionRecord；
- ContextManifest；
- Protocol / Model / Tool execution provenance；
- Candidate；
- Validation / Commit handoff。

本专项负责：

- 哪些版本进入 semantic binding；
- 哪些版本仅是 execution provenance；
- re-execution 与 historical reconstruction 的区分；
- Protocol version compatibility；
- provider revision unavailable 时 replay capability 如何降级。

### 10.3 State / Dependency / Invalidation

State 专项负责 exact dependencies、Current Resolution、typed invalidation 与 current validity barrier。

本专项提供：

- version identity；
- active resolution；
- compatibility result；
- version impact semantics；
- reinterpretation / migration relation。

二者结合形成：

```text
Resolve exact state
+ resolve version eligibility
+ check compatibility
+ check current validity
```

### 10.4 Interaction & Decision Runtime

Interaction 使用：

- Target / Action / Policy / Protocol version；
- current Binding / Authority version；
- DecisionContext exact refs；
- ActionIntent exact semantics。

本专项要求：

- DecisionCycle 保存 exact VersionContext；
- activation 变化不改写历史 Decision；
- Policy / Action incompatible 时不能 silent fallback；
- Plan 对相关 semantic version 使用 CURRENT dependency；
- new active version 影响 future Decision opportunity，不形成自动 action command。

### 10.5 Evaluation

Evaluation 的 Evidence / Belief 需要知道：

- Claim / Evidence / Inference semantics；
- Observation semantics；
- Responsibility Boundary；
- assistance exposure interpretation semantics；
- dependency compatibility。

若 semantic version 改变：

```text
compatibility check
→ reinterpret Evidence when required
→ reinfer Belief when required
```

Evaluation 仍是 Belief 唯一 writer。

### 10.6 Evolution / Governance

Evolution：

- 发现旧版本问题；
- 形成 RevisionCandidate；
- 产生 ValidationEvidence；
- 分析 compatibility / migration / replay impact。

Governance：

- 授权 canonical change；
- 授权 activation / rollback；
- 授权高风险 migration policy when required。

本专项不合并 Evolution 与 Governance。

### 10.7 Data Authority / Privacy / Security

Replay / re-execution / reinterpretation 都属于新的 data use。

每次 operation 必须重新检查当前：

```text
Purpose
Data Authority
Disclosure Scope
Destination
Retention
Security
```

历史版本存在，不代表今天有权读取。

---

## 11. Capability Staging 与验证状态

### 11.1 本专项的 Architecture Contract

以下从 v0.1 起属于 S0 mandatory contract：

- 无全局 SystemSemanticVersion；
- per-boundary coherent RuntimeVersionContext；
- Semantic / Execution Version 分离；
- Approved / Committed / Active 分离；
- multi-version coexistence；
- scope-relative activation；
- pinned historical refs；
- Current != Latest；
- UnknownCompatibility != Compatible；
- Data Migration != Semantic Reinterpretation；
- Historical Reconstruction / Re-execution / Reinterpretation / Counterfactual 分离；
- rollback 不改写历史；
- replay capability 与 authorization 分离；
- typed version impact；
- no silent cross-version interpretation。

### 11.2 Consolidated Spike 中必须真实验证的部分

Dimension C 至少需要验证：

1. 无全局版本号时，一个最小 MVCL 是否能依靠 per-boundary VersionContext 保持 coherent；
2. 版本 activation 发生时，in-flight boundary 能否保持 pinned meaning；
3. incompatible combination 是否被阻止；
4. semantic reinterpretation 能否形成新 revision 而保留旧历史；
5. Historical Reconstruction 与 Reasoning Re-execution 是否能在实现上清晰区分；
6. retention / provider nondeterminism 存在时，系统能否诚实表达 PARTIAL / UNAVAILABLE。

### 11.3 可以 staged 的工程能力

可以延后到 S2 / S3：

- 大规模 persistent compatibility index；
- 自动 migration planner；
- 大规模 historical backfill；
- production replay farm；
- multi-region version registry；
- 自动 canary / shadow rollout 平台；
-完整 rollback orchestration；
- provider-level exact environment recreation；
-跨年历史数据批量 reinterpretation。

但 staging 不得降低本文档的语义边界。

### 11.4 Architecture Assumption AA-C01

**AA-C01 — Per-Boundary Version Context Sufficiency**

假设：

> DeerMind 不需要全局 `SystemSemanticVersion`；只要每个 consistency boundary 解析并固定 coherent VersionContext，就足以保证正式 reasoning / effect 的语义一致性。

当前状态：

```text
SUPPORTED within declared Spike scope; production migration and scale remain unvalidated
```

主要 falsifier：

- 多个 boundary 持续要求全系统原子版本切换才能避免语义撕裂；
- compatibility 组合复杂度无法被局部解析；
- cross-boundary state 无法用 exact refs 解释；
- 全局 generation 成为 correctness 必需，而不是实现便利。

如果被 Denied，首先修订 Version Context / consistency design；只有证明全局版本是不可避免的架构要求时，才考虑 Architecture Reopen。

### 11.5 Architecture Assumption AA-C02

**AA-C02 — Honest Reconstruction Without Deterministic Reproducibility**

假设：

> 即使模型输出不可严格复现、某些 provider revision 不可获得、部分 grounding 因合法 retention 被删除，系统仍能通过 execution history、version / provenance 与 FULL / PARTIAL / UNAVAILABLE 能力声明，清晰区分 Historical Reconstruction、Re-execution 与 Reinterpretation。

当前状态：

```text
SUPPORTED within declared Spike scope; production migration and scale remain unvalidated
```

主要 falsifier：

- 关键审计要求必须依赖完全相同模型重跑才能满足；
- 删除部分 raw data 后，系统无法解释历史 decision 到最低可接受程度；
- execution provenance 不足以区分“当时发生”与“后来重新生成”。

### 11.6 Focused Design Closure 判断

本专项合同纳入 System Design v1.0 基线，与总体及其余五项专项完成一致性评审。Gate E/F 的逐项依据及能力分期见[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)，实验范围见[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)。该关闭指可实施设计完成，不证明生产质量、可靠率或规模能力。

AA-C01/AA-C02 的支持限于已有受控版本、重建和保留场景；不代表模型可确定性重现，亦不代表生产迁移平台已验证。

### 11.7 下一 Work Package

当前系统设计内部 Phase 6 已完成，Gate E/F 通过；总体 Development Phase 2 准入。下一工作是 Architecture Validation Build 的组件与验证方案，随后实现真实窄范围闭环，见[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md) §5。Spike 原否定/未决保持；后续证据可触发新版本修订，不能在实现中静默改变本合同。

## Appendix A — Version / Replay Invariant Registry

| ID | Invariant |
|---|---|
| **VR-01** | DeerMind 不使用要求全系统同步升级的 `SystemSemanticVersion`。 |
| **VR-02** | 每个正式 consistency boundary 必须拥有 coherent `RuntimeVersionContext`。 |
| **VR-03** | `SemanticIdentity != CanonicalVersion != DerivedRevision != ExecutionVersion`。 |
| **VR-04** | `ProtocolVersion != PromptVersion != ModelVersion`。 |
| **VR-05** | Execution version 默认属于 provenance，不自动成为 semantic validity dependency。 |
| **VR-06** | `ContextManifest != VersionContext != DependencySet`。 |
| **VR-07** | `IndividuallyActive not=> JointlyCompatible`。 |
| **VR-08** | `UnknownCompatibility != Compatible`。 |
| **VR-09** | Boundary 内 semantic meaning 可以 pinned；future authority / data authority / security eligibility 不能永久 pinned。 |
| **VR-10** | `ApprovedVersion != CommittedVersion != ActiveVersion`。 |
| **VR-11** | Governance approval 必须绑定 exact candidate / proposal / base version。 |
| **VR-12** | Multi-version coexistence 是架构能力，包括 historical、in-flight 与 scope coexistence。 |
| **VR-13** | Activation change 不改写 historical version refs。 |
| **VR-14** | `Rollback != HistoryRewrite`；rollback 是新的未来 Activation Decision。 |
| **VR-15** | `Retired != Deleted`，`Superseded != Wrong`。 |
| **VR-16** | `HistoricalReconstruction != ReasoningReexecution`。 |
| **VR-17** | `SemanticReinterpretation != VersionFieldRewrite`。 |
| **VR-18** | `FactualReplay != CounterfactualEvaluation`。 |
| **VR-19** | Re-execution 产生新的 execution identity，不替代旧 execution。 |
| **VR-20** | Reinterpretation 默认从 factual grounding / artifact / admissible context 开始。 |
| **VR-21** | `DataMigration != SemanticReinterpretation`。 |
| **VR-22** | Representation migration 不能自动声明 semantic equivalence。 |
| **VR-23** | Migration / backfill 不能创造历史中不存在的 evidence opportunity。 |
| **VR-24** | Version change 必须 typed impact，不得统一 invalidate all。 |
| **VR-25** | Target revision 默认影响 Assessment / Plan，不自动重写 Learner Belief。 |
| **VR-26** | Claim / Evidence / Inference semantic revision 可以触发 Evidence reinterpretation 与 Belief reinference。 |
| **VR-27** | Binding / Authority revision 主要影响 Policy Context / Plan / Action eligibility，不自动产生 epistemic change。 |
| **VR-28** | `ReplaySupport != IndefiniteRetention`。 |
| **VR-29** | `ReplayCapability != ReplayAuthorization`。 |
| **VR-30** | Replay capability 必须 operation-specific，可为 `FULL / PARTIAL / UNAVAILABLE`。 |
| **VR-31** | Historical authorization evidence 不能作为新的 replay / re-execution credential。 |
| **VR-32** | `Deletion != SemanticInvalidation`，但可以降低 grounding availability / replay capability。 |
| **VR-33** | `NoActiveVersion` 是合法状态；禁止 fallback 到 latest / retired / unrelated scope。 |
| **VR-34** | Activation concurrency 不使用 Last-Write-Wins。 |
| **VR-35** | Canonical Commit 与 Activation 是不同 concurrency domain。 |
| **VR-36** | Recovery 不得通过重新运行 LLM 伪造 historical execution。 |
| **VR-37** | `NewUnderstanding != NewPast`。 |

---

## Appendix B — Core Version Object Responsibility Matrix

| Object / Record | Owner / Authority | Standing | 核心职责 |
|---|---|---|---|
| SemanticIdentity | 对应 semantic owner | Canonical identity | 定义“这是同一个什么对象” |
| CanonicalVersion | 对应 semantic owner + Governance authorization when required | Canonical semantic state | 一个 identity 的正式语义版本 |
| GovernanceDecision | Governance | Authorization standing | 对 exact proposal / candidate / base 授权 |
| CanonicalChangeAuthorization | Governance / authority mechanism | Commit authority | 允许 semantic owner 执行 exact canonical commit |
| ActivationRecord | Governance / authorized activation mechanism | Activation history | 定义某 version 对某 scope / time 的 activation change |
| RuntimeVersionContext | boundary resolver | Runtime control snapshot | 一次 reasoning / effect 的 coherent version bindings |
| CompatibilityResult | version / compatibility resolver | Derived control result | 某 exact version combination 是否可共同使用 |
| ContextManifest | AI Runtime | Execution provenance | 当时模型实际看到了什么 |
| DependencySet | downstream semantic owner + state runtime support | Provenance / validity relation | 结果依赖哪些 exact upstream |
| ReasoningExecutionRecord | AI Runtime | Execution history | 当时 cognition 如何执行 |
| HistoricalExecutionView | replay / audit projection | Historical projection | 重建已记录过去，不产生新历史 |
| ReexecutionRecord | AI Runtime / validation workflow | New execution history | 对历史条件的新一次 execution |
| ReinterpretationRevision | 对应 derived semantic owner | New derived formal state | 用新语义解释旧 grounding |
| MigrationRecord | migration mechanism / owning domain | Operational / canonical audit | representation / data migration 过程与结果 |
| SemanticEquivalenceMapping | semantic owner + validation / governance as required | Canonical / governed mapping | 声明 source / target semantic equivalence 的适用条件 |
| ReplayCapabilityAssessment | replay resolver | Derived capability status | FULL / PARTIAL / UNAVAILABLE 及原因 |

---

## Appendix C — Version Resolution Decision Table

| 情况 | 允许 current use? | 默认结果 |
|---|---:|---|
| exact version active + compatible + valid | 是 | Use exact version |
| latest but not active | 否 | `NoActiveVersion` / resolve active |
| active but incompatible with boundary peers | 否 | `VersionIncompatible` |
| compatibility unknown | 否 | `VersionCompatibilityUnknown` |
| historical pinned version, only for audit | 是（historical purpose） | Historical read |
| historical pinned version for new decision | 否，除非重新解析后仍 eligible | Re-resolve current |
| retired version referenced by historical execution | 是（historical purpose） | Preserve exact ref |
| revoked version in in-flight effect | 否 | Commit / execution rejection |
| model version changed, semantic contract unchanged | 通常是 | New execution provenance only |
| Protocol semantic version changed | 视 compatibility | New boundary resolution |
| raw grounding deleted | 视 use contract | semantic standing 可保留；replay 降级 |
| rollback reactivates old canonical version | 对未来 boundary 是 | New ActivationRecord |

---

## Appendix D — Replay Operation Contract Matrix

| Contract | Historical Reconstruction | Reasoning Re-execution | Semantic Reinterpretation | Counterfactual Evaluation |
|---|---|---|---|---|
| Primary question | 当时发生了什么 | 再执行会怎样 | 新语义如何理解旧事实 | 未发生 alternative 可能怎样 |
| Historical Event required | 通常需要 | 通常需要 | 通常需要 | 通常需要但不足 |
| Original ContextManifest | 重要 | 若要逼近历史条件则重要 | 可选，取决于 reinterpretation | 可作为输入 |
| Original model availability | 不要求 | 可能要求但不可保证 | 不要求使用旧模型 | 不固定 |
| New AI execution | 否 | 是 | 通常是 | 可能 |
| Creates new execution record | 否 | 是 | 若使用 AI 则是 | 若使用 AI 则是 |
| Can create new derived semantics | 否 | 只有显式 commit 时 | 是 | 通常形成 validation / hypothesis evidence |
| Changes historical facts | 否 | 否 | 否 | 否 |
| Needs current Data Authority | 是 | 是 | 是 | 是 |
| Can be PARTIAL | 是 | 是 | 是 | 是 |
| Default reproducibility expectation | recorded-history reconstruction | nondeterministic | intentionally allows new meaning | methodology-dependent |

---

## Appendix E — Architecture Assumption Registry Entry

### AA-C01 — Per-Boundary Version Context Sufficiency

**Claim**  
Per-boundary coherent Version Context 足以替代全局 SystemSemanticVersion。

**Protects**  
VR-01、VR-02、VR-07、VR-08、SI-22。

**Validation Dimension**  
C — Version / Replay。

**Falsifier**  
现实组合持续需要全局 atomic semantic generation 才能避免正式语义撕裂，或局部 compatibility resolution 无法表达关键 cross-boundary consistency。

**Status**  
`SUPPORTED within declared Spike scope; production migration and scale remain unvalidated`

**If Denied**  
优先修订 compatibility / consistency boundary；只有证明全局 generation 是 semantic correctness 必需时才提出 Architecture Reopen Candidate。

### AA-C02 — Honest Reconstruction Without Deterministic Reproducibility

**Claim**  
在模型不可严格复现、provider revision 不完整、合法 retention 导致部分 grounding 缺失时，系统仍能诚实区分 Reconstruction / Re-execution / Reinterpretation，并用 FULL / PARTIAL / UNAVAILABLE 表达能力边界。

**Protects**  
VR-16、VR-18、VR-28、VR-29、VR-30、VR-36、SI-24。

**Validation Dimension**  
C — Version / Replay。

**Falsifier**  
关键历史解释必须依赖不可获得的 exact model replay，或 execution provenance / retained grounding 不足以区分过去事实与后来生成结果。

**Status**  
`SUPPORTED within declared Spike scope; production migration and scale remain unvalidated`

**If Denied**  
修订 provenance retention、ExecutionRecord、replay contract 或 Product Context retention requirements；验证价值本身不得自动创造新的 Data Authority。

---

## Appendix F — 当前不冻结的实现决策

以下仍是后续 ADR / implementation decision，而不是本专项的架构结论：

- Version ID 编码格式；
- Canonical Registry 的物理数据模型；
- activation index / compatibility index 的存储结构；
- compatibility rule engine 的实现方式；
- split / merge mapping 的具体 schema；
- migration worker / backfill scheduler；
- replay worker / queue；
- large-scale snapshot storage；
- provider artifact pinning 机制；
- Prompt artifact registry；
- rollout / canary / shadow 平台；
- batch reinterpretation framework；
- migration transaction 的数据库实现；
- historical archive tier；
- FULL / PARTIAL capability 的自动评估算法。

这些实现应由本文档已经冻结的 semantic integrity、authority、privacy、operability 与 validation requirements 反向推导，而不能反过来弱化版本语义。
