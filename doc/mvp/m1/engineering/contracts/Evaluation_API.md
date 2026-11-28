# M1 Evaluation API

> **版本**：v0.7<br>
> **状态**：Claim 定义及评价追溯接口见 OpenAPI，验收进度见实施计划<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-28<br>
> **修订说明**：v0.5 → v0.6，明确证据列表与作答原文的时间依据<br>

所有写入口只维护评价定义；个人Evidence、Belief和目标结果只能由已登记处理流程产生。查询不重新评价、不改概率。共同认证、回执和错误见[总册](../API_and_Message_Design.md)。

来源通则：业务ID及查询响应维持现有形状，来源字段source_event_id:ID指向生成该对象的事实；正文片段返回EventPartRef。正文读取来自事件及固定附件，业务表只是投影。内部适配器负责本业务用途和范围，不从私有表提供独立原文；写请求仍走原业务入口，客户端不能指定事件内容或source_event_id。

## 共用结果

| 类型 | 字段 | 内容定义 |
| --- | --- | --- |
| ClaimView | claim_ref:ClaimRef、definition:ClaimDefinition、gaps:Issue[] | [Evaluation§1.3](../Evaluation_Space_Design.md#13-定义结构与引用)；完整方法列表由Task决定 |
| GoalResult | goal_evaluation_ref、scope_id、target_basis_ref、snapshot_ref、publication_seq、calculation_rule_ref、trigger_event_id、computed_at、readiness、attainment、reasons、items、current_state_applied、not_applied_reason | 类型、枚举、逐项结果沿[§4.4](../Evaluation_Space_Design.md#44-目标结果载荷)；无快照为null/0，不能以先验达标 |
| BeliefItem | 完整分项字段沿[Evaluation§5.1](../Evaluation_Space_Design.md#51-学习者掌握状态的发布视图) | 保留aspect、evidence_coverage、unknown_reasons、source_refs原名，不另造一套概率结构 |
| EvidenceView | 正式EvidenceItem及授权来源，见[Evaluation§2.4](../Evaluation_Space_Design.md#24-ai候选与程序接受) | qualification=eligible/ineligible/unknown；verdict=positive/negative/null，条件不足不是negative |

ClaimRow只含claim_ref:ClaimRef、task_ref:ObjectRef(task)、title:string、gaps:Issue[]，四项必填。Evidence 摘要见 E06 的响应表。原文沿授权引用读取。

<a id="e01"></a>
## E01 Claim列表

`GET /evaluation/claims` → `evaluation.query_basis/definitions`。权限：管理员。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#15-定义存储与http)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `domain_id` | ID | 是 | 领域 |
| `task_id` | ID | 否 | Task稳定身份筛选 |
| `name` | string | 否 | 名称子串 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `items` | ClaimRow[] | 是 | 字段见下述类型，不返回个人状态 |
| `next_cursor` | string或null | 是 | 按claim_id升序当前头列表 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "domain_id": "00000000-0000-4000-8000-000000000001",
  "limit": 20
}
```

<a id="e02"></a>
## E02 Claim详情

`GET /evaluation/claims/{claim_id}` → `evaluation.query_basis/definitions`。权限：管理员；内部读定义走授权端口。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#15-定义存储与http)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `revision` | Revision | 否；头修订 | 指定历史不会升级 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `claim` | ClaimView | 是 | 精确定义及缺口 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{
  "revision": 1
}
```

<a id="e03"></a>
## E03 修改Claim及判据

`POST /evaluation/claim-commands` → `evaluation.manage_claim`。权限：管理员。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#14-保存与删除判据)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | create_claim/save_claim/save_criterion/set_method_criteria/save_aspect_rule/remove_criterion | 是 | 只带对应分支字段 |
| `domain_id` | ID | 是 | 所属域 |
| `task_ref` | ObjectRef(task) | 是 | 固定Task版本 |
| `claim_id` | ID | 非create是 | 原Claim |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `title` | string，各一 | create/save_claim是 | 基本信息 |
| `description` | string，各一 | create/save_claim是 | 基本信息 |
| `aspects` | AspectDefinition[] | create/save_claim是 | Evaluation§1.3；至少一项 |
| `criterion` | ExecutionCriterion | save_criterion是 | 新建省略criterion_id，其他字段完整 |
| `method_ref` | ObjectRef(solution) | 方法关联/方面规则时是 | Task直接方法 |
| `criterion_ids` | ID[] | set_method_criteria是 | 可以[]作为草稿缺口 |
| `rule` | AspectRule | save_aspect_rule是 | 该方法本方面规则 |
| `criterion_id` | ID | remove_criterion是 | 被引用时不能删除 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `claim_ref` | ClaimRef | 是 | 新或未变化的修订 |
| `changed` | boolean | 是 | 无变化不制造版本 |
| `gaps` | Issue[] | 是 | 定义缺口 |
| `affected_method_refs` | ObjectRef(solution)[] | 是 | 本次影响方法 |

处理边界：只追加定义快照，不启动个人评价、应用目标或复制旧Belief。

公共收据使用动作 `evaluation.manage_claim`、资源类型 `domain` 及 `domain_id`。成功后按原 `request_id` 读取，返回原修订、变更标记、定义缺口及受影响方法。创建判据时由服务端分配 `criterion_id`。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；claim_exists；revision_conflict；invalid_reference；criterion_in_use。

请求／查询参数（示意数据）：

```json
{
  "request_id": "criteria-01",
  "action": "set_method_criteria",
  "domain_id": "00000000-0000-4000-8000-000000000001",
  "task_ref": {
    "kind": "task",
    "object_id": "00000000-0000-4000-8000-000000000001",
    "version": 1
  },
  "claim_id": "00000000-0000-4000-8000-000000000002",
  "expected_revision": 1,
  "method_ref": {
    "kind": "solution",
    "object_id": "00000000-0000-4000-8000-000000000003",
    "version": 1
  },
  "criterion_ids": []
}
```

目标展示的入口分工：学生目标页读[Product P25](Product_API.md#p25)聚合结果；管理员直接核对评价可用E04，固定历史用E05；目标项Evidence列表及Evidence／Belief详情用E06。上述分工不扩大读取权限，所有引用仍核对本人空间或管理授权。

<a id="e04"></a>
## E04 目标结果查询

`GET /evaluation/spaces/{scope_id}/goals` → `evaluation.query_basis/target`。权限：本人/获授权管理员；Product内部调用query_basis，不借浏览器身份调用HTTP。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#55-目标结果http与查询状态)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `target_basis_ref` | Ref | 否；当前采用依据 | 省略时先由Product授权读取 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `target_basis_ref` | Ref | 是 | 实际查询依据 |
| `processing` | GoalProcessing | 是 | 本次目标处理状态 |
| `pending` | boolean | 是 | 是否另有后续评价尚未结束 |
| `failure_ref` | Ref或null | 是 | 当前请求处理最终失败时给出 |
| `current_result_ref` | Ref或null | 是 | 匹配依据的结果 |
| `result` | GoalResult或null | 是 | 未计算不冒充不足 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="e05"></a>
## E05 固定目标历史

`GET /evaluation/spaces/{scope_id}/goal-results/{ref}` → `evaluation.query_basis/target`。权限：本人/管理员。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#55-目标结果http与查询状态)。

除路径与共同认证头外，无业务请求字段。

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `result` | GoalResult | 是 | 不可变结果 |
| `is_current` | boolean | 是 | 读取时是否当前，不改current_state_applied |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="e06"></a>
## E06 评价依据与Evidence列表

`GET /evaluation/spaces/{scope_id}/basis` → `evaluation.query_basis`。权限：本人/管理员/本次教学授权；补齐既有query_basis查询投影。处理规则：[Evaluation处理规则](../Evaluation_Space_Design.md#54-query_basis查询处理情况与判断依据)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `view` | processing/target/belief/evidence/event | 是 | 从空间事件反查时使用event，限管理员 |
| `result_id` | UUID | target列表是 | 固定目标结果 |
| `item_id` | ID | target列表是 | 该结果的目标项 |
| `snapshot_id` | UUID | belief是 | 固定发布快照 |
| `claim_id`、`claim_revision` | UUID、int | belief是 | 分项定义 |
| `method_id`、`method_version` | UUID、int | belief是 | 实际方法 |
| `aspect_code` | string | belief是 | 具体评价方面 |
| `evidence_id` | UUID | evidence是 | 固定单条证据 |
| `event_id` | UUID | processing、event是；evidence可选 | 原触发、反查事件或该证据允许读取的一个来源 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `view` | 请求枚举 | 是 | 与请求对应 |
| `basis_ref` | Ref或null | 是 | 固定结果或快照；未处理可null |
| `belief` | BeliefItem或null | belief是 | 分项判断 |
| `evidence` | EvidenceView | evidence是 | 证据解释、源引用及本条导致的概率变化 |
| `source` | SourceExcerpt | evidence选择event_id时有 | 仅返回本证据已经关联的原文片段 |
| `items` | Evidence摘要[] | target/belief/event是 | evidence_ref、aspect_code、qualification、verdict、reason、source_event_refs，以及下述来源时间字段 |
| `next_cursor` | string | 有下一页时返回 | 绑定身份、范围及当前筛选 |
| `processing` | not_found/pending/completed/failed | processing是 | 查询源事件的评价处理状态，不启动工作 |

摘要中的 `occurred_at` 取固定评价输入中的服务端作答受理时间或教学机会结束时间。`source_activity` 区分有检测轮的作答（detection）、其他作答（answer）和教学机会（teaching）。`timed_event_id` 只在触发事件已列入 source_event_refs 时返回。客户端按北京时间显示，只在打开这个事件的原文时沿用该时间。来源缺失时省略相应值。

处理边界：目标→Evidence列表→单Evidence→源事件；来源事件不直接替代目标依据列表。每个view只返回对应字段，其他分支字段省略。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；引用与空间不符forbidden；未知分项not_found。

请求／查询参数（示意数据）：

```json
{
  "view": "target",
  "result_id": "00000000-0000-4000-8000-000000000001",
  "item_id": "00000000-0000-4000-8000-000000000009",
  "limit": 20
}
```

## 内部发布与计算入口

| 入口 | 调用与字段合同 | 边界 |
| --- | --- | --- |
| read_claim_contract | Product及获授权取材 | [Evaluation§1.2](../Evaluation_Space_Design.md#12-课程检查的定义读取)为唯一字段定义 |
| read_publication | Runtime委托Evaluation；scope_id、publication_type、publication_ref? → available/not_found及MasterySnapshot | 完整载荷沿[§5.1](../Evaluation_Space_Design.md#51-学习者掌握状态的发布视图)；只读快照 |
| query_basis | Product/Interaction/管理员查询适配；E06参数及access_context | 不允许读取Evaluation私有表或修改Evidence |
| evaluate_submission / apply_learning_opportunity | 已登记原事件 → 固定输入、解释、数值处理、发布结果 | AI与程序分工沿[§2—3](../Evaluation_Space_Design.md#2-原始事实到evidence)；不是HTTP重算入口 |

字段含义仍以Evaluation业务载荷为准，数据库分册只决定如何保存。跨Space有加工任务的触发统一走事件，以上只读或同库保护端口不绕过异步处理边界。

## 依据查询样例

E06的target分支先返回证据摘要，点击后以evidence_ref读取详情及来源事件：

```json
{
  "view": "target",
  "basis_ref": {
    "owner": "evaluation",
    "type": "goal_result",
    "id": "goal-result-01"
  },
  "items": [
    {
      "evidence_ref": {
        "owner": "evaluation",
        "type": "evidence",
        "id": "evidence-01"
      },
      "qualification": "eligible",
      "aspect_code": "independent",
      "source_activity": "detection",
      "occurred_at": "2026-11-24T08:31:00Z",
      "timed_event_id": "answer-event-01",
      "verdict": "positive",
      "reason": "本次无当题帮助，列式与结果符合要求。",
      "source_event_refs": [
        "answer-event-01"
      ]
    }
  ],
  "next_cursor": null
}
```

此例仅展示传输结构，不给出未经算法计算的概率。processing=pending/failed时，已有合法结果可继续展示并注明处理情况；不得生成一条新的达标结论。

## 教材提炼的评估标准

管理员先选教材和已发布提炼。令 `M=/api/m1/evaluation/textbooks/{book}/extractions/{extraction}/models`。

| 操作 | 入口 | 结果 |
| :--- | :--- | :--- |
| 生成草稿 | 教材助手消息，edition_job.action=assess | 指定版任务和方法、标准名称、侧重点。后台逐任务生成，全部成功后保存一套草稿 |
| 列出标准 | GET M | 本提炼的草稿和发布版，按版本倒序 |
| 保存或发布 | POST M/{model} | 核对预期修订。发布须完整覆盖提炼任务、方法和四个评价方面，每个任务获得本套自己的 Claim |
| 目标选用 | GET /api/m1/evaluation/models/{model}/claims | 已发布标准的成员。目标保存时再次核对标准归属和成员 |

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
| v0.2 | 2026-11-15 | 明确学生目标聚合、管理查询及Evidence／Belief读取入口。见MVP决定登记§95。 |
| v0.3 | 2026-11-15 | 统一事件事实源、正文来源及查询投影，承接同事务写入与按需订阅；见MVP决定登记§96。本轮仅修改文档。 |
| v0.4 | 2026-11-23 | 登记 Claim 定义写入、固定修订查询和公共收据 |
| v0.5 | 2026-11-23 | 登记目标、概率、Evidence 与来源事件的双向查询 |
| v0.6 | 2026-11-25 | 增加证据来源类别、发生时间与原文时间归属 |
| v0.7 | 2026-11-28 | 登记按教材提炼生成整套标准、手改、发布与目标选用。 |
