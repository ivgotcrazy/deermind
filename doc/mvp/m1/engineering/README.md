# M1 工程设计

> **版本**：v0.26<br>
> **状态**：端到端总体协作草案待审；模块草案保留，未编码<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计文档规范 v1.0](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-13<br>
> **修订说明**：v0.25 → v0.26，索引端到端总体协作草案和四项待确认建议，更新总体版本；模块草案及实现顺序保持<br>

工程设计负责把M1产品规则落实为可实现的系统。当前交付是[总体设计v0.16的端到端协作草案](System_Design.md#4-主流程的跨模块协作)：从启动、教材准备与领域入库，走到学生选用、教学检测、评价及教学接续；配有总览、关键时序与输入输出说明。

[四项总体建议](System_Design.md#721-本轮需要确认的总体选择)分别处理入口路由、同一空间活动推进、跨空间结果就绪及上下文组装，均待用户确认。既定分层、公共运行与Operation边界、选型及最小账号范围保持；本轮未细化Operation字段或编码，见[本批记录§47](../../DECISIONS.md#47-端到端总体协作草案与未决选择)。

其他工程稿保持：公共运行v0.9、AI底座v0.4、Interaction v0.5、产品业务v0.4、客户端v0.4、基础设施v0.5、实施计划v0.13、Domain v0.2、Evaluation v0.4。整体链路和关键选择通过后，再按[九类非功能质量问题](System_Design.md#63-非功能质量属性待讨论清单)讨论目标、保障、部署与验证，最后接收总体设计并细化模块。

## 1. 文档分工

详细设计按实现责任组织，同一模块的输入输出、处理过程、数据、事件和异常放在一起。文件划分不决定进程数或部署服务数。

| 文档 | 职责与独立成文的理由 |
| --- | --- |
| [系统总体设计](System_Design.md) | 给出系统分层、模块与进程关系、跨模块协作和技术选择；为详细设计提供共同结构 |
| [产品业务设计](Product_Application_Design.md) | 账号、教材与教材助手、目标定义、学习空间；明确产品条件怎样传入核心模型 |
| [领域空间设计](Domain_Space_Design.md) | Domain、模板、实例、KC 与依赖、入库及供题；集中维护可复用领域内容 |
| [交互空间设计](Interaction_Space_Design.md) | 活动配置与执行、学习助手、检测轮、主动任务及评价协作；集中说明活动怎样推进 |
| [评估空间设计](Evaluation_Space_Design.md) | Claim、Evidence、Belief、数值核心及目标结果；一处读懂完整评价处理 |
| [AI 底座设计](AI_Foundation_Design.md) | Agent 调用循环、工具协议、上下文与记忆；各类 AI 工作复用的执行方式 |
| [公共运行机制设计](System_Foundation_Design.md) | 接入、路由、派发、运行保障、事件与回传；AI与普通后台任务共用，业务编排归Operation |
| [客户端工程设计](Client_Design.md) | 学生与管理员网页的组件、状态、接口、内容渲染、恢复及浏览器验收 |
| [基础设施与部署设计](Infrastructure_and_Deployment_Design.md) | 存储、外部服务适配、启动、配置、观测、部署与维护 |

AI 底座和公共运行机制同属共用底座。各 Space 分别描述自己的定义与运行对象；Domain 题目实例不混入学生作答。Evolution 后置，在总体设计说明边界，不建立空的 M1 实现文档。

[实施与交付计划](Delivery_Plan.md)安排设计确认后的工作依赖、技术验证和交付，不属于上述九份设计。不新建交付报告占位；有实际交付后再记录结果。

## 2. 设计输入与历史参考

| 当前产品输入 | 版本与作用 |
| --- | --- |
| [PRD](../PRD.md) | v0.24：M1产品行为与验收；Web交付，学习用时功能后置 |
| [内容与模型规格](../design/Content_and_Model_Reference.md) | v0.22：对象关系、教学与评价语义、试用算法和参数 |
| [交互规格](../design/Interaction_Design.md)及[原型](../prototype/README.md) | 交互规格 v0.21：管理员和学生的操作、状态、截图；原型用于理解交互 |
| [验证计划](../validation/Validation_Plan.md) | v0.5：内容、语义、数值、效果及真实浏览器验收口径 |

内容与交互规格仍保持 `37bd334cf29fd56b1fe5ef6f61cc3c819f01dfb0` 中的版本；最小账号能力及取消离线保持检查由[后续决定§45](../../DECISIONS.md#45-公共运行底座路由与operation执行边界)收窄，旧产品输入中的宽泛权限或时间触发描述不得覆盖本轮决定。PRD v0.24与验证计划v0.5此前按浏览器交付及用时后置决定修订，以本表及[登记§34](../../DECISIONS.md#34-mvp浏览器交付与学习用时功能后置)为当前输入。正式接收具体模块时核对实际文件和资产，不把原型mock当成生产数据或算法。

分层依据见[已确认方向](../../DECISIONS.md#31-m1系统设计首轮实现草案)；领域与评价语义分别参考[Domain v1.5](../../../concept-design/DeerMind_Domain_Space_Design_v1.5.md)、[Evaluation v1.9](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.9.md)，AI 执行边界参考[AI Native 原则](../../../top/DeerMind_AI_Native_Architecture_Principles_v0.6.md)。具体 M1 规则以产品输入和后续已确认决定为准。

旧工程稿已进入[归档](../../archive/2026-11-11-before-swdd/README.md)，含精确原文 ZIP、SHA-256 清单和可读副本。旧稿只供参考；重建时未直接复制旧稿正文，后续确认的选型与职责按各次决定登记更新。旧稿中的 Python、数据库、框架、调度和代码目录均不因归档或重建获得批准。

## 3. 本轮必须承接的实现与复测要求

下表是产品规则到新设计位置的索引。字段、算法和异常在责任文档中展开，不在此另写一套合同。

| 产品输入 | 主要设计位置 | 需要写出的工程内容 |
| --- | --- | --- |
| PRD R01、R17：身份与必要确认 | [产品业务](Product_Application_Design.md)、[公共运行](System_Foundation_Design.md) | 预置账号、简单登录、固定两角色及必要确认；本人空间隔离与后台授权，不建设完整权限平台 |
| R02–03：整册导入、对话纠错及候选采用 | [产品业务](Product_Application_Design.md)、[AI 底座](AI_Foundation_Design.md) | 文件与页序、引用、Agent 协议、候选检查、采用及失败处理 |
| R04：领域管理与章节采用 | [Domain](Domain_Space_Design.md)、[产品业务](Product_Application_Design.md) | KC Task／复合 Task、模板与实例、依赖检查、入库、方法与章节适用来源 |
| R05、R08、R10：Claim、目标与选用 | [Evaluation](Evaluation_Space_Design.md)、[产品业务](Product_Application_Design.md) | 评价定义、目标条件、应用检查、空间采用；目标定义与个人结果分开 |
| R06、R11–13、R16：活动与检测 | [Interaction](Interaction_Space_Design.md)、[客户端](Client_Design.md) | 四类配置及活动森林、允许动作、帮助顺序、实际展示、提交与恢复 |
| R07：题目准备与运行供题 | [Domain](Domain_Space_Design.md)、[Interaction](Interaction_Space_Design.md) | 已有实例筛选、生成检查保存、本次用途及无可用题分支 |
| R14、内容§4.16–4.21：Evidence、概率与目标 | [Evaluation](Evaluation_Space_Design.md) | 解释资格、稳定机会身份、去重、纯函数、参数校验、子 Task 更新及目标派生 |
| R09、R14、交互§3：运行及依据追溯 | [Evaluation](Evaluation_Space_Design.md)、[公共运行](System_Foundation_Design.md)、[产品业务](Product_Application_Design.md) | 原始事件、派生依据和结果的授权查询；事件只追加 |
| R15：主动任务 | [Interaction](Interaction_Space_Design.md)、[公共运行](System_Foundation_Design.md) | 必要性和重复依据、接受／暂缓／拒绝、进入空间检查保持条件及等待评价；无离线保持检查 |
| R18、验证§1–3：AI 与质量 | [AI 底座](AI_Foundation_Design.md)、[基础设施](Infrastructure_and_Deployment_Design.md)、[实施计划](Delivery_Plan.md) | 上下文及工具权限、识别来源、失败与成本记录；确定性、接线、交互和语义验证分别安排 |

整册教材建模是 M1 交付范围，“四分之一”用于代表性运行链检查。R19／A18的学习用时功能整体后置，不再分派M1工程章节。Evolution、错误评价纠正、历史重算和跨版本演进按现有决定后置，正常失败重试、事件时间、保持及主动任务时间条件仍需设计。

## 4. 推进与审阅

当前先审阅[总体§4](System_Design.md#4-主流程的跨模块协作)的完整协作草案，再集中确认[§7.2.1](System_Design.md#721-本轮需要确认的总体选择)的四项建议；A01–A12继续记录覆盖与决定状态。现有分层、Space所有权、公共路由与Operation边界、组件选型及质量约束作为输入。

| 顺序 | 讨论范围 | 本轮要形成的输出 |
| --- | --- | --- |
| 1：当前 | 初始化、教材准备与领域融合、课程选用、学习检测、评价及教学接续 | 明确谁发起、各模块处理什么、读取和保存什么、如何传递事件及返回结果；核对AI取材、依赖等待和关键业务分支 |
| 2：随后 | [非功能质量清单](System_Design.md#63-非功能质量属性待讨论清单) | 按已明确流程确认质量目标、优先级、总体保障思路及验证条件；必要时返回调整框架 |
| 3 | 模块详细设计与工程接收 | 细化已确认方案的Operation、接口、存储、恢复及配置，不将未决架构交给编码 |

本轮交付总体协作草案和待审建议；响应时限、可接受停机或数据损失、费用阈值及补发去重方案仍在后续讨论，不将质量事项整体后置M2。A01–A12和V01–V08继续追溯；原有Operation及字段仍为草案。

E01—E07 继续表达已确认的实现顺序，见[原决定](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)；设计文档交叉推进，不按九本文件逐本写完。每轮说明实际交付、当前未决和下一步，不把目录稿算作方案完成。

## 5. M1 Operation总目录

本表保留M1业务操作目录草案，尚不是已定的智能路由候选目录；求助Operation的拆分命名及登记方式待讨论，示意名不自动成为新接口。同一入口的有限动作以输入枚举区分，例如章节关联的添加、编辑与取消。实现不得新增一个含义不明的万能`execute`来绕过这些合同。每项的权限、输入输出、步骤、提交和失败处理只在所属模块维护。

### 5.1 产品业务

| Operation | 完成的工作 | 合同位置 |
| --- | --- | --- |
| `product.save_trial_account` | 初始化或维护试用账号、角色和关系 | [产品业务§2.1](Product_Application_Design.md#21-productsave_trial_account初始化或维护试用账号) |
| `product.record_usage_confirmation` | 留存必要使用确认 | [§2.2](Product_Application_Design.md#22-productrecord_usage_confirmation记录必要首次确认) |
| `product.sign_in` | 验证原账号并建立登录身份 | [§2.3](Product_Application_Design.md#23-productsign_in登录原账号) |
| `product.recover_account` | 管理员协助恢复原账号访问 | [§2.4](Product_Application_Design.md#24-productrecover_account管理员协助找回) |
| `product.receive_material` | 上传整册或补充材料，保留页序及原件 | [§3.1](Product_Application_Design.md#31-productreceive_material接收整批或补充材料) |
| `product.save_material_metadata` | 维护书名、领域和版本来源等基本信息 | [§3.2](Product_Application_Design.md#32-productsave_material_metadata补录教材基本信息) |
| `product.delete_material_import` | 删除未完成导入，不删除已生效模型 | [§3.3](Product_Application_Design.md#33-productdelete_material_import删除未完成导入) |
| `product.converse_material_assistant` | 通过持续对话解析或修正候选 | [§3.4](Product_Application_Design.md#34-productconverse_material_assistant持续对话解析与纠错) |
| `product.decide_material_candidate` | 核对后采用或放弃候选 | [§3.5](Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选) |
| `product.submit_domain_intake` | 分别提交知识、题目、解法供领域处理 | [§3.6](Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域) |
| `product.save_chapter_association` | 为章节添加、编辑或取消Task及方法采用 | [§4.1](Product_Application_Design.md#41-productsave_chapter_association添加编辑或取消章节关联) |
| `product.save_learning_target` | 按教材范围和Claim保存目标条件 | [§4.2](Product_Application_Design.md#42-productsave_learning_target维护目标定义) |
| `product.apply_course` | 检查准备情况并确认应用教材与目标组合 | [§4.3](Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合) |
| `product.open_learning_space` | 选用可用组合创建空间，或进入既有空间 | [§5.1](Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间) |
| `product.query_product_view` | 按资源与权限读取教材、目标、空间等视图 | [§5.2](Product_Application_Design.md#52-productquery_product_view按权限读取业务视图) |

### 5.2 Domain

| Operation | 完成的工作 | 合同位置 |
| --- | --- | --- |
| `domain.save_definition` | 保存Domain、TaskTemplate、SolutionTemplate或KC定义 | [Domain§2.1](Domain_Space_Design.md#21-domainsave_definition) |
| `domain.receive_intake` | 幂等接收教材提交的待入库内容 | [§2.2](Domain_Space_Design.md#22-domainreceive_intake) |
| `domain.process_intake` | 添加／复用KC，关联实例或移除待入库项 | [§2.3](Domain_Space_Design.md#23-domainprocess_intake) |
| `domain.extract_template` | 根据题目或解法提出模板候选 | [§3.2](Domain_Space_Design.md#32-domainextract_template) |
| `domain.query_dependencies` | 展开本层方法、子Task及KC依赖 | [§4.2](Domain_Space_Design.md#42-domainquery_dependencies) |
| `domain.save_instance` | 检查并保存TaskInstance／SolutionInstance与模板关系 | [§5.1](Domain_Space_Design.md#51-domainsave_instance) |
| `domain.supply_task` | 筛选已有题；不足时生成、检查、保存后供题 | [§5.2](Domain_Space_Design.md#52-domainsupply_task) |
| `domain.query_content` | 查询已有定义、实例、候选与待入库内容 | [§6.1](Domain_Space_Design.md#61-domainquery_content) |

### 5.3 Interaction

| Operation | 完成的工作 | 合同位置 |
| --- | --- | --- |
| `interaction.manage_activity_config` | 维护四类活动蓝图、规则与推荐策略 | [Interaction§1.1](Interaction_Space_Design.md#11-manage_activity_config维护活动配置) |
| `interaction.control_activity` | 开始、暂停、继续、结束及切换活动 | [§2.1](Interaction_Space_Design.md#21-control_activity控制活动与检测开始) |
| `interaction.query_conversation` | 读取当前活动、活动目录和聊天历史 | [§2.2](Interaction_Space_Design.md#22-query_conversation查询当前交流和历史) |
| `interaction.handle_input` | 接收一次交流，校验并提交下一活动动作 | [§3.3](Interaction_Space_Design.md#33-handle_input处理一次学生交流) |
| `interaction.record_presentation` | 记录实际内容呈现及已给出的帮助 | [§3.4](Interaction_Space_Design.md#34-record_presentation记录内容呈现) |
| `interaction.prepare_detection` | 确定检测要求并异步准备题目 | [§4.1](Interaction_Space_Design.md#41-prepare_detection准备本次检测) |
| `interaction.submit_answer` | 保存当轮作答及当时的检测条件 | [§4.2](Interaction_Space_Design.md#42-submit_answer提交实际作答) |
| `interaction.check_proactive_task` | 根据有效依据核对是否提出主动任务 | [§5.1](Interaction_Space_Design.md#51-check_proactive_task核对主动任务) |
| `interaction.respond_proactive_task` | 处理接受、暂缓、拒绝及提醒去重 | [§5.2](Interaction_Space_Design.md#52-respond_proactive_task响应主动任务) |
| `interaction.continue_after_result` | 结果就绪后检查当前活动并接续 | [§6.4](Interaction_Space_Design.md#64-continue_after_result结果就绪后接续) |

### 5.4 Evaluation

| Operation | 完成的工作 | 合同位置 |
| --- | --- | --- |
| `evaluation.manage_claim` | 维护Task Claim、方法判据及四方面判据 | [Evaluation§1](Evaluation_Space_Design.md#1-claim方法判据与评价方面) |
| `evaluation.evaluate_submission` | 作答解释、Evidence、概率更新、目标派生及结果发布 | [§2](Evaluation_Space_Design.md#2-原始事实到evidence) |
| `evaluation.apply_learning_opportunity` | 判定教学机会资格并更新学习转移预测 | [§3](Evaluation_Space_Design.md#3-belief分项与数值更新) |
| `evaluation.reassess_target` | 目标采用变化后仅重新派生目标结果 | [§4](Evaluation_Space_Design.md#4-学习目标达成计算) |
| `evaluation.query_basis` | 沿目标、Belief、Evidence查询原始依据 | [§5](Evaluation_Space_Design.md#5-评价数据与公开接口) |

### 5.5 覆盖与底座接口

| PRD范围 | 对应操作 |
| --- | --- |
| R01、R17 身份与必要确认 | 产品业务§2四项操作；各操作共同授权检查 |
| R02–03 教材输入、对话解析与纠错 | 产品业务§3.1–3.5 |
| R04 领域建模与章节采用 | `submit_domain_intake`、Domain维护／入库／查询、`save_chapter_association` |
| R05、R08、R10 Claim、目标与学生选用 | `manage_claim`、`save_learning_target`、`apply_course`、`open_learning_space` |
| R06、R11–13、R16 配置、讲解、提问、检测及持续对话 | Interaction配置／活动／输入／呈现／作答／查询及接续操作 |
| R07 出题与保存 | `prepare_detection`、`supply_task`、`save_instance` |
| R09、R14 评价及依据追溯 | Evaluation处理／查询、`query_product_view`及公共事件查询 |
| R15 主动任务 | `check_proactive_task`、`respond_proactive_task`、公共等待与到期触发 |
| R18 AI与运行质量 | AI调用合同、公共执行记录、模块错误返回；验证另按实施计划进行 |

以上38项是业务Operation定义，不表示要创建38个常驻Agent或独立服务。模型与工具循环、上下文组装是[AI底座技术接口](AI_Foundation_Design.md#1-ai任务协议与运行边界)；执行受理／查询／重试／取消／恢复以及结果读写／等待是[公共运行技术接口](System_Foundation_Design.md#33-operationrun与步骤记录)。它们共用一套实现，不在每个Space复制。

数值函数、实例验证、来源校验等内部函数只列入所属Operation的步骤；不另建调度任务。底座具体事件存储、授权适配、浏览器API和外部工具接线仍需细化，本目录的业务覆盖不等于全部技术设计已完成。后续新增公开入口必须在本表登记用途、调用方及合同位置。
