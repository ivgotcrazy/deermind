# DeerMind Evaluation Space Design v1.5

> **版本**：v1.5<br>
> **中文名称**：DeerMind 评估空间设计<br>
> **文档性质**：Space Design / Architecture Baseline<br>
> **状态**：阶段性语义结论已纳入正式设计；本轮未新增实证或阶段 Gate 结论<br>
> **上位基线**：DeerMind Concept Architecture v1.5<br>
> **上位领域基线**：[DeerMind Domain Space Design v1.3](DeerMind_Domain_Space_Design_v1.3.md)；[Learning Space v1.3](DeerMind_Learning_Space_Design_v1.3.md)<br>
> **上位价值约束**：DeerMind Product Thesis v1.0、DeerMind Product Constitution v1.0<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：用户确认调整方向并授权修订；具体合同由作者推演与核对，文档检查不代表模型效果或 Gate 通过<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-20<br>
> **修订说明**：重构单模板多维 Claim，明确绑定、条件、裁剪和跨任务边界；同步相关合同与现行引用。逐文件变更见[修订记录 §11](DeerMind_Learning_Model_Reassessment.md#11-单模板多维-claim-的正式修订记录)。

---

## 1. 文档定位与设计命题

Evaluation Space 解决的不是“给学习者打一个分数”，也不是维护一个越来越复杂的学习者画像。它面对的是一个更基本的问题：**DeerMind 永远无法直接读取学习者真实的认知状态，却必须根据有限、受条件影响、可能互相冲突的行为证据，形成长期、可修正的能力认识。**

Domain Space v1.3 提供任务模板、方法与 KC；Learning Space v1.3 提供 LearningTarget、范围和支持责任。Evaluation 需要判断具体表现支持哪个条件性命题，区分未达目标与证据不足，并保证模型映射变化不会被误当成真实学习变化。

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
ClaimAspectSpecificEvidence
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

根据 Concept Architecture v1.5，Domain 提供领域定义，Learning Space 提供材料与目标规范；Evaluation 形成对学习者的可修正认识；Interaction 使用这些认识、当前 Context 与现实约束做行动决策。必须长期保持：

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

Learner State Model 只保留 **Task Claim**，规范类型沿用 `TaskProficiencyClaim`，其个人状态为 `TaskProficiencyBelief`。Task Claim 是针对一类任务的结构化能力声明，内部包含多个评价方面；它定义需要判断什么，不保存某个人的判断结果，也不要求整项声明只能得到一个真假值或掌握概率。

**绑定与身份。** 每个 Claim 精确引用一个 TaskTemplate 版本。TaskScope 是该模板内采用的参数、情境、表征、完成责任及排除范围，不再是一组模板的集合。Claim 不绑定一道具体题；由同一模板生成或受控映射到它的不同题目，可以提供相应能力证据。

- 同一模板、同一套评价条件组织一个多维 Claim，不再为独立、解释、迁移、保持分别创建顶层 Claim。同一 Learning Space 对同一评价条件采用一个明确的有效 Claim 版本。
- 不要求全系统每个模板永远只有一个 Claim：同一模板若存在不可混用的方法、责任或支持条件，可以采用不同的受控定义／版本。例如允许任选算术或方程，与指定算术法，是不同的评价条件；不能把旧判断直接改义。
- 不因不同学习者、题目、活动、单次帮助或目标分数门槛而复制 Claim。规范定义可以复用，个人 Belief 仍按学习者、Learning Space 和 Claim 版本隔离。
- 跨任务的课程要求由 LearningTarget 组织，达成情况由 TargetAssessment 派生；不再用一个 Claim 同时代表多个 TaskTemplate，也不从任务 A 成功自动推出任务 B 已掌握。需要整体完成的复合任务可以有自己的真实任务模板与递归方法，但不能为汇总分数虚造模板。

| Claim 的语义组成 | 必须说明的内容 |
| --- | --- |
| TaskTemplateRef / TaskScope | 唯一模板及版本；其内部采用的参数、情境、表征、任务责任和排除范围 |
| 评价条件 | 可用方法、任选／指定／分别覆盖的含义、工具和支持边界；各方面可进一步限定，但不得无声明地放宽 |
| 评价方面（Aspect） | Claim 内的稳定方面键、含义、责任、质量判据、适用条件及证据要求；默认采用下述四维 |
| 采用与裁剪／扩展 | 每方面是否适用、依据、目标影响、决定及审核责任和版本；不得用暂无证据代替裁剪依据 |

Aspect 是 Claim 的内部结构，可以用 `ClaimVersion + AspectKey` 精确引用，不是新 Space、核心 Model、独立 Claim 或拥有独立发布生命周期的能力对象。责任、方法、条件及方面定义随 Claim 版本发布；跨版本复用方面键不表示语义自动兼容。

**默认四维。** 每个采用的任务能力声明默认从下列四个方面组织评价，保留有依据的裁剪和扩展。不为每个题目或子步骤自动生成四份状态，也不要求每轮全部检测。

| 方面 | 要定义的能力责任与条件 | 不能自动推出的结论 |
| --- | --- | --- |
| 独立完成 | 在明确允许的工具和支持边界内，自行承担关键判断、操作或求解责任，并达到质量要求 | 一次答案正确不证明独立；独立不等于禁止所有工具 |
| 理解与解释 | 用语言、图示、辨析、操作或反例等表现说明关系、理由或适用边界；写清有效表现及帮助边界 | 流畅复述不等于理解；没有要求解释不表示不会解释 |
| 迁移应用 | 写清参照学习经历、变化了什么，以及变化后仍须完成的责任；评价对象仍为本 Claim 绑定的任务 | 换数字不自动构成有效迁移；一种变化成功不证明任意泛化 |
| 延迟保持 | 写清保持的是哪项责任、先前表现依据、间隔、可比条件及期间练习／帮助背景 | 时间流逝不证明保持；强化后成功不证明无强化保持或永不遗忘 |

四方面是当前设计框架，不是已证实相互独立或穷尽所有领域的心理因子。独立性可同时约束解释、迁移和保持；保持必须指明保持求解还是解释等责任。一个方面可有必要的质量与覆盖条款，判断须保留未覆盖部分，不把四维及所有条件机械展开为笛卡尔积。扩展效率、精度、协作等时，先判断能否用现有方面的责任或质量条款表达，再决定是否增加内部方面。

**方法与知识。** 纳入方法 A、B 可以得到相关 KC 的覆盖并集，但任选 A 成功不能证明会用 B。指定 B 或要求两法分别覆盖时，按实际方法证据核对；方法覆盖是各方面依据的派生视图，不另建 Solution Belief。比较、选法等责任可以纳入适用方面或有依据扩展，不能因分别执行过两法就自动推断。KC 保留领域定义、关系、局部解释及教学作用；不创建 KCClaim / KCBelief，也不为全部 KC 换名生成 Task Claim。

**目标与个人判断分开。** Evaluation 定义 Claim、方面及 Belief 语义；Learning Space 的已发布目标选择任务范围、符合条件的 Claim 版本及所需方面／标准。只改变目标选择或门槛时重算 TargetAssessment，不直接改变个人能力判断；改变方面责任、方法要求、迁移范围或保持条件时，则须核对 Claim 语义版本与证据兼容。解释活动本身、一次正确或目标改版都不能直接上调 Belief。

**裁剪、未知与准备缺口。** 裁剪须有领域或目标依据，记录适用边界、对能力宣称的影响、责任人和版本；不能因为学生表现差、难取证、时点未到或实现未完成就声明不适用。运行中的 LLM 可提候选，不能自行发布定义或降低标准。首版管理员可兼任编辑、审核与发布者，仍保留各项依据。

采用的方面尚未定义完整是内容准备缺口；已有方面定义但无足够表现是认识不足；经批准不适用属于规范状态，不占一个“失败”或“零分”的个人方面。独立完成已有支持，解释仍未知、保持尚待观察，可以同时存在于一个 Belief 中。所有方面都有证据并不表示必须把它们平均成总掌握率。

**图 EVAL-01：单模板能力声明与多维判断。** 本图表达对象引用和证据去向，不规定数据库结构。

```mermaid
flowchart TB
    TT["Domain：TaskTemplate<br/>任务定义及版本"]
    C["Evaluation：Task Claim<br/>只绑定一个模板版本"]
    A["Claim 内部评价方面<br/>独立 · 理解 · 迁移 · 保持"]
    O["实际表现及上下文<br/>方法、帮助、变化与时间"]
    E["Evidence<br/>指向 Claim 版本与方面"]
    B["一个学习者的多维 Belief<br/>各方面的判断、不确定性与依据"]
    G["LearningTarget<br/>选择任务、方面与标准"]
    TA["派生 TargetAssessment"]
    C -->|"引用唯一模板"| TT
    C -->|"包含"| A
    A -->|"定义解释条件"| E
    O -->|"提供表现来源"| E
    E -->|"经推断按适用方面更新"| B
    G -->|"引用已发布声明及方面"| C
    G -->|"提供目标要求"| TA
    B -->|"提供分方面认识"| TA
```

矩形表示规范定义、来源或判断对象；箭头含义由标签说明。Aspect 包含于 Claim，多维判断包含于一个 Belief；两者不各自增加发布者或个人状态写入者。目标可以汇总多个任务的相应方面，图中仅画一个任务；同一 Claim 可用于不同学习者，其个人记录不混用。

本次简化减少顶层命题及引用关系，不消除分方面的证据与校准工作。若内部方面无法保留重要教学差异，先审查模板粒度、责任和方面定义；恢复多模板 Claim 或新增核心状态类型须另有实际证据和受治理决定。

### 3.2 Evidence Model：定义 Observation 对 Claim 的哪个方面意味着什么

Evidence Model 解释一次表现对某个已定义评价方面的意义，不直接形成最终 Belief。

\[
Evidence=Interpret(Observation,ClaimVersion,AspectKey,EpistemicContext,DomainSemantics)
\]

每条能力 Evidence 必须能定位 Claim 版本及方面，并保留实际任务／参数、方法、帮助、变化、时间和来源依赖。可以在一次解释中给出多个方面的关系，但不能只给一个笼统的“支持 Claim”就更新全部方面；方面不存在、未采用或定义不完整时保留相应准备／解析缺口，不临时创建规范定义。

同一次表现对不同方面可以有不同意义。例如比例题中正确列出单位量关系，却将 `42÷6` 算为 8：

- 独立完成方面：建模有局部支持，但最终求解不满足本次质量要求，保留正确部分与错误位置。
- 理解与解释方面：若未要求说明且没有足够过程依据，不能从列式正确直接断言理解，也不能把没有解释判为不会。
- 迁移、保持方面：只有实际变化和时间条件满足定义时才解释相应 Evidence；普通即时题不自动覆盖它们。
- 若过程中的除法子任务另有已发布模板及 Claim，且实际子任务表现足够清楚，可按该任务独立核对其方面；不能从母任务结果反推所有子任务或 KC 状态。

| Relation | 相对于明确方面的语义 |
| --- | --- |
| Supports | 该表现支持方面所定义的责任及条件 |
| Contradicts | 该表现对方面提供反向依据，须说明违背什么要求 |
| Discriminates | 帮助区分某方面的竞争解释或失配原因 |
| NonInformative | 对该方面没有足够信息价值，不等于失败 |

一条 Observation 可以形成多项方面关系，甚至在明确子任务映射下关联不同 Claim；必须保留同源标识，不增加虚假的独立样本。迁移来自任务 A 的学习经历、在任务 B 上表现时，正式评价指向 B 的 Claim 方面，A 是背景来源；B 方面须明示这种变化及依据。任务间结构相似或先修关系本身不授权复制 Belief。

### 3.3 Inference Model：决定当前应该相信什么

Inference Model 综合各方面先前判断、适用 Evidence、方面之间的实际依赖、时间与模型假设，更新一个 Task Claim 的多维 Belief。分方面记录不要求独立推断；共同推断须保留依赖依据，不能将一次表现当多份独立证据，也不能从已支持方面自动填满未检测方面。

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

## 4. Learner Belief：可修正的多维认识

一个 TaskProficiencyBelief 表达：DeerMind 对某位学习者在某个 Learning Space 中、某个明确版本 Task Claim 各方面能力的当前认识。Claim 定义评什么，Belief 保存各方面相信什么及为什么。

\[
Belief_t(L,S,C@v)=\{a\mapsto(Assessment_{t,a},EpistemicUncertainty_{t,a},EpistemicStatus_{t,a},EvidenceBasis_{t,a})\mid a\in ActiveAspects(C@v)\}
\]

这是一个 Belief 内部的方面映射，不新增四种 Belief 类型或四个顶层 Claim。方面是评价维度；Assessment、不确定性、认识状态和证据依据是每个方面都需要的认识组成，两组概念不可混用。每项还需可追溯的证据时间与更新依赖，具体存储协议由工程阶段实现。

一次 Evaluation 提交形成新的 Belief 修订。未受本次证据影响的方面保留原判断、依据及时间，不因其他方面更新而冒充已刷新。请求只需要某些方面时，按这些方面检查当前有效性；根对象存在或部分方面有效，不代表所有方面都已知、有效或达标。缺少所需定义／有效输入时按合同返回 non-resolution，允许认识不足的情况下明确返回 UNKNOWN，不用旧值冒充当前结果。

可以派生任务摘要，但摘要必须保留所用方面、范围与未知；不另存一个会与方面判断竞争的总掌握状态。目标是否达成由 TargetAssessment 比较实际采用的方面和标准。下文 Assessment、UNKNOWN、不确定性、Evidence Basis 与时间语义均落实到所讨论的具体方面。

### 4.1 Assessment：方向性判断

Assessment 回答：

> 综合适用 Evidence，DeerMind 对该 Claim 某个明确方面的方向性判断倾向是什么？

当前架构只冻结 Assessment 的语义，不冻结数值表示。System Design 可以比较 ordinal、probability、interval、分布或其他 calibrated 表示，只要它们保留这里定义的认识论含义。

\[
AssessmentSemantics\ first,
Representation\ deferred
\]

### 4.2 UNKNOWN：证据不足，不是 0.5

UNKNOWN 表示当前 Evidence 不足以支撑有根据的方向性判断。

\[
UNKNOWN(C,a)\neq Failure(C,a)
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
Belief[ClaimVersion,AspectKey]
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

一次表现的 Independent / Assisted 标记属于 Evidence Context，不是两套个人状态。Claim 的独立完成方面评价的是跨适用表现的能力；其他方面也可以要求特定独立责任。一次帮助对哪个方面有影响，取决于它替代了该方面要求学习者承担的哪项责任，不能把整份 Belief 一概标为受助或低能力。

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
ClaimVersion,
AspectKey,
ResponsibilityBoundary,
InterventionHistory
)
\]

同一个提示可能替代本 Claim 独立完成方面的选法责任，却未提供理解方面所要求的理由；也可能保留一个已明确定义的计算子任务责任。是否有支持要逐方面检查实际表现，不能仅凭提示没给答案就认定所有责任独立。对“独立形成诊断”与“验证 AI 候选诊断”这类不同评价条件，同一帮助可能有不同适用性，不能混用状态。

Evaluation 不能只知道“发生过帮助”，还必须能够追溯暴露链：帮助在什么时间发生、暴露了什么、替代了哪部分责任，以及这种替代与当前 Claim 的关系。

\[
NoAssistanceClassificationWithoutExposureLineage
\]

如果暴露链不完整，正确结果是降低 Evidence 可解释性或标记 support state unknown，而不是默认 Independent。

### 5.4 迁移与延迟：方面定义与实际条件分开

迁移和保持是同一 Task Claim 的内部方面，不再各建顶层 Claim。迁移方面规定参照经历、变化及仍须完成的责任；保持方面规定所保持责任、先前依据、间隔和期间支持条件。实际表征、间隔、练习和帮助进入 Evidence Context，是否满足这些定义仍须解释，不能只贴上“迁移”或“延迟”标签。

迁移范围仍以所绑定任务为评价对象。同模板内的表征变化可按已声明范围解释；从另一个模板的学习迁移到本任务时，来源模板只作为背景，正式方面仍属于目标任务 Claim。不把两个模板装进同一个 Claim，也不根据结构对应自动传播掌握结论。

保持可针对独立求解、解释或其他明确责任；一个方面的质量／覆盖条款须保留这些边界，不能把求解保持推广到所有能力。尚未到观察时点、期间背景未知或只覆盖一部分变化时，保留相应不足。不为每个间隔和表征新增顶层 Claim，也不在观察后修改定义来适配结果。

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

- 同一比例任务 Claim 的独立完成方面：本次最终求解未满足要求，单位量关系的正确列式保留为局部支持；
- 理解与解释方面：只有实际表达或过程足以支持规定责任时才形成相关 Evidence，未要求解释不记失败；
- 除法错误作为局部诊断依据；有明确子任务映射及适用计算 Claim 时才另行评价，否则保留观察，不增设 KC 状态。

如果 DeerMind 随后提示“再检查一下 42÷6”，学习者修正为 7 并得到 105，那么这次成功的 Evidence 需要按 Claim 与发生顺序解释。提示前已经呈现的 Unit Rate 策略保留原有证据价值，不能因后来的算术提示追溯性地判为受助选择；提示后的步骤也不能被重复计为一次新的独立策略选择。若评价计算责任，相应 Task Claim 的 Evidence 必须保留提示定位了错误这一步的条件；完整任务成功不能当作独立完成。

一周后学习者在新的表面情境中独立完成同构比例题，可补充该间隔与变化范围的证据；不能仅凭“延迟”或“新题”标签赋予固定更高权重，也不能据此宣称普遍迁移或长期保持。

如果之后学习者在 table 表示中持续失败，Inference 应保留 structured 冲突，而不是创建永久 `TableAbilityState`。必要时产生 System Signal，交给 Evolution 判断是否是 Task / KC / Observation / Evidence 模型失配。

这个例子展示了：

\[
Observation
\rightarrow
ClaimAspectSpecificEvidence
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

Learning Space 拥有 Target Requirement；Evaluation 拥有多维 Belief 与比较语义。一个目标可以引用多个任务 Claim 的指定方面及标准，TargetAssessment 逐项比较后组织目标结果；不由总分掩盖要求中的未知，不生成跨模板总能力 Claim，也不成为新的 Learner State。

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

### 6.8 分数应用：一个 Claim 的多维 Belief 更新实例

以下自编案例用于说明模型，不是正式教材包、已执行测量或经校准规则。TaskTemplate T1：已知原量 \(a>0\)，增加或减少原量的 \(r\)，求最终量；\(0<r<1\)，计数情境须有整数量。范围限于单次变化、原量作基准；不含连续变化、不同基准和逆求原量。

S1 先求 \(ar\)，再求 \(a\pm ar\)；S2 先求最终量比例 \(1\pm r\)，再求 \((1\pm r)a\)。KC 提供基准量、分数关系、同基准合并及计算等依据。当前评价条件允许任选 S1、S2。

定义一个 Claim **C-FA**，绑定 T1 的明确版本。下表 I、U、T、R 是该 Claim 内的方面键，不是四个 Claim 或四个独立状态类型。

| 内部方面 | C-FA 的方面定义 |
| --- | --- |
| I：独立完成 | 对熟悉文字表述，自行辨认原量、变化方向和最终量，选用获准方法正确求解；不接受定位、关系式或答案帮助 |
| U：理解与解释 | 独立用语言、图示或等价表达说明基准、变化量与最终量，不要求固定措辞，不把复述解析当理解 |
| T：迁移应用 | 已学习文字表述后，面对未练过的表格表述，仍能自行识别关系并求解；只对 T1 内这一规定变化作判断 |
| R：延迟保持 | 有先前独立求解依据，在预定间隔和可比条件下仍能独立求解；本例用七天说明时间合同，期间练习与帮助须记录。不是通用七天标准，也不宣称同时保持 U 或 T |

| 事件与表现 | 指向 C-FA 的 Evidence | 一个多维 Belief 的更新 |
| --- | --- | --- |
| 原有 40 本书，增加 1/4；答最终 10 本 | I 反向：混淆变化量与最终量；本次未要求解释，也未满足迁移／延迟条件 | I 增加未满足责任的依据；U、T、R 保留原判断或未知 |
| 提示“10 本是增加的，还是现在全部的？”后改为 50 | 记录定位帮助和订正；不满足 I 的独立条件 | 不用订正覆盖原错，也不将 I 改为独立通过；其余方面只按实际表现解释 |
| 新文字题：60 减少 1/5；独立写 60−60×1/5=48 | I 正向；保留刚接受同类教学背景 | 增加 I 的即时应用依据；U 未测，T 未发生规定变化，R 未到时点 |
| 后续文字题：80 增加 3/8；独立写 80×(1+3/8)=110，并说明共同基准 | I、U 正向，两个方面共用本次来源 | I、U 分别增加适用支持；不能把 T、R 填为通过，也不能将两个方面当成两份独立样本 |
| 七天后表格给出 72 减少 5/12；独立答 42 并解释 | 若表格确属规定变化、先前依据与期间条件满足定义，T、R 可获得正向 Evidence，表达也可能支持 U | 在同一 Belief 中更新适用方面，保留背景与来源。表格已反复练过则不支持本例 T；期间条件不明则限制 R 的结论 |

更新单位是 C-FA 的 Belief 修订，证据作用范围是具体方面。每个方面保留自己的 Assessment、不确定性、认识状态和依据；未更新方面不刷新证据时间。T 与 R 的联合探针失败时，不能直接判定是迁移困难还是未保持，可保留归因不确定，必要时安排可区分的后续观察；是否继续取证由 Interaction 按价值和负担决定。

**方法条件对照。** 若目标只提高正确性门槛，重新比较相同方面的判断，不改变 Belief。若要求从“任选 S1、S2”变为“两法分别覆盖”，改变的是评价责任，须绑定适用的新定义／版本；只有 S1 证据表示 S2 覆盖未知，不表示 S2 失败。不得直接复制旧 ANY 条件下的判断。

**任务绑定对照。** 逆求原量属于另一个模板 T2；本例 C-FA 不评价 T2。学生独立完成 T2 后，证据进入其已发布 Claim 的适用方面；两种任务的课程目标可一起汇总，彼此不自动推定掌握。T2 的迁移方面若将 T1 学习列为参照，仍只评价 T2 的迁移表现。

**历史迁移对照。** 前版 C1–C4 是已退出的组织方式。迁移时将旧责任逐项对应到新 Claim 的方面，核对模板、支持、变化和时间语义，并去除同源重复计权；不能仅把四个旧分数拼成向量。无法恢复适用依据的方面保持未知；没有领域或证据依据，不机械恢复 KC Claim 或跨模板 Claim。

运行链为：Interaction 保留具体题目、表现和帮助，形成 Observation；Evaluation 对 `C-FA@版本 + 方面键` 解释 Evidence，提交新的多维 Belief；TargetAssessment 比较目标选定方面；Interaction 据具体缺口选择下一步。没有统一题量、精确掌握率、先验或衰减公式被本例提前验证。

## 7. Cross-Space Contracts、版本与 Evolution

Evaluation 必须保持自己的认识职责，同时依赖其他 Space 提供规范坐标、当前 Observation、事实溯源信息和系统级演化机制。

### 7.1 Domain 与 Learning Space：规范输入分开

Domain 提供 TaskTemplate 的身份、版本、参数与责任范围，SolutionTemplate 的适用条件、子任务依赖及方法相关 grounding，以及 KC 的定义和适用条件。Learning Space 提供 LearningTarget 的版本、材料映射、范围、期望标准与支持责任。两组输入必须分别记录依赖，不能由一个含混的“学习空间版本”替代。

Interaction 提供实际问题的版本引用、参数、呈现条件、已发生的帮助和表现 Observation。实际采用何种方法需要行为依据，不能从参考 SolutionTemplate 反向推定。上传问题未映射、方法覆盖不完整或证据不足时，可保留未知，不伪造完备模型后再给出精确能力结论。

Evaluation 仅在明确任务范围、责任及方法要求上维护 TaskProficiencyClaim，并形成 Evidence、Belief 与派生 TargetAssessment；KC 只作为领域解释和教学依据。材料章节只提供产品汇总入口，不是新的能力本体；产品空间隔离与授权限制同样作用于 Evidence 的可用范围。

LearningTarget 按 §3.1 记录所选任务 Claim 版本、方面及标准；Evaluation 负责单模板声明、内部方面和多维判断。定义缺口由规范内容路径补齐，Runtime 不临时发布 Claim 或方面。目标可以跨任务汇总，但单个 Claim 不跨模板；目标本身不能生成 Evidence 或 Belief。

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

- Learner Claim 语义身份／版本、唯一 TaskTemplate 引用及内部方面键；
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

**D3 — 一个 Task Claim 绑定一个模板，并包含多个评价方面。**

同一评价条件下以一个 Claim 组织默认四维；方面有独立判断、未知及证据，不必各建顶层命题。TaskScope 限于所绑定模板；不同任务的目标汇总是派生比较，不能复制其 Belief。

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
| 实证性 | 选法等责任适合现有方面、扩展方面还是独立真实任务 | 按责任、证据与行动价值验证；不按每项责任机械另立 Claim 或 Strategy 状态 |
| 实证性 | 仅 Task Claim 是否跨数学、系统工程、写作等领域仍具有足够预测与教学价值 | 需跨域验证 |
| 实证性 | Responsibility-boundary-relative contamination 是否能预测后续表现 | 需真实 assistance / AI 使用数据 |
| 实证性 | Target Assessment 在高噪声开放任务中的校准质量 | 需长期数据 |
| 实证性 | Assistance / Support Dependency diagnostic 是否具有稳定预测与干预价值 | 暂保持 derived |
| 治理性 | 哪些 Population Prior 允许进入 Inference，如何审计公平风险 | 需 Product Constitution / Governance 细化 |
| 治理性 | 高风险 Target 的 Evidence threshold 与 Safety authority 如何交互 | 需 Context Constitution |
| 实现性 | Belief 与 Target Assessment 的 version pinning / invalidation 索引 | 交给 System Design |
| 实现性 | 单模板多维 Claim、方面 Evidence 与 Belief 的存储及局部有效性协议 | 语义与输入输出合同已定，字段及实现由 System Design／Phase 5 承接 |
| 实现性 | LLM 参与 Evidence / Inference 时如何保证依据可追踪 | 交给 AI Runtime / System Design |

### 8.4 本版下游传导

本版将 Claim 收敛为单模板、多方面的声明；Evidence 指向 Claim 版本与方面，Belief 保留分方面判断及有效性。概念、系统和 MVP 同步承接绑定、查询、失效与迁移条件；这不表示内容包或工程实现已经迁移。

实现不得引入第二 LearnerBelief writer、TargetBelief 或自动 Gap→Action 路径。TaskProficiencyClaim 标识继续使用，但必须检查 TaskScope、方法要求和历史证据兼容性；旧 KC 状态仅保留历史读取，不转换成新 Task 状态或经兼容回退进入当前决策。出现重要无法表达的反例再重新审查模型，不能在 Runtime 静默扩张认识权限。

多方面语义变更须核对旧 Claim 到新声明及方面的对应。跨多个模板的旧 Claim 需按任务拆解并重新核对证据；同模板的旧 C1–C4 可按语义对应合入方面，但不能按字段拼接判断。只在语义等价且来源完整、依赖去重的情况下显式保留既有方面判断；改变含义或缺乏来源时重解释，依据不足保持未知。定义版本变化不能自动刷新其余方面的证据时间。

## 附录 A — Evaluation Space Semantic Invariant Registry

正文只保留最核心的认识边界；以下 registry 用于设计审计、实现检查和跨版本回归。

| ID | Invariant | 含义 |
|---|---|---|
| E1 | No Belief Without Claim | 多维 Belief 对应明确单模板 Claim，方面判断有已发布的内部定义 |
| E2 | Observation != Evidence != Belief | 行为解释、证据关系与最终认识不可合并 |
| E3 | No Evidence Without Claim | 能力 Evidence 必须指向明确 Claim 版本与方面，不能无范围地更新全部判断 |
| E4 | Only Evaluation Writes Learner Belief | Learner Belief 只有 Evaluation 能修改 |
| E5 | Requirement != Evidence != Belief | Target requirement 不能直接生成 learner evidence / belief |
| E6 | Missing Evidence != Negative Evidence | 未观察到不能自动解释成不会 |
| E7 | EvidenceCondition != ClaimCondition | 条件默认属于 Evidence；只有改变能力语义才进入 Claim |
| E8 | Support Compatibility Is Claim-Relative | Assistance 的证据影响取决于 Claim / Responsibility Boundary |
| E9 | No Assistance Classification Without Exposure Lineage | 独立/受助判断必须有真实暴露链 |
| E10 | TaskOutcome != TaskPerformance != Capability | 现实结果、可归因表现与稳定能力必须分层 |
| E11 | 知识依据不等于个人能力状态 | KC 用于解释与教学；只维护 Task Claim Belief，不从任务成功扩写 KC 掌握 |
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
| E28 | Default Dimensions != Mandatory Tests Each Turn | 默认四维覆盖有版本，可有依据裁剪／扩展；未测与不适用分开，不强制每题四测 |
| E29 | Shared Observation != Independent Evidence | 多方面或已核对的多任务证据共享表现须保留共同来源，不重复计权 |
| E30 | One Claim References One TaskTemplate | 同一声明不跨模板；其方面是内部结构，不能独立漂移或发布 |
| E31 | Aspect Validity Is Explicit | 根 Belief 存在或一次更新不使所有方面自动有效、已知或达标 |

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
- 每个 Claim 是否只绑定一个模板，同一评价条件下四维是否组织为内部方面？
- 方面的范围、方法、帮助、变化与时间是否明确，裁剪与扩展是否有依据和版本？
- 是否把某方面的更新、当前有效或成功不当地扩展到全部方面／另一任务？
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

本版将单一 Task Claim 类型进一步收敛为单模板绑定、多方面定义；Belief 由单命题判断改为同一声明下的方面判断集合。默认四维及有依据裁剪／扩展继续有效。原多模板 Claim 和按四维拆分 C1–C4 的组织方式不再作为当前合同。Evidence、查询、有效性、版本迁移及例子已同步；不恢复个人 KC 状态。

旧 KCClaim / KCBelief 按原版本留在历史中，不删除、不作为当前能力输入、不直接改成 Task Claim。若原始表现足以支持新的明确任务命题，可经新版本 Evidence 解释与推断形成新 Belief，并保留原始来源及证据依赖；依据不足则 UNKNOWN。已有 Task Claim 也须核对责任、范围、方法和支持条件，不只改字段名。

旧 Freeze Gate、Spike、Build 和 G3 结果继续属于原基线。本轮只传导文档合同，不声称代码、领域包、评测参考或参数已迁移和通过验证。逐文件修订及未完成迁移见[模型复核 §11](DeerMind_Learning_Model_Reassessment.md#11-单模板多维-claim-的正式修订记录)。
