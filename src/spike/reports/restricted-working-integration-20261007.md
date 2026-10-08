# 固定工作配置的运行集成与请求审计（2026-10-07）

已将固定配置接入 [WorkingWorld / run_batch](../foundation/working_campaign.py)，用原共享 BoundaryRuntime、PolicyRuntime、RestrictedEntry、SerialSession 和 mock ActionRuntime 注册、形成、校验、提交和执行。此次是离线脚本语义验证，未加载真实 API key、未访问服务、未形成新模型质量结论。

## 1. 实际链路与精确绑定

工作输入注册为中性 identity 的原始任务作答和 CurrentInteractionInput，host 的 case ID、要求和作者预期不进入这些 payload。work 使用 v13，request 使用已有 v2；请求 Observation 只读当前请求事实，作答 Observation 只读原始题目和作答，不读取旧 Belief。Context 绑定当前串行轮次，生成前已固定协议和目的。

必需校验后 Observation 成功正式提交，才组装 Policy Context。Policy 使用 v4，Context 含当前成功 Observation、原题作答、当前请求、固定活动 envelope 和 exact registered actions。协议、语义规则、utility 规则的 refs 与 VersionContext 明确匹配，Policy material record 与 quote registry 由原 runtime 生成。提交授权分别绑定 Observation 和 PolicyOutcome 的 owner/kind，不使用无参数权限替代。失败 Observation 不进入 Policy。

Policy 校验及正式提交后，测试 utility 评审精确候选；其结果不授予提交资格、不改写候选。该固定验证若 utility 不通过就停止并收束，尚未派发的动作不执行。允许的 Execute 仍经过真实 Intent 准入、mock effect 和结果处理；NoIntervention 无 Intent 或伪造效果即可结束。

固定对照使用单独声明的脚本 Observation 基础，不替代正常生成结果，不提交或执行对照候选。有效状态与预期不符立即停止；负例还检查相应 S2/S3/S5 或 Observation 边界/职责检查，因无关原因失败不计对应缺陷识别。检查解释是否真正有来源仍须内容复核，不能以规则 ID 匹配冒充语义裁决。

## 2. 请求与停止条件审计

[离线准备入口](../run_working_integration.py)仅使用显式脚本 transport，没有真实执行开关。[冻结审计包](../review-packages/restricted-working-v1/manifest.json)保存 201 项源摘要、每例历史快照、[51 条实际 adapter 请求记录](../review-packages/restricted-working-v1/actual-requests.json)及测试输出。机器记录中 actual_outgoing_messages_audited 的 51 指请求记录数，每条包含实际 messages，而不是单条 chat message 的计数。

测试检查真实 user JSON 中不含 required_content、expected_semantic、expected_utility、required_detection、source_case 等 host 字段，并用独特 host sentinel 检查所有角色消息。候选 digest、Context、rule/material refs 和字符串引用 handles 在真实共享调用中生成，不从作者预期拼装。最大消息序列化长度 14,575 字符，低于现有 adapter 的 16,000 字符上限；这不是服务 token 容量或模型理解质量证明。

CallBudget 在每次调用之前检查全批和单例剩余调用预算，按墙钟剩余时间缩短该请求 timeout；到期不派发请求，调用返回时已越过期限也停止。首次已知反例误放只调用一次，后九项 NOT_RUN；首次 provider 失败不重试；额度耗尽不产生额外 transport 调用；Observation 失败关闭旧轮并阻止 Policy 生成。阶段结束仍不假定未确认远端 effect 已停止，当前 executor 为同步 mock。

## 3. 结果与适用限度

最终完整本地回归 332 项通过，新增 10 项集成测试；没有失败、错误、跳过或网络连接尝试。十个样例在明确脚本回应下走完，合计 51 次脚本 adapter 调用，真实模型调用为零。201 项冻结源未变化；包内摘要可复核。[运行摘要](../review-packages/restricted-working-v1/summary.json)保存各项计数。

脚本生成的 Observation 和 PASS/FAIL 是为了验证机器合同、调用次序和停止条件，不能证明 v13 已完成实际教学判断，也不能证明 Policy 对暂停、讲解或新题请求的回应合格。实际内容正确、负例理由和作者分歧仍须在真实输出上复核；该准备没有独立盲评、学习效果或 production reliability 证据。

下一步仅执行原固定计划的一次真实尝试，按预定 58 次调用和 900 秒上限、首次失败停止，不重试或扩容。执行前复核冻结源及模型配置，并保留逐请求记录；若结果不满足要求，按计划记录失败/未决及 NOT_RUN 后收口，不自动调优。原 A2 DENIED、9/17、原 Completion 和 Gate E/F OPEN 保留。
