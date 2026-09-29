# DeerMind Runtime & Event Architecture v0.1

> **中文名称**：DeerMind 运行时与事件架构  
> **版本**：v0.1  
> **文档性质**：Focused System Design / Pre-Validation Candidate  
> **状态**：§3.2 Focused Design Closure 候选  
> **上位基线**：`DeerMind_Product_Constitution_v1.0.md`、`DeerMind_Concept_Architecture_v1.1.md`、四份 Space Design v1.1、`DeerMind_AI_Native_Architecture_Principles_v0.2.md`、`DeerMind_System_Design_v0.1.md`  
> **阶段路线图**：`DeerMind_System_Design_Roadmap_v0.4.md`  
> **写作规范**：`DeerMind_Design_Document_Standard_v1.0.md`  
> **更新时间**：2026-09-29  
> **版本说明**：v0.1 是 Runtime & Event Architecture 的首个 Pre-Validation Focused Design Candidate。它不改变 Concept Architecture 与 System Design 已冻结的 `Event != Observation != Evidence != Belief`、immutable factual history、`SelectedAction != ActionOccurrence`、append-only correction、per-boundary versioning、Data Authority 与 historical replay 边界，而是把这些系统级合同深化为可直接约束实现的事实运行契约。本文档冻结 Event identity、occurrence identity、factual authority、time / ordering、admission、deduplication、correction、late arrival、ActionOccurrence、ExternalInput、历史与 retention / replay 等运行规则；数据库产品、分区模型、消息系统和生产级物理持久化仍不在本版本冻结范围内。

---

## 1. 文档定位与设计命题

### 1.1 为什么需要独立 Runtime & Event Architecture

DeerMind 的所有长期认识、决策与演化最终都依赖一个更基础的问题：**系统究竟凭什么说“某件事情发生过”？**

如果 Event 只被理解成“消息队列里的一条消息”或“数据库里的一行日志”，后续 Observation、Evidence、Belief、Action、Replay 与 Audit 都会失去共同事实基础。相反，如果 Event 被赋予过多解释责任，又会把 learner ability、policy judgment、authority interpretation 等派生语义偷偷塞进事实层，使事实历史无法保持稳定。

因此本专项的核心设计命题是：

\[
\boxed{
Event = Authorized\ Attestation\ of\ an\ Occurrence
}
\]

Event 不是“世界绝对真相”，而是 DeerMind 对一个授权来源所作 occurrence attestation 的正式记录。Factual Runtime 的职责，是让这种 occurrence standing 可追溯、不可静默改写、可纠正、可去重、可晚到、可审计，并能成为所有上层语义的稳定 grounding。

### 1.2 本文档解决什么

本文档负责定义：

- Event Identity 与 Occurrence Identity；
- factual producer、actor、direct source、reported source 与 factual authority；
- Event admission、validation、commit、deduplication 与 idempotency；
- occurred / received / recorded / processing time 的语义边界；
- record order、occurrence order、producer order、causal order 的区分；
- correlation、episode、workflow 与 causality 的不同责任；
- Learner Work、External Input、ActionOccurrence、Target Binding occurrence 等事实进入 Factual History 的条件；
- ActionIntent、Action execution result 与 ActionOccurrence 的 effect boundary；
- correction、late arrival、supersession 与 current factual view；
- Factual History、Reasoning History、Semantic History、Audit / Telemetry 的边界；
- Event retention、payload deletion、ReplaySupport 与 Historical Reconstruction 的关系；
- 与 State / Dependency、Interaction、AI Runtime、Version / Replay、Security / Data Authority 的接口。

### 1.3 本文档不解决什么

本文档不冻结：

- PostgreSQL、EventStoreDB、Kafka、Pulsar、RabbitMQ 等具体产品；
- 单库、分库、日志式存储或对象存储等物理持久化方式；
- Event partition key、索引、冷热分层、压缩格式等性能设计；
- 服务拆分、微服务边界或部署拓扑；
- 具体 RPC / API / protobuf / JSON schema；
- 生产级跨区域复制、灾备、吞吐和容量规划；
- Observation、Evidence、Belief 的领域解释算法；
- Interaction Policy 与 Evaluation Inference 的具体策略。

这些实现可以演进，但不得改变本文档冻结的事实语义。

### 1.4 与总体 System Design 的关系

总体 `DeerMind_System_Design_v0.1` 规定 Factual Runtime 在系统中的位置、Source of Truth 与上层闭环；本文档负责把该系统级责任深化到 Focused Design Closure。本文档不新建新的 semantic owner，也不把 Factual Runtime 提升成一个独立 Conceptual Space。

可以概括为：

```text
Concept Architecture
    定义 Global Event Model 的语义边界
        ↓
Integrated System Design
    定义 Factual Runtime 在全系统中的位置
        ↓
Runtime & Event Architecture
    定义 occurrence 如何取得、保持和修正 factual standing
```

---

## 2. Factual Runtime 的心智模型与责任边界

### 2.1 Event Truth 不等于 World Truth

Event 的事实性是 **attestation truth**，不是 payload 中每个命题都已经被 DeerMind 证明为现实真相。

例如 learner 说：“老师说我比例应用题不行。”

Factual Runtime 可以正式记录：

```text
LearnerReported(
  reported_source = Teacher,
  statement = "比例应用题不行"
)
```

它不能直接记录为：

```text
LearnerCapability(RatioWordProblem) = Weak
```

后者需要 Observation、Evidence 与 Inference。

因此：

\[
EventTruth \neq WorldTruth
\]

以及：

\[
ReportedClaimEvent \neq ClaimIsTrue
\]

### 2.2 Event、Observation、Evidence、Belief 必须分层

Factual Runtime 只拥有发生事实，不拥有对发生事实的学习语义解释：

\[
\boxed{
Event \neq Observation \neq Evidence \neq Belief
}
\]

- Event 回答：发生了什么、谁声明发生、什么时候被记录；
- Observation 回答：该 occurrence 在当前交互语义下意味着什么；
- Evidence 回答：该 Observation 相对于某个 Claim 有什么认识价值；
- Belief 回答：Evaluation 当前正式相信 learner 能做什么。

任何“为了方便”直接从 Event 写 Belief 的实现，都违反架构。

### 2.3 Factual Runtime 的三项核心责任

Factual Runtime 只有三类不可替代责任：

1. **Occurrence Admission**：判断一个输入是否有资格成为 DeerMind 正式 Factual History 的一部分；
2. **Factual Standing Preservation**：保证已 Commit 的 occurrence attestation 不被静默覆盖，并保留 identity、time、source、authority 与 provenance；
3. **Correction / Historical Resolution**：通过 append-only correction 表达“过去记录有误或需要修正”，同时让 current factual view 能停止使用被纠正记录。

Factual Runtime 不负责：

- 判断 learner 是否掌握；
- 判断一个 external request 是否应当服从；
- 判断一个 action 是否值得执行；
- 判断一个 event 对某个 Claim 是支持还是反驳；
- 决定 canonical semantics 应否变化。

### 2.4 Factual History 不是 Application Log

只有具有跨边界、长期解释或正式 effect 意义的 occurrence 才需要进入 Factual History。

因此：

\[
GlobalEvent \subset FactualHistory
\]

且：

\[
FactualHistory \neq ApplicationLog \neq Telemetry
\]

例如一次数据库连接重试、GC pause、内部 cache miss 通常属于 Operational Telemetry；它们只有在影响正式 Action result、Security boundary、Data Authority 或其他系统语义时，才可能通过专门 factual contract 被提升为正式 occurrence。

这同时意味着 DeerMind 不要求采用“所有状态都从 Event 重建”的 Event Sourcing Architecture。Event History 是事实来源，不是对某种软件架构模式的强制选择。

---

## 3. Event Identity、Authority 与 Factual Envelope

### 3.1 Event Identity 与 Occurrence Identity 分离

一个正式 Event 至少需要区分：

```text
EventIdentity      = DeerMind 对这条正式 factual record 的稳定 identity
OccurrenceIdentity = 这条 record 所指向的现实 occurrence identity
```

二者不能合并。

原因是同一个 occurrence 可能被：

- 重复发送；
- 不同传输路径重投；
- 同一 producer retry；
- correction 记录引用；
- 不同 source 分别作独立 attestation。

因此：

\[
EventIdentity \neq OccurrenceIdentity
\]

### 3.2 Occurrence Identity 的最低语义

Occurrence identity 必须能支持 **同一来源语义下的重复识别**。逻辑上至少包括：

```text
OccurrenceKey
├── Namespace
├── Producer / Source Scope
└── ProducerOccurrenceKey or StableOccurrenceKey
```

实际实现可以使用 UUID、业务键、producer sequence 或组合键，但不能仅用 payload hash 代替 occurrence identity。

\[
SamePayload \not\Rightarrow SameOccurrence
\]

两次完全相同的答案提交可能是两次不同学习机会；一次 occurrence 的网络重试也可能产生两份字节完全相同的 payload。Payload equality 既不能证明同一 occurrence，也不能证明不同 occurrence。

### 3.3 Actor、Producer、Source 与 Authority 不可混淆

Factual Envelope 必须能区分以下角色：

- **Actor**：现实中执行或声明某行为的主体；
- **Producer**：把 attestation 送入 DeerMind 的技术生产者；
- **Direct Source**：DeerMind 直接接收到信息的来源；
- **Reported Source**：Direct Source 所转述的原始来源；
- **Factual Authority**：某来源是否被允许对这一类 occurrence 作正式 attestation。

例如 learner 转述 teacher 的要求：

```text
Actor / DirectSource = Learner
ReportedSource        = Teacher
Producer              = ClientApp
```

系统不能把 `ReportedSource = Teacher` 伪装成“Teacher 直接向 DeerMind 输入”。

同样：

\[
ActorIdentity \neq FactualAuthority
\]

一个主体“是谁”与它“是否有权对某类事实作正式 attestation”是两个问题。

### 3.4 Factual Authority 只授权记录事实，不授权解释事实

Factual authority 的作用是：

> **允许某 source 对某类 occurrence 进入 Factual History。**

它不意味着：

- external input 自动变成 AuthorityDirective；
- parent request 自动变成 Policy command；
- teacher-reported claim 自动变成 Evidence；
- model output 自动变成 Event；
- event source 自动拥有 canonical change 权限。

因此：

\[
FactualAuthority \neq SemanticAuthority \neq PolicyAuthority
\]

### 3.5 Event Envelope 的逻辑字段族

本文档冻结字段的 **语义类别**，不冻结具体序列化 schema。正式 Event 至少需要能够表达：

```text
EventEnvelope
├── Identity
│   ├── EventId
│   ├── EventType
│   └── OccurrenceKey
├── Subject / Source
│   ├── SubjectRef(s)
│   ├── ActorRef
│   ├── DirectSourceRef
│   ├── ReportedSourceRef(s)
│   └── ProducerRef
├── Factual Authority
│   ├── AuthorityBasisRef
│   └── AdmissionScope
├── Time
│   ├── OccurredAt / OccurrenceTimeRange
│   ├── SourceObservedAt (optional)
│   ├── ReceivedAt
│   └── RecordedAt
├── Content
│   ├── TypedPayload
│   └── ArtifactRef(s)
├── Relation
│   ├── CorrelationRef(s)
│   ├── CausalRef(s) when explicitly supported
│   ├── EpisodeRef(s) when available
│   └── WorkflowExecutionRef(s) when applicable
├── Correction
│   ├── CorrectsEventRef
│   └── CorrectionReason / Basis
└── Provenance
    ├── AdmissionPolicyVersion
    ├── ProducerProtocolVersion
    └── DataAuthority / Security Audit Ref(s) as required
```

重要的是：这些字段回答 occurrence standing，而不是把 Observation / Evidence / Policy semantics 偷塞入 Event。

---

## 4. 时间、顺序、关联与因果

### 4.1 DeerMind 不假设全局时间真相

分布式运行中，“什么时候发生”“什么时候被 source 观察”“什么时候到达 DeerMind”“什么时候正式写入”是不同概念。

至少区分：

- **OccurredAt**：source attested 的 occurrence time；
- **SourceObservedAt**：source 自己实际观察到 occurrence 的时间，可选；
- **ReceivedAt**：DeerMind runtime 首次接收到该 attestation 的时间；
- **RecordedAt**：该 Event 取得正式 factual standing 的时间；
- **ProcessingTime**：某个下游 workflow 实际处理它的时间，属于 execution context，不应被误写成 occurrence time。

因此：

\[
OccurredAt \neq ReceivedAt \neq RecordedAt \neq ProcessingTime
\]

系统可以接受不精确的 OccurredAt，但必须保留不确定性或范围；不能为了排序方便把 ReceivedAt 伪装成 OccurredAt。

### 4.2 不存在全局总序

必须保持：

\[
RecordOrder
\neq OccurrenceOrder
\neq ProducerOrder
\neq CausalOrder
\]

Factual History 只保证其自身 append / commit history 可审计，不声称它就是“现实发生的唯一总序”。

不同 source 的时钟漂移、离线提交、批量同步、网络重试和 correction 都会破坏简单的 `ORDER BY created_at` 现实解释。

### 4.3 Correlation 不等于 Causality

关系字段必须分层：

- **Correlation**：这些 occurrence 在业务或运行上相关；
- **Temporal precedence**：A 在已知时间上先于 B；
- **Causality**：有明确依据声明 A 导致 / 触发 B；
- **Semantic dependency**：下游正式语义依赖某 Event；该责任属于 State / Dependency，而不是 Event relation 本身。

因此：

\[
Correlation \neq TemporalPrecedence \neq Causality \neq SemanticDependency
\]

CausalRef 只能在系统拥有明确机制依据时记录，例如某 `ActionOccurrence` 明确由某 `ActionIntent` 的执行产生；不能因为两个 learner 行为前后相邻就自动声明 causality。

### 4.4 Episode 与 Workflow Execution 不是同一概念

`EpisodeRef` 用于把现实交互事实组织进一个可理解的交互片段；`WorkflowExecutionRef` 用于关联内部运行流程。二者都只是 correlation / grouping identity，不是 semantic owner。

特别地：

\[
Episode \neq Session \neq TaskInstance \neq EvidenceOpportunity \neq Workflow
\]

Roadmap 不要求建立一个万能 Session 对象来承载所有关系。

`WorkflowCheckpoint` 也不因为引用 Event 就变成 epistemic state 或事实来源。

---

## 5. Factual Admission、Commit 与主要 Event Family

### 5.1 Factual Admission 是正式边界

一个外部或内部输入不能因为“到达系统”就自动成为 Event。合法路径为：

```text
Source Attestation
→ Factual Admission Request
→ Structural Validation
→ Source / Producer Identity Check
→ Factual Authority Resolution
→ Data Authority / Security Eligibility
→ Occurrence Identity / Dedup Check
→ Commit Factual Record
→ Event
```

Factual Admission 不执行 learner semantic interpretation。它只判断：

1. 该 occurrence 是否属于 DeerMind 需要长期保留的正式事实；
2. source 是否被授权对该类 occurrence 作 attestation；
3. identity、time、subject、payload / artifact 与 provenance 是否足以形成可审计事实；
4. 当前 Data Authority 与 Security 是否允许接收和保存该内容。

### 5.2 Event admission criteria

一个 occurrence 通常只有满足至少一种条件时才值得成为 Global Event：

- 它改变 learner-facing reality；
- 它是 learner / external actor 的重要输入；
- 它产生或终止某个正式运行约束；
- 它是 Action effect 的事实依据；
- 它会被 Observation / Evidence / Policy / Evolution 长期引用；
- 它对于 correction、audit、replay、security 或 governance 具有独立解释价值。

普通技术执行细节不因“发生过”就自动成为 Global Event。

### 5.3 Learner Work

`LearnerWorkSubmitted` 只证明：

> 某主体在某个 occurrence 中提交了某份 work / artifact。

它可以引用 task instance、artifact、input channel 与时间，但不能把下列结论编码进 Event：

- “答对了”；
- “理解了”；
- “使用了某种策略”；
- “独立完成”；
- “掌握了 KC”。

这些属于 Observation / Evidence / Belief。

### 5.4 External Input

External Input Event 必须保留：

- direct source；
- reported source（如有）；
- exact content / artifact；
- occurrence time；
- authority / provenance basis；
- channel / producer。

但：

\[
Request \neq Constraint \neq Obligation \neq AuthorityDirective
\]

Event 只记录“谁说了什么 / 提交了什么 / 声明了什么”；其是否构成 obligation、constraint 或 authority directive，由 Product Context / Context Constitution / downstream runtime interpretation 决定。

### 5.5 Target Binding occurrence

Target Binding 涉及三层责任：

1. **发生事实**：某 binding 被创建、终止、修改或某 authority source 作出相关 attestation —— 可形成 Event；
2. **合法 authority / scope**：由 Product Context / Context Constitution / Governance 解释；
3. **当前 effective binding projection**：由 Interaction / Current Resolution 形成。

因此 Factual Runtime 不能把“发生了 binding-related occurrence”直接等价为“该 binding 当前有效”。

### 5.6 ActionOccurrence

必须保持：

\[
ActionCandidate \neq ActionIntent \neq ActionOccurrence
\]

ActionOccurrence 只能在 **真实 effect crossing** 后产生。

执行链为：

```text
PolicyOutcome = Execute(ActionCandidate)
→ ActionIntent
→ Executor
→ Effect Boundary
→ ActionOccurrence | NotOccurred | Indeterminate
```

- `ActionIntent` 是被授权执行什么；
- `ActionOccurrence` 是效果确实穿过定义的现实边界；
- `NotOccurred` 表示确认未发生，不得创建虚假 occurrence；
- `Indeterminate` 表示当前无法确定是否发生，必须保留 reconciliation path。

### 5.7 Informational Action 的 effect boundary

对于 Hint、Explanation、Question 等 learner-facing informational action，首阶段可接受的最小 occurrence 边界是：

```text
Executor dispatch
→ client / presentation boundary confirms render
→ ActionOccurrence(Rendered)
```

但必须保持：

\[
Rendered \neq Perceived \neq Understood \neq Used
\]

如果只能确认服务端发送成功而不能确认 learner-facing presentation，就不能把“已显示”写成事实。

后续更强 client instrumentation 可以提高 factual precision，但不能修改以上语义边界。

### 5.8 Tool occurrence

必须区分：

\[
AIRuntimeToolUse \neq LearnerTaskToolUse
\]

AI Runtime 为 reasoning 调用搜索、计算或 retrieval tool，主要进入 ReasoningExecutionHistory；只有当该 tool use 本身构成 learner-facing reality、正式 external effect 或需要 Factual History 追踪的 occurrence 时，才进入 Global Event。

 learner 使用 calculator、code runner 或其他 Task Tool，则是否进入 Event 取决于它是否是正式学习 occurrence / assistance lineage 的事实组成部分。

---

## 6. Deduplication、Late Event、Correction 与 Current Factual View

### 6.1 传输可以 at-least-once，事实 Commit 必须 idempotent

DeerMind 不把 exactly-once delivery 当成架构不变量。更稳健的要求是：

\[
AtLeastOnceDelivery + IdempotentFactualCommit
\]

同一 occurrence 的 retry 不得生成多个独立 factual standing。

Admission 使用稳定 OccurrenceKey 进行去重。若相同 key 的重复输入在 payload 或关键 provenance 上发生冲突，不能简单“最后写入覆盖”，而必须进入显式冲突 / correction 处理。

### 6.2 Duplicate 与 independent repetition 分离

两个 Event payload 一样，可能代表：

- 同一 occurrence 的 retry；
- 两次独立、相同内容的 learner response；
- 不同 source 对同一现实 occurrence 的两份 attestation。

因此 dedup 只能基于 identity / source contract，而不能基于语义相似度。

### 6.3 Late Event 是合法路径

Late Event 不意味着过去历史被重写。它通过正常 append 取得 factual standing，并可能使已存在的 derived semantics 失去 current usability。

路径为：

```text
Late Event admitted
→ append to Factual History
→ dependency/currentness reevaluation
→ affected derived state becomes stale / invalid if required
→ asynchronous reinterpretation / recompute
```

Event 层本身不负责重算 Observation、Evidence 或 Belief，但必须提供足够 identity、time 与 provenance 让 State / Dependency 层完成影响分析。

### 6.4 Correction 使用新记录，不覆盖旧 Event

已 Commit 的 Event 不被原地修改。Correction 形成新的正式 record，并引用被纠正 Event：

```text
E1 = original Event
C1 = correction Event / factual correction record
C1.corrects = E1
```

历史上 E1 曾经存在这一事实仍然成立；C1 改变的是 E1 对当前事实解析的可用性。

因此：

\[
Correction \neq DeleteOriginal
\]

### 6.5 Fact Correction、Interpretation Correction 与 Semantic Reinterpretation 分离

三类修正不能混淆：

**Fact Correction** 说明 factual attestation 本身有误，例如错误 subject、错误 payload、重复 occurrence、错误 occurrence time。

**Interpretation Correction** 说明 Event 没错，但旧 Observation / Evidence 对它的解释错了。

**Semantic Reinterpretation** 说明在新的 canonical semantic version 下重新解释同一历史事实。

因此：

\[
FactCorrection
\neq InterpretationCorrection
\neq SemanticReinterpretation
\]

只有第一类属于本专项的 factual correction contract。

### 6.6 Raw Event History 与 Effective Current Factual View 分离

历史保存和当前使用不能混成一个概念：

\[
RawEventHistory \neq EffectiveCurrentFactualView
\]

- Raw Event History 保留 append-only records；
- Effective Current Factual View 根据 correction chain、retention availability、Data Authority 与 purpose 解析哪些 factual records 当前可作为 grounding。

被 correction 的 Event 仍可用于 Historical Audit，但不应继续被 current Observation 解释当作“未经纠正事实”。

### 6.7 Correction authority

Correction 本身也需要 factual authority。不能因为某个 downstream subsystem 认为旧 Event “看起来不对”就原地修改事实。

最低规则：

- source 可以在其授权 scope 内对自己的 attestation 提交 correction；
- 系统级 factual integrity mechanism 可以在明确定义的 authority 下标记 duplicate / malformed / misattributed record；
- Observation / Evaluation / Evolution 发现矛盾时只能提出 correction request / signal，不能直接获得 factual rewrite 权限。

---

## 7. 历史、Retention、Replay 与相邻运行契约

### 7.1 多类 History 必须分离

至少保持：

```text
Factual History
Reasoning Execution History
Semantic State History
Formal Commit / Effect History
Governance / Activation History
Data Access / Disposition Audit
Security Signal History
Operational Telemetry
```

Event History 不能吸收其他 History 的责任。

例如 `ReasoningExecutionRecord` 可以权威记录模型当时看到什么、输出什么 Candidate，但不能因为“发生过一次 reasoning”就自动成为 learner-world Event。

### 7.2 Historical Reconstruction 不能只依赖 Event

Historical Reconstruction 要回答“当时发生了什么、系统当时基于什么做了什么”。

它通常需要组合：

```text
Factual History
+ exact semantic versions
+ ContextManifest
+ ReasoningExecutionRecord
+ committed semantic revisions
+ Decision / Action records
+ authority / activation history
```

因此 Event History 是必要基础，但不是全部历史解释材料。

### 7.3 ReplaySupport 不等于无限期保留

必须保持：

\[
ReplaySupport \neq IndefiniteRetention
\]

某 Event 的原始 payload / artifact 可能因为 Data Authority、儿童数据政策、retention contract 或 deletion request 被合法删除。

删除后系统可以保留：

- Event identity；
- minimum provenance；
- cryptographic / content digest（若合法且有独立价值）；
- disposition record；
- historical references。

但不得伪装为仍可 FULL replay。

Replay capability 可以退化：

```text
FULL
→ PARTIAL
→ UNAVAILABLE
```

### 7.4 Replay capability 与 replay authorization 分离

即使历史 payload 仍存在，也不代表今天有权读取：

\[
ReplayCapability \neq ReplayAuthorization
\]

Historical existence 也不等于 current disclosure authority。

Data Authority resolver 必须在每次新的 replay / historical disclosure purpose 下重新判断当前授权。

### 7.5 与 State / Dependency Architecture 的接口

Event 作为 factual grounding 时，下游 Derived State 应保留 exact Event refs。

本专项提供：

- stable factual identity；
- correction chain；
- current factual eligibility signal；
- occurrence time / relation / provenance。

State / Dependency 专项负责：

- 哪些 Observation / Evidence / Belief 依赖该 Event；
- correction / late arrival 如何传播 stale / invalid；
- synchronous validity barrier；
- asynchronous recompute。

Factual Runtime 不维护一个“所有下游都有哪些依赖”的 authoritative push graph。

### 7.6 与 Interaction Runtime 的接口

Interaction 从 Event 形成 Observation，但不能改写 Event。

Interaction 输出 ActionIntent 后，Executor 的 effect result 进入 Factual Admission；只有成功跨越 effect boundary 才形成 ActionOccurrence。

这保证：

```text
Event → Observation → Decision → ActionIntent → ActionOccurrence → New Event
```

形成真正闭环，而不是把“系统想做什么”误当成“已经发生什么”。

### 7.7 与 Evaluation Runtime 的接口

Evaluation 可以通过 Observation / EvidenceBasis 引用 Event provenance、ActionOccurrence 与 assistance lineage，但不得：

- 绕过 Observation 建立第二套 Event interpretation；
- 用 Event source authority 替代 epistemic validity；
- 用 ActionOccurrence 直接证明 learning happened。

### 7.8 与 AI Reasoning Runtime 的接口

Event / Artifact 进入 AI Context 前仍需要：

```text
Purpose
→ Data Authority
→ Epistemic Admissibility
→ Validity / Currentness
→ Relevance
→ Minimum Sufficient Context
```

Event existence 不意味着 model visibility。

Reasoning Runtime 的 tool execution、model output、working memory 默认属于 execution provenance；只有满足 Factual Admission Criteria 的现实 occurrence 才进入 Global Event。

### 7.9 与 Version / Replay Architecture 的接口

Event identity 不随着 semantic version 变化而变化。新的 semantic version 可以对历史 Event 形成新的 Observation / Evidence revision，但不能回写旧 Event 的“新含义”。

因此：

\[
SemanticReinterpretation(Event@E1, Version@V2)
\not\Rightarrow
Rewrite(Event@E1)
\]

Event admission policy / producer protocol 本身可以 versioned，并进入 provenance，用于解释当时为什么允许该 record 取得 factual standing。

### 7.10 与 Security / Data Authority 的接口

Factual Admission 必须同时满足：

- factual authority；
- current data collection / persistence authority；
- source authentication / integrity requirement；
- payload / artifact security eligibility。

但：

\[
SecuritySignal \neq EmergencyAuthority
\]

发现可疑输入可以阻止 admission、限制 capability 或形成 SecuritySignal；不能因此自动扩大 Governance / factual rewrite 权限。

---

## 8. Failure、Recovery、Staging 与 Focused Design Closure

### 8.1 Factual Runtime 的主要 failure semantics

Factual Admission 至少需要区分：

| 结果 | 含义 |
|---|---|
| `Committed` | 新 occurrence 取得 factual standing |
| `Duplicate` | 已确认是同一 occurrence 的重投，不新增 standing |
| `Conflict` | 相同 occurrence identity 出现 incompatible attestation，需要显式处理 |
| `UnauthorizedSource` | source / producer 没有该类 factual attestation authority |
| `DataAuthorityDenied` | 当前不允许 collection / persistence |
| `MalformedAttestation` | identity / time / type / provenance 不满足最低事实合同 |
| `SecurityRejected` | 安全策略阻止 admission |
| `Indeterminate` | 无法确定 occurrence 是否真正发生，不能伪造 Event |

`Indeterminate` 特别适用于现实 effect 无法确认的 Action execution。

### 8.2 Recovery 不能制造 occurrence

服务重启、executor retry、network retry 都不能因为“恢复流程需要继续”就补造一个 Event。

必须保持：

\[
Restart \neq Reoccurrence
\]

以及：

\[
Recovery \neq FactualReplay
\]

恢复后若已有 durable ActionOccurrence，则读取已有事实；若只有 ActionIntent 而 occurrence 未知，则必须进入 reconciliation / indeterminate path，而不是再次执行后假装是同一个 occurrence。

### 8.3 最低一致性要求

Factual commit 是同步 correctness boundary：

- 同一 OccurrenceKey 的 duplicate / conflict 判定必须与 commit 保持一致；
- correction relation 在取得 standing 时必须引用可解析 target；
- source / authority / data authority / security 在 commit 时必须当前有效；
- append 成功后才对下游发布“该 Event 已取得 standing”。

这不要求全系统全局事务，也不要求所有 Event 严格顺序处理。

### 8.4 Capability staging

本专项遵循：

\[
Freeze\ Full\ Semantic\ Contract;
\qquad Stage\ Runtime\ Capability
\]

**S0 — Architecture Contract Mandatory**

当前 v0.1 已冻结：identity、authority、time、admission、dedup、ordering、correction、late event、ActionOccurrence、history / retention / replay boundary。

**S1 — Consolidated Spike Required**

共享 Harness 至少需要实现：

- in-memory FactualHistory；
- stable OccurrenceKey；
- duplicate admission；
- append-only correction；
- late event；
- ActionOccurrence；
- source / authority rejection；
- Event refs 可被 downstream dependency 使用。

**S2 — Minimal Simulation Allowed**

可以 hardcode / mock：

- retention policy；
- data disposition worker；
- external source authentication；
- producer protocol registry。

**S3 — Deferred**

允许延后：

- 生产级 Event Store；
- partition / sharding；
- cross-region replication；
- archival tiering；
- high-throughput ingestion；
- full disaster recovery。

这些延后不得改变本文件的 semantic contract。

### 8.5 本专项的文档封装判断

本专项判定为：

```text
SEPARATE
```

理由不是“Roadmap 预先列了一个文件名”，而是 Runtime & Event Architecture 同时承担 identity、authority、time、ordering、admission、correction、ActionOccurrence、history / retention / replay 等多个长期独立责任；这些内容若全部塞回总体 System Design，会破坏主文档的系统地图作用，并使事实层与其他专项的边界难以维护。

因此独立文档的复杂度具有不可替代价值。

### 8.6 Focused Design Closure 判断

截至 v0.1，本专项在 **语义设计层** 达到 Focused Design Closure Candidate：

```text
Core Objects / Identity                 CLOSED
Factual Authority                      CLOSED
Event Admission / Commit               CLOSED
Time / Ordering / Correlation          CLOSED
Dedup / Idempotency                    CLOSED
Late Event / Correction                CLOSED
ActionOccurrence Boundary              CLOSED
History / Retention / Replay Boundary  CLOSED
Adjacent Work-Package Interfaces       CLOSED
Physical Persistence / Scaling         DEFERRED
Engineering Validation                 UNVALIDATED
```

这意味着实现团队不应再需要重新决定“Event 是什么、谁有资格写、怎样识别同一 occurrence、什么时候算 Action 已发生、怎样修正历史、late event 怎么进入系统、Event 与 Observation / Evidence / Replay 的边界是什么”。

仍未冻结的是物理 persistence、索引、分区、消息基础设施和生产级 scale，这些属于 ADR / implementation design，而不是本专项的语义缺口。

### 8.7 相关验证责任

本专项不新增新的 Validation Dimension。其关键假设由现有 Consolidated Spike 维度共同覆盖：

- Dimension B：late event / correction 与 downstream invalidation；
- Dimension C：historical reconstruction、retention 与 replay completeness；
- Dimension D：ActionOccurrence / disclosure lineage；
- Dimension F：source authority、untrusted input 与 security provenance。

Spike 若否定某项实现假设，应优先修订 focused design 或 ADR；只有证据证明 factual invariant 本身不可实现或与上位架构冲突时，才形成 Architecture Reopen Candidate。

### 8.8 ADR 与下一步

当前保留以下实现级 ADR Candidate，不在本文档提前冻结：

- Event / Factual History 物理持久化模型；
- OccurrenceKey 在不同 producer 下的工程编码方式；
- duplicate index / conflict detection 的物理实现；
- Event retention / archival / deletion 的 storage strategy；
- cross-region factual replication；
- Event publication 与 downstream consumption 的 delivery mechanism。

本专项完成后，Phase 4 继续进入 Roadmap §3.3：

```text
AI Reasoning Runtime Architecture
```

若后续专项深化发现必须修改本文件冻结的事实合同，应形成 v0.x 新 revision，并同步检查 `DeerMind_System_Design_v0.x` 是否需要修订。

---

## Appendix A — Runtime & Event Invariant Registry

| ID | Invariant |
|---|---|
| **RE-01** | `Event = Authorized Attestation of an Occurrence`；Event 不声明 World Truth。 |
| **RE-02** | `Event != Observation != Evidence != Belief`。 |
| **RE-03** | `EventIdentity != OccurrenceIdentity`。 |
| **RE-04** | `ActorIdentity != FactualAuthority`。 |
| **RE-05** | `FactualAuthority != SemanticAuthority != PolicyAuthority`。 |
| **RE-06** | 已 Commit Event immutable；修正通过新 factual record 表达。 |
| **RE-07** | `SamePayload not=> SameOccurrence`；payload equality 不能作为 dedup identity。 |
| **RE-08** | `RecordOrder != OccurrenceOrder != ProducerOrder != CausalOrder`。 |
| **RE-09** | `Correlation != TemporalPrecedence != Causality != SemanticDependency`。 |
| **RE-10** | At-least-once transport 合法；Factual Commit 必须 idempotent。 |
| **RE-11** | `SelectedAction != ActionIntent != ActionOccurrence`。 |
| **RE-12** | `Rendered != Perceived != Understood != Used`。 |
| **RE-13** | `RawEventHistory != EffectiveCurrentFactualView`。 |
| **RE-14** | `FactCorrection != InterpretationCorrection != SemanticReinterpretation`。 |
| **RE-15** | Late Event append，不重写过去记录。 |
| **RE-16** | `FactualHistory != ApplicationLog != OperationalTelemetry`。 |
| **RE-17** | `ReplaySupport != IndefiniteRetention`。 |
| **RE-18** | `ReplayCapability != ReplayAuthorization`。 |
| **RE-19** | `Restart != Reoccurrence`；Recovery 不得制造 occurrence。 |
| **RE-20** | AI Runtime tool execution 默认属于 execution history，不自动成为 learner-world Event。 |

---

## Appendix B — Core Factual Object Responsibility Matrix

| Object / Record | Standing | Owner / Authority | Identity | Currentness | Downstream Role |
|---|---|---|---|---|---|
| Event | Factual | authorized factual producer + admission | EventId + OccurrenceKey | correction / eligibility resolution | Observation grounding、audit、replay |
| ExternalInput Event | Factual | source-specific factual authority | occurrence-specific | does not imply directive currentness | Interaction / Context interpretation |
| LearnerWorkSubmitted | Factual | learner/input factual authority | submission occurrence | immutable, may be corrected | Observation grounding |
| ActionIntent | Runtime execution authority | Interaction | intent id | expiry / precondition sensitive | Executor input；不是 Event |
| ActionOccurrence | Factual | executor / client-confirmed factual authority | action occurrence id | immutable, may be corrected | new reality / Exposure grounding |
| Factual Correction | Factual correction | correction authority | correction occurrence id | changes target Event current factual eligibility | invalidation trigger |
| ReasoningExecutionRecord | Execution history | AI Runtime | execution id | historical | provenance；不是 learner-world fact |
| WorkflowCheckpoint | Execution state | workflow runtime | workflow execution id | resumability-specific | recovery；不是 epistemic/factual SoT |
| SecuritySignal | Security history | security detection contract | signal id | security lifecycle | containment / audit；不创造 authority |

---

## Appendix C — Admission Decision Matrix

| 输入 | 是否自动成为 Event | 最低判断 |
|---|---:|---|
| Learner work submission | 是，满足 admission 后 | source、occurrence identity、artifact、time、authority |
| Parent / external message | 是，若具有正式交互意义 | direct / reported source、content、authority、data authority |
| AI model output | 否 | Candidate / execution record；除非另有现实 occurrence |
| Tool call issued by AI | 否 | execution history；若产生现实 effect，再由 effect admission |
| Client-confirmed learner-facing render | 可以 | ActionIntent 关联、effect boundary、occurrence identity |
| Server dispatch success | 通常否 | 不能证明 learner-facing render |
| Policy selected ActionCandidate | 否 | 只是 decision candidate |
| ActionIntent committed | 否 | 只是被授权执行，不证明发生 |
| Database retry / cache miss | 否 | operational telemetry，除非跨越正式语义边界 |
| Target Binding created / terminated | occurrence 层可以 | 记录发生事实；current legality 由 authority / Interaction 解析 |
| GovernanceDecision | 作为 governance formal record；是否同步投影为 Global Event 由后续实现决定 | 不得以 Event 替代 Governance authority record |

---

## Appendix D — Open Implementation Decisions

以下不是语义 UNKNOWN，而是明确留给 ADR / implementation design 的工程选择：

- Event Store 物理模型；
- event index 与 dedup index；
- stream / partition 划分；
- 同步写入与异步 publication 的实现；
- message broker 是否存在；
- retention tier 与 object storage strategy；
- cross-region factual replication；
- event schema serialization；
- artifact storage 与 payload encryption；
- occurrence identity 的具体生成算法。

这些选择若未来证明会改变 factual semantics，而不仅是工程 enforcement，则必须回到本文件重新评审，而不能通过实现细节静默改变事实合同。
