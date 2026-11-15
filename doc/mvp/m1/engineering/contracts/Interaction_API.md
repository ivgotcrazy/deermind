# M1 Interaction API

> **版本**：v0.1<br>
> **状态**：接口与消息详细设计稿，待用户审阅；未编码<br>
> **维护与评审**：Codex 编写及自检，用户审阅<br>
> **写作规范**：[系统设计规范](../../../../top/DeerMind_System_Design_Writing_Standard.md)<br>
> **更新日期**：2026-11-15

学生推进交流的入口按空间串行。查询、教材浏览和呈现回执不占聊天入口；stop_reply是忙时唯一学生控制例外。所有入口共用[总册](../API_and_Message_Design.md)认证、回执和错误。运行配置、消息与活动的业务语义仍由Interaction维护。

## 共用视图与输入

| 类型 | 字段 | 约束 |
| --- | --- | --- |
| ActivityRef | {activity_id:ID,revision:Revision} | 运行修订；不替代配置版本 |
| ActivityView | activity_ref、type、name、started_at、parent_id:ID\|null、root_id:ID、node_id:ID、run_state、first_message_ref:ID\|null、children:ActivityView[] | 类型与运行状态沿Interaction§2.5；树目录不返回私有规则/候选 |
| CurrentView | current_activity:ActivityView\|null、path:ActivityView[]、active_input_id:ID\|null、allowed_actions:string[]、latest_message_seq:int、proactive_cards:Ref[]、processing:Processing | 只返回当前合法动作；无活动不是失败 |
| MessageView | message_id:ID、message_seq:int、role:student/assistant/system、parts:MessagePart[]、activity_ref:ActivityRef\|null、committed_at:Timestamp | parts沿Interaction§2.4；只含已提交内容 |
| StudentInput | text:string或null、attachment_refs:ID[]、explicit_refs:Ref[] | text和附件至少一项非空；浏览位置不自动进入explicit_refs |
| AnswerInput | text:string或null、content:RichContent或null、attachment_refs:ID[] | 至少一项实际作答；结构化content用途为作答，不接受HTML脚本 |

Activity与Message的显示字段由所有者投影，不能让浏览器读数据库后自行拼装。教学意图由handle_input解释，前端不得声称“已独立完成”或“已关闭检测轮”。

<a id="i01"></a>
## I01 活动配置读取

`GET /interaction/activity-configs/{activity_type}` → `interaction.manage_activity_config`。权限：管理员；课程检查走内部端口。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#11-manage_activity_config维护活动配置)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `config_ref` | Ref | 否；当前包 | 指定读取历史包 |
| `config_kind` | blueprint/rule/strategy/binding | 否；完整包 | 只读筛选 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `config_ref` | Ref | 是 | 固定配置包 |
| `definition` | ResolvedActivityConfig及其定义 | 是 | Interaction§1.3完整结构 |
| `gaps` | Issue[] | 是 | 未完整项 |
| `usage_refs` | Ref[] | 是 | 当前引用位置 |

处理边界：只读；无数据不等于读取失败，不产生学习或评价事件。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)。

请求／查询参数（示意数据）：

```json
{}
```

<a id="i02"></a>
## I02 活动配置保存

`PUT /interaction/activity-configs/{activity_type}` → `interaction.manage_activity_config`。权限：管理员。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#11-manage_activity_config维护活动配置)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `config_kind` | blueprint/rule/strategy/binding | 是 | 配置对象种类 |
| `config_ref` | Ref或null | 是 | 已有对象给引用；新规则/策略为null |
| `expected_revision` | Revision或null | 是 | 既有包给当前包修订；首次明确null |
| `definition` | 对应Interaction§1.3载荷 | 是 | 只保存此类对象，不接收运行状态 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `config_ref` | Ref | 是 | 新解析包 |
| `definition_ref` | Ref | 是 | 保存的对象修订 |
| `affected_refs` | Ref[] | 是 | 受影响绑定 |
| `gaps` | Issue[] | 是 | 草稿不足 |

处理边界：活动类型协议值explanation/question_answer/detection/free_chat；运行中活动保留原包。开始/结束节点不可删除，节点不得弱化硬规则。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；revision_conflict；invalid_reference；invalid_blueprint。

请求／查询参数（示意数据）：

```json
{
  "request_id": "config-01",
  "config_kind": "strategy",
  "config_ref": null,
  "expected_revision": 1,
  "definition": {
    "activity_type": "explanation",
    "name": "举例比较",
    "purpose": "对比两种数量关系",
    "applicability": "原量概念不清",
    "materials": [],
    "approach": "比较增加量与新量",
    "adaptation": "仍不清楚时换图示",
    "finish_conditions": "能解释区别",
    "enabled": true
  }
}
```

<a id="i03"></a>
## I03 学生自然输入

`POST /learning-spaces/{scope_id}/inputs` → `interaction.handle_input`。权限：空间所属学生且满足使用条件。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#33-handle_input处理一次学生交流)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `input` | StudentInput | 是 | 原文与显式引用，不随浏览器当前章节限制 |

受理：202 `AcceptedReceipt`；最终结果从原收据查询，`result`为下表。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `input_id` | ID | 是 | 原输入 |
| `message_refs` | ID[] | 是 | 已正式提供的回应与提示 |
| `current` | CurrentView | 是 | 当前活动 |
| `outcome` | completed/needs_input/blocked/failed/cancelled | 是 | 交流结果，不表示目标已达标 |

处理边界：保存输入和受理后才返回；回复检查保存后整条显示。聊天内要求检测继续同一后台工作，不再重复派发。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；interaction_busy不受理；identity_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "chat-01",
  "input": {
    "text": "为什么增加四分之一还要加回原量？",
    "attachment_refs": [],
    "explicit_refs": []
  }
}
```

<a id="i04"></a>
## I04 活动控制和停止

`POST /learning-spaces/{scope_id}/activity-actions` → `interaction.control_activity`。权限：本人；内部可复用处理函数。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#21-control_activity控制活动与检测开始)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `action` | pause/resume/finish/switch/start_detection/continue_detection/stop_reply | 是 | return_from_child仅程序内部，浏览器不可提交 |
| `activity_ref` | ActivityRef | 非stop_reply是 | 当前活动 |
| `expected_activity_revision` | Revision | 非stop_reply是 | 匹配活动修订 |
| `plan_ref` | PlanRef | start/continue_detection是 | 学生明确确认的精确题单 |
| `content_request` | StudentInput | switch是 | 新学习内容的明确请求 |
| `target_input_id` | ID | stop_reply是 | 正在处理的原输入；其余活动字段省略 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `current` | CurrentView | 是 | 保存后的运行位置 |
| `outcome` | changed/already_committed/stopped | 是 | 停止不能撤回已提供的内容 |
| `committed_refs` | Ref[] | 是 | 已发生事实引用 |

处理边界：开测须确认题单；准备题完成不自动开测。停止只废止本输入继续提交，不取消Evaluation或回滚已保存答案。switch若要AI准备，按原入口受理规则返回202。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；interaction_busy；revision_conflict；stale_plan；blocked。

请求／查询参数（示意数据）：

```json
{
  "request_id": "start-01",
  "action": "start_detection",
  "activity_ref": {
    "activity_id": "00000000-0000-4000-8000-000000000001",
    "revision": 3
  },
  "expected_activity_revision": 3,
  "plan_ref": {
    "plan_id": "00000000-0000-4000-8000-000000000002",
    "revision": 1
  }
}
```

<a id="i05"></a>
## I05 提交作答

`POST /learning-spaces/{scope_id}/answers` → `interaction.submit_answer`。权限：本人。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#42-submit_answer提交实际作答)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `submission_id` | ID | 是 | 客户端稳定作答身份，重试不变 |
| `task_use_ref` | Ref | 是 | 实际题目使用，不是仅题目模板 |
| `activity_ref` | ActivityRef | 是 | 本活动 |
| `round_ref` | Ref或null | 是 | 正式轮必填；练习为null |
| `expected_round_revision` | Revision | 正式轮是 | 提交前轮修订 |
| `answer` | AnswerInput | 是 | 原始内容；不接受概率/得分结论 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `submission_ref` | Ref | 是 | 已保存答案 |
| `event_ref` | ID | 是 | AnswerSubmitted |
| `round_state` | closed或null | 是 | 检测关闭；练习无轮 |
| `result_keys` | ResultKey[] | 是 | 可查的掌握/目标结果身份 |
| `feedback_runtime_ref` | ID或null | 是 | 如需生成本题反馈 |

处理边界：成功200确认作答保存；允许反馈时可带后台工作引用。Evaluation独立消费事件，后台反馈失败不把原答案改成未提交。聊天识别答案由程序带source_input_ref内部调用，浏览器不能指定别人的输入。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；round_closed；revision_conflict；identity_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "answer-01",
  "submission_id": "00000000-0000-4000-8000-000000000011",
  "task_use_ref": {
    "owner": "interaction",
    "type": "task_use",
    "id": "00000000-0000-4000-8000-000000000012"
  },
  "activity_ref": {
    "activity_id": "00000000-0000-4000-8000-000000000001",
    "revision": 4
  },
  "round_ref": {
    "owner": "interaction",
    "type": "round",
    "id": "00000000-0000-4000-8000-000000000013"
  },
  "expected_round_revision": 1,
  "answer": {
    "text": "120×1/4+120=150",
    "content": null,
    "attachment_refs": []
  }
}
```

<a id="i06"></a>
## I06 显示回执

`POST /learning-spaces/{scope_id}/presentations` → `interaction.record_presentation`。权限：本人已授权内容。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#34-record_presentation记录内容呈现)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `presentation_id` | ID | 是 | 稳定回执身份，不另造业务请求 |
| `surface` | chat/history/textbook | 是 | 显示位置 |
| `resource_ref` | Ref | 是 | 确切已提供内容 |
| `content_part_refs` | Ref[] | 是 | 实际报告片段 |
| `client_reported_at` | Timestamp或null | 否；null | 只作参考 |

成功：200，直接返回下表对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `presentation_ref` | Ref | 是 | 已保存回执 |
| `received_at` | Timestamp | 是 | 服务端收到时间 |

处理边界：200直接确认presentation_ref/received_at，按presentation_id去重；不占聊天入口、不更新概率、不决定是否正式提供教学。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；identity_conflict。

请求／查询参数（示意数据）：

```json
{
  "presentation_id": "00000000-0000-4000-8000-000000000022",
  "surface": "chat",
  "resource_ref": {
    "owner": "interaction",
    "type": "message",
    "id": "00000000-0000-4000-8000-000000000023"
  },
  "content_part_refs": [],
  "client_reported_at": null
}
```

<a id="i07"></a>
## I07 对话当前状态与历史

`GET /learning-spaces/{scope_id}/conversation` → `interaction.query_conversation`。权限：本人/获授权管理员；原文评价另用内部端口。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#22-query_conversation查询当前交流和历史)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `view` | current/activity_tree/messages | 是 | 三种视图 |
| `activity_ref` | Ref | 树展开或消息筛选可选 | 同空间 |
| `anchor_message_id` | ID | messages可选 | 定位历史锚点 |
| `after_seq` | int，各可选 | messages可选 | 首屏上界服务端确定 |
| `upper_seq` | int，各可选 | messages可选 | 首屏上界服务端确定 |
| `cursor` | string | 否；首次省略 | 不透明续页游标，绑定筛选、身份及读取范围 |
| `limit` | int | 否；沿总册分页配置 | 正整数，不超过部署已接收上限 |

响应：200，直接返回下列对象。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `current` | CurrentView | current是 | 当前路径独立读取 |
| `items` | ActivityView[]或MessageView[] | 目录/消息是 | 对应请求视图 |
| `next_cursor` | string或null | 目录/消息是 | 续页 |
| `last_seq` | int，各一 | 消息是 | 范围固定 |
| `upper_seq` | int，各一 | 消息是 | 范围固定 |

处理边界：回看不恢复活动；current分支不返回items，其他分支不返回current。树按开始时间/稳定ID排序，子活动只在请求展开范围返回。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；invalid_cursor；forbidden。

请求／查询参数（示意数据）：

```json
{
  "view": "messages",
  "after_seq": 0,
  "limit": 20
}
```

<a id="i08"></a>
## I08 响应主动任务

`POST /learning-spaces/{scope_id}/proactive-tasks/{task_id}/responses` → `interaction.respond_proactive_task`。权限：本人。处理规则：[Interaction处理规则](../Interaction_Space_Design.md#52-respond_proactive_task响应主动任务)。

请求字段（路径字段不重复放入正文）：

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `request_id` | RequestId | 是 | 同一次操作重试沿用；不随重新连接改变 |
| `expected_revision` | Revision | 修改时是 | 要修改的资源修订；冲突后重读，不自动覆盖 |
| `response` | accept/defer/reject | 是 | 接受/暂缓/拒绝 |

成功：200 `MutationReceipt`，其中`result`为下表；需要后台检查的分支另按说明返回202。

| 字段 | 类型 | 必填／缺省 | 含义与约束 |
| --- | --- | --- | --- |
| `task_ref` | Ref | 是 | 任务及新修订 |
| `state` | pending/deferred/rejected/accepted/running/waiting_result/finished/cancelled/execution_failed | 是 | Interaction§5.3业务状态 |
| `activity_ref` | Ref或null | 是 | 已关联执行 |
| `runtime_ref` | ID或null | 是 | 接受后的准备工作 |

处理边界：暂缓当天不再催，拒绝同依据不再提示；接受检测先准备和确认题单，不自动开始轮。

错误：共同错误见[总册§2](../API_and_Message_Design.md#2-认证回执与错误)；interaction_busy；revision_conflict。

请求／查询参数（示意数据）：

```json
{
  "request_id": "defer-01",
  "expected_revision": 1,
  "response": "defer"
}
```

## 内部接口

| 端口 | 调用方与完整合同 | 结果与限制 |
| --- | --- | --- |
| read_activity_contract(access_context,activity_type,config_ref?) | Product准备检查、Interaction运行；[§1.2](../Interaction_Space_Design.md#12-课程检查与活动采用) | 固定蓝图、规则、推荐策略、生效引用及gaps；无写入 |
| read_evaluation_facts(access_context,scope_id,trigger_event_id,related_event_refs=[]) | Evaluation；[§2.3字段表](../Interaction_Space_Design.md#23-评价原文的授权读取边界) | source、content_parts、provision_facts、help_basis、presentation_facts、completeness；不返回私有记忆/判题结论/草稿 |
| continue_after_result | 已登记Wait的接续；[§6.3—6.4](../Interaction_Space_Design.md#63-保存等待与恢复动作) | 先验证结果及活动仍可接续，再只提交一次；浏览器不可调用 |

Evaluation读取原文必须沿已授权源事件；直接给任意message_id不构成取证权限。未确定的资料与读取故障分开，不能以complete空列表掩盖故障。

## 已提交不等于已评价

I05接受作答后返回本次提交引用；Evaluation自行按原始事件处理。停止本次回复不撤销这一提交：

```json
{
  "request_ref": "answer-request-01",
  "result": {
    "submission_ref": {
      "owner": "interaction",
      "type": "submission",
      "id": "submission-01"
    },
    "event_ref": "answer-event-01",
    "round_state": "closed",
    "result_keys": [
      {
        "scope_id": "space-01",
        "trigger_event_id": "answer-event-01",
        "producer": "evaluation",
        "result_kind": "belief_result"
      }
    ],
    "feedback_runtime_ref": "execution-feedback-01"
  }
}
```

实际字段以I05响应表为准；聊天收到changed后重新读取已保存消息，不把通知里的状态显示成“已掌握”。

## 修订记录

| 版本 | 日期 | 修改 |
| --- | --- | --- |
| v0.1 | 2026-11-15 | 补齐接口/消息字段、边界及样例；具体格式待审阅，未编码 |
