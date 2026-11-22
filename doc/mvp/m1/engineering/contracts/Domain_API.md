# M1 Domain API

> **版本**：v0.4<br>
> **状态**：设计合同；已实现范围和进度见实施计划<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-22<br>
> **修订说明**：v0.3 → v0.4，登记 E02-01 的领域列表、首版保存、详情和回执<br>

共同类型与回执见[总册](../API_and_Message_Design.md)。接口只接受已授权领域及精确对象引用；所有定义/内容结构以[Domain§1](../Domain_Space_Design.md#1-领域对象身份与关系)为唯一来源。API不直接接收数据库行或模型任意生成的ID。

来源通则：业务ID及查询响应维持现有形状，来源字段source_event_id:ID指向生成该对象的事实；正文片段返回EventPartRef。正文读取来自事件及固定附件，业务表只是投影。内部适配器负责本业务用途和范围，不从私有表提供独立原文；写请求仍走原业务入口，客户端不能指定事件内容或source_event_id。

E02-01 接入 D01、D02、D04 和 D13 的管理员领域根分支。各请求携带当前 `X-Expected-Session`，D02 另带 `X-CSRF-Token`。

## 响应对象

| 类型 | 字段 | 约束 |
| --- | --- | --- |
| DomainRow | object_ref:ObjectRef(domain)、name:string、description:RichContent\|null、is_deleted:boolean | 当前可见领域 |
| ObjectRow | object_ref:ObjectRef、name:string、is_deleted:boolean、gaps:Issue[] | 列表为头版本；历史详情另读 |
| ObjectView | object_ref:ObjectRef、content:对应对象载荷、content_ref:ContentRef、is_identity_deleted:boolean、source_refs:Ref[]、gaps:Issue[] | content按所请求view裁剪；绝不把完整数据库快照直接交学生 |
| ContentRef | {owner:"domain",object_ref:ObjectRef,path:string}或{owner:"domain",artifact_id:ID,path:string} | 二选一；path为授权JSON Pointer，不授予额外读取权 |
| IntakeView | item_id:ID、revision:Revision、kind:kc/task_instance/reference、group_ref:Ref、source_ref:Ref、content_ref:ContentRef、parent_ref:Ref\|null、state:string、result:对象\|null | state及分支结果沿Domain§6.4／§2.3；不返回其他来源 |
| ArtifactView | artifact_ref:Ref、kind:string、payload:对应已登记产物、definition_refs:ObjectRef[]、source_refs:Ref[]、issues:Issue[] | 提取/归类/就绪产物结构沿Domain§3.2／4.1／5.3；kind不是任意JSON仓库 |

<a id="d01"></a>
## D01 领域列表

`GET /domains` → `domain.query_content`。权限：管理员及已获领域读取授权的使用者。处理规则：[Domain处理规则](../Domain_Space_Design.md#61-domainquery_content)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | DomainRow[] | 是 | M1返回完整可见列表，不含删除领域 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

E02-01 返回当前未删除的领域根，管理端在列表中按名称查找。各项带首版来源 `source_event_id`。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="d02"></a>
## D02 保存领域定义

`POST /domain-definitions` → `domain.save_definition`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#21-domainsave_definition)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `object_kind` | domain/task/solution/kc | 是 | 不能使用task_instance |
| `action` | create/update/soft_delete | 是 | 更新或删除均追加版本 |
| `domain_id` | ID | 新建成员是 | 新建Domain省略 |
| `object_ref` | ObjectRef | update/soft_delete是 | 当前编辑基准 |
| `expected_version` | Revision | update/soft_delete是 | 与被修改对象基准一致 |
| `definition` | 对应Domain§1.2载荷 | create/update是 | 完整定义；soft_delete省略 |
| `candidate_ref` | Ref | 否 | 采用提取建议时携带 |
| `change_note` | string | 是 | 变更原因；非空 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `object_ref` | ObjectRef | 是 | 保存后的精确版本 |
| `content_ref` | ContentRef | 是 | 新内容 |
| `gaps` | Issue[] | 是 | 合法但未准备完整的缺口 |

处理边界：普通保存200；缺方法可存草稿，但Task直接关联KC等非法关系拒绝。soft_delete保留历史，无物理删除入口。

E02-01 接受 `object_kind=domain`、`action=create`、`definition.name` 和 `change_note`。名称和变更说明去掉首尾空白后须非空，覆盖范围及描述留空。服务端分配领域 ID，将 `DomainDefinitionSaved`、首版、领域头、投影收据和请求收据同事务提交。原请求编号与内容相同时返回原结果，原编号用于不同内容时返回 409。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；version_conflict；dependency_cycle；invalid_reference。

请求／查询参数（示意数据）：

```json
{
  "request_id": "domain-01",
  "object_kind": "domain",
  "action": "create",
  "definition": {
    "name": "小学数学",
    "coverage": null,
    "description": null
  },
  "change_note": "建立领域"
}
```

<a id="d03"></a>
## D03 领域对象列表

`GET /domains/{domain_id}/objects` → `domain.query_content`。权限：管理员/获授权内容选择入口。处理规则：[Domain处理规则](../Domain_Space_Design.md#61-domainquery_content)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `kinds` | 对象kind[] | 否；所有可见种类 | 查询串同名参数重复表示数组 |
| `name` | string | 否 | 名称子串 |
| `task_ref` | ObjectRef，各可选 | 否 | 请求查询串用JSON序列化对象；必须同域 |
| `solution_ref` | ObjectRef(solution) | 否 | 请求查询串用JSON序列化对象；必须同域 |
| `availability` | string | 否 | 按已登记用途状态筛选 |
| `purpose` | example/practice/assessment | availability存在时是 | 只读用途状态，不供题 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | ObjectRow[] | 是 | object_id升序 |
| `next_cursor` | string或null | 是 | 目录变动后须重读 |
| `read_token` | string | 是 | 固定catalog_revision |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；read_range_changed；invalid_reference。

请求／查询参数（示意数据）：

```json
{
  "kinds": [
    "task"
  ],
  "name": "比例",
  "limit": 20
}
```

<a id="d04"></a>
## D04 领域对象详情

`GET /domains/{domain_id}/objects/{object_id}` → `domain.query_content`。权限：按内容用途授权；学生只能题面视图。处理规则：[Domain处理规则](../Domain_Space_Design.md#61-domainquery_content)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `version` | Revision | 否；头版本 | 精确历史版本不自动升级 |
| `view` | statement/reference/full | 题目实例是 | 学生只允许statement；其他对象省略 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `object` | ObjectView | 是 | 历史身份已删除时也明确标记 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

E02-01 要求两个路径 ID 均为同一领域根。越界或指定版本不存在返回 404，`source_event_id` 指向详情所读的事实。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_request（实例缺view）；forbidden（请求答案）。

请求／查询参数（示意数据）：

```json
{
  "version": 1,
  "view": "statement"
}
```

<a id="d05"></a>
## D05 方法与先导依赖

`GET /domains/{domain_id}/dependencies` → `domain.query_dependencies`。权限：管理员/有界内部取材。处理规则：[Domain处理规则](../Domain_Space_Design.md#42-domainquery_dependencies)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_id` | ID | 是 | 本领域Task |
| `version` | Revision | 是 | 精确Task版本 |
| `solution_ids` | ID[] | 否；全部直接方法 | 只可选择Task引用的方法 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_ref` | ObjectRef(task) | 是 | 查询对象 |
| `method_refs` | ObjectRef(solution)[] | 是 | Task直接方法 |
| `kc_refs` | ObjectRef(kc)[] | 是 | 方法引用知识去重 |
| `prerequisites` | 先导关系[] | 是 | Domain§1.2的task_ref、适用方法与依赖条件；不是可执行子调用树 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference。

请求／查询参数（示意数据）：

```json
{
  "task_id": "00000000-0000-4000-8000-000000000001",
  "version": 1
}
```

<a id="d06"></a>
## D06 待入库列表

`GET /domains/{domain_id}/intake-items` → `domain.query_content`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#61-domainquery_content)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `kind` | kc/task_instance/reference | 否 | 待办类别 |
| `source_ref` | Ref | 否 | 教材来源过滤 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | IntakeView[] | 是 | 仅pending，item_id升序 |
| `next_cursor` | string或null | 是 | 续页 |
| `read_token` | string | 是 | 目录读取基准 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "kind": "task_instance",
  "limit": 20
}
```

<a id="d07"></a>
## D07 待入库详情

`GET /domains/{domain_id}/intake-items/{item_id}` → `domain.query_content`。权限：管理员/已授权教材调用者。处理规则：[Domain处理规则](../Domain_Space_Design.md#23-domainprocess_intake)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `item` | IntakeView | 是 | 含已处理结果，查询不重建待办 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="d08"></a>
## D08 处理待入库项

`POST /domains/{domain_id}/intake-items/{item_id}/actions` → `domain.process_intake`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#23-domainprocess_intake)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `action` | add_kc/associate_task/associate_solution/discard | 是 | 按下表只携该分支参数 |
| `definition` | KC载荷 | add_kc恰一 | 新建或复用知识 |
| `existing_kc_ref` | ObjectRef(kc) | add_kc恰一 | 新建或复用知识 |
| `task_ref` | ObjectRef(task) | associate_task是 | 题目归属Task |
| `existing_instance_ref` | ObjectRef(task_instance) | associate_task可选 | 明确复用同题，省略新建 |
| `solution_ref` | ObjectRef(solution) | associate_solution是 | 方法及已入库父题 |
| `task_instance_ref` | ObjectRef(task_instance) | associate_solution是 | 方法及已入库父题 |
| `expected_version` | Revision | associate_solution是 | 父题当前版本 |
| `confirm_add_method` | boolean | 否；false | 需要给Task补方法时明确true |
| `expected_task_version` | Revision | confirm_add_method=true时是 | Task并发基准 |
| `confirm_discard_children` | boolean | 否；false | 放弃父题且尚有待办解法时必须true |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `item_ref` | Ref | 是 | 原待办 |
| `state` | added/associated/discarded | 是 | 实际结果 |
| `object_ref` | ObjectRef或null | 是 | 知识或题目；放弃为null |
| `reference_ref` | Ref或null | 是 | 追加题内解法时给出 |
| `check_refs` | Ref[] | 是 | 采用检查 |
| `affected_item_refs` | Ref[] | 是 | 实际影响项 |
| `group_pending_count` | int | 是 | 剩余待办数；非负 |

处理边界：普通处理200；需AI归类先202，正式入库以Domain收据committed为准。定义先保存而后续关联失败，不撤销已保存定义。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；classification_failed/classification_unresolved；missing_parent；parent_not_linked；confirmation_required；already_processed。

请求／查询参数（示意数据）：

```json
{
  "request_id": "associate-01",
  "expected_revision": 1,
  "action": "associate_task",
  "task_ref": {
    "kind": "task",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  }
}
```

<a id="d09"></a>
## D09 保存题目实例

`POST /domains/{domain_id}/instances` → `domain.save_instance`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#51-domainsave_instance)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | create/update/soft_delete | 是 | 只管理题目内容 |
| `instance` | TaskInstance载荷 | create/update是 | Domain§1.2；完整题面、Task与题内参考 |
| `object_ref` | ObjectRef(task_instance) | update/soft_delete是 | 基准题目 |
| `expected_version` | Revision | update/soft_delete是 | 当前版本 |
| `change_note` | string | 是 | 原因 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `object_ref` | ObjectRef(task_instance) | 是 | 新版本 |
| `content_ref` | ContentRef | 是 | 固定内容 |
| `classification_check_refs` | Ref[] | 是 | 归类依据 |
| `gaps` | Issue[] | 是 | 用途就绪缺口 |

处理边界：新建/修改需语义检查时202，软删除普通200且不重新归类。未有检测参考可保存，但不冒充已可检测。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；classification_failed/classification_unresolved；version_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "delete-instance-01",
  "action": "soft_delete",
  "object_ref": {
    "kind": "task_instance",
    "object_id": "00000000-0000-4000-8000-000000000003",
    "version": 1
  },
  "expected_version": 1,
  "change_note": "停止新用途选用"
}
```

<a id="d10"></a>
## D10 确认KC检验路径

`POST /domains/{domain_id}/kc-test-paths` → `domain.confirm_kc_path`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#43-kc直接检验路径的准备与确认)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `kc_ref` | 对应ObjectRef | 全部是 | 三个精确版本 |
| `task_ref` | 对应ObjectRef | 全部是 | 三个精确版本 |
| `solution_ref` | ObjectRef(solution) | 全部是 | 三个精确版本 |
| `observable_behavior` | string | 是 | 能直接观察的理解/表现 |
| `insufficient_examples` | string[] | 是 | 仅引用而不能证明理解的反例 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `confirmation_ref` | Ref | 是 | 固定确认依据 |

处理边界：不产生个人Evidence或概率，也不改变章节采用。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_reference；not_ready。

请求／查询参数（示意数据）：

```json
{
  "request_id": "kc-path-01",
  "kc_ref": {
    "kind": "kc",
    "object_id": "00000000-0000-4000-8000-000000000004",
    "version": 1
  },
  "task_ref": {
    "kind": "task",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  },
  "solution_ref": {
    "kind": "solution",
    "object_id": "00000000-0000-4000-8000-000000000002",
    "version": 1
  },
  "observable_behavior": "解释每小时路程如何累加",
  "insufficient_examples": [
    "只背出公式"
  ]
}
```

<a id="d11"></a>
## D11 提取定义候选

`POST /domains/{domain_id}/definition-candidates` → `domain.extract_template`。权限：管理员。处理规则：[Domain处理规则](../Domain_Space_Design.md#32-domainextract_template)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `intake_item_ref` | Ref | 是 | 已采用题目或具体解法待办 |
| `template_kind` | task/solution | 是 | 沿既有技术标识 |
| `extraction_instruction` | string或null | 否；null | 本轮要求 |
| `prior_candidate_ref` | Ref | 否 | 继续核对时指定 |

受理：202 `AcceptedReceipt`；最终结果从原收据查询，`result`为下表。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `candidate_ref` | Ref，各一 | 是 | 程序保存的技术产物 |
| `check_ref` | Ref，各一 | 是 | 程序保存的技术产物 |
| `proposed_definition` | Task或Solution载荷 | 是 | Domain§1.2 |
| `issues` | Issue[] | 是 | 缺口与理由 |

处理边界：只提出候选；确认保存走D02，题目仍需D08关联。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；source_unavailable；invalid_reference。

请求／查询参数（示意数据）：

```json
{
  "request_id": "extract-01",
  "intake_item_ref": {
    "owner": "domain",
    "type": "intake_item",
    "id": "00000000-0000-4000-8000-000000000001"
  },
  "template_kind": "task"
}
```

<a id="d12"></a>
## D12 读取产物

`GET /domains/{domain_id}/artifacts/{artifact_id}` → `domain.query_content`。权限：按来源授权的管理员或内部调用。处理规则：[Domain处理规则](../Domain_Space_Design.md#66-http请求响应与分页)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `artifact` | ArtifactView | 是 | 固定产物；无秘密 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="d13"></a>
## D13 Domain收据内部投影

本节不是HTTP接口。公共运行通过`domain.query_content`取得原请求的收据；浏览器只调用[公共收据R04](Runtime_Protocols.md#r04)。查找依据为原action、resource及request_id，加已验证的原请求人；所有者再次核对当前权限。业务处理规则见[模块合同](../Domain_Space_Design.md#64-请求与待办状态)。

E02-01 登记 `domain.save_definition` 的新建领域回执。新建时尚无领域 ID，以原管理员账号作为查找范围。已提交返回 D02 原结果，当前会话仍须具备管理员权限。

所有者返回下列内部投影；底座按R04转换字段。无记录返回not_found，查询故障返回读取失败，不伪造空收据。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_ref` | ID | 是 | 收据身份 |
| `state` | accepted/committed/rejected/failed | 是 | Domain§6.4业务收据状态 |
| `result` | D02/D08/D09对应结果或null | 是 | 未成功为null |
| `error` | ErrorResponse.error或null | 是 | 真实失败原因 |
| `runtime_ref` | ID或null | 是 | 后台执行 |

## 内部查询与提交保护

| 端口 | 调用方 | 唯一合同位置 |
| --- | --- | --- |
| query_content / query_dependencies | Product、Interaction、Evaluation及授权管理查询 | [Domain§6.1](../Domain_Space_Design.md#61-domainquery_content)、[§4.2](../Domain_Space_Design.md#42-domainquery_dependencies) |
| guard_references | Product保存/应用、Evaluation定义保存 | [Domain§6.7](../Domain_Space_Design.md#67-模块端口与消息交接) |
| read_intake_result | Product | [Domain§6.7](../Domain_Space_Design.md#67-模块端口与消息交接) |

以上字段及来源锁规则见[Domain§6.7](../Domain_Space_Design.md#67-模块端口与消息交接)。供题、归类和提取按原Operation合同执行；HTTP不能直接伪造供题完成事件。task_supply、intake_receipt结果载荷分别沿[§5.2](../Domain_Space_Design.md#52-domainsupply_task)、[§2.2](../Domain_Space_Design.md#22-domainreceive_intake)，正式事件保存完整正文及来源，NATS只传事件通知。

## 入库结果样例

D08需归类时先返回202；浏览器随后按[公共收据R04](Runtime_Protocols.md#r04)查询。以下为D13内部投影示例，R04将state映射为business_state并以completed表示已提交；result保持相同结构。后续编辑不改原收据：

```json
{
  "request_ref": "domain-request-01",
  "state": "committed",
  "result": {
    "item_ref": {
      "owner": "domain",
      "type": "intake_item",
      "id": "item-01"
    },
    "state": "associated",
    "object_ref": {
      "kind": "task_instance",
      "object_id": "instance-01",
      "version": 1
    },
    "reference_ref": null,
    "check_refs": [
      {
        "owner": "domain",
        "type": "classification",
        "id": "check-01"
      }
    ],
    "affected_item_refs": [],
    "group_pending_count": 1
  },
  "error": null,
  "runtime_ref": "execution-02"
}
```

ContentRef只允许所属view已授权的JSON Pointer；图文重排不升对象版本。客户端缓存身份须包含完整ObjectRef及view，不能混用题面与答案。未支持内容块明确显示缺口，不降为未经校验的HTML。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 将模块收据改为内部投影，浏览器统一查询公共收据。见MVP决定登记§95。 |
| v0.3 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.4 | 2026-11-22 | 登记 E02-01 的领域列表、首版保存、详情、权限和回执 |
