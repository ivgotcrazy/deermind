# X5：诊断转教学及新独立机会（2026-10-05）

本批固定执行已结束，结论为 **INCONCLUSIVE**。5 次完整路径尝试共调用 DeepSeek Flash 24 次，完整路径为 0/5，没有实际到达活动切换或讲解阶段，四个需要真实阶段快照的边界分支全部记为 NOT_RUN。没有追加调用或替补样本。X5 不加入完整验收计数，当前仍为 9/17；原 AA-A02 的 DENIED、其余未决结论以及 Gate E/F OPEN 均保持。

## 执行与失败归因

| 尝试 | 调用数 | 实际到达的位置 | 停止原因 |
| --- | ---: | --- | --- |
| 1 | 4 | 初始作答 Observation 校验 | 明确指出除法错误，但只复述最终答案 120，未完成要求的最终结果判断；语义 FAIL，未提交 |
| 2 | 4 | 初始作答 Observation 校验 | 同样缺少最终结果判断；语义 FAIL，未提交 |
| 3 | 4 | 初始作答 Observation 校验 | 同样缺少最终结果判断；语义 FAIL，未提交 |
| 4 | 10 | 初始 Observation、C2 fixture Evidence、首次 NoIntervention 正式提交，第一轮结算；第二轮真实理解学习请求 | 请求审查返回 `request` 判据，但本次适配的 schema 枚举仍为旧列表，触发 OutputSchemaMismatch |
| 5 | 2 | 初始 Observation 已生成，进入职责分类 | 模型把字段名返回为 `candidate.description`，真实候选字段为 `description`；触发 InvalidResponsibilitySegment |

前三次是生成内容不满足本批冻结合同，不是误放，也不把它们自动判为语义误拒。模型说明 8×15=120 与错误中间值一致，确实不等于明确判断本题正确总价为 105。第四次的结构失败属于本次协议适配的实现缺陷：语义判据新增了 `request`，输出契约却没有同步。不能将这个缺陷归咎于服务不稳定或模型幻觉。第五次返回满足宽泛 JSON 结构，但未满足候选字段精确绑定；24 次调用中 adapter 记录 23 次 COMPLETED、1 次 FAILED，23 不能解读为 23 次有效语义校验。

第四次中，“Learner asks for a complete explanation of the problem, stating they want to learn the method first.” 已由真实模型生成，职责分类与空算术提取完成，但未取得 Observation standing。完整讲解、切换和新题正确作答均未执行。本批没有网络断连、越权实际讲解或历史事实改写的记录；由于没有到达相关效果阶段，这不能证明完整路径安全或有效。

## 已交付的机制与验证边界

实现了明确类型的 Activity Control、受信 mock 确认和不可变 ActivityTransitionOccurred。活动转换不使用事实 correction；成功事件终止旧活动的当前适用性，旧活动和旧决策历史仍可读取。精确 Policy 提交、执行权限与数据用途、ActionIntent、实际 Control 结果、结果处理、同一轮内新的决策周期分别保留。只有成功 Control 且结果已处理时才能继续同一轮；普通展示、失败 Control 或仅有意图均不能开启下一决策周期。

完整讲解和固定新题题面使用登记的精确 ActionSemantic；模型负责理解请求、选择动作及语义审查。Control 和题面展示由显式类型与帮助披露区分。新作答的 Evaluation fixture 保留新 TaskInstance、实际前题讲解和帮助前 C2 依据，不把换题或答对升级为独立掌握，也不重复计作新的独立策略选择。这里是已实现并通过本地模拟的行为，不是本批真实模型已经走通的结果。

调用前全量回归 211 项通过，包括新增的 6 项 X5 测试；这些本地测试用明确脚本的生成及审查，验证完整路径和四种边界机制，不提供语义能力证据。实际模型批次仅完成 14 项机制检查，没有失败检查；其覆盖限于已经到达的位置。离线审计核对 139 个冻结输入、原始调用及检查数量一致，审计 PASS 只表示证据记录一致。方案、源码、fixture 和原始结果均保留，不通过把 NOT_RUN 改名为 PASS 弥补缺口。

## 修复、限制与下一步

批次结束后另存 `observation-x5-request-v2.json`，只修正判据名称枚举，保持语义要求不变；新增 2 项离线契约测试通过。原 v1 协议、固定 runner、manifest 与失败记录保持原样，v2 未接入新批次、未调用服务，也不获得语义支持结论。即使 v2 的格式能表达判据，也不保证真实返回的片段覆盖、来源归属或职责判断正确。任何未来运行须新建显式方案，不能重开已结束的 v1。

已有证据索引引用的旧 actions/runtime 源码指纹另存精确匹配的 `.txt` 快照，当前源码指纹单独更新并保留迁移记录。旧批次 manifest 和正式评估未重写，避免把新机制代码冒充旧批次运行代码。

主要未决项是 Observation 的有用性与完整性合同、结构契约的预运行一致性检查，以及失败轮次如何显式结束或恢复。本批不自行放宽 v11、不把失败候选交给 Policy，也不改成关键词识别请求。下一步应先完成尚未独立评估的 A1 形成与有用性范围，并在统一设计收口中判断：一份来源正确但遗漏某个局部判断的 Observation 是否必须阻断整轮、与该遗漏无关的新学习请求应如何在失败收束后处理。该问题涉及产品与责任合同，不应靠继续试提示词替代设计决定。

内存运行时、单进程串行、受控 transport 交错、脚本 Evaluation 和 mock Control/display 仍是范围限制；没有生产可靠率或学习效果结论。详细证据见 [固定方案](composition-x5-design-20261005.md)、[原始汇总](../runs/composition-x5-v1/summary.json)、[离线审计](composition-x5-audit-20261005.json)及[正式评估](composition-x5-assessment-20261005.json)。
