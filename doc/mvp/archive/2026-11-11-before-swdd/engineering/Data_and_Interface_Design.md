# M1 数据与接口设计

> **版本**：v0.4<br>
> **文档性质**：M1数据与接口工程设计工作稿<br>
> **状态**：归档可读副本；v0.3 原稿及未提交内容保存在原文 ZIP，正文为当时草案<br>
> **上游依据与基线**：输入清单见下文；产品工作基线仍为 `37bd334cf29fd56b1fe5ef6f61cc3c819f01dfb0`；本批修改前提交为 `72b4fd97c65ac0b45a7323601f88c07704382022`，输入核对见[工程入口](README.md)，本批记录见[登记§31](../../../DECISIONS.md#31-m1系统设计首轮实现草案)<br>
> **维护责任**：Codex负责整理与自检；用户审阅范围及关键取舍<br>
> **评审记录**：用户确认按面向实现标准推进；本轮接口、存储及并发方案为待审阅建议，未获实现批准<br>
> **写作规范**：[设计文档规范 v1.1](../../../../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-11<br>
> **修订说明**：v0.3 → v0.4，仅调整归档文档头与相对链接；精确原文见[归档说明](../README.md)。

---

**职责。** 统一维护工程字段、对象标识、存储关系、消息与接口合同及提交一致性要求，供各模块实际交换和保存数据。

**输入。** [PRD v0.23 §3–6](../../../m1/PRD.md)、[内容规格 v0.22](../../../m1/design/Content_and_Model_Reference.md)、[Domain v1.5](../../../../concept-design/DeerMind_Domain_Space_Design_v1.5.md)、[Evaluation v1.9](../../../../concept-design/DeerMind_Evaluation_Space_Design_v1.9.md)；共同设计输入为[业务运行机制](Business_Flow_Design.md)、[运行框架](Agent_Runtime_Design.md)和[上下文设计](Context_and_Memory_Design.md)。

**预期输出与接收者。** 对象及存储关系图、字段与Schema、接口请求响应、事件载荷及错误码、事务与幂等规则；供前后端、工具、任务处理和工程测试使用。

**边界。** 字段和完整接口合同在此唯一维护；不改变Space语义所有权，不新增学习要求实体、KC Claim或算法配置页面，不设计Evolution跨版本迁移和历史重算。

本轮只把“检测提交→评价→返回教学”做成可评审的局部实现合同。标注“待设计”的范围仍为大纲；表名和接口名均属本轮建议，不以落笔代替用户确认。采用[总体架构](Engineering_Design.md)的Python／FastAPI／PostgreSQL、API与worker分进程候选；共同范围及产品规则承接见[工程入口](README.md#31-产品规则到工程章节的对应)。

## 1. 对象身份、归属与存储

完整对象族仍须覆盖下列范围。本轮只为本链运行记录提出表及字段，不将局部表清单当成全部数据库设计。

- Domain对象族：Domain、TaskTemplate、SolutionTemplate、KnowledgeComponent、TaskInstance、SolutionInstance；KC Task／复合Task、子Task与方法依赖，以及解法实例对题目实例和方法模板的引用。
- 教材与课程：教材、章节、章节TT／ST采用及方法×章节适用来源；跨章汇总不能丢失来源限制，不增章节直接关联KC。
- 活动配置与运行：蓝图、节点／条件转移、规则／推荐策略定义及活动级／节点级引用，与学习空间中的活动实例、检测轮、提交和实际帮助分开。
- 评价与任务：Claim、Evidence、Belief分项、目标配置与个人目标状态、主动任务和Agent运行任务；定义与个人状态不混用。
- 教学机会：稳定机会身份、实际展示事件、收束依据、Task／方法／方面责任与资格；暂停、拆消息和同一输出重试沿用身份。它是教学事实的解释与计权依据，不新增管理员管理页面。

### 1.1 本轮身份与值类型

持久对象标识由程序分配UUID；浏览器在首次提交前生成并保存`client_submission_id`，断线重发沿用。LLM不得创建业务身份。`learner_id`由服务端从授权学习空间取得，不接受客户端指定其他学生。

共用`SourceRef`建议为`{kind: string, id: UUID, content_ref: string | null}`：kind由程序登记，id指对象，content_ref指实际采用的不可变内容／快照。不可变事件可仅凭id定位；可能修改的定义或内容在模型输入、事实依据中必须有content_ref。引用只能通过所属模块授权查询解析，不能直接变成数据库表名或任意文件路径。

`claim_ref / solution_ref / target_ref`使用SourceRef表达实际采用依据；完整定义保存合同后续展开，不能仅指向会被编辑覆盖的名称。联合键中的ref比较其规范化身份`kind＋id＋content_ref`，不按显示名称或JSON字段排列比较。`aspect_id`引用Claim已定义方面，本例为`independence / understanding / transfer / retention`；扩展须先有明确的评价定义。

时间使用带时区的时间戳，存储统一UTC。服务端记录有效提交的接受时间；客户端声明时间另列，不直接当作保持间隔依据。概率为有限数值、范围`[0,1]`；存储和达标比较不采用界面四舍五入后的百分数。数值精度与边界fixture须在实现前核对，不自行增加阈值容差。

### 1.2 本链记录与约束

以下为PostgreSQL候选表；schema表示维护责任，不表示独立服务。常规标识为UUID、时间为timestamptz、顺序与修订为bigint；结构载荷须经Pydantic校验再存jsonb，不是任意LLM文本。

| 表及写入方 | 必要字段／含义 | 关键约束 |
| --- | --- | --- |
| `interaction.rounds`，Interaction | `round_id, space_id, activity_id, task_instance_ref, state, revision, started_at, ended_at?, submission_id?` | 状态候选`prepared / answering / submitted / ended_for_help / cancelled`；只有answering接受新提交；题面与采用条件可回查 |
| `interaction.submissions`，Interaction | `submission_id, space_id, round_id, client_submission_id, answer, request_hash, accepted_at, evaluation_id` | `UNIQUE(round_id)`及`UNIQUE(space_id, client_submission_id)`；已接受答案不可覆盖 |
| `evaluation.streams`，Evaluation | `space_id, next_sequence, completed_sequence` | space主键；初始1、0；作答和教学机会共用顺序，分配与推进均短事务加锁 |
| `evaluation.runs`，Evaluation | `evaluation_id, space_id, sequence, source_kind, source_id, processing_status, stages, input_snapshot, result, job_id`及时间 | `UNIQUE(space_id, sequence)`及`UNIQUE(space_id, source_kind, source_id)`；source_kind为`answer_submission / teaching_opportunity` |
| `evaluation.evidence`，Evaluation | `evidence_id, evaluation_id, space_id, performance_source_id, claim_ref, solution_ref, aspect_id, criterion_results, verdict, eligibility, source_spans, conditions, reason` | 同一作答×Claim×方法×方面先合并，至多一个解释记录；verdict为`pass / fail / undetermined`，eligibility为`eligible / ineligible / undetermined` |
| `evaluation.belief_components`，Evaluation | `space_id, learner_id, claim_ref, solution_ref, aspect_id, observed_probability?, current_probability, revision, last_performance_at?, last_update_id?` | 前五字段联合唯一；无合格观测时observed为空，内部current可为先验，不能展示为已测能力 |
| `evaluation.belief_updates`，Evaluation | `update_id`、判断位置、`update_kind, source_id, evidence_id?, opportunity_id?`、前后概率／修订、算法／参数引用及事件引用 | `UNIQUE(space_id, claim_ref, solution_ref, aspect_id, update_kind, source_id)`；kind为`observation / learning_transition`，消息或算法编号不参与去重 |
| `evaluation.goal_results`，Evaluation | `goal_result_id, space_id, target_ref, evaluation_id`、逐方法／方面结果、Belief修订与Evidence、`calculated_at` | 保留本次依据；失败不覆盖此前有效结果，不将处理失败写成学生能力不足 |

`input_snapshot`保存解释所用事件引用、题面、采用定义及帮助／时间依据，解释前固定，正常重试沿用；不向证据解释器提供诱导本次判断的旧Belief。完整AI上下文包见[上下文设计§2](Context_and_Memory_Design.md#2-各类任务的上下文合同)，不在此复制一套记忆机制。

判据记录至少包含判据引用、满足／违背／未知及原始依据；条件包括实际帮助、迁移背景、保持基准／间隔／期间练习或未知。片段必须能定位原始事件，完整多模态定位Schema交§2。方法无法确定时记录跳过原因，不建立虚假的方法Belief。

无法确定方法的解释保存在本次结果的skipped条目，不创建虚假方法的Evidence或Belief。建议索引`runs(space_id, sequence)`、`evidence(space_id, claim_ref, solution_ref, aspect_id)`及`goal_results(space_id, calculated_at)`；查询必须先限定授权空间，索引不代替权限。

### 1.3 通用执行记录

运行状态及执行规则唯一见[运行框架§2–4](Agent_Runtime_Design.md)。这里维护其最小存储字段；job的业务含义仍由JobHandler所属模块决定。

| 表 | 必要字段及约束 |
| --- | --- |
| `runtime.jobs` | `job_id, kind, owner, space_id?, input_ref, dedup_key, state, attempt_no, checkpoint_ref?, result_ref?, available_at, lease_token?, lease_until?, budget_policy_snapshot, error?, created_at, updated_at`；`UNIQUE(kind, dedup_key)`。budget_policy_snapshot保留各step_key初始有限额度；result_ref为带类型的业务结果引用，不塞入完整聊天或Belief |
| `runtime.dependencies` | `job_id, depends_on_job_id, required_result`；前二字段联合唯一。首条链required_result为`final`，继续任务等待评价完整协议完成（包括合法skip）；完整阶段依赖待逐动作确认，不先假设全部动作都能用部分结果恢复 |
| `runtime.steps` | `step_id, job_id, step_key, attempt_no, operation_id, kind, status, input_ref?, output_ref?, started_at, ended_at?, usage?, details?, error?`；operation_id由程序维护且在job内唯一。usage记录本次实际占用的模型调用数、工具调用数及主动执行时长，按job_id＋step_key累计；details按kind校验，不接受任意JSON。重新领取不清零已用预算 |

预算耗尽后的受控运维追加使用现有runtime.steps的`kind=budget_grant`追加记录，不新建管理页面。details至少保存`operator_id, reason, approved_at, limits_before, limits_after`，范围由同一job_id＋step_key确定；限额包含模型／工具调用数和主动执行时长，增量必须有限且非负。经权限校验的运维操作锁定该job，核对前值并保存记录；重复operation_id不重复追加。已使用额度不改写，剩余额度由初始快照＋已授权增量−累计usage计算。LLM和普通Agent工具无写入或授权权限，禁止通过换job_id／step_key重置额度。具体处置见[运行框架§3.3](Agent_Runtime_Design.md#33-预算耗尽后的受控恢复)。

API查询可按已成功阶段先提供合法反馈，这不创建第二条继续任务。继续任务的幂等键以原活动／本次评价／继续步骤为依据，不采用通知编号；其精确键随完整活动步骤合同进一步固定。runtime表不代替业务去重约束。

## 2. 教材内容、原件与多模态数据

待设计：定义KC／题目／解法的结构化内容、公式图表、文件引用、解析候选和出处；区分教学辅助内容与原题。

预期产出：内容Schema、文件接口及合法／缺失样例；引用已有有限提取试验，不冒充无损提取已验证。

## 3. 事件与执行记录

### 3.1 全局事件与本链载荷

建议`event_log.events`保存唯一的追加式事件记录。生产者负责事件含义，共用模块提供追加及授权查询；各Space自己的当前状态仍由其维护。技术工具调用、检查点和Token用量留在运行记录，不全部复制进空间事件。

| 信封字段 | 类型与约束 |
| --- | --- |
| `event_id, producer, event_type` | UUID及已授权生产者／登记类型；LLM不自由决定生产者 |
| `space_id?, subject_ref` | 学习事件必填space；全局教材等事件可无个人space，但有明确业务主体及授权范围 |
| `occurred_at?, recorded_at, recorded_sequence` | 实际发生时间及来源、数据库记录时间、记录序号；未知发生时间明确保留，记录顺序不冒充现实因果顺序 |
| `correlation_id, causation_event_id?` | 本次业务操作和直接起因；多条依据另由payload的source_event_ids保留 |
| `payload_schema, payload` | 已校验的载荷类型与当时内容／结果，不仅引用会被覆盖的当前值 |

| 候选事件名 | 生产者及载荷 |
| --- | --- |
| `interaction.answer_submitted` | Interaction：提交、轮、题面、接受时间、答案引用及实际展示／帮助事实 |
| `interaction.round_ended` | Interaction：轮、结束原因、提交或求助请求；未做题不等于答错 |
| `evaluation.evidence_formed` | Evaluation：Evidence、方法／方面／判据、资格及理由、原始事件和片段 |
| `evaluation.belief_updated` | Evaluation：分项、前后值和修订、Evidence或机会、更新性质及算法／参数依据 |
| `evaluation.goal_updated` | Evaluation：目标采用依据、逐项结果、Belief修订与Evidence、变化原因 |

事件名待与其他流程统一确认。无资格只记录真实处理结果，不伪造概率更新。应用账号和接口不得UPDATE／DELETE事件表；后三类处理事件不得重新成为学生表现证据。备份恢复权限与产品改写接口分开。

### 3.2 后续事件合同

教学机会仍须有稳定机会标识、实际展示、收束理由、资格及限制；主动任务须保留触发依据、提醒／响应、活动关联及结果等待。完整事件清单随对应业务流程展开，本轮不宣称全部完成。

用时记录承接发生／记录时间、计时区间、空间与学生归属、自动测量／用户补记／未知来源、学生等待与纯后台运算的区分；未知不能记零。业务累计和空闲口径引用业务运行§7，重叠区间不重复累计；记录更正如需补充，追加来源，不改写原事件。

后续补完整载荷Schema与合法／未知／失败样例；模型输出不能冒充已执行效果。

## 4. 模块、Agent与工具接口

### 4.1 模块操作候选

本表是Python应用服务操作，不表示独立HTTP服务。各模块只通过公开操作协作，不直接读取其他模块ORM实体或写其表。

| 操作及所属模块 | 输入 | 输出／写入 |
| --- | --- | --- |
| `Interaction.submit_answer` | 授权身份、space／round、客户端提交标识、答案 | 提交收据及evaluation_id，按§6 T1保存 |
| `Evaluation.register_request` | space、source_kind／source_id、采用依据 | evaluation_id及顺序；参与T1，同源返回已有请求 |
| `Evaluation.evaluate_submission` | evaluation_id、当前RuntimeJob租约 | 证据解释、资格、计算与提交；job结果指向Evaluation结果，LLM不写概率 |
| `Evaluation.get_result` | 授权身份、space、evaluation_id | 本次处理状态、分层结果与依据；旧结果不冒充本次成功 |
| `Interaction.continue_after_evaluation` | 依赖结果引用、预期活动及运行位置 | 核对当前活动后继续或结束本次恢复，不重新启动过时活动 |

业务层向Evaluation提供只读目标输入：目标采用依据、Claim、方法任选／分别达标、方面与范围条件。全局阈值不由请求传入；教材可问范围与目标必评范围不能合成聊天白名单。

### 4.2 解释与数值函数

解释器返回候选判据判断、实际方法／方面、原始片段、资格理由、条件与限制。程序检查引用、帮助、时间及重复来源；Schema合法不能证明语义正确，冲突保留未决。子Task按真实子过程与自身Claim／方法归因，不传播父任务成功。

| 数值函数候选 | 输入与返回 |
| --- | --- |
| `validate_parameters(params)` | 服务端加载`M1-BELIEF-PARAM-01`；校验p0／S／G／L范围及`1-S>G`，不接受客户端参数覆盖 |
| `observe_probability(prior, passed, params)` | 已通过资格检查的current_probability、布尔判据结果；返回观测概率。unknown／ineligible不转false调用 |
| `apply_learning_transition(prior, aspect_id, qualified_opportunity, params)` | 已核对的相关机会；返回计算概率及有效L。迁移／保持L=0；不更新observed_probability或实际表现时间 |
| `derive_goal(target_input, components, applicable_evidence)` | 目标条件、有效观测概率与证据基础；返回逐方法／方面`achieved / needs_strengthening / pending_confirmation`及依据；无资格证据先待确认，合格项按未舍入概率与0.90比较 |

函数执行[内容§4.18–4.20](../../../m1/design/Content_and_Model_Reference.md#418-概率计算学习转移与共享参数)既定公式，不重复维护算法。它们不分配身份、不调用LLM、不写库，也不承担去重；外层负责资格、顺序和持久提交。学习预测不能独自达标。完整类型定义、精度和边界fixture在数值模块接收时补齐。

## 5. 前后端与流式交互

### 5.1 提交答案

候选：`POST /api/v1/learning-spaces/{space_id}/rounds/{round_id}/submissions`。需登录且有该空间学生提交权限；管理员可查询不等于可代学生作答。请求示例中的UUID为合成数据。

```json
{
  "client_submission_id": "7d2e570c-c744-4892-af21-87285013cf4c",
  "answer": {
    "text": "120×1/4=30，120+30=150。以120为参照，还要加回原量。",
    "attachment_ids": []
  }
}
```

text为字符串、attachment_ids为已上传且有权引用的文件UUID数组，至少一项有内容。文件类型／大小和富文本完整Schema待文件设计确认，不以此样例宣称多模态协议已完成。

首个有效提交返回`202 Accepted`；同一客户端标识及相同规范化请求内容重发返回`200`、原submission_id／evaluation_id及当前处理状态，不新建提交或评价。

request_hash建议为SHA-256，输入包含`operation=submit_answer`、服务端解析后的space_id／round_id及完整合法请求体；递归按JSON属性名排序、使用UTF-8和固定无额外空白的分隔符序列化，禁止非有限数值及未知字段。答案字符串不trim、不作Unicode或文字改写；附件数组保留顺序。查到已有客户端标识后必须比较完整hash：跨轮复用同一标识即使答案相同也返回409，不能误返回另一轮收据。

```json
{
  "submission_id": "f8aba48e-2f02-4492-bd7a-6c26f8f7c719",
  "evaluation_id": "8cfac50e-2cba-4cb0-8f0f-22b0afc707b0",
  "submission_status": "accepted",
  "evaluation_status": "pending"
}
```

收据只确认事实保存，不附解法。原题单尚有后题时，即使评价已完成也不能提前泄露提示。

| HTTP／错误码 | 行为 |
| --- | --- |
| `401 AUTH_REQUIRED`、`403 SPACE_ACCESS_DENIED` | 不写提交，不泄露未授权空间的题面或评价 |
| `404 ROUND_NOT_FOUND` | 已授权空间中不存在该轮 |
| `409 SUBMISSION_ID_REUSED` | 同一客户端标识对应不同操作／轮／内容，不覆盖原提交或返回另一轮收据 |
| `409 ROUND_CLOSED` | 已提交／求助结束／取消，不能以新标识再作答；相同请求先按幂等路径返回原收据 |
| `422 INVALID_ANSWER` | 空内容、结构或文件引用非法，返回字段错误 |
| `503 COMMIT_UNAVAILABLE` | 事务未成功；保留原标识重试，不先显示提交成功 |

### 5.2 读取评价结果

候选：`GET /api/v1/learning-spaces/{space_id}/evaluations/{evaluation_id}`。顶层`processing_status=pending / processing / succeeded / failed`；`feedback / evidence / belief / goal`各阶段为`pending / succeeded / failed`。合法未知／无资格可以处理成功，使用`skipped[]`说明原因，不将学生待确认状态当作技术失败。

响应至少有evaluation_id、submission_id、activity_id、round_id、顶层及阶段状态、允许展示的当题反馈、Evidence／Belief修订／目标结果引用、skipped、error和updated_at。API由Interaction检查学生反馈展示时机；Evaluation内部结果已保存也不能通过GET绕过后题保护。管理员追溯需独立授权。

反馈存于`evaluation.runs.result.feedback`，结构至少为`checked_scope: answer_result | task_performance`、`judgement: correct | incorrect | undetermined`、`reason`、`reference_refs`、`source_spans`和`limitations`。只有最终答案时最多核对answer_result，不能用correct冒充完整方法／解释已通过。候选由可靠参考／检查工具及必要的模型解释产生，Evaluation校验引用、依据和内容后才将feedback阶段置为succeeded；工具输出或模型候选不能直接作为已核对结果。未能可靠判断可以持久化undetermined及原因并成功结束此阶段，技术调用或保存失败则为failed。反馈是否可展示由Interaction另查当前题单和活动，不能将“已核对”当成“已展示”。系统反馈不能回灌为学生Evidence，解释仍引用原始表现。

当题反馈不依赖Evidence非空：只答150且可靠参考可确认时，反馈可为correct，但方法归因跳过；不能据此更新A或B。反馈成功、Evidence失败时仍保留该反馈，允许时可先显示。首条链的final要求各阶段完成；反馈技术失败也保留队头等待原请求重试，不因无法评价而强行造反馈成功。反馈合法未决不阻塞final。

例如两步算式正确但无解释：独立更新成功；理解跳过`NO_EXPLANATION`、迁移跳过`NO_QUALIFIED_TRANSFER`、保持跳过`RETENTION_NOT_DUE`，处理仍为succeeded。解释服务故障另返回`EVIDENCE_INTERPRETATION_FAILED`，不生成学生反证。阶段成功而后续失败时，已成功结果仍可按展示规则读取。

本链可先用轮询实现读取。完整聊天流式消息、重连游标、SSE与取消协议待后续确认；轮询或刷新不能重新创建评价。

## 6. 事务、幂等与并发提交

### 6.1 提交边界与唯一触发

各模块通过同一应用事务上下文调用各自repository，完成必要关联写入；不因此授予任意跨模块写表权限。任何事务都不得跨越LLM请求或等待学生输入。

| 提交点 | 同时保存的内容 | 故障处理 |
| --- | --- | --- |
| T1 接受作答 | 锁round并检查；保存submission及原始事件；结束该轮；锁streams分配顺序；登记Evaluation请求、唯一RuntimeJob及所需后续依赖 | 全成或全不成。响应丢失返回原收据；worker领取已保存job，不再由事件订阅另建一次评价 |
| T2a 当题反馈 | 保存已核对反馈、参考及原文依据、feedback阶段结果；此时尚非实际展示 | 未保存候选不算成功；反馈合法未决可完成，技术失败待原请求重试 |
| T2b 解释与资格 | 保存Evidence、合法未决／跳过、形成事件及evidence阶段结果；不要求Evidence非空 | 已成功阶段复用固定结果；Evidence失败不撤销T2a反馈，也不重新解释已入库Evidence |
| T3 数值更新 | 核对队头和租约；读取分项；插入唯一belief_updates、更新分项及其事件、保存阶段结果 | 同一事务完成或回滚；重试查阶段与唯一键，不再次套公式 |
| T4 目标与完成 | 保存目标结果及事件、最终结果；推进completed_sequence；通过执行模块保存job成功和result_ref、使依赖可领取 | 通知丢失仍可查已保存结果；目标失败不回滚T2／T3，队头保留并只重试未完成阶段 |

T4复核目标采用条件；若已变化，取得当前条件重新对照，不重复Evidence或Belief，也不让旧目标结果覆盖新目标。实际表现和活动采用依据仍保留；跨定义迁移及历史重算不在本轮范围。

T2a／T2b至T4的后台提交先锁当前job，检查`state=running`、lease_token匹配且`lease_until`大于数据库当前时间，再按streams→evaluation.run→稳定分项键顺序取锁；等待锁后用数据库实际当前时间检查，不使用可能过时的客户端或事务开始时间。T1还没有可见job，只锁round→streams后插入关联记录。任一租约条件不满足时，迟到worker不得写业务结果或成功检查点。阶段成功标记和对应结果同事务保存。目标采用与目标结果的并发检查须在同一提交边界内完成，其与目标应用的具体锁约定随该管理流程补齐。RuntimeJob与恢复详情见[运行框架](Agent_Runtime_Design.md)。

### 6.2 顺序、去重与竞争

建议M1同一空间评价全串行：仅`sequence=completed_sequence+1`的请求可执行。注册时锁streams行分配next_sequence并加一，作答与已收束教学机会共用序号；不同空间、教材助手以及不依赖当前评价的聊天可并行。

教学机会实际收束时先登记其请求，后续资格解释在队头执行；不能等LLM判定合格后才入队，否则后发生作答可能先更新概率。这里排序依据是服务端已接受的业务操作与关联因果，不按任意客户端时钟重排。教学机会的完整注册接口仍须随其业务流程细化。

前序技术失败保留队头，不推进completed_sequence。有界自动重试或工程运维显式重试沿用evaluation_id、job_id及已成功阶段；无归因／资格未知等合法结果可完成并推进。取消执行任务也不能直接跨过尚未完成的评价。

**待用户确认的取舍：** 一个评价故障会阻塞该空间后续数值更新及其依赖动作。此方案避免L转移和作答乱序，不建设失败后插队重算；后续按实际需要优化。错误评价纠正仍不属于技术重试。

- 同作答×Claim×实际方法×方面至多一次观测；多条判据与递归路径先合并，不按输出条数计权。
- 教学转移键为学习空间＋Claim采用依据＋实际方法＋方面＋稳定机会身份。更换消息、算法编号或恢复任务不再次加L，子Task必须有自己的实际依据。
- 提交与实质求助竞争时锁同一round，并核对revision，只允许一个合法结束转移。迟到求助不能改写已接受提交；求助请求不等于已展示帮助。
- T3按稳定分项键顺序锁定记录，保留唯一约束和租约检查，防止过期worker或重试绕过顺序。
- 主动任务的触发依据键随业务§7展开；不能用新job_id冒充新提醒理由。

## 7. 权限、隔离与数据恢复

本链权限：学生只提交自己的活动轮；Evaluation仅取得本次授权空间与采用定义；Interaction读取结果或请求处理，不能直接改概率；管理员只读个人评价依据。程序根据身份及任务来源授予工具权限，LLM输出不构成授权。每个repository查询包含授权范围，共享数据库不等于跨Space任意写入。

完整权限矩阵、凭据及备份恢复仍待展开。管理员不手改个人概率及达标结果；教材助手不能越过采用／入库流程直接修改已入库定义和章节采用。已知不可靠结论不继续用于受影响自动决策，原记录保留；未映射历史作答不追补，错误评价替代和历史重算后置，不与正常处理失败后的幂等重试混淆。

预期产出：权限矩阵及数据恢复要求；运维部署由[总体架构](Engineering_Design.md)汇总，既定只追加事件不得改写。

## 8. 完成条件与审阅

以下是完整设计达到可接收状态的要求。本轮只交付局部候选合同，均不勾选；示例、字段和接口没有实现或真实验证结论。

- [ ] 对象标识、关联、字段含义、可选值和读写归属可检查，与现行模型及主流程一致。
- [ ] 主要接口具有正常、未知和失败示例，流式展示和后台处理可以按同一来源追溯。
- [ ] 重复请求、并发评价、结果通知和备份恢复有明确数据约束；不因Schema设计重新引入后置范围。
- [ ] 所需图表和示例真实存在、与正文一致；技术验证标明已验证或待验证及其影响，不用设计描述冒充结果。
- [ ] 上下游引用、权限和M1范围核对完成；作者自检、用户审阅和允许进入对应实现的范围分别记录。

审阅分工：Codex先自检，用户审阅技术方案及细节；本轮重点为接口命名、关联提交、同空间评价串行及故障队头阻塞。记录见[DECISIONS §31](../../../DECISIONS.md#31-m1系统设计首轮实现草案)，后续验证见[实施计划](Delivery_Plan.md)和[验证入口](../../../m1/validation/README.md)。管理、文件、完整聊天协议及恢复合同尚未完成。

