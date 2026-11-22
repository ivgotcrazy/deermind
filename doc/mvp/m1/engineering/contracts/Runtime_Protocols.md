# M1 运行接口与 WebSocket 协议

> **版本**：v0.9<br>
> **状态**：设计合同；已实现范围和进度见实施计划<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-22<br>
> **修订说明**：v0.8 → v0.9，落实教材范围的文件上传、状态查询和原件回读<br>

公共运行只提供通用认证、收据、派发、等待与回传；所有者仍决定业务处理和可展示内容。HTTP路径相对/api/m1，WebSocket /ws使用deermind.v1。底层订阅与发布格式见[事件分册](Event_Messages.md)。

<a id="r01"></a>
## R01 登记文件上传

`POST /file-uploads` → `infrastructure.files/register_upload`。权限：管理员教材用途；本人学习附件用途。处理规则：[文件处理规则](../Infrastructure_and_Deployment_Design.md#23-文件对象与上传合同)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `purpose` | material_source/student_attachment | 是 | 本稿HTTP用途登记；技术AI/Temporal载荷不从浏览器上传 |
| `original_name` | string | 是 | 只供显示，不作路径 |
| `declared_media_type` | string | 是 | 服务器另核验真实类型 |
| `declared_byte_size` | int | 是；非负 | 按文件限额校验 |
| `domain_ref` | ObjectRef(domain) | 教材用途是 | 无领域不发上传身份 |
| `import_id` | ID | 教材补页时是 | 已有导入归属 |
| `scope_id` | ID | 学习附件是 | 本人学习空间 |

成功：200，直接返回下表对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `upload_id` | ID | 是 | 稳定上传身份 |
| `state` | receiving | 是 | 未接收完整字节 |

处理边界：普通登记；相同账号/用途/request_id返回原身份；不创建教材，不调用LLM。公开用途代码是本稿待审映射，不新增附件能力。

E02-07仅接线`material_source`。重查同一登记返回当前UploadView，含state、receipt和error。字节大小必须大于0。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；payload_too_large。

请求／查询参数（示意数据）：

```json
{
  "request_id": "upload-01",
  "purpose": "material_source",
  "original_name": "book.pdf",
  "declared_media_type": "application/pdf",
  "declared_byte_size": 1024,
  "domain_ref": {
    "kind": "domain",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  }
}
```

<a id="r02"></a>
## R02 上传完整字节

`PUT /file-uploads/{id}/content` → `infrastructure.files/write_upload`。权限：原上传者，重新核对用途权限。处理规则：[文件处理规则](../Infrastructure_and_Deployment_Design.md#23-文件对象与上传合同)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `body` | binary | 是 | 完整文件，Content-Type为申报类型；不是JSON字段 |

成功：200，直接返回下表对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `upload_id` | ID | 是 | 原上传 |
| `state` | ready | 是 | 核验并保存完成 |
| `receipt` | FileReceipt | 是 | 固定引用/hash/实际类型/大小 |

处理边界：200直接返回上传结果，无业务MutationReceipt；失败重传本文件。ready后字节不可覆盖，同内容重复返回原结果；没有分块续传。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；upload_busy；content_conflict；unsupported_media_type；payload_too_large。

请求／查询参数（示意数据）：

```json
{
  "说明": "请求体为文件二进制；此JSON不是上传正文"
}
```

<a id="r03"></a>
## R03 上传查询

`GET /file-uploads/{id}` → `infrastructure.files/read_upload`。权限：原上传者。处理规则：[文件处理规则](../Infrastructure_and_Deployment_Design.md#23-文件对象与上传合同)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `upload_id` | ID | 是 | 原上传 |
| `state` | receiving/ready/failed | 是 | 已保存状态 |
| `receipt` | FileReceipt或null | 是 | 只有ready有值 |
| `error` | ErrorResponse.error或null | 是 | 失败原因 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="r04"></a>
## R04 按原请求查回执

已接入的动作使用 `resource_kind=account`、`resource_id=原请求人账号UUID`、原 `request_id` 和当前 `X-Expected-Session`。

| 动作 | 结果及权限 |
| :--- | :--- |
| `product.record_usage_confirmation` | 学生本人原确认的 `ConfirmationResult`，其中 allowed/gaps 保留当时结果 |
| `domain.save_definition` | 原管理员新建领域的 D02 结果，仍须具备管理员权限 |

无收据返回 200/not_found，越权返回 404，未知动作返回 400，失效登录返回 401，读取故障返回 503 或 500。网页仅可补读已登记的原请求。

`GET /requests/receipt` → `runtime.read_request_receipt`。权限：原请求人，并通过所有者当前权限。处理规则：[恢复规则](../System_Foundation_Design.md#55-重连与通知遗漏)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `action` | 登记动作名 | 是 | HTTP和WS映射同一owner/entry |
| `resource_kind` | 登记资源类型 | 是 | 例如learning_space/material_import |
| `resource_id` | ID | 是 | 作用范围 |
| `request_id` | RequestId | 是 | 首次发送使用的身份 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `receipt_state` | not_found/accepted/completed/rejected | 是 | 受理／提交投影；不替代业务及执行状态 |
| `receipt_ref` | ID或null | 是 | 所有者收据的稳定身份；原模块request_ref或receipt_id在此统一命名 |
| `business_state` | string或null | 是 | 所属入口的原业务状态，不把技术失败显示成处理中 |
| `result` | 原入口定义的结果或null | 是 | 按登记action返回已保存结果，与原写入口result类型一致 |
| `error` | ErrorResponse.error或null | 是 | 已保存的处理失败／拒绝；本次查询自身失败使用HTTP错误响应 |
| `execution_ref` | ID或null | 是 | 适用后台工作 |
| `execution_state` | string或null | 是 | 底座执行状态，与业务状态分开 |
| `result_refs` | Ref[] | 是 | 已保存可取结果 |
| `allowed_actions` | string[] | 是 | 当前允许动作；不是额外授权 |

底座按原action、资源、request_id及已验证发起者委托所有者查找，不要求浏览器预先知道receipt_ref。HTTP查询使用所有者入口名；WS动作按动作表转换，例如learning.input映射interaction.handle_input。只返回原请求人当前可读的结果，不遍历私表、不重新派发。

| 所有者情况 | 统一投影 |
| --- | --- |
| 尚无可读收据 | receipt_state=not_found；所有可空字段为null，引用和动作数组为空；读取故障不能用not_found代替 |
| 已可靠受理但业务未提交 | receipt_state=accepted；business_state和execution_state照实返回；失败／停止不能仅凭accepted显示为处理中 |
| 业务已提交，包括Domain committed | receipt_state=completed；返回原入口result；关联AI仍执行或失败不撤销提交 |
| 已明确业务拒绝 | receipt_state=rejected；error保留原因，不自动重做 |

Domain和Product分别提供[D13](Domain_API.md#d13)、[P26](Product_API.md#p26)内部投影：state映射business_state，result／error原样按授权返回，runtime_ref映射execution_ref；receipt_state由登记的所有者适配器按上表投影。其他入口沿其原写结果映射，不另造业务状态。not_found不自动生成新请求。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "action": "interaction.handle_input",
  "resource_kind": "learning_space",
  "resource_id": "00000000-0000-4000-8000-000000000100",
  "request_id": "chat-01"
}
```

<a id="r05"></a>
## R05 空间事件列表

`GET /learning-spaces/{scope_id}/events` → `runtime.query_events`。权限：本人可见内容/获授权管理员；补齐既有空间事件查询。处理规则：[事件查询规则](../System_Foundation_Design.md#25-查询与读取边界)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `event_types` | 登记事件名[] | 否 | 等值筛选，不允许脚本 |
| `subject_ref` | Ref | 否 | 活动/作答等主体 |
| `correlation_id` | ID，各可选 | 否 | 链路及直接前因 |
| `causation_event_id` | ID，各可选 | 否 | 链路及直接前因 |
| `recorded_from` | Timestamp，各可选 | 否 | 记录时间闭开区间[from,to) |
| `recorded_to` | Timestamp，各可选 | 否 | 记录时间闭开区间[from,to) |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | EventSummaryView[] | 是 | 授权摘要；字段定义见下文，不返回完整payload/records |
| `upper_seq` | int | 是 | 首屏已提交上界 |
| `next_cursor` | string或null | 是 | 绑定筛选和上界 |

处理边界：只读；正式事件无编辑/删除接口。过滤列表不能作为Evaluation连续扫描游标。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "event_types": [
    "AnswerSubmitted"
  ],
  "limit": 20
}
```

EventSummaryView包含event_id、event_type、schema_version、scope_kind、scope_id、scope_event_seq、occurred_at、recorded_at、time_basis、owner_ref、subject_refs及summary:string；身份/关系先经授权过滤，summary由登记模板及可见字段生成，不调用LLM。EventDetailView在此基础上增加payload_view:已授权类型化动作字段、record_views:{record_id,record_type,schema_version,content:已授权字段对象,visible_paths:string[],visibility:complete/partial}[]。partial仅表示授权裁剪，不表示原事件损坏；记录身份本身不可见时整条省略。记录内容不返回文件storage_key、私有模型输入或其他人的字段。

浏览器视图不冒充完整FactRecord DTO，不用于重建；未知事件类型只可返回获准摘要，不能兜底透传原payload。服务端按[正文§2.2](Event_Facts.md#22-原文读取用途与权限)选择student_history或admin_review，浏览器不提交purpose。

<a id="r06"></a>
## R06 精确事件读取

`GET /learning-spaces/{scope_id}/events/{event_id}` → `runtime.query_events/read_event`。权限：本人可见内容/获授权管理员。处理规则：[事件查询规则](../System_Foundation_Design.md#25-查询与读取边界)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `event` | EventDetailView | 是 | 已授权事实片段；不是完整内部事件信封，字段定义见R05后的公共视图 |
| `source_content_refs` | EventPartRef[] | 是 | 仅给有权继续读取的来源；后续请求重新授权 |

处理边界：对外查询入口先核验权限、限定来源和字段，再由read_facts按范围及EventPartRef读取；事件列表返回摘要及获授权片段，事件ID不授予整个空间或私有记录的读取权限。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="r07"></a>
## R07 授权读取文件

`GET /resource-files` → `owner.query_file → infrastructure.files/read_file`。权限：当前资源有权读取者；补齐基础设施§2.4既有所有者查询入口。处理规则：[文件展示规则](../Infrastructure_and_Deployment_Design.md#24-授权展示与派生资源)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `owner_ref` | Ref | 是 | 教材来源、当前题面附件、已提供消息附件等具体业务引用；不接受任意路径/URL |
| `storage_ref` | ID | 是 | 必须由该业务引用确切引用 |
| `view` | source/statement/provided | 是 | 与该资源已授权展示用途一致 |

响应：200，文件字节流及响应头如下；不是JSON对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `body` | binary | 是 | 已核验原文件或固定派生文件字节 |
| `Content-Type` | HTTP响应头 | 是 | 实际媒体类型 |
| `Content-Length` | HTTP响应头 | 是 | 返回字节数 |
| `Cache-Control` | HTTP响应头 | 是；no-store | 私有文件不得共享缓存 |

处理边界：200是文件字节而非JSON。网关只向已登记所有者派发；所有者核对引用、用途及空间采用，再调用文件适配。不能借题面引用读取参考答案，不能读取Temporal或AI内部载荷。

教材来源参数`owner_ref`用JSON字符串传输，owner=product、type=material_source，view=source。服务检查管理员会话、活跃导入及与storage_ref的精确对应，再校验文件完整性。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；forbidden；not_found；source_unavailable。

请求／查询参数（示意数据）：

```json
{
  "owner_ref": {
    "owner": "product",
    "type": "material_source",
    "id": "00000000-0000-4000-8000-000000000011"
  },
  "storage_ref": "00000000-0000-4000-8000-000000000012",
  "view": "source"
}
```

## WebSocket 信封

所有帧为UTF-8 JSON对象。下表是传输字段定义，业务payload只引用对应API请求结构。未知type/action拒绝，不透传任意函数或Operation名称。

| 字段 | 类型 | 必填条件 | 含义 |
| --- | --- | --- | --- |
| type | string | 所有帧 | 下表登记的帧种类 |
| frame_id | RequestId | 客户端命令/订阅/健康帧；对应回执原样回传 | 单次传输关联，不作为业务防重键 |
| request_id | RequestId | command及其receipt/error | 同一业务请求跨断线保持；业务字段payload不重复声明不同request_id |
| action | string | command | 已登记动作名 |
| resource | {kind:string,id:ID} | command | 已验证作用范围；不是权限声明 |
| payload | 对应API正文去除request_id的对象 | command | 类型由action唯一决定；路径资源由resource确定 |

| type | 方向 | 此帧其余字段（未列字段不接收） | 行为 |
| --- | --- | --- | --- |
| hello | 客户端→服务端 | csrf_token:string、session_id:ID | 第一帧；比对Cookie当前身份和来源 |
| ready | 服务端→客户端 | connection_id:ID、server_time:Timestamp | 只确认连接可用，不替业务数据同步 |
| command | 客户端→服务端 | 上述公共字段 | 每帧重新授权和作用范围校验 |
| receipt | 服务端→客户端 | frame_id、request_id、state:accepted/completed、owner_receipt_ref:ID、execution_ref:ID\|null、result_refs:Ref[] | 可靠受理/保存后才发送；最终结果另读 |
| error | 服务端→客户端 | frame_id:string\|null、request_id:string\|null、error:ErrorResponse.error、acceptance:not_accepted/unknown | 传输未知先查原收据；不返回模型正文/服务堆栈 |
| watch | 客户端→服务端 | frame_id、watch_id:ID、resource:{kind,id}、views:string[] | 登记授权范围内有限刷新订阅 |
| watch_ready | 服务端→客户端 | frame_id、watch_id、resource、views | 客户端随后补读权威数据；不表示订阅前消息都已推送 |
| unwatch | 客户端→服务端 | frame_id、watch_id | 幂等取消；返回unwatch_ready(type,frame_id,watch_id) |
| unwatch_ready | 服务端→客户端 | frame_id、watch_id | 确认取消，不需要重新发送resource或views |
| changed | 服务端→客户端 | watch_id、resource、views、request_id:ID\|null | 只通知重新查询，不携聊天/Evidence/概率正文 |
| ping / pong | 双向 | frame_id | 保活；不延长登录到期，不记学习事件 |
| resync_required | 服务端→客户端 | watch_id:ID\|null、reason:string | 重新建立订阅并补读，不重发新业务请求 |

### 动作与授权视图

| action | 所有者与HTTP合同 | 权限与路径参数 |
| --- | --- | --- |
| learning.input | [I03](Interaction_API.md#i03) | 本人；resource.kind=learning_space |
| learning.answer | [I05](Interaction_API.md#i05) | 本人；source_input_ref只能由程序内部设置 |
| learning.activity_action | [I04](Interaction_API.md#i04) | 本人；停止仍按target_input_id校验 |
| learning.proactive_response | [I08](Interaction_API.md#i08) | 本人；payload另带task_id定位待响应任务 |
| learning.presentation | [I06](Interaction_API.md#i06) | 本人；request_id与presentation_id保持同一重试身份 |
| material.input | [P09](Product_API.md#p09) | 管理员；resource.kind=material_import |

上述六个动作在HTTP和WS使用同一业务大小校验：将输入投影为本册command，计量时frame_id固定取request_id，其余action、resource和payload完整保留；采用无多余空白、不转义非ASCII字符的UTF-8 JSON计量。投影总字节不得超过[基础设施§4.5 S03](../Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)。HTTP仍须符合H02，实际WS消息还须符合S03的传输限制；额外空白或过长frame_id不能绕过传输检查。

超限在受理前拒绝：HTTP返回413，WS返回error.code=payload_too_large、acceptance=not_accepted；无法安全解析超大消息时可关闭连接。客户端保留草稿，文件沿上传接口；不截断正文、不自动改走HTTP。H02 的 2 MiB 和 S03 的 64 KiB 已确认。

watch的最小view登记：learning_space允许conversation、activity_tree、goal、events；material_import允许messages、contents、candidates、intake。所有者校验角色与字段权限；订阅不扩大读取能力。原请求人可以同时取得对应收据变化提示，跨账号后清理旧订阅。浏览器不订阅原始NATS主题。

```json
{
  "type": "command",
  "frame_id": "frame-01",
  "request_id": "chat-01",
  "action": "learning.input",
  "resource": {
    "kind": "learning_space",
    "id": "00000000-0000-4000-8000-000000000100"
  },
  "payload": {
    "input": {
      "text": "给我一点提示",
      "attachment_refs": [],
      "explicit_refs": []
    }
  }
}
```

```json
{
  "type": "receipt",
  "frame_id": "frame-01",
  "request_id": "chat-01",
  "state": "accepted",
  "owner_receipt_ref": "00000000-0000-4000-8000-000000000101",
  "execution_ref": "00000000-0000-4000-8000-000000000102",
  "result_refs": []
}
```

错误帧示例（同一error对象也用于HTTP响应）：

```json
{
  "type": "error",
  "frame_id": "frame-02",
  "request_id": "chat-02",
  "error": {
    "code": "interaction_busy",
    "message": "正在处理上一条，请稍后发送。",
    "issues": [],
    "retryable": false
  },
  "acceptance": "not_accepted"
}
```

断线时已受理工作继续处理。重新 hello→ready→watch→watch_ready 后补读正式消息、当前状态和原请求收据。changed可合并或重复，客户端按实体身份/修订合并，不按通知数量新增消息。服务端回复按已定规则检查保存后整条提供，WS不直传未经核对的模型token。

## 内部运行端口

下列不是HTTP接口。字段保持[公共运行§1—4](../System_Foundation_Design.md#1-共用合同与调用边界)的唯一执行合同，本分册登记调用边界；不会在事件payload中传执行函数。

| 端口 | 使用者及作用 | 唯一字段与执行合同 |
| --- | --- | --- |
| read_result / read_publication / publish_result | 注册生产者及获授权消费者 | [公共运行§1.2](../System_Foundation_Design.md#12-公开操作) |
| register_wait / cancel_wait | 消费模块 | [公共运行§3.1](../System_Foundation_Design.md#31-等待记录) |
| append_events / read_facts / apply_projection / rebuild_projection | 注册生产者、获授权读取方或维护处理器；不开放任意事件写HTTP入口 | [公共运行§2](../System_Foundation_Design.md#2-全局事件的追加与查询)、[正文合同](Event_Facts.md) |
| query_metadata / scan_scope | 获授权读取方；完整扫描与界面筛选分开 | [公共运行§2.2](../System_Foundation_Design.md#22-各范围事件顺序与有界读取)、[§2.5](../System_Foundation_Design.md#25-查询与读取边界) |
| read_operation_run | 原工作授权读取方 | [公共运行§1.3](../System_Foundation_Design.md#13-operationstep与operationrun) |
| read_execution / retry_execution / read_handoffs / retry_handoff | 受控维护入口；不新增浏览器任意执行权限 | [公共运行§4.5](../System_Foundation_Design.md#45-失败收尾停止与授权恢复) |

受理、重试、恢复、停止、投递和清理仍沿公共运行/基础设施实现合同。未新增开放给浏览器的任意执行启动、概率写入或后台维护接口。

HTTP请求收据中的action采用登记的所有者入口名；WS动作名先按本册映射为同一个入口名，再生成去重键。两种通道不能为同一次输入建立两份业务请求。R07返回二进制，R02请求体为二进制，两者的字段表描述流和HTTP头，不是JSON包装。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 统一收据结果投影、WS错误内层与跨通道输入计量。见MVP决定登记§95。 |
| v0.3 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.4 | 2026-11-15 | 补齐事件正文、记录映射、状态或读取边界；容量及保留候选仍待确认。仅文档修订，见MVP决定登记§98。 |
| v0.5 | 2026-11-16 | 实现R04本人使用确认收据；明确当前登记动作和读取边界 |
| v0.6 | 2026-11-22 | 区分公开事件视图及内部读取合同 |
| v0.7 | 2026-11-22 | 登记已确认的消息上限与连接恢复顺序 |
| v0.8 | 2026-11-22 | 登记 E02-01 新建领域收据的原请求、账号范围和结果 |
| v0.9 | 2026-11-22 | 落实教材范围的文件上传、状态查询和原件回读 |
