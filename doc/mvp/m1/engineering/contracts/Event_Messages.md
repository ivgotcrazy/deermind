# M1 事件与消息载荷

> **版本**：v0.13<br>
> **状态**：设计合同；实际接线范围和进度见实施计划，不表示本册全部已实现<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-22<br>
> **修订说明**：v0.12 → v0.13，对齐固定分析输入、归类、正式入库和章节关联的事件正文<br>

本分册是事件信封、类型化动作字段与通知结构的唯一字段定义；完整事实正文及投影登记见[事件正文合同](Event_Facts.md)。事件何时保存、消费者怎样处理仍归业务模块；主流程事件索引保留在[工程README§6](../README.md#6-跨模块事件目录)。所有事件只追加；重试沿原事件身份。

E01-05接线初始账号事实、生产者投影及收据；E01-06新增FileReceived及完整DTO附件，事件引用不代替正文校验；E01-08新增维护结果ProjectionRebuildFinished（records为空，仅一次完成或明确失败留痕）；E01-12新增DeliveryStateChanged及既定DeliveryNotice传输副本；E01-13新增ExecutionStateChanged；其余类型按所属增量实施。既有事实保存见[E01-05](../../../../../src/m1/deploy/environments/local-wsl/E01-05-facts.md)，文件与附件见[E01-06](../../../../../src/m1/deploy/environments/local-wsl/E01-06-files.md)，进度以[实施计划](../Delivery_Plan.md)为准。

## 1. 正式事件信封 v2

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `event_id` | ID | 是 | 程序分配；同事实重投不改 |
| `commit_id` | ID | 是 | 同一数据库提交的事件共用身份；事务重试沿用，不等于请求或Execution身份 |
| `event_type` | 登记事件名 | 是 | 下文精确名称，大小写敏感 |
| `schema_version` | int | 是；设计升版及已接线版本见§3开头 | 该类型payload版本，不是Domain内容版本 |
| `producer` | product/domain/interaction/evaluation等已登记模块 | 是 | 由受权保存者确定 |
| `scope_kind` | string | 是 | 登记资源种类，见各事件归属 |
| `scope_id` | ID | 是 | 对应范围身份；空间事件必须是真实学习空间 |
| `owner_ref` | Ref | 是 | 事实描述的对象身份；不是原文存储位置，不要求先有业务行 |
| `subject_refs` | Ref[] | 是 | 便于按活动、作答、题目等过滤 |
| `actor_ref` | Ref或null | 是 | 已核验用户/服务身份，不是客户端角色 |
| `source_execution_ref` | Ref或null | 是 | 普通短提交允许null |
| `source_request_id` | RequestId或null | 是 | 用户/管理员请求来源 |
| `causation_event_id` | ID或null | 是 | 直接前因；与source_request_id至少一项有值 |
| `correlation_id` | ID | 是 | 链路查询，不作去重键 |
| `scope_event_seq` | int | 是 | 每个(scope_kind,scope_id)内正整数，所有范围必填 |
| `occurred_at` | Timestamp或null | 是 | 已核实业务发生时点；未知null |
| `recorded_at` | Timestamp | 是 | 服务端追加时间，不在重试覆盖 |
| `time_basis` | server_recorded/referenced_fact/unknown | 是 | 可信时间来源 |
| `time_source_ref` | Ref或null | 是 | referenced_fact必须有引用；unknown不伪造 |
| `client_reported_at` | Timestamp或null | 否；null | 只作参考 |
| `payload` | 按event_type的对象 | 是 | 下文逐类型定义；禁止任意脚本或未登记字段 |

同字段若为跨模块交接方便在payload中出现，必须与信封一致，否则拒绝；本稿原则上不重复scope_id。scope_kind的本批代码登记为learning_space、material_import、domain、learning_target、course_application、activity_config；账号内部事实另用account；AI及工作用execution，投递用event_delivery，文件用file，维护用maintenance。它们是待审的传输名称，不改变数据所有者。

发生时间未知时time_basis=unknown且occurred_at=null；用引用时校验time_source_ref；服务端保存动作取服务端确认时点。学习评价顺序按scope_event_seq，不能用不同机器的到达时间排序。详见[公共运行§2.2—2.3](../System_Foundation_Design.md#22-空间事件顺序与有界读取)。

## 2. NATS 交接与订阅

正式事件保存在数据库；JetStream只保存投递副本。subject沿E01-12已确认配置`dm.<deployment_key>.event.<event_type>`，不带学生姓名、题面或消息正文。本机采用local-wsl隔离命名，durable取程序登记的subscriber_id；不由请求方临时命名。

| DeliveryNotice字段 | 类型/必填 | 含义 |
| --- | --- | --- |
| delivery_id | ID/是 | 本次可靠交接身份；技术重发沿用，获准重新投递另记交接 |
| event_id | ID/是 | 正式事件身份；重新投递仍不变 |
| event_type | 登记名/是 | 必须和subject及正式记录一致 |
| schema_version | int/是 | 对应正式事件payload版本 |
| producer | 登记模块/是 | 正式生产者 |
| scope_kind、scope_id | string、ID/是 | 帮助授权定位；不能信任它们代替查正式事件 |

消费者先按event_id向底座核验正式记录，再解析payload；伪造/不支持的消息留下接入失败，不调用业务处理器。事件及执行安排可靠保存后Ack，不等待AI结束；最终业务失败归原模块处理，不靠MQ重投整条业务。subscriber_id+event_id防重复承接；NATS投递确认不是业务成功。

订阅按start_policy=new_only或history_then_live登记；后者只允许确定性查询投影，沿公共运行§2.6补读，不重做历史评价。订阅项完整字段为subscriber_id:string、event_types:string[]、handler_ref:string、handler_revision:string、scope_policy:登记授权策略引用、acceptor_ref:string、on_success:string、on_failure:string、start_policy:string。投影订阅还固定projector_id及projector_revision；在线代次为1，重建代次按公共运行§2.6。handler只能来自程序装配登记，不接收事件里的函数名。超时属于消费方Wait，使用单独on_timeout登记，不要求生产者在指定时间发布。

消息是否订阅只按下文“消费方式”。仅留痕事件没有业务订阅者不算失败；浏览器刷新由底座按已授权watch转换为changed，不能直接转发完整信封。成功发布仍以正式数据库事实为准。

## 3. 逐类型业务载荷

§3、§4原47类事件采用设计版本2，新增records及各范围序号；已接线的TrialAccountSaved、AccountSignedIn保留既有版本1，不改写事实或虚构迁移。本轮首次接线的UsageConfirmationRecorded、AccountRecovered采用版本2，正文DTO仍为版本1；事件版本与正文版本分别校验。§4.1新类型为1。每类payload均必须有records:FactRecord[]，其字段及逐类型正文约束见[正文合同§2—3](Event_Facts.md#2-正文结构)。以下字段表列其余字段，不重复records。每个事件允许和必须携带的正文、数量、条件唯一维护在[正文§3.2](Event_Facts.md#32-事件携带记录与条件)；payload引用不等于需要重复携带该对象正文。Ref可标识本事件新建的业务对象或既有对象，不能据此证明投影行已存在；原文来源使用EventPartRef。对象ID须与records中的主键及版本相符，重建保留原ID。确切形状沿[总册§3](../API_and_Message_Design.md#3-共用类型与字段规则)。列表允许空时必须表示确认无项，未知以缺口/限制表达。时间、账号及源请求由信封保留，不因正文省略而丢失追溯。

<a id="domainintakerequested"></a>
### 3.1 `DomainIntakeRequested`

生产方：`product`；归属：`material_import`。产生条件：管理员提交已采用内容并共同保存请求。

消费方式：domain.receive_intake。

实施版本为1，订阅者为 `domain_intake`。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `intake_request_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `candidate_refs` | CandidateRef[] | 是；非空 | 固定所选已采用内容；类别/父题从提交读取 |
| `sources` | IntakeSource[] | 是；与candidate_refs逐一对应 | 每项含candidate_ref、指向完整候选记录的candidate_fact（EventPartRef）、adoption_ref |
| `parent_bindings` | ParentBinding[] | 是；无参考时为空 | 固定每个参考项的父题。parent_candidate_ref、parent_item_ref、task_instance_ref恰选其一 |

本事件固定所提交内容的EventPartRef及来源闭包，不依赖候选业务行取原文；只提交题目允许，单独提交解法须有可定位父题。

<a id="domainintakereceived"></a>
### 3.2 `DomainIntakeReceived`

生产方：`domain`；归属：`material_import`。产生条件：整批接收或业务拒绝与结果共同保存。

消费方式：Product读取intake_receipt；等待桥按已登记条件提示。

实施版本为1，订阅者为 `product_intake_result`。收到后由Product登记本模块状态。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `trigger_event_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `domain_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `intake_request_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `receipt_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `result_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `outcome` | 常量received | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `items` | Ref[] | 是 | 已受理待办的有序引用，包含复用项 |
| `issues` | Issue[] | 是；可空数组 | 受理问题 |

只有可信Product提交才有业务决定；技术失败不发拒绝。事件不表示定义/题目已经入库。

<a id="domainintakerejected"></a>
### 3.3 `DomainIntakeRejected`

生产方：`domain`；归属：`material_import`。产生条件：整批接收或业务拒绝与结果共同保存。

消费方式：Product读取intake_receipt；等待桥按已登记条件提示。

实施版本为1，订阅者为 `product_intake_result`。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `trigger_event_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `domain_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `intake_request_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `receipt_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `result_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `outcome` | 常量rejected | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `items` | Ref[] | 是；空数组 | 无受理待办 |
| `issues` | Issue[] | 是；非空 | 确定的业务拒绝依据 |

只有可信Product提交才有业务决定；技术失败不发拒绝。事件不表示定义/题目已经入库。

<a id="materialcandidatesadopted"></a>
### 3.4 `MaterialCandidatesAdopted`

生产方：`product`；归属：`material_import`。产生条件：管理员采用修正内容。

消费方式：domain.receive_intake来源失效分支。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adopted_refs` | CandidateRef[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `replaced_refs` | CandidateRef[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `affected_submission_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

Domain只处理仍pending的受影响待办；已入库定义保持。

<a id="materialimportdeleted"></a>
### 3.5 `MaterialImportDeleted`

生产方：`product`；归属：`material_import`。产生条件：未完成导入业务删除成功。

消费方式：domain.receive_intake来源失效分支。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `deletion_receipt_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `invalidated_source_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `affected_submission_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不授权物理删文件，不撤销既有领域对象。

<a id="learningtargetapplied"></a>
### 3.6 `LearningTargetApplied`

生产方：`product`；归属：`learning_space`。产生条件：空间首次采用或实际目标依据改变。

消费方式：evaluation.reassess_target。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `application_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_target_basis_ref` | Ref或null | 是 | 首次为null |
| `applied_at` | Timestamp | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `cause_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

只重算目标对照，不重算Belief；仅改教材说明不发本事件。

<a id="learningspaceentered"></a>
### 3.7 `LearningSpaceEntered`

生产方：`product`；归属：`learning_space`。产生条件：接受学生实际进入请求。

消费方式：interaction.check_proactive_task。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `application_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

同请求一次；查询/重连不产生；不自动开始检测。

<a id="activitychanged"></a>
### 3.8 `ActivityChanged`

生产方：`interaction`；归属：`learning_space`。产生条件：活动与路径修订共同保存。

消费方式：Interaction普通接入先判定固定修订是否结束，再决定check_proactive_task；其他只追溯。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `revision_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `parent_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `node_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `reason` | string | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_input_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_trigger_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

来源输入/事实至少一项；只有结束条件命中才安排主动检查，不能所有节点迁移都调用AI。

<a id="tasksupplyrequested"></a>
### 3.9 `TaskSupplyRequested`

生产方：`interaction`；归属：`learning_space`。产生条件：形成固定的例题/练习/检测供题要求。

消费方式：domain.supply_task。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `supply_input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `domain_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `purpose` | example/practice/assessment | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `task_ref` | ObjectRef(task) | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `allowed_method_refs` | ObjectRef(solution)[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `assessment_constraints_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `method_source_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `exposure_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `count` | int | 是；正数 | 需提供的题量 |

复杂条件通过固定supply_input_ref读取Domain§5.2输入；exposure_refs=[]只在确认无经历时使用，未知须带输入缺口。

<a id="domaintasksupplycompleted"></a>
### 3.10 `DomainTaskSupplyCompleted`

生产方：`domain`；归属：`learning_space`。产生条件：供题批次及合格新题保存完成。

消费方式：Interaction读取task_supply及批次；仅匹配等待才接续。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `trigger_event_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `supply_batch_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `result_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

空批是合法业务结果，技术失败不是空批；取回后仍需条件复核，检测先确认题单。

<a id="answersubmitted"></a>
### 3.11 `AnswerSubmitted`

生产方：`interaction`；归属：`learning_space`。产生条件：接受实际作答并固定条件。

消费方式：evaluation.evaluate_submission，按空间顺序扫描。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `submission_ref` | Ref | 是 | 本事件submissions记录的预分配身份；不要求查询行先存在 |
| `task_use_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `round_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `plan_ref` | PlanRef或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `help_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

练习可无轮/题单；原文在Interaction，答案全文在事件正文或固定事件附件中。一次已接受提交只产生一次触发。

<a id="teachingopportunityclosed"></a>
### 3.12 `TeachingOpportunityClosed`

生产方：`interaction`；归属：`learning_space`。产生条件：服务端教学段收束。

消费方式：evaluation.apply_learning_opportunity，按空间顺序扫描。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `opportunity_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `closure_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `provided_part_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `purpose` | string | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `close_reason` | completed/interrupted/cancelled/unable_to_continue | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

只含已正式提供内容，不靠浏览器回执；拆消息/暂停/重试不另增学习机会。

<a id="beliefevaluationcompleted"></a>
### 3.13 `BeliefEvaluationCompleted`

生产方：`evaluation`；归属：`learning_space`。产生条件：本批解释及更新/不更新结果共同提交。

消费方式：Interaction按授权读取、匹配等待或核对主动任务；其他只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `trigger_event_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `evidence_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `belief_revision_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `snapshot_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `result_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `reason_codes` | string[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

零数值变化也可合法完成并发布覆盖；事件本身不携概率，不表示目标已达标。

<a id="goalevaluationcompleted"></a>
### 3.14 `GoalEvaluationCompleted`

生产方：`evaluation`；归属：`learning_space`。产生条件：目标结果及是否成为当前结果共同保存。

消费方式：Interaction读取当前依据后接续/核对建议；Product查询展示。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `trigger_event_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `goal_evaluation_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `snapshot_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `result_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_current_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `current_state_applied` | boolean | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `not_applied_reason` | string或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

旧目标/旧快照结果也留痕；读取者不能看到事件名就宣布达标，同源两类评价通知不重复建建议。

<a id="learningtargetsaved"></a>
### 3.15 `LearningTargetSaved`

生产方：`product`；归属：`learning_target`。产生条件：保存目标定义修订。

消费方式：只查询，不重评。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `target_ref` | TargetRef | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_target_ref` | TargetRef或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `textbook_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

定义保存不等于应用。

<a id="courseapplied"></a>
### 3.16 `CourseApplied`

生产方：`product`；归属：`course_application`。产生条件：确认教材目标组合应用。

消费方式：只查询，不替代个人目标采用触发。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `application_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_application_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `check_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `textbook_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_ref` | TargetRef | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

每个受影响空间另保留自己的采用事实。

<a id="learningspacecreated"></a>
### 3.17 `LearningSpaceCreated`

生产方：`product`；归属：`learning_space`。产生条件：新建本人空间及初次采用。

消费方式：只查询；同次提交LearningTargetApplied触发目标对照。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `student_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `textbook_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

重复选同组合复用原空间，不再发创建事件。

<a id="learningspaceadoptionchanged"></a>
### 3.18 `LearningSpaceAdoptionChanged`

生产方：`product`；归属：`learning_space`。产生条件：空间当前教材/目标采用推进。

消费方式：只查询；目标依据变更另发LearningTargetApplied。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `previous_adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_target_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `target_basis_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `cause_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

既有活动仍沿原采用，不因通知改写过去题目和作答。

<a id="domaindefinitionsaved"></a>
### 3.19 `DomainDefinitionSaved`

生产方：`domain`；归属：`domain`。产生条件：新建/修订/软删除定义提交。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `object_ref` | ObjectRef | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_ref` | ObjectRef或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `action` | create/update/soft_delete | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

对象完整历史保留，不启动历史评价。

<a id="domainintakesourceinvalidated"></a>
### 3.20 `DomainIntakeSourceInvalidated`

生产方：`domain`；归属：`domain`。产生条件：pending来源确认不可继续入库。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `item_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `import_id` | ID | 是 | 来源所属的教材导入 |
| `trigger_event_id` | ID | 是 | 导入失效的原始事件 |

已终结项不反向改状态；重复通知无变化不另发事件。

<a id="domainintakeitemprocessed"></a>
### 3.21 `DomainIntakeItemProcessed`

生产方：`domain`；归属：`domain`。产生条件：待入库处理结果提交。

消费方式：Product授权查询；不自动写章节关联。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 是 | 待办归属的领域，与事件作用域一致 |
| `request_ref` | ID | 是 | 本次处理收据 |
| `result` | IntakeActionResult | 是 | 待办修订、处理结果、对象及参考引用、归类依据、受影响待办和组内剩余数量 |

放弃时对象引用为空。组供列表展示，每次按明确选择的待办提交。

<a id="domaintemplatecandidateprepared"></a>
### 3.22 `DomainTemplateCandidatePrepared`

`DomainAnalysisInputFixed` 固定教材候选或待校验实例、父题及所选定义。`DomainTemplateCandidatePrepared` 记录 Task／Solution 定义候选。`DomainClassificationPrepared` 记录实例归类结果。这三类事件均由 Domain 生产，作用域为 `domain`，共用下表和一条 `domain.artifact` 正文。

消费方式：管理员查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 是 | 分析归属领域 |
| `request_ref` | ID | 是 | 后台工作对应的请求 |
| `artifact_ref` | Ref | 是 | 本事件正文中的固定输入、定义候选或检查产物 |
| `intake_item_ref` | Ref | 是 | 所检查的待办或手动录入输入身份 |

早期本机数据中的 `DomainInstanceClassificationChecked` 按同一正文读取。当前只写 `DomainClassificationPrepared`。

<a id="domaininstancesaved"></a>
### 3.23 `DomainInstanceSaved`

生产方：`domain`；归属：`domain`。产生条件：题目版本与参考保存。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `instance_ref` | InstanceRef | 是 | 本次追加的题目实例版本 |
| `previous_ref` | InstanceRef或null | 是 | 上一题目版本，首次保存为空 |
| `classification_check_refs` | Ref[] | 是 | 本次保存采用的检查产物 |
| `action` | create／update／soft_delete | 是 | 实际执行的动作 |
| `request_ref` | ID | 是 | 本次记录所对应的收据 |

不会产生学生已见题或作答事件。

<a id="domainkctestpathconfirmed"></a>
### 3.24 `DomainKCTestPathConfirmed`

生产方：`domain`；归属：`domain`。产生条件：确认直接检验路径。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `confirmation_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `basis_ref` | Ref | 是 | 同一事件生成的固定检验依据 |
| `kc_ref` | ObjectRef(kc) | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `task_ref` | ObjectRef(task) | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `solution_ref` | ObjectRef(solution) | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不修改个人状态和章节采用。

<a id="domainkctestpathnotready"></a>
#### 3.24.1 `DomainKCTestPathNotReady`

生产方 `domain`，归属 `domain`。要检查的关系有效且字段缺失或管理员确认依据不足时产生。随事件保存问题、可观察表现、不足示例及固定任务责任引用。使用与 §3.24 一致的 KC、Task、Solution、依据和请求引用，`confirmation_ref=null`。两类路径事实首次接线版本均为 v1，仅供查询。

<a id="activityconfigsaved"></a>
### 3.25 `ActivityConfigSaved`

生产方：`interaction`；归属：`activity_config`。产生条件：保存对象修订及新解析包。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `activity_type` | explanation/question_answer/detection/free_chat | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `config_kind` | blueprint/rule/strategy/binding | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `definition_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `config_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_config_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

旧活动不换包。

<a id="detectionplanprepared"></a>
### 3.26 `DetectionPlanPrepared`

生产方：`interaction`；归属：`learning_space`。产生条件：形成可确认题单。

消费方式：只查询/通知补读。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `plan_ref` | PlanRef | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `coverage_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不能将本事件当已同意开测。

<a id="taskusecreated"></a>
### 3.27 `TaskUseCreated`

生产方：`interaction`；归属：`learning_space`。产生条件：固定题面并正式提供。

消费方式：Evaluation沿相关作答取材；不是新评价触发。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_use_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `activity_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `round_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `plan_ref` | PlanRef或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `adoption_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

正式提供不等于已经阅读；题面原文由Interaction提供。

<a id="presentationrecorded"></a>
### 3.28 `PresentationRecorded`

生产方：`interaction`；归属：`learning_space`。产生条件：保存显示报告。

消费方式：仅显示追溯。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `presentation_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `surface` | chat/history/textbook | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `resource_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `part_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

缺失、重复或迟到不更新学习机会或概率。

<a id="helphandled"></a>
### 3.29 `HelpHandled`

生产方：`interaction`；归属：`learning_space`。产生条件：分类/轮处置或正式提供帮助分别保存。

消费方式：Evaluation经源事件取证，不直接触发评价。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `help_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `stage` | handled/provided | 是 | 区分本次留痕阶段 |
| `source_input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `classification` | neutral/substantive/uncertain | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `round_closure_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `provided_message_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

provided阶段必须有已提交消息；处理阶段为null，不把请求帮助当已提供提示。

<a id="chatmessagerecorded"></a>
### 3.30 `ChatMessageRecorded`

生产方：`interaction`；归属：`learning_space`。产生条件：正式消息保存。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `message_ref` | Ref | 是 | 消息业务身份；ChatMessageRecorded中对应本事件message记录，其余事件只引用同批或既有消息 |
| `activity_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_input_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_trigger_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `role` | student/assistant/system | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

至少一种实际来源；待分配活动不伪造归属；消息完整parts进入records；来源用EventPartRef追溯，不以引用替代必填正文。

<a id="interactioninputstopped"></a>
### 3.31 `InteractionInputStopped`

生产方：`interaction`；归属：`learning_space`。产生条件：废止当前输入后续提交权。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `stop_request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `committed_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不撤销已发生作答/供题/评价。

<a id="detectionroundclosed"></a>
### 3.32 `DetectionRoundClosed`

生产方：`interaction`；归属：`learning_space`。产生条件：检测轮收束。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `round_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `revision_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `reason` | string | 是 | submitted/help_requested/finished/switched/content_unusable等登记原因 |
| `submission_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不是第二次作答触发；没有提交时不制造答案。

<a id="answerfeedbackprepared"></a>
### 3.33 `AnswerFeedbackPrepared`

生产方：`interaction`；归属：`learning_space`。产生条件：私有当题核对已保存。

消费方式：只查询；Evaluation不订阅其语义结果。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `feedback_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `submission_ref` | Ref | 是 | 本事件submissions记录的预分配身份；不要求查询行先存在 |
| `source_input_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

反馈何时给学生由检测规则控制，不随事件提前暴露答案。

<a id="proactivetaskchanged"></a>
### 3.34 `ProactiveTaskChanged`

生产方：`interaction`；归属：`learning_space`。产生条件：保存建议变化或学生响应。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `revision_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `basis_key` | string | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `reason_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `execution_activity_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不直接修改Belief；接受不等于检测已开始；拒绝不记负证据。

<a id="proactivetaskresponded"></a>
### 3.35 `ProactiveTaskResponded`

生产方：`interaction`；归属：`learning_space`。产生条件：保存建议变化或学生响应。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `revision_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `basis_key` | string | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `reason_refs` | Ref[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `execution_activity_ref` | Ref或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `response` | accept/defer/reject | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

不直接修改Belief；接受不等于检测已开始；拒绝不记负证据。

<a id="proactivetaskprompted"></a>
### 3.36 `ProactiveTaskPrompted`

生产方：`interaction`；归属：`learning_space`。产生条件：安全时点正式提示提交。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `prompt_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `task_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `basis_key` | string | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `source_trigger_ref` | Ref | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `message_ref` | Ref | 是 | 消息业务身份；ChatMessageRecorded中对应本事件message记录，其余事件只引用同批或既有消息 |

不等浏览器回执；开放检测轮不插入提示。

<a id="claimdefinitionchanged"></a>
### 3.37 `ClaimDefinitionChanged`

生产方：`evaluation`；归属：`domain`。产生条件：Claim完整修订保存。

消费方式：只查询。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `task_ref` | ObjectRef(task) | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `previous_claim_ref` | ClaimRef或null | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `claim_ref` | ClaimRef | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `action` | string | 是 | E03合法动作 |
| `affected_method_refs` | ObjectRef(solution)[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `affected_criterion_ids` | ID[] | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |
| `request_ref` | ID | 是 | 按字段类型保存事实值或对象身份；引用不授予原文读取权限 |

非学生学习事件，不自动重评或替换应用中的Claim。

## 4. 仅模块内部使用的事实

以下沿既有模块合同留痕，不新增跨Space订阅。均采用同一信封，payload按下表；secret/password/hash/完整对话不得写入。将来用作跨模块触发时，必须先登记消费者与版本。

<a id="trialaccountsaved"></a>
### 4.1 `TrialAccountSaved`

生产方/归属：product/account。产生条件：账号及必要关系共同保存。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `account_id` | ID | 是 | 涉及的账号，不是凭据 |
| `action` | bootstrap_admin/create_student/update_student | 是 | 本次合法管理动作 |
| `account_revision` | Revision | 是 | 保存后的账号修订 |
| `relation_refs` | Ref[] | 是 | 本次涉及的已核实关系 |

<a id="usageconfirmationrecorded"></a>
### 4.2 `UsageConfirmationRecorded`

生产方/归属：product/account。产生条件：真实确认记录保存；不从密码重置推断同意。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `student_id` | ID | 是 | 已核实学生身份 |
| `confirmation_ref` | Ref | 是 | 实际使用确认记录 |
| `usage_conditions_ref` | Ref | 是 | 程序计算的使用条件 |
| `notice_text` | string | 是 | 当时告知全文；E01-10使用合成测试告知，不依赖未来文件内容反查 |

<a id="accountsignedin"></a>
### 4.3 `AccountSignedIn`

生产方/归属：product/account。产生条件：成功登录；会话ID不是Cookie凭据。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `account_id` | ID | 是 | 涉及的账号，不是凭据 |
| `session_id` | ID | 是 | 内部会话身份，不是Cookie令牌 |

<a id="accountrecovered"></a>
### 4.4 `AccountRecovered`

生产方/归属：product/account。产生条件：凭据已更新，不含明文或摘要。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `account_id` | ID | 是 | 涉及的账号，不是凭据 |
| `verification_ref` | Ref | 是 | 找回账号所据核实记录 |
| `credential_revision` | Revision | 是 | 重置后凭据修订，不含密码摘要 |

<a id="materialreceived"></a>
### 4.5 `MaterialReceived`

生产方/归属：product/material_import。产生条件：已接收文件引用保存；不代表已经解析。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 本次导入 |
| `textbook_id` | ID | 是 | 固定教材身份，原收据重放按本事实返回 |
| `source_refs` | Ref[] | 是 | 已接收文件来源 |
| `source_revision` | int | 是 | 保存后的来源修订 |
| `failed` | Issue[] | 是 | 未成功部分及原因，无则[] |

<a id="materialmetadatasaved"></a>
### 4.6 `MaterialMetadataSaved`

生产方/归属：product/material_import。产生条件：白名单基本信息保存。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `textbook_id` | ID | 是 | 教材身份 |
| `metadata_revision` | Revision | 是 | 保存后的教材信息修订 |
| `changed_fields` | string[] | 是 | 本次修改的白名单字段名 |

<a id="materialassistantmessagereceived"></a>
### 4.7 `MaterialAssistantMessageReceived`

生产方/归属：product/material_import。产生条件：教材助手受理成功。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 本次导入 |
| `request_ref` | ID | 是 | 已保存请求 |
| `message_ref` | ID | 是 | 本事件用户消息记录的预分配身份，与records主键一致 |

<a id="materialassistantturnfinished"></a>
### 4.8 `MaterialAssistantTurnFinished`

生产方/归属：product/material_import。产生条件：真实结束结局；失败不生成假候选。仅模块留痕，不新增业务订阅。

| 字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 本次导入 |
| `request_ref` | ID | 是 | 已保存请求 |
| `reply_ref` | ID或null | 是 | 本事件回复记录身份；非空必须有且仅有对应记录，无回复为null |
| `candidate_batch_refs` | Ref[] | 是 | 本次保存的候选批次，无则[] |
| `outcome` | completed/needs_input/failed/cancelled | 是 | 本轮实际结局 |


未命名的纯技术日志不冒充正式事件。新增正式事件类型须先登记类型、产生条件及payload，不能在实现中临时拼字符串发布。

### 4.9 `MaterialCandidateDeclined`

Product在管理员明确不采用候选且决定已保存时产生；scope_kind=material_import。只供追溯，不触发Domain或评价。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 原导入 |
| `batch_ref` | {batch_id:ID,batch_revision:Revision} | 是 | 固定候选批次 |
| `decision_ref` | Ref | 是 | 不可变拒绝决定 |
| `request_ref` | ID | 是 | 本次请求 |

### 4.10 `ChapterAssociationSaved`

Product完成章节添加、编辑或取消关联时产生，作用域为 `textbook`。章节关联的学生端生效由后续课程应用决定。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `textbook_id` | ID | 是 | 教材 |
| `chapter_id` | ID | 是 | 章节 |
| `result` | ChapterAssociationResult | 是 | 关系修订、Task版本、采用的方法版本、当前有效标记及汇总KC；取消时方法为空 |

## 4.1 补齐的事实类型（schema_version=1）

以下均为正式留痕，默认不触发跨Space业务。需要订阅时由消费模块登记；不能因为新增事实就默认调用AI。payload均含records，完整正文见正文合同§3；runtime补充记录见下表后的规则。

| 事件 | 生产方 / 范围 | 何时产生 | 必需事实 |
| --- | --- | --- | --- |
| `MaterialCandidatePrepared` | product / material_import | 助手保存一批候选；核对或继续修正另存新候选 | 候选及批次完整正文 |
| `MaterialIntakeStatusUpdated` | product / material_import | 消费Domain接收/拒绝事件后保存教材侧状态 | 原提交及所用Domain事件 |
| `ApplicationChecked` | product / course_application | 保存教材/目标应用检查结果 | 完整检查项、限制及固定依据 |
| `AccountSignedOut` | product / account | 确认退出或使旧登录失效 | 账号、会话非秘密身份和原因 |
| `DomainClassificationPrepared` | domain / domain | 保存题目或解法归类候选 | 所用实例内容、候选Task/Solution及检查依据 |
| `InteractionInputAccepted` | interaction / learning_space | 接受学生输入，先于AI处理 | 完整学生输入及固定空间/采用依据 |
| `InteractionInputCompleted` | interaction / learning_space | 本次处理完成或明确失败 | 输入身份、正式输出引用、结果或错误 |
| `MessageAssigned` | interaction / learning_space | 正式确定消息所属活动 | 消息及活动身份、归属版本 |
| `DetectionRoundStarted` | interaction / learning_space | 学生确认题单后开始一轮 | 轮及计划修订、题目使用身份、检测条件 |
| `TeachingOpportunityStarted` | interaction / learning_space | 创建稳定教学机会 | 机会身份、覆盖对象及依据 |
| `InteractionDecisionRecorded` | interaction / learning_space | 保存允许/拒绝的活动决策 | 规则检查、语义依据及决定；无隐藏思考 |
| `InteractionContextPrepared` | interaction / learning_space | 固定本次AI上下文 | 实际输入内容及来源；仅内部授权读取 |
| `InteractionMemorySaved` | interaction / learning_space | 保存一版记忆或摘要 | 正文、来源和替代关系；私有用途不变 |
| `ProactiveCheckCompleted` | interaction / learning_space | 完成一次主动任务必要性检查 | 输入依据、建议或无建议原因 |
| `EvaluationInputPrepared` | evaluation / learning_space | 固定本次取证材料 | 候选范围、原始事件片段、历史及缺口 |
| `EvaluationInterpretationPrepared` | evaluation / learning_space | 保存解释候选与校验结论 | 完整解释及资格依据；不是概率更新 |
| `GoalCalculationPrepared` | evaluation / learning_space | 固定目标计算依据 | 目标版本、快照、覆盖状态 |
| `AIConfigurationPinned` | ai / execution | 工作受理时固定模型配置 | 配置内容与credential_ref；禁止密钥 |
| `AICallChanged` | ai / execution | AI调用开始、完成、失败或获准恢复 | 调用及尝试的已知状态；不包括每个token |
| `ModelRequestChanged` | ai / execution | 模型请求预约或取得结果 | 实际请求、输出/错误、用量及未知项 |
| `ToolActionChanged` | ai / execution | 工具调用获准/拒绝或完成 | 实际参数、授权结论及结果；副作用由所属业务事件证明 |
| `AICandidatePrepared` | ai / execution | 保存通过结构校验的技术候选 | 候选完整内容及材料来源 |
| `ExecutionStateChanged` | runtime / execution | 工作受理、尝试开始、保存Step、停止、失败、完成或恢复 | 执行、尝试及已保存步骤；不把模型超时当成外部未执行 |
| `WaitStateChanged` | runtime / execution | 登记等待、匹配、到期、取消或处理接续 | 等待条件、期限、决定及处理结果 |
| `DeliveryStateChanged` | runtime / event_delivery | 交接安排、承接/拒绝/忽略或失败/获准重送 | 事件、订阅、交接和故障身份；不记录每次网络心跳 |
| `FileReceived` | runtime / file | 文件完整保存且校验通过 | 文件身份、媒体、字节数、hash和非秘密存储定位 |
| `ProjectionRebuildFinished` | runtime / maintenance | 维护重建完成或明确失败 | 范围、代次、固定上界、检查结果或错误 |

共同动作字段：subject_ref:Ref、outcome:string、reason_code:string或null，三者必填；subject_ref必须与信封owner_ref相同。outcome按下表穷举，不能传任意状态。记录正文通过正文合同§3登记Schema校验。本轮累计已接线TrialAccountSaved（管理员/学生开户及资料更新）、UsageConfirmationRecorded、AccountRecovered、AccountSignedIn、AccountSignedOut、FileReceived、ProjectionRebuildFinished、DeliveryStateChanged和ExecutionStateChanged；其余类型未实现。事件版本沿§3登记，不宣称执行过历史数据迁移。

| 类型 | outcome允许值 | 额外字段 |
| --- | --- | --- |
| 名称以Prepared/Pinned/Saved/Started/Accepted/Assigned/Received结尾的本节类型 | recorded | 无；仅保留服务端已确认事实 |
| MaterialIntakeStatusUpdated | received/rejected | submission_id、domain_event_id、domain_receipt_ref、outcome 必填。Domain事件同时登记为信封的原因 |
| ApplicationChecked | ready/blocked | 无；完整检查项在正文 |
| AccountSignedOut | signed_out/invalidated | account_id:ID、session_id:ID，必填；不能包含会话秘密 |
| InteractionInputCompleted | completed/failed | 无；失败原因不可为空 |
| ProactiveCheckCompleted | suggested/no_action/blocked | 无 |
| AICallChanged / ModelRequestChanged / ToolActionChanged | started/completed/failed/cancelled/unknown/denied | reason_code按结果填写；unknown保留未确认边界 |
| ExecutionStateChanged | accepted/started/stopped/failed/completed/recovery_accepted/progress_saved | 无 |
| WaitStateChanged | registered/matched/timed_out/cancelled/handled | 无 |
| DeliveryStateChanged | arranged/accepted/rejected/ignored/failed/redelivery_approved | source_event_ref:EventPartRef，必填；不能订阅自身再生成无穷投递事实 |
| ProjectionRebuildFinished | completed/failed | projector_id:string、generation:integer、scope_bounds:{scope_kind,scope_id,upper_seq}[]、checks:Issue[]，必填 |

InteractionDecisionRecorded的outcome为allowed/denied/clarify。EvaluationInterpretationPrepared的recorded只表示候选保存，不代表Evidence资格成立。新事件引用具体消息/作答时，只使用其事件正文；没有正文快照的纯动作事件，其完整事实即上述payload。

runtime运行留痕的records使用固定DTO，逐事件数量及条件见正文§3.2（H类）：ExecutionStateChanged采用executions/execution_attempts/step_results，WaitStateChanged采用waits/wait_handling，DeliveryStateChanged采用handoffs/handoff_attempts/subscription_receipts/delivery_failures，FileReceived采用file_objects。record_type为runtime.表名，schema_version=1，业务字段和JSON映射按正文合同§2.1；不含授权秘密。它们用于历史核对，不纳入业务查询表的自动重建。技术游标、锁和MQ内部状态不逐次转成事件。

按scope_kind分配序号，AI和runtime工作事实使用execution_id；投递事实使用handoff_id。对应原学习空间/教材作为subject_refs登记，可授权关联查询，但不得混进该学习空间的评价顺序。事件本身的追加、查询、发布不再产生“追加事件的事件”。

## 5. 例子与接收检查

下面只演示作答事件，不代表已经生成Evidence：

```json
{
  "event_id": "00000000-0000-4000-8000-000000000201",
  "event_type": "AnswerSubmitted",
  "schema_version": 2,
  "producer": "interaction",
  "scope_kind": "learning_space",
  "scope_id": "00000000-0000-4000-8000-000000000100",
  "owner_ref": {
    "owner": "interaction",
    "type": "submission",
    "id": "00000000-0000-4000-8000-000000000200"
  },
  "subject_refs": [],
  "actor_ref": {
    "owner": "product",
    "type": "account",
    "id": "00000000-0000-4000-8000-000000000001"
  },
  "source_execution_ref": null,
  "source_request_id": "answer-01",
  "causation_event_id": null,
  "correlation_id": "00000000-0000-4000-8000-000000000202",
  "scope_event_seq": 17,
  "occurred_at": "2026-11-15T02:00:00Z",
  "recorded_at": "2026-11-15T02:00:00Z",
  "time_basis": "server_recorded",
  "time_source_ref": null,
  "payload": {
    "submission_ref": {
      "owner": "interaction",
      "type": "submission",
      "id": "00000000-0000-4000-8000-000000000200"
    },
    "task_use_ref": {
      "owner": "interaction",
      "type": "task_use",
      "id": "00000000-0000-4000-8000-000000000203"
    },
    "activity_ref": {
      "owner": "interaction",
      "type": "activity",
      "id": "00000000-0000-4000-8000-000000000204"
    },
    "round_ref": null,
    "plan_ref": null,
    "adoption_ref": {
      "owner": "product",
      "type": "space_adoption",
      "id": "00000000-0000-4000-8000-000000000205"
    },
    "help_basis_ref": {
      "owner": "interaction",
      "type": "submission_help_basis",
      "id": "00000000-0000-4000-8000-000000000200"
    },
    "records": [
      {
        "record_id": "answer",
        "record_type": "interaction.submissions",
        "schema_version": 1,
        "content": {
          "storage": "inline",
          "value": {
            "submission_id": "00000000-0000-4000-8000-000000000200",
            "scope_id": "00000000-0000-4000-8000-000000000100",
            "source_input_ref": "00000000-0000-4000-8000-000000000208",
            "task_use_ref": "00000000-0000-4000-8000-000000000203",
            "activity_id": "00000000-0000-4000-8000-000000000204",
            "round_id": null,
            "answer": {
              "parts": [
                {
                  "part_id": "p1",
                  "type": "text",
                  "text": "原量80，增加20，新量100。"
                }
              ]
            },
            "help_basis": {
              "help_refs": [],
              "cutoff_seq": 16,
              "completeness": "complete"
            },
            "adoption_ref": "00000000-0000-4000-8000-000000000205",
            "accepted_at": "2026-11-15T02:00:00Z",
            "event_ref": "00000000-0000-4000-8000-000000000201"
          }
        }
      }
    ]
  },
  "commit_id": "00000000-0000-4000-8000-000000000207"
}
```

对应传输副本不复制payload：

```json
{
  "delivery_id": "00000000-0000-4000-8000-000000000206",
  "event_id": "00000000-0000-4000-8000-000000000201",
  "event_type": "AnswerSubmitted",
  "schema_version": 2,
  "producer": "interaction",
  "scope_kind": "learning_space",
  "scope_id": "00000000-0000-4000-8000-000000000100"
}
```

| 输入 | 接收规则 |
| --- | --- |
| 同event_id同事实重投 | 原承接收据，不新增第二次评价 |
| 同event_id不同正文/不同scope | identity_conflict，保留技术失败；不覆盖正式事件 |
| 已接受结果通知早于Wait | 结果已经持久化，后续probe可读取；不依赖再发一次通知 |
| 已结束工作收到迟到结果 | 保存可查询事实，不自动重启活动 |
| 未知event_type/schema_version | 不猜读；保留失败及传输引用，升级合法解码器后按恢复合同继续 |
| 无关作用范围或原文读取越权 | 拒绝，不以字段过滤后的空结果冒充成功 |

事件变更采用显式schema_version。旧事实不改写；新增字段先部署兼容读取，破坏性变化保留旧解码器。v1旧事件缺少完整正文时不能宣称可重建；现阶段未上线，不需虚构迁移记录。将来升级须明确旧事实完整性，不能静默从当前业务表补历史。详细迁移和恢复顺序沿基础设施§5.3，本稿不引入Evolution或历史重算。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.3 | 2026-11-15 | 补齐事件正文、记录映射、状态或读取边界；容量及保留候选仍待确认。仅文档修订，见MVP决定登记§98。 |
| v0.4 | 2026-11-16 | 同步E01-05接线范围；保留既定字段与记录矩阵 |
| v0.5 | 2026-11-16 | 登记FileReceived、完整DTO附件及E01-06实现范围 |
| v0.6 | 2026-11-16 | 接线ProjectionRebuildFinished维护结果，不增加业务事件 |
| v0.7 | 2026-11-16 | 落实账号及首次确认事件，固定告知正文与读取用途 |
| v0.8 | 2026-11-16 | 接线既定DeliveryNotice及DeliveryStateChanged，固定正式事实核验 |
| v0.9 | 2026-11-16 | 登记ExecutionStateChanged已实现范围，事件类型总数不变 |
| v0.10 | 2026-11-22 | 登记直接检验路径依据和未确认的留痕 |
| v0.11 | 2026-11-22 | 补教材接收事件的固定教材身份 |
| v0.12 | 2026-11-22 | 登记教材提交、领域受理和教材端状态回写 |
| v0.13 | 2026-11-22 | 对齐固定分析输入、归类、正式入库和章节关联的事件正文 |
