# M1 Domain Space 设计

> **版本**：v0.7<br>
> **状态**：本轮领域模型、原型及关联合同已修订，待用户审阅；真实服务与效果未验证<br>
> **维护与评审**：Codex编写及自检，用户审阅<br>
> **写作规范**：[系统设计写作规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-14<br>
> **修订说明**：v0.6 → v0.7，同步Task／Solution新定义、多KC方法、Task先导、题内参考及相关Task独立取证；保持既定数值规则和工程边界；逐文件记录见MVP决定登记§68<br>

本文维护可复用领域内容及其业务操作，不保存学生作答、个人接触史或 Belief。依据为 [PRD R04](../PRD.md#34-维护领域处理入库并关联章节m1-r04)、[R07](../PRD.md#37-准备题目和参考m1-r07)与[内容规格§3.2–3.3](../design/Content_and_Model_Reference.md#32-领域对象与字段)；共同输入见[工程入口§2](README.md#2-设计输入与历史参考)。

入库受理和供题按Domain自己的业务合同执行并发布事实事件，公开结果保留来源引用。Product或Interaction是否等待、采用什么期限，不改变Domain的处理义务和执行预算；它们结束等待不自动取消Domain任务。消费方通过底座订阅匹配及处理自己的超时，见[总体§7.2.1三](System_Design.md#721-已确认的总体选择)。

## 1. 领域对象、身份与关系

### 1.1 公共输入与引用

本Space的AI Operation为定义提取、实例语义归类和智能供题；定义维护、入库受理／提交、实例保存及只读查询是普通业务。共用执行边界见[公共运行§1.3](System_Foundation_Design.md#13-operationstep与operationrun)。普通处理可安排AI归类，但保存本身不成为Operation；本文件不将Solution求解步骤称为运行Step。既有字段仍为待审合同，本轮不新增接口Schema。

| 字段／类型 | 含义与校验 |
| --- | --- |
| `access_context`／程序授权上下文 | 各操作共同输入；程序授予领域读取、维护或供题权限，模型输出不能授权 |
| `request_id`／非空标识 | 直接请求输入；同次重试沿用。事件受理改用 `trigger_event_id`，写入去重遵循公共合同 |
| `scope_id`／资源身份 | 领域维护采用 Domain；教材请求采用导入资源；学习供题采用学习空间。新 Domain 创建采用调用者账户身份 |
| `object_ref`／对象引用 | `{domain_id, kind, id}`，`kind` 为 Domain、Task、Solution、KC、TaskInstance ；题内参考解法通过TaskInstance的内容引用定位；ID 由程序分配 |
| `content_ref`／不可变内容引用 | 固定本次读取、生成或展示所依据的内容；后续修改不覆盖已引用题面，不引入跨版本迁移 |
| `expected_revision`／可选并发令牌 | 更新已有对象必填；仅用于防止覆盖并发修改，不代表 Evolution 版本管理 |
| `source_refs[]`／来源引用 | 引用已采用教材候选及页位置、管理员输入或系统生成记录；来源方维护原件，不把教材来源当成定义身份 |

### 1.2 对象载荷与就绪检查

`definition`、`instance` 为按对象类型校验的结构；名称和领域归属不可为空。草稿可缺内容，返回 `gaps[]`；不存在的引用、越域关联及依赖环返回错误，不写入。正式使用必须核对当前Task、采用方法及直接KC的完整性；先导缺口供教学安排参考，不扩充使用范围或自动锁定学习入口，不能只读取对象自身的“已保存”标记。

| 类型 | 操作接收的业务字段 | 引用与缺口 |
| --- | --- | --- |
| Domain | `name, coverage, description` | 创建后为空，不复制其他领域；`coverage`、`description` 草稿可空 |
| Task | 名称、认知责任、交付与完成条件、适用条件、边界、方法及先导 | 参数与变化结构可选；不保存结构角色或Task→KC引用 |
| Solution | 名称、方法思路与依据、适用条件、关键过程、直接KC | 可关联多个KC；不要求子调用图或输入输出绑定 |
| KC | 名称、含义、条件、正反例及必要语义呈现 | 正式使用前须有责任明确的直接检验Task及Solution；仅被引用不算完成检验路径 |
| TaskInstance | 题面、主要Task、来源、语义呈现、参考答案或评分依据、参考解法内容 | 一题一个主要归属；参考解法可多条、可后补，来源和内容身份保留，不独立管理题内参考解法 |

旧`task_template_ref`等接口草案字段对应Task；旧实例／参考引用保留可追溯身份。精确字段更名、兼容读写和协议序列化在第二层确认，不以本轮名称统一擅自确定接口迁移机制。

`representation` 承载所属元素的公式、表格、图形语义及必要呈现信息；题面与参考解法分开读取。详细多模态结构和检查器待结合已保存解析试验确定，本轮不把截图或文字摘要当作完整替代。

载荷中名称、含义和说明是文本，`*_refs[]` 是引用数组，可选变量信息只在具体任务需要时采用，`completion` 是交付内容与检查条件对象。`gaps[]/issues[]` 均为 `{code,path,message}` 数组，`path` 定位缺口位置。`classification_check_ref` 固定实例内容、定义内容及归类结论；`availability` 含 `check_status=not_checked|passed|failed`、`checked_purposes[]` 和问题引用，不能用一个保存成功标记代替。`use_check_ref` 另固定本次供题输入与用途检查，不能替代长期公共可用性记录。

## 2. 定义维护与教材内容入库

### 2.1 `domain.save_definition`

**触发与输入。** 管理员新建／编辑或确认定义候选；需要领域维护权限。输入 `object_kind`（Domain／Task／Solution／KC）、`action=create|update`、`definition`、可选 `object_ref, expected_revision, candidate_ref, source_refs[]`；更新必须给对象与并发令牌，确认提取结果给 `candidate_ref`。

1. 校验权限、输入类型及当前引用；新建分配身份，更新读取当前令牌。
2. 按§1、§3、§4检查任务责任、引用和先导，缺少尚未建立的内容记入 `gaps[]`；不自动创建所依赖KC、方法或先导Task。
3. 在一次短事务中保存定义内容、来源关系、并发令牌及 `DomainDefinitionSaved` 事件，返回 `object_ref, content_ref, revision, gaps[]`。

同请求返回原结果；并发不一致返回 `revision_conflict`，非法引用／环返回 `invalid_reference|dependency_cycle`。提交失败整体回滚；此操作不拆持久 Step。**验收例：** 保存缺方法的Task返回草稿缺口；方法可直接关联多个KC；Task直接挂KC或先导循环须拒绝。

### 2.2 `domain.receive_intake`

**触发与输入。** 教材业务提交 `DomainIntakeRequested` 后异步调用；服务身份需有向目标领域提交内容的权限。输入 `trigger_event_id, domain_id, intake_request_id, candidate_refs[]`。经教材公开接口读取每项的 `知识／题目／题内参考解法类型, content_ref, source_refs[]`；解法另有 `parent_candidate_ref` 或已入库 `task_instance_ref`。

1. 校验请求事件和资源范围，读取教材业务已采用且当前仍有效的不可变候选；未采用或已过时来源不进入待办。
2. 按题目与其解法建立 `group_ref`，KC 独立成组；解法父题可在本批、已有待办或已入库记录中，无法定位则返回 `missing_parent`。
3. 同次提交保存整批待办与 `DomainIntakeReceived`，发布 `producer=domain, result_kind=intake_receipt`。回执为 `intake_request_id, items[{candidate_ref,intake_item_ref,group_ref,state}]`；这里只接收，不创建定义、实例或章节关联。

事件重复沿用原受理记录；同领域、同已采用候选已有有效待办／入库结果时回传已有映射，避免重复排队。读取来源故障保留受理记录重试，不产生半批回执。**验收例：** 只提交题目可进入待办；另提交解法时可定位此前题目，不要求一起导入。

同操作接收 `MaterialCandidatesAdopted|MaterialImportDeleted` 的来源失效分支：输入为事件中的导入身份、被替代／删除的来源及受影响提交引用。只将未入库行标为 `source_invalid` 并追加 `DomainIntakeSourceInvalidated`，不覆盖已入库对象；不发布新的 `intake_receipt`。处理待办前仍查询教材公开有效性，不能依靠通知恰好先到。

### 2.3 `domain.process_intake`

**触发与输入。** 管理员点击待办行按钮；需要领域维护权限。输入 `intake_item_ref, expected_revision, action` 和下表分支参数。

| `action` | 参数与处理 | 输出 |
| --- | --- | --- |
| `add_kc` | 新建时 `definition`；复用时 `existing_kc_ref`，二者恰一。复用只核对含义和记录来源，不覆盖定义 | `object_ref` 与 `state=added` |
| `associate_task` | `task_template_ref`；用已采用题目调用§5.1的归类及保存逻辑 | `task_instance_ref` 与 `state=associated` |
| `associate_solution` | `solution_template_ref, task_instance_ref, confirm_add_method`；先校验父题对应，方法不在父题 Task 中时必须明确确认补引用 | 题目引用、题内参考内容引用与 `state=associated` |
| `discard` | `confirm_child_discard`：取消未入库父题且存在待处理解法时必填 `true` | `state=discarded` 与 `affected_item_refs[]` |

每行处理先核对来源仍有效；`source_invalid` 返回 `source_unavailable`，不能继续新增模型。需要AI归类时安排§5.3的归类Operation，取得检查结论后继续普通保存；提交时再核对来源有效性和并发令牌，在短事务内同时保存对象／引用、待办结果、来源映射和 `DomainIntakeItemProcessed`；需补 Task→Solution 引用则一并提交。结果含 `group_pending_count`；整组无未完成项后不再列待办，追溯记录保留。取消待办不删除教材和已入库对象。

缺父题、需要确认补方法、语义无法确认分别返回 `parent_not_linked|confirmation_required|classification_unresolved`，不改待办。已处理项的同请求返回原结果，另请求改变处理结果返回 `already_processed`。**验收例：** 提取定义后题目仍待关联；解法关联失败不撤销此前成功入库的题目。引用和提交校验复用内部函数；语义归类单独归AI能力，重试复用其有效检查产物，不重复生成同一结果。

## 3. 任务的结构化表达

### 3.1 可检查的任务定义

Task必须描述责任、交付表现、完成条件、适用条件和边界。参数表可选；存在公式、单位或结构化变量时进行相应校验，不要求每类任务先参数化。

生成和反向归类使用同一责任边界：核对所需表现、条件及方法适用性，不仅比较题干、公式或KC重叠。新数字可以保持归属；新认知责任不能硬塞原Task。未知或冲突保留未决。Task完成条件不是个人目标达标规则。

### 3.2 `domain.extract_template`

本轮保留已登记的Operation标识，不新增或拆分AI能力。这里的template沿用旧技术命名，产物语义是Task或Solution定义候选；不是强制参数定义或运行流程。后续如更名须同步目录与调用方。

**触发与输入。** 管理员在题目／解法待办点击提取；需要领域维护权限。输入 `intake_item_ref, template_kind=task|solution, extraction_instruction`（可空）、可选 `prior_candidate_ref`。源元素类型必须相符，内容取当前已采用引用。

| 持久 Step | 输入与执行 | 保存产物与停止条件 |
| --- | --- | --- |
| `prepare_template_input` | 固定候选内容、来源、现有定义查询结果及用户要求 | `extraction_input_ref`；源不存在或权限不符即停止 |
| `derive_template_candidate` | 经 AI 底座提取可复用任务责任或方法依据、条件与关键过程；参数按需保留；只允许读取本领域内容 | `candidate_ref`，载荷为§1定义字段、依据与 `unresolved[]`；不允许模型写模型库或编造已存在对象身份 |
| `check_template_candidate` | 检查结构、引用与来源支撑；不能确认的依赖保留为建议 | `check_ref, issues[]`；不自动补建其他模型元素 |

受理返回 `operation_run_id`，通过公共 `read_operation_run` 读取状态及最终 `candidate_ref, check_ref, proposed_definition, issues[]`，追加 `DomainTemplateCandidatePrepared`。候选需管理员确认后调用 `domain.save_definition` 才成为定义，实例仍待关联。技术重试复用已完成产物；重新提出不同要求是新请求，保留前候选引用。**验收例：** 从例题具体解法提出Solution候选，不同时创建其他定义或修改题目参考；缺知识依据或方法条件时显示缺口。

## 4. 方法知识与Task先导

### 4.1 直接知识与先导的不同用途

Solution直接关联多个KC。Task知识是其直接方法的KC并集；章节知识只汇总章节采用的方法。不沿先导继续汇总，不维持另一套KC先修图，不要求可执行的递归方法分解。

Task先导记录已有Task、理由和适用方法（全部或指定）。保存检查同领域引用、自引用、重复和循环；用于教学回补，不锁定学习入口，不直接传播概率。旧方法调用或KC先修不会自动转换为新先导。综合Task仍有自己的组织、选择和结果检查责任。

### 4.2 `domain.query_dependencies`

这是普通授权只读查询。调用方指定Task及需要的方法范围；Domain返回当前Task的直接方法、按方法标明来源的KC集合、适用先导及缺口。知识汇总与先导列表分开返回，后者不扩充章节采用或正式评价范围。

校验方法确属Task，按KC身份去重；缺引用和先导环明确报告，不裁掉问题伪造完整结果。不根据定义推断学生实际方法或更新Belief。具体字段在详细设计确认。

**验收例：** 方法A用乘法意义，B用乘除互逆；查询A只返回A的KC及适用先导，不把B特有要求或先导的全部知识算进去。

## 5. 题目与解法供给

### 5.1 `domain.save_instance`

**触发与输入。** 管理员从任务维护题目／解法，或明确关联教材实例；需要领域维护权限。输入保存动作、TaskInstance及要新增或修改的题内参考内容；题内参考不再使用独立实例类型，具体载荷在详细设计确认；更新另给 `object_ref, expected_revision`。`instance` 字段见§1.2；可选 `classification_check_ref` 仅能复用针对同内容和同定义的检查结果。

1. 固定题目／解法及定义内容；校验题面必要条件、图表、实际变量与单位（适用时）、Task 责任及边界。解法还检查所属题目、Solution 及 Task 的直接方法引用。
2. 反向归类得到 `matched|unresolved|mismatch`；后两者分别返回 `classification_unresolved|classification_failed`，保留候选不创建已关联实例。参考答案／用途未核对可保存为 `not_checked`，但不能供正式检测。
3. 一次短事务保存实例、检查引用、来源及 `DomainInstanceSaved`，返回 `instance_ref, content_ref, classification_check_ref, availability, gaps[]`；更新后原已引用内容仍可读取。

`save_instance`是普通保存处理。需要语义归类时安排§5.3的AI Operation；取得结论后，程序核对内容、定义及引用仍与检查时一致，再进入保存事务。不增加用户操作：同一保存请求可经历归类等待和提交两个部分。归类已通过但保存失败时复用有效产物，不重新调用模型；内容或定义已变须重新检查。纯引用与字段更新不建OperationRun，同请求不重复建实例。**验收例：** 有表格但漏单位的题不能通过可用检查；教材没有解法仍可保存已归类TI，不伪造教材原解。

### 5.2 `domain.supply_task`

**触发与输入。** Interaction 提交 `TaskSupplyRequested`，Domain 异步受理；需要本次学习空间的供题权限。输入 `trigger_event_id, domain_id, purpose=example|practice|assessment, task_ref, allowed_method_refs[], assessment_constraints, method_source_refs[], exposure_refs[], count`。`count` 为正整数；课程方法来源引用、目标条件和个人已见题面／解法／帮助的记录由调用方提供，Domain 不读个人私有表。

**供题职责。** `domain.supply_task`是按本次用途、方法、条件和接触史裁决适用实例的唯一入口；无论库存是否充足均走本流程。`query_content`只浏览或读取指定内容，不承担第二套供题筛选。Interaction负责题单安排及使用前条件复核，不重复实现`select_instances`。

`assessment_constraints` 包含本次参数范围、拟检查方面与表征／时间条件；空对象表示无额外条件，不能表示已满足所有方面。供题不证明保持已达标；实际间隔及 Evidence 资格由 Interaction／Evaluation 判断。`exposure_refs=[]` 只表示调用方确认无相关经历；来源未知须显式返回缺口，不能据此声称新题。

| 持久 Step | 执行与分支 | 可恢复产物 |
| --- | --- | --- |
| `prepare_supply` | 固定定义、允许方法及调用方条件；核对定义就绪、方法来源与用途 | `supply_input_ref`；无方法或非法范围时返回明确缺口 |
| `select_instances` | 查询已核对实例，逐题按当前用途和提供的接触史筛选，去除重复 | `selection_ref`；够数直接进入批次提交，不调用生成 |
| `generate_candidates` | 不足部分经 AI 底座按固定定义生成题目和必要解法参考；读取权限限本次材料 | `candidate_batch_ref`；不可扩大定义或通过读 Belief 改写题意 |
| `check_candidates` | 检查题意／图表、参数、答案、范围、归类及本次用途；失败候选隔离 | `check_batch_ref`；有合格替代继续，预算内仍无题则记录 `unfilled[]` |
| `commit_supply` | 将合格新实例、参考与检查保存，再提交供题批次；已有实例直接引用 | `supply_batch_ref`；本步失败从已有候选恢复，不重新生成已通过题 |

生成输出为§1.2的 题目及其参考解法候选、适用条件，参考解法、提示和题面分开。程序校验结构与引用，语义检查记录所用模型／规则及理由；检查无法确认不作通过。模型超时、格式错误走有界技术重试；合法但无合格题是业务结果，不无限换题。

提交保存 `DomainTaskSupplyCompleted`，按请求事件发布 `producer=domain,result_kind=task_supply`。载荷为 `supply_batch_ref, items[{task_instance_ref,content_ref,reference_solution_refs[],matched_method_refs[],use_check_ref}], unfilled[{condition,reason}]`；无合格题时记录空批及原因，作为本次供题事实发布；不因消费方等待到期提前伪造空批。检查通过、保存成功后方可交付，无须管理员逐题批准。

成功结果同键只发布一次；重试不追加第二批实例。Interaction取回后核对活动仍有效、条件未变及题面是否刚被展示，保存计划并返回题单摘要。学生确认当前计划后，Interaction才建立首轮及出题事件；题目就绪或晚到都不自动开始检测。**验收例：** 现有题都展示过答案时生成新题；生成检查失败且无替代时返回缺口，不能把旧题当新独立证据。

### 5.3 `domain.classify_instance`

这项AI能力承接原`save_instance`中的语义归类步骤，用于判断具体题目或解法是否符合所选定义。由需要语义检查的入库／保存流程安排，读取获授权的实例内容、定义及必要关联，返回匹配依据、不匹配或无法确认的原因；程序负责引用、结构及有效性检查。归类不等于保存成功，不直接建立正式实例或修改定义。

归类产物保留实际内容和定义依据，只有仍适用于当前保存请求时才可复用。其AI处理函数也可作为供题Operation内部步骤使用，不强制每次内部复用都新建OperationRun。输入输出字段、运行拆分和回传接线留待详细设计。

## 6. 持久化、公开接口与并发修改

### 6.1 `domain.query_content`

调用范围按[总体§6.6.1](System_Design.md#661-最小调用授权矩阵)核对。Evaluation可按已授权事件关联读取固定定义、实例和参考解法；学生查询仍受题面／答案展示权限限制。Domain不因内部调用便开放所有内容，也不为供题读取整段私人对话。

**触发与输入。** 管理员列表／详情、教材选关联、Interaction浏览／读取既定题目和Evaluation读取参考；需要相应内容读取权限。输入 `domain_id, kinds[], filters, cursor, limit`，或 `object_ref/content_ref` 精确读取；`cursor` 可空，`limit` 为受服务上限约束的正整数。候选和待办查询还需该来源处理权限。

`filters` 仅接受名称、对象类型、关联 Task／方法和可用性等注册字段；不接受个人能力条件。输出 `items[], next_cursor, read_token` 或对象内容、来源与 `gaps[]`；`next_cursor=null` 表示当前读取范围结束。分页按稳定对象身份排序，游标固定本次读取范围；修改后需刷新，不混拼两个读取结果。

实例按 `view=statement|reference|full` 返回；学生题面只允许 `statement`，解法和教学辅助内容不能混入。原始参考由获授权的 Interaction／Evaluation 读取，是否向学生展示由活动规则控制。不存在、越权、故障分别返回 `not_found|forbidden|temporarily_unavailable`；查询无业务事件、不触发提取／生成／检查。**验收例：** 查询题面不会附带其参考解法；换领域不能读到另一领域的候选。

### 6.2 提交边界与保存记录

| Domain 记录 | 保存内容与唯一约束 |
| --- | --- |
| 定义与内容 | 对象身份、当前内容引用、并发令牌、缺口；不可变内容供历史引用，不在M1建设演进平台 |
| 定义与实例关系 | Task→Solution；Solution→多个KC；Task→有理由与方法条件的先导Task；题目→Task，题内参考→Solution；禁止非法跨域引用 |
| 入库及来源 | 已采用候选、处理组、行状态、结果引用、取消原因；同候选重放回传已有有效结果 |
| 生成与检查产物 | 输入内容引用、模型／规则来源、候选、检查结果、失败理由；技术失败不伪装语义否定 |
| 供题批次 | 请求事件、固定条件、实例与参考引用、未满足项；同请求事件只一份成功批次 |

维护写入与对应领域事件在同一提交边界内生效；异步结果还需按[公共运行§4](System_Foundation_Design.md#4-可靠交接与提交控制)可靠登记结果及待发通知。事件载荷含操作引用、受影响对象／内容引用和来源，不能用通知代替事实。

AI OperationRun及Step尝试由公共运行维护；普通保存和消息受理仍保留请求／事件防重及处理记录，不借用AI执行身份。Domain 在提交前重查所用对象引用及并发令牌；不一致返回冲突，不把较早候选覆盖到新定义上。教材章节关联只能由教材业务写入；接收、处理待办和供题都不隐式应用课程。

**待细化。** 按已定PostgreSQL补物理表、索引和事务实现；定义／图表 Schema、语义归类及质量检查提示协议需单独验证。上述未定实现不能被视为已完成检查器，数值预算沿公共运行策略，不在本模块随意填写。

跨模块事件名称、生产方及用途见[工程入口§6](README.md#6-跨模块事件目录)。本模块维护入库与供题的业务含义，公共运行维护通用事件机制；目录不为已有留痕事件额外创建消费方。

## 7. 领域合同验证

以下是待执行的合同验收，不是本批测试结果。确定性约束、接线恢复和语义质量分开记录，语义样例不能由 mock 返回“通过”代替。

| 合同 | 输入／异常 | 预期 |
| --- | --- | --- |
| 维护与依赖 | 同Task两法关联不同KC合法；Task直接挂KC非法；先导A→B→A非法 | 返回具体路径与错误；合法草稿缺字段可保存但不可正式使用 |
| 定义提取 | 初中分类讨论、高中参数题、K8s排查各提取一次 | 保留变量角色、分支／有界复查及完成条件；不擅自生成所依赖对象 |
| 入库重放 | 同候选重复提交；题目成功后解法失败；取消尚未入库父题 | 不重复排队／实例；保留已完成题；待处理子解法一起取消且模型不删除 |
| 实例引用 | 解法父题未入库；Solution不在Task的方法中；管理员未确认补方法 | 失败不创建半关联；确认后方法引用与题内参考一并提交；不修改定义含义 |
| 供题 | “增加四分之一”，方法A/B；无库存；候选答案错误或缺图 | 优先已有适用题；不足生成检查保存；错误候选不下发、不宣称掌握不足 |
| 恢复 | 生成后崩溃；保存后通知丢失；成功结果重复投递；活动已切换 | 复用产物，不重复实例；仍可读取批次；由Interaction决定是否采用迟到结果 |
| 消费方等待 | 没有等待者；Interaction或Product先超时 | Domain按自身规则处理并发布；不读取消费方期限，不因等待结束取消任务 |
| 读取 | 学生读取statement；跨领域引用；分页期间更新 | 不泄漏答案；拒绝越域；固定读取范围或要求刷新，不静默漏项 |

本轮同步新领域模型与原型；三项AI Operation与普通业务的分工保留。原型检查不能替代后端接线或真实内容质量测试。后续应先核对接口样例与失败路径，再实现Schema、检查器和持久接线。

## 修订记录

| 版本 | 日期 | 修改 |
| --- | --- | --- |
| v0.1 | 2026-11-11 | 按 SwDD 分工建立七章目录 |
| v0.2 | 2026-11-12 | 展开八项 Operation、必要持久 Step、来源失效、供题提交和验收合同；不选择存储或生成算法 |
| v0.3 | 2026-11-13 | 明确Domain独立发布入库与供题事实，消费方管理自身等待和超时；按原头部修订说明及登记§50补登 |
| v0.4 | 2026-11-14 | 统一供题筛选入口，区分内容查询与使用前复核，确认后开测并引用事件目录，补登v0.3并纠正存储待选旧状态 |
| v0.5 | 2026-11-14 | 对齐内容查询的调用授权与资源范围，区分评价参考和学生展示权限 |
| v0.6 | 2026-11-14 | 区分模板提取、实例归类和供题AI能力与普通入库保存，拆清归类检查与正式提交 |
| v0.7 | 2026-11-14 | 同步Task／Solution新定义、多KC方法、Task先导、题内参考及相关Task独立取证；保持既定数值规则和工程边界 |
