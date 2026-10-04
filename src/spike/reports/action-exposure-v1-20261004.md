# D1/D2 行动与帮助披露验证报告

日期：2026-10-04。批次：`action-exposure-20261004T073701Z-4e9959cb65b4`。结论：**AA-D01、AA-D02 在运行前声明的确定性机制范围内 SUPPORTED**。D1/D2 场景完成，完整 Spike 未完成；AA-A02 仍为 DENIED，v11 语义方案仍为 INCONCLUSIVE，Gate E/F 保持 OPEN。

## 范围与结果

本轮按[运行前方案](action-exposure-design-20261004.md)和 `fixtures/action-exposure-v1.json` 各执行一次 D1、D2，共 124 项检查通过。执行没有外部模型调用，没有失败后替补运行。Observation、Policy 选择和 Evidence 含义及语义 PASS 为显式脚本 fixture，展示确认来自受控 mock；正式 Context / Candidate / Commit、权限核验、行动执行、事实记录和依赖解析使用共享 runtime。该支持不涵盖真实 Policy 的质量或 LLM 对帮助影响的解释能力。

| 场景 | 检查数 | 关键证据 |
| --- | ---: | --- |
| D1 | 91 | 六个变体，五个正式行动意图，三次确认披露，一次未发生，一次结果不确定；可用未使用变体没有意图或披露 |
| D2 | 33 | 一次确认提示、帮助前后两条正式 Observation、三条 Claim-relative Evidence，同时解析为 Current |

D1 的三个确认披露分别为部分展示、完整展示、以及发生在作答之后的提示。部分展示只记录实际确认的“再检查一”，完整展示记录“再检查一下 42÷6。”；两者明确区分 PARTIAL / FULL。作答早于提示时，后续查询仍能看到提示已发生，但 before_response 为 false，不把它倒填成此前的帮助。NotOccurred 和 Indeterminate 没有进入 ActionOccurrence factual history；查询分别保留两种状态，不把缺少确认理解成已发生，也不把未知等同于明确未发生。

展示源由 mock 的实际确认形成，并记录 exact intent、实际 payload、完整度和 renderedAt。重建时沿 ActionExecutionResult、ActionOccurrence、DisplayAcknowledgement 和作答时间读取，按 learner / scope / purpose / episode 限定范围，没有 durable AssistanceExposureModel。即使重新创建执行器实例，同一 intent 的重复调用也返回原有终态，不新增展示；Indeterminate 不会被自动重试成 Occurred。该幂等实现扫描既有执行历史，是单进程验证实现，不代表生产持久化或并发协议。

D2 中三条 Evidence 都经 Evaluation owner 正式提交，绑定同一后续 Observation、同一 ActionOccurrence、同一帮助前 Observation，同时分别引用 C1/C2/C3:v1。C1 记录本次完成不能当作独立任务成功；C2 保留帮助前已经选择单位率策略的依据；C3 承认局部提示，但表达后续算术仍可能保留部分正面证据。三种解释共同存在且均可按当前依赖解析，不要求将整次 response 简化为一个 assisted 布尔值。这里验证表达和依赖机制，不验证这些脚本解释的模型质量、数值 strength 或学习者实际使用了提示。

## 边界检查与证据复核

调用前 174 项本地测试通过，其中新增十项涵盖 effect-time authority / data authority 撤销、expiry、Policy 依据 correction、exact payload 不可替换、部分确认、终态幂等、当前读取权限、历史事实不被后续 correction 改写，以及 D1/D2 规定场景。另验证即使不同 payload 已成为正式 PolicyOutcome，也不能扩大原有行动授权。安全失败均发生在展示确认之前，不产生 ActionOccurrence。这些检查支持该实现的机制约束，不独立关闭 E/F 或 X3。

[离线审计](action-exposure-audit-20261004.json)核对 101 个冻结输入指纹、八份快照指纹及所有检查结果。六个 D1 世界和一个 D2 世界共有 16 条派生记录，全部对应真实成功 CommitOutcome，并逐条匹配 Candidate digest、语义校验、精确内容及追加的 provenance；没有用直接安装派生 fixture 代替正式提交。六个 ActionIntent 均对应正式 Execute PolicyOutcome 的原样 payload，四个 ActionOccurrence 均与展示确认内容、时间和原意图绑定一致。D2 的三个 Current 解析结果及共同依赖也已复核。

原始目录为 `src/spike/runs/action-exposure-20261004T073701Z-4e9959cb65b4`，保留 manifest、D1.jsonl、D2.jsonl、summary.json。原始 runner 的评估待定字段不回填；正式结论及证据指纹见 [AA-D01/AA-D02 评估](assumption-d1-d2-20261004.json)。

## 设计后果与剩余工作

这批证据支持继续沿用 occurrence / actual disclosure / ordered lineage，无需为基本暴露事实新建独立权威模型；帮助对 Claim 的影响留在 Evaluation 的相对解释中，不在 Interaction 写入全局污染结论。确定性程序处理枚举、精确引用、权限和时序，脚本样例只隔离机制，不引入关键词语义分类。

当前 ActionRuntime 明确将整个 Policy 依据作为 effect-critical 依赖；后续真实 Policy 接入时还需检验关键依据的声明和选择，不应把所有无关事件都当作重决策触发。受控时钟的 recordedAt 代表本轮事件发生时间，晚到事件、真实 UI / network 确认和生产并发均未验证。完整 X3 的解释变化与历史帮助共存、X5 的诊断转教学、新独立机会，以及 E/F 真实模型攻击链仍待执行。

总体完成范围从 4/17 增至 6/17：B1、B2、C1、C2、D1、D2 已在声明范围完成。接下来将真实 Policy 接入现有 ActionRuntime，预先固定 E1 的合法性与有用性分开评估及模型调用预算，再推进严格串行处理到行动结果的 E2 和组合场景；本轮不追加 Observation S1/S2。
