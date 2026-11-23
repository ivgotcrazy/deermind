# M1 事件正文与业务投影合同

> **版本**：v0.16<br>
> **状态**：设计合同；实际接线范围和进度见实施计划，不表示本册全部已实现<br>
> **维护与评审**：Codex编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-23<br>
> **修订说明**：v0.15 → v0.16，登记首次活动蓝图及节点移除的绑定记录<br>

本册定义事件如何保存完整事实、生成业务查询数据，以及怎样安全重建。事件信封和通知载荷见[事件消息](Event_Messages.md)；表字段仍只在[数据库分册](../Database_Design.md)维护。新增的正文DTO和投影接线是本轮详细设计，待审阅；不增加页面或AI Operation。

E01-05接线初始账号事实、生产者投影及收据；E01-06新增FileReceived及完整DTO附件，事件引用不代替正文校验；E01-08接线初始账号受控重建及维护结果；其余类型按所属增量实施。既有事实保存见[E01-05](../../../../../src/m1/deploy/environments/local-wsl/E01-05-facts.md)，文件与附件见[E01-06](../../../../../src/m1/deploy/environments/local-wsl/E01-06-files.md)，授权查询见[E01-07](../../../../../src/m1/deploy/environments/local-wsl/E01-07-reads.md)，进度以[实施计划](../Delivery_Plan.md)为准。

## 1. 事实边界

事件及其不可变附件是历史事实的唯一来源。消息、教材候选、定义版本、活动、Evidence、Belief和目标结果是这些事实的业务投影；其当前索引可更新，原事件不能改写。业务模块拥有投影转换、写入和校验；底座只保存、查询、投递事件并提供通用控制记录。事件记录的是“当时接收、提供、判断或保存了什么”，不把AI结论当作永远正确的知识。

以下均须留痕：业务输入与正式输出、版本和采用变化、活动及检测轮变化、评价结果，以及工作受理、停止、失败、恢复、模型和工具请求结果。轮询、心跳、每个token、内部函数调用只记必要日志。写数据库前就被拒绝的传输包、服务完全不可用时的故障不能声称已经形成正式事件；恢复后只补记已核实的故障事实，不伪造发生时间。

owner_ref、subject_refs及message_ref、submission_ref、reply_ref等对象引用只标识事件描述的业务身份；它们不是指向必须先存在的投影行。生产方先分配业务ID，事件与投影共同提交，重建沿用相同ID及关系，不重新分配。历史原文不得依赖这些对象的业务行反查。引用另一件已发生的事实使用EventPartRef；教材原件、大图和模型材料使用不可变文件附件。密码、会话秘密、模型密钥和隐藏思考不写事件；运行控制表与Temporal内部数据仍按恢复合同备份，不能用业务投影重建来启动旧工作。

## 2. 正文结构

每个事件payload保留事件消息分册的业务定位字段，另含records数组（必填，允许[]）。本册§3登记的本次对象变化必须有对应记录；仅表达进入、接受/拒绝等动作的事件可只用其完整的类型化payload。不能用records=[]省略实际变化。

| 类型 / 字段 | JSON类型 | 必填与约束 |
| --- | --- | --- |
| FactRecord.record_id | string | 本事件内唯一，不从数组位置生成引用 |
| FactRecord.record_type | 登记名称 | §3中的精确名称；程序注册，不由模型选择表 |
| FactRecord.schema_version | integer | 本稿1；正文版本独立于事件信封版本 |
| FactRecord.content | ArtifactValue | inline或固定file二选一；解包后必须是完整DTO并通过对应Schema。EventPartRef仅可出现在Schema明确声明的来源/依据字段，不能替代必填正文 |
| EventPartRef | {event_id:ID,record_id:string或null,path:string} | record_id非空定位FactRecord解码内容，null定位类型化payload；path是JSON Pointer，空串表示整个对象；不允许SQL/网络地址 |
| EventPartRef的授权 | 程序上下文 | 引用不授权；按事件范围、记录类型、用途和字段分别检查。事件列表可见不等于AI材料、记忆或作答原文可见 |

ArtifactValue沿数据库总册§3。文件先完整保存并核验hash，再把身份、hash和媒体类型写入事件；文件准备失败不提交事件。不覆盖已引用文件，事件引用期间不得删除。事务失败留下的未引用临时文件不算已发生的业务事实。正文hash按所登记Schema的固定编码计算；不同内容不得复用同一引用。

内部read_facts读取单个事件：scope种类、scope ID和事件ID必填；refs逐项点名记录及JSON Pointer，必须属于该事件。调用方可进一步限定事件类型、版本、correlation_id。返回items与refs同序，包含ref、schema_ref、content、sha256、visible_paths、visibility、completeness和missing_reasons。引用的目标另行授权读取。

### 2.1 正文Schema与字段字典的关系

§3逐项登记的是固定业务快照DTO。其v1字段精确采用链接表的全部业务列，排除source_event_id，以及product.material_import.active_request_ref和next_message_seq；后两项分别是运行占用和可重算消息序号，不属于历史正文；各主键、版本、时间与可空约束保留。uuid/text映射string，bigint映射integer，boolean映射boolean，timestamptz映射UTC Timestamp，date映射YYYY-MM-DD字符串，数值映射有限JSON number，JSONB沿字段注明的业务Schema。所有字段都显式给出，SQL NULL映射JSON null；不依赖数据库默认值补全历史。

这是本次字段定义的复用，**不是运行时读取表生成事件，也不是允许事件执行任意表更新**。写入前由所有者构造并校验DTO，事件保存后由所属业务的生成器映射查询表。后续数据库列变更不会自动改变已登记DTO；需单独升正文Schema版本并保留旧解码器。业务数据不经事件API直接写入。

消息parts、教材消息body及提交answer保存完整正文；学生输入和消息允许重复保存文字，聊天转作答也保留本次完整answer。图片等按其Schema保留不可变附件引用。大DTO可整体放入FactRecord.content.file，读取文件后仍须得到同一个完整DTO；不在表的parts里塞入另一种未定义类型。

EventPartRef只表达已声明的来源、证据或取材关系；不是任意字段的替身。模型request/response等字段只有其Schema已声明ArtifactValue时才可外置，不递归猜测解引用。原业务ID表示身份，不能替代原文；投影按正文和附件解包，不靠消息业务表或LLM补全。

同次提交的事件共用commit_id；互相关联对象先分配稳定ID，再作为一个批次提交；支持延迟约束。目录catalog_revision按该范围内改变可见内容的commit_id去重递增，不能一事件加一次。不可变版本遇同键异文报错；可变状态行按其所属范围的scope_event_seq更新；不比较UUID大小。同一commit内仍按范围序号，跨范围不得竞争覆盖同一业务行。投影器不能以当前时间、新UUID、当前配置或LLM补齐历史。

### 2.2 原文读取用途与权限

下表描述业务用例的权限。业务入口从已核验的会话、执行或维护任务确定可用范围、来源、记录与字段，再调用底座。用途名不能作为授权凭据。

| purpose | 调用方 | 允许记录及字段 | 范围与限制 |
| --- | --- | --- | --- |
| student_history | 已核验学生身份的查询入口（含runtime事件查询） | interaction.{inputs,messages,message_assignments,activities,activity_revisions,task_uses,submissions,answer_feedback,help_facts}的本人可见片段；evaluation.{evidence,mastery_snapshot,goal_evaluation}的公开解释 | 仅本人空间；输入控制字段、未展示答案、私有Context/Memory、AI/运行材料不返回 |
| admin_review | 已核验管理员身份的管理查询（含runtime事件查询） | 所管理资源对应的product/domain正文、evaluation.claim_version、Interaction四类配置及resolved_configs；空间追溯采用student_history集合及evaluation.belief_revision | 各查询入口进一步限制字段；账号/监护敏感依据不在通用事件页返回；不返回私有记忆或整份模型请求 |
| material_processing | 教材助手 | product.{textbook,material_import,material_source,material_message,material_turn,material_candidate_batch,material_candidate,material_adoption,material_chapter} | 由本次导入及显式引用圈定；不取学生空间原文 |
| domain_intake | Domain入库/归类处理 | product.{material_intake_submission,material_candidate,material_candidate_batch,material_adoption,material_source}；domain.{object_version,artifact,intake_item,intake_submission} | 精确提交及依赖闭包；不遍历教材或学生对话 |
| task_supply | Domain供题 | domain.{object_version,supply_batch}；interaction.{task_uses,presentations} | 接触事实仅题目身份、使用/呈现条件和时间；不读作答、聊天、Belief或私有记忆 |
| learning_context | Interaction Operation | 本Space已授权正文；domain.{object_version,supply_batch}；product.{space_adoption,target_basis,course_application,chapter_association,material_chapter,material_source}；evaluation.{claim_version,mastery_snapshot,goal_evaluation}公开字段 | 依本次活动和采用范围；本Space私有context_bundles/memory_revisions仅本用途；参考可读与可展示分别判断；不读Evaluation私有解释 |
| evaluation_basis | Evaluation处理器/Operation | interaction.{inputs,messages,submissions,task_uses,activities,activity_revisions,detection_plans,plan_revisions,plan_progress,detection_rounds,round_revisions,help_facts,answer_feedback,teaching_opportunities,opportunity_closures,presentations}；domain.object_version；product.{space_adoption,target_basis,course_application}；本Space评价正文 | 必须绑定来源事件和获准Task范围；不读未提交草稿、Interaction Context/Memory及AI完整请求 |
| execution_support | runtime/AI的授权执行或维护处理器 | 指定执行的AI配置、调用、请求、工具、候选及runtime历史核对记录；已获准的业务输入/步骤片段 | 必须有execution/attempt或维护授权；技术身份不开放任意学生资料；不含密钥 |
| projection_rebuild | 所属业务的受控维护处理器 | 获准范围内该业务投影必需的完整DTO、来源和附件 | 固定上界/投影器/代次；当前账号为product.account_rebuild；不开放给浏览器或Agent工具，不调用模型、通知或业务任务 |

花括号为精确record_type后缀集合；“本Space正文”仅指§3中该所有者已登记类型，不包含其他模块。四类配置指blueprint_revisions、rule_revisions、strategy_revisions、binding_revisions。业务所有者仍要逐字段收窄；模块在白名单不表示其所有学生数据可读。

业务入口逐次核对表中的账号、资源、执行及来源约束。底座执行显式条件；不匹配时不给出其他范围是否存在该事件的信息。缺字段按incomplete返回；非法片段或附件故障明确失败。

record_id=null的payload读取仍按事件类型和字段授权：业务消费者只读其已登记触发事件及本次关联事实；例如Domain供题读取TaskSupplyRequested，目标计算读取LearningTargetApplied。它不开放同范围全部事件。浏览器只取R05/R06公开视图；维护纯动作只对相应维护授权可见。

### 2.3 消息正文校验顺序

1. 生产方分配input_id、message_id、submission_id和事件ID；检查正文及附件权限。
2. InputAccepted保留完整输入；ChatMessageRecorded保留完整parts；若构成作答，AnswerSubmitted保留完整answer。三者语义不同，来源关系记录在各自已定义字段。
3. 校验事件类型及§3.2的记录集合，再解包各ArtifactValue并校验DTO、业务主键和payload身份的一致性。
4. 同事务追加事件、投影及收据。重建采用同一校验和转换；缺记录、错身份、未知类型或附件不完整均拒绝，不生成半份消息。


**取材边界。** record_id为空时只能选动作字段；空路径显式选择该对象全部内容，动作对象始终排除records。读取记录必须点名record_id。列表只提供源事件的元数据，可见摘要和对外游标归业务入口。

业务入口选材后，底座核对附件的后端、类别、事件ID＋record_id归属、媒体类型、长度、哈希、规范编码及记录Schema。账号重建按投影器选定类型执行完整事件校验，其余事件仅检查序号。预算见[基础设施§4.5](../Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)。

## 3. 事实正文与投影登记

下表维护73类业务正文及主键。A为不可变记录首次追加；S为同一主键的完整状态快照，首次创建、后续按来源顺序更新。已存在A记录再次引用时不重发其正文；同一提交只由一个事实事件创建。事件到正文的唯一映射见§3.2，不能只从表名猜测事件内容。生产方只构造自己拥有的正文；跨模块消费者产生自己的事实。

| record_type（v1） | 字段定义 / 查询投影 | 主键 | 写入 |
| --- | --- | --- | --- |
| `ai.execution_configs` | [ai.execution_configs](../database/Business_AI.md#1-aiexecution_configs) | `(execution_id)` | A |
| `ai.ai_calls` | [ai.ai_calls](../database/Business_AI.md#2-aiai_calls) | `(call_id)` | S |
| `ai.ai_call_attempts` | [ai.ai_call_attempts](../database/Business_AI.md#3-aiai_call_attempts) | `(call_id,attempt_id)` | S |
| `ai.model_requests` | [ai.model_requests](../database/Business_AI.md#5-aimodel_requests) | `(call_id,attempt_id,request_ordinal,transport_attempt)` | S |
| `ai.tool_actions` | [ai.tool_actions](../database/Business_AI.md#6-aitool_actions) | `(tool_action_key,attempt_id)` | S |
| `ai.ai_candidates` | [ai.ai_candidates](../database/Business_AI.md#7-aiai_candidates) | `(candidate_id)` | A |
| `domain.object_version` | [domain.object_version](../database/Business_Domain.md#2-domainobject_version) | `(object_id,version)` | A |
| `domain.intake_submission` | [domain.intake_submission](../database/Business_Domain.md#4-domainintake_submission) | `(submission_id)` | A |
| `domain.intake_item` | [domain.intake_item](../database/Business_Domain.md#5-domainintake_item) | `(item_id)` | S |
| `domain.artifact` | [domain.artifact](../database/Business_Domain.md#6-domainartifact) | `(artifact_id)` | A |
| `domain.kc_test_path` | [domain.kc_test_path](../database/Business_Domain.md#7-domainkc_test_path) | `(confirmation_id)` | A |
| `domain.supply_batch` | [domain.supply_batch](../database/Business_Domain.md#8-domainsupply_batch) | `(batch_id)` | A |
| `evaluation.claim_version` | [evaluation.claim_version](../database/Business_Evaluation.md#2-evaluationclaim_version) | `(claim_id,revision)` | A |
| `evaluation.evaluation_input` | [evaluation.evaluation_input](../database/Business_Evaluation.md#3-evaluationevaluation_input) | `(input_id)` | A |
| `evaluation.interpretation` | [evaluation.interpretation](../database/Business_Evaluation.md#4-evaluationinterpretation) | `(interpretation_id)` | A |
| `evaluation.evidence` | [evaluation.evidence](../database/Business_Evaluation.md#5-evaluationevidence) | `(evidence_id)` | A |
| `evaluation.belief_revision` | [evaluation.belief_revision](../database/Business_Evaluation.md#6-evaluationbelief_revision) | `(belief_revision_id)` | A |
| `evaluation.mastery_snapshot` | [evaluation.mastery_snapshot](../database/Business_Evaluation.md#8-evaluationmastery_snapshot) | `(snapshot_id)` | A |
| `evaluation.goal_calculation_input` | [evaluation.goal_calculation_input](../database/Business_Evaluation.md#10-evaluationgoal_calculation_input) | `(input_id)` | A |
| `evaluation.goal_evaluation` | [evaluation.goal_evaluation](../database/Business_Evaluation.md#11-evaluationgoal_evaluation) | `(goal_evaluation_id)` | A |
| `interaction.inputs` | [interaction.inputs](../database/Business_Interaction.md#1-interactioninputs) | `(input_id)` | A |
| `interaction.messages` | [interaction.messages](../database/Business_Interaction.md#4-interactionmessages) | `(message_id)` | A |
| `interaction.message_assignments` | [interaction.message_assignments](../database/Business_Interaction.md#5-interactionmessage_assignments) | `(message_id)` | S |
| `interaction.activities` | [interaction.activities](../database/Business_Interaction.md#6-interactionactivities) | `(activity_id)` | A |
| `interaction.activity_revisions` | [interaction.activity_revisions](../database/Business_Interaction.md#7-interactionactivity_revisions) | `(activity_id,revision)` | A |
| `interaction.detection_plans` | [interaction.detection_plans](../database/Business_Interaction.md#9-interactiondetection_plans) | `(plan_id)` | A |
| `interaction.plan_revisions` | [interaction.plan_revisions](../database/Business_Interaction.md#10-interactionplan_revisions) | `(plan_id,revision)` | A |
| `interaction.detection_rounds` | [interaction.detection_rounds](../database/Business_Interaction.md#12-interactiondetection_rounds) | `(round_id)` | A |
| `interaction.round_revisions` | [interaction.round_revisions](../database/Business_Interaction.md#13-interactionround_revisions) | `(round_id,revision)` | A |
| `interaction.task_uses` | [interaction.task_uses](../database/Business_Interaction.md#14-interactiontask_uses) | `(task_use_id)` | A |
| `interaction.submissions` | [interaction.submissions](../database/Business_Interaction.md#15-interactionsubmissions) | `(submission_id)` | A |
| `interaction.answer_feedback` | [interaction.answer_feedback](../database/Business_Interaction.md#16-interactionanswer_feedback) | `(feedback_id)` | A |
| `interaction.help_facts` | [interaction.help_facts](../database/Business_Interaction.md#17-interactionhelp_facts) | `(help_id,stage)` | A |
| `interaction.presentations` | [interaction.presentations](../database/Business_Interaction.md#18-interactionpresentations) | `(presentation_id)` | A |
| `interaction.teaching_opportunities` | [interaction.teaching_opportunities](../database/Business_Interaction.md#19-interactionteaching_opportunities) | `(opportunity_id)` | A |
| `interaction.opportunity_closures` | [interaction.opportunity_closures](../database/Business_Interaction.md#20-interactionopportunity_closures) | `(opportunity_id)` | A |
| `interaction.blueprint_revisions` | [interaction.blueprint_revisions](../database/Business_Interaction.md#21-interactionblueprint_revisions) | `(blueprint_id,revision)` | A |
| `interaction.rule_revisions` | [interaction.rule_revisions](../database/Business_Interaction.md#22-interactionrule_revisions) | `(rule_id,revision)` | A |
| `interaction.strategy_revisions` | [interaction.strategy_revisions](../database/Business_Interaction.md#23-interactionstrategy_revisions) | `(strategy_id,revision)` | A |
| `interaction.binding_revisions` | [interaction.binding_revisions](../database/Business_Interaction.md#24-interactionbinding_revisions) | `(binding_id,revision)` | A |
| `interaction.resolved_configs` | [interaction.resolved_configs](../database/Business_Interaction.md#25-interactionresolved_configs) | `(config_id)` | A |
| `interaction.decision_records` | [interaction.decision_records](../database/Business_Interaction.md#27-interactiondecision_records) | `(decision_id)` | A |
| `interaction.context_bundles` | [interaction.context_bundles](../database/Business_Interaction.md#28-interactioncontext_bundles) | `(bundle_id)` | A |
| `interaction.memory_revisions` | [interaction.memory_revisions](../database/Business_Interaction.md#29-interactionmemory_revisions) | `(memory_id,revision)` | A |
| `interaction.proactive_checks` | [interaction.proactive_checks](../database/Business_Interaction.md#31-interactionproactive_checks) | `(check_id)` | A |
| `interaction.proactive_tasks` | [interaction.proactive_tasks](../database/Business_Interaction.md#32-interactionproactive_tasks) | `(task_id)` | A |
| `interaction.proactive_revisions` | [interaction.proactive_revisions](../database/Business_Interaction.md#33-interactionproactive_revisions) | `(task_id,revision)` | A |
| `interaction.proactive_prompts` | [interaction.proactive_prompts](../database/Business_Interaction.md#34-interactionproactive_prompts) | `(prompt_id)` | A |
| `product.accounts` | [product.accounts](../database/Business_Product.md#1-productaccounts) | `(account_id)` | S |
| `product.guardian_records` | [product.guardian_records](../database/Business_Product.md#4-productguardian_records) | `(guardian_id)` | A |
| `product.student_guardian_relations` | [product.student_guardian_relations](../database/Business_Product.md#5-productstudent_guardian_relations) | `(relation_id)` | A |
| `product.usage_confirmations` | [product.usage_confirmations](../database/Business_Product.md#6-productusage_confirmations) | `(confirmation_id)` | A |
| `product.textbook` | [product.textbook](../database/Business_Product.md#8-producttextbook) | `(textbook_id)` | S |
| `product.material_import` | [product.material_import](../database/Business_Product.md#9-productmaterial_import) | `(import_id)` | S |
| `product.material_source` | [product.material_source](../database/Business_Product.md#10-productmaterial_source) | `(source_id)` | A |
| `product.material_message` | [product.material_message](../database/Business_Product.md#11-productmaterial_message) | `(message_id)` | A |
| `product.material_turn` | [product.material_turn](../database/Business_Product.md#12-productmaterial_turn) | `(request_ref)` | S |
| `product.material_candidate_batch` | [product.material_candidate_batch](../database/Business_Product.md#13-productmaterial_candidate_batch) | `(batch_id)` | S |
| `product.material_candidate` | [product.material_candidate](../database/Business_Product.md#14-productmaterial_candidate) | `(candidate_id,candidate_revision)` | A |
| `product.material_adoption` | [product.material_adoption](../database/Business_Product.md#16-productmaterial_adoption) | `(decision_id)` | A |
| `product.material_chapter` | [product.material_chapter](../database/Business_Product.md#17-productmaterial_chapter) | `(chapter_id)` | S |
| `product.material_intake_submission` | [product.material_intake_submission](../database/Business_Product.md#18-productmaterial_intake_submission) | `(submission_id)` | S |
| `product.chapter_association` | [product.chapter_association](../database/Business_Product.md#19-productchapter_association) | `(association_id)` | A |
| `product.learning_target` | [product.learning_target](../database/Business_Product.md#21-productlearning_target) | `(target_id)` | S |
| `product.learning_target_version` | [product.learning_target_version](../database/Business_Product.md#22-productlearning_target_version) | `(target_id,revision)` | A |
| `product.application_check` | [product.application_check](../database/Business_Product.md#23-productapplication_check) | `(check_id)` | A |
| `product.course_application` | [product.course_application](../database/Business_Product.md#24-productcourse_application) | `(application_id)` | A |
| `product.target_basis` | [product.target_basis](../database/Business_Product.md#26-producttarget_basis) | `(basis_id)` | A |
| `product.learning_space` | [product.learning_space](../database/Business_Product.md#27-productlearning_space) | `(space_id)` | S |
| `product.space_adoption` | [product.space_adoption](../database/Business_Product.md#28-productspace_adoption) | `(adoption_id)` | A |
| `interaction.input_results` | [interaction.input_results](../database/Business_Interaction.md#2-interactioninput_results) | `(result_id)` | A |
| `interaction.plan_progress` | [interaction.plan_progress](../database/Business_Interaction.md#11-interactionplan_progress) | `(plan_id,plan_revision)` | S |
| `product.usage_conditions` | [product.usage_conditions](../database/Business_Product.md#7-productusage_conditions) | `(student_id)` | S |

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

### 3.2 事件携带记录与条件

方括号表示本事件携带条数；未列类型禁止携带。“无”要求records=[]，事实由类型化payload完整表达。0..n不是任意省略：生产方须把本次改变的全部对象列齐，引用已有且未改变的对象不重复放records。表中业务主键和写入方式取§3；runtime记录为H（仅历史核对），字段字典沿Event_Messages §4.1，不参与P表重建。

| 事件类型 | records完整集合与数量 | 必须满足的条件 |
| --- | --- | --- |
| `DomainIntakeRequested` | `product.material_intake_submission`[1] | 首次提交；status=submitted，身份等于intake_request_id |
| `DomainIntakeReceived` | `domain.artifact`[1]；`domain.intake_submission`[1]；`domain.intake_item`[0..n] | 整批接收。只携带新增待办的正文，已有待办返回原引用。依次投影输入、提交、父题和参考 |
| `DomainIntakeRejected` | `domain.artifact`[1]；`domain.intake_submission`[1] | 整批拒绝。记录固定输入和拒绝依据 |
| `MaterialCandidatesAdopted` | `product.material_adoption`[1]；`product.material_candidate_batch`[1]；`product.material_import`[1]；`product.material_chapter`[0..n] | decision=adopt、batch=adopted；chapter精确覆盖本次目录write_set，无目录变化为0 |
| `MaterialImportDeleted` | `product.material_import`[1] | status=deleted；失效来源列在payload，Domain自行消费并另记事实 |
| `LearningTargetApplied` | 无 | 通知当前采用改变；采用正文由同批LearningSpaceCreated/AdoptionChanged保存，不再复制 |
| `LearningSpaceEntered` | 无 | 只记录进入；不生成第二份空间或采用记录 |
| `ActivityChanged` | `interaction.activities`[0..1]；`interaction.activity_revisions`[1]；`interaction.round_revisions`[0..1]；`interaction.plan_progress`[0..n] | 首次活动含activities；暂停/恢复开放轮时含该轮新修订；取消无开放轮题单时含其进度；有开放轮则由DetectionRoundClosed唯一保存该题单进度 |
| `TaskSupplyRequested` | 无 | 供题要求及精确材料引用在类型化payload；不创建实例 |
| `DomainTaskSupplyCompleted` | `domain.supply_batch`[1] | 批结果含合格实例及未满足项；新实例另由DomainInstanceSaved登记 |
| `AnswerSubmitted` | `interaction.submissions`[1] | 身份等于submission_ref；answer保存完整提交，不用EventPartRef替代必填正文 |
| `TeachingOpportunityClosed` | `interaction.opportunity_closures`[1] | 机会身份等于opportunity_id；不重复创建teaching_opportunities |
| `BeliefEvaluationCompleted` | `evaluation.evidence`[0..n]；`evaluation.belief_revision`[0..n]；`evaluation.mastery_snapshot`[1] | Evidence/修订集合分别等于payload引用集合；合法完成总有新快照；跳过数值更新时修订为0 |
| `GoalEvaluationCompleted` | `evaluation.goal_evaluation`[1] | 结果等于goal_evaluation_ref；是否更新当前索引按current_state_applied，不重新算目标 |
| `LearningTargetSaved` | `product.learning_target`[1]；`product.learning_target_version`[1] | 身份/当前头快照及本次新版本；不重复投影旧版本 |
| `CourseApplied` | `product.course_application`[1]；`product.target_basis`[1] | 同一application的新应用及固定依据；检查结果已由ApplicationChecked登记 |
| `LearningSpaceCreated` | `product.learning_space`[1]；`product.space_adoption`[1] | 首次空间和初始采用；身份分别匹配scope与adoption_ref |
| `LearningSpaceAdoptionChanged` | `product.learning_space`[1]；`product.space_adoption`[1] | 空间身份不变；追加新采用并保存current_adoption_ref |
| `DomainDefinitionSaved` | `domain.object_version`[1] | 本次object_ref的新版本；create/update/soft_delete都不覆盖旧版本 |
| `DomainIntakeSourceInvalidated` | `domain.intake_item`[1] | item_ref的最新有效性快照；不删除已入库定义 |
| `DomainIntakeItemProcessed` | `domain.intake_item`[1..n] | 一项正常处理；确认同时移除子项时携带全部受影响项。领域对象另记版本 |
| `DomainAnalysisInputFixed` | `domain.artifact`[1] | 定义提取或归类的固定输入，含原内容与所选固定定义 |
| `DomainTemplateCandidatePrepared` | `domain.artifact`[1] | candidate_ref；候选不等于正式定义 |
| `DomainInstanceSaved` | `domain.object_version`[1] | kind=task_instance；题面及各参考解法包含在本次固定版本中 |
| `DomainKCTestPathConfirmed` | `domain.artifact`[1]、`domain.kc_test_path`[1] | 固定三版本、任务责任引用及就绪依据一致 |
| `DomainKCTestPathNotReady` | `domain.artifact`[1] | `kind=readiness_check`，保留固定版本和问题；无确认行 |
| `ActivityConfigSaved` | `interaction.blueprint_revisions`[0..1]；`interaction.rule_revisions`[0..1]；`interaction.strategy_revisions`[0..1]；`interaction.binding_revisions`[0..1]；`interaction.resolved_configs`[1] | 按 `config_kind` 携带对应定义。首次蓝图另带空绑定。移除有绑定的节点时另带新版绑定。`config_ref` 指本次解析包 |
| `DetectionPlanPrepared` | `interaction.detection_plans`[0..1]；`interaction.plan_revisions`[1]；`interaction.plan_progress`[1..n] | 首次含plan；每次含新内容修订及prepared进度；替代旧修订时同时含其superseded进度 |
| `TaskUseCreated` | `interaction.task_uses`[1] | 本次task_use_ref；同批轮事件仅引用，不再复制正文 |
| `PresentationRecorded` | `interaction.presentations`[1] | 原回执及未知项；不补写教学或评价结论 |
| `HelpHandled` | `interaction.help_facts`[1] | 主键=(help_id,stage)；handled与provided各自一条，内容与stage一致 |
| `ChatMessageRecorded` | `interaction.messages`[1] | message_ref对应完整parts；活动归属另由MessageAssigned保存 |
| `InteractionInputStopped` | `interaction.input_results`[1] | 取消结果指原input_id；已受理输入不重写；已有回复不重复保存 |
| `DetectionRoundClosed` | `interaction.round_revisions`[1]；`interaction.plan_progress`[1] | round变closed；更新所属固定题单修订的进度，不追加题单内容版本 |
| `AnswerFeedbackPrepared` | `interaction.answer_feedback`[1] | 完整当题反馈及其作答依据；聊天展示另记消息 |
| `ProactiveTaskChanged` | `interaction.proactive_tasks`[0..1]；`interaction.proactive_revisions`[1] | 首次建议含task；后续只追加修订，分别记录运行、等待、失败或完成 |
| `ProactiveTaskResponded` | `interaction.proactive_revisions`[1] | 按accept/defer/reject形成对应状态；不重复写task身份 |
| `ProactiveTaskPrompted` | `interaction.proactive_prompts`[1] | 一次实际提示；message_ref指同批或先前消息，不重复保存消息正文 |
| `ClaimDefinitionChanged` | `evaluation.claim_version`[1] | claim_ref新修订；不自动重评历史 |
| `TrialAccountSaved` | `product.accounts`[1]；`product.usage_conditions`[0..1]；`product.guardian_records`[0..n]；`product.student_guardian_relations`[0..n] | 学生条件本次改变才带usage_conditions；仅携带relation_refs所需的新监护登记/关系，已有记录只引用；管理员条件数为0 |
| `UsageConfirmationRecorded` | `product.usage_confirmations`[1]；`product.usage_conditions`[1]；`product.guardian_records`[0..n]；`product.student_guardian_relations`[0..n] | 确认及接受后的条件必须保存；仅携带本次新增监护登记/关系 |
| `AccountSignedIn` | 无 | 登录事实在payload；会话和凭据属控制数据，不重建登录 |
| `AccountRecovered` | `product.accounts`[0..1]；`product.usage_conditions`[0..1] | 仅当公开账号/使用条件确有改变时携带；单纯重置凭据时records=[] |
| `MaterialReceived` | `product.textbook`[0..1]；`product.material_import`[1]；`product.material_source`[1..n] | 首次含textbook；source集合等于成功source_refs；追加原件不重复旧source。全失败只记失败收据，不伪造接收事件 |
| `MaterialMetadataSaved` | `product.textbook`[1]；`product.material_import`[1] | 元数据及导入修订变化；不重写不可变原件 |
| `MaterialAssistantMessageReceived` | `product.material_message`[1]；`product.material_turn`[1]；`product.material_import`[1] | 用户消息完整body、turn=accepted；导入revision更新；占用列仍属控制数据 |
| `MaterialAssistantTurnFinished` | `product.material_message`[0..1]；`product.material_turn`[1]；`product.material_import`[1] | reply_ref非空恰有对应消息，否则为0；turn.state=outcome；候选另由Prepared登记 |
| `MaterialCandidateDeclined` | `product.material_adoption`[1]；`product.material_candidate_batch`[1]；`product.material_import`[1] | decision=decline、batch=declined；不改当前内容指针 |
| `ChapterAssociationSaved` | `product.chapter_association`[1] | 新增关系修订；取消仍保存方法为空的修订，不删除历史 |
| `MaterialCandidatePrepared` | `product.material_candidate_batch`[1..2]；`product.material_candidate`[0..n]；`product.material_import`[1] | 恰一个新pending批，附明确被替代旧pending批的superseded快照。仅撤下内容或调整目录时可无新候选，已采用批不改 |
| `MaterialIntakeStatusUpdated` | `product.material_intake_submission`[1] | status=received/rejected，与domain_event_id的Domain决定一致 |
| `ApplicationChecked` | `product.application_check`[1] | ready/blocked和完整检查项一致 |
| `AccountSignedOut` | 无 | 只记录失效事实；不从事件重建可用Cookie或登录 |
| `DomainClassificationPrepared` | `domain.artifact`[1] | 本次归类候选及检查结果 |
| `InteractionInputAccepted` | `interaction.inputs`[1] | 原输入首次接受；消息与作答分别由自己的事件保存 |
| `InteractionInputCompleted` | `interaction.input_results`[1] | 一次正式处理结果；不复制已存在的inputs；失败恢复另存新step_key结果 |
| `MessageAssigned` | `interaction.message_assignments`[1] | 消息归属决定；主键message_id不变，允许按新事实更新归属 |
| `DetectionRoundStarted` | `interaction.detection_rounds`[1]；`interaction.round_revisions`[1]；`interaction.plan_progress`[1] | 本次新轮及open修订，题单含确认依据；不新建plan_revisions；task_use另记 |
| `TeachingOpportunityStarted` | `interaction.teaching_opportunities`[1] | 稳定机会首次建立；拆消息、暂停和重试不重复创建 |
| `InteractionDecisionRecorded` | `interaction.decision_records`[1] | allowed/denied/clarify及程序采用依据 |
| `InteractionContextPrepared` | `interaction.context_bundles`[1] | 实际取材及来源；只对获准内部用途可见 |
| `InteractionMemorySaved` | `interaction.memory_revisions`[1] | 本次记忆修订；不覆盖原文 |
| `ProactiveCheckCompleted` | `interaction.proactive_checks`[1] | 建议/无建议/等待均记录；建议实体另记ProactiveTaskChanged |
| `EvaluationInputPrepared` | `evaluation.evaluation_input`[1] | 本次有界取证输入和缺口 |
| `EvaluationInterpretationPrepared` | `evaluation.interpretation`[1] | 解释与资格检查；不等于概率已更新 |
| `GoalCalculationPrepared` | `evaluation.goal_calculation_input`[1] | 固定目标与快照依据 |
| `AIConfigurationPinned` | `ai.execution_configs`[1] | 一次工作配置固定；不含凭据秘密 |
| `AICallChanged` | `ai.ai_calls`[1]；`ai.ai_call_attempts`[0..1] | 调用状态必填；本次开始或结束具体尝试时含该尝试，否则为0；不重复嵌入模型请求正文 |
| `ModelRequestChanged` | `ai.model_requests`[1] | 按请求四元键更新已知请求/响应；pending结果明确为空，不补猜 |
| `ToolActionChanged` | `ai.tool_actions`[1] | 按工具动作及attempt记录授权、参数和结果；业务副作用另由业务事件证明 |
| `AICandidatePrepared` | `ai.ai_candidates`[1] | 结构检查通过的技术候选，不表示业务已采用 |
| `ExecutionStateChanged` | `runtime.executions`[1]；`runtime.execution_attempts`[0..1]；`runtime.step_results`[0..n] | H类：尝试实际变化才带；仅带本次首次保存Step。只保存Step时outcome=progress_saved；不重建执行 |
| `WaitStateChanged` | `runtime.waits`[1]；`runtime.wait_handling`[0..1] | H类：handling创建或变化时带；登记、决议及收尾分别留痕 |
| `DeliveryStateChanged` | `runtime.handoffs`[1]；`runtime.handoff_attempts`[0..1]；`runtime.subscription_receipts`[0..1]；`runtime.delivery_failures`[0..n] | H类：仅带本次改变项；accepted/rejected/ignored承接必带收据，首次故障及处置必带故障快照；不生成留痕事件的投递留痕循环 |
| `FileReceived` | `runtime.file_objects`[1] | H类：文件已完整保存；事件附件读取还须所属业务授权 |
| `ProjectionRebuildFinished` | 无 | 范围、代次、上界及检查结果在完整payload；不以重建结果重建运行控制 |

同一事件内(record_type,业务主键)不得重复；同一commit不允许两个事件重复声明创建同一A记录。同一S记录若确有连续业务变化，以范围序号逐次应用；不得用新事件重复声明相同变化。record_id在原事件内固定，重建不重新编号。

应用收据粒度是(generation,projector_id,event_id)。一次投影器应用必须处理该事件属于自己的全部记录，再共同提交收据；不能处理第一条就写成功。跨事件FK在同批结束时检查，任何记录缺失或失败均回滚整批。新建轮同时引用题目使用时，两者分属RoundStarted和TaskUseCreated，但共用commit_id，不重复投影同一记录。

E01-12已接线DeliveryStateChanged，投递控制快照只用于核对；原子安排与原事实共用commit_id，承接收据与后续安排同事务保存。它不登记业务重建投影，也不能订阅自身。

E01-13接线ExecutionStateChanged：每次一份execution，尝试变化时携带一份attempt；progress_saved携带本次首次保存的一个Step，不复制既有Step。状态、所有者业务收尾与事实同事务；仅维护授权读取，不能据此重建或再次派发。

控制事件的记录只用于核对，不按表名自动恢复控制表；H条目即使同名也不取得P投影权限。ExecutionStateChanged的progress_saved记录新Step检查点；DeliveryStateChanged的accepted/rejected/ignored记录真实承接结论，不把已可靠接住当作业务成功。

### 3.3 业务状态与执行状态

| 数据 | 事实与投影规则 | 恢复规则 |
| --- | --- | --- |
| material_candidate_batch.decision_state | pending由Prepared；adopted由Adopted；declined由Declined；superseded由替代它的Prepared保存旧批快照 | 四种状态均可重建；不重新决定采用或拒绝 |
| material_import.status/revision | active/deleted及所有已登记业务修订由§3.2事件保存 | 不把status解释为运行进度；控制占用和消息计数仍按§3.1例外 |
| material_turn.state/work_state_ref | state只保存accepted及轮结束的completed/needs_input/failed/cancelled；work_state_ref只在这两类事实中保存已交付检查点 | 正在运行/等待及最新技术步骤从Execution/Step组合读取，不写无事件的P列；获准恢复仍保留上次业务结果，直到新结果事实提交 |
| 检测题单与轮 | 题单内容只由PlanPrepared追加；确认、当前轮、取消和结束写plan_progress；轮暂停/恢复经ActivityChanged写round_revisions | 业务状态及确认依据完整重建；不因重建重新开测 |
| AI调用/请求/工具状态 | Changed事件携带每次已接受状态快照，未知结果保持unknown | 能重建已记录的历史状态；重建不继续调用 |

不设“P表中间态可以不记事件”的通用例外。其他业务中间态若影响后续决策，仍须登记事实；锁、租约、占用和技术检查点由控制恢复合同处理。查询响应可以组合两类状态，但不能把运行控制变化冒充新业务结论。

E01-10接线TrialAccountSaved的学生创建和基本资料更新，UsageConfirmationRecorded带confirmation与conditions完整正文。Product的`product.usage_receipt`处理器只在核对请求收据归属后，通过execution_support读取同一correlation_id下的这两类记录；不向浏览器开放任意账号事件。告知全文在事件元数据中固定。当前账号重建包含使用确认及使用条件，按范围顺序保留最新快照；密码恢复、登录等审计只扫描，不恢复凭据或有效会话。五表覆盖和共享监护人边界见§5及Product§2.8。

## 4. 写入与消费

事件登记与投影登记相互独立。业务决定采用哪些事件、生成哪些表及各行关系，允许一对多、多对一和多对多。生产者直接调用、订阅处理与历史重建复用业务自己的确定性生成器。底座只保存和交付事实，不按record_type或投影声明操作业务表。

生产者：事务外完成AI和文件准备 → 按既定锁序检查条件 → 追加完整事件 → 同事务投影本模块业务对象及投影收据 → 保存命令收据、结果和待发安排 → 提交 → 返回/通知。失败整笔回滚；同一命令重试取得原收据，不新增第二件事实。

消费者：收到通知 → 核验正式事件及权限 → 可靠保存承接收据和执行安排 → Ack → 按本模块规则处理。产生新判断时追加自己的结果事件，再同步生成自己的查询投影。结果的因果引用指向所用源事件；不能修改生产者事实。

历史补读和实时接续按[公共运行§2.6](../System_Foundation_Design.md#26-历史补读实时接续与重建)。每范围独立顺序，跨范围依赖按EventPartRef先后解决；前置事件暂未处理则阻塞相关投影，不能跳过后宣称完整。业务订阅默认从启用后开始；新增投影可显式补读历史。

## 5. 重建与验收

M1只提供受控维护重建，不新增管理页面。业务生成器先按§3.2校验事件必需记录及条件，缺一条也不得把该生成器登记为已应用。没有采用的事件可推进扫描位置，但不产生投影完成收据；事件本身也不强制要求有投影。维护窗口停止相关写入，固定各范围上界；在线代次为1，重建使用独立代次，完成时按公共运行§2.6原子接回在线收据和进度；在临时关系中按登记Schema和确定性投影器重建，先从事件的登记正文建立业务身份/版本到来源事件的索引，再按因果依赖与范围序号生成，最后按既定FK顺序整体替换查询数据。临时索引属于本次重建，不增加另一份事实源。保留原业务ID、时间、版本、概率及依据，不产生新业务事件、通知、模型调用、工具副作用或待办。仅追加一次维护结果留痕；失败保留旧查询数据。

事件及附件缺失、Schema不支持、来源闭包不完整、同键异文均中止重建并报告范围；不能猜测补全。运行控制数据不属于替换集合；material_import.active_request_ref保持运行恢复的决定，next_message_seq从已记录消息序号重算，不恢复成历史忙碌状态。其恢复另按Execution/Attempt/Step、Wait及整批备份合同执行。

| 场景 | 必须满足 |
| --- | --- |
| 事件成功、投影失败 | 整个生产事务回滚，不能返回成功 |
| 重复投递/重建 | 同代次、同投影器、同事件只应用一次；新代次可重新生成 |
| 清空测试副本的业务查询表 | 仅凭事件、固定附件和登记解码器恢复相同业务内容；不要求其他业务表充当原文来源 |
| 来源是聊天作答或答题区提交 | 均可由EventPartRef读到实际原文；只接收一次AnswerSubmitted语义 |
| 重建含AI/Evidence/Belief数据 | 使用已经记录的输出和概率；AI调用数、通知数、教学任务数均为0 |
| 补读期间出现实时事件 | 固定上界前无漏项，上界后连续接续；重复通知不重复产生业务效果 |
| 无权读私有材料 | 按§2.2逐层授权；伪造purpose、跨空间及借附件越权均拒绝 |
| 同事件多记录，其中一条失败 | 投影与应用收据共同回滚；重试覆盖全部记录，不丢后续记录 |
| 候选采用/拒绝/替代后重建 | 决定及状态完全一致；不退回pending，不伪造管理员操作 |
| 消息引用自己的业务ID | 空查询库也能凭事件创建原ID；不用投影存在性校验原始事实 |

当前维护入口覆盖账号五表，按指定范围读取全部授权事实，核对隔离副本后，同事务替换正式行、更新在线收据与覆盖位置、追加唯一成功事件。失败回滚本批，修复后另建批次从头重做。维护记录及临时副本不是另一份事实源。详情见[公共运行§2.6](../System_Foundation_Design.md#26-历史补读实时接续与重建)。

上表其余业务验收条件随对应增量实施，不以本轮账号测试宣称已完成。设计采用事件存储与查询投影的分工；参考[Event Sourcing模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)与[重放的外部副作用边界](https://martinfowler.com/eaaDev/EventSourcing.html#ExternalUpdates)。不引入独立事件数据库或新的消息系统。

当前账号接线已补修为`product.account_views.v2`：一份生成器处理账号与使用确认事实，生成账号、监护人、关系、确认和当前条件五表。底座不执行这些表的生成或重建，业务校验与替换范围见[Product§2.8](../Product_Application_Design.md#28-账号业务投影与维护重建)。旧单表结果不被重新解释为五表完成。既有事件Schema、正文和引用不因生成器调整而改写。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 登记完整正文、逐类投影、原文追溯与无副作用重建；待审阅 |
| v0.2 | 2026-11-15 | 补齐事件正文、记录映射、状态或读取边界；容量及保留候选仍待确认。仅文档修订，见MVP决定登记§98。 |
| v0.3 | 2026-11-16 | 同步E01-05接线范围；保留既定字段与记录矩阵 |
| v0.4 | 2026-11-16 | 登记FileReceived、完整DTO附件及E01-06实现范围 |
| v0.5 | 2026-11-16 | 补齐E01-07字段授权、附件读取及错误边界 |
| v0.6 | 2026-11-16 | 补齐首批账号重建、固定维护记录和失败边界 |
| v0.7 | 2026-11-16 | 登记使用确认投影及收据读取；账号资料重建保留原身份 |
| v0.8 | 2026-11-16 | 登记DeliveryStateChanged控制快照及不参与重建的边界 |
| v0.9 | 2026-11-16 | 接线ExecutionStateChanged控制快照，不参与业务投影重建 |
| v0.10 | 2026-11-16 | 明确事件与业务生成器解耦、真实应用收据和重建覆盖边界 |
| v0.11 | 2026-11-22 | 同步按范围重建及失败重做 |
| v0.12 | 2026-11-22 | 明确业务授权与三种内部读取的边界 |
| v0.13 | 2026-11-22 | 登记路径确认和依据不足的事件正文组合 |
| v0.14 | 2026-11-22 | 登记领域受理固定输入、新增待办正文及复用引用 |
| v0.15 | 2026-11-22 | 登记领域分析固定输入和待办处理组合 |
| v0.16 | 2026-11-23 | 登记首次活动蓝图及绑定事实 |
