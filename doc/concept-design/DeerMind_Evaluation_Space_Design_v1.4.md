# DeerMind Evaluation Space Design v1.4

> **版本**：v1.4<br>
> **中文名称**：DeerMind 评估空间设计<br>
> **文档性质**：Space Design / Architecture Baseline<br>
> **状态**：阶段性语义结论已纳入正式设计；本轮未新增实证或阶段 Gate 结论<br>
> **上位基线**：DeerMind Concept Architecture v1.4<br>
> **上位领域基线**：[DeerMind Domain Space Design v1.2](DeerMind_Domain_Space_Design_v1.2.md)；[Learning Space v1.2](DeerMind_Learning_Space_Design_v1.2.md)<br>
> **上位价值约束**：DeerMind Product Thesis v1.0、DeerMind Product Constitution v1.0<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：本轮模型及修改范围由用户确认；文档检查不代表模型效果或 Gate 通过<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-19<br>
> **修订说明**：定义默认四维、Claim 映射、裁剪扩展及未知边界，增加运行关系图；修正原先默认不拆迁移命题的含混说明，区分实际条件与所评能力；用分数应用 C1–C4 明确四维命题和逐步证据更新，补充联合探针归因限制；明确跨空间四维规范归属；同步架构决策；区分已决定框架与待验证问题；同步检查清单；同步证据检查；补充语义不变量；更新本版变更说明；更新当前下游传导说明；更新本版修订记录引用；同步现行交叉引用和导航。逐文件变更见[修订记录 §10](DeerMind_Learning_Model_Reassessment.md#10-默认四维评价框架的正式修订记录)。

---

## 1. 文档定位与设计命题

Evaluation Space 解决的不是“给学习者打一个分数”，也不是维护一个越来越复杂的学习者画像。它面对的是一个更基本的问题：**DeerMind 永远无法直接读取学习者真实的认知状态，却必须根据有限、受条件影响、可能互相冲突的行为证据，形成长期、可修正的能力认识。**

Domain Space v1.2 提供任务模板、方法与 KC；Learning Space v1.2 提供 LearningTarget、范围和支持责任。Evaluation 需要判断具体表现支持哪个条件性命题，区分未达目标与证据不足，并保证模型映射变化不会被误当成真实学习变化。

Evaluation 仍然是 DeerMind 的**学习者认识层**。它维护的是系统对学习者的可修正认识，而不是学习者真实状态本身，也不是 Learning Target 的规范要求。

\[
\boxed{
EvaluationSpace
=
LearnerStateModel
+
EvidenceModel
+
InferenceModel
}
\]

三个 Model 分别回答三个不可互换的问题：

| Model | 核心问题 |
|---|---|
| Learner State Model | DeerMind 允许对学习者维护什么类型的 Claim 与 Learner Belief？ |
| Evidence Model | 某个 Observation 在特定条件与责任边界下，对一个明确 Claim 具有什么证据意义？ |
| Inference Model | 综合相关证据后，当前应该维持怎样的 Learner Belief，以及这些 Beliefs 是否足以支持某个 Target requirement？ |

它们共同形成：

\[
Observation
\rightarrow
ClaimSpecificEvidence
\rightarrow
Inference
\rightarrow
LearnerBelief
\]

Target Assessment 则建立在正式 Target Definition 与当前 Learner Beliefs 之上，是跨 Space 派生认识，不属于新的 Learner State。

### 1.1 本文档解决什么

本文档定义 Evaluation Space 的稳定语义责任，包括：

- 学习者命题与 Learner Belief 的最小规范结构；
- Task Claim 作为唯一核心学习者命题类型，KC 保留领域解释与教学作用；
- Conditions、Support / Responsibility Boundary 与 Quality Requirement 如何进入能力 Claim 或 Evidence Context；
- Observation 如何在明确 Claim 下形成 Evidence；
- Assistance、Delayed、Transfer、Missing Evidence 等条件如何改变一次表现的认识意义；
- 多条证据如何在依赖、时间和冲突条件下被综合；
- UNKNOWN、不确定性、Epistemic Status 和 Evidence Basis 的语义；
- Target Assessment、Target Gap 与 Epistemic Gap 的派生关系；
- Equal Epistemic Standing、Population Prior 与 Authority Override 对 Evaluation 的约束；
- Evaluation 与 Domain、Learning Space、Interaction、Global Event Model 和 Evolution 的边界；
- Evaluation 如何被现实挑战、版本化和重新解释。

### 1.2 本文档不解决什么

Evaluation Space 不负责：

- 定义 Learning Target、Task、Solution、KC 或 Support / Responsibility Boundary 等规范领域语义；
- 决定谁正在追求某个 Target、为什么追求、优先级或截止时间；
- 从原始 Event 直接解释当前表现；
- 决定现在是否应该提示、解释、等待、停止或主动测评；
- 把疲劳、当前意愿、情绪等运行条件写成长期能力；
- 把 Target Assessment 变成新的 `TargetBelief` 或 `TargetMasteryBelief`；
- 把 Assistance Dependency 变成稳定人格或长期 trait；
- 决定 Evaluation 模型自身是否应正式变更；
- 规定最终使用 Bayesian、IRT、neural estimator、规则系统还是其他具体算法；
- 规定 Belief、Evidence 或 Target Assessment 的数据库 schema、服务边界或 API。

这些内容分别属于 Domain Space、Interaction Space、Product Context、Evolution、Governance 或后续 System Design。

### 1.3 上位边界

根据 Concept Architecture v1.4，Domain 提供领域定义，Learning Space 提供材料与目标规范；Evaluation 形成对学习者的可修正认识；Interaction 使用这些认识、当前 Context 与现实约束做行动决策。必须长期保持：

\[
Requirement
\neq
Evidence
\neq
Belief
\]

以及：

\[
Only\ EvaluationSpace\ may\ revise\ LearnerBelief
\]

Target Requirement 可以规定“学习者应当在条件 C、支持边界 S 下达到质量 Q”，但它不能据此产生“学习者已经具备该能力”的 Evidence 或 Belief。Target Assessment 只能建立在正式 Target Requirement 与已经形成的 Learner Beliefs 之上。

当前疲劳、意愿、注意残余等交互周期内条件可以由 Interaction 维护；外部考试、教师、家长、雇主、认证机构或学习者自己的陈述都只能成为事实、Observation 或 Evidence 的来源。制度 authority、群体统计或安全限制都不能绕过 Evidence / Inference 直接改写 Learner Belief。

## 2. 设计问题与基本约束

Evaluation Space 的结构来自几个不可消除的现实限制。理解这些限制，比记住后面的对象名称更重要。

### 2.1 学习者真实状态不可直接观察

DeerMind 只能看到行为和结果，而不能读取“真实掌握度”。同一个正确答案可能来自独立能力、模仿、提示、猜测、答案暴露或特殊上下文；同一个错误也可能来自粗心、算术 slip、任务理解错误或系统 Observation 错误。

因此：

\[
LearnerReality
\neq
SystemBelief
\]

Learner Belief 必须始终被理解为 DeerMind 当前的认识立场，而不是学习者真实状态的复制品。

### 2.2 行为不能直接变成 Belief

一次表现首先需要被 Interaction 解释成 Observation；只有当 Observation 被放到明确学习者命题下，才能讨论它是否构成 Evidence；多条 Evidence 还需要经过 Inference，才可能改变 Learner Belief。

\[
\boxed{
Event
\neq
Observation
\neq
Evidence
\neq
Belief
}
\]

这条分层防止系统把自己的解释写回事实，也防止“答对 → 掌握”“提示后成功 → 已会”“家长说不会 → Belief 下降”等捷径。

### 2.3 没有 Claim，就没有合法 Belief

“这个学习者数学不行”“理解能力弱”“自信心不足”这类模糊结论很难被证伪，也很容易变成永久标签。Evaluation 只允许对具有明确语义、可观察证据和实际决策价值的 Claim 形成 Belief。

\[
NoBeliefWithoutClaim
\]

同理，Evidence 也必须指向明确 Claim：

\[
NoEvidenceWithoutClaim
\]

### 2.4 模型复杂度不能超过可观测性

如果两个学习者构念无法通过现实数据稳定区分，就不应因为理论上“可能存在”而都进入规范 Learner State。模型越复杂，对 Evidence 质量、数据量和推断假设的要求越高。

因此 Evaluation 采用：

\[
ModelComplexity
\le
Observability
\]

以及：

\[
ModelResolution
\le
DecisionResolution
\]

更细的 diagnosis 只有在能够改变重要 Belief 或 Interaction 决策时才值得。

### 2.5 Evidence，不是 Command

学习者、家长、教师、学校、认证机构、雇主、外部测评和 DeerMind 自身教学动作都可以影响系统认识，但都不能直接写 Learner Belief。

外部主体可以拥有真实制度 authority，却不因此拥有对 learner capability 的直接认识写入权：

\[
ExternalAuthority
\neq
EpistemicAuthority
\]

同样，安全、监护、组织政策或制度要求可以限制当前允许执行什么，但这种限制不是关于学习者能力的 Evidence：

\[
AuthorityOverride
\neq
EpistemicEvidence
\]

### 2.6 Condition 默认属于 Evidence；只有改变 Claim 语义时才进入 Claim

Assistance、Delayed、Transfer、疲劳、环境噪声、工具可用性等条件通常改变的是一次表现“能证明什么”，而不是自动创造新的 Learner State。

因此默认规则是：

\[
EvidenceCondition
\neq
ClaimCondition
\]

只有当某个条件或 Support Boundary 真正改变“我们究竟在断言哪一种能力”时，它才进入 Claim semantics。例如“在 AI 提供候选诊断时能够验证并决策”和“在没有 AI 诊断候选时独立形成 root-cause 判断”是不同能力命题；而“今天很疲劳”通常只是 Evidence Context。

这条原则防止状态空间按照条件组合无限膨胀，同时允许 Target Responsibility Boundary 在真正改变能力含义时成为 Claim 的一部分。

### 2.7 Population Prior 不能替代 Individual Evidence

Product Constitution 要求每个学习者保有平等认识地位。Evaluation 可以使用与当前学习问题相关、经过治理允许的群体统计作为受限 prior 或假设来源，但不能把它直接写成对具体学习者的 Evidence 或 Belief。

必须保持：

\[
PopulationPrior
\neq
IndividualEvidence
\]

以及：

\[
GroupExpectation
\not\Rightarrow
IndividualCapabilityClaim
\]

当真实个体 Evidence 与 prior 冲突时，Inference 必须允许 prior 被修正，而不能通过持续降低反证权重来保护既有判断。

### 2.8 模型解释失败时，不先发明学习者特征

当现实数据与现有 Claim、Evidence 或 Inference 模型不一致时，最危险的做法是创造新的学习者 label 来吸收异常。例如学习者在 verbal 表示上成功、在 table 表示上失败，并不能自动推出一个新的 `RepresentationAbility` 特征。

更合理的路径是先保留冲突，形成临时推断假设，再检查 Task granularity、KC Application Conditions、Observation、Target Conditions 与 Evidence 语义是否过粗。

\[
ModelMismatch
\not\Rightarrow
CreateNewLearnerTrait
\]

## 3. Evaluation Space 的核心架构

Evaluation 的三个 Model 不是算法模块，而是三类不同的认识责任。它们可以在软件实现中共享基础设施，也可以由多种算法共同实现，但语义边界不能合并。

```mermaid
flowchart LR
    O["Observation\nfrom Interaction"]
    E["Evidence Model\nClaim-specific meaning"]
    I["Inference Model\nIntegrate evidence"]
    B["Learner State Model\nCurrent belief"]

    O --> E --> I --> B
    B -. "prior belief" .-> I
```

### 3.1 Learner State Model：定义 DeerMind 可以相信什么

Learner State Model 定义值得持续维护的个人能力命题。当前只保留 **Task Claim**，规范标识沿用 `TaskProficiencyClaim`；其个人状态为 `TaskProficiencyBelief`。这不是旧 TaskFamily 本体的恢复，也不是把一次任务结果当作能力。

\[
LearnerClaimSpace=\{TaskProficiencyClaim\},\qquad
LearnerStateCore=\{Belief(Learner,LearningSpace,ClaimVersion)\}
\]

一个 Task Claim 表达：学习者在明确任务范围、条件、方法要求和支持边界下，能否相对稳定地承担指定认知或行动责任，并满足相应质量要求。其语义至少包含下表；不要求提前固定为数据库字段。

| 语义部分 | 必须说明的内容 |
| --- | --- |
| TaskScope | 一个或多个明确版本的 TaskTemplate，参数、情境、表征及排除范围 |
| Responsibility | 求解、解释、选法、构造或检查等实际评价责任；未要求的责任不能随意加入 |
| MethodRequirement | 允许的方法范围，以及任选、指定或多个方法分别覆盖的含义 |
| Conditions / SupportBoundary | 环境、工具及哪些工作必须由学习者自行承担；实际帮助另记 Evidence Context |
| QualityRequirement | 正确性、说明质量和所声明的稳定、迁移或保持范围；证据充分性与阈值须有版本和依据 |

TaskTemplate 与 Claim 不必一一对应。同一模板可以支持求解和解释两个不同命题，一个命题也可以覆盖有依据的一组模板。只有差异具有独立证据和教学决策价值时才持续维护；不为每道题、每个子任务、每种方法或每个 KC 自动建立状态。

**方法覆盖。** 纳入方法 A、B 可得到两者所关联 KC 的课程覆盖范围，但不自动规定每次表现必须经过两条路径。允许任选时，实际采用 A 可以支持任务完成，不支持“会用 B”；指定 B 时必须有 B 的适用表现；要求 A、B 均掌握时，证据须分别覆盖，不要求每题重复两遍。比较与选择方法是另一个责任，不能由分别会执行自动推出。覆盖记录由 Evidence 派生，不增加一套 Solution 掌握状态。

**知识层的保留与降层。** KC 的定义、关系和方法 grounding 仍由 Domain 维护；Observation / Evidence 可关联 KC，用于解释具体表现、设计讲解和取证。Evaluation 不再创建、更新或作为 current-valid 能力输入返回 KCClaim / KCBelief，也不能把带 KC 标签的临时分析累计成隐藏的知识掌握库。理解知识的目标通过有范围、可观察责任的 Task Claim 表达，不给全部 KC 机械改名。

**证据与状态的区别。** 一次成功可能受到提示、工具、模仿或偶然因素影响。正确结果支持哪项责任，必须看实际表现；未要求解释不能当作不会解释，Task 成功也不自动表示全部方法或知识已掌握。重复题、刚接受相关讲解和不同表征等条件先进入 Evidence Context；只有真正改变能力命题才另立 Claim。

**简化的代价。** 当前不维护独立跨任务 KC 掌握状态；诊断和教学仍可使用具体表现及知识依据。若 Task Claim 无法表达重要决策差异，或新增知识层状态确有独立证据、预测与行动价值，再通过受治理模型修订调整。动机、疲劳、帮助依赖等也不因可能有用就自动进入稳定状态。

**默认四维评价框架。** 对一组有教学意义的 TaskScope，默认从独立完成、理解与解释、迁移应用、延迟保持四个维度定义需要认识的能力。默认覆盖作用于任务范围及其目标要求，不要求每个模板、每个子任务或每道题各建四个状态，也不要求每轮互动检测全部维度。

| 默认维度 | Task Claim 必须表达的责任与条件 | 不能据此自动推出的结论 |
| --- | --- | --- |
| 独立完成 | 在明确允许的工具和支持边界内，自行承担关键判断、操作或求解责任，并达到质量要求；独立不等于禁止一切工具 | 一次答案正确不证明独立；独立完成熟悉任务不证明理解、迁移或保持 |
| 理解与解释 | 解释关系、理由或适用边界，或通过图示、辨析、操作与反例等表现显示理解；明确所需内容及帮助边界 | 复述解析、语言流利或只给正确结果不等于理解；未要求表达不能判为不会解释 |
| 迁移应用 | 明确参照任务及学习经历、变化了哪些情境／表征／条件，以及变化后仍须承担的责任和质量 | 仅换数字、做过同类题不自动证明迁移；一次指定变化的成功不证明任意泛化 |
| 延迟保持 | 明确要保持的责任、先前表现依据、观察间隔和可比条件；记录期间练习、帮助及资料可得性 | 当场完成或时间流逝不证明保持；期间强化后的成功不证明无强化保持，也不等于永久掌握 |

这些维度是 DeerMind 当前采用的通用设计框架，不是已验证相互独立、穷尽所有领域的四个心理测量因子。独立性同时约束其他维度的表现：例如迁移 Claim 可以明确要求独立迁移；保持 Claim 必须说明保持的是求解、解释还是其他责任，不能笼统写“能力持久”。正确性和适用质量同样贯穿各维度。

**维度与 Claim 的对应。** 维度不新增 Learner State 类型。每项采用的维度必须能追溯到一个或多个条件明确的 Task Claim；一个 Claim 也可承载有关联的维度。若需要分别回答“能独立完成，但尚不知道能否迁移”，应有可分别推断的 Claim，不能从一个合取命题的总判断虚构分项 Belief。复合 Claim 只支持其整体命题；需要分项认识时，定义有独立判断价值的相应命题。不机械枚举四维的全部组合，也不为每个间隔、表征或 KC 自动拆出状态。

**采用、裁剪与扩展。** Evaluation 定义通用框架与 Claim 语义；Learning Space 的目标定义说明在所选 TaskScope 中采用哪些要求。规范内容须保存以下覆盖记录，作为 Claim 与目标定义的版本化组成，而非新增核心模型：

- 每个默认维度的采用情况、适用任务范围、对应 Claim 和目标要求；解释形式、迁移变化及保持责任／间隔须具体化。
- 裁剪的理由、适用边界、对可宣称能力及目标达成的影响、决定者和审核／发布版本。单一表现机会不适合检测某维度，不代表整个目标可以裁剪该维度。
- 扩展维度的定义、可区分的证据及教学决策价值；效率、精度、协作等先判断能否由现有 Claim 的责任和质量要求表达，再决定是否需要额外命题。

裁剪必须有领域或目标依据，不能因为学习者表现差、证据难收集、观察时间未到或实现尚未完成而改成“不适用”。运行中的 LLM 可以提出修订候选，不能自行修改正式覆盖记录。首版管理员可兼任编辑、审核和发布者，但各项依据和版本仍须保留；重要范围改变遵循既有产品决策权限。

**定义与认识状态分开。** 已采用但尚未定义清楚对应 Claim 是内容准备缺口；Claim 已定义但尚未取得足够证据是认识不足。两者均不能被静默裁掉。经批准不适用属于规范适用性；未测、证据不足和保持观察时点未到属于认识或取证条件，不是能力失败。多个维度的判断不得简单平均为掌握率；同一表现支持多个 Claim 时必须保留共同来源，不能当成多份独立证据来增强置信度。

```mermaid
flowchart TB
    F["默认四维评价<br/>独立完成 · 理解与解释<br/>迁移应用 · 延迟保持"]
    G["按任务范围与目标确定采用<br/>有依据的裁剪与扩展，保留版本"]
    C["条件明确的 Task Claim<br/>统一类型，按判断需要定义命题"]
    O["实际表现与帮助<br/>变化条件、时间及历史来源"]
    E["相对于 Claim 解释 Evidence"]
    B["Evaluation 更新各 Claim 的 Belief"]
    T["与目标要求比较"]
    F --> G --> C --> E
    O --> E --> B --> T
    G -. "目标要求" .-> T
```

图中覆盖记录和 Claim 的定义／发布发生在受治理规范路径；实际表现不会自动发布新的 Claim。四维框架与 §4 的 Belief 四个组成部分处于不同层次：前者规定评什么，后者描述对每个命题相信什么、存在何种不确定性及依据。

### 3.2 Evidence Model：定义 Observation 对 Claim 意味着什么

Evidence Model 不负责形成最终 Belief。它只回答一个局部问题：

> **某个 Observation，在当前 epistemic context 和 Domain Space 语义下，对一个明确 Claim 有什么认识论意义？**

\[
\boxed{
Evidence
=
Interpret(
Observation,
Claim,
EpistemicContext,
DomainSemantics
)
}
\]

Evidence 是一种相对于命题的关系，而不是脱离 Claim 独立存在的“证据分数”。

同一个 Observation 可以针对不同 Claim 形成不同 Evidence。例如学习者在比例题中选择了正确的 Unit Rate 策略，却把 `42÷6` 算错：

- 对“独立组织并正确完成本范围比例任务”的 Task Claim，形成反向证据；
- 若已有“独立建立单位量关系”的 Task Claim，实际列式可形成正向证据；
- 除法位置的错误保留为局部表现及知识关联；只有存在已定义、适用的计算 Task Claim 时才另作评价，不临时建立 Division KC 掌握状态。

因此：

\[
OneObservation
\rightarrow
MultipleClaimSpecificEvidenceRelations
\]

Evidence Relation 至少需要区分：

| Relation | 语义 |
|---|---|
| Supports | Observation 支持 Claim |
| Contradicts | Observation 反驳 Claim |
| Discriminates | 主要用于区分 competing hypotheses |
| NonInformative | 对该 Claim 没有足够信息价值 |

这套结构不要求 System Design 最终必须用离散枚举实现，但概念上必须保留这些不同认识作用。

### 3.3 Inference Model：决定当前应该相信什么

Inference Model 综合先验信念、历史与当前 Evidence、Evidence 依赖、时间结构以及模型假设，形成新的 Learner Belief。

\[
B_{t+1}
=
Infer(
B_t,
Evidence_{1:t},
Dependencies,
Time,
ModelAssumptions
)
\]

Evidence 与 Inference 必须分离。相同 Evidence 面对不同先验，可能产生不同信念 update；相同先验面对不同 Evidence 语义，也可能产生不同结果。

Inference 的核心职责不是“算一个 mastery score”，而是保留 Evidence 的依赖、冲突、时间相关性和模型不确定性，使系统知道自己为什么相信、为什么犹豫，以及什么新信息可能真正改变判断。

---

## 4. Learner Belief：可修正认识，而不是分数

当前所有正式 Learner Belief 都针对 Task Claim。一个合法 Learner Belief 是：

> **DeerMind 在某一时刻，基于当前可用 Evidence，对一个明确 Learner Claim 所持有的、可追溯、带不确定性、可被未来 Evidence 修正的认识论立场。**

概念上：

\[
\boxed{
Belief_t(C)
=
(
Assessment_t,
EpistemicUncertainty_t,
EpistemicStatus_t,
EvidenceBasis_t
)
}
\]

这是一项语义定义，不是数据库 schema，也不要求某一种概率表示。

### 4.1 Assessment：方向性判断

Assessment 回答：

> 综合当前 Evidence，DeerMind 对 Claim 的方向性判断倾向是什么？

当前架构只冻结 Assessment 的语义，不冻结数值表示。System Design 可以比较 ordinal、probability、interval、分布或其他 calibrated 表示，只要它们保留这里定义的认识论含义。

\[
AssessmentSemantics\ first,
Representation\ deferred
\]

### 4.2 UNKNOWN：证据不足，不是 0.5

UNKNOWN 表示当前 Evidence 不足以支撑有根据的方向性判断。

\[
UNKNOWN(C)\neq \neg C
\]

同时：

\[
UNKNOWN\neq 0.5
\]

“没有足够证据”与“证据正反各半”是两种完全不同的认识状态。前者要求更多有信息价值的观察，后者可能需要区分竞争性假设或重新检查模型。

### 4.3 Epistemic Uncertainty：系统对自己判断的不确定性

Epistemic Uncertainty 属于 DeerMind，而不是学习者。

\[
LearnerSelfConfidence
\neq
SystemEpistemicUncertainty
\]

学习者自述“我很有把握”本身可以成为 Observation / Evidence；系统对当前 Belief 有多大把握则属于另一层。

### 4.4 Epistemic Status：为什么不确定

一个不确定性 scalar 无法解释原因。高不确定性可能来自：

- Evidence 稀缺；
- Evidence 冲突；
- Observation 歧义；
- 证据 currentness concern；
- 模型失配。

Epistemic Status 用于表达这种结构。多个原因可以同时存在，因此当前不把它冻结成互斥 enum。

这一信息很重要，因为不同不确定性来源对 Interaction 的意义不同。Evidence 稀缺可能需要新的 observation opportunity；Evidence 冲突可能需要更有区分力的任务；模型失配则可能产生 System Signal。

### 4.5 Evidence Basis：每个 Belief 都必须可以回答“为什么”

任何重要 Learner Belief 都必须能够追溯到形成它的 Evidence：

\[
Belief
\rightarrow
EvidenceBasis
\rightarrow
Observation
\rightarrow
Event
\]

这使 DeerMind 能够在 Observation 被修正、Evidence 语义被更新或规范版本发生变化后，定位受影响的 Belief，并重新推断。

\[
\boxed{
NoOpaqueLearnerBelief
}
\]

### 4.6 Belief 的时间语义

时间流逝本身不是负 Evidence。

\[
TimePassage
\not\Rightarrow
CompetenceDecrease
\]

如果很久没有新 Evidence，首先增加的是对当前状态是否仍然有效的不确定性，而不是自动降低能力评估。

\[
CurrentnessUncertainty\uparrow
\]

只有存在新的 Evidence，或已经通过现实验证的 learning / forgetting transition 模型，系统才可以做方向性能力 revision。

\[
NoDirectionalCompetenceRevision
Without
NewEvidence
Or
ValidatedStateTransitionModel
\]

---

## 5. Evidence 与 Inference：决定一次表现能证明什么

Evaluation 的真正难点不在保存 Belief，而在于避免系统把受条件影响的表现错误地当作独立能力证据。Assistance、Delayed、Transfer、Missing Evidence、Evidence 依赖、Freshness 和 Conflict 都属于这一问题的不同侧面。

### 5.1 Evidence 是结构化关系，不是先压成一个数字

概念层不建立统一的：

\[
EvidenceStrength=0.83
\]

因为 evidential 价值至少可能依赖：

- Claim relevance；
- Observation 质量；
- 帮助 / 信息暴露；
- diagnosticity；
- 任务 / 过程轨迹覆盖度；
- temporal 关系；
- 迁移 / novelty 关系；
- 溯源信息。

System Design 可以为具体推断 algorithm 设计数值表示，但不能因此丢掉这些结构差异。

### 5.2 Assistance：关键不是“用了工具”，而是是否替代 Claim 要求的责任

Independent / Assisted 不属于 Learner State，也不是天然高低排序的两套 Belief。一次帮助是否削弱 Evidence，取决于它是否替代了当前 Claim 要求由 learner 自己承担的认知或行动责任。

因此真正关键的是：

\[
ClaimSubstitutingAssistance
\]

Evaluation 在解释 assistance 时至少需要区分三层语义：

1. **Task Canonical Tool Semantics**：Task 在领域上允许或要求哪些工具；
2. **Claim / Target Responsibility Boundary**：当前能力命题要求 learner 自己承担什么；
3. **Actual Exposure / Tool Use**：这次运行中真实发生了什么。

例如，日志与监控可能是诊断 Task 的正常工具；但某个 Target 仍可能要求 learner 自己形成 root-cause 判断。如果 AI 直接给出 root cause，即使 Task 本身允许使用 AI，这次表现也不能证明该独立判断能力。反之，如果 Target 本身要求的是“在 AI 提供候选的情况下验证、识别风险并做最终决策”，相同 AI 行为不构成对该 Claim 的越界替代。

所以：

> **Support Compatibility Is Claim-Relative。**

`Prompted` 也不作为与 Independent / Assisted 平级的规范证据类型。不同 prompt 暴露的信息差异极大，从“再检查一下”到直接给出关键结构，必须依据真实 exposure lineage 解释。

学习者请求讲解与系统实际提供帮助是不同事实。请求可以结束一次独立诊断，但不能仅凭请求推出能力不足，也不能将请求时刻当作帮助已经暴露的时刻。请求前的独立表现保留原有证据价值；诊断结束时证据不足，可以保持 UNKNOWN / InsufficientEvidence，不能因活动终止而补造负面结论。转入教学后，Evaluation 依据实际发生的帮助及其时间、内容与 Claim 关系解释后续表现。

后续判断独立能力需要新的、符合该 Claim 支持条件的机会。新建活动或重新标记为“独立”不会消除既有暴露；刚接受解法讲解后答对同一道题，不能直接证明独立掌握。是否形成有效的独立 Evidence，仍需检查相关历史暴露，而不是只看活动名称或会话边界。

### 5.3 Contamination 是 Claim 与 Responsibility-Boundary Relative 的

一次干预不会均匀污染整个 Task 的所有 Evidence。更准确地说：

\[
Contamination
=
f(
Observation,
Claim,
ResponsibilityBoundary,
InterventionHistory
)
\]

同一个提示可能替代选法 Task Claim 的责任，却仍保留某个计算 Task Claim 要求的独立执行责任；同一次 AI 帮助对“独立形成诊断”Claim 构成强污染，对“验证 AI 候选诊断”Claim 却可能完全兼容。

Evaluation 不能只知道“发生过帮助”，还必须能够追溯暴露链：帮助在什么时间发生、暴露了什么、替代了哪部分责任，以及这种替代与当前 Claim 的关系。

\[
NoAssistanceClassificationWithoutExposureLineage
\]

如果暴露链不完整，正确结果是降低 Evidence 可解释性或标记 support state unknown，而不是默认 Independent。

### 5.4 迁移与延迟：实际条件和能力命题分开

实际发生的时间间隔、期间练习与帮助，以及相对既有学习经历的情境／表征变化，先记录为 Evidence Context。它们不会仅凭标签自动创造个人状态，也不存在“延迟证据总比即时证据强”或“换题就是迁移”的全局排序。

默认四维框架同时要求明确迁移和保持的能力命题。例如，“能独立求解熟悉表述的任务”与“能在规定表征变化下独立建模求解”具有不同的概括范围；“在已说明间隔与条件下保持求解责任”又增加了时间条件。需要分别判断时，定义相应 Task Claims；不能只给原求解 Claim 的 Evidence 加上标签，就声称已有可分别查询的迁移与保持 Belief。

Claim 规定希望推断的范围，Evidence 记录这一次实际发生的条件。实际变化或间隔不满足 Claim 时，只能在适用命题内解释，或保留取证缺口；不能为适配每次表现临时更改命题。也不为每个具体变化和间隔机械增加 Claim。§3.1 的有依据裁剪、扩展和版本规则同样适用。

### 5.5 Missing Evidence 不是 Negative Evidence

系统没有看到某种表现，可能只是从未创造观察机会。

\[
MissingEvidence
\neq
NegativeEvidence
\]

因此：

- 未观察到迁移 success，不等于迁移能力 weak；
- 未观察到某 KC activation，不等于学习者不会该 KC；
- 没有 intermediate 过程轨迹，不等于学习者没有策略。

Evaluation 必须认识到 data collection 策略会塑造可见数据。选择性缺失不能自动解释成学习者能力不足。

### 5.6 Provenance 决定 Evidence 是否可解释

Evidence 必须保留足够溯源信息，使 Inference 和 Evolution 能判断：

- Observation 来源；
- underlying Event references；
- Task / Solution / KC 版本；
- 干预链路；
- timestamp；
- observation 不确定性；
- 来源直接性；
- 任务相似度与交互周期关系。

如果外部主体 A 转述主体 B 的评价，则应同时保留直接来源与被转述来源。这类信息可以与学习者命题相关，但来源身份或制度地位不会自动变成学习者真实状态。

### 5.7 Evidence Resolution 必须有行动价值

Evidence attribution 可以无限细化到 Task、Strategy、TaskNode、Step、KC 和干预，但系统不应默认这样做。

\[
EvidenceResolution
\le
RequiredBeliefResolution
\le
ActionResolution
\]

只有更细 attribution 会改变重要 Learner Belief 或 Interaction 决策时，进一步下钻才有价值。

### 5.8 Evidence Dependency：多次成功不一定是多份独立证据

三道高度同构 Task 即使每次都没有 Hint，也可能共享同一次 explanation、相同 surface structure 和相近时间窗口，因此不能机械地当成三份独立证据。

\[
ExecutionIndependence
\neq
EpistemicIndependence
\]

Inference Model 必须识别 shared 干预链路、任务相似度和交互周期 correlation，避免相关的证据被重复计算。

### 5.9 Freshness 属于 Inference，而不是改写历史 Evidence

历史 Evidence 在发生时的意义不会因为时间流逝被重写。变化的是它对**当前 Learner Claim** 的相关程度。

\[
CurrentRelevance(E,t)
=
f(
EvidenceTime,
CurrentTime,
ClaimStabilityAssumption,
SubsequentEvidence,
TransitionAssumptions
)
\]

这里使用 `ClaimStabilityAssumption`，而不是含糊的 `TargetStability`。Learning Target 的版本变化与能力状态随时间变化是两种不同问题：前者通常要求重新计算 Target Assessment；后者才可能影响当前 Learner Belief 的相关性判断。

因此 Freshness 是 Inference concern。系统不能为了表达“旧了”而修改历史 Evidence 本身。

### 5.10 Conflict 必须在聚合后仍然可见

高质量矛盾性证据不能被一个平均值吞掉。

\[
10\ Supports
+
10\ Contradicts
\]

并不自然等价于：

\[
Mastery=0.5
\]

系统必须区分：

\[
UnknownDueToInsufficientEvidence
\]

与：

\[
UncertainDueToConflictingEvidence
\]

两者可能具有相似不确定性，却要求完全不同的下一步。

### 5.11 Structured Conflict：先怀疑模型，再增加特征

如果学习者在 verbal 表示中稳定成功、在 table 表示中稳定失败，Inference 不应该立即创建新的稳定学习者特征。

更合理的结果是：

- 当前 Claim remains conflicted；
- 形成类似 `RepresentationDependentPattern` 的临时推断假设；
- 检查 TaskTemplate、KC Application Conditions、Observation 和 Evidence 语义是否过粗。

这保留了进一步解释空间，同时避免学习者画像变成吸收所有异常的垃圾桶。

### 5.12 Competing Inference Hypotheses

Inference 可以维护学习者层竞争性假设，例如：

\[
H_1=DivisionStepDifficultyInCurrentScope
\]

\[
H_2=RelationConstructionDifficultyInCurrentScope
\]

\[
H_3=ObservationError
\]

\[
H_4=OneTimeSlip
\]

这些 hypothesis 是 Evaluation 内部受证据范围限制的推断 workspace，用于解释本次任务表现或 Evidence 冲突，并支持下一步取证。它们不是 Learner State，不形成独立 Hypothesis Model，也不得以 KC 为索引持续累计为个人掌握状态。跨活动复用须重新核对原始依据、范围、时间和帮助，不能把假设当 current-valid Belief。

必须与 Evolution Space 的 SystemHypothesis 分开：

\[
InferenceHypothesis
\neq
SystemHypothesis
\]

单个学习者模式可以产生 `ModelMismatchSignal`，但是否构成系统问题、原因是什么，由 Evolution 负责。

### 5.13 Disconfirmation：Belief 必须允许被现实推翻

Disconfirmation 不是一种 Evidence Type，而是一条推断 discipline：

\[
EveryBeliefMustRemainRevisable
\]

当前强 Belief 遇到高质量矛盾性证据时必须允许下降；原本弱 Belief 也必须允许被新 Evidence 修正上升。Inference 不能把所有反证都解释成 noise 来保护已有判断。

### 5.14 Epistemic Gap：Evaluation 只表达“不知道什么”

Inference 可以识别重要未解决不确定性，例如 Evidence 太少、strong 冲突、竞争性假设无法区分、old 证据 currentness concern 或模型失配模式。

Evaluation 负责表达：

> **我们不知道什么，以及为什么不知道。**

是否值得为了填补这个 Gap 而主动打扰学习者，属于 Interaction。

\[
EpistemicGap\in Evaluation
\]

\[
WorthResolving(EpistemicGap)\in Interaction
\]

### 5.15 教学动作不能成为自证学习者 update

DeerMind 的教学 Action 是 Event，但不是能力证据。

\[
InstructionDelivered
\not\Rightarrow
LearnerBeliefIncrease
\]

否则系统会形成危险的自证循环：

\[
Teach
\rightarrow
BelieveLearned
\rightarrow
Stop
\]

学习是否真正发生，必须由后续学习者表现产生新的 Observation 与 Evidence 来回答。

---

### 5.16 Task Outcome、Learner Performance 与 Capability 必须分离

问题结果、个人表现与潜在能力需要分别解释：

\[
TaskOutcome
\neq
TaskPerformance
\neq
Capability
\]

真实任务的结果可能同时受到环境、其他参与者、工具与偶然因素影响。Evaluation 不能因为团队项目失败就直接降低 learner capability，也不能因为系统最终恢复成功就自动把全部成功归给 learner。

Evidence Model 应尽可能解释 learner 在当前责任边界内实际承担了什么、表现如何，以及哪些结果可以归因于 learner contribution。Outcome 可以是重要 Observation，但它不是 Capability 的直接代理。

### 5.17 Equal Epistemic Standing：prior 必须允许被个体 Evidence 推翻

群体统计、历史画像或已有高置信 Belief 都不能让系统失去观察反证的能力。Inference 可以使用合法 prior，但必须保证高质量个体 Evidence 能真正改变结论。

如果系统因为既有 prior 持续把反证解释成 noise，或者因为既有低 Belief 只采集低难度任务而再用这些数据证明原判断，Evaluation 会形成认识论自我封闭。

因此：

\[
Prior
\neq
Evidence
\]

并且：

\[
StrongPrior
\not\Rightarrow
ClosedBelief
\]

Interaction 负责提供是否存在充分反证机会的运行条件；Evaluation 负责不把 prior、机会选择偏差或缺失数据伪装成个体能力事实。

### 5.18 Authority Override 不能生成能力结论

Product Context 中的安全限制、监护要求、组织政策或制度义务可以改变当前允许执行什么，但不能自动产生能力 Evidence。

\[
AuthorityOverride
\neq
EpistemicEvidence
\]

例如因为安全规则禁止 learner 独立操作高压设备，只说明当前 Action 被限制；它既不能证明 learner 不具备能力，也不能证明 learner 已具备能力。Evaluation 必须把“没有机会表现”与“表现失败”区分开。

## 6. Evaluation 如何在运行系统中工作

Evaluation 的运行起点不是原始 Event，而是 Interaction Space 已经形成的 Observation。它既支持跨交互周期的长期认识，也必须允许局部交互在不等待 Belief 更新的情况下继续运行。

### 6.1 主运行链

Evaluation 的主认识链仍然保持：

```mermaid
flowchart LR
    O["Observation"]
    EM["Evidence Model"]
    EV["Claim-specific Evidence"]
    IM["Inference Model"]
    B["Learner Belief"]
    G["Epistemic Status / Gap"]
    T["Learning Target"]
    TA["Target Assessment / Target Gap"]

    O --> EM --> EV --> IM
    B -. "prior" .-> IM
    IM --> B
    IM --> G
    T --> TA
    B --> TA
```

Observation 描述当前表现；Evidence Model 把它放入明确 Claim；Inference Model 综合历史 Evidence 与先验；Learner State Model 保存当前认识；Epistemic Status / Gap 暴露系统认识的限制。

Target Assessment 不进入这条 Belief 写入链。它读取正式 Target Definition 与当前 Learner Beliefs，回答现有认识是否足以支持目标要求。它可以物化、缓存和版本化，但没有独立 source of truth。

### 6.2 Fast Interaction 与 Learner Evaluation 是两条不同回路

DeerMind 可以根据当前 Observation 直接作出局部反应，而不必先把一次错误写成长时学习者能力不足。

Fast Interaction Loop：

\[
Event
\rightarrow
Observation
\rightarrow
InteractionPolicy
\rightarrow
Action
\rightarrow
Event
\]

Learner Evaluation Loop：

\[
Observation
\rightarrow
Evidence
\rightarrow
Inference
\rightarrow
LearnerBelief
\rightarrow
InteractionPolicy
\]

两条回路在 Interaction Policy 汇合，但 Evaluation 不拥有 Action 决策。

### 6.3 一个端到端例子

假设学习者解决：

> 6kg 苹果 42 元，15kg 多少钱？

学习者写：

\[
42\div6=8
\]

\[
8\times15=120
\]

Interaction 可能形成：

- Unit Rate structure observed；
- division 操作已选择的；
- arithmetic 失配 at division step；
- multiplication consistent with 先验 wrong result；
- final answer incorrect。

Evaluation 不会直接得到“不会比例”。

Evidence Model 可以分别形成：

- 对独立完成本范围比例任务的 Task Claim：反向证据；
- 对已定义的单位量关系建立 Task Claim：列式可以提供正向证据；
- 除法错误作为局部诊断依据；若有适用计算 Task Claim 可解释其证据，否则保留观察，不增设 KC 状态。

如果 DeerMind 随后提示“再检查一下 42÷6”，学习者修正为 7 并得到 105，那么这次成功的 Evidence 需要按 Claim 与发生顺序解释。提示前已经呈现的 Unit Rate 策略保留原有证据价值，不能因后来的算术提示追溯性地判为受助选择；提示后的步骤也不能被重复计为一次新的独立策略选择。若评价计算责任，相应 Task Claim 的 Evidence 必须保留提示定位了错误这一步的条件；完整任务成功不能当作独立完成。

一周后学习者在新的表面情境中独立完成同构比例题，可补充该间隔与变化范围的证据；不能仅凭“延迟”或“新题”标签赋予固定更高权重，也不能据此宣称普遍迁移或长期保持。

如果之后学习者在 table 表示中持续失败，Inference 应保留 structured 冲突，而不是创建永久 `TableAbilityState`。必要时产生 System Signal，交给 Evolution 判断是否是 Task / KC / Observation / Evidence 模型失配。

这个例子展示了：

\[
Observation
\rightarrow
ClaimSpecificEvidence
\rightarrow
EvidenceIntegration
\rightarrow
Belief
\]

而不是：

\[
WrongAnswer
\rightarrow
PersistentKnowledgeDeficit
\]

### 6.4 Progressive Evaluation Resolution

Evaluation 不默认对所有行为进行最细粒度诊断。合理流程仍然从 Task-level Observation / Evidence 开始；只有当进一步分析可能改变重要 Learner Belief、Target Assessment、Epistemic Gap 或 Interaction 决策时，才继续查看 Solution Trace、关联 KC、Subtask 和 Step-level Observation。细化分析服务同一套 Task Claim Evidence 与教学判断，不创建第二类能力状态。

\[
ProgressiveEvaluationResolution
\]

目标不是牺牲理论精度，而是让诊断复杂度、计算成本和学习者注意力负担与真实认识价值匹配。拥有更细模型不意味着运行时必须获取最大分辨率。

### 6.5 Target Assessment：比较 Requirement 与 Learner Belief

Target Assessment 是跨 Space 派生认识：

\[
TargetAssessment
=
Assess(
TargetDefinition,
LearnerBeliefs
)
\]

Learning Space 拥有 Target Requirement；Evaluation Space 拥有 Learner Belief 与比较所需的认识论语义；Target Assessment 自身不成为新的 Learner State primitive。

一个 Target Assessment 至少需要能够区分：

- Evidence 已足以支持当前 requirement；
- Evidence 已支持 learner 当前低于 requirement；
- Evidence 不足，无法判断是否达到；
- Evidence 冲突、过时或只覆盖部分 requirement；
- 某些 requirement 无法在当前条件下可靠识别。

具体状态表示暂不冻结成 enum，也不要求压缩为单一百分比。

必须长期保持：

\[
BelowRequirement
\neq
InsufficientEvidence
\]

### 6.6 Target Gap 与 Epistemic Gap

**Target Gap** 表示已有 Evidence 支持“当前能力低于某项 Target requirement”；**Epistemic Gap** 表示系统还没有足够 Evidence 判断是否达到 requirement。

\[
TargetGap
\neq
EpistemicGap
\]

例如 learner 多次在独立网络诊断中失败，可以形成 Target Gap；而 learner 从未获得过独立诊断机会，只能形成 Epistemic Gap。两者都不能直接产生 Action：

\[
Gap
\neq
Action
\]

是否值得评估、练习、提示或暂不干预，仍属于 Interaction Policy。

### 6.7 Assistance / Support Dependency 是 Target-relative 派生诊断

Evaluation 可以形成一个派生诊断：对于某个 Target 明确要求 learner 自己承担的责任，learner 是否持续只能在替代性支架存在时成功。

这种 dependency 必须相对于 Target / Responsibility Boundary 解释：

\[
DependencyRisk
=
f(
ObservedAssistancePattern,
ResponsibilityBoundary
)
\]

它不是新的 Learner Trait，也不进入 Learner State Core。同一个 learner 对 Target A 可能存在不必要依赖，对 Target B 则完全不存在，因为 Target B 本身允许外部化相同责任。

### 6.8 分数应用：Task Claim 与 Belief 更新实例

以下是说明语义的自编案例，不是已执行测量、正式教材包或经校准的达标规则。模板 T1：已知原量 \(a>0\)，增加或减少原量的 \(r\)，求最终量；\(0<r<1\)，计数情境须满足整数量约束。范围包括单次变化、明确原量作基准；连续变化、不同基准和逆求原量暂不包含。

方法 S1 先求 \(ar\)，再求 \(a\pm ar\)；S2 先构造最终量占原量的 \(1\pm r\)，再求 \((1\pm r)a\)。两者的 KC 依据包括基准量、分数表示的数量关系、同基准合并、算术及等价变形。Learning Space 允许任选 S1、S2，不要求每题使用两种方法。

本例为分别判断四方面表现，定义四个 Task Claims。它们共享 T1 的数学关系和方法参照，但完成责任或概括条件不同。

| Task Claim | 所承载维度及责任边界 |
| --- | --- |
| C1：独立建模并求解 | 独立完成：在熟悉文字表述的 T1 范围内，自行辨认原量、变化方向和最终量，选用获准方法得到合理结果；不接受定位、关系式或答案帮助 |
| C2：说明数量关系 | 理解与解释：在 T1 范围内独立用语言、图示或等价表达说明基准、变化量与最终量；不要求固定措辞，不把背诵解析当理解 |
| C3：在规定表征变化下建模求解 | 迁移应用：已有文字表述的学习经历后，面对未练过的表格表述，自行识别原量和变化关系并求解；数学范围仍为 T1，不含逆求原量和任意新题型 |
| C4：延迟后保持求解责任 | 延迟保持：已有独立求解的表现依据，在预定间隔和可比条件下仍能独立建模求解；本例暂用七天展示合同含义，并记录期间练习与帮助。七天不是通用标准，不据此同时宣称解释或迁移能力的保持 |

C2 不是“基准 KC 已掌握”的替代标签。C3 的变化范围和 C4 的时间、期间支持条件必须在取证前具体化；未练过表格或期间是否练习尚不清楚时，要保留条件不确定性。C4 未限定无强化时，只能给出实际练习背景下的保持判断；不得把它解释为无练习仍能保持。四项命题也不穷尽六年级全部分数能力。

| 事件与实际表现 | Evidence 解释 | Belief 可据此怎样变化 |
| --- | --- | --- |
| 原有 40 本书，增加原量的 1/4；学生算 10 并回答最终有 10 本 | C1 反向；混淆变化量与最终量。未要求解释，无新的 C2 证据 | C1 增加未满足求解责任的依据；C2–C4 不据此自动下降，更不推断全部 KC 不会 |
| 系统提示“10 本是增加的，还是现在全部的？”；学生改为 50 | 保留定位帮助和订正，不满足 C1 的独立边界 | 不覆盖原始错误，也不作为独立通过；C2 须另看实际表达及帮助 |
| 随后文字新题原量 60、减少 1/5；独立写出 60−60×1/5=48 | C1 正向，覆盖 S1 与减少情境；保留刚接受同类讲解的背景 | 增加即时应用依据；未解释、未发生约定表征变化、未到保持观察时点，C2–C4 不自动取得正向证据 |
| 后续文字新题原量 80、增加 3/8；独立列 80×(1+3/8)=110，说明 1 和 3/8 都以 80 为基准 | C1、C2 正向，记录实际帮助与时间，覆盖 S2 与增加情境 | 可分别支持独立求解和理解；C3 尚待指定变化的证据，C4 尚待延迟表现；不平均成“掌握一半” |
| 七天后表格给出原量 72、减少 5/12；独立答 42 并说明关系 | 若表征对该学习者确属规定变化、期间练习记录及可比条件满足合同，可分别解释 C3、C4 的正向 Evidence；表达也可能支持 C2 | 只支持规定表征变化和该间隔／背景下的求解保持。若表格已被反复练过，不能据此支持本例 C3；缺少先前表现或期间条件，不足以确认 C4 的保持结论 |

同一次表格作答可以同时检验变化与延迟，但共享同一个 Observation 和背景，不能当成多份独立样本。若失败，不能仅据此断言是迁移困难还是未保持，需要保留归因不确定性，必要时用熟悉表述或即时变化的适用任务补充区分。诊断是否继续由 Interaction 按价值和负担决定。

Inference 按 Evidence 的相关性、帮助、时间和重复依赖，分别更新每个 Claim 的 Assessment、EpistemicUncertainty、EpistemicStatus 与 EvidenceBasis。早期错误与教学后成功可能反映状态变化，不应无视时间统一标为矛盾；教学发生本身不直接上调能力。本例不指定统一正确率、先验、衰减公式或精确掌握百分比，相关规则须经工程与质量验证校准。

若目标改为 S1、S2 均须覆盖，只有 S1 证据表示方法覆盖不足，不表示 S2 已失败；若目标还要判断比较选法或解释的延迟保持，必须补充相应责任与证据合同，不能从现有四个名称自动推出。合理扩展与裁剪均按 §3.1 的依据和版本规则进行。

运行链为：Interaction 保留题目、实际输入、实际帮助与时间条件，形成 Observation；Evaluation 按已发布 Claim 形成 Evidence，由 Inference 更新各 Belief；TargetAssessment 与已采用要求比较；Interaction 据当前有效认识决定讲解或取证。KC 支持解释与教学，不增加 KC 状态更新链。

## 7. Cross-Space Contracts、版本与 Evolution

Evaluation 必须保持自己的认识职责，同时依赖其他 Space 提供规范坐标、当前 Observation、事实溯源信息和系统级演化机制。

### 7.1 Domain 与 Learning Space：规范输入分开

Domain 提供 TaskTemplate 的身份、版本、参数与责任范围，SolutionTemplate 的适用条件、子任务依赖及方法相关 grounding，以及 KC 的定义和适用条件。Learning Space 提供 LearningTarget 的版本、材料映射、范围、期望标准与支持责任。两组输入必须分别记录依赖，不能由一个含混的“学习空间版本”替代。

Interaction 提供实际问题的版本引用、参数、呈现条件、已发生的帮助和表现 Observation。实际采用何种方法需要行为依据，不能从参考 SolutionTemplate 反向推定。上传问题未映射、方法覆盖不完整或证据不足时，可保留未知，不伪造完备模型后再给出精确能力结论。

Evaluation 仅在明确任务范围、责任及方法要求上维护 TaskProficiencyClaim，并形成 Evidence、Belief 与派生 TargetAssessment；KC 只作为领域解释和教学依据。材料章节只提供产品汇总入口，不是新的能力本体；产品空间隔离与授权限制同样作用于 Evidence 的可用范围。

LearningTarget 按 §3.1 的默认框架记录维度采用、裁剪／扩展及 Claim 对应关系；Evaluation 负责命题语义和个人判断。缺少对应定义是内容缺口，不能由 Runtime 临时捏造正式 Claim。LearningTarget 不能直接生成 LearnerBelief，个体表现不能直接修改 Domain 或目标定义。要求、证据与信念保持分层。

### 7.2 Interaction Space → Evaluation：提供 Observation 和暴露事实

Interaction 是 Evaluation 的主要运行时 semantic input 来源。它提供 Observation，包括 Task 结果、observed 策略、过程轨迹语义、error / 失配、self-报告、外部报告、Observation 不确定性和 Event 溯源信息。

Evaluation 不得绕过 Observation Model，直接从原始 Event 建立竞争性的表现 interpretation。

Assistance / 独立性 / 污染判断还必须结合已发生的 Action Event 与信息暴露链路。Observation 告诉系统“看到了什么”，Action Event 告诉系统“系统实际暴露过什么”；两者不能互相替代。

### 7.3 Observation 被修正后，Evaluation 必须重新评估依赖结论

Observation 是可修正解释。如果 Observation 后来被纠正、替代或失效，Evaluation 必须能够定位依赖它形成的 Evidence，并重新推断相关 Learner Belief。

\[
\boxed{
ObservationInvalidated
\rightarrow
EvidenceReevaluation
\rightarrow
BeliefReInference
}
\]

语义上要求重新评估，不代表工程上必须同步全量重算。stale 标记、优先级、batch 和 async recomputation 属于 System Design。

已经真实发生的 Event / Action 不被重写，因为解释错误不等于现实交互没有发生。

### 7.4 Global Event Model → Evaluation：提供历史事实与溯源信息

Evaluation 可以查询 Event History 获取：

- timestamp；
- 来源身份；
- 干预链路；
- causal / correlation history；
- 模型 / semantic 版本 references。

但 Event 不能绕过 Observation / Evidence 直接写 Learner Belief。

### 7.5 Evaluation → Interaction：提供只读认识论 view

Evaluation 向 Interaction 提供：

- Task Proficiency Beliefs；
- Task Claim 的方法覆盖、适用范围与证据限制（由正式 Evidence 派生）；
- 不确定性 / Epistemic Status；
- Epistemic Gaps；
- Target Assessment；
- Evidence-supported Target Gaps；
- 相对于 Responsibility Boundary 的 Assistance / Support Dependency diagnostic；
- 其他经过依据支持的派生 diagnostic views。

Interaction 可以读取这些内容，但无权直接修改 Learner Belief，也不能把 Target Gap 或 Epistemic Gap 当成自动行动命令。

### 7.6 Evaluation → Evolution：输出 System Signal，不越级形成结论

Evaluation 可以发现 recurring 模型失配、Evidence 映射 failure、Inference 校准 failure、systematic contradiction 模式或 claim granularity concern。

这些内容首先是 System Signal：

\[
EvaluationSystemSignal
\neq
SystemIssue
\neq
SystemHypothesis
\neq
ValidationEvidence
\]

单个学习者 anomaly 不能自动触发 ontology 变更。是否存在 System Issue、原因是什么、是否需要 Revision Candidate，由 Evolution 继续处理。

### 7.7 Evolution / Governance → Evaluation：新语义必须通过正式版本进入

Evolution 可以形成 System Issue、System Hypothesis、Revision Candidate、Validation Evidence 和 Change Recommendation，但这些输出本身不能直接改写 Evaluation 规范语义。

正式变化需要：

\[
ValidatedChange
\rightarrow
Governance
\rightarrow
NewApprovedEvaluationVersion
\]

这适用于 Learner Claim definitions、Evidence 语义、Inference 语义、transition assumptions、校准 parameters 和有效范围。

### 7.8 Evolution Contract

Evaluation 中具有独立语义责任和演化生命周期的组件必须支持：

\[
Identity
+
Version
+
ActivationBoundary
+
Provenance
+
ValidityScope
+
FalsifiableExpectation
+
ReplaySupport
\]

至少包括：

- Learner Claim 语义身份 / 版本；
- Evidence 映射身份 / 版本；
- Inference 语义 / 模型身份 / 版本；
- Evidence Basis 与 Event / Observation / 信息暴露链路；
- Belief revision history；
- 不确定性 / 冲突原因；
- 校准结果；
- Evidence 依赖；
- Target Assessment 所绑定的 Target Version 与 Learner Belief Version；
- 有效范围和已知限制；
- 可证伪预期；
- 重放支持；
- downstream 依赖过程轨迹。

Target Assessment 可以被物化，但它的 identity 不能被理解成新的 epistemic source of truth；它始终是上游 Target 与 Learner Belief 的版本化派生结果。

### 7.9 两类版本变化必须使用不同失效路径

如果 Target 的 Required Standard、Conditions、Support Boundary 或 Success Semantics 改变，通常不意味着 learner 的既有能力发生了变化。此时应失效并重新计算 Target Assessment：

\[
TargetRevision
\Rightarrow
TargetAssessmentInvalidation
\]

但：

\[
TargetRevision
\not\Rightarrow
LearnerBeliefRevision
\]

相反，如果 TaskTemplate、Learner Claim semantics、Evidence 解释规则或 Inference 语义发生变化，旧 Belief 可能不再能静默继承。正确路径是重新解释历史事实、重新形成 Evidence 并重新推断，或者使用经过验证、显式记录 provenance 的 migration rule。

\[
NoSilentCrossVersionInterpretation
\]

证据不足时返回 UNKNOWN。历史重放产生的是新的解释，而不是新的历史事实。

### 7.10 Evaluation 必须可以被现实证伪

三个 Model 都必须有独立失败信号。

**Learner State Model** 应在以下情况被重新打开：Task Claim 无法解释重要决策差异；范围、方法与支持条件仍无法表达重要能力边界；包括知识层判断在内的新状态具有独立 Evidence、预测价值和行动价值。重开不等于自动恢复旧 KC Claim。

**Evidence Model** 应在相对于命题的映射持续失真、Responsibility Boundary 无法解释 assistance 污染、Outcome 与 learner contribution 经常被错误归因、群体 prior 系统性替代个体 Evidence 时接受修订。

**Inference Model** 应在校准长期偏差、相关 Evidence 被重复计算、历史证据当前相关性处理失真、冲突被平均隐藏、Target Assessment 长期失配或 system 置信度与真实结果不匹配时接受挑战。

正常面向具体学习者的 Belief revision 属于 Object-Level Evaluation；修改 Claim、Evidence 或 Inference 语义则属于 System Evolution。

\[
LearnerAdaptation
\neq
SystemAdaptation
\]

## 8. 关键架构决策、风险、开放问题与下游对齐

### 8.1 关键架构决策

**D1 — 三个 Core Model 保持不变。**  
本版不新增 Target Evaluation Model、Capability Model、Dependency Model 或 Fairness Model。Target 对齐通过现有 Learner State / Evidence / Inference 责任与跨 Space 派生语义完成。

**D2 — Learner State Core 只保留 Task Claim 的 Belief。**  
KCClaim / KCBelief、TargetBelief、TargetMasteryBelief、CapabilityBelief、AssistanceDependencyTrait 都不进入当前 Core。目标要求、派生 assessment 与 dependency diagnostic 都保持各自 owner。

**D3 — Task Claim 必须表达任务范围、责任、方法要求、条件、支持边界与质量要求。**  
默认以独立完成、理解与解释、迁移应用、延迟保持检查任务范围的评价覆盖，允许按 §3.1 有依据地裁剪与扩展。所需认识由明确 Task Claims 表达，不能用一个熟悉题求解判断替代其余维度；四维也不增加四种状态类型或每题四项检测。

**D4 — Evidence Condition 与 Claim Condition 默认分离。**  
只有真正改变能力命题语义的条件才进入 Claim；疲劳、一次性环境、普通提示等默认保持为 Evidence Context。这避免状态空间按条件组合爆炸。

**D5 — Assistance 的认识意义由 Responsibility Boundary 决定。**  
“用了 AI”不是能力高低判断。真正需要判断的是帮助是否替代了当前 Claim 要求 learner 自己承担的责任。

**D6 — Target Assessment 是派生认识，不是 Learner State。**  
它绑定 Target Version 与 Learner Belief Version，可以缓存和重算，但没有独立 source of truth。

**D7 — Target Gap 与 Epistemic Gap 分离。**  
Evidence 支持未达标与证据不足是不同认识状态，不能用一个“能力缺口”覆盖。

**D8 — Population Prior 不得替代 Individual Evidence。**  
受限 prior 可以存在，但必须允许被真实个体 Evidence 推翻。

**D9 — Authority Override 不产生能力 Evidence。**  
制度、安全或监护限制影响 Action authority，不直接改变 learner capability belief。

### 8.2 主要失败模式

| 失败模式 | 触发条件 | 后果 | 缓解方式 | 重新打开条件 |
|---|---|---|---|---|
| Claim 条件爆炸 | 每个 assistance / context 都拆成新 Task Proficiency State | Learner State 无法校准、无法复用 | EvidenceCondition 与 ClaimCondition 分离 | 大量真实能力无法在当前 Claim 模型中区分 |
| Target 偷偷进入 Learner State | 为每个 Target 创建 mastery belief | Requirement 与 Belief 混淆、重复真相 | Target Assessment 保持 derived | 发现 Target-specific latent state 具有不可约证据语义 |
| Assistance 二元化 | “用了工具”即低价值 Evidence | AI-native Target 被错误低估，传统独立性被绝对化 | Responsibility-boundary-relative contamination | 实证证明更简单规则长期更准 |
| Outcome 归因错误 | 把团队/环境结果直接归给 learner | 能力高估或低估 | 区分 Outcome / Performance / Capability | 无法可靠识别 learner contribution |
| Prior 自我封闭 | 群体 prior 或既有 Belief 持续压制反证 | Equal Epistemic Standing 失效 | prior 可反证、反证机会审计 | 多场景证明该约束不足 |
| Gap 混用 | 不知道与已知未达标都输出“缺口” | Interaction 采取错误行动 | Target Gap / Epistemic Gap 分层 | 实现无法稳定区分两者 |
| 版本失效过度 | Target 改版直接重算所有 Learner Belief | 历史认识被无必要改写 | Target revision 只失效 Target Assessment | Target revision 真正改变 Claim semantics |
| 版本失效不足 | Claim / Evidence semantics 变化仍复用旧 Belief | 跨版本含义漂移 | replay / reinference / explicit migration | 证明语义等价可安全继承 |

### 8.3 开放问题

| 类别 | 问题 | 当前状态 |
|---|---|---|
| 概念性 | Task Proficiency Claim 中哪些 Conditions 必须进入 Claim semantics | 冻结原则，不冻结统一字段集 |
| 实证性 | 默认四维及其裁剪／扩展能否覆盖实际领域中的重要教学差异 | 框架及 Task Claim 对应原则已定；各领域粒度、证据充分性和数值校准待验证，不压成总分 |
| 概念性 | 是否需要对特定任务范围的选法责任单独维护 Task Claim | 按独立证据与教学价值判断，不新增 Strategy 状态类型 |
| 实证性 | 仅 Task Claim 是否跨数学、系统工程、写作等领域仍具有足够预测与教学价值 | 需跨域验证 |
| 实证性 | Responsibility-boundary-relative contamination 是否能预测后续表现 | 需真实 assistance / AI 使用数据 |
| 实证性 | Target Assessment 在高噪声开放任务中的校准质量 | 需长期数据 |
| 实证性 | Assistance / Support Dependency diagnostic 是否具有稳定预测与干预价值 | 暂保持 derived |
| 治理性 | 哪些 Population Prior 允许进入 Inference，如何审计公平风险 | 需 Product Constitution / Governance 细化 |
| 治理性 | 高风险 Target 的 Evidence threshold 与 Safety authority 如何交互 | 需 Context Constitution |
| 实现性 | Belief 与 Target Assessment 的 version pinning / invalidation 索引 | 交给 System Design |
| 实现性 | 多维 Claim、Evidence 与 Assessment 的存储/查询协议 | 交给 System Design |
| 实现性 | LLM 参与 Evidence / Inference 时如何保证依据可追踪 | 交给 AI Runtime / System Design |

### 8.4 本版下游传导

本版的默认四维、命题与证据边界同步传导至概念、系统及 MVP 合同。Claim identity、Evidence provenance、TargetAssessment dependency、版本解析、typed invalidation 与重放按各自运行合同实现；正文对齐不表示内容包、工程实现或校准质量已经符合新合同。

实现不得引入第二 LearnerBelief writer、TargetBelief 或自动 Gap→Action 路径。TaskProficiencyClaim 标识继续使用，但必须检查 TaskScope、方法要求和历史证据兼容性；旧 KC 状态仅保留历史读取，不转换成新 Task 状态或经兼容回退进入当前决策。出现重要无法表达的反例再重新审查模型，不能在 Runtime 静默扩张认识权限。

## 附录 A — Evaluation Space Semantic Invariant Registry

正文只保留最核心的认识边界；以下 registry 用于设计审计、实现检查和跨版本回归。

| ID | Invariant | 含义 |
|---|---|---|
| E1 | No Belief Without Claim | 任何 Learner Belief 必须对应明确 Claim |
| E2 | Observation != Evidence != Belief | 行为解释、证据关系与最终认识不可合并 |
| E3 | No Evidence Without Claim | Evidence 必须是 claim-relative |
| E4 | Only Evaluation Writes Learner Belief | Learner Belief 只有 Evaluation 能修改 |
| E5 | Requirement != Evidence != Belief | Target requirement 不能直接生成 learner evidence / belief |
| E6 | Missing Evidence != Negative Evidence | 未观察到不能自动解释成不会 |
| E7 | EvidenceCondition != ClaimCondition | 条件默认属于 Evidence；只有改变能力语义才进入 Claim |
| E8 | Support Compatibility Is Claim-Relative | Assistance 的证据影响取决于 Claim / Responsibility Boundary |
| E9 | No Assistance Classification Without Exposure Lineage | 独立/受助判断必须有真实暴露链 |
| E10 | TaskOutcome != TaskPerformance != Capability | 现实结果、可归因表现与稳定能力必须分层 |
| E11 | 知识依据不等于个人能力状态 | KC 用于解释与教学；只维护 Task Claim Belief，不从任务成功扩写 KC 掌握 |
| E12 | Default Dimensions != Mandatory Tests Each Turn | 默认四维覆盖有版本，可有依据裁剪／扩展；未测与不适用分开，不强制每题四测 |
| E13 | Shared Observation != Independent Evidence | 多 Claim 共享表现须保留共同来源；不得平均为总掌握率或重复增强置信度 |
| E12 | Belief Must Remain Revisable | 任何 Belief 都必须允许未来 Evidence 推翻 |
| E13 | Teaching Action != Learning Evidence | DeerMind 自己教过不能成为学习者已学会的证据 |
| E14 | Time Passage != Negative Evidence | 时间流逝本身不降低 competence assessment |
| E15 | Correlated Evidence != Independent Repetition | 多次执行独立不等于 epistemic independence |
| E16 | Conflict Must Survive Aggregation | 高质量冲突不能被平均值隐藏 |
| E17 | Belief Is Action-Neutral | Learner Belief 不包含 action recommendation |
| E18 | Target Assessment Is Derived | Target Assessment 没有独立 source of truth |
| E19 | TargetGap != EpistemicGap | 已知未达标与未知是否达标必须分离 |
| E20 | PopulationPrior != IndividualEvidence | 群体 prior 不能替代个体 Evidence |
| E21 | AuthorityOverride != EpistemicEvidence | 制度/安全限制不产生能力证据 |
| E22 | Do Not Invent Learner Traits to Repair Model Mismatch | 模型失配先检查模型，不靠新 trait 吸收异常 |
| E23 | InferenceHypothesis != SystemHypothesis | learner-level explanation 与 system-level explanation 分层 |
| E24 | Observation Invalidation Reaches Dependents | Observation 失效后相关 Evidence / Belief 必须重新评估 |
| E25 | Target Revision Invalidates Assessment, Not Automatically Belief | Target 改版默认重算 assessment，而非能力 belief |
| E26 | No Silent Cross-Version Interpretation | canonical semantics 变化后旧 Belief 不得静默继承 |
| E27 | Historical Replay Creates New Interpretation, Not New History | replay 产生新解释，不改写 Event truth |

## 附录 B — 典型反模式

### B.1 Answer Correct → Mastered

错误：

\[
CorrectAnswer
\Rightarrow
Mastered
\]

它忽略策略、帮助、guessing、过程轨迹覆盖度和 claim specificity。

### B.2 Hint 后成功 → 所有相关 KC 都会

Assisted Task success 不能机械映射到所有 structural KC。Evidence 必须基于实际 Observation Trace 和相对于命题的污染。

### B.3 没看到 → 不会

错误：

\[
AbsenceOfObservation
\Rightarrow
NegativeEvidence
\]

这把 selection 效应误写成学习者能力不足。

### B.4 正反 Evidence 平均成 0.5

把冲突压成一个均值会丢掉 future diagnostic 价值。Evidence 稀缺与 Evidence 冲突必须可区分。

### B.5 模型解释不了 → 给学习者增加新特征

结构化差异首先形成冲突 / 推断假设；如果怀疑规范模型失配，则产生 System Signal，而不是直接扩张 Learner State。

### B.6 DeerMind 教过 → 学习者学会

这是典型自证循环。教学 Action 只能改变后续信息暴露情境，不能直接提升 Belief。

### B.7 把疲劳 / willingness 写入能力

这些 condition 可以改变 Interaction 决策，但默认不改变长期学习者能力信念。

---

### B.8 Target Requirement → Learner Belief

错误：

\[
TargetRequires(X)
\Rightarrow
LearnerHas(X)
\]

规范要求只说明“应该达到什么”，不能成为“已经会什么”的 Evidence。

### B.9 Group Prior → Individual Belief

错误：

\[
PopulationPrior
\Rightarrow
IndividualLearnerBelief
\]

群体统计最多是受限 prior 或假设来源，必须允许个体 Evidence 推翻。

### B.10 Authority Restriction → Capability Failure

因为安全、监护或制度要求不允许 learner 执行某项行为，不能据此推出 learner 缺乏能力。没有表现机会与表现失败必须区分。

## 附录 C — Evaluation Validation Checklist

### Learner State Model

- 只维护 Task Claim 是否足以解释重要决策差异，且没有隐性 KC 状态？
- Task Claim 是否表达必要范围、责任、方法覆盖、条件、支持边界与质量要求？
- 是否把一次性 Evidence Condition 错误升级成长期 Claim dimension？
- 四个默认维度是否有明确 Claim 对应，裁剪与扩展是否有依据、权限和版本？
- 是否把未测、条件未知或保持时点未到误记为不适用或失败？
- 是否出现有独立证据和行动价值、需受治理讨论的新增状态类型？
- 是否存在不可证伪的学习者特征膨胀？

### Evidence Model

- 相对于命题的映射是否能预测后续表现？
- assistance 污染是否真正相对于 Responsibility Boundary 解释？
- 暴露链缺失是否被错误解释成 Independent？
- Outcome 是否被错误当成 learner Performance？
- Authority Override 是否被错误当成能力 Evidence？
- 某类 Observation 是否被系统性高估或低估？
- 迁移变化、保持责任与时间条件是否明确，证据是否适用，联合探针是否保留归因限制？

### Inference Model

- Belief 校准是否长期偏差？
- 相关 Evidence 是否被重复计算？
- ClaimStabilityAssumption 是否与现实能力变化相符？
- 高质量冲突是否被平均隐藏？
- Population Prior 是否压制了高质量个体反证？
- Target Assessment 是否与 Target Version / Learner Belief Version 正确绑定？
- Below Requirement 与 Insufficient Evidence 是否被稳定区分？
- system 置信度是否与后续结果匹配？

### Cross-Space Derived Semantics

- Target Assessment 是否仍然可以追溯到 Target Requirement 与 Learner Beliefs？
- Target revision 是否只失效必要的派生结果？
- Task / Claim / Evidence semantic revision 是否触发正确的 reinference？
- Assistance Dependency diagnostic 是否保持 Target-relative，而没有变成 learner trait？
- Target Gap、Epistemic Gap 是否都保持 action-neutral？

## 附录 D — 本版调整与历史边界

本版在 Task Claim 单一能力状态基础上，确立默认四维评价及有依据的裁剪／扩展，修订 §3.1、§5.4 与 §6.8，区分条件事实、能力命题、证据缺口和规范适用性。四维不新增状态类型，也不改变 Evaluation 单写、事实与认识分层及受治理变更合同。前版的 KC 降层决定继续有效。

旧 KCClaim / KCBelief 按原版本留在历史中，不删除、不作为当前能力输入、不直接改成 Task Claim。若原始表现足以支持新的明确任务命题，可经新版本 Evidence 解释与推断形成新 Belief，并保留原始来源及证据依赖；依据不足则 UNKNOWN。已有 Task Claim 也须核对责任、范围、方法和支持条件，不只改字段名。

旧 Freeze Gate、Spike、Build 和 G3 结果继续属于原基线。本轮只传导文档合同，不声称代码、领域包、评测参考或参数已迁移和通过验证。逐文件修订及未完成迁移见[模型复核 §10](DeerMind_Learning_Model_Reassessment.md#10-默认四维评价框架的正式修订记录)。
