# D1/D2 行动与帮助披露机制验证方案

日期：2026-10-04。依据 Consolidated Architecture Spike Design §4.16、§10 及 Interaction & Decision Runtime §3.13–3.16。本方案在正式运行前固定：D1、D2 各执行一次确定性场景，不调用外部模型。模型五次重复要求不适用于这些显式隔离的机制测试。

D1 覆盖已选未发生、部分披露、完整披露、可用但未使用、作答早于提示五个规定变体，另保留结果不确定变体。观察事实必须由受信 mock 展示确认产生；执行失败和结果不确定只能留在执行历史，不能成为 ActionOccurrence。部分披露保存确认的实际前缀及时间，不复制意图全文；该前缀是 mock 传输控制，不作含义判断。

Observation 和 Policy 的语义及验证结果为明确声明的脚本 fixture，但 PolicyOutcome 经共享 Context / Candidate / Commit 正式提交。ActionIntent 只能绑定这个正式 Execute 结果及其确切 ActionSemantic 和 payload，权限范围不由文本扩大。当前最小机制将整个 Policy 依据显式列作 effect-critical precondition；执行前重新检查 authority、data authority、expiry 和精确依据。这里不宣称已实现通用 Policy dependency 最小化或 E1/E2。单进程执行从检查到 mock 展示没有挂起点，真实网络和并发竞争另行验证。

本轮幂等性由既有执行历史中的 exact intent 和终态结果提供，不新增 authoritative exposure state。重复执行返回历史终态，包括 Indeterminate，不自动重试未知效果；相同 key 对不同内容或有效期冲突。历史结果读取需要当前权限，后续 correction 不改写已发生披露。Exposure 查询按 learner、scope、purpose 和 episode 关联事实，输出实际内容、完整度、renderedAt 与作答的先后关系；不推断学习者确实利用了帮助。learner stimulus 的 recordedAt 在本轮受控时钟中就是发生时间，晚到或失序网络事件不在范围内。

D2 使用固定提示“再检查一下 42÷6。”及随后 7、105 的作答。按照 §4.14 的 SCRIPTED Evaluation，分别形成 C1 Task Proficiency、C2 Strategy Selection、C3 Division Arithmetic 的 Evidence，并通过 Evaluation owner 的真实提交获得 standing。三条记录都绑定同一真实发生提示、同一后续 Observation，以及帮助前已经选择单位率策略的 Observation，同时各自绑定准确 Claim。预期依次为非独立任务成功、保留帮助前策略依据、承认局部提示但可保留部分正面算术证据；不冻结数值 strength，不把脚本解释当成 LLM 的正确性。

支持 AA-D01 的机制范围需所有规定变体从 intent / occurrence / disclosure / ordered lineage 恢复事实，且无需新增独立 durable Exposure Model。支持 AA-D02 的机制范围需三条不同解释同时正式提交并可解析为 current，不以 global assisted 标志替代 Claim-relative 表达。检查失败保留全部证据后评估，不自动替补批次；原始 runner PASS 需证据复核后才能形成 SUPPORTED。真实 Policy、有用性、A1/A2、完整 X3/X5、生产 UI / network、实际利用帮助和真实 Evaluation 模型质量均不在本轮支持范围。Gate E/F 不随 D1/D2 局部结论关闭。
