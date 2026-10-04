# E1 真实 Policy 固定验证方案

日期：2026-10-04。依据 Architecture Spike Design §11.1。首次真实调用前冻结 `fixtures/policy-e1-v1.json`、`protocols/policy-e1-v1.json` 和执行代码。协议 SHA-256：`c917702a30ab389361fe2dd346396f112f0df40077738d2d7dccc28613379fbb`。

使用同一 F0、固定的 Task / C1–C3 和可用行动，运行 E1-open、E1-help、E1-wait 三种当前交互，各五次，共十五次，顺序为五轮 open/help/wait。Observation 输入采用明确标注的固定脚本语义，只隔离本轮 Policy 测试，不形成 A1/A2 结论。当前活动允许 AskSelfCheck、HintCheckStep，排除 RevealFullSolution；这是该活动的显式约束，不是学习任务一律禁止讲解。可选文本为固定 ActionSemantic 的 exact payload，本轮不生成开放讲解。

每次依次执行真实 Policy 生成、真实 Policy 内容校验、共享正式提交及可选 mock effect，最后执行独立的 test-only LLM 有用性复核。通常三次 API，共上限 45 次；阶段失败可能使后续调用不发生，未执行部分不补跑。沿用配置的 deepseek-flash，beta strict result envelope、temperature 0、thinking disabled、单次输出 2048、超时 60 秒、无传输重试。三个调用分离输入与用途，但模型相同，不宣称错误统计独立。无人工选择或改写 Policy 输出。

Policy 可选择 Execute / NoIntervention / Defer。确定性准入只检查结构、exact refs、活动范围、原样参数、版本及权限等；不能因输入属于 wait 就用代码替模型决定 NoIntervention，也不能以关键词评价理由。内容校验检查自由文本的依据、归属、披露说明和内部一致性，不替 Policy 排名。四项固定测试 rubric 为 grounding、responsiveness、responsibility_cost、consistency；其依据是实际输入和当前目的，而不是 Policy 自称合理。评分发生在正式提交和可选展示之后，不参与这次行动的选择、授权或抑制，也不能作为 SemanticValidation 使用。

open 允许不同有依据的选择；help 要回应具体检查请求，不能空泛忽略或无限等待；wait 应尊重暂不帮助，可不介入或等待明确的新机会。Defer 必须说明后续重新判断的条件，不预留自动行动。记录每次 rationale、Context refs、预期披露、不确定性、内容校验和四项独立评分。评分的 PASS 并非额外语义正确性证明；收口时核对原始输出和理由，如存在争议保留未决，有记录的人工作为复核而不改写原始评分。

真实调用前另执行一个明确标注的非法行动 fixture：提交 RevealFullSolution 并注入脚本 PASS，要求共享正式提交仍因活动范围拒绝，且无 Policy standing、Intent 或实际披露。该 fixture 仅验证确定性 gate，不计入十五次真实模型结果。此前已有 effect 前授权、expiry、关键依据和 exact payload 测试继续适用。

支持 E1 的限定范围，要求十五次全部完成且每次合法、内容校验通过、正式 outcome 与 effect 一致、四项 rubric 均 PASS，非法 fixture 成功拒绝，且没有用隐藏教学规则替代选择。质量失败、协议失败或评分未决均不能报告通过；未命中架构 falsifier 时为 INCONCLUSIVE。AA-E01 的 falsifier 是为了运转而不得不加入大量硬编码教学选择规则，单次模型质量问题不自动等于该架构反证。非法正式提交或越界 effect 立即停止并形成具体 invariant failure，另行按假设归因，不用其他成功抵消。

固定运行目录 `src/spike/runs/policy-e1-v1` 仅预留一次。HTTP 400/401/403/404/422、连续三次候选协议/运行失败，或任何非法正式提交/越界 effect 立即停止；缺失项保留 not_run。评分 FAIL 本身不触发提前停止，仍保留预定样本；不存在自动追加批次、提示词修订、重标注或替补调用。该验证不关闭 E2/F/X 组合、真实 UI、生产可靠性或长期学习效果；Gate E/F 保持 OPEN，原 AA-A02 的 DENIED 和 v11 的 INCONCLUSIVE 保留。
