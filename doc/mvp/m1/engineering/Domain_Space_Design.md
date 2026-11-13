# M1 Domain Space 设计

> **版本**：v0.2<br>
> **状态**：Operation 合同设计草案，待用户审阅；存储选型及语义检查实现待设计<br>
> **维护与评审**：Codex编写及自检，用户审阅<br>
> **写作规范**：[系统设计写作规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-12<br>
> **修订说明**：v0.1 → v0.2，定义领域维护、教材入库、模板提取、实例保存、依赖查询和供题的 Operation 合同；见[决定登记§36](../../DECISIONS.md#36-operation与step的工程定义)。

本文维护可复用领域内容及其业务操作，不保存学生作答、个人接触史或 Belief。依据为 [PRD R04](../PRD.md#34-维护领域处理入库并关联章节m1-r04)、[R07](../PRD.md#37-准备题目和参考m1-r07)与[内容规格§3.2–3.3](../design/Content_and_Model_Reference.md#32-领域对象与字段)；共同输入见[工程入口§2](README.md#2-设计输入与历史参考)。

## 1. 领域对象、身份与关系

### 1.1 公共输入与引用

Operation 是业务操作，Step 是其中需要保存进度的执行步骤，统一合同见[公共运行§1.3](System_Foundation_Design.md#13-operationstep与operationrun)。本文件不将 Solution 的求解步骤称为运行 Step。下面字段没有标注“可选”时均为必填；空数组与未知分开，未知不能伪装成没有限制。

| 字段／类型 | 含义与校验 |
| --- | --- |
| `access_context`／程序授权上下文 | 各操作共同输入；程序授予领域读取、维护或供题权限，模型输出不能授权 |
| `request_id`／非空标识 | 直接请求输入；同次重试沿用。事件受理改用 `trigger_event_id`，写入去重遵循公共合同 |
| `scope_id`／资源身份 | 领域维护采用 Domain；教材请求采用导入资源；学习供题采用学习空间。新 Domain 创建采用调用者账户身份 |
| `object_ref`／对象引用 | `{domain_id, kind, id}`，`kind` 为 Domain、TaskTemplate、SolutionTemplate、KC、TaskInstance 或 SolutionInstance；ID 由程序分配 |
| `content_ref`／不可变内容引用 | 固定本次读取、生成或展示所依据的内容；后续修改不覆盖已引用题面，不引入跨版本迁移 |
| `expected_revision`／可选并发令牌 | 更新已有对象必填；仅用于防止覆盖并发修改，不代表 Evolution 版本管理 |
| `source_refs[]`／来源引用 | 引用已采用教材候选及页位置、管理员输入或系统生成记录；来源方维护原件，不把教材来源当成模板身份 |

### 1.2 对象载荷与就绪检查

`definition`、`instance` 为按对象类型校验的结构；名称和领域归属不可为空。草稿可缺内容，返回 `gaps[]`；不存在的引用、越域关联及依赖环返回错误，不写入。正式使用必须再核对依赖闭包，不能只读取对象自身的“已保存”标记。

| 类型 | 操作接收的业务字段 | 引用与缺口 |
| --- | --- | --- |
| Domain | `name, coverage, description` | 创建后为空，不复制其他领域；`coverage`、`description` 草稿可空 |
| TaskTemplate | `name, description, task_role, responsibility, completion, variables[], constraints[], variations[], boundaries[], method_refs[]` | `task_role=kc_task\|composite_task`；方法引用为直接方法，不能直接填 KC；结构见§3 |
| SolutionTemplate | `name, rationale, applicability, inputs[], outputs[], solution_steps[], direct_kc_refs[], subtask_calls[], end_conditions[]` | 求解控制与调用见§4；共享方法须满足所有关联 Task 的本层约束 |
| KC | `name, meaning, applicability, examples[], boundaries[], representation, explanation_refs[]` | 对应 KC Task 由方法反查；没有直接检验路径可暂存，返回未就绪缺口 |
| TaskInstance | `task_template_ref, statement, givens, requested_output, representation, bindings, references[], source_kind, source_refs[]` | 只归属一个 TaskTemplate；`references[]` 保存参考结果／评分要点，可暂缺但不能用于检测；不保存学生答案 |
| SolutionInstance | `task_instance_ref, solution_template_ref, worked_process, reference_result, representation, source_kind, source_refs[]` | 同时引用具体题和方法；`source_kind=textbook\|system_generated\|admin_authored`，不能混称来源 |

`representation` 承载所属元素的公式、表格、图形语义及必要呈现信息；题面与参考解法分开读取。详细多模态结构和检查器待结合已保存解析试验确定，本轮不把截图或文字摘要当作完整替代。

载荷中名称、含义和说明是文本，`*_refs[]` 是引用数组，`givens/bindings` 是变量键到类型化值的映射，`completion` 是交付内容与检查条件对象。`gaps[]/issues[]` 均为 `{code,path,message}` 数组，`path` 定位缺口字段或调用路径。`classification_check_ref` 固定实例内容、模板内容及归类结论；`availability` 含 `check_status=not_checked|passed|failed`、`checked_purposes[]` 和问题引用，不能用一个保存成功标记代替。`use_check_ref` 另固定本次供题输入与用途检查，不能替代长期公共可用性记录。

## 2. 定义维护与教材内容入库

### 2.1 `domain.save_definition`

**触发与输入。** 管理员新建／编辑或确认模板候选；需要领域维护权限。输入 `object_kind`（Domain／TaskTemplate／SolutionTemplate／KC）、`action=create|update`、`definition`、可选 `object_ref, expected_revision, candidate_ref, source_refs[]`；更新必须给对象与并发令牌，确认提取结果给 `candidate_ref`。

1. 校验权限、输入类型及当前引用；新建分配身份，更新读取当前令牌。
2. 按§1、§3、§4检查角色、引用和依赖，缺少尚未建立的内容记入 `gaps[]`；不自动创建所依赖 KC、方法或子 Task。
3. 在一次短事务中保存定义内容、来源关系、并发令牌及 `DomainDefinitionSaved` 事件，返回 `object_ref, content_ref, revision, gaps[]`。

同请求返回原结果；并发不一致返回 `revision_conflict`，非法引用／环返回 `invalid_reference|dependency_cycle`。提交失败整体回滚；此操作不拆持久 Step。**验收例：** 保存一个缺方法的复合 Task 得到草稿缺口；给它直接挂有 KC 的方法时拒绝，不改写成 KC Task。

### 2.2 `domain.receive_intake`

**触发与输入。** 教材业务提交 `DomainIntakeRequested` 后异步调用；服务身份需有向目标领域提交内容的权限。输入 `trigger_event_id, domain_id, intake_request_id, candidate_refs[]`。经教材公开接口读取每项的 `kind=kc|task_instance|solution_instance, content_ref, source_refs[]`；解法另有 `parent_candidate_ref` 或已入库 `task_instance_ref`。

1. 校验请求事件和资源范围，读取教材业务已采用且当前仍有效的不可变候选；未采用或已过时来源不进入待办。
2. 按题目与其解法建立 `group_ref`，KC 独立成组；解法父题可在本批、已有待办或已入库记录中，无法定位则返回 `missing_parent`。
3. 同次提交保存整批待办与 `DomainIntakeReceived`，发布 `producer=domain, result_kind=intake_receipt`。回执为 `intake_request_id, items[{candidate_ref,intake_item_ref,group_ref,state}]`；这里只接收，不创建模板、实例或章节关联。

事件重复沿用原 Operation；同领域、同已采用候选已有有效待办／入库结果时回传已有映射，避免重复排队。读取来源故障保留受理记录重试，不产生半批回执。**验收例：** 只提交题目可进入待办；另提交解法时可定位此前题目，不要求一起导入。

同操作接收 `MaterialCandidatesAdopted|MaterialImportDeleted` 的来源失效分支：输入为事件中的导入身份、被替代／删除的来源及受影响提交引用。只将未入库行标为 `source_invalid` 并追加 `DomainIntakeSourceInvalidated`，不覆盖已入库对象；不发布新的 `intake_receipt`。处理待办前仍查询教材公开有效性，不能依靠通知恰好先到。

### 2.3 `domain.process_intake`

**触发与输入。** 管理员点击待办行按钮；需要领域维护权限。输入 `intake_item_ref, expected_revision, action` 和下表分支参数。

| `action` | 参数与处理 | 输出 |
| --- | --- | --- |
| `add_kc` | 新建时 `definition`；复用时 `existing_kc_ref`，二者恰一。复用只核对含义和记录来源，不覆盖定义 | `object_ref` 与 `state=added` |
| `associate_task` | `task_template_ref`；用已采用题目调用§5.1的归类及保存逻辑 | `task_instance_ref` 与 `state=associated` |
| `associate_solution` | `solution_template_ref, task_instance_ref, confirm_add_method`；先校验父题对应，方法不在父题 Task 中时必须明确确认补引用 | `solution_instance_ref` 与 `state=associated` |
| `discard` | `confirm_child_discard`：取消未入库父题且存在待处理解法时必填 `true` | `state=discarded` 与 `affected_item_refs[]` |

每行处理先核对来源仍有效；`source_invalid` 返回 `source_unavailable`，不能继续新增模型。需要AI归类时复用§5.1的持久检查步骤；提交时再核对来源有效性和并发令牌，在短事务内同时保存对象／引用、待办结果、来源映射和 `DomainIntakeItemProcessed`；需补 Task→Solution 引用则一并提交。结果含 `group_pending_count`；整组无未完成项后不再列待办，追溯记录保留。取消待办不删除教材和已入库对象。

缺父题、需要确认补方法、语义无法确认分别返回 `parent_not_linked|confirmation_required|classification_unresolved`，不改待办。已处理项的同请求返回原结果，另请求改变处理结果返回 `already_processed`。**验收例：** 提取模板后题目仍待关联；解法关联失败不撤销此前成功入库的题目。这里只复用内部校验函数，不嵌套创建另一份 OperationRun。

## 3. 任务模板的结构化表达

### 3.1 可检查的模板结构

`variables[]` 每项为 `{key,name,type,role,constraints}`；`role=given|to_solve|to_investigate`。`constraints[]`、`variations[]`、`boundaries[]` 各项保留稳定条目标识、描述及可选结构表达；符号、单位和变量引用先做确定性检查，语义解释不能替代这些检查。

`completion` 指本类任务交付什么及怎样检查完成，不等于学习目标达标规则。正向生成只能在已定义参数、关系及变化内实例化；反向归类同时核对责任、条件与边界，不仅比较题干相似度。条件未知返回待核对，不当作满足。

### 3.2 `domain.extract_template`

**触发与输入。** 管理员在题目／解法待办点击提取；需要领域维护权限。输入 `intake_item_ref, template_kind=task|solution, extraction_instruction`（可空）、可选 `prior_candidate_ref`。源元素类型必须相符，内容取当前已采用引用。

| 持久 Step | 输入与执行 | 保存产物与停止条件 |
| --- | --- | --- |
| `prepare_template_input` | 固定候选内容、来源、现有定义查询结果及用户要求 | `extraction_input_ref`；源不存在或权限不符即停止 |
| `derive_template_candidate` | 经 AI 底座提取可复用责任、条件和参数；只允许读取本领域内容 | `candidate_ref`，载荷为§1定义字段、依据与 `unresolved[]`；不允许模型写模型库或编造已存在对象身份 |
| `check_template_candidate` | 检查结构、引用与来源支撑；不能确认的依赖保留为建议 | `check_ref, issues[]`；不自动补建其他模型元素 |

受理返回 `operation_run_id`，通过公共 `read_operation_run` 读取状态及最终 `candidate_ref, check_ref, proposed_definition, issues[]`，追加 `DomainTemplateCandidatePrepared`。候选需管理员确认后调用 `domain.save_definition` 才成为定义，实例仍待关联。技术重试复用已完成产物；重新提出不同要求是新请求，保留前候选引用。**验收例：** 从例题解法提取 ST，不同时生成 KC、TT 或 SI；缺子方法时显示缺口。

## 4. 方法分解与知识依赖

### 4.1 本层约束与递归结构

`solution_steps[]` 使用 `solution_step_id`，含动作、输入、产出与后继；条件转移记录条件和目标，复查记录返回位置与停止条件。`subtask_calls[]` 每项含 `call_id, at_solution_step_id, child_task_ref, child_method_ref, condition, input_bindings, output_bindings`。子方法必须是所指子 Task 的直接方法；条件未知时不虚构已走过该分支。

- KC Task 的每个本层方法直接引用恰一个 KC，备选方法须为同一 KC；递归并集可包含更多 KC。
- 复合 Task 的本层方法直接 KC 为零，依赖经子 Task 调用表达；本层组织和检查责任仍存在。
- 方法调用图不得循环；同一子任务可在不同调用位置复用。本层有界复查不是模板引用环。
- 章节采用的 TT／ST 及方法适用来源由教材业务维护。Domain 返回知识路径，不维护第二份章节选择或个人状态。

### 4.2 `domain.query_dependencies`

**触发与输入。** 管理员查看依赖，教材业务汇总知识，Interaction／Evaluation 读取求解路径；均需领域读取权限。输入 `task_ref, method_refs[]`（可选，省略为该 Task 全部直接方法）、可选 `content_ref, path_filter`；`path_filter` 仅引用已有分支／调用位置，不输入任意待执行代码。

先校验所选方法归属，再按调用位置展开子 Task／方法，保留每条条件与路径并检测环；按 KC 身份去重但保留所有到达路径。输出 `dependency_ref, input_content_refs[], nodes[], calls[], kc_summary[], gaps[]`，其中 `calls` 保留输入输出绑定。缺子方法返回缺口；非法指定或环返回结构错误，不裁掉错误分支伪造完整结果。

这是只读查询，无业务事件或持久 Step；读取故障可重试。结果只表示定义依赖，不推断实际执行、更不更新 Belief。**验收例：** A、B 两方法各用不同子 Task；查询 A 不能返回 B 独有 KC 为必需依赖，同一 KC 多次引用只汇总一次。

## 5. 题目与解法供给

### 5.1 `domain.save_instance`

**触发与输入。** 管理员从任务维护题目／解法，或明确关联教材实例；需要领域维护权限。输入 `instance_kind=task|solution, action=create|update, instance`；更新另给 `object_ref, expected_revision`。`instance` 字段见§1.2；可选 `classification_check_ref` 仅能复用针对同内容和同模板的检查结果。

1. 固定题目／解法及模板内容；校验题面必要条件、图表、变量绑定、Task 责任及边界。解法还检查对应 TI、ST 及 Task 的直接方法引用。
2. 反向归类得到 `matched|unresolved|mismatch`；后两者分别返回 `classification_unresolved|classification_failed`，保留候选不创建已关联实例。参考答案／用途未核对可保存为 `not_checked`，但不能供正式检测。
3. 一次短事务保存实例、检查引用、来源及 `DomainInstanceSaved`，返回 `instance_ref, content_ref, classification_check_ref, availability, gaps[]`；更新后原已引用内容仍可读取。

涉及 AI 归类时先受理为 OperationRun，通过 `read_operation_run` 读取结果；持久保存 `classify_instance` 的输入与检查产物，再进入短事务。纯引用与字段更新不机械拆 Step。并发或当前引用失效须重查后再保存，同请求不重复建实例。**验收例：** 有表格但漏单位的题不能通过可用检查；教材没有解法仍可保存已归类 TI，不伪造教材 SI。

### 5.2 `domain.supply_task`

**触发与输入。** Interaction 提交 `TaskSupplyRequested`，Domain 异步受理；需要本次学习空间的供题权限。输入 `trigger_event_id, domain_id, purpose=example|practice|assessment, task_ref, allowed_method_refs[], assessment_constraints, method_source_refs[], exposure_refs[], count`。`count` 为正整数；课程方法来源引用、目标条件和个人已见题面／解法／帮助的记录由调用方提供，Domain 不读个人私有表。

`assessment_constraints` 包含本次参数范围、拟检查方面与表征／时间条件；空对象表示无额外条件，不能表示已满足所有方面。供题不证明保持已达标；实际间隔及 Evidence 资格由 Interaction／Evaluation 判断。`exposure_refs=[]` 只表示调用方确认无相关经历；来源未知须显式返回缺口，不能据此声称新题。

| 持久 Step | 执行与分支 | 可恢复产物 |
| --- | --- | --- |
| `prepare_supply` | 固定模板、允许方法及调用方条件；核对定义就绪、方法来源与用途 | `supply_input_ref`；无方法或非法范围时返回明确缺口 |
| `select_instances` | 查询已核对实例，逐题按当前用途和提供的接触史筛选，去除重复 | `selection_ref`；够数直接进入批次提交，不调用生成 |
| `generate_candidates` | 不足部分经 AI 底座按固定模板生成题目和必要解法参考；读取权限限本次材料 | `candidate_batch_ref`；不可扩大模板或通过读 Belief 改写题意 |
| `check_candidates` | 检查题意／图表、参数、答案、范围、归类及本次用途；失败候选隔离 | `check_batch_ref`；有合格替代继续，预算内仍无题则记录 `unfilled[]` |
| `commit_supply` | 将合格新实例、参考与检查保存，再提交供题批次；已有实例直接引用 | `supply_batch_ref`；本步失败从已有候选恢复，不重新生成已通过题 |

生成输出为§1.2的 TI／SI 候选及条件绑定，参考解法、提示和题面分开。程序校验结构与引用，语义检查记录所用模型／规则及理由；检查无法确认不作通过。模型超时、格式错误走有界技术重试；合法但无合格题是业务结果，不无限换题。

提交保存 `DomainTaskSupplyCompleted`，按请求事件发布 `producer=domain,result_kind=task_supply`。载荷为 `supply_batch_ref, items[{task_instance_ref,content_ref,reference_solution_refs[],matched_method_refs[],use_check_ref}], unfilled[{condition,reason}]`；无题也返回空批及原因。检查通过、保存成功后方可交付，无须管理员逐题批准。

成功结果同键只发布一次；重试不追加第二批实例。Interaction 取回后核对活动仍有效、条件未变及题面是否刚被展示，再建立本次题单和展示事件。题目晚到不自动开始检测。**验收例：** 现有题都展示过答案时生成新题；生成检查失败且无替代时返回缺口，不能把旧题当新独立证据。

## 6. 持久化、公开接口与并发修改

### 6.1 `domain.query_content`

**触发与输入。** 管理员列表／详情、教材选关联、Interaction 取题和 Evaluation 取参考；需要相应内容读取权限。输入 `domain_id, kinds[], filters, cursor, limit`，或 `object_ref/content_ref` 精确读取；`cursor` 可空，`limit` 为受服务上限约束的正整数。候选和待办查询还需该来源处理权限。

`filters` 仅接受名称、对象类型、关联 Task／方法和可用性等注册字段；不接受个人能力条件。输出 `items[], next_cursor, read_token` 或对象内容、来源与 `gaps[]`；`next_cursor=null` 表示当前读取范围结束。分页按稳定对象身份排序，游标固定本次读取范围；修改后需刷新，不混拼两个读取结果。

实例按 `view=statement|reference|full` 返回；学生题面只允许 `statement`，解法和教学辅助内容不能混入。原始参考由获授权的 Interaction／Evaluation 读取，是否向学生展示由活动规则控制。不存在、越权、故障分别返回 `not_found|forbidden|temporarily_unavailable`；查询无业务事件、不触发提取／生成／检查。**验收例：** 查询题面不会附带其 SI；换领域不能读到另一领域的候选。

### 6.2 提交边界与保存记录

| Domain 记录 | 保存内容与唯一约束 |
| --- | --- |
| 定义与内容 | 对象身份、当前内容引用、并发令牌、缺口；不可变内容供历史引用，不在M1建设演进平台 |
| 模板与实例关系 | TT→直接 ST；ST→本层 KC／子 Task 及选定 ST；TI→TT；SI→TI、ST；禁止重复或越域引用 |
| 入库及来源 | 已采用候选、处理组、行状态、结果引用、取消原因；同候选重放回传已有有效结果 |
| 生成与检查产物 | 输入内容引用、模型／规则来源、候选、检查结果、失败理由；技术失败不伪装语义否定 |
| 供题批次 | 请求事件、固定条件、实例与参考引用、未满足项；同请求事件只一份成功批次 |

维护写入与对应领域事件在同一提交边界内生效；异步结果还需按[公共运行§4](System_Foundation_Design.md#4-可靠交接与提交控制)可靠登记结果及待发通知。事件载荷含操作引用、受影响对象／内容引用和来源，不能用通知代替事实。

OperationRun 幂等键、Step 尝试、租约和预算由公共运行维护。Domain 在提交前重查所用对象引用及并发令牌；不一致返回冲突，不把较早候选覆盖到新定义上。教材章节关联只能由教材业务写入；接收、处理待办和供题都不隐式应用课程。

**待细化。** 选择存储后补物理表、索引和事务实现；模板／图表 Schema、语义归类及质量检查提示协议需单独验证。上述未定实现不能被视为已完成检查器，数值预算沿公共运行策略，不在本模块随意填写。

## 7. 领域合同验证

以下是待执行的合同验收，不是本批测试结果。确定性约束、接线恢复和语义质量分开记录，语义样例不能由 mock 返回“通过”代替。

| 合同 | 输入／异常 | 预期 |
| --- | --- | --- |
| 维护与依赖 | KC Task 两个本层方法引用不同 KC；复合方法直接挂 KC；A→B→A | 返回具体路径与错误；合法草稿缺字段可保存但不可正式使用 |
| 模板提取 | 初中分类讨论、高中参数题、K8s排查各提取一次 | 保留变量角色、分支／有界复查及完成条件；不擅自生成所依赖对象 |
| 入库重放 | 同候选重复提交；题目成功后解法失败；取消尚未入库父题 | 不重复排队／实例；保留已完成题；待处理子解法一起取消且模型不删除 |
| 实例引用 | 解法父题未入库；ST不在TT中；管理员未确认补方法 | 失败不创建半关联；确认后引用和SI一并提交；不修改模板含义 |
| 供题 | “增加四分之一”，方法A/B；无库存；候选答案错误或缺图 | 优先已有适用题；不足生成检查保存；错误候选不下发、不宣称掌握不足 |
| 恢复 | 生成后崩溃；保存后通知丢失；成功结果重复投递；活动已切换 | 复用产物，不重复实例；仍可读取批次；由Interaction决定是否采用迟到结果 |
| 读取 | 学生读取statement；跨领域引用；分页期间更新 | 不泄漏答案；拒绝越域；固定读取范围或要求刷新，不静默漏项 |

本批自检范围为八项 Operation 的字段、分支、事件、去重及模块边界；没有运行实现或内容质量测试。后续应先核对接口样例与失败路径，再实现 Schema、检查器和持久接线。

## 修订记录

| 版本／日期 | 变更 |
| --- | --- |
| v0.2／2026-11-12 | 展开八项 Operation、必要持久 Step、来源失效、供题提交和验收合同；不选择存储或生成算法 |
| v0.1／2026-11-11 | 按 SwDD 分工建立七章目录 |
