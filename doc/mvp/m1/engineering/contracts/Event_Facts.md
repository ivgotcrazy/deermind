# M1 事件正文与业务投影合同

> **版本**：v0.1<br>
> **状态**：事件事实源修订稿，待用户审阅；未编码<br>
> **维护与评审**：Codex编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-15<br>
> **修订说明**：事件正文、投影及来源的完整合同；见MVP决定登记§96

本册定义事件如何保存完整事实、生成业务查询数据，以及怎样安全重建。事件信封和通知载荷见[事件消息](Event_Messages.md)；表字段仍只在[数据库分册](../Database_Design.md)维护。新增的正文DTO和投影接线是本轮详细设计，待审阅；不增加页面或AI Operation。

## 1. 事实边界

事件及其不可变附件是历史事实的唯一来源。消息、教材候选、定义版本、活动、Evidence、Belief和目标结果是这些事实的业务投影；其当前索引可更新，原事件不能改写。业务模块仍拥有语义和校验权；底座只执行已登记的事件与投影机制。事件记录的是“当时接收、提供、判断或保存了什么”，不把AI结论当作永远正确的知识。

以下均须留痕：业务输入与正式输出、版本和采用变化、活动及检测轮变化、评价结果，以及工作受理、停止、失败、恢复、模型和工具请求结果。轮询、心跳、每个token、内部函数调用只记必要日志。写数据库前就被拒绝的传输包、服务完全不可用时的故障不能声称已经形成正式事件；恢复后只补记已核实的故障事实，不伪造发生时间。

owner_ref、subject_refs等只标识事件所描述的对象。历史原文不得依赖这些对象的业务行反查。引用另一件已发生的事实使用EventPartRef；教材原件、大图和模型材料使用不可变文件附件。密码、会话秘密、模型密钥和隐藏思考不写事件；运行控制表与Temporal内部数据仍按恢复合同备份，不能用业务投影重建来启动旧工作。

## 2. 正文结构

每个事件payload保留事件消息分册的业务定位字段，另含records数组（必填，允许[]）。本册§3登记的本次对象变化必须有对应记录；仅表达进入、接受/拒绝等动作的事件可只用其完整的类型化payload。不能用records=[]省略实际变化。

| 类型 / 字段 | JSON类型 | 必填与约束 |
| --- | --- | --- |
| FactRecord.record_id | string | 本事件内唯一，不从数组位置生成引用 |
| FactRecord.record_type | 登记名称 | §3中的精确名称；程序注册，不由模型选择表 |
| FactRecord.schema_version | integer | 本稿1；正文版本独立于事件信封版本 |
| FactRecord.content | ArtifactValue | 完整且通过该正文Schema校验；inline或固定file二选一；允许嵌套EventPartRef复用更早原文 |
| EventPartRef | {event_id:ID,record_id:string或null,path:string} | record_id非空定位FactRecord解码内容，null定位类型化payload；path是JSON Pointer，空串表示整个对象；不允许SQL/网络地址 |
| EventPartRef的授权 | 程序上下文 | 引用不授权；按事件范围、记录类型、用途和字段分别检查。事件列表可见不等于AI材料、记忆或作答原文可见 |

ArtifactValue沿数据库总册§3。文件先完整保存并核验hash，再把身份、hash和媒体类型写入事件；文件准备失败不提交事件。不覆盖已引用文件，事件引用期间不得删除。事务失败留下的未引用临时文件不算已发生的业务事实。正文hash按所登记Schema的固定编码计算；不同内容不得复用同一引用。

内部read_event_facts接收access_context、refs:EventPartRef[]、purpose:登记用途。成功返回items，顺序与refs一致；每项为ref、schema_ref:{record_type,schema_version}或{event_type,schema_version}、content:已授权内容、sha256、completeness:complete/incomplete及missing_reasons:string[]。缺失必须逐项明确；无权、非法片段或存储故障返回对应错误，不能伪装成完整空结果。不提供跨空间无界全文读取。

### 2.1 正文Schema与字段字典的关系

§3逐项登记的是固定业务快照DTO。其v1字段精确采用链接表的全部业务列，排除source_event_id，以及product.material_import.active_request_ref和next_message_seq；后两项分别是运行占用和可重算消息序号，不属于历史正文；各主键、版本、时间与可空约束保留。uuid/text映射string，bigint映射integer，boolean映射boolean，timestamptz映射UTC Timestamp，date映射YYYY-MM-DD字符串，数值映射有限JSON number，JSONB沿字段注明的业务Schema。所有字段都显式给出，SQL NULL映射JSON null；不依赖数据库默认值补全历史。

这是本次字段定义的复用，**不是运行时读取表生成事件，也不是允许事件执行任意表更新**。写入前由所有者构造并校验DTO，事件保存后由登记的投影器映射业务表。后续数据库列变更不会自动改变已登记DTO；需单独升正文Schema版本并保留旧解码器。业务数据不经事件API直接写入。

对payload、parts、content、request/response等嵌套正文，必须展开完整内容、使用ArtifactValue，或使用指向更早事件的EventPartRef。版本对象ID可以表达关系，但被引用定义本身也必须已有创建事实；原文、模型请求、参考答案不能只留下业务对象ID。读取和重建按事件及附件闭包完成。

同次提交的事件共用commit_id；互相关联对象先分配稳定ID，再作为一个批次提交；支持延迟约束。目录catalog_revision按该范围内改变可见内容的commit_id去重递增，不能一事件加一次。不可变版本遇同键异文报错；可变状态行只接受比当前source_event_id更新的同范围事件。投影器不能以当前时间、新UUID、当前配置或LLM补齐历史。

## 3. 事实正文与投影登记

下表record_type也是注册Schema的稳定名称，外观与首版表名一致，不授予表访问权限。一个事件可包含多条同类型记录；生产方只构造自己拥有的正文。跨模块消费者保存自己派生的新事实时另发本模块事件，不能给生产方事件补写内容。

| record_type（v1） | 字段定义 / 查询投影 | 产生事件 |
| --- | --- | --- |
| `ai.execution_configs` | [ai.execution_configs](../database/Business_AI.md#1-aiexecution_configs) | `AIConfigurationPinned` |
| `ai.ai_calls` | [ai.ai_calls](../database/Business_AI.md#2-aiai_calls) | `AICallChanged` |
| `ai.ai_call_attempts` | [ai.ai_call_attempts](../database/Business_AI.md#3-aiai_call_attempts) | `AICallChanged` |
| `ai.model_requests` | [ai.model_requests](../database/Business_AI.md#5-aimodel_requests) | `ModelRequestChanged` |
| `ai.tool_actions` | [ai.tool_actions](../database/Business_AI.md#6-aitool_actions) | `ToolActionChanged` |
| `ai.ai_candidates` | [ai.ai_candidates](../database/Business_AI.md#7-aiai_candidates) | `AICandidatePrepared` |
| `domain.object_version` | [domain.object_version](../database/Business_Domain.md#2-domainobject_version) | `DomainDefinitionSaved`、`DomainInstanceSaved` |
| `domain.intake_submission` | [domain.intake_submission](../database/Business_Domain.md#4-domainintake_submission) | `DomainIntakeReceived`、`DomainIntakeRejected` |
| `domain.intake_item` | [domain.intake_item](../database/Business_Domain.md#5-domainintake_item) | `DomainIntakeReceived`、`DomainIntakeItemProcessed`、`DomainIntakeSourceInvalidated` |
| `domain.artifact` | [domain.artifact](../database/Business_Domain.md#6-domainartifact) | `DomainTemplateCandidatePrepared`、`DomainClassificationPrepared` |
| `domain.kc_test_path` | [domain.kc_test_path](../database/Business_Domain.md#7-domainkc_test_path) | `DomainKCTestPathConfirmed` |
| `domain.supply_batch` | [domain.supply_batch](../database/Business_Domain.md#8-domainsupply_batch) | `DomainTaskSupplyCompleted` |
| `evaluation.claim_version` | [evaluation.claim_version](../database/Business_Evaluation.md#2-evaluationclaim_version) | `ClaimDefinitionChanged` |
| `evaluation.evaluation_input` | [evaluation.evaluation_input](../database/Business_Evaluation.md#3-evaluationevaluation_input) | `EvaluationInputPrepared` |
| `evaluation.interpretation` | [evaluation.interpretation](../database/Business_Evaluation.md#4-evaluationinterpretation) | `EvaluationInterpretationPrepared` |
| `evaluation.evidence` | [evaluation.evidence](../database/Business_Evaluation.md#5-evaluationevidence) | `BeliefEvaluationCompleted` |
| `evaluation.belief_revision` | [evaluation.belief_revision](../database/Business_Evaluation.md#6-evaluationbelief_revision) | `BeliefEvaluationCompleted` |
| `evaluation.mastery_snapshot` | [evaluation.mastery_snapshot](../database/Business_Evaluation.md#8-evaluationmastery_snapshot) | `BeliefEvaluationCompleted` |
| `evaluation.goal_calculation_input` | [evaluation.goal_calculation_input](../database/Business_Evaluation.md#10-evaluationgoal_calculation_input) | `GoalCalculationPrepared` |
| `evaluation.goal_evaluation` | [evaluation.goal_evaluation](../database/Business_Evaluation.md#11-evaluationgoal_evaluation) | `GoalEvaluationCompleted` |
| `interaction.inputs` | [interaction.inputs](../database/Business_Interaction.md#1-interactioninputs) | `InteractionInputAccepted`、`InteractionInputStopped`、`InteractionInputCompleted` |
| `interaction.messages` | [interaction.messages](../database/Business_Interaction.md#4-interactionmessages) | `ChatMessageRecorded` |
| `interaction.message_assignments` | [interaction.message_assignments](../database/Business_Interaction.md#5-interactionmessage_assignments) | `MessageAssigned` |
| `interaction.activities` | [interaction.activities](../database/Business_Interaction.md#6-interactionactivities) | `ActivityChanged` |
| `interaction.activity_revisions` | [interaction.activity_revisions](../database/Business_Interaction.md#7-interactionactivity_revisions) | `ActivityChanged` |
| `interaction.detection_plans` | [interaction.detection_plans](../database/Business_Interaction.md#9-interactiondetection_plans) | `DetectionPlanPrepared` |
| `interaction.plan_revisions` | [interaction.plan_revisions](../database/Business_Interaction.md#10-interactionplan_revisions) | `DetectionPlanPrepared`、`DetectionRoundStarted`、`DetectionRoundClosed` |
| `interaction.detection_rounds` | [interaction.detection_rounds](../database/Business_Interaction.md#12-interactiondetection_rounds) | `DetectionRoundStarted` |
| `interaction.round_revisions` | [interaction.round_revisions](../database/Business_Interaction.md#13-interactionround_revisions) | `DetectionRoundStarted`、`DetectionRoundClosed` |
| `interaction.task_uses` | [interaction.task_uses](../database/Business_Interaction.md#14-interactiontask_uses) | `TaskUseCreated` |
| `interaction.submissions` | [interaction.submissions](../database/Business_Interaction.md#15-interactionsubmissions) | `AnswerSubmitted` |
| `interaction.answer_feedback` | [interaction.answer_feedback](../database/Business_Interaction.md#16-interactionanswer_feedback) | `AnswerFeedbackPrepared` |
| `interaction.help_facts` | [interaction.help_facts](../database/Business_Interaction.md#17-interactionhelp_facts) | `HelpHandled` |
| `interaction.presentations` | [interaction.presentations](../database/Business_Interaction.md#18-interactionpresentations) | `PresentationRecorded` |
| `interaction.teaching_opportunities` | [interaction.teaching_opportunities](../database/Business_Interaction.md#19-interactionteaching_opportunities) | `TeachingOpportunityStarted`、`TeachingOpportunityClosed` |
| `interaction.opportunity_closures` | [interaction.opportunity_closures](../database/Business_Interaction.md#20-interactionopportunity_closures) | `TeachingOpportunityClosed` |
| `interaction.blueprint_revisions` | [interaction.blueprint_revisions](../database/Business_Interaction.md#21-interactionblueprint_revisions) | `ActivityConfigSaved` |
| `interaction.rule_revisions` | [interaction.rule_revisions](../database/Business_Interaction.md#22-interactionrule_revisions) | `ActivityConfigSaved` |
| `interaction.strategy_revisions` | [interaction.strategy_revisions](../database/Business_Interaction.md#23-interactionstrategy_revisions) | `ActivityConfigSaved` |
| `interaction.binding_revisions` | [interaction.binding_revisions](../database/Business_Interaction.md#24-interactionbinding_revisions) | `ActivityConfigSaved` |
| `interaction.resolved_configs` | [interaction.resolved_configs](../database/Business_Interaction.md#25-interactionresolved_configs) | `ActivityConfigSaved` |
| `interaction.decision_records` | [interaction.decision_records](../database/Business_Interaction.md#27-interactiondecision_records) | `InteractionDecisionRecorded` |
| `interaction.context_bundles` | [interaction.context_bundles](../database/Business_Interaction.md#28-interactioncontext_bundles) | `InteractionContextPrepared` |
| `interaction.memory_revisions` | [interaction.memory_revisions](../database/Business_Interaction.md#29-interactionmemory_revisions) | `InteractionMemorySaved` |
| `interaction.proactive_checks` | [interaction.proactive_checks](../database/Business_Interaction.md#31-interactionproactive_checks) | `ProactiveCheckCompleted` |
| `interaction.proactive_tasks` | [interaction.proactive_tasks](../database/Business_Interaction.md#32-interactionproactive_tasks) | `ProactiveTaskChanged` |
| `interaction.proactive_revisions` | [interaction.proactive_revisions](../database/Business_Interaction.md#33-interactionproactive_revisions) | `ProactiveTaskChanged`、`ProactiveTaskResponded` |
| `interaction.proactive_prompts` | [interaction.proactive_prompts](../database/Business_Interaction.md#34-interactionproactive_prompts) | `ProactiveTaskPrompted` |
| `product.accounts` | [product.accounts](../database/Business_Product.md#1-productaccounts) | `TrialAccountSaved`、`AccountRecovered` |
| `product.guardian_records` | [product.guardian_records](../database/Business_Product.md#4-productguardian_records) | `UsageConfirmationRecorded` |
| `product.student_guardian_relations` | [product.student_guardian_relations](../database/Business_Product.md#5-productstudent_guardian_relations) | `UsageConfirmationRecorded` |
| `product.usage_confirmations` | [product.usage_confirmations](../database/Business_Product.md#6-productusage_confirmations) | `UsageConfirmationRecorded` |
| `product.textbook` | [product.textbook](../database/Business_Product.md#8-producttextbook) | `MaterialReceived`、`MaterialMetadataSaved` |
| `product.material_import` | [product.material_import](../database/Business_Product.md#9-productmaterial_import) | `MaterialReceived`、`MaterialMetadataSaved`、`MaterialImportDeleted`、`MaterialCandidatesAdopted` |
| `product.material_source` | [product.material_source](../database/Business_Product.md#10-productmaterial_source) | `MaterialReceived`、`MaterialMetadataSaved` |
| `product.material_message` | [product.material_message](../database/Business_Product.md#11-productmaterial_message) | `MaterialAssistantMessageReceived`、`MaterialAssistantTurnFinished` |
| `product.material_turn` | [product.material_turn](../database/Business_Product.md#12-productmaterial_turn) | `MaterialAssistantMessageReceived`、`MaterialAssistantTurnFinished` |
| `product.material_candidate_batch` | [product.material_candidate_batch](../database/Business_Product.md#13-productmaterial_candidate_batch) | `MaterialCandidatePrepared` |
| `product.material_candidate` | [product.material_candidate](../database/Business_Product.md#14-productmaterial_candidate) | `MaterialCandidatePrepared` |
| `product.material_adoption` | [product.material_adoption](../database/Business_Product.md#16-productmaterial_adoption) | `MaterialCandidatesAdopted` |
| `product.material_chapter` | [product.material_chapter](../database/Business_Product.md#17-productmaterial_chapter) | `MaterialCandidatesAdopted` |
| `product.material_intake_submission` | [product.material_intake_submission](../database/Business_Product.md#18-productmaterial_intake_submission) | `DomainIntakeRequested`、`MaterialIntakeStatusUpdated` |
| `product.chapter_association` | [product.chapter_association](../database/Business_Product.md#19-productchapter_association) | `ChapterAssociationSaved` |
| `product.learning_target` | [product.learning_target](../database/Business_Product.md#21-productlearning_target) | `LearningTargetSaved` |
| `product.learning_target_version` | [product.learning_target_version](../database/Business_Product.md#22-productlearning_target_version) | `LearningTargetSaved` |
| `product.application_check` | [product.application_check](../database/Business_Product.md#23-productapplication_check) | `ApplicationChecked` |
| `product.course_application` | [product.course_application](../database/Business_Product.md#24-productcourse_application) | `CourseApplied` |
| `product.target_basis` | [product.target_basis](../database/Business_Product.md#26-producttarget_basis) | `CourseApplied` |
| `product.learning_space` | [product.learning_space](../database/Business_Product.md#27-productlearning_space) | `LearningSpaceCreated`、`LearningSpaceAdoptionChanged` |
| `product.space_adoption` | [product.space_adoption](../database/Business_Product.md#28-productspace_adoption) | `LearningSpaceCreated`、`LearningSpaceAdoptionChanged` |
| `interaction.input_results` | [interaction.input_results](../database/Business_Interaction.md#2-interactioninput_results) | `InteractionInputCompleted`、`InteractionInputStopped` |
| `interaction.plan_progress` | [interaction.plan_progress](../database/Business_Interaction.md#11-interactionplan_progress) | `DetectionPlanPrepared`、`DetectionRoundStarted`、`DetectionRoundClosed` |
| `product.usage_conditions` | [product.usage_conditions](../database/Business_Product.md#7-productusage_conditions) | `UsageConfirmationRecorded`、`TrialAccountSaved`、`AccountRecovered` |

product.material_intake_submission的接收状态由Domain接收事件驱动：Product消费后追加MaterialIntakeStatusUpdated并投影自己的记录，不在Domain事件中夹带Product正文。此例说明“消费者自己加工”与“生产者同步投影”并不冲突。

### 3.1 派生索引与控制数据

| 类别 | 数据 | 生成或恢复方式 |
| --- | --- | --- |
| 当前版本索引 | Domain对象身份/头、Claim身份/头、活动/配置/记忆头、目标/掌握当前索引 | 从对应已记录版本的正式选用顺序生成；不能简单取最大ID |
| 关系与覆盖索引 | object_reference、material_content_current、application_head | 从版本正文、采用/同意/完成事实确定性计算；保存索引与投影收据同事务 |
| 业务中包含的当前引用 | learning_space.current_adoption_ref等 | 由对应采用事件的完整快照更新；重建不重新判断目标达成 |
| 控制与秘密 | 命令收据、登录会话/凭据、space_runtime、resume_actions、evaluation_progress、AI预算预约、执行/等待/交接表 | 不在业务投影重建中重启或替换。按运行恢复/整套备份恢复；其重要状态变化另有事件，不能用控制行替代历史事实 |
| 文件及执行产物 | file_objects及文件、step_results、published_results | 原件和已保存步骤保留；正式输出的内容来源是事件或事件附件。文件位置、执行接续仍由原子系统维护 |

各表分类见[数据库总册§3.1](../Database_Design.md#31-事实投影与控制数据)。表的source_event_id指向支撑该行内容的事件；已有event_ref若表示该行的生成事件，则与source_event_id同值；trigger_event_id等输入来源仍指向先前事实，不能改成结果事件；对应正文用record_type及该行主键唯一定位，不能只根据最后更新时间猜来源。

## 4. 写入与消费

生产者：事务外完成AI和文件准备 → 按既定锁序检查条件 → 追加完整事件 → 同事务投影本模块业务对象及投影收据 → 保存命令收据、结果和待发安排 → 提交 → 返回/通知。失败整笔回滚；同一命令重试取得原收据，不新增第二件事实。

消费者：收到通知 → 核验正式事件及权限 → 可靠保存承接收据和执行安排 → Ack → 按本模块规则处理。产生新判断时追加自己的结果事件，再同步生成自己的查询投影。结果的因果引用指向所用源事件；不能修改生产者事实。

历史补读和实时接续按[公共运行§2.6](../System_Foundation_Design.md#26-历史补读实时接续与重建)。每范围独立顺序，跨范围依赖按EventPartRef先后解决；前置事件暂未处理则阻塞相关投影，不能跳过后宣称完整。业务订阅默认从启用后开始；新增投影可显式补读历史。

## 5. 重建与验收

M1只提供受控维护重建，不新增管理页面。维护窗口停止相关写入，固定各范围上界；在线代次为1，重建使用独立代次，完成时按公共运行§2.6原子接回在线收据和进度；在临时关系中按登记Schema和确定性投影器重建，先从事件的登记正文建立业务身份/版本到来源事件的索引，再按因果依赖与范围序号生成，最后按既定FK顺序整体替换查询数据。临时索引属于本次重建，不增加另一份事实源。保留原业务ID、时间、版本、概率及依据，不产生新业务事件、通知、模型调用、工具副作用或待办。仅追加一次维护结果留痕；失败保留旧查询数据。

事件及附件缺失、Schema不支持、来源闭包不完整、同键异文均中止重建并报告范围；不能猜测补全。运行控制数据不属于替换集合；material_import.active_request_ref保持运行恢复的决定，next_message_seq从已记录消息序号重算，不恢复成历史忙碌状态。其恢复另按Execution/Attempt/Step、Wait及整批备份合同执行。

| 场景 | 必须满足 |
| --- | --- |
| 事件成功、投影失败 | 整个生产事务回滚，不能返回成功 |
| 重复投递/重建 | 同代次、同投影器、同事件只应用一次；新代次可重新生成 |
| 清空测试副本的业务查询表 | 仅凭事件、固定附件和登记解码器恢复相同业务内容；不要求其他业务表充当原文来源 |
| 来源是聊天作答或答题区提交 | 均可由EventPartRef读到实际原文；只接收一次AnswerSubmitted语义 |
| 重建含AI/Evidence/Belief数据 | 使用已经记录的输出和概率；AI调用数、通知数、教学任务数均为0 |
| 补读期间出现实时事件 | 固定上界前无漏项，上界后连续接续；重复通知不重复产生业务效果 |
| 无权读私有材料 | 只返回已授权字段；不能通过事件源绕过Space权限 |

以上为实现验收条件，本轮只做文档检查。设计采用事件存储与查询投影的分工；参考[Event Sourcing模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)与[重放的外部副作用边界](https://martinfowler.com/eaaDev/EventSourcing.html#ExternalUpdates)。不引入独立事件数据库或新的消息系统。

## 修订记录

| 版本 | 日期 | 修改 |
| --- | --- | --- |
| v0.1 | 2026-11-15 | 登记完整正文、逐类投影、原文追溯与无副作用重建；待审阅 |
