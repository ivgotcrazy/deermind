# M1 API 与消息设计

> **版本**：v0.5<br>
> **状态**：事件合同评审修订稿；容量与保留候选待确认，未编码<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-15<br>
> **修订说明**：v0.4 → v0.5，补正文、投影矩阵、状态及读取授权；容量候选待审，见MVP决定登记§98<br>

本册维护传输格式、入口目录和共同约束；分册逐项定义请求、响应与事件。模块文档维护业务处理、AI输入输出语义、提交和恢复规则；数据库分册维护物理字段。接口对象不直接等于数据库行。

本稿沿用现有入口与授权边界。原先仅有业务查询名称的入口，在分册标为“补齐查询投影”；这些路径和字段是本次待审设计，不表示已获批准或已经实现。没有增加AI Operation、算法或新的管理页面。

## 1. 分册与覆盖

| 分册 | 定义范围 |
| --- | --- |
| [Product API](contracts/Product_API.md) | 登录、教材助手、候选采用、章节关联、目标、应用和空间；账号维护等内部入口另列 |
| [Domain API](contracts/Domain_API.md) | 定义、实例、待入库、内容与依赖查询；内部来源与引用保护 |
| [Interaction API](contracts/Interaction_API.md) | 活动配置、学生输入、作答、控制、历史和评价原文读取 |
| [Evaluation API](contracts/Evaluation_API.md) | Claim定义、目标、Evidence与Belief只读查询；不提供概率写接口 |
| [运行协议](contracts/Runtime_Protocols.md) | 文件上传、请求收据、空间事件查询、WebSocket及内部结果/等待端口 |
| [事件正文](contracts/Event_Facts.md) | 完整事实DTO、对象身份/来源引用、逐事件记录矩阵、用途授权及重建边界 |
| [事件消息](contracts/Event_Messages.md) | 正式事件信封、逐类型payload、生产/消费关系、NATS投递格式和版本处理 |

每份分册中的P/D/I/E/R编号只用于文档定位，不进入业务请求。

所有HTTP路径相对`/api/m1`；WebSocket为同源`/ws`，协议名`deermind.v1`。内部端口是程序调用，不因列入分册自动成为HTTP接口。Temporal内部历史不是业务事实；AI实际请求和已知结果有专门留痕事件，不作为学生新表现。

## 2. 认证回执与错误

浏览器身份来自`__Host-dm_session` Cookie。除登录、当前会话读取外，API携带`X-Expected-Session`；写请求另携`X-CSRF-Token`。两个头均由当前会话查询取得，不是可自行声明的权限。登录/退出例外见Product分册。所有私有响应`Cache-Control: no-store`；内部服务使用程序建立的access_context，不借学生Cookie调用。

| 结构 | 字段 | 规则 |
| --- | --- | --- |
| MutationReceipt | request_ref:ID、result:该入口结果 | 200只确认该业务提交；作答已保存不等于反馈或评价已完成 |
| AcceptedReceipt | request_ref:ID、state:"accepted"、runtime_ref:ID | 202只在可靠保存受理与派发后返回；不包含尚未核对的AI正文 |
| ErrorResponse | error:{code:string,message:string,issues:Issue[],retryable:boolean}、request_ref?:ID | 可追溯引用放在授权的Issue中；不返回堆栈、密钥或私有Prompt |
| Issue | code:string、path:string、message:string、related_ref?:Ref | path定位请求字段/内容块；related_ref只在当前调用者可读取时返回 |

查询成功返回分册指定对象，不再套一层含义不明的data。写请求的最终result类型沿该入口定义；后台技术状态与业务状态分别返回。首次回执丢失，用原request_id查询公共收据，不能要求客户端先知道丢失的request_ref。

HTTP错误响应与WebSocket error帧共用同一个error对象（code、message、issues、retryable）。WS另带传输关联与acceptance；HTTP保留状态码和可选request_ref。客户端统一读取error，受理是否明确则按各自传输字段判断。

浏览器统一通过[运行协议R04](contracts/Runtime_Protocols.md#r04)按原请求查询收据和结果。Domain、Product的收据结构是底座向所有者读取的内部投影，不另开放模块收据路由；底座不直接读各模块私表。

| HTTP | code与使用条件 | 行为 |
| --- | --- | --- |
| 400 | invalid_request | 类型、字段、枚举或组合非法；未受理 |
| 401 / 403 | unauthenticated / forbidden；session_changed用409 | 不泄露无权对象内容；身份切换后重新获取会话 |
| 404 | not_found | 在当前授权范围内不存在；越权不靠返回其他对象解释 |
| 409 | request_conflict或identity_conflict、revision_conflict、version_conflict；各入口busy及基准冲突 | 旧合同错误名保留；两种请求冲突均为同键异文，不自动重发新请求 |
| 413 | payload_too_large | 按已接收请求/文件/消息限额拒绝，不截断一个图表或内容块 |
| 422 | 各分册业务拒绝 | 说明条件或引用缺口，不能以技术重试强行通过 |
| 429 | too_many_attempts | 仅认证尝试限额；不改账号状态 |
| 503 | temporarily_unavailable、resource_unavailable | 故障/资源不足明确返回；受理未知时先查原收据 |

202之后的失败保存在原收据，不修改先前HTTP响应。retryable只表明同一请求是否可在条件允许时再尝试，不授权增加额度、切模型或重做已经提交的部分。停止、恢复等权限和幂等规则仍由所有者执行。

## 3. 共用类型与字段规则

| 类型 | JSON表达 | 校验 |
| --- | --- | --- |
| ID / RequestId | 非空string | 持久对象ID由所有者分配；客户端输入/作答/呈现的防重身份按各入口明确产生；RequestId由调用者稳定生成。只作身份，不从名称、时间推断权限 |
| Revision / Sequence | integer | 非负整数，初值随资源定义；对象版本及正式修订≥1，尚无内容的source/content/basis_revision可为0；不得混用版本与序号 |
| Timestamp | UTC ISO 8601 string，例如2026-11-15T02:00:00Z | 发生、记录和客户端时间分开；未知允许处用null，不能用当前时间补猜 |
| ObjectRef | {kind,object_id,version} | kind=domain/task/solution/kc/task_instance；精确版本；定义见Domain§1.1 |
| TargetRef | {target_id:ID,revision:Revision} | 精确学习目标定义；不可用名称匹配 |
| ClaimRef | {claim_id,revision} | Task精确版本对应的评价定义修订 |
| EventPartRef | {event_id,record_id:string或null,path:string} | 原文片段；path为JSON Pointer；引用不授权，见事件正文合同§2 |
| Ref | {owner,type,id,revision?或version?,path?} | 具体所有者若已有专用引用形状，沿专用形状；不可将任意JSON当引用；持有引用不等于授权 |
| CandidateRef | {candidate_id,candidate_revision,basis_revision} | 固定采用候选；版本不可省略 |
| PlanRef | {plan_id,revision} | 学生确认和继续均指明精确题单修订 |
| FileReceipt | {storage_ref:ID,media_type:string,byte_size:int,sha256:string} | 已完整保存；大小非负，sha256为64位小写十六进制；内部文件路径不外露 |
| RichContent | Domain§1.4的schema_version、role、blocks、data_tables、source_refs结构 | 公式、图表随内容所属用途；题面中不得夹参考答案 |
| ResultKey | {scope_id,trigger_event_id,producer,result_kind} | 四者完全匹配；不能只用correlation_id匹配结果 |
| GoalProcessing | available/pending/failed | Evaluation目标查询状态；已有结果时可同时存在后续pending，不与掌握结论合并 |
| Processing | {state:not_started/pending/completed/failed,execution_ref:ID或null,failure_ref:Ref或null} | 新查询视图的技术进度；不改模块原业务状态，GoalProcessing另用目标查询合同 |

学习空间范围内，路径中的id、scope_id和Product的space_id表示同一个值；其他schema沿用scope_id，不做身份转换。通用合同中resource.kind或scope.kind不是learning_space时，resource.id或scope_id表示该类资源身份，例如教材导入ID，不能当作学习空间ID。

同一字段组合的条件以分支说明为准；未使用分支的字段不得发送。

本稿中字段表的“是”表示不可省略；“可null”另写明。缺省仅适用于标明可省略的字段；所有数组区分[]与未知。请求未知字段拒绝；客户端不能传principal_id、role、权限、概率、达标结论或任意Operation名称。嵌套业务结构以分册直接链接的定义为准，不从数据库JSON列猜结构。

枚举和字段名称是待审的接口设计；不可据此更改现行产品行为。示例只演示格式，不是实际账号、事件或验收记录。

内部EventEnvelope/FactRecord与对外授权事件视图区分，见[运行协议R05—R06](contracts/Runtime_Protocols.md#r05)。OpenAPI只生成后者的公开响应；客户端类型不得把可裁剪视图当作完整内部事实。正文、记录矩阵与用途权限唯一见事件正文分册。

## 4. 重复请求与分页

写请求稳定身份由所有者的action、scope、request_id及已验证发起者组成；HTTP与WebSocket映射到同一owner/entry，不产生两套身份。登录不重放旧凭据，上传字节以upload_id校验，显示回执以presentation_id防重，其他例外分册逐项说明。

| 读取种类 | 顺序与游标 |
| --- | --- |
| Domain对象/待办 | object_id/item_id升序；catalog_revision变化返回read_range_changed |
| 教材、目标、空间列表 | 稳定ID升序，游标绑定调用者和筛选；这是当前视图，允许页间内容更新。新建较小ID需刷新才能看到，不承诺跨页数据库快照 |
| 聊天 | message_seq/seq升序；首屏固定upper_seq，续页同范围。锚点与活动筛选绑定游标 |
| 空间事件 | scope_event_seq升序，固定已提交上界；事件只追加，缺页以查询补齐 |
| Evidence/概率修订 | 先固定发布快照或目标结果，再分页其引用集合；不能翻页时切到最新结论 |

通用字段为cursor?:string、limit?:int；返回items及next_cursor:string|null。读取需保持同一依据时另返回read_token或upper_seq。无游标首次读取，游标携带已绑定筛选，调用者不得中途改筛选；修改后重新开始。每页条数、响应字节与超限行为引用[基础设施§4.5](Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)，候选数值仍待审，不在本册批准新数值。

具有HTTP和WS两种承载的同一动作，使用相同业务输入限额；HTTP通用正文上限不扩大聊天容量。共同计量与拒绝规则见[运行协议](contracts/Runtime_Protocols.md#动作与授权视图)，数值仅引用基础设施H02／S03。

## 5. 三类消息的边界

HTTP承担查询与普通写入；WebSocket command映射同一业务入口，changed只通知补读；NATS只交接后端事件引用。浏览器不能直接发布AnswerSubmitted等正式事件，也不能从NATS消费原文。业务事件与聊天消息分别保存；通知、呈现回执、服务端正式提供内容是三种不同事实。

跨Space读取走有界授权端口；需要AI或加工的跨Space请求走事件。结果读取不启动生产任务，通知不代表结果可直接展示。消费方自行决定等待条件、期限和超时；本册不改变现有等待和恢复机制。

## 6. 审阅与接收

本批检查：原HTTP入口、WS动作和正式事件均能找到分册；请求/响应类型、权限、错误和幂等一致；事件保存完整事实、查询对象保留来源；Operation及页面不变，数据库新增投影进度和来源字段。首次分册检查见DECISIONS §94，本轮评审修订见[§95](../../DECISIONS.md#95-api与数据库评审修订)；静态检查不代表实现或协议联调通过。

具体路径、字段、错误和新增查询投影供审阅；通过后实现者定义DTO和路由，按§7导出OpenAPI及消息Schema。本轮只维护文档，不另生成一份待手工同步的OpenAPI草稿。限额候选、技术选型版本继续由原责任文档审阅。

## 7. OpenAPI与可执行合同

HTTP API采用OpenAPI规范；先审阅本册及分册的业务合同，实现时由Pydantic请求/响应DTO和FastAPI路由生成机器合同。不同时手写一套OpenAPI YAML；生成文件用于评审、客户端生成和兼容检查，不成为第二份手工事实源。设计阶段字段仍以本册和分册为准，本轮不创建Schema或生成代码。

### 7.1 定义与生成位置

| 内容 | 源位置（相对src/m1） | 产物或使用方 |
| --- | --- | --- |
| 业务请求、响应、分页与错误类型 | server/src/deermind下所属模块public | FastAPI路由、模块公开端口及校验 |
| HTTP方法、路径、状态码、认证和参数绑定 | server/src/deermind/entrypoints/api/routes | contracts/generated/http/openapi.json |
| 共用错误、通用引用和收据协议 | foundation/system/public；业务result仍由所有者定义 | 按需被各公开DTO引用 |
| HTTP客户端和类型 | 从OpenAPI生成 | clients/src/shared/api/generated |
| WS与事件版本Schema | 通用信封归底座，业务payload归所有者public | contracts/generated/websocket、events；浏览器只取公开WS类型 |
| 统一内容结构 | spaces/domain/public | contracts/generated/content；HTTP已引用的类型不另手工复制 |

公开DTO只含接口允许字段，不直接序列化SQLAlchemy行，也不把数据库的所有表自动公开。公开Schema模块导入无I/O；导出工具使用应用工厂的合同模式，只装配路由和类型，不连接PG/NATS/Temporal、不执行迁移、不启动Worker。

### 7.2 HTTP合同最低要求

每条实际HTTP路由登记稳定且唯一的`operationId`、所属模块tag、请求参数位置、正文媒体类型、成功/失败响应及示例。这里的OpenAPI operation是HTTP术语，与九项AI Operation不是同一目录；不得借此增加AI能力。内部函数和消息处理器不生成HTTP路径。

认证声明采用现行Cookie会话；`X-Expected-Session`、`X-CSRF-Token`按各入口要求分别登记。二者不伪装成角色权限；OpenAPI展示不能代替服务端授权。200/202、统一ErrorResponse及框架校验错误都按本册§2登记；默认校验错误通过异常适配转换，不能出现未声明的另一种错误外壳。

必填、可省略、可null分别表达；请求未知字段拒绝。文件上传媒体类型、大小约束、下载响应头与字节返回按已有合同；禁止统一套JSON响应模型。多分支对象使用明确的区分字段；不以任意object掩盖已定义业务结构。OpenAPI规范版本随接收的FastAPI及生成器组合固定，不手工修改生成器输出的版本声明。

### 7.3 变更与兼容检查

1. 修改所属业务合同并确认行为；在同一变更中调整DTO、路由和对应测试。
2. 通过`scripts/export-contracts.sh`导出OpenAPI及消息Schema。输出顺序稳定，文件中不注入随机值、环境秘密或每次变化的时间戳；来源提交和hash放manifest。
3. 与上一接收基线比较。删除接口/字段、增加必填输入、收窄枚举、改变空值、认证或响应语义均需显式评审；新增响应枚举也检查客户端穷举分支。机器diff不能替代语义审阅。
4. 生成TypeScript客户端及公开消息类型，执行类型检查和接口/组件合同测试。共用DTO只生成一份可复用类型，不在WS或页面里手写副本。
5. CI重新生成并检查工作区差异；生成物陈旧、operationId重复、响应未声明或新增未经登记路由均阻止发布。

新增字段不要求一次全盘重写历史事件；事件/正文Schema版本仍按原合同保留解码器。HTTP变更与事件兼容分别检查，不能只因OpenAPI通过就判定NATS、WS和历史事实兼容。HTTP授权、字段裁剪、CSRF和幂等还需实际接线测试。

客户端请求头、会话、错误提示、稳定请求ID和受理不明处理放手写包装层；生成器不能默认启用写请求重试。生成器及版本在接线前确认，方向参照[FastAPI SDK生成](https://fastapi.tiangolo.com/advanced/generate-clients/)。OpenAPI、WS Schema和事件合同不新增API网关、消息平台或算法配置页面。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 统一公共收据、HTTP／WS错误内层、范围身份和共同输入限额。见MVP决定登记§95。 |
| v0.3 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.4 | 2026-11-15 | 同步工程目录、职责依赖、Vue客户端及OpenAPI生成边界。仅文档修订，见MVP决定登记§97。 |
| v0.5 | 2026-11-15 | 补齐事件正文、记录映射、状态或读取边界；容量及保留候选仍待确认。仅文档修订，见MVP决定登记§98。 |
