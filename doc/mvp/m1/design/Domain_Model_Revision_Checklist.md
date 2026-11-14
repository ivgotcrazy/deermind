# Domain 模型调整清单

> **版本**：v0.2<br>
> **文档性质**：跨文档、原型与验证资产的实施清单和接收记录<br>
> **状态**：本轮领域模型、原型及关联合同已修订，待用户审阅；真实服务与效果未验证<br>
> **上游依据与基线**：2026-11-14 用户提供的 Gemini 讨论及随后“理解 d=v×t”的讨论；当前工作区基线见§1<br>
> **维护责任**：Codex 负责影响核对、实施与自检；用户确认模型取舍及待决方案<br>
> **评审记录**：用户批准模型变更及完整实施；作者检查见MVP决定登记§68，不代表真实效果验收通过<br>
> **写作规范**：[设计文档规范](../../../top/DeerMind_Design_Document_Standard_v1.1.md)；工程文件继续遵循[系统设计写作规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-14<br>
> **修订说明**：v0.1 → v0.2，记录获准实施范围、实际交付、作者检查与历史资产边界；逐文件记录见MVP决定登记§68<br>

---

本次要将领域模型调整为 Domain 内的 Task、Solution、KC 与 TaskInstance，减少强制参数化和递归解法维护，另以 Task 先导关系支持教学。交付目标是新模型在现行文档、原型和验收口径中一致；不以文档完成代替真实提取、教学或评价验证。

**最终审阅顺序：先看§8交付和检查结果，再按§2、§3核对模型变化，最后对照原型与正文。** §1及§4中的旧版本是实施前基线，现行版本见§8清单。长期模型定义仍由Domain专项文档维护。

## 1. 当前基线与修改边界

本次读取的 Git HEAD 为 `417bd08da2a39f8895fded1e94ac3b9d40c335f2`。工作区另有14份既有文档修改，主要是已完成的 Operation 边界修订；HEAD不能代表这些工作内容。本清单以当前文件内容为工作基线，执行前固定可恢复基线并核对期间新增改动，不覆盖此前工作。

| 输入 | 当前版本与用途 |
| --- | --- |
| [Domain 专项定义](../../../concept-design/DeerMind_Domain_Space_Design_v1.6.md) | v1.5：对象、KC Task／复合 Task、方法调用及知识汇总的现行合同 |
| [Evaluation 专项定义](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.10.md) | v1.9：Task Claim、Evidence、Belief及任务间更新边界 |
| [M1 PRD](../PRD.md) | v0.24：管理员准备、学生使用与验收 |
| [内容与模型规格](Content_and_Model_Reference.md) | v0.22：对象字段、实例、判据、概率及贯穿案例 |
| [交互规格](Interaction_Design.md) | v0.21：页面流程、截图及已知文档／原型差距 |
| [工程入口](../engineering/README.md) | v0.46：9项AI Operation、普通业务与事件目录 |
| [总体设计](../engineering/System_Design.md)／[Domain工程设计](../engineering/Domain_Space_Design.md) | v0.36／v0.6：跨模块主流程与领域操作合同 |
| [验证计划](../validation/Validation_Plan.md)／[决定登记](../../DECISIONS.md) | v0.5／v0.63：未来验证要求及已有决定历史 |
| [M1 原型](../prototype/README.md) | 独立 Vue 原型及浏览器本地 mock；不能由文档推定页面已适配 |

已核实三个实际差距：原型仍维护 KC 先修列表；评估原型仍递归读取子方法判据；原型未完整实现上一轮文档的 KC Task／复合 Task 限制。因此，实施直接对照新合同整理实际代码，不先补齐即将取消的旧限制。

本次不重选技术栈、不接真实LLM、不改BKT公式和全局0.90阈值，不扩展课程或客户端范围。取消 Domain 求解调用树，不取消 Interaction 的活动森林，也不取消工程 Operation 内部的 Step。它们是不同结构。

## 2. 新旧规则与变更范围

用户已批准以下方向及§3的M1处理方式，现已传导到模型、规格、原型与工程合同。业务语义在Domain专项定义维护，M1内容规格展开实际字段与案例，其他文件引用并描述自身如何使用。

| 编号 | 原来是什么 | 准备改成什么 | 主要影响与接收条件 |
| --- | --- | --- | --- |
| DM01 对象名称与身份 | TaskTemplate、SolutionTemplate、KC及两类实例 | Task、Solution、KC、TaskInstance；Domain仍是一等领域容器 | 定义、页面、目录、图示和引用统一；Task定义与具体题、活动、系统待办不混称。仅更名不默认重建对象身份 |
| DM02 Task表达 | 参数、关系、变化、边界及KC／复合角色共同定义任务 | 明确任务责任、应交付的表现、适用条件和边界；取消强制参数化及两类结构角色 | 仍能区分“解释关系”“代入计算”和复杂综合任务；保留已有公式及有效条件，不退化成名称标签 |
| DM03 Solution表达 | 输入输出、步骤控制、子Task与子方法调用、绑定、退出条件 | 描述学生完成Task的方法、依据、适用条件及必要关键过程；不要求预建递归执行图 | 不要求填写子调用和绑定才可使用；有价值的分支、复查含义可保留为方法说明；不混入系统教学策略 |
| DM04 知识关联 | KC Task本层仅一个KC；复合方法本层零KC；知识沿调用树汇总 | Solution直接关联所涉及的多个KC；Task汇总自身方法，章节汇总选用方法，按KC身份去重 | Task和章节仍不直接关联KC；先导Task的全部知识不混入当前方法覆盖。每个正式用于教学评价的KC仍有明确的直接检验任务与方法 |
| DM05 先导关系 | 规范依赖主要沿Solution调用表达；旧原型另维护KC先修 | 在Task层表达先导任务，按需要注明适用方法；KC不维护另一套先导图 | 用于教学检查和安排，不直接传播概率，不将特定方法的需要强加全部方法；Q03确定维护口径 |
| DM06 具体解法 | SolutionInstance独立命名、归类和入库，引用题目与方法 | 具体解法作为TaskInstance的参考内容保存，保留Solution关联、图表和来源 | 取消独立对象管理不等于删除教材原解、运行参考或历史依据；题目可先入库、解法可后补。见Q01 |
| DM07 教材与章节 | 提取三类模型候选，分别入库，再关联模板及方法 | 保留知识、题目、具体解法的语义提取；解法依附题目；领域处理完成后，章节选Task与Solution | 教材助手仍用对话纠错；题目与解法仍能分别选择；提取、正式入库、章节采用保持不同责任 |
| DM08 实例归属与供题 | 按模板参数和结构归类、实例化并检查 | 按Task责任、范围和Solution条件识别归属、生成及检查 | 同义情境可归同一Task，改变责任不得硬归；无法确认保留未决；供题仍由Domain统一检查、保存后使用。见Q04 |
| DM09 Claim与Evidence | 按Task／方法／四方面评价，并沿实际子调用核对证据 | 保留Claim、方法、四方面及确定性概率更新；取消按定义调用树自动展开判据 | 正确性不等于方法已确认；同一作答支持其他Task须独立核对其方法、判据、方面和来源，见Q02 |
| DM10 教学与追溯 | 取领域定义、方法分解及个人状态组织教学，沿实例引用追溯 | 取Task责任、Solution说明、相关KC与Task先导关系；按保留的原始内容追溯 | 浏览教材不限制聊天；四类活动规则不变；参考方法不等于学生真实执行路径；目标→Evidence→事件链不断 |
| DM11 工程登记与验证 | Operation、事件及验收实例仍使用模板／解法实例与递归合同 | 按新输入、产物和责任重写受影响合同，统一候选、正式内容、参考及通知含义 | 先核对提取、归类、供题及教材助手职责，不预设仍恰好9项；命名或拆并另列建议确认，不因改名新增Agent或工作流 |

继续保留的共同边界：Domain独立于教材；Task可以有多种方法；Claim只绑定一个明确Task，不新增KC Claim；个人判断由Evaluation维护；方法执行判据与四方面规则分开；目标可以要求各方法分别达标；事件只追加；AI候选不自行变成正式定义；答案和提示不能混入学生题面。

## 3. 已确认的处理方式

以下Q01—04按用户“改吧”及“直到修改完成”的授权执行。原问题与建议保留，便于核对本次取舍。

| 编号 | 具体问题 | 推荐的M1处理方式 | 未确认时影响什么 |
| --- | --- | --- | --- |
| Q01 具体解法保存 | 取消独立SolutionInstance后，教材原解、系统参考和后补解法放哪里？ | 在TaskInstance下维护多条参考解法内容，分别关联Solution并保留来源、必要图表和可追溯身份。仍可只选题目、不选解法；采用解法时先确定题目和方法。没有教材原解不补造。无需独立管理页面 | DM06—07；教材候选、入库、题库参考、事件引用和截图 |
| Q02 其他Task的Evidence | 没有方法调用树后，怎样确定某段作答还能更新哪个Task？ | 先评价当前Task；对明确的局部表现，在本次获准评价的已定义Task范围内提出匹配候选，逐一核对该Task的方法、判据和四方面资格。引用不明则不更新该项。不能沿先导边复制成功，也不能拿KC列表直接推断掌握 | DM09；评价详规、原型判据展示、学习机会取材和测试。取消树不能静默变成取消已有的明确证据联动能力 |
| Q03 先导关系维护 | 如何避免给所有方法强加同一前置条件，以及怎样处理旧关系？ | 在当前Task中选已有先导Task，记录理由和适用方法（全部或指定方法）；不把达标作为自动锁定学习入口的开关。检查自身引用和先导环，存在冲突先核对。旧KC先修与子调用只作为候选依据，不自动转换为新先导关系 | DM05；Task编辑、KC编辑、方法适用与教学选材 |
| Q04 归属与既有数据 | 不靠强参数表如何归类？现有mock是否全部重建？ | 归类核对责任、条件、所需表现和方法适用性；不能仅凭共用KC或文本相似。语义未变的对象尽量保留身份；现有具体题原则上保留一个明确Task归属，综合责任可建独立Task。旧公式、方法说明、题面和解法保留；不能确定的关系列为待核对。新演示数据与既有浏览器记录隔离，未经确认不清空或批量重挂 | DM01—03、DM08；保存与归类、示例加载、本地数据适配和历史追溯 |

一个需在Q02中明确检查的反例：学生先正确算出“增加量”，却把增加量当作最终量。当前综合任务可以出现负证；如果局部表现确实符合另一个已定义Task，则可为其形成正证。两者使用同一来源，不能算成两次独立练习，也不能因为没有旧调用树就全部忽略。

Solution里的关键过程说明只描述方法；判断学生是否掌握的正式判据仍由Evaluation维护。每个KC有直接检验路径，指任务责任明确覆盖该知识，不是任意Solution引用它就自动算覆盖。实际是否需要区分“核心／支撑知识”字段，留在领域交互方案中提出，不在本清单预设新字段或一对一约束。

## 4. 文档影响清单

“修改”表示已有内容直接受影响；“核对”表示检查后有冲突或引用变化才修改；“历史”表示保留原记录。下表版本是本稿读取的工作版本，不是已实施的新版本。每份实际修改的文档都升版，包括只修改导航或链接的文件。

### 4.1 通用模型与产品规格

| 文件及当前版本 | 处理 | 修改位置与重点 | 对应变更 |
| --- | --- | --- | --- |
| [Domain Space v1.5](../../../concept-design/DeerMind_Domain_Space_Design_v1.6.md) | 修改，模型定义主文件 | §2—6对象、角色、关系、实例与案例；§7—9引用、验证边界和替代记录；整段改写旧结构，不能仅追加例外 | DM01—06、DM08 |
| [Concept Architecture v1.5](../../../concept-design/DeerMind_Concept_Architecture_v1.6.md) | 修改 | Domain总览、对象图、Space关系及身份说明；清除现行摘要中的旧强制结构 | DM01—05、DM09 |
| [Learning Space v1.3](../../../concept-design/DeerMind_Learning_Space_Design_v1.4.md) | 修改 | 课程范围、章节选用、目标引用与知识汇总；不把先导闭包自动加入课程范围 | DM04—07、DM09 |
| [Evaluation v1.9](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.10.md) | 修改 | Claim绑定、方法依据、相关Task证据定位；保留四方面、资格、数值及目标判断职责 | DM01、DM03、DM09 |
| [Interaction v1.5](../../../concept-design/DeerMind_Interaction_Space_Design_v1.6.md) | 修改受影响合同 | 教学使用领域内容和先导关系的方式；不把Solution写成教学策略，不删除活动嵌套 | DM03、DM05、DM10 |
| [M1 PRD v0.24](../PRD.md) | 修改 | §2对象与流程图；R03—05解析／领域／目标，R07供题，R11—14教学评价及相应验收；检查追溯与权限引用 | DM01—10 |
| [Content v0.22](Content_and_Model_Reference.md) | 修改，M1详细语义主文件 | §1、§3.1—3.7准备与入库；§4.2、4.9、4.12—4.18方法／证据；§4.22—4.24追溯；§5逐章建模。公式、阈值不因模型改名重定 | DM01—10 |
| [Interaction Design v0.21](Interaction_Design.md) | 修改，与原型同批 | §1.1—1.5教材／领域／评价目标；§2—3受影响的学生示例和追溯；§4旧方案替代；替换实际变化的截图 | DM01—10 |
| [AI-Native原则 v0.6](../../../top/DeerMind_AI_Native_Architecture_Principles_v0.7.md) | 修改受影响引用 | 领域对象名称、候选与正式提交、方法取材示例；保留AI／程序权限分工 | DM01、DM03、DM11 |
| [路线图 v0.10](../../../top/DeerMind_Development_Roadmap_v0.11.md) | 修改受影响摘要 | M1整册建模对象和完成口径；不缩减为一章，不重开阶段划分 | DM01、DM06—08 |
| [学习模型重审 v0.7](../../../concept-design/DeerMind_Learning_Model_Reassessment.md) | 核对现行结论入口 | 只更新被当作当前结论的摘要／导航；保留历史分析，不重写早期讨论 | DM01—09 |
| [Evolution v1.5](../../../concept-design/DeerMind_Evolution_Space_Design_v1.6.md) | 核对交叉引用 | 如仍被当前架构引用，只纠正对象及边界引用；不新增M1演进、迁移或历史重算能力 | DM01、DM11 |

### 4.2 工程合同

| 文件及当前版本 | 处理 | 修改位置与重点 | 对应变更 |
| --- | --- | --- | --- |
| [Domain工程 v0.6](../engineering/Domain_Space_Design.md) | 修改 | §1对象；§2入库；§3—4任务／方法／依赖；§5归类与供题；§6内容保存与查询。以确认后的语义重写合同，不设计DDL | DM01—08、DM11 |
| [Product工程 v0.11](../engineering/Product_Application_Design.md) | 修改 | 教材Agent候选、采用与领域提交、解法归属、章节关联和课程应用 | DM06—08、DM11 |
| [Evaluation工程 v0.10](../engineering/Evaluation_Space_Design.md) | 修改 | §1定义维护、作答／学习机会取材及证据定位、参考原文查询和验收案例；保留确定性计算及发布边界 | DM03、DM06、DM09—11 |
| [Interaction工程 v0.12](../engineering/Interaction_Space_Design.md) | 修改受影响合同 | 学习助手取材、方法选择、检测准备、反馈及参考内容查询；取消对旧求解结构的假设 | DM03、DM05—06、DM08—11 |
| [总体设计 v0.36](../engineering/System_Design.md) | 修改 | 对象与所有权摘要；教材／供题／评价主流程图及其文字；引用和当前状态清单 | DM01—11 |
| [工程README v0.46](../engineering/README.md) | 修改 | §2—3输入和承接项；§5—7 AI Operation、事件与普通处理目录，登记已确认的名称和责任变化 | DM01、DM06—11 |
| [Client v0.11](../engineering/Client_Design.md) | 核对并按页面变化修改 | 管理员原型复用范围、候选与参考内容展示、字段／路由接入责任，不借机调整学生布局 | DM01、DM05—07 |
| [Delivery v0.27](../engineering/Delivery_Plan.md) | 修改 | 输入接收、领域／教材／评价实现依赖、资产复用、语义与工程测试的区别 | DM01—11 |
| [公共运行 v0.24](../engineering/System_Foundation_Design.md)／[AI底座 v0.13](../engineering/AI_Foundation_Design.md) | 核对，非默认重写 | 仅处理本轮改动的Operation、事件或内容引用示例；运行、工具、上下文和恢复职责不变 | DM11 |
| [基础设施 v0.18](../engineering/Infrastructure_and_Deployment_Design.md) | 核对，预计保留主体 | 如有旧对象或下游引用则同步；不因Domain调整改变存储、部署和组件选型 | DM11 |

Operation方面至少核对教材助手、`domain.extract_template`、`domain.classify_instance`、`domain.supply_task`、学习输入／检测准备、作答评价及学习机会解释。先写清各自的新输入与产物，再提出是否更名或合并；不能只把`template`字符串换成`task`。事件目录同步检查领域候选、入库、供题、定义变更与引用事实，生产方和消费方必须对应；本批不展开协议字段。

### 4.3 验证、导航与历史

| 文件或资产 | 处理 |
| --- | --- |
| [Validation Plan v0.5](../validation/Validation_Plan.md) | 修改领域补建、解法参考、归类、相关Task证据与整册建模验收；概率算例不凭名称变化重算；区分mock行为、语义质量与真实效果 |
| [验证README v0.7](../validation/README.md) | 更新未来验证入口和旧结果适用范围；未复验不能标记已通过 |
| [概念入口 v0.10](../../../concept-design/README.md)、[系统入口 v0.35](../../../system-design/README.md) | 指向修订后的现行模型与M1合同，保留历史基线说明；顺带消除这条引用链中的文件名／显示版本不一致 |
| [MVP入口 v0.62](../../README.md)、[M1入口 v0.41](../README.md)、[设计入口 v0.40](README.md)、[原型入口 v0.7](../prototype/README.md) | 同步工作包、交付状态、图文入口及已知差距；只报告本轮实际完成的内容 |
| [DECISIONS v0.63](../../DECISIONS.md) | 新增本次决定、旧新版本、实际改动与检查结果；明确替代§19的结构约束和§20涉及的递归取材表述，保留公式等未变决定及历史过程 |
| [M2入口](../../m2/README.md)、[M3入口](../../m3/README.md)、[产品宪章](../../../top/DeerMind_Product_Constitution_v1.0.md)、[产品主张](../../../top/DeerMind_Product_Thesis_v1.0.md)及写作规范 | 核对引用；当前未发现需要改变其产品目标、阶段范围或规范的理由，不默认升版 |
| [内容表达试验 v0.2](../validation/Content_Representation_Trial.md)、旧概念版本、`doc/mvp/archive/`、旧System／Spike／Build报告 | 历史：保持原实验输入、结论和引用。通过当前入口说明新模型需重新核对，不能反写报告 |
| [四例提取试验资产](../../../../src/mvp_foundation/m1/content-representation/round2/) | 当前试验保留。若后续复用，单独适配候选表达、`catalog.json`、`mapping-schema.json`、`extract-rules.txt`、`map-rules.txt`；不覆盖`runs/`及其输入快照，不在原型修改阶段调用LLM重跑 |
| `design/assets/`中的截图、关系图和采集清单 | 新版截图另存一批并更新现行引用；历史批次不覆盖，不把旧图冒充新模型截图 |

## 5. 原型修改清单

实际原型根目录为[prototype](../prototype/)。下表是入口级影响清单；实施前按导入关系补齐辅助文件，并把新增影响登记回来。本轮仅按已批准模型调整相关操作，保留既有布局，不重做无关页面。

| 编号 | 页面与主要文件 | 拟调整内容 | 必须保留／核对 |
| --- | --- | --- | --- |
| UI01 领域／Task | [DomainWorkspace](../prototype/src/components/domain/DomainWorkspace.vue)、[TaskWorkspace](../prototype/src/components/domain/TaskWorkspace.vue)、[domain.ts](../prototype/src/model/domain.ts) | 名称、任务责任与范围；取消参数表强制要求；增加Task先导维护 | 原有分项编辑、列表和领域隔离；禁止靠改标签保留旧必填校验 |
| UI02 Solution／KC | [MethodWorkspace](../prototype/src/components/domain/MethodWorkspace.vue)、[KnowledgeWorkspace](../prototype/src/components/domain/KnowledgeWorkspace.vue) | 方法说明、多KC关联；取消子调用图编辑与KC先修维护，改为查看相关Task | 方法条件、有效说明、KC定义和图表；先导关系在Task维护 |
| UI03 题目与参考 | [TaskInstances](../prototype/src/components/domain/TaskInstances.vue)、[domain.ts](../prototype/src/model/domain.ts) | 归属Task、参考解法及Solution关联、来源展示 | 原题图表与讲解辅助材料分开；独立解法对象简化不丢原文 |
| UI04 教材助手／待入库 | [MaterialAssistant](../prototype/src/components/MaterialAssistant.vue)、[DomainIntake](../prototype/src/components/domain/DomainIntake.vue)、[material-assistant.ts](../prototype/src/model/material-assistant.ts)、[intake-actions.ts](../prototype/src/model/intake-actions.ts)、[material-flow.ts](../prototype/src/model/material-flow.ts) | 候选称谓、具体解法依附题目、提取定义／关联／保存后的反馈；核对[review-content](../prototype/src/model/review-content.ts)与教材fixture | 持续对话纠错、题目／解法分选、仅题入库、后补解法、来源与候选采用；不恢复手工解析编辑器 |
| UI05 章节采用 | [MaterialIntegrationWorkspace](../prototype/src/components/MaterialIntegrationWorkspace.vue)、[material-integration.ts](../prototype/src/model/material-integration.ts)、[textbook.ts](../prototype/src/model/textbook.ts) | 采用Task／Solution，按所选方法直接汇总KC | 添加、编辑、取消关联既有操作；先导Task及其方法不自动进入课程 |
| UI06 Claim／目标 | [EvaluationWorkspace](../prototype/src/components/EvaluationWorkspace.vue)、[ClaimCriteriaPanel](../prototype/src/components/ClaimCriteriaPanel.vue)、[MethodStandards](../prototype/src/components/MethodStandards.vue)、原`MethodCriteriaTree.vue`（本轮删除，历史由Git追溯）、[TargetWorkspace](../prototype/src/components/TargetWorkspace.vue)、[evaluation.ts](../prototype/src/model/evaluation.ts) | 移除旧`methodTree`驱动的递归判据和就绪校验；按当前方法维护本任务判据与四方面规则；目标范围适配 | 方法tab、判据独立维护、方法分别达标；不能把先导Task判据当成本Task必须继承的判据 |
| UI07 学习与追溯 | [StudentSpace](../prototype/src/student/StudentSpace.vue)、[quarter.ts](../prototype/src/student/quarter.ts)、[LessonMessage](../prototype/src/student/LessonMessage.vue)、[LearningSpaceWorkspace](../prototype/src/components/LearningSpaceWorkspace.vue)、[learning-spaces.ts](../prototype/src/model/learning-spaces.ts) | 只改受影响的任务／参考引用、mock内容、证据归因和说明；检查活动fixture引用 | 聊天＋教材单页、活动目录、书页独立浏览、检测求助边界、Evidence→事件追溯 |
| UI08 示例与资产加载 | [domain-example](../prototype/src/model/domain-example.ts)、[domain-complex-examples](../prototype/src/model/domain-complex-examples.ts)、[method-flow-examples](../prototype/src/model/method-flow-examples.ts)、[evaluation-example](../prototype/src/model/evaluation-example.ts)、[review-fixtures](../prototype/src/model/review-fixtures.ts)及相关fixture | 用新定义重组现有示例；旧浏览器数据按Q04处理；检查加载器和派生结果 | 不删除已有用户mock；初中／高中／K8s仅作表达检查，不增加正式课程验收范围 |

当前`package.json`区分10个默认测试文件和5个历史导入UI测试文件，另有未接入默认命令的测试。实施时逐个确认用途：新模型约束要改期望，仍有效的行为保留；已被替代的历史测试明确标记用途，不能全部删除或只运行默认命令就宣布全覆盖。

优先核对[domain.test](../prototype/tests/domain.test.mjs)、[task-template.test](../prototype/tests/task-template.test.mjs)、[solution-template.test](../prototype/tests/solution-template.test.mjs)、[evaluation-target.test](../prototype/tests/evaluation-target.test.mjs)、[material-flow.test](../prototype/tests/material-flow.test.mjs)、[material-assistant.test](../prototype/tests/material-assistant.test.mjs)、[intake-dialog.test](../prototype/tests/intake-dialog.test.mjs)、[learning-spaces.test](../prototype/tests/learning-spaces.test.mjs)。学生相关测试按实际受影响行为选择，不为纯文案逐条新增镜像测试。

## 6. 实施顺序与每批交付

B00—B05的作者实施与检查已完成；用户最终审阅尚未进行。每批修改自身涉及的PRD、详规、工程合同和原型，不等所有文档写完才检查页面。前一批语义变化传到后一批；发现新问题先补入清单和决定，再继续受影响工作。

| 批次 | 要做什么 | 交付物与退出条件 |
| --- | --- | --- |
| B00 评估与确认 | 审阅DM01—11、Q01—04、文件范围及测试计划 | 本清单；明确采用和修改意见；执行前固定包含未提交修改的基线 |
| B01 新模型与领域管理 | 更新权威Domain定义和直接相关上位摘要；M1规格、领域原型与Domain工程合同互相核对 | Task／Solution／KC／题目／先导关系可浏览可维护；“d=v×t”示例和受影响截图；RV01、02、05通过作者检查 |
| B02 教材到课程 | 调整具体解法候选、领域待办、题目参考和章节采用；同步Product及供题相关合同 | 仅题、后补解法、多方法、章节裁剪闭环；相应PRD、详规和截图；RV03、04、07通过作者检查 |
| B03 教学与评价使用 | 调整判据、目标、相关Task取证及教学取材；同步Interaction／Evaluation合同和原型引用 | 四分之一双方法与综合任务正反例；Evidence追溯可读；RV06、08、09通过作者检查，原数值规则不变 |
| B04 工程总览与资产收束 | 核对总体图、Operation／普通处理／事件目录、客户端、验证和实施计划；更新导航 | 每条变化有权威定义、使用方和检查项；没有孤立的事件、旧调用树假设或现行引用断链；不展开新增接口字段或实现后端 |
| B05 整体审阅 | 使用完整主流程、已有数据和反例复核全部变更；用户浏览原型审阅 | 逐文件旧新版本及实际检查记录；RV10、11通过作者检查；未决项如实列出，用户审阅前不标整体完成 |

各批完成后报告三件事：本批实际交付及浏览入口、整体完成到哪一批、下一批做什么及是否被待决问题阻塞。按实际工作量推进，不预填日期或测试结果。

## 7. 接收场景与防遗漏检查

以下为本轮接收要求；已执行检查及其边界见§8，不将语义推演写成真实模型测试通过。浏览器与mock检查只能证明表达和交互逻辑，不证明真实LLM效果。模型简化不能降低教材完整性、证据来源或方法识别要求。

| 编号 | 场景 | 应看到的结果 | 覆盖 |
| --- | --- | --- | --- |
| RV01 基本对象 | 建立“解释d=v×t”、两种方法及相关KC | 关系知识有自己的KC；两法关联多个KC；Task责任与Evaluation判据分清；无需递归调用树 | DM01—04 |
| RV02 先导差异 | A依靠乘法意义，B依靠乘除关系；学生选择A | B特有先导不强加给A；未知先导不冒充已掌握；不自动更新概率；先导冲突能被发现 | DM05、DM09—10 |
| RV03 教材例题 | 只入题、随后补教材原解，再追加系统参考 | 同一题目下来源分明、方法可定位；后补参考不改变原题面，不重复创建题目 | DM06—07 |
| RV04 公式和图表 | 复用四例C02／C03／C05／C06的已有材料，检查题面图表和解释辅助图 | 原始信息与归属保持；没有解法的练习不伪造解法；原题辨错内容不被“修正”掉 | DM06—08 |
| RV05 表达与归属 | 更换数字／情境；另加入追及或其他新责任 | 前者可保持Task归属；后者须核对是否仍在范围，不能因同样使用d=v×t直接通过；保留综合Task的独立责任 | DM02、DM08 |
| RV06 两种方法 | 四分之一任务要求A、B分别达标，学生只展示A | A有依据才更新；B保持原状态；不能用两法共用KC宣布B达标 | DM03—04、DM09 |
| RV07 章节范围与供题 | 领域有A、B，章节只采用A；库存不足 | 课程KC按A汇总；供题按Task和允许方法生成、检查、保存再用；仅已生成不算合格 | DM04、DM07—08 |
| RV08 局部与整体证据 | 增加量算对、最终量答错；对照只有最终答案的情况 | 明确局部可形成其Task证据，整体独立判断；仅答案不虚构方法；同一来源不重复计数 | DM09 |
| RV09 新方法与追溯 | 学生采用未收录但可能正确的方法；管理员查看依据 | 不因不匹配参考方法直接判错；无法归因的分项保留未决；目标→Evidence→原事件／题面／帮助原文可追溯 | DM06、DM09—10 |
| RV10 既有记录 | 装载旧mock与本次新示例，刷新并打开历史记录 | 不清空、不错误重挂、不用新生成解法替换当时依据；不能转换的内容有明确处理结果 | DM01、DM06、DM11 |
| RV11 文档闭环 | 从整册准备走到学生作答、评价和下一步；反向核对定义及截图 | 本轮旧约束不再作为当前要求；图文、例子、Operation和事件的责任一致；历史引用与现行合同可区分 | DM01—11 |

最后收尾使用三种检查，不以某一种代替全部：

1. **语义核对。** 按DM编号追踪权威定义→PRD／详规→页面→工程合同→验收；每项有修改或保留理由。扫描旧术语只是找线索，活动递归、执行Step和历史内容不能误删。
2. **资产核对。** 运行实际受影响的类型／构建与行为检查，浏览相关页面，渲染修改的Mermaid图，更新真实截图和采集清单；语义试验在后续验证阶段单独记录。
3. **版本核对。** 每个修改文件升版；带版本文件名同步名称与现行引用；在DECISIONS登记替代条款、旧新版本、检查结果和剩余问题。历史文件及实验输入保持原义，不追加伪造通过记录。

## 8. 本轮交付与检查记录

本轮更新权威Domain定义、关联概念摘要、M1 PRD／内容／交互规格、原型及受影响工程合同。执行前保存了包含14份既有未提交修改的工作副本；没有以HEAD覆盖先前Operation修订。历史实验、旧原型和用户浏览器记录没有清空或重写。

- 模型与页面：Task认知责任、可选参数、按方法适用的先导；Solution方法说明与多KC；题目内多条参考解法；Claim按当前方法维护，不再继承子方法判据。
- 教材到课程：对话与候选采用保留；仅题先入库、后补参考；归属不明阻止关联；章节按所选方法汇总KC；跨章节方法取并集并标明来源。
- 工程：定义提取、语义归类和供题职责已适配。保留9项AI Operation及既有技术标识；具体字段迁移和真实质量检查继续属于详细设计，不另定接口或实现后端。
- 数值与历史：BKT公式、参数及0.90阈值未变；新目标示例清除早期两题门槛，既有记录不覆盖。明确表现可以支持其他Task，但须独立取证。旧子调用和KC先修不自动变成Task先导，不从新模型重挂历史证据。

| 接收项 | 本轮核对方式与限制 |
| --- | --- |
| RV01／02／05 | d=v×t独立mock、手动维护、可选参数、方法限定先导、自引用／循环拦截；归属匹配／不匹配／待确认分支。只验证交互与确定性约束，不证明AI分类准确率 |
| RV03／04／07 | 四例原材料、仅题入库、后补两法、图表和辨错原文保留、章节增改取消与方法范围；跨章方法并集与KC直接汇总。真实供题仍按合同验证 |
| RV06／08／09 | 双方法判据与目标覆盖测试、来源Evidence追溯；内容§4.15／4.17逐项核对局部正证与整体负证、未识别方法不推断掌握。其他Task语义归因是文档走查，未接入自动Evidence提取 |
| RV10 | 旧存储身份、混合旧判据、新示例隔离和刷新检查；旧不明关系提示核对。没有实现生产迁移或历史重算 |
| RV11 | 本轮改动文件、版本、有效链接、Mermaid及截图逐项检查；结果与文件哈希见下方复核记录 |

实际测试、截图和版本清单分别见[复核记录](assets/domain-model-v0.1/review.json)、[截图清单](assets/domain-model-v0.1/capture-manifest.json)及[逐文件版本](assets/domain-model-v0.1/document-versions.json)。结果只代表本轮mock与文档检查；没有调用LLM、运行真实教学或重新校准概率。

| 版本 | 日期 | 本次交付与边界 |
| --- | --- | --- |
| v0.1 | 2026-11-14 | 建立DM01—11、Q01—04、文件／原型清单、B00—B05及RV01—11；仅新增清单 |
| v0.2 | 2026-11-14 | 按批准范围实施并记录作者复核；新旧语义及历史资产边界明确，待用户最终审阅 |
