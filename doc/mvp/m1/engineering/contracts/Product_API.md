# M1 Product API

> **版本**：v0.10<br>
> **状态**：设计合同；已实施范围和进度见实施计划<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-23<br>
> **修订说明**：v0.9 → v0.10，登记学习工作区只读恢复与教材来源<br>

共同类型、认证头、回执和错误见[总册](../API_and_Message_Design.md)。本分册定义前后端载荷；内容提取、采用和应用规则仍由Product负责。

来源通则：业务ID及查询响应维持现有形状，来源字段source_event_id:ID指向生成该对象的事实；正文片段返回EventPartRef。正文读取来自事件及固定附件，业务表只是投影。内部适配器负责本业务用途和范围，不从私有表提供独立原文；写请求仍走原业务入口，客户端不能指定事件内容或source_event_id。

教材助手查询可显示runtime组合的running/waiting，但material_turn.state只保存已提交业务结果；该显示状态不是新增业务事实。候选决定状态均由事件重建，见[正文§3.3](Event_Facts.md#33-业务状态与执行状态)。

## 响应对象

| 类型 | 完整字段与含义 | 规则来源 |
| --- | --- | --- |
| AccountView | account_id:ID、display_name:string、role:student/admin、usage_gaps:Issue[] | Product§2；不含凭据或监护身份正文 |
| TextbookRow | textbook_id:ID、domain_ref:ObjectRef、title:string、edition:string\|null、import_id:ID、status:active/deleted、metadata_revision:Revision、application_refs:Ref[] | 当前管理信息；学生只经采用读取公开教材 |
| ImportView | import_id:ID、textbook:TextbookRow、revision:Revision、source_revision:int、content_revision:int、chapters:ChapterRow[]、active_request_ref:ID\|null、deletion_scope_ref:Ref\|null | 删除确认范围由服务端生成；已应用时不提供可删除确认 |
| ChapterRow | chapter_id:ID、parent_id:ID\|null、title:string、order:int、page_refs:Ref[]、revision:Revision | order只定显示顺序，不作身份 |
| MaterialMessage | message_id:ID、seq:int、role:user/assistant、body:RichContent、explicit_refs:Ref[]、turn_ref:ID、created_at:Timestamp | 正式正文；进度不反复改写正文 |
| CandidateBatchView | Product§3.4.3的完整CandidateBatch，另含decision_state:pending/adopted/declined/superseded、decision_revision:Revision | read_set/write_set及coverage沿原结构；不返回私有Prompt |
| TargetView | target_ref:{target_id,revision}、textbook_id:ID、title:string、items:GoalItem[]、chapter_basis_refs:Ref[]、gaps:Issue[] | GoalItem沿Product§4.2.1；保存不等于应用 |
| SpaceRow | space_id:ID、student_id:ID、textbook_id:ID、target_id:ID、current_adoption_ref:Ref、title:string | 仅本人或获授权管理员；列表不推算掌握率 |
| AdoptionView | space_id:ID、adoption_ref:Ref、application_ref:Ref、target_basis_ref:Ref、textbook_content_ref:Ref、target_ref:Ref | 固定采用内容；既有活动不因当前采用更新而换依据 |

表中的content及候选结构直接引用[Product§3.4](../Product_Application_Design.md#34-productconverse_material_assistant持续对话解析与纠错)，GoalItem引用[§4.2.1](../Product_Application_Design.md#421-目标条目)。列表行不返回文件系统路径、秘密或整本解析正文。

### 嵌套查询类型

| 类型.字段 | 类型 | 必填／缺省 | 含义 |
| --- | --- | --- | --- |
| ParentBinding.candidate_ref | CandidateRef | 是 | 正在提交的解法候选 |
| ParentBinding.parent_candidate_ref | CandidateRef | 三种父题引用恰一 | 同批提交的父题 |
| ParentBinding.parent_item_ref | Ref | 三种父题引用恰一 | 此前已登记的父题待办 |
| ParentBinding.task_instance_ref | ObjectRef(task_instance) | 三种父题引用恰一 | 已入库父题精确版本 |
| IntakeMapping.candidate_ref | CandidateRef | 是 | 原提交项 |
| IntakeMapping.intake_item_ref | Ref | 是 | Domain受理的待办 |
| IntakeMapping.group_ref | Ref | 是 | 父题/解法的显示分组 |
| IntakeMapping.parent_ref | Ref或null | 是 | 解法关联的父题；其他项null |
| CourseOption.textbook_id | ID | 是 | 教材身份 |
| CourseOption.title | string | 是 | 教材名 |
| CourseOption.target_id | ID | 是 | 目标身份 |
| CourseOption.target_title | string | 是 | 目标名 |
| CourseOption.application_ref | Ref | 是 | 固定已应用结果 |
| CourseOption.limitations | Issue[] | 是 | 用途限制；无则[] |
| CourseOption.existing_space_id | ID或null | 是 | 本人已选同组合时返回原空间 |

<a id="p01"></a>
## P01 登录

`POST /auth/sign-in` → `product.sign_in`。权限：匿名同源；固定角色取账号记录。处理规则：[Product处理规则](../Product_Application_Design.md#23-productsign_in登录原账号)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `login_identifier` | string | 是 | 登录标识 |
| `password` | string | 是 | CredentialProof的受保护凭据；不进入普通日志/收据 |
| `return_to` | string | 否 | 仅允许站内路径 |

成功：200，直接返回下表对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `account` | AccountView | 是 | 当前身份 |
| `expires_at` | Timestamp | 是 | 会话固定到期 |
| `return_to` | string或null | 是 | 已校验跳转 |

处理边界：这是认证响应，直接返回表内对象并Set-Cookie，不套业务MutationReceipt、不回传session_token；登录丢回执先查当前会话。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；登录失败统一unauthenticated；too_many_attempts不改账号状态。

请求／查询参数（示意数据）：

```json
{
  "login_identifier": "student001",
  "password": "<仅经受保护连接提交>"
}
```

<a id="p02"></a>
## P02 当前会话

`GET /auth/session` → `product.sign_in/session`。权限：当前Cookie；不要求X-Expected-Session。处理规则：[Product处理规则](../Product_Application_Design.md#27-认证端口与请求保护)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `account` | AccountView | 是 | 缺确认也可读取身份 |
| `session_id` | ID | 是 | 诊断与预期身份，不是登录凭据 |
| `csrf_token` | string | 是 | 仅当前会话可取 |
| `expires_at` | Timestamp | 是 | 到期时刻 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="p03"></a>
## P03 退出

`POST /auth/sign-out` → `product.sign_in/sign_out`。权限：当前会话与CSRF；已无有效会话时幂等清Cookie。处理规则：[Product处理规则](../Product_Application_Design.md#26-退出重置与初始化)。

除路径与共同认证头外，无业务请求字段。

成功：200，直接返回下表对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `signed_out` | boolean | 是；true | 已撤销当前会话 |

处理边界：200直接返回signed_out；清Cookie。重复退出成功，不取消已经受理的后台工作。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="p04"></a>
## P04 创建教材导入

`POST /material-imports` → `product.receive_material/new_import`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#31-productreceive_material接收整批或补充材料)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `domain_ref` | ObjectRef(domain) | 是 | 必须是可用领域 |
| `title` | string | 是 | 教材名 |
| `source` | string | 是 | 来源说明 |
| `edition` | string或null | 否；null | 未知版次不猜 |
| `files` | MaterialFile[] | 是；非空 | 每项receipt:FileReceipt、original_name:string、order:int；已完成文件且顺序不重复 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `textbook_id` | ID，各一 | 是 | 新建教材与持续导入身份 |
| `import_id` | ID，各一 | 是 | 新建教材与持续导入身份 |
| `received` | Ref[] | 是 | 实际接收的原件引用 |
| `failed` | Issue[] | 是 | 未接收项及原因 |
| `source_revision` | int | 是 | 原件集合修订 |

处理边界：原件先上传；这里只接收合法文件收据，保存成功不启动解析。全部不可接收时422；可接收部分按received/failed明确返回。

原请求收据沿R04，action为`product.receive_material`。新建使用领域ID和`resource_kind=domain`，补充使用导入ID和`resource_kind=material_import`。回读返回最初提交结果。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；缺领域invalid_reference；未完成/越权文件source_unavailable。

请求／查询参数（示意数据）：

```json
{
  "request_id": "import-01",
  "domain_ref": {
    "kind": "domain",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  },
  "title": "六年级数学",
  "source": "已获准原件",
  "edition": null,
  "files": [
    {
      "receipt": {
        "storage_ref": "00000000-0000-4000-8000-000000000002",
        "media_type": "application/pdf",
        "byte_size": 1024,
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      },
      "original_name": "book.pdf",
      "order": 1
    }
  ]
}
```

<a id="p05"></a>
## P05 补充原件

`POST /material-imports/{id}/files` → `product.receive_material/append_files`。权限：管理员，id为现有导入。处理规则：[Product处理规则](../Product_Application_Design.md#31-productreceive_material接收整批或补充材料)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `files` | MaterialFile[] | 是；非空 | 沿原领域，格式同P04 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 原导入 |
| `source_revision` | int | 是 | 追加后原件修订 |
| `received` | Ref[] | 是 | 实际追加项 |
| `failed` | Issue[] | 是 | 未收项 |

处理边界：先鉴权，再按原request_id去重；共同保存业务结果与应有事件后返回。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；revision_conflict比较source_revision；source_unavailable。

请求／查询参数（示意数据）：

```json
{
  "request_id": "append-01",
  "expected_revision": 1,
  "files": [
    {
      "receipt": {
        "storage_ref": "00000000-0000-4000-8000-000000000003",
        "media_type": "image/png",
        "byte_size": 256,
        "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      },
      "original_name": "p49.png",
      "order": 2
    }
  ]
}
```

<a id="p06"></a>
## P06 教材基本信息

`PATCH /textbooks/{id}/metadata` → `product.save_material_metadata`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#32-productsave_material_metadata补录教材基本信息)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `metadata_patch` | 对象 | 是；非空 | 仅title:string、source:string、edition:string／null、copyright_page_ref:Ref／null；省略不改 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `textbook` | TextbookRow | 是 | 新基本信息 |

处理边界：先鉴权，再按原request_id去重；共同保存业务结果与应有事件后返回。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；revision_conflict；禁止修改领域、解析内容或关联。

请求／查询参数（示意数据）：

```json
{
  "request_id": "metadata-01",
  "expected_revision": 1,
  "metadata_patch": {
    "title": "六年级上册数学"
  }
}
```

<a id="p07"></a>
## P07 删除未完成导入

`POST /material-imports/{id}/delete` → `product.delete_material_import`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#33-productdelete_material_import删除未完成导入)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `confirmed_scope_ref` | Ref | 是 | P08详情生成的删除确认范围；不是浏览器自造清单 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `import_id` | ID | 是 | 被移除导入 |
| `deleted` | boolean | 是 | 是否已完成业务删除 |

处理边界：保留领域已入库内容及被引用文件；取消该导入未完成处理，晚到候选不得采用。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；已应用not_ready；范围变化revision_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "delete-01",
  "expected_revision": 3,
  "confirmed_scope_ref": {
    "owner": "product",
    "type": "deletion_scope",
    "id": "00000000-0000-4000-8000-000000000001"
  }
}
```

<a id="p08"></a>
## P08 教材列表与导入详情

`GET /textbooks；GET /textbooks/{id}` → `product.query_product_view`。权限：管理员；补齐已有教材管理查询投影。处理规则：[Product处理规则](../Product_Application_Design.md#52-productquery_product_view按权限读取业务视图)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 列表可选 | 仅指定领域 |
| `name` | string | 列表可选 | 书名子串 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | TextbookRow[] | 列表是 | 列表不带整册正文 |
| `next_cursor` | string或null | 列表是 | 续页 |
| `import` | ImportView | 详情是 | 详情不同时返回items |

ImportView包含textbook、revision、source_revision、content_revision、sources和next_source_cursor。sources每项含来源身份、文件收据、文件名、顺序和文件内页数。详情沿cursor继续读来源，原件使用R07读取。

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "domain_id": "00000000-0000-4000-8000-000000000001",
  "limit": 20
}
```

<a id="p09"></a>
## P09 教材助手输入

`POST /material-imports/{id}/messages` → `product.converse_material_assistant`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#34-productconverse_material_assistant持续对话解析与纠错)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `message` | string | 是 | 非空请求原文 |
| `selection` | MaterialSelection | 否 | Product§1.1的明确选区；无选区不等于当前浏览页 |
| `previous_batch_ref` | Ref | 否 | 继续核对指定候选 |
| `supplementary_file_refs` | ID[] | 否；[] | 当前导入内已完成补充文件 |

受理：202 `AcceptedReceipt`；最终结果从原收据查询，`result`为下表。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `message_ref` | ID | 是 | 原用户消息 |
| `reply_ref` | ID或null | 是 | 正式回应，未完成时null |
| `outcome` | enum | 是 | completed/needs_input/failed/cancelled |
| `candidate_batch_refs` | Ref[] | 是 | 正式候选；可为空 |
| `issues` | Issue[] | 是 | 缺口或错误 |

处理边界：同一导入忙时拒绝并保留客户端草稿；候选提出不自动采用、入库或建立章节关联。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；assistant_busy不保存新消息；identity_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "material-chat-01",
  "message": "请核对第49页题目中的分数"
}
```

<a id="p10"></a>
## P10 教材聊天历史

`GET /material-imports/{id}/messages` → `product.query_product_view`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#38-http与客户端交接)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `after_seq` | int | 否；0 | 只取其后消息 |
| `upper_seq` | int | 否；首屏服务端固定 | 续读沿原上界 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | MaterialMessage[] | 是 | seq升序 |
| `upper_seq` | int，各一 | 是 | 固定上界与本页最后位置 |
| `last_seq` | int，各一 | 是 | 固定上界与本页最后位置 |
| `next_cursor` | string或null | 是 | 续页 |
| `active_request_ref` | ID或null | 是 | 当前助手工作 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "after_seq": 0,
  "limit": 20
}
```

<a id="p11"></a>
## P11 解析内容

`GET /material-imports/{id}/contents` → `product.query_product_view`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#38-http与客户端交接)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `chapter_id` | ID | 否 | 只读该章；超大范围明确缩小 |
| `candidate_ref` | CandidateRef | 否 | 固定历史候选；与章当前列表查询互斥 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `content_revision` | int | 是 | 当前内容游标 |
| `items` | 已采用候选视图[] | 是 | candidate_ref、kind、chapter_ref、content、parent_ref、source_refs、validity；内容沿Product§3.4.3 |
| `read_token` | string | 是 | 本次一致读取依据 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；范围过大payload_too_large；历史不替换当前。

请求／查询参数（示意数据）：

```json
{
  "chapter_id": "00000000-0000-4000-8000-000000000049"
}
```

<a id="p12"></a>
## P12 候选核对

`GET /material-imports/{id}/candidate-batches/{batch_id}` → `product.query_product_view`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `batch` | CandidateBatchView | 是 | 固定提案及当前决定 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="p13"></a>
## P13 采用或不采用候选

`POST /material-imports/{id}/candidate-batches/{batch_id}/decision` → `product.decide_material_candidate`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#35-productdecide_material_candidate采用或不采用候选)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `batch_ref` | {batch_id:ID,batch_revision:Revision} | 是 | 与路径一致 |
| `decision` | adopt/decline | 是 | 一次明确决定 |
| `expected_revision` | Revision | 是 | 候选决定修订 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `decision_ref` | Ref | 是 | 已保存决定 |
| `batch_ref` | {batch_id:ID,batch_revision:Revision} | 是 | 原候选批次 |
| `decision` | adopt/decline | 是 | 原决定 |
| `adopted_content_refs` | CandidateRef[] | 是 | 实际采用项；拒绝为[] |
| `affected_source_refs` | Ref[] | 是 | 本次失效来源 |
| `content_revision` | int | 是 | 当前内容修订 |

处理边界：只比较本次修改内容和依赖；不自动合并冲突，不自动写Domain或章节关联。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；candidate_basis_changed；already_decided；incomplete_candidate。

请求／查询参数（示意数据）：

```json
{
  "request_id": "adopt-01",
  "batch_ref": {
    "batch_id": "00000000-0000-4000-8000-000000000008",
    "batch_revision": 1
  },
  "decision": "adopt",
  "expected_revision": 1
}
```

<a id="p14"></a>
## P14 提交待入库

`POST /material-imports/{id}/intake-submissions` → `product.submit_domain_intake`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `adopted_content_refs` | CandidateRef[] | 是；非空 | 题目、知识和解法分别选择 |
| `parent_bindings` | ParentBinding[] | 否；[] | 每项含candidate_ref；父题以parent_candidate_ref（本批题目）、parent_item_ref（已有待办）、task_instance_ref（已入库题目）恰一表示；三者不能混用 |

受理：202 `AcceptedReceipt`；最终结果从原收据查询，`result`为下表。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `submission_id` | ID | 是 | 固定提交 |
| `trigger_event_ref` | ID | 是 | DomainIntakeRequested |
| `status` | submitted | 是 | 已保存提交，不是已入库 |

处理边界：此202确认Product提交及派发；查询P15取得Domain业务接收结论；不要求管理员在当前请求等AI。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；missing_parent；source_unavailable。

请求／查询参数（示意数据）：

```json
{
  "request_id": "intake-01",
  "adopted_content_refs": [
    {
      "candidate_id": "00000000-0000-4000-8000-000000000009",
      "candidate_revision": 1,
      "basis_revision": 1
    }
  ],
  "parent_bindings": []
}
```

<a id="p15"></a>
## P15 待入库提交状态

`GET /material-imports/{id}/intake-submissions/{submission_id}` → `product.query_product_view`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#36-productsubmit_domain_intake提交已采用内容到领域)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `submission_id` | ID | 是 | 原提交 |
| `status` | submitted/received/rejected | 是 | Domain明确决定才改变 |
| `domain_receipt_ref` | Ref或null | 是 | 决定引用 |
| `items` | Ref[] | 是 | 按提交顺序的待办引用，包含复用项 |
| `trigger_event_ref` | ID | 是 | 原提交事件 |
| `issues` | Issue[] | 是 | 拒绝原因 |
| `wait_state` | waiting/timed_out/closed | 是 | Product自身等待 |
| `delivery_state` | Processing | 是 | 底座只读状态 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="p16"></a>
## P16 章节关联

`POST /textbooks/{id}/chapters/{chapter_id}/associations` → `product.save_chapter_association`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#41-productsave_chapter_association添加编辑或取消章节关联)。

同路径的GET返回当前有效关联，支持cursor、limit。每行包含association_ref、task_ref、method_refs和active。写入按教材范围经R04补读。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | add/update/remove | 是 | 即时单项保存 |
| `task_ref` | ObjectRef(task) | 是 | 同领域精确Task |
| `association_id` | ID | 修改/取消是 | 现有关系 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `method_refs` | ObjectRef(solution)[] | 添加/修改是 | 非空且均为Task直接方法；取消省略 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `association_ref` | Ref | 是 | 关系及新修订 |
| `active` | boolean | 是 | 取消为false |
| `kc_refs` | ObjectRef(kc)[] | 是 | 由所选方法汇总，不接受直接选择KC |

处理边界：先鉴权，再按原request_id去重；共同保存业务结果与应有事件后返回。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；revision_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "associate-01",
  "action": "add",
  "task_ref": {
    "kind": "task",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  },
  "method_refs": [
    {
      "kind": "solution",
      "object_id": "00000000-0000-4000-8000-000000000002",
      "version": 1
    }
  ]
}
```

<a id="p17"></a>
## P17 保存目标

`POST /learning-targets` → `product.save_learning_target`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#42-productsave_learning_target维护目标定义)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | create/update | 是 | 新建/追加修订 |
| `textbook_id` | ID | 是 | 目标所属教材 |
| `target_id` | ID | update是 | 固定目标身份 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `title` | string | 是 | 目标名 |
| `items` | GoalItem[] | 是 | Product§4.2.1完整条目；Task/方法范围来自教材关联，`task_conditions` 只含文字 `description` |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `target` | TargetView | 是 | 目标及缺口 |

处理边界：结构合法但尚未配置完整可存草稿；不得将空items当可应用目标。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；越出教材范围not_ready。

请求／查询参数（示意数据）：

```json
{
  "request_id": "target-01",
  "action": "create",
  "textbook_id": "00000000-0000-4000-8000-000000000001",
  "title": "本册学习目标",
  "items": []
}
```

<a id="p18"></a>
## P18 目标列表与详情

`GET /learning-targets；GET /learning-targets/{id}` → `product.query_product_view`。权限：管理员；列表为既有查询补齐。处理规则：[Product处理规则](../Product_Application_Design.md#52-productquery_product_view按权限读取业务视图)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `textbook_id` | ID | 列表是 | 教材范围 |
| `revision` | Revision | 详情可选 | 省略读当前草稿 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | TargetView[] | 列表是 | 条目正文可由详情取 |
| `next_cursor` | string或null | 列表是 | 续页 |
| `target` | TargetView | 详情是 | 精确目标修订 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "textbook_id": "00000000-0000-4000-8000-000000000001",
  "limit": 20
}
```

<a id="p19"></a>
## P19 检查应用

`POST /course-applications/checks` → `product.apply_course/check`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `textbook_id` | ID | 是 | 教材 |
| `target_ref` | TargetRef | 是 | 精确目标修订 |
| `expected_application_ref` | Ref或null | 是 | 首次应用明确null |
| `chapters` | ChapterSelection[] | 是 | 每项固定 `chapter_id`、`revision` 及 `content_refs`。只替换本次选中的章节 |
| `activity_config_refs` | Ref[] | 是 | 按配置包精确修订，每类最多一条。空缺按用途报告 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `check_ref` | Ref | 是 | 不可变检查 |
| `base_application_ref` | Ref或null | 是 | 检查基准 |
| `changes` | Issue[] | 是 | 变化摘要 |
| `proposed_application` | CourseSnapshot | 是 | 本次检查固定的教材、目标、章节及准备结论 |
| `readiness` | 用途检查对象[] | 是 | purpose、status、basis_refs、issues；结构沿Product§4.3 |
| `can_apply` | boolean | 是 | 程序从检查结果决定 |

处理边界：只保存检查；学生尚不能选用拟应用内容。
管理员用 `GET /course-applications/current?textbook_id={id}&target_id={id}` 取得当前应用基准。检查和确认的公共收据分别使用 `product.check_course`、`product.confirm_course`。范围为 `textbook`。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；revision_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "check-01",
  "textbook_id": "00000000-0000-4000-8000-000000000001",
  "target_ref": {
    "target_id": "00000000-0000-4000-8000-000000000002",
    "revision": 1
  },
  "expected_application_ref": null,
  "chapters": [
    {
      "chapter_id": "00000000-0000-4000-8000-000000000011",
      "revision": 1,
      "content_refs": []
    }
  ],
  "activity_config_refs": []
}
```

<a id="p20"></a>
## P20 确认应用

`POST /course-applications/confirmations` → `product.apply_course/confirm`。权限：管理员。处理规则：[Product处理规则](../Product_Application_Design.md#43-productapply_course检查并应用教材与目标组合)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `check_ref` | Ref | 是 | P19固定检查 |
| `expected_application_ref` | Ref或null | 是 | 与检查基准一致 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `application_ref` | Ref | 是 | 已应用快照 |
| `changed` | boolean | 是 | 内容未变化可false |
| `affected_spaces` | ID[] | 是 | 实际推进采用的空间 |

处理边界：一起保存应用、空间采用及相关事件；只推进同textbook_id、同target_id的空间，不修改空间身份；仅目标依据改变才产生LearningTargetApplied。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；check_stale；not_ready。

请求／查询参数（示意数据）：

```json
{
  "request_id": "confirm-01",
  "check_ref": {
    "owner": "product",
    "type": "application_check",
    "id": "00000000-0000-4000-8000-000000000001"
  },
  "expected_application_ref": null
}
```

<a id="p21"></a>
## P21 可选教材目标组合

`GET /course-options` → `product.query_product_view`。权限：学生，已满足使用条件。处理规则：[Product处理规则](../Product_Application_Design.md#52-productquery_product_view按权限读取业务视图)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 否 | 限定领域 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | CourseOption[] | 是 | 仅已应用且调用者可选的组合 |
| `next_cursor` | string或null | 是 | 续页 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "limit": 20
}
```

<a id="p22"></a>
## P22 创建或进入空间

`POST /learning-spaces/open` → `product.open_learning_space`。权限：学生本人，满足使用条件。处理规则：[Product处理规则](../Product_Application_Design.md#51-productopen_learning_space创建或进入个人空间)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | create/enter | 是 | 两种明确进入动作 |
| `textbook_id` | ID，各一 | create是 | 选择的组合 |
| `target_id` | ID，各一 | create是 | 选择的组合 |
| `expected_application_ref` | Ref | create是 | 界面看到的已应用版本 |
| `space_id` | ID | enter是 | 已有本人空间；其他选择字段省略 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `space` | SpaceRow | 是 | 同学生/教材/目标复用已有空间 |
| `created` | boolean | 是 | 是否本次新建 |
| `adoption` | AdoptionView | 是 | 进入时采用 |
| `entry_event_ref` | ID | 是 | 实际进入事实 |

处理边界：每次真实进入按新request_id记录；网络重试沿原请求，不再次触发主动任务。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；application_changed；not_ready。

请求／查询参数（示意数据）：

```json
{
  "request_id": "enter-01",
  "action": "enter",
  "space_id": "00000000-0000-4000-8000-000000000100"
}
```

<a id="p23"></a>
## P23 空间列表

`GET /learning-spaces` → `product.query_product_view`。权限：学生只读本人；管理员可按学生筛选；补齐已有列表查询。处理规则：[Product处理规则](../Product_Application_Design.md#52-productquery_product_view按权限读取业务视图)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `student_id` | ID | 管理员可选 | 学生不得指定他人 |
| `student_name` | string | 否 | 按学生显示名筛选 |
| `textbook_id` | ID | 否 | 组合筛选 |
| `target_id` | ID | 否 | 组合筛选 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | SpaceRow[] | 是 | 授权范围内 |
| `next_cursor` | string或null | 是 | 续页 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "limit": 20
}
```

<a id="p24"></a>
## P24 空间采用内容

`GET /learning-spaces/{space_id}` 返回当前 `AdoptionView`。学生只可读本人空间，管理员可读授权空间。视图含采用引用、应用引用、目标依据和固定课程快照。

`GET /learning-spaces/{space_id}/workspace` 仅供本人学生刷新恢复。200 返回 `{space, adoption}`，不追加 `LearningSpaceEntered`。正常进入继续用 `POST /learning-spaces/open`。

`GET /learning-spaces/{space_id}/chapters/{chapter_id}` 返回对应采用章节的 `items`，各条 `source_ref` 为对应内容的固定引用。正文从候选事实的固定版本读出。章节越界返回 404。

`GET /learning-spaces/{space_id}/events` 仅供管理员。接受 `event_type`、`after_seq`、`upper_seq` 和 `limit`，返回 `items`、`upper_seq` 和 `next_after_seq`。继续翻页沿用读取上界。列表项只含事件元数据。
<a id="p25"></a>
## P25 空间目标展示

`GET /learning-spaces/{space_id}/goal`。学生只可读本人，管理员可读授权空间。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `target_basis_ref` | Ref | 当前采用的评价依据 |
| `target_title` | string | 当前应用的目标名称 |
| `domain_id` | UUID | 教材所属领域，用于读取方法名称 |
| `pending` | boolean | 当前依据的计算尚未保存 |
| `current` | GoalEvaluation 或 null | Evaluation 保存的完整目标判断，含分项状态、理由及 Evidence 引用 |

E03 由 Product 调用 Evaluation 的只读查询，只返回匹配当前目标依据的结果。教材与目标要求沿 P24 读取。Evidence 的深入取材见 [Evaluation E06](Evaluation_API.md#e06)。
<a id="p26"></a>
## P26 Product收据内部投影

本节不是HTTP接口。公共运行通过`product.query_product_view`取得原请求的收据；浏览器只调用[公共收据R04](Runtime_Protocols.md#r04)。查找依据为原action、resource及request_id，加已验证的原请求人；所有者再次核对当前权限。业务处理规则见[模块合同](../Product_Application_Design.md#38-http与客户端交接)。

所有者返回下列内部投影；底座按R04转换字段。无记录返回not_found，查询故障返回读取失败，不伪造空收据。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_ref` | ID | 是 | 原请求 |
| `state` | string | 是 | 所属动作业务状态，见原处理规则 |
| `result` | 入口对应结果或null | 是 | 成功前可null |
| `error` | ErrorResponse.error或null | 是 | 失败原因 |
| `runtime_ref` | ID或null | 是 | 有后台工作时非null |

## 内部入口与授权读取

内部端口必须接收程序建立的access_context；事务保护另接收transaction_context，不能自行提交。下表直接引用现有逐字段/分支合同，不把它们再次包装成HTTP或AI Operation。

| 入口 | 调用方 | 输入输出唯一合同 | 限制 |
| --- | --- | --- | --- |
| save_trial_account / recover_account | 受控部署命令或管理员已有后台处理 | [Product§2.1／2.4](../Product_Application_Design.md#21-productsave_trial_account初始化或维护试用账号) | 不新增自助注册、找回；密码不进入请求收据或普通事件 |
| record_usage_confirmation | 管理员或学生本人意愿 | [Product§1.1／2.2](../Product_Application_Design.md#22-productrecord_usage_confirmation记录必要首次确认) | 学生不能代监护确认；返回服务端计算条件 |
| authenticate_session / check_execution_subject | 公共运行 | [Product§2.7](../Product_Application_Design.md#27-认证端口与请求保护) | 后台不依赖浏览器会话仍有效；不返回密码摘要 |
| read_adopted_content / read_intake_submission | Domain | [Product§3.6.1](../Product_Application_Design.md#361-教材来源读取与提交保护) | 固定候选、原页和父题绑定；故障不能返回空成功 |
| guard_adopted_sources | Domain提交 | 同上 | 同库短事务锁来源；只写自己模块数据 |
| read_space_adoption / read_application_basis / read_target_basis / guard_target_adoption | Evaluation | [Product§5.2.1](../Product_Application_Design.md#521-采用依据的公开读取) | 前三者按空间采用读取固定依据；guard_target_adoption只保护结果提交，不跨AI持锁 |

路径和字段缺口在本稿补齐，限额及部署命令的安全接线继续沿认证/基础设施设计。不得以内部服务身份读取无关教材或任意学生空间。
<a id="p27"></a>
## P27 空间教材阅读

E03 的已采用章节正文使用 P24。下列原页及教材阅读合同由学生端增量接线。

`GET /learning-spaces/{id}/textbook` → `product.query_product_view/space_material`。权限：本人/管理员；补齐既有教材查询投影。处理规则：[Product处理规则](../Product_Application_Design.md#52-productquery_product_view按权限读取业务视图)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `adoption_ref` | Ref | 否；当前采用 | 历史阅读明确采用引用 |
| `chapter_id` | ID | 否；省略只读目录 | 允许阅读采用教材内任意章，不限制当前聊天 |
| `content_ref` | Ref | 否 | 精确内容读取，必须属于指定采用 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `adoption_ref` | Ref | 是 | 固定本次读取依据 |
| `textbook` | TextbookRow | 是 | 采用时教材信息 |
| `chapters` | ChapterRow[] | 目录读取是 | 已采用目录 |
| `items` | MaterialElement[] | 章节/内容读取是 | kind、candidate_ref、content:RichContent、source_refs；结构沿Product§3.4.3 |
| `next_cursor` | string或null | 是 | 绑定采用及筛选 |
| `source_file_refs` | Ref[] | 是 | 可授权读取原页的业务引用 |

处理边界：阅读不改变当前活动，不隐式给学生输入附加当前章节。原件经R07授权读取；题面和教学辅助分开。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；source_unavailable。

请求／查询参数（示意数据）：

```json
{
  "chapter_id": "00000000-0000-4000-8000-000000000011",
  "limit": 20
}
```

<a id="p28"></a>
## P28 必要使用确认

`POST /usage-confirmations` → `product.record_usage_confirmation`。权限：学生仅本人student_assent；管理员按已核实材料登记；补齐既有普通处理入口。处理规则：[Product处理规则](../Product_Application_Design.md#22-productrecord_usage_confirmation记录必要首次确认)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `confirmation` | ConfirmationInput | 是 | 逐字段定义沿Product§1.1：student_id、kind、notice_ref、decision、occurred_at、source_ref |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `confirmation_ref` | Ref | 是 | 实际确认记录 |
| `conditions_revision` | Revision | 是 | 新的使用条件修订 |
| `allowed` | boolean | 是 | 程序计算，不接受客户端传入 |
| `gaps` | Issue[] | 是 | 尚未满足条件 |

处理边界：网页仅接收本人student_assent，拒绝管理员代填、跨学生提交、客户端发生时间及pending；服务端写入接受时间。source_ref必须等于当前GET返回的确认提示。线下监护确认仅由受控管理员命令录入。相同request_id返回原事件快照；条件修订变化返回409。request_id采用UUID，写入携带X-Expected-Session和X-CSRF-Token。

配套读取：`GET /api/m1/usage-conditions`只读当前登录学生，不接收任意student_id。响应为student_id、revision、notice_ref、notice_text、source_ref、allowed、gaps、can_confirm；不返回监护身份原文。会话失效返回401，错误角色403，条件不存在404，响应不缓存。E01-10仅使用合成测试告知；正式文本未批准。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；forbidden；revision_conflict；invalid_reference。

请求／查询参数（示意数据）：

```json
{
  "request_id": "00000000-0000-4000-8000-000000000028",
  "expected_revision": 1,
  "confirmation": {
    "student_id": "00000000-0000-4000-8000-000000000001",
    "kind": "student_assent",
    "notice_ref": {
      "owner": "product",
      "type": "usage_notice",
      "id": "00000000-0000-4000-8000-000000000001",
      "revision": 1
    },
    "decision": "accepted",
    "occurred_at": "2026-11-15T02:00:00Z",
    "source_ref": {
      "owner": "product",
      "type": "assent_prompt",
      "id": "00000000-0000-4000-8000-000000000003"
    }
  }
}
```

## 结果样例

候选采用成功只表示教材内容已采用；领域入库和章节采用仍分别操作：

```json
{
  "request_ref": "adopt-example-01",
  "result": {
    "decision_ref": {
      "owner": "product",
      "type": "candidate_decision",
      "id": "decision-01"
    },
    "batch_ref": {
      "batch_id": "batch-01",
      "batch_revision": 1
    },
    "decision": "adopt",
    "adopted_content_refs": [
      {
        "candidate_id": "candidate-01",
        "candidate_revision": 1,
        "basis_revision": 1
      }
    ],
    "affected_source_refs": [],
    "content_revision": 2
  }
}
```

助手受理后返回202；正文通过P10读取，不能把受理当成候选已经完成：

```json
{
  "request_ref": "material-request-01",
  "state": "accepted",
  "runtime_ref": "execution-01"
}
```

相关题面已变化时返回409，原候选保留供继续对话核对：

```json
{
  "error": {
    "code": "candidate_basis_changed",
    "message": "本题已被另一份修正替换，请让教材助手重新核对。",
    "issues": [
      {
        "code": "dependency_changed",
        "path": "batch_ref",
        "message": "候选依据的题面已变化。"
      }
    ],
    "retryable": false
  },
  "request_ref": "adopt-example-02"
}
```

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 收据改为内部投影，明确目标页入口及应用空间范围。见MVP决定登记§95。 |
| v0.3 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.4 | 2026-11-15 | 补齐事件正文、记录映射、状态或读取边界；容量及保留候选仍待确认。仅文档修订，见MVP决定登记§98。 |
| v0.5 | 2026-11-16 | 接线本人使用条件查询与首次确认；管理操作采用命令 |
| v0.6 | 2026-11-22 | 登记教材原件清单与原请求恢复字段 |
| v0.7 | 2026-11-22 | 登记教材候选工作流、领域受理和章节即时保存合同 |
| v0.8 | 2026-11-23 | 登记目标、应用选择和学习空间读写合同 |
| v0.9 | 2026-11-23 | 同步目标文字范围的保存合同 |
| v0.10 | 2026-11-23 | 登记学习工作区只读恢复及教材内容的固定引用 |
