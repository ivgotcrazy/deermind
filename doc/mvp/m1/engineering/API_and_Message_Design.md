# M1 API 与消息设计

> **版本**：v0.1<br>
> **状态**：接口与消息详细设计稿，待用户审阅；未编码<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-15

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
| [事件消息](contracts/Event_Messages.md) | 正式事件信封、逐类型payload、生产/消费关系、NATS投递格式和版本处理 |

每份分册中的P/D/I/E/R编号只用于文档定位，不进入业务请求。

所有HTTP路径相对`/api/m1`；WebSocket为同源`/ws`，协议名`deermind.v1`。内部端口是程序调用，不因列入分册自动成为HTTP接口。Temporal任务、AI提示与模型响应不是业务事件。

## 2. 认证回执与错误

浏览器身份来自`__Host-dm_session` Cookie。除登录、当前会话读取外，API携带`X-Expected-Session`；写请求另携`X-CSRF-Token`。两个头均由当前会话查询取得，不是可自行声明的权限。登录/退出例外见Product分册。所有私有响应`Cache-Control: no-store`；内部服务使用程序建立的access_context，不借学生Cookie调用。

| 结构 | 字段 | 规则 |
| --- | --- | --- |
| MutationReceipt | request_ref:ID、result:该入口结果 | 200只确认该业务提交；作答已保存不等于反馈或评价已完成 |
| AcceptedReceipt | request_ref:ID、state:"accepted"、runtime_ref:ID | 202只在可靠保存受理与派发后返回；不包含尚未核对的AI正文 |
| ErrorResponse | error:{code:string,message:string,issues:Issue[],retryable:boolean}、request_ref?:ID | 可追溯引用放在授权的Issue中；不返回堆栈、密钥或私有Prompt |
| Issue | code:string、path:string、message:string、related_ref?:Ref | path定位请求字段/内容块；related_ref只在当前调用者可读取时返回 |

查询成功返回分册指定对象，不再套一层含义不明的data。写请求的最终result类型沿该入口定义；后台技术状态与业务状态分别返回。首次回执丢失，用原request_id查询公共收据，不能要求客户端先知道丢失的request_ref。

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
| Ref | {owner,type,id,revision?或version?,path?} | 具体所有者若已有专用引用形状，沿专用形状；不可将任意JSON当引用；持有引用不等于授权 |
| CandidateRef | {candidate_id,candidate_revision,basis_revision} | 固定采用候选；版本不可省略 |
| PlanRef | {plan_id,revision} | 学生确认和继续均指明精确题单修订 |
| FileReceipt | {storage_ref:ID,media_type:string,byte_size:int,sha256:string} | 已完整保存；大小非负，sha256为64位小写十六进制；内部文件路径不外露 |
| RichContent | Domain§1.4的schema_version、role、blocks、data_tables、source_refs结构 | 公式、图表随内容所属用途；题面中不得夹参考答案 |
| ResultKey | {scope_id,trigger_event_id,producer,result_kind} | 四者完全匹配；不能只用correlation_id匹配结果 |
| GoalProcessing | available/pending/failed | Evaluation目标查询状态；已有结果时可同时存在后续pending，不与掌握结论合并 |
| Processing | {state:not_started/pending/completed/failed,execution_ref:ID或null,failure_ref:Ref或null} | 新查询视图的技术进度；不改模块原业务状态，GoalProcessing另用目标查询合同 |

同一字段组合的条件以分支说明为准；未使用分支的字段不得发送。

本稿中字段表的“是”表示不可省略；“可null”另写明。缺省仅适用于标明可省略的字段；所有数组区分[]与未知。请求未知字段拒绝；客户端不能传principal_id、role、权限、概率、达标结论或任意Operation名称。嵌套业务结构以分册直接链接的定义为准，不从数据库JSON列猜结构。

枚举和字段名称是待审的接口设计；不可据此更改现行产品行为。示例只演示格式，不是实际账号、事件或验收记录。

## 4. 重复请求与分页

写请求稳定身份由所有者的action、scope、request_id及已验证发起者组成；HTTP与WebSocket映射到同一owner/entry，不产生两套身份。登录不重放旧凭据，上传字节以upload_id校验，显示回执以presentation_id防重，其他例外分册逐项说明。

| 读取种类 | 顺序与游标 |
| --- | --- |
| Domain对象/待办 | object_id/item_id升序；catalog_revision变化返回read_range_changed |
| 教材、目标、空间列表 | 稳定ID升序，游标绑定调用者和筛选；这是当前视图，允许页间内容更新。新建较小ID需刷新才能看到，不承诺跨页数据库快照 |
| 聊天 | message_seq/seq升序；首屏固定upper_seq，续页同范围。锚点与活动筛选绑定游标 |
| 空间事件 | space_event_seq升序，固定已提交上界；事件只追加，缺页以查询补齐 |
| Evidence/概率修订 | 先固定发布快照或目标结果，再分页其引用集合；不能翻页时切到最新结论 |

通用字段为cursor?:string、limit?:int；返回items及next_cursor:string|null。读取需保持同一依据时另返回read_token或upper_seq。无游标首次读取，游标携带已绑定筛选，调用者不得中途改筛选；修改后重新开始。每页条数、响应字节与超限行为引用[基础设施§4.5](Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)，候选数值仍待审，不在本册批准新数值。

## 5. 三类消息的边界

HTTP承担查询与普通写入；WebSocket command映射同一业务入口，changed只通知补读；NATS只交接后端事件引用。浏览器不能直接发布AnswerSubmitted等正式事件，也不能从NATS消费原文。业务事件与聊天消息分别保存；通知、呈现回执、服务端正式提供内容是三种不同事实。

跨Space读取走有界授权端口；需要AI或加工的跨Space请求走事件。结果读取不启动生产任务，通知不代表结果可直接展示。消费方自行决定等待条件、期限和超时；本册不改变现有等待和恢复机制。

## 6. 审阅与接收

本批检查：原HTTP入口、WS动作和正式事件均能找到分册；请求/响应类型、权限、错误和幂等一致；消息字段不复制正文；Operation目录与数据库结构不变。静态检查结果记入DECISIONS §94，不代表实现或协议联调通过。

具体路径、字段、错误和新增查询投影供本轮审阅；通过后实现者据此编写OpenAPI/消息Schema及类型定义。本轮只维护文档，不另生成一份待手工同步的OpenAPI草稿。限额候选、技术选型版本继续由原责任文档审阅。

## 修订记录

| 版本 | 日期 | 修改 |
| --- | --- | --- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
