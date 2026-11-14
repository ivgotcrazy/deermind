# M1 工程设计

> **版本**：v0.47<br>
> **状态**：本轮领域模型、原型及关联合同已修订，待用户审阅；真实服务与效果未验证<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计文档规范 v1.0](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-14<br>
> **修订说明**：v0.46 → v0.47，同步新领域模型、现行文档版本、原型入口与检查边界；逐文件记录见MVP决定登记§68<br>

工程设计把M1产品规则落实为实现方案。当前审阅[系统总体设计v0.37](System_Design.md)；**确认状态和未决项统一见[总体§7.2](System_Design.md#72-总体架构问题清单)**，本入口维护文档、Operation和事件索引，不另列确认进度。

此前已将Operation限定为AI业务能力，普通业务入口另列于[§7](#7-普通业务处理目录)，路由、Worker及执行记录按此区分；见[目录§5](#5-m1-operation总目录)及[登记§67](../../DECISIONS.md#67-operation限定为ai业务能力)。未定机制仍按[总体§7.2.3](System_Design.md#723-详细设计事项的责任与确认时点)提出并确认。总体尚待用户接收，接口与字段仍为草案，未编码。

相关工程稿版本：公共运行v0.24、AI底座v0.13、Interaction v0.12、产品业务v0.12、客户端v0.11、基础设施v0.18、实施计划v0.27、Domain v0.7、Evaluation v0.11。

## 1. 文档分工

详细设计按实现责任组织，同一模块的输入输出、处理过程、数据、事件和异常放在一起。文件划分不决定进程数或部署服务数。

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

AI 底座和公共运行机制同属共用底座。各 Space 分别描述自己的定义与运行对象；Domain 题目实例不混入学生作答。Evolution 后置，在总体设计说明边界，不建立空的 M1 实现文档。

[实施与交付计划](Delivery_Plan.md)安排设计确认后的工作依赖、技术验证和交付，不属于上述九份设计。不新建交付报告占位；有实际交付后再记录结果。

## 2. 设计输入与历史参考

| 当前产品输入 | 版本与作用 |
| --- | --- |
| [PRD](../PRD.md) | v0.25：M1产品行为与验收；Web交付，学习用时功能后置 |
| [内容与模型规格](../design/Content_and_Model_Reference.md) | v0.23：对象关系、教学与评价语义、试用算法和参数 |
| [交互规格](../design/Interaction_Design.md)及[原型](../prototype/README.md) | 交互规格 v0.22：管理员和学生的操作、状态、截图；原型用于理解交互 |
| [验证计划](../validation/Validation_Plan.md) | v0.6：内容、语义、数值、效果及真实浏览器验收口径 |

本轮产品输入已按新领域模型修订，不再沿用`37bd334`作为当前内容基线。此前最小账号、取消离线检查、浏览器交付及用时后置决定仍有效。正式接收模块时固定本表现行文件与资产哈希；历史输入和mock不构成生产模型或算法。

分层依据见[已确认方向](../../DECISIONS.md#31-m1系统设计首轮实现草案)；领域与评价语义分别参考[Domain v1.6](../../../concept-design/DeerMind_Domain_Space_Design_v1.6.md)、[Evaluation v1.10](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.10.md)，AI 执行边界参考[AI Native 原则](../../../top/DeerMind_AI_Native_Architecture_Principles_v0.7.md)。具体 M1 规则以产品输入和后续已确认决定为准。

旧工程稿已进入[归档](../../archive/2026-11-11-before-swdd/README.md)，含精确原文 ZIP、SHA-256 清单和可读副本。旧稿只供参考；重建时未直接复制旧稿正文，后续确认的选型与职责按各次决定登记更新。旧稿中的 Python、数据库、框架、调度和代码目录均不因归档或重建获得批准。

## 3. 本轮必须承接的实现与复测要求

下表是产品规则到新设计位置的索引。字段、算法和异常在责任文档中展开，不在此另写一套合同。

| 产品输入 | 主要设计位置 | 需要写出的工程内容 |
| --- | --- | --- |
| PRD R01、R17：身份与必要确认 | [产品业务](Product_Application_Design.md)、[公共运行](System_Foundation_Design.md) | 预置账号、简单登录、固定两角色及必要确认；本人空间隔离与后台授权，不建设完整权限平台 |
| R02–03：整册导入、对话纠错及候选采用 | [产品业务](Product_Application_Design.md)、[AI 底座](AI_Foundation_Design.md) | 文件与页序、引用、Agent 协议、候选检查、采用及失败处理 |
| R04：领域管理与章节采用 | [Domain](Domain_Space_Design.md)、[产品业务](Product_Application_Design.md) | 任务责任、方法与题目、Task先导检查、入库、方法与章节适用来源 |
| R05、R08、R10：Claim、目标与选用 | [Evaluation](Evaluation_Space_Design.md)、[产品业务](Product_Application_Design.md) | 评价定义、目标条件、应用检查、空间采用；目标定义与个人结果分开 |
| R06、R11–13、R16：活动与检测 | [Interaction](Interaction_Space_Design.md)、[客户端](Client_Design.md) | 四类配置及活动森林、允许动作、帮助顺序、实际展示、提交与恢复 |
| R07：题目准备与运行供题 | [Domain](Domain_Space_Design.md)、[Interaction](Interaction_Space_Design.md) | 已有实例筛选、生成检查保存、本次用途及无可用题分支 |
| R14、内容§4.16–4.21：Evidence、概率与目标 | [Evaluation](Evaluation_Space_Design.md) | 解释资格、稳定机会身份、去重、纯函数、参数校验、相关Task独立取证更新及目标派生 |
| R09、R14、交互§3：运行及依据追溯 | [Evaluation](Evaluation_Space_Design.md)、[公共运行](System_Foundation_Design.md)、[产品业务](Product_Application_Design.md) | 原始事件、派生依据和结果的授权查询；事件只追加 |
| R15：主动任务 | [Interaction](Interaction_Space_Design.md)、[公共运行](System_Foundation_Design.md) | 必要性和重复依据、接受／暂缓／拒绝、进入空间检查保持条件及等待评价；无离线保持检查 |
| R18、验证§1–3：AI 与质量 | [总体§6.6](System_Design.md#66-已确认的读取工具与越权边界)、[AI 底座](AI_Foundation_Design.md)、[公共运行](System_Foundation_Design.md#5-授权执行与访问隔离)、[实施计划](Delivery_Plan.md) | Operation选材、工具及业务校验，底座通用授权与越权拦截；识别、失败和成本沿基础设施设计；确定性、接线、交互及语义验证分开 |

整册教材建模是 M1 交付范围，“四分之一”用于代表性运行链检查。R19／A18的学习用时功能整体后置，不再分派M1工程章节。Evolution、错误评价纠正、历史重算和跨版本演进按现有决定后置，正常失败重试、事件时间、保持及主动任务时间条件仍需设计。

## 4. 推进与审阅

[总体§4](System_Design.md#4-主流程的跨模块协作)已形成主流程边界，[§7.2.1](System_Design.md#721-已确认的总体选择)记录逐项决定。入口路由、同空间消息串行、生产方发布／消费方等待及Operation上下文记忆职责均已确认。恢复目标及四点保障方案已确认；A07按[登记§55](../../DECISIONS.md#55-m1资源不足的简化处理)取消业务优先级，资源不足直接返回错误和提示，不建设专门资源调度。A08的权限和模型外发职责已确认，M1不增加材料标记或内容审查；A11的短暂停机及备份恢复边界已确认，A12的日志与事件观测要求已确认，消息与事件分存边界已补齐。收口检查见[总体§7.2.2](System_Design.md#722-总体收口检查)，未发现需新增Space或底座模块的主流程缺口；单仓模块化后端、API／Worker共用代码及Python＋FastAPI已定；前端采用Vue 3＋TypeScript＋Vite，一个工程两个入口。初期API与Worker同节点共用local-path＋PVC，保留文件存储隔离与后续替换能力；现成模型API由AI底座统一接入，各类Agent可分别配置；教材解析与对话修正已确认不单独接入OCR；具体模型和量化验收安排仍需确认。表结构、接口和重试参数不展开。A01–A12继续记录覆盖与决定状态。现有分层、Space所有权、公共路由与Operation边界、组件选型及质量约束作为输入。

| 顺序 | 讨论范围 | 本轮要形成的输出 |
| --- | --- | --- |
| 1：已形成主流程边界 | 初始化、教材准备与领域融合、课程选用、学习检测、评价及教学接续 | 明确谁发起、各模块处理什么、读取和保存什么、如何传递事件及返回结果；核对AI取材、依赖等待和关键业务分支 |
| 2：当前 | [总体收口检查](System_Design.md#722-总体收口检查) | 继续确认具体模型及量化验收安排；接收总体边界，列清详细设计与验证承接 |
| 3 | 模块详细设计与工程接收 | 细化已确认方案的Operation、接口、存储、恢复及配置，不将未决架构交给编码 |

总体当前状态只在§7.2维护；[收口检查](System_Design.md#722-总体收口检查)承接详细设计与验证事项，量化验收由责任文档提出、用户确认，见[实施计划§2.1](Delivery_Plan.md#21-量化验收的提出与确认)。原有Operation及字段不因索引补齐而自动获批。

E01—E07 继续表达已确认的实现顺序，见[原决定](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)；设计文档交叉推进，不按九本文件逐本写完。每轮说明实际交付、当前未决和下一步，不把目录稿算作方案完成。

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

上方仅列AI能力；普通查询、保存、控制和确定性处理见[§7独立目录](#7-普通业务处理目录)。

- 普通入口直接处理；需要AI能力时才安排对应Operation，不先运行万能Agent再决定是否需要AI。
- 同一个AI Operation可包含确定性函数、授权查询、模型调用及跨Space异步等待。Worker执行业务代码，Temporal保障持久执行，Pydantic AI承接模型和工具调用。
- `submit_answer`只保存原始作答；AI当题反馈由`handle_input`承接已保存作答，不再次提交答案。`continue_after_result`是恢复原执行的普通回调，不是新的AI能力。
- `reassess_target`是确定性消息处理，不调用LLM、不创建AI OperationRun；作答解释内部的目标计算复用同一函数，不另建任务。
- 公共结果、等待、订阅、授权和回传服务于两类处理。结果的生产方不必是Operation；生产记录与技术执行身份的具体映射仍待详细设计。

调用方及资源边界见[总体§6.6.1](System_Design.md#661-最小调用授权矩阵)。评价原文读取见[Interaction§2.3](Interaction_Space_Design.md#23-评价原文的授权读取边界)；其接口是否复用聊天查询仍待确认，不能因需要读原文新增一个AI Operation。新增AI能力或普通公开入口均须更新相应目录和所属合同；[§3](#3-本轮必须承接的实现与复测要求)继续承接产品规则覆盖。

## 6. 跨模块事件目录

本目录登记主流程的事件含义、生产方、使用方和关联事实，作为图与模块合同的共同索引。**业务含义归生产模块，公共信封与投递机制归公共运行。** 目录中的具体命名沿用已有合同草案，字段、订阅接线及尚未命名事件留待详细设计确认；不把结果类型或Operation名称当成事件类型。

“触发处理”表示消费方因事实开展工作；“结果通知”只提示可授权读取；“查询取证／留痕”不新增订阅任务。生产方不读取使用方等待条件，是否等待、期限及超时仍归使用方；无等待者也保留正式事实。

### 6.1 触发处理与结果交接

| 事件或事实 | 何时产生／生产方 | 使用方与用途 | 关联事实与唯一合同位置 |
| --- | --- | --- | --- |
| `DomainIntakeRequested` | 产品业务提交已采用的知识、题目或解法 | Domain普通消息处理`receive_intake` | 导入、章节、已采用候选及所选内容；[产品业务§3.6](Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域)、[Domain§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `DomainIntakeReceived` | Domain已接收并保存待入库组 | 产品业务获取接收结果；不表示内容已入库 | 原提交事件、处理组和接收结果；[Domain§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `MaterialCandidatesAdopted` | 产品业务采用教材修正候选 | Domain核对受影响待办的来源是否仍有效；不改已入库定义 | 导入、采用内容及替代关系；[产品业务§3.5](Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选)、[Domain§2](Domain_Space_Design.md#2-定义维护与教材内容入库) |
| `MaterialImportDeleted` | 产品业务删除未完成导入 | Domain标记相应未入库来源失效，保留已入库内容 | 导入及受影响来源；[产品业务§3.3](Product_Application_Design.md#33-productdelete_material_import删除未完成导入)、[Domain§2](Domain_Space_Design.md#2-定义维护与教材内容入库) |
| `LearningTargetApplied` | 产品业务在空间首次采用目标或其目标条件实际变化时产生 | Evaluation普通消息处理`reassess_target`，只重新派生目标结果，不更新Belief | 学习空间、实际目标采用和条件；[应用§4.3](Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合)、[创建§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间)、[Evaluation§4](Evaluation_Space_Design.md#4-学习目标达成计算) |
| `TaskSupplyRequested` | Interaction形成一组供题要求 | Domain触发`supply_task`，统一筛选及补足题目 | 当前活动、Task、方法、用途、条件和接触事实；[Interaction§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测)、[Domain§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `DomainTaskSupplyCompleted` | Domain完成供题处理并保存批次；可有未满足项 | Interaction读取批次并复核使用条件，不自动开测 | 原供题事件、批次、实例及未满足项；[Domain§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `AnswerSubmitted` | Interaction接受实际作答并固定当时条件 | Evaluation触发`evaluate_submission`；不等当题判题 | 本次题目使用、作答、活动／轮及内容引用；[Interaction§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答)、[Evaluation§2](Evaluation_Space_Design.md#2-原始事实到evidence) |
| `TeachingOpportunityClosed` | Interaction确认教学目的收束且有实际展示依据 | Evaluation触发`apply_learning_opportunity`，再判断资格 | 稳定机会身份、展示、目的及收束依据；[Interaction§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现)、[Evaluation§3](Evaluation_Space_Design.md#3-belief分项与数值更新) |
| Evidence处理／Belief更新事实（事件名待定） | Evaluation完成证据处理或确定性更新 | Interaction按需要授权读取掌握发布；目标及追溯查询可读取相关依据 | 原始触发事件、Evidence、更新或未更新原因、只读发布引用；[Evaluation§6](Evaluation_Space_Design.md#6-处理顺序提交与恢复)；`belief_result`是结果类型 |
| 目标计算事实（事件名待定） | Evaluation完成目标对照并保存结果 | Interaction按需接续；产品业务查询入口组织目标展示 | 原始触发、目标采用、所用能力依据及目标发布引用；[Evaluation§4／6](Evaluation_Space_Design.md#4-学习目标达成计算)；`goal_result`是结果类型 |

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
| `ActivityConfigSaved` | Interaction保存活动配置 | 查询蓝图、规则及推荐策略的实际依据 | [Interaction§1.1](Interaction_Space_Design.md#11-manage_activity_config维护活动配置) |
| `ActivityChanged` | Interaction改变活动及父子接续位置 | 聊天和活动目录查询；Evaluation按需核对当时活动，不据此直接加分 | [Interaction§2.1](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| `DetectionPlanPrepared` | Interaction保存可确认题单 | 查询计划、覆盖及反馈安排；不是开测或作答事件 | [Interaction§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测) |
| 出题／题目使用事实（事件名待定） | Interaction实际安排本轮题目 | Evaluation沿作答查询当时题面和条件；引用Domain实例及实际使用内容 | [Interaction§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答)、[Evaluation§2](Evaluation_Space_Design.md#2-原始事实到evidence) |
| `PresentationRecorded`及帮助事实 | Interaction记录实际内容呈现及帮助 | Evaluation查询实际展示、时点与内容引用；没有回执仍为未知 | [Interaction§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现) |
| `DetectionRoundClosed` | Interaction记录检测轮结束 | 查询提交、求助或结束原因；不是第二次作答评价触发 | [Interaction§2.1／4.2](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| 当题判题事实（事件名待定） | Interaction保存当题判断及反馈 | 用于反馈和追溯，M1不作为Evaluation的语义Evidence输入 | [Interaction§6.1](Interaction_Space_Design.md#61-提交事实由evaluation订阅处理) |
| `ProactiveTaskChanged` | Interaction提出任务或处理学生响应 | 查询建议依据、接受／暂缓／拒绝及提醒记录，不直接改Belief | [Interaction§5](Interaction_Space_Design.md#5-主动任务的触发与接续) |
| `ClaimDefinitionChanged` | Evaluation保存Claim及判据定义 | 查询实际定义依据；不因保存自动重算历史 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面) |

普通账号、上传、候选等模块内部留痕仍在各自合同维护；一旦成为跨模块触发或取证依据须登记到本目录。消息正文经所有者授权读取，事件仅保存事实及必要引用；不得为了省一次读取把所有正文复制进事件。登记不决定所有事件都发消息或推送浏览器，订阅与客户端刷新接线仍待设计。

`apply_course`原合同已有`LearningTargetApplied`；本轮补登记而非新增触发路径。Evaluation按§6.1的作答、教学机会两类事实启动AI Operation，目标采用事实启动普通目标对照处理，不同时订阅上述保存、应用和空间留痕事件重算同一目标。需交接但未被可靠承接的失败按[总体§6.5.1](System_Design.md#651-自动重试结束后的收尾责任)处理；没有订阅用途的留痕不记“无人消费故障”。

## 7. 普通业务处理目录

以下30项从原Operation目录移出，原有业务责任继续保留。标识只是对应合同的处理名称，不统一包装为Agent或OperationRun。API、消息及内部回调的具体接线待详细设计；并非每项都对浏览器开放。

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
| `domain.save_definition` | 保存Domain、Task、Solution或KC定义 | [Domain§2.1](Domain_Space_Design.md#21-domainsave_definition) |
| `domain.receive_intake` | 幂等接收教材提交的待入库内容 | [§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `domain.process_intake` | 添加／复用KC，关联实例或移除待入库项 | [§2.3](Domain_Space_Design.md#23-domainprocess_intake) |
| `domain.query_dependencies` | 读取直接方法、KC及按方法适用的Task先导 | [§4.2](Domain_Space_Design.md#42-domainquery_dependencies) |
| `domain.save_instance` | 检查并保存题目归属与题内参考解法的方法关系 | [§5.1](Domain_Space_Design.md#51-domainsave_instance) |
| `domain.query_content` | 查询已有定义、实例、候选与待入库内容 | [§6.1](Domain_Space_Design.md#61-domainquery_content) |
| `interaction.manage_activity_config` | 维护四类活动蓝图、规则与推荐策略 | [Interaction§1.1](Interaction_Space_Design.md#11-manage_activity_config维护活动配置) |
| `interaction.control_activity` | 开始、暂停、继续、结束及切换活动 | [§2.1](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| `interaction.query_conversation` | 读取当前活动、活动目录和聊天历史 | [§2.2](Interaction_Space_Design.md#22-query_conversation查询当前交流和历史) |
| `interaction.record_presentation` | 记录实际内容呈现及已给出的帮助 | [§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现) |
| `interaction.submit_answer` | 保存当轮作答及当时的检测条件 | [§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答) |
| `interaction.respond_proactive_task` | 处理接受、暂缓、拒绝及提醒去重 | [§5.2](Interaction_Space_Design.md#52-respond_proactive_task响应主动任务) |
| `interaction.continue_after_result` | 结果就绪后检查当前活动并接续 | [§6.4](Interaction_Space_Design.md#64-continue_after_result结果就绪后接续) |
| `evaluation.manage_claim` | 维护Task Claim、方法判据及四方面判据 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面) |
| `evaluation.reassess_target` | 目标采用变化后仅重新派生目标结果 | [§4](Evaluation_Space_Design.md#4-学习目标达成计算) |
| `evaluation.query_basis` | 沿目标、Belief、Evidence查询原始依据 | [§5](Evaluation_Space_Design.md#5-评价数据与公开接口) |

普通处理同样执行授权、业务校验、提交防重和事件留痕；普通异步工作的失败及恢复要求不取消。查询和短事务可直接在API执行，需要后台处理的普通工作也可交Worker，是否需要Temporal持久执行按恢复要求设计，不因此改名为Operation。

[Operation目录](#5-m1-operation总目录)有9项AI能力，本节另列30项普通处理。其中`domain.classify_instance`从原`save_instance`已包含的AI归类步骤中分出：归类产生检查结论，普通保存处理验证所用内容仍有效后提交实例。没有增加一项用户操作，也不新增实例管理页面。
