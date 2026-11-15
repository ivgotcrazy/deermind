# M1 工程设计

> **版本**：v0.76<br>
> **状态**：完整工程组织与OpenAPI修订稿待审；未创建源码、未编码<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计文档规范 v1.0](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-15<br>
> **修订说明**：v0.75 → v0.76，同步完整工程目录、模块依赖及OpenAPI使用；见MVP决定登记§97<br>

工程设计把M1产品规则落实为实现方案。本批展开后端、Vue客户端、测试和部署目录，明确模块依赖及OpenAPI生成方式。目录见[源码组织](Source_Organization.md)，公开字段见[API与消息总册](API_and_Message_Design.md)，物理定义见数据库分册；修订稿待审阅，未编码。

Operation仅封装AI业务能力，普通业务入口另列于[§7](#7-普通业务处理目录)；本批仍为9项AI Operation，不因新增字段或保存检查扩充目录。详细设计直接形成可审阅文稿，用户review后再处理意见；不以逐条对话或先写验证代码作为推进前置。影响架构的风险单独提出，其他验证留实现阶段，见[登记§70](../../DECISIONS.md#70-domain详细设计对象内容与入库)。

当前版本以各文档头部及[本轮升版表](../../DECISIONS.md#961-升版)为准；不在此重复维护第二份版本清单。

## 1. 文档分工

[数据库总册](Database_Design.md)维护分库总览和公共存储规则；`database/`分册是表、字段、物理约束、索引和关系图的唯一维护位置。[API与消息总册](API_and_Message_Design.md)及`contracts/`维护公开接口和消息字段；模块文档维护业务对象语义、读写流程、内部端口和事务边界。内部端口在分册只索引，不重复字段；物理表也只引用数据库分册。

详细设计按实现责任组织；模块说明输入输出的业务含义、处理和异常，传输格式由接口分册维护，物理存储引用数据字典。文件划分不决定进程数或部署服务数。

| 文档 | 职责与独立成文的理由 |
| --- | --- |
| [系统总体设计](System_Design.md) | 给出系统分层、模块与进程关系、跨模块协作和技术选择；为详细设计提供共同结构 |
| [产品业务设计](Product_Application_Design.md) | 账号、教材与教材助手、目标定义、学习空间；明确产品条件怎样传入核心模型 |
| [领域空间设计](Domain_Space_Design.md) | Domain、Task、Solution、KC、题目与先导、入库及供题；集中维护可复用领域内容 |
| [交互空间设计](Interaction_Space_Design.md) | 活动配置与执行、学习助手、检测轮、主动任务及评价协作；集中说明活动怎样推进 |
| [评估空间设计](Evaluation_Space_Design.md) | Claim、Evidence、Belief、数值核心及目标结果；一处读懂完整评价处理 |
| [AI 底座设计](AI_Foundation_Design.md) | 模型调用、工具执行与通用材料处理；取材、上下文组装和记忆逻辑由所属Operation维护 |
| [公共运行机制设计](System_Foundation_Design.md) | 接入、路由、派发、运行保障、事件与回传；AI与普通后台任务共用，业务流程归所属模块 |
| [客户端工程设计](Client_Design.md) | 学生与管理员网页的组件、状态、接口、内容渲染、恢复及浏览器验收 |
| [基础设施与部署设计](Infrastructure_and_Deployment_Design.md) | 存储、外部服务适配、启动、配置、观测、部署与维护 |

[源码与工程资产组织](Source_Organization.md)维护完整目录、依赖、测试和部署资产；[API与消息设计](API_and_Message_Design.md)及其七份分册维护接口合同。这些是九份设计的专题分册，不增加系统模块；源码分册不重复模块处理逻辑。

AI 底座和公共运行机制同属共用底座。各 Space 分别描述自己的定义与运行对象；Domain 题目实例不混入学生作答。Evolution 后置，在总体设计说明边界，不建立空的 M1 实现文档。

[实施与交付计划](Delivery_Plan.md)安排设计确认后的工作依赖、技术验证和交付，不属于上述九份设计。不新建交付报告占位；有实际交付后再记录结果。

事件传输和正文分开维护：[事件消息](contracts/Event_Messages.md)定义信封与逐类型动作字段；[事件正文](contracts/Event_Facts.md)定义完整内容、投影及来源闭包。字段字典仍在数据库分册，不复制到各业务模块。

## 2. 设计输入与历史参考

| 当前产品输入 | 版本与作用 |
| --- | --- |
| [PRD](../PRD.md) | v0.29：M1产品行为与验收；Web交付，学习用时功能后置 |
| [内容与模型规格](../design/Content_and_Model_Reference.md) | v0.27：对象关系、教学与评价语义、试用算法和参数 |
| [交互规格](../design/Interaction_Design.md)及[原型](../prototype/README.md) | 交互规格 v0.26：管理员和学生的操作、状态、截图；原型用于理解交互 |
| [验证计划](../validation/Validation_Plan.md) | v0.10：内容、语义、数值、效果及真实浏览器验收口径 |

本轮产品输入已按新领域模型修订，不再沿用`37bd334`作为当前内容基线。此前最小账号、取消离线检查、浏览器交付及用时后置决定仍有效。正式接收模块时固定本表现行文件与资产哈希；历史输入和mock不构成生产模型或算法。

分层依据见[已确认方向](../../DECISIONS.md#31-m1系统设计首轮实现草案)；领域与评价语义分别参考[Domain v1.7](../../../concept-design/DeerMind_Domain_Space_Design_v1.7.md)、[Evaluation v1.11](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.11.md)，AI 执行边界参考[AI Native 原则](../../../top/DeerMind_AI_Native_Architecture_Principles_v0.7.md)。具体 M1 规则以产品输入和后续已确认决定为准。

旧工程稿已进入[归档](../../archive/2026-11-11-before-swdd/README.md)，含精确原文 ZIP、SHA-256 清单和可读副本。旧稿只供参考；重建时未直接复制旧稿正文，后续确认的选型与职责按各次决定登记更新。旧稿中的 Python、数据库、框架、调度和代码目录均不因归档或重建获得批准。

## 3. 本轮必须承接的实现与复测要求

下表是产品规则到新设计位置的索引。字段、算法和异常在责任文档中展开，不在此另写一套合同。

| 产品输入 | 主要设计位置 | 需要写出的工程内容 |
| --- | --- | --- |
| PRD R01、R17：身份与必要确认 | [产品业务](Product_Application_Design.md)、[公共运行](System_Foundation_Design.md) | 预置账号、简单登录、固定两角色及必要确认；本人空间隔离与后台授权，不建设完整权限平台 |
| R02–03：整册导入、对话纠错及候选采用 | [产品业务](Product_Application_Design.md)、[AI 底座](AI_Foundation_Design.md) | 文件与页序、引用、Agent 协议、候选检查、采用及失败处理 |
| R04：领域管理与章节采用 | [Domain](Domain_Space_Design.md)、[产品业务](Product_Application_Design.md) | Domain§1维护固定版本和内容语法，§2维护复用／入库，§5.3维护归类与保存交接，§4.3维护KC路径；[物理表](database/Business_Domain.md)单独维护；Product负责章节明确采用 |
| R05、R08、R10：Claim、目标与选用 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面)、[Product§4—5](Product_Application_Design.md#4-章节关联目标定义与课程应用) | Claim快照、方法判据／方面规则、目标条件和应用；旧应用不改，空间可采用新版 |
| R06、R11–13、R16：活动与检测 | [Interaction](Interaction_Space_Design.md)、[客户端](Client_Design.md) | 四类配置及活动森林、busy与停止、整条回复、先关轮再帮助、正式提供事实及恢复 |
| R07：题目准备与运行供题 | [Domain](Domain_Space_Design.md)、[Interaction](Interaction_Space_Design.md) | 已有实例筛选、生成检查保存、本次用途及无可用题分支 |
| R14、内容§4.16–4.21：Evidence、概率与目标 | [Evaluation](Evaluation_Space_Design.md) | §2取材与资格；§3数值接线；§4目标计算；[物理表](database/Business_Evaluation.md)；§5.6维护覆盖规则，§6.4／6.6维护提交。§6.7顺序处理；§6.8保持时间 |
| 事件唯一事实源（登记§96） | [事件正文](contracts/Event_Facts.md)、[公共运行§2](System_Foundation_Design.md#2-全局事件的追加与查询)、[数据库](Database_Design.md) | 完整事实、生产者共同事务投影、订阅和历史接续、无副作用重建；消息和结果不能是独立事实源 |
| R09、R14、交互§3：运行及依据追溯 | [Evaluation](Evaluation_Space_Design.md)、[公共运行](System_Foundation_Design.md)、[产品业务](Product_Application_Design.md) | 原始事件、派生依据和结果的授权查询；事件只追加 |
| R15：主动任务 | [Interaction§5.1](Interaction_Space_Design.md#51-check_proactive_task核对主动任务)、[Product§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间) | 实际进入事件触发保持检查；同请求及同依据去重，无离线检查；接受／暂缓／拒绝按已有规则 |
| R18、验证§1–3：AI 与质量 | [总体§6.6](System_Design.md#66-已确认的读取工具与越权边界)、[AI 底座](AI_Foundation_Design.md)、[公共运行](System_Foundation_Design.md#5-授权执行与访问隔离)、[实施计划](Delivery_Plan.md) | Operation选材、工具及业务校验，底座通用授权与越权拦截；识别、失败和成本沿基础设施设计；确定性、接线、交互及语义验证分开 |

整册教材建模是 M1 交付范围，“四分之一”用于代表性运行链检查。R19／A18的学习用时功能整体后置，不再分派M1工程章节。Evolution、错误评价纠正、历史重算和跨版本演进按现有决定后置，正常失败重试、事件时间、保持及主动任务时间条件仍需设计。

## 4. 推进与审阅

[总体主流程](System_Design.md#4-主流程的跨模块协作)、[已确认选择](System_Design.md#721-已确认的总体选择)和[收口检查](System_Design.md#722-总体收口检查)作为模块设计输入，不在此复制技术选型和确认状态。详细设计按模块展开对象、处理、接口和存储；具体模型、量化验收及跨模块机制未决仍由原责任文档承接，不能在编码时无记录地决定。

| 顺序 | 讨论范围 | 本轮要形成的输出 |
| --- | --- | --- |
| 1：已形成主流程边界 | 初始化、教材准备与领域融合、课程选用、学习检测、评价及教学接续 | 明确谁发起、各模块处理什么、读取和保存什么、如何传递事件及返回结果；核对AI取材、依赖等待和关键业务分支 |
| 2：作为输入 | [总体收口检查](System_Design.md#722-总体收口检查) | 保留未决及验证责任，不重复以总体未确认阻塞已获准的详细设计 |
| 3：当前 | 模块详细设计与工程接收 | 本批展开源码组织、Vue客户端、测试部署与OpenAPI使用；详细稿及既有配置候选待用户审阅 |

总体当前状态只在§7.2维护；[收口检查](System_Design.md#722-总体收口检查)承接详细设计与验证事项，量化验收由责任文档提出、用户确认，见[实施计划§2.1](Delivery_Plan.md#21-量化验收的提出与确认)。原有Operation及字段不因索引补齐而自动获批。

E01—E07 继续表达已确认的实现顺序，见[原决定](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)；设计文档交叉推进，不按九本文件逐本写完。每轮说明实际交付、当前未决和下一步，不把目录稿算作方案完成。

本批先审[源码与工程资产组织](Source_Organization.md)，再审[Vue目录与接线](Client_Design.md#21-vue工程目录)、[OpenAPI使用](API_and_Message_Design.md#7-openapi与可执行合同)。实现接收见[计划§2.8](Delivery_Plan.md#28-源码组织与openapi接收)；真实运行和语义验证留实施阶段。

## 5. M1 Operation总目录

**Operation封装一项AI业务能力。** 它由所属业务模块或Space组织上下文、模型与工具调用、业务步骤及结果校验。普通查询、保存、活动控制和确定性计算通过API或消息处理，不因多步骤、异步执行或使用Temporal而成为Operation。

API和消息承载两类请求：普通入口直接调用相应处理器；AI入口才派发Operation。一次AI能力可以复用已有结果或走确定性分支，不要求每次调用LLM。内部函数、单次模型调用和摘要步骤不逐个登记Operation。下列名称用于合同定位，不预定HTTP路径或新增前端入口；具体接口仍待审。

### 5.1 产品业务

| Operation | AI业务能力 | 合同位置 |
| --- | --- | --- |
| `product.converse_material_assistant` | 教材助手：理解原页和修正要求，解析或修正内容候选 | [§3.4](Product_Application_Design.md#34-productconverse_material_assistant持续对话解析与纠错) |

### 5.2 Domain

| Operation | AI业务能力 | 合同位置 |
| --- | --- | --- |
| `domain.extract_template` | 定义提取：从具体题目或解法抽取Task／Solution候选（沿用技术标识） | [§3.2](Domain_Space_Design.md#32-domainextract_template) |
| `domain.supply_task` | 智能供题：按用途选题，不足时生成、核验并保存新题 | [§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `domain.classify_instance` | 实例归类：判断具体题目或解法是否符合所选Task／Solution，给出依据和缺口 | [Domain§5.3](Domain_Space_Design.md#53-domainclassify_instance) |

### 5.3 Interaction

| Operation | AI业务能力 | 合同位置 |
| --- | --- | --- |
| `interaction.handle_input` | 学习交流：理解输入，组织讲解、答疑及当题反馈，提出合法活动动作 | [§3.3](Interaction_Space_Design.md#33-handle_input处理一次学生交流) |
| `interaction.prepare_detection` | 检测准备：结合目标与已有表现提出题单安排，取得可用题并说明覆盖 | [§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测) |
| `interaction.check_proactive_task` | 主动任务建议：结合当前事实提出建议目的、内容和依据 | [§5.1](Interaction_Space_Design.md#51-check_proactive_task核对主动任务) |

### 5.4 Evaluation

| Operation | AI业务能力 | 合同位置 |
| --- | --- | --- |
| `evaluation.evaluate_submission` | 作答证据解释：按方法和判据解释表现，经程序校验后更新掌握状态 | [§2](Evaluation_Space_Design.md#2-原始事实到evidence) |
| `evaluation.apply_learning_opportunity` | 教学机会识别：定位实际教到的责任和片段，经程序核对后更新学习预测 | [§3](Evaluation_Space_Design.md#3-belief分项与数值更新) |

### 5.5 目录与执行框架的对应

<a id="55-覆盖与底座接口"></a>

上方仅列AI能力；普通查询、保存、控制和确定性处理见[§7独立目录](#7-普通业务处理目录)。与Worker的逐项映射见[公共运行§3.3.1](System_Foundation_Design.md#331-入口与worker注册对应)；共享队列不增加AI能力或改变普通入口分类。

- 普通入口直接处理；需要AI能力时才安排对应Operation，不先运行万能Agent再决定是否需要AI。
- 聊天内检测准备复用prepare_detection实现，沿handle_input原Execution；独立检测入口可直接派发prepare_detection，不新增Operation。
- 同一个AI Operation可包含确定性函数、授权查询、模型调用及跨Space异步等待。Worker执行业务代码，Temporal保障持久执行，Pydantic AI承接模型和工具调用。
- `submit_answer`只保存原始作答；AI当题反馈由`handle_input`承接已保存作答，不再次提交答案。`continue_after_result`是恢复原执行的普通回调，不是新的AI能力。
- `reassess_target`是确定性消息处理，不调用LLM、不创建AI OperationRun；作答解释内部的目标计算复用同一函数，不另建任务。
- 公共结果、等待、订阅、授权和回传服务于两类处理。结果生产方可以是ai_operation或handler，均绑定Execution及有效attempt；同步API收据不伪造后台执行。键与发布约束见公共运行§1.1—1.2。

调用方及资源边界见[总体§6.6.1](System_Design.md#661-最小调用授权矩阵)。评价原文读取见[Interaction§2.3](Interaction_Space_Design.md#23-评价原文的授权读取边界)，通过内部只读适配器承接答题区、聊天及附件，不新增AI Operation。新增AI能力或普通公开入口均须更新相应目录和所属合同；[§3](#3-本轮必须承接的实现与复测要求)继续承接产品规则覆盖。

## 6. 跨模块事件目录

本节保留类型和主流程用途索引；正式信封、逐事件字段及模块内部事实统一维护于[事件消息分册](contracts/Event_Messages.md)。业务保存条件仍由各模块负责。

本目录登记主流程的事件含义、生产方、使用方和关联事实，作为图与模块合同的共同索引。**业务含义归生产模块，公共信封与投递机制归公共运行。** 目录中的具体命名沿用已有合同草案，字段、订阅接线及尚未命名事件留待详细设计确认；不把结果类型或Operation名称当成事件类型。

“触发处理”表示消费方因事实开展工作；“结果通知”只提示可授权读取；“查询取证／留痕”不新增订阅任务。生产方不读取使用方等待条件，是否等待、期限及超时仍归使用方；无等待者也保留正式事实。

### 6.1 触发处理与结果交接

| 事件或事实 | 何时产生／生产方 | 使用方与用途 | 关联事实与唯一合同位置 |
| --- | --- | --- | --- |
| `DomainIntakeRequested` | 产品业务提交已采用的知识、题目或解法 | Domain普通消息处理`receive_intake` | 导入、章节、已采用候选及所选内容；[产品业务§3.6](Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域)、[Domain§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `DomainIntakeReceived` | Domain整批接收并保存待入库组 | Product读取intake_receipt，outcome=received；不表示已入库 | 原提交事件、处理组和接收结果；[Domain§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `DomainIntakeRejected` | Domain确认来源失效或父题缺失等业务原因，整批拒收 | Product读取intake_receipt，outcome=rejected，结束等待并展示原因；技术故障不发此事件 | 原提交事件、候选及原因；同上。重复投递读取原决定，补齐后须明确提交新请求 |
| `MaterialCandidatesAdopted` | 产品业务采用教材修正候选 | Domain核对受影响待办的来源是否仍有效；不改已入库定义 | 导入、采用内容及替代关系；[产品业务§3.5](Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选)、[Domain§2](Domain_Space_Design.md#2-定义维护与教材内容入库) |
| `MaterialImportDeleted` | 产品业务删除未完成导入 | Domain标记相应未入库来源失效，保留已入库内容 | 导入及受影响来源；[产品业务§3.3](Product_Application_Design.md#33-productdelete_material_import删除未完成导入)、[Domain§2](Domain_Space_Design.md#2-定义维护与教材内容入库) |
| `LearningTargetApplied` | Product在空间首次采用或目标依据变化时产生 | Evaluation普通处理reassess_target，只重新对照已有状态 | scope_id（学习空间）、adoption_ref、application_ref、target_basis_ref；[Product§6.1](Product_Application_Design.md#61-写入事件与跨模块交接)、[Evaluation§4](Evaluation_Space_Design.md#4-学习目标达成计算) |
| `LearningSpaceEntered` | Product接受学生实际进入；同请求一次，重连／查询除外 | Interaction的check_proactive_task；不自动开测、不触发评价 | 空间及进入时采用引用、request_ref；[Product§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间)、[Interaction§5.1](Interaction_Space_Design.md#51-check_proactive_task核对主动任务) |
| `ActivityChanged` | Interaction保存活动及路径修订 | 普通接入核对固定修订，仅结束事实触发check_proactive_task；其他变化只供查询，不能直接加分 | 活动、修订、父子返回位置及来源；[Interaction§2.5](Interaction_Space_Design.md#25-活动运行与返回)、[§5.3](Interaction_Space_Design.md#53-主动任务的依据和生命周期) |
| `TaskSupplyRequested` | Interaction形成例题、练习或检测供题要求 | Domain触发`supply_task`，统一筛选及补足题目 | 当前活动、Task、方法、用途、条件和接触事实；[Interaction§3.11](Interaction_Space_Design.md#311-讲解例题与形成性练习的供题)、[§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测)、[Domain§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `DomainTaskSupplyCompleted` | Domain完成供题处理并保存批次；可有未满足项 | Interaction读取批次并复核使用条件，不自动开测 | 原供题事件、批次、实例及未满足项；[Domain§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `AnswerSubmitted` | Interaction接受实际作答并固定当时条件 | Evaluation触发`evaluate_submission`；不等当题判题 | 本次题目使用、作答、活动／轮及内容引用，当时目标／教材采用依据与存在时的题单引用；[Interaction§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答)、[Evaluation§2](Evaluation_Space_Design.md#2-原始事实到evidence) |
| `TeachingOpportunityClosed` | Interaction收束服务端正式提供的教学段，不等显示回执 | Evaluation触发`apply_learning_opportunity`，再判断资格 | 机会身份、正式内容、目的、收束及采用引用；[Interaction§3.7](Interaction_Space_Design.md#37-帮助与教学机会的服务端事实)、[Evaluation§3](Evaluation_Space_Design.md#3-belief分项与数值更新) |
| `BeliefEvaluationCompleted` | Evaluation提交一批Evidence及更新／未更新结果 | Interaction按需要授权读取、接续或核对主动任务；目标及追溯查询可读取依据 | 原始触发、input_ref、Evidence／修订、snapshot_ref、result_ref及原因；[Evaluation§6.5](Evaluation_Space_Design.md#65-事件与结果交接)、[Interaction§5.3](Interaction_Space_Design.md#53-主动任务的依据和生命周期)；未取得目标结果时不能先宣告达标 |
| `GoalEvaluationCompleted` | Evaluation保存本次目标计算结果，含历史／未推进结果 | Interaction核对当前依据后接续或检查主动任务；Product授权查询并组织展示 | 触发、目标及快照、结果引用、是否推进当前；[Evaluation§6.5](Evaluation_Space_Design.md#65-事件与结果交接)、[Interaction§5.3](Interaction_Space_Design.md#53-主动任务的依据和生命周期)；两类评价通知不重复创建同依据任务 |

### 6.2 查询取证与业务留痕

| 事件或事实 | 生产方与含义 | 使用方式与关联事实 | 合同位置 |
| --- | --- | --- | --- |
| `LearningTargetSaved` | 产品业务保存共享目标定义 | 查询定义及采用依据；不针对个人空间，不触发目标重评 | [产品业务§4.2](Product_Application_Design.md#42-productsave_learning_target维护目标定义) |
| `CourseApplied` | 产品业务确认应用教材与目标组合；不新增课程实体 | 查询组合采用及使用限制；不是个人目标重评触发 | [产品业务§4.3](Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合) |
| `LearningSpaceCreated` | 产品业务创建个人学习空间 | 查询空间、所属学生及首次采用；初始目标对照由同次提交的`LearningTargetApplied`触发 | [产品业务§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间) |
| `LearningSpaceAdoptionChanged` | 产品业务更新已有空间的当前教材／目标采用 | 查询新旧采用依据；仅当目标条件实际变化时另有`LearningTargetApplied`，不重复触发评价 | [产品业务§4.3](Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合) |
| `DomainDefinitionSaved` | Domain保存定义 | 查询定义及实际依据，不自动重新评价历史作答 | [Domain§2.1](Domain_Space_Design.md#21-domainsave_definition) |
| `DomainIntakeSourceInvalidated` | Domain确认未入库来源已被替代或删除 | 教材与待办查询来源失效结果；不撤销已入库对象 | [Domain§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `DomainIntakeItemProcessed` | Domain处理入库项 | 教材可查询处理结果及关联对象；不自动建立章节关联 | [Domain§2.3](Domain_Space_Design.md#23-domainprocess_intake) |
| `DomainTemplateCandidatePrepared` | Domain形成Task／Solution候选 | 管理员核对候选及来源，不等于正式定义已保存 | [Domain§3.2](Domain_Space_Design.md#32-domainextract_template) |
| `DomainInstanceSaved` | Domain保存题目、题内参考及定义关系 | 查询题目、题内参考、Task／Solution及来源；不等于学生已见题 | [Domain§5.1](Domain_Space_Design.md#51-domainsave_instance) |
| `DomainKCTestPathConfirmed` | Domain确认已有版本的KC直接检验路径 | 查询内容就绪依据；不产生个人评价、不自动改章节关联 | [Domain§4.3](Domain_Space_Design.md#43-kc直接检验路径的准备与确认)、[§6.6](Domain_Space_Design.md#66-http请求响应与分页) |
| `ActivityConfigSaved` | Interaction保存活动配置 | 查询蓝图、规则及推荐策略的实际依据 | [Interaction§1.1](Interaction_Space_Design.md#11-manage_activity_config维护活动配置) |
| `DetectionPlanPrepared` | Interaction保存可确认题单 | 查询计划、覆盖及反馈安排；不是开测或作答事件 | [Interaction§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测) |
| `TaskUseCreated` | Interaction固定并正式提供本次题面 | Evaluation沿作答读取当时题面、条件和采用引用；不代表浏览器已阅读 | [Interaction§4.3、§6.5](Interaction_Space_Design.md#43-计划题目使用与提交记录) |
| `PresentationRecorded` | Interaction保存客户端显示报告 | 只供显示追溯；缺失或迟到不影响评价 | [Interaction§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现) |
| `HelpHandled` | Interaction提交帮助分类／轮处置或正式帮助内容 | Evaluation沿作答读取提交前正式帮助；请求与提供分开留痕 | [Interaction§3.7、§6.5](Interaction_Space_Design.md#37-帮助与教学机会的服务端事实) |
| `ChatMessageRecorded` | Interaction保存正式消息 | 查询消息与事件的引用；不等于新的作答或机会 | [Interaction§6.5](Interaction_Space_Design.md#65-本space的事件载荷) |
| `InteractionInputStopped` | Interaction停止当前回复并废止提交令牌 | 查询停止及已有结果；不撤销作答或评价 | [Interaction§3.6](Interaction_Space_Design.md#36-停止本次回复) |
| `DetectionRoundClosed` | Interaction记录检测轮结束 | 查询提交、求助或结束原因；不是第二次作答评价触发 | [Interaction§2.1／4.2](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| `AnswerFeedbackPrepared` | Interaction保存当题判断及反馈 | 用于反馈和追溯，M1不作为Evaluation的语义Evidence输入 | [Interaction§6.1](Interaction_Space_Design.md#61-提交事实由evaluation订阅处理) |
| `ProactiveTaskChanged`／`ProactiveTaskResponded` | Interaction提出任务或处理学生响应 | 查询建议依据、接受／暂缓／拒绝及提醒记录，不直接改Belief | [Interaction§5](Interaction_Space_Design.md#5-主动任务的触发与接续) |
| `ProactiveTaskPrompted` | Interaction在安全时点保存正式提示 | 查询提示发生及消息引用；不触发接受、活动执行或概率更新 | [Interaction§5.4／6.5](Interaction_Space_Design.md#54-提示接受与返回) |
| `ClaimDefinitionChanged` | Evaluation保存Claim及判据定义 | 查询实际定义依据；不因保存自动重算历史 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面) |

账号、上传、候选和运行留痕统一登记于事件合同；本目录索引生产方和用途。事件保存当时完整事实，大正文使用固定附件，NATS只传通知。登记不表示向浏览器推送完整事件；客户端仍按授权查询业务视图。

`apply_course`原合同已有`LearningTargetApplied`；本轮补登记而非新增触发路径。Evaluation按§6.1的作答、教学机会两类事实启动AI Operation，目标采用事实启动普通目标对照处理，不同时订阅上述保存、应用和空间留痕事件重算同一目标。需交接但未被可靠承接的失败按[总体§6.5.1](System_Design.md#651-自动重试结束后的收尾责任)处理；没有订阅用途的留痕不记“无人消费故障”。

### 6.3 完整事实与运行留痕补充

正文和类型化字段只在[事件消息](contracts/Event_Messages.md#41-补齐的事实类型schema_version1)与[事件正文](contracts/Event_Facts.md)维护。下表是新增类型的责任索引；只留痕不等于自动订阅，不增加AI Operation。原47类载荷升至v2，新27类为v1；共74类。

| 事件 | 生产方 / 范围 | 事实及用途 |
| --- | --- | --- |
| `MaterialCandidatePrepared` | product / material_import | 助手保存一批候选；核对或继续修正另存新候选；按授权查询/投影，不默认触发AI |
| `MaterialIntakeStatusUpdated` | product / material_import | 消费Domain接收/拒绝事件后保存教材侧状态；Product消费Domain结果后生成教材状态 |
| `ApplicationChecked` | product / course_application | 保存教材/目标应用检查结果；按授权查询/投影，不默认触发AI |
| `AccountSignedOut` | product / account | 确认退出或使旧登录失效；按授权查询/投影，不默认触发AI |
| `DomainClassificationPrepared` | domain / domain | 保存题目或解法归类候选；按授权查询/投影，不默认触发AI |
| `InteractionInputAccepted` | interaction / learning_space | 接受学生输入，先于AI处理；按授权查询/投影，不默认触发AI |
| `InteractionInputCompleted` | interaction / learning_space | 本次处理完成或明确失败；按授权查询/投影，不默认触发AI |
| `MessageAssigned` | interaction / learning_space | 正式确定消息所属活动；按授权查询/投影，不默认触发AI |
| `DetectionRoundStarted` | interaction / learning_space | 学生确认题单后开始一轮；按授权查询/投影，不默认触发AI |
| `TeachingOpportunityStarted` | interaction / learning_space | 创建稳定教学机会；按授权查询/投影，不默认触发AI |
| `InteractionDecisionRecorded` | interaction / learning_space | 保存允许/拒绝的活动决策；按授权查询/投影，不默认触发AI |
| `InteractionContextPrepared` | interaction / learning_space | 固定本次AI上下文；按授权查询/投影，不默认触发AI |
| `InteractionMemorySaved` | interaction / learning_space | 保存一版记忆或摘要；按授权查询/投影，不默认触发AI |
| `ProactiveCheckCompleted` | interaction / learning_space | 完成一次主动任务必要性检查；按授权查询/投影，不默认触发AI |
| `EvaluationInputPrepared` | evaluation / learning_space | 固定本次取证材料；按授权查询/投影，不默认触发AI |
| `EvaluationInterpretationPrepared` | evaluation / learning_space | 保存解释候选与校验结论；按授权查询/投影，不默认触发AI |
| `GoalCalculationPrepared` | evaluation / learning_space | 固定目标计算依据；按授权查询/投影，不默认触发AI |
| `AIConfigurationPinned` | ai / execution | 工作受理时固定模型配置；按授权查询/投影，不默认触发AI |
| `AICallChanged` | ai / execution | AI调用开始、完成、失败或获准恢复；按授权查询/投影，不默认触发AI |
| `ModelRequestChanged` | ai / execution | 模型请求预约或取得结果；按授权查询/投影，不默认触发AI |
| `ToolActionChanged` | ai / execution | 工具调用获准/拒绝或完成；按授权查询/投影，不默认触发AI |
| `AICandidatePrepared` | ai / execution | 保存通过结构校验的技术候选；按授权查询/投影，不默认触发AI |
| `ExecutionStateChanged` | runtime / execution | 工作受理、尝试开始、停止、失败、完成或恢复；按授权查询/投影，不默认触发AI |
| `WaitStateChanged` | runtime / execution | 登记等待、匹配、到期、取消或处理接续；按授权查询/投影，不默认触发AI |
| `DeliveryStateChanged` | runtime / event_delivery | 交接安排、确认承接或失败/获准重送；按授权查询/投影，不默认触发AI |
| `FileReceived` | runtime / file | 文件完整保存且校验通过；按授权查询/投影，不默认触发AI |
| `ProjectionRebuildFinished` | runtime / maintenance | 维护重建完成或明确失败；按授权查询/投影，不默认触发AI |

## 7. 普通业务处理目录

以下31项普通处理保留原有业务责任，其中30项从原Operation目录移出，KC路径确认已另行登记。认证会话读取、退出及连接订阅是技术子接口，不另列AI能力。标识只是对应合同的处理名称，不统一包装为Agent或OperationRun。Domain的API与消息端口见其§6，其余接线按模块细化；并非每项都对浏览器开放。

| 普通处理 | 完成的工作 | 合同位置 |
| --- | --- | --- |
| `product.save_trial_account` | 初始化或维护试用账号、角色和关系 | [产品业务§2.1](Product_Application_Design.md#21-productsave_trial_account初始化或维护试用账号) |
| `product.record_usage_confirmation` | 留存必要使用确认 | [§2.2](Product_Application_Design.md#22-productrecord_usage_confirmation记录必要首次确认) |
| `product.sign_in` | 验证原账号并建立登录身份 | [§2.3](Product_Application_Design.md#23-productsign_in登录原账号) |
| `product.recover_account` | 管理员协助恢复原账号访问 | [§2.4](Product_Application_Design.md#24-productrecover_account管理员协助找回) |
| `product.receive_material` | 上传整册或补充材料，保留页序及原件 | [§3.1](Product_Application_Design.md#31-productreceive_material接收整批或补充材料) |
| `product.save_material_metadata` | 维护书名、领域和版本来源等基本信息 | [§3.2](Product_Application_Design.md#32-productsave_material_metadata补录教材基本信息) |
| `product.delete_material_import` | 删除未完成导入，不删除已生效模型 | [§3.3](Product_Application_Design.md#33-productdelete_material_import删除未完成导入) |
| `product.decide_material_candidate` | 核对后采用或放弃候选 | [§3.5](Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选) |
| `product.submit_domain_intake` | 分别提交知识、题目、解法供领域处理 | [§3.6](Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域) |
| `product.save_chapter_association` | 为章节添加、编辑或取消Task及方法采用 | [§4.1](Product_Application_Design.md#41-productsave_chapter_association添加编辑或取消章节关联) |
| `product.save_learning_target` | 按教材范围和Claim保存目标条件 | [§4.2](Product_Application_Design.md#42-productsave_learning_target维护目标定义) |
| `product.apply_course` | 检查准备情况并确认应用教材与目标组合 | [§4.3](Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合) |
| `product.open_learning_space` | 选用可用组合创建空间，或进入既有空间 | [§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间) |
| `product.query_product_view` | 按资源与权限读取教材、目标、空间等视图 | [§5.2](Product_Application_Design.md#52-productquery_product_view按权限读取业务视图) |
| `domain.save_definition` | 新建、追加修订或软删除定义；保留全部历史版本 | [Domain§2.1](Domain_Space_Design.md#21-domainsave_definition) |
| `domain.receive_intake` | 幂等接收教材提交的待入库内容 | [§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `domain.process_intake` | 添加／复用KC，关联实例或移除待入库项 | [§2.3](Domain_Space_Design.md#23-domainprocess_intake) |
| `domain.confirm_kc_path` | 确认已有KC／Task／Solution版本的直接检验路径，追加内容就绪依据 | [Domain§4.3](Domain_Space_Design.md#43-kc直接检验路径的准备与确认)、[§6.6](Domain_Space_Design.md#66-http请求响应与分页) |
| `domain.query_dependencies` | 读取直接方法、KC及按方法适用的Task先导 | [§4.2](Domain_Space_Design.md#42-domainquery_dependencies) |
| `domain.save_instance` | 检查归属后保存题目／参考的新版本，或软删除题目 | [§5.1](Domain_Space_Design.md#51-domainsave_instance) |
| `domain.query_content` | 查询已有定义、实例、候选与待入库内容 | [§6.1](Domain_Space_Design.md#61-domainquery_content) |
| `interaction.manage_activity_config` | 维护四类活动蓝图、规则与推荐策略 | [Interaction§1.1](Interaction_Space_Design.md#11-manage_activity_config维护活动配置) |
| `interaction.control_activity` | 开始、暂停、继续、结束及切换活动；停止本次回复 | [§2.1](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| `interaction.query_conversation` | 读取当前活动、活动目录和聊天历史 | [§2.2](Interaction_Space_Design.md#22-query_conversation查询当前交流和历史) |
| `interaction.record_presentation` | 记录客户端显示报告，不触发评价 | [§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现) |
| `interaction.submit_answer` | 保存当轮作答及当时的检测条件 | [§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答) |
| `interaction.respond_proactive_task` | 处理接受、暂缓、拒绝及提醒去重 | [§5.2](Interaction_Space_Design.md#52-respond_proactive_task响应主动任务) |
| `interaction.continue_after_result` | 结果就绪后检查当前活动并接续 | [§6.4](Interaction_Space_Design.md#64-continue_after_result结果就绪后接续) |
| `evaluation.manage_claim` | 维护Task Claim、方法判据及四方面判据 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面) |
| `evaluation.reassess_target` | 目标采用变化后仅重新派生目标结果 | [§4](Evaluation_Space_Design.md#4-学习目标达成计算) |
| `evaluation.query_basis` | 沿目标、Belief、Evidence查询原始依据 | [§5](Evaluation_Space_Design.md#5-评价数据与公开接口) |

普通处理同样执行授权、业务校验、提交防重和事件留痕；普通异步工作的失败及恢复要求不取消。查询和短事务可直接在API执行，需要后台处理的普通工作也可交Worker，是否需要Temporal持久执行按恢复要求设计，不因此改名为Operation。

[Operation目录](#5-m1-operation总目录)有9项AI能力，本节另列31项普通处理。其中`domain.classify_instance`从原`save_instance`已包含的AI归类步骤中分出：归类产生检查结论，普通保存处理验证所用内容仍有效后提交实例。没有增加一项用户操作，也不新增实例管理页面。

此前评价候选范围和KC路径修订见[决定登记§69](../../DECISIONS.md#69-评价候选范围与kc直接检验路径补齐)。领域旧技术名称与本批详细设计字段的对应见[变更清单§9](../design/Domain_Model_Revision_Checklist.md#9-评审修订与待迁移名称)；不把旧字段名或Operation标识当成模型结构。

本轮修订（v0.48，2026-11-14）：同步现行版本及产品规则到工程责任；链接候选范围、KC路径及迁移登记。本轮仅改文档；完整记录见MVP决定登记§69。

本轮修订（v0.49，2026-11-14）：转入模块详细设计，登记Domain v0.9、产品业务v0.14和客户端v0.12；更新入库、内容、版本及审阅入口，Operation和事件目录数量不变。变更清单与自检见MVP决定登记§70。

本轮修订（v0.50，2026-11-14）：登记Domain v0.10存储／接口及同库事务，更新相关版本和下一步；9项AI Operation不变，普通处理增补KC路径确认及其留痕事件，见MVP决定登记§71。

本轮修订（v0.51，2026-11-14）：更新Product详细设计审阅路径、关联模块版本及后续安排；AI Operation仍9项、普通入口31项。教材内部工具及保护端口不另登记业务能力，见决定登记§72。

本轮修订（v0.52，2026-11-15）：登记目标应用和学生选用交付，补进入事件及跨模块读取；AI Operation仍9项、普通入口31项，见MVP决定登记§73。

本轮修订（v0.53，2026-11-15）：更新Evaluation审阅入口、版本与目标计算事件目录；本批只修订文档，见MVP决定登记§74。

本轮修订（v0.54，2026-11-15）：更新评价取材审阅入口、版本及Belief事件目录；本批仅修订文档，见MVP决定登记§75。

本轮修订（v0.55，2026-11-15）：同步事件目录、版本、审阅入口及后续安排。本批仅修订文档，见MVP决定登记§76。

本轮修订（v0.56，2026-11-15）：同步版本、事件登记、规则归属与本批审阅入口。仅修订文档，见MVP决定登记§77。

本轮修订（v0.57，2026-11-15）：同步现行版本、运行合同与审阅入口。仅修订文档，见MVP决定登记§78。

本轮修订（v0.58，2026-11-15）：同步AI底座交付、工程版本及审阅入口。仅修订文档，见MVP决定登记§79。

本轮修订（v0.59，2026-11-15）：同步认证与客户端详细设计入口及版本。仅修订文档，见MVP决定登记§80。

本轮修订（v0.60，2026-11-15）：同步存储部署、迁移与备份恢复详细稿及后续事项。仅修订文档，见MVP决定登记§81。

本轮修订（v0.61，2026-11-15）：同步本批模型接线交付、决定和后续顺序。仅修订文档，见MVP决定登记§82。

本轮修订（v0.62，2026-11-15）：更新本批合同审阅入口、版本和后续顺序。仅修订文档，见MVP决定登记§83。

本轮修订（v0.63，2026-11-15）：同步首轮模型、测试环境、部署入口和候选审阅顺序。仅修订文档，见MVP决定登记§84。

本轮修订（v0.64，2026-11-15）：更新部署草案审阅入口、当前版本和后续计划。仅修订文档，见MVP决定登记§85。

本轮修订（v0.65，2026-11-15）：同步恢复决定、预算草案入口及当前工程版本。仅修订文档，见MVP决定登记§86。

本轮修订（v0.66，2026-11-15）：同步材料容量与保留决定、审阅入口及当前工程版本。仅修订文档，见MVP决定登记§87。

本轮修订（v0.67，2026-11-15）：同步日志简化、剩余设计顺序及当前工程版本。仅修订文档，见MVP决定登记§88。

本轮修订（v0.68，2026-11-15）：同步Worker注册入口及当前工程版本。仅修订文档，见MVP决定登记§89。

本轮修订（v0.69，2026-11-15）：同步参数审阅入口及当前工程版本。仅修订文档，见MVP决定登记§90。

本轮修订（v0.70，2026-11-15）：同步主流程检查结论、审阅入口及现行版本。仅修订文档，见MVP决定登记§91。

本轮修订（v0.71，2026-11-15）：同步数据库总目录、完整字段及关系图；维护字段与处理合同的单一职责，物理设计待审阅。仅文档修订，见MVP决定登记§92。

本轮修订（v0.72，2026-11-15）：物理表定义集中到数据库分册；模块保留流程、接口和事务规则。保持同库schema划分，未改原型或编码。见MVP决定登记§93。

本轮修订（v0.73，2026-11-15）：集中API与消息传输合同，模块保留业务语义和处理规则；字段与入口待审，未编码。见[MVP决定登记§94](../../DECISIONS.md#94-api与消息设计分册及唯一维护位置)。

本轮修订（v0.74，2026-11-15）：落实API与数据库评审，统一相关文档口径。见MVP决定登记§95。

本轮修订（v0.75，2026-11-15）：统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。

本轮修订（v0.76，2026-11-15）：同步工程目录、职责依赖、Vue客户端及OpenAPI生成边界。仅文档修订，见MVP决定登记§97。
