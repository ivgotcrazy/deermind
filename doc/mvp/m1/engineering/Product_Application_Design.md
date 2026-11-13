# M1 产品业务设计

> **版本**：v0.4<br>
> **状态**：M1业务Operation合同草案，待审；存储、认证协议及传输接口仍待细化<br>
> **维护与评审**：Codex编写及自检，用户审阅<br>
> **写作规范**：[系统设计写作规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-13<br>
> **修订说明**：v0.3 → v0.4，收窄为预置账号、固定角色和必要确认，区分账号业务与底座授权执行，不新增完整权限产品<br>

本文设计教材准备、学习目标、学习空间和账号关系等产品业务，说明这些业务如何调用核心Space。教材助手归本模块管理，个人能力与目标达成计算仍由Evaluation负责；共同输入见[工程入口§2](README.md#2-设计输入与历史参考)。学习用时统计与提醒后置，不作为M1模块或验收条件。

## 1. 业务对象与模块组织

本文件完整维护产品业务Operation；不是给每个内部函数或校验步骤建立一个OperationRun。共用身份、执行状态及Step合同见[系统底座§1.3](System_Foundation_Design.md#13-operationstep与operationrun)。本轮不决定HTTP路由、数据库或Agent框架。

| 对象／责任 | 本模块拥有的数据与边界 |
| --- | --- |
| 账号与使用条件 | 固定管理员／学生身份、必要监护确认；产品业务对接认证组件，底座执行授权检查，M1不建设完整账号权限平台或家长产品 |
| 教材与导入 | 原文件引用、教材信息、章节目录、助手对话、内容候选及采用；原件不被候选覆盖 |
| 领域交接 | 保存待入库提交及来源有效性；Domain订阅请求后维护其待办、模板、知识和实例，本模块不写Domain私有数据 |
| 目标与采用 | 章节→TaskTemplate／SolutionTemplate关联、目标定义、应用结果与空间当前引用；Claim及个人判断归Evaluation |
| 学习空间 | 学生所有权、选用教材／目标、采用记录；持续对话与活动归Interaction，Evidence／Belief与目标达成归Evaluation |

### 1.1 共用入参与类型

所有操作接收程序建立的`access_context`。有写入的调用携带稳定`request_id`；同操作、同作用范围、同请求身份只执行一次，参数变化返回`identity_conflict`。程序生成的`operation_run_id`不由LLM指定。更新请求带`expected_revision`，用于检查并发变化，不是Evolution版本。

| 类型 | 必需字段／允许的可选字段 | 约束与唯一维护位置 |
| --- | --- | --- |
| `ID`、`Ref`、`Revision` | 非空不透明标识；`Ref`固定对象与采用依据 | 不用标题或数组位置当身份；空值须由下文显式允许 |
| `AccountInput` | `login_identifier:string, display_name:string`；学生另需`guardian:{existing_ref:Ref? , verified_identity_ref:Ref}, verification_ref:Ref` | guardian无existing_ref时按已核实身份建立必要监护记录，不开通家长应用。凭据使用`CredentialProof`／`CredentialReset`受保护对象，格式由认证设计确定，不入普通事件 |
| `ConfirmationInput` | `student_id:ID, kind:enum, notice_ref:Ref, decision:enum, occurred_at:timestamp, source_ref:Ref` | kind为`guardian_consent`／`student_assent`；decision为`accepted`／`declined`／`pending`，分别表示同意／未同意／待确认，不把缺值当同意 |
| `MaterialInput` | `domain_ref:Ref, title:string, source:string, files:FileReceipt[]`非空；`edition:string?` | FileReceipt含`storage_ref:Ref, type:pdf|jpg|png, original_name:string, order:int`；文件内分页保留顺序，版权页未知如实留空 |
| `MaterialSelection` | `import_id:ID, scope:batch|chapter|content, basis_revision:Revision, source_refs:Ref[]` | chapter／content需对应对象引用；引用按本次明确请求确定，浏览位置不能自动替代选区 |
| `CandidateRef` | `candidate_id:ID, candidate_revision:Revision, basis_revision:Revision` | 内容为KC／TaskInstance／SolutionInstance候选；图表和公式随所属元素，SI必须引用父题；结构语义见[内容规格§3.1](../design/Content_and_Model_Reference.md#31-提取什么以及怎样保存图表和来源) |
| `GoalItem` | `item_id:ID?`（仅新增可省）、`title:string, claim_ref:Ref, chapter_refs:Ref[], task_conditions:object, method_mode:enum, methods:MethodRequirement[]` | method_mode为`specified`／`any_one`／`each`；MethodRequirement含`method_ref:Ref, chapter_refs:Ref[], aspects:{aspect_ref:Ref, condition_values:object}[]`。条件值受Claim判据约束；不提供逐目标概率阈值 |
| `ApplicationRef` | 不可变应用结果引用 | 固定教材、目标、Domain、章节方法、Claim、活动定义及逐行为可用条件；不是新增课程模型 |

未列为可选的操作入参均必需。`action`属于参数明确的操作族，分支不同不改变所有权。各操作编号依次定义逻辑Step `s01`、`s02`等；需要恢复的步骤持久保存此身份，后续插入步骤不得重排已使用身份。同步函数、AI循环和跨模块等待是Step的实现方式，不另编产品操作身份。

## 2. 账号、角色与业务权限

依据：[PRD R01](../PRD.md#31-初次启动与试用账号m1-r01)、[R17](../PRD.md#51-谁定义谁产生谁可以修改m1-r17)。真实学习输入前必须核对使用条件；登录成功不代表必要确认已经完成。

本轮确认的最小范围：试用账号提前创建并统一发放、简单登录、固定学生／管理员角色、学生仅访问自己的学习空间，以及Agent／后台任务的受限身份。必要的监护与使用确认记录保留。

不建设自助注册、自定义角色、权限配置、完整亲子关系管理、复杂找回或单点登录。下列既有操作合同仍待审，开户与必要重置可由受控管理方式完成，不据操作名新增整套管理页面；是否保留专门找回入口在最小认证方案中确认。认证组件尚未选型。

账号及学习空间归产品业务，所属Space定义资源访问规则，公共运行底座在路由、派发、读取及恢复处执行授权检查。按已登记的公开查询向底座提供必要路由事实，不转移数据所有权。

### 2.1 `product.save_trial_account`：初始化或维护试用账号

**调用与合同。** 部署者仅可在尚无首个管理员时调用`action=bootstrap_admin`；管理员可调用`create_student`／`update_student`。输入为`action, AccountInput`，新建另需受保护的`CredentialReset`，更新另需`student_id, expected_revision`且不修改凭据。输出账号引用、角色、关系记录与使用条件缺口；完成不代表已允许处理真实学习输入。

1. 校验初始化资格或管理员权限；核对登录标识唯一、学生与监护关系的核实记录。
2. `bootstrap_admin`只建立首个管理员；`create_student`建立独立身份，复用或建立必要监护记录；`update_student`仅修改该学生基本信息及核实后的关系，不更换身份或授予管理员角色。
3. 通过受保护机制建立／保持凭据，保存账号、关系及`TrialAccountSaved`操作事件，返回结果。

**恢复与验收。** 重复请求返回同一账号；关系核实缺失或并发修订冲突不写入。凭据建立失败不得返回可登录成功。验收首个管理员重复创建被挡、学生更新保留原空间、角色边界不能绕过；初始化密钥交付方式在认证设计中定。

### 2.2 `product.record_usage_confirmation`：记录必要首次确认

**调用与合同。** 管理员记录线下监护确认及已核实的学生意愿；学生仅能提交本人的使用意愿。输入`ConfirmationInput`及该学生使用条件记录的`expected_revision`（开户时建立）；输出确认记录与当前使用条件结果，不接受调用者直接传入“可用=true”。

1. 校验学生、监护关系、确认材料与记录者权限；学生不能代替监护人确认。
2. 追加实际确认记录，按已定条件计算是否允许真实输入；未同意或缺失保持不满足。
3. 保存`UsageConfirmationRecorded`事件与结果；确认不创建学习活动或个人能力判断。

**恢复与验收。** 同请求去重，冲突先重读；失败不默认为已同意。验证监护确认缺失时不能提交真实学习输入，补齐后按原账号继续，合成案例准备不因此禁止。本操作不新增撤回授权流程。

### 2.3 `product.sign_in`：登录原账号

**调用与合同。** 未认证的学生或管理员提交`login_identifier, CredentialProof`，可选客户端返回位置（仅允许站内）；输出认证会话收据、角色、可进入的业务范围和必要确认缺口，密钥及凭据不进入业务日志。

1. 交认证组件核验凭据与账号，不根据请求中的角色授权。
2. 取得角色、关系及必要确认结果；校验返回位置。
3. 建立认证会话，留`AccountSignedIn`安全操作记录，返回进入页面所需身份；缺确认者仅进入允许完成确认的流程。

**恢复与验收。** 认证失败不创建学习空间或暴露他人账号详情；重复成功请求按认证收据恢复，不因重试创建新身份。验证学生与管理员的访问边界及缺确认登录后的写入限制；会话时限与凭据协议待认证设计确认。

### 2.4 `product.recover_account`：管理员协助找回

**调用与合同。** 管理员在线下重新核实后提交`account_id, verification_ref, CredentialReset, expected_revision`；输出恢复收据及原账号身份，不返回学生历史内容给未获授权的人。

1. 核对管理员权限、找回对象和有效核实依据。
2. 通过认证组件更换该账号凭据并处理旧认证凭据，具体会话失效协议交认证设计。
3. 追加`AccountRecovered`记录，保留学生ID、关系与空间引用，返回恢复结果。

**恢复与验收。** 同请求只恢复一次；核实不足拒绝，认证组件未确认成功不返回完成。验收恢复后仍进入原空间，失败不新建学生或清空历史。

## 3. 教材助手与内容准备

依据：[PRD R02–03](../PRD.md#32-批量导入教材m1-r02)。本节管理员操作记录归教材业务，不写成学生空间聊天或能力Evidence。

### 3.1 `product.receive_material`：接收整批或补充材料

**调用与合同。** 管理员提交`action=new_import|append_files, MaterialInput`；补充另需`import_id, expected_revision`，沿用原Domain，不能借补页另换领域。输出导入ID、原件收据、页序及失败部分，完成表示材料可供解析，不表示已解析或已应用。

1. 只读核对Domain存在；校验文件类型、收据和顺序，未选领域立即拒绝。
2. 保存已成功接收的原件及页序；PDF内部分页，保留文件内页与印刷页码的区别，不猜版次。
3. 建立或补充同一导入记录及`MaterialReceived`事件；失败文件单列，已有内容可继续使用。

**恢复与验收。** 同请求、同文件收据不重复追加；部分上传失败按原导入继续接收，删除中的导入拒绝新材料。验证整批PDF／图片、未选领域、补页及重试保留已收部分。文件大小／数量上限与上传协议待基础设施设计，不在此编造数值。

### 3.2 `product.save_material_metadata`：补录教材基本信息

**调用与合同。** 管理员提交`textbook_id, expected_revision, metadata_patch`；patch仅含书名、来源说明、已核实版次／版权页引用，不接收解析内容、Domain替换或章节方法配置。输出新基本信息修订。

1. 核对对象及字段白名单，未知版次保持空值。
2. 比较并发修订，保存指定字段及`MaterialMetadataSaved`事件。
3. 返回已保存信息；已应用组合继续使用原采用结果，须另行应用更新。

**恢复与验收。** 冲突不覆盖；同请求复用结果。验证补录版权页不改题面、模型或既有活动，普通保存不令新内容立即供学生采用。

### 3.3 `product.delete_material_import`：删除未完成导入

**调用与合同。** 管理员提交`import_id, expected_revision, confirmed_scope_ref`，确认引用对应界面已说明的删除范围；输出删除收据。已应用教材不能从本入口撤下。

1. 核对导入未完成、确认范围仍有效，列明领域已入库内容不受影响。
2. 标记该导入不再可操作，追加`MaterialImportDeleted`事件；取消该导入未完成的助手工作及提交等待，晚到结果在提交检查时失效。
3. 返回列表移除结果；相关未入库来源失效通过事件交Domain处理，不删除其已保存对象。

**恢复与验收。** 重复删除返回原收据；应用状态已变化则拒绝。验收旧助手候选不能在删除后采用，已入库定义、实例及其他教材不受影响。原文件物理保留／销毁不由此操作决定。

### 3.4 `product.converse_material_assistant`：持续对话解析与纠错

**调用与合同。** 管理员提交`import_id, message:string`；可选`MaterialSelection`、前一候选引用及补充材料收据。输出持久对话消息、澄清请求或候选批引用及处理状态；没有明确选区时只澄清，不默认整个教材。

1. 保存消息及本次明确引用；读取原件、同一导入的相关历史、当前采用内容和已有候选，不把后来浏览章节替换引用。
2. 交AI底座执行教材助手：按规则调用解析／识别与局部补提工具。允许澄清、补图、纠正公式、拆解法；只读来源，只写候选。
3. 程序维护编号、父题与原件定位，核对本次修改范围、必需图表／条件和结构；缺信息返回补充请求，服务故障记失败，不能编造合格结果。
4. 保存候选批、原内容对照、改动说明及`MaterialCandidateProposed`事件；等待管理员采用或继续对话，不自动覆盖当前内容。

**恢复与验收。** 长操作通过`read_operation_run`读取进度及输出。缺信息时本轮以`needs_input`合法完成，下条管理员消息是新请求，引用同一对话／候选；技术重试沿原消息恢复。已有候选不重做采用，旧内容变化须重新核对。验证刷新恢复、局部修正不改整章、题面不带提示、无手工编辑器；具体Agent输出Schema／预算引用AI底座后续合同。

### 3.5 `product.decide_material_candidate`：采用或不采用候选

**调用与合同。** 管理员提交`CandidateRef, decision=adopt|decline, expected_revision`；输出采用记录或未采用结论与当前解析内容引用。只接受完整核对范围内的候选批，变更范围由候选明确列出。

1. 校验候选仍待核对、基础内容修订未变、必要内容完整且父题引用有效。
2. `decline`保留旧内容；`adopt`只替换声明范围，保留旧内容和候选来历，标记被替代候选。
3. 共同保存当前引用、决定及`MaterialCandidatesAdopted`或`MaterialCandidateDeclined`事件；采用使旧待入库来源失效，由Domain订阅处理。

**恢复与验收。** 同请求返回原决定；来源变化或并发采用冲突不覆盖，要求重新引用核对。验证未采用内容不能提交入库、旧待办不能使用过时来源、已入库领域对象不被本操作改写。

### 3.6 `product.submit_domain_intake`：提交已采用内容到领域

**调用与合同。** 管理员提交`import_id, adopted_content_refs:Ref[], expected_revision`；可选已入库父题引用。输出提交收据及Domain待办受理引用；不输出“模板已建立”或“章节已关联”。

1. 核对所选内容均已采用且来源有效；KC、题目、解法分别选择。选解法必须同时选父题，或准确引用同一道已入库题，不能偷偷附带其他解法。
2. 保存按来源修订固定的提交包，追加`DomainIntakeRequested`事件；Domain的`domain.receive_intake`订阅创建待办，Product不直接写其模板或实例。
3. 按`(导入scope_id,触发事件,domain,intake_receipt)`等待受理结果；仅提交事件已保存时返回处理中，成功取得`intake_item_ref/group_ref`及候选映射后才完成。

**恢复与验收。** 同一来源修订的重复提交复用待办／已有入库引用；Domain未受理时重投原事件，不再生成提交包。来源已替代不得继续入库，需提交新内容。验证只选题不带解法、缺父题被挡、重复投递只建一次待办。

## 4. 章节关联、目标定义与课程应用

依据：[PRD R04–05](../PRD.md#34-维护领域处理入库并关联章节m1-r04)、[R08](../PRD.md#38-检查应用与更新m1-r08)及[内容规格§3.7](../design/Content_and_Model_Reference.md#37-课程应用结果与学生选用交接)。保存草稿、确认应用与学生采用是不同提交，不用一个成功标志代替。

### 4.1 `product.save_chapter_association`：添加、编辑或取消章节关联

**调用与合同。** 管理员提交`action=add|update|remove, textbook_id, chapter_id, task_ref, expected_revision`；add／update另需非空`method_refs:Ref[]`。输出已保存的章节关联及由方法递归汇总的只读KC；不接收直接KC关联。

1. 从Domain公开读取所选Task及直接方法，核对同领域、引用有效和方法属于该Task；add／update至少一法。
2. 比较修订；add保存新关联，update只替换本章方法，remove只删除该章节引用，不删领域对象。
3. 保存`ChapterAssociationSaved`事件及结果；提示受影响目标需要核对，原已应用采用记录不被草稿改写。

**恢复与验收。** 同请求复用结果；无效引用或并发冲突不生效。验收取消弹窗无写入、确认即保存；第一章A与第二章B保留各自来源，不能被计算成全章只允许交集或任意章均开放两法。

### 4.2 `product.save_learning_target`：维护目标定义

**调用与合同。** 管理员提交`action=create|update, textbook_ref, title, items:GoalItem[]`；update另需`target_id, expected_revision`。输出目标定义修订及待补缺口；不创建Claim、不写个人达成结果。

1. 读取所选章节采用的Task／方法和Evaluation公开Claim，核对Claim绑定Task及方法／方面适用性。
2. 按章节方法并集保留方法来源；校验任务条件、方面要求和`specified`／`any_one`／`each`：指定一种、同一种任选达标、各法分别达标。
3. 保存合法目标定义及`LearningTargetSaved`事件；缺定义或方法来源失效单列，不通过删除目标项伪装完整，不把保存当应用。

**恢复与验收。** 非法引用拒绝；可描述的准备缺口保留为未具备应用条件，不能造学生“待确认”。同请求返回原目标，冲突不覆盖。验收两法分别要求不会拼接成达标，不允许修改全局0.90阈值。

### 4.3 `product.apply_course`：检查并应用教材与目标组合

**调用与合同。** 管理员提交`action=check|confirm, textbook_ref, target_ref`；check可含所选章节／内容引用，confirm须带`check_ref, expected_revision`。check输出逐行为检查结果；confirm成功输出`ApplicationRef`、可用范围及受影响空间，不新增课程实体。

1. `check`读取原件／语义内容、章节方法、目标／Claim、活动定义和题目供给依据，保存引用固定的检查结果；可读、讲解答疑、反馈与正式评价分别列缺口。无备用题但可生成并检查不算自动阻塞。
2. `confirm`复核检查依据仍有效、教材与目标及其适用关系合法；阻塞组合身份的缺口拒绝，其余逐行为限制随应用保存。检查过时要求重查。
3. 共同提交新采用记录、组合当前引用、已选同一教材及同一目标的空间当前采用与`CourseApplied`／`LearningSpaceAdoptionChanged`事件；失败不替换旧有效引用，普通保存不走此步骤。
4. 若某空间目标条件实际变化，再追加`LearningTargetApplied`供Evaluation订阅重新对照；不直接调用计算或修改概率。既有活动保留旧依据，后续活动读取新采用；目标结果更新不作为应用成功的前提。

**恢复与验收。** 同请求恢复原应用结果，不重复更新空间；新的管理员确认使用新请求并校验前序。验证未确认不出现学生选项、部分评价缺口不封禁全章提问、更新不换目标身份、不改旧活动；跨对象提交方案由存储设计落实，失败不能出现一半空间被宣称成功。

## 5. 学习空间生命周期与核心输入

依据：[PRD R09–10](../PRD.md#41-选用课程与阅读教材m1-r10)。空间属于学生，课程采用只提供内容／目标依据；不把阅读位置、一次活动内容或长期章节范围混为一谈。

### 5.1 `product.open_learning_space`：创建或进入个人空间

**调用与合同。** 学生提交`action=create|enter`；create须带`ApplicationRef`，enter须带`space_id`。输出空间身份、当前采用、使用条件和可恢复的页面／活动引用；首个真实输入仍按当时有效使用条件再校验。

1. 校验学生身份与必要确认；create只允许应用成功且仍适用的组合，所有试用学生同等可选，不增加教材授权审批；enter只允许本人空间。
2. create保存个人空间及`LearningSpaceCreated`、首次`LearningTargetApplied`事件；enter读取当前引用并记录实际进入事件，不复制教材、不切换当前活动或重建对话。
3. 返回首次呈现条件或原阅读位置／活动／草稿引用，分别由客户端和Interaction读取与恢复。未产生表现不填掌握结果；Evaluation通过事件完成初始目标对照，未完成明确返回处理中。

**恢复与验收。** 同创建请求只产生一个空间；进入失败不创建替代空间。应用已变时核对当前组合，不能悄悄采用无效旧请求。验证无组合时提示未准备、浏览章节不影响活动、首次与再次进入的恢复不同、他人空间不可进入。本操作不新增学生修改教材／目标或空间删除能力。

### 5.2 `product.query_product_view`：按权限读取业务视图

**调用与合同。** 学生／管理员或已注册的模块身份提交`resource_kind`，按下表提供筛选／对象引用；模块只读获授权的交接材料，不冒用管理员权限。可选不透明分页`cursor`和`limit:positive integer`。输出只读内容、采用／发布时间、未完成说明及`next_cursor`；不创建持久OperationRun、不触发Agent或评价。

| `resource_kind` | 必需定位／可选筛选 | 可见范围与数据所有者 |
| --- | --- | --- |
| `accounts` | 管理员；可选学生ID／登录标识 | Product账号与关系，不返回凭据 |
| `materials`／`material_import` | 后者需导入ID；可选Domain、教材名 | 管理员看草稿、对话和候选；学生教材内容走本人空间采用，不读后台候选 |
| `adopted_material_content` | `CandidateRef`；Domain服务另绑定其Domain身份 | 返回固定内容、类别、父题及来源引用、当前是否仍可入库和原因；过时内容可追溯但不可继续入库 |
| `application_basis`／`target_definition` | `ApplicationRef`／目标依据引用；服务另绑定使用空间 | 返回Product拥有的采用范围及目标定义；不夹带Evaluation结果，防止目标读取反向递归调用评价 |
| `selectable_combinations` | 学生使用身份；可选教材ID | 只列成功应用组合及主要限制，不列未经应用的草稿 |
| `learning_spaces`／`space_material` | 后者需空间ID；管理员可按学生筛选 | 学生仅本人；教材读取固定当前采用与请求书页，不自动附入聊天上下文 |
| `space_goal`／`space_evidence` | 空间ID；Evidence详情另需证据引用 | Product目标要求结合Evaluation公开结果；目标内先看Evidence，再看来源事件，不直读私表 |
| `space_events`／`activity_trace` | 空间ID；可选活动／事件类型／时间范围 | 经事件与Interaction公开读取取得原始事实、轮次、步骤及运行依据；学生只见允许本人查看内容 |

1. 校验kind与必需定位，先做所有权及字段权限过滤，再查询，不能先读全部后在客户端隐藏。
2. 调用所属模块公开读取，固定所用采用／结果引用；列表以稳定顺序和游标返回，具体分页上限待接口设计。
3. 区分空列表、未知判断、处理中和读取失败；只有全部成功的部分可标为完成，不拼接跨空间个人状态。

**恢复与验收。** 读取故障可以重读，无写入去重要求；无权限、对象不存在与参数非法分别返回受保护错误。验证领域筛选、本人空间隔离、目标→Evidence→事件追溯及无数据不显示零掌握率。关闭窗口或历史浏览不触发新活动。

## 6. 数据、接口与业务验证

### 6.1 写入、事件与跨模块交接

每项变更操作在结果可见前共同保存业务写入、请求去重收据及需投递的事件；需持久执行时另保存OperationRun及Step完成位置，短事务维护不强制建立后台任务。跨Space异步工作仅由事件触发；等待、重试和通知补查采用系统底座合同，内部函数不再偷偷启动第二个OperationRun。

| 交接事件 | 最小业务载荷（共用事件信封不重复） | 接收结果与边界 |
| --- | --- | --- |
| `DomainIntakeRequested` | `scope_id`为导入资源全局身份；`domain_id:ID, intake_request_id:ID, candidate_refs:Ref[]`均指向已采用不可变内容；类别、父题关系及来源经§5.2公开读取 | Domain负责受理和待办；`producer=domain, result_kind=intake_receipt`返回候选与待办／分组映射，失败保留原提交等待恢复，不自动入库 |
| `MaterialCandidatesAdopted`／`MaterialImportDeleted` | 导入ID、替代／删除前后来源引用、受影响待入库提交引用 | Domain使尚未入库的过时来源不可继续；入库时仍复核来源有效性，防止通知延迟造成误入库 |
| `LearningTargetApplied` | `scope_id, target_basis_ref, applied_at, previous_target_basis_ref?, application_ref, cause_ref`；`cause_ref`引用原请求收据／事实事件，持久执行另带可选`caused_by_operation_run_id` | 首次空间建立或目标条件变化时触发Evaluation目标对照；只更新目标结果，不增权或历史重算。仅补教材来源说明不发此事件 |

本模块其他事件记录对应操作对象、前后引用、操作者与原因；学校／使用时长不由这些操作推算。账号及教材管理事件不冒充学生学习事件；空间创建和采用变化进入该空间只追加事件列表。

### 6.2 共同错误与待细化边界

`forbidden`拒绝越权，`invalid_request`说明字段／引用错误，`revision_conflict`要求重读，`identity_conflict`拒绝同请求换参数，`not_ready`说明使用／应用条件，`dependency_pending`表示事件已提交但对方未完成，`temporarily_unavailable`保留已提交结果等待技术恢复。空结果与合法未决不是技术失败；认证错误的外部披露由认证合同裁剪。

本轮已给出15项操作的输入、完成条件、Step和最低验收。仍须细化：凭据／首次管理员初始化协议；文件上传及限额；Agent候选Schema；草稿修订、批量采用和空间更新的存储事务；查询分页与传输接口。这些不改变本文件的产品权限或完成条件，不能由LLM临时决定。

端到端接收按以下顺序核对：账号与确认 → 批量接收 → 对话及候选采用 → 领域受理／入库 → 章节关联与目标 → 检查及确认应用 → 学生创建／进入空间 → 只读追溯。每项最小验收须配正常和本节失败分支；当前只定义验收输入，不声称已有实现或测试通过。

### 6.3 修订记录

| 版本 | 日期 | 修改 |
| --- | --- | --- |
| v0.3 | 2026-11-12 | 定义15项产品业务Operation、共享输入类型、事件交接及恢复和验收边界；保留未选型的实现细节待设计 |
