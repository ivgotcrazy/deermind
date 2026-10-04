# X3/X4 确定性组合验证方案

日期：2026-10-04。依据 Spike §13.3–13.4。复用 ActionWorld / VersionReplayWorld 及共享 Harness、BoundaryRuntime、CurrentResolver、SecurityRuntime、ActionRuntime、ReplayRuntime。本轮外部模型调用为零；Observation、Policy、Evaluation 意义及回放 provider 为明确脚本 fixture，实际帮助披露采用已有 mock 确认，不验证新的语义准确率。

X3 单条完整确定性路径：正式 Policy → Intent → 实际局部提示 → 学习者后续作答 → 正式 O2 / E2 / B2 → 受信 owner 撤回 O2 → 旧 Evidence / Belief 立即 current-unusable → 依次正式提交新 O / E / B revision。重算每一步检查当前状态，不允许提前恢复下游；旧候选不能因新依据出现而被静默重绑。ActionOccurrence、DisplayAcknowledgement、exact payload / completeness / rendered_at、Intent 与终态结果均保持原字节和引用，exposure view 仍从同一次实际披露重建，不新增 authoritative Exposure Model。重新读取已完成 Intent 只能返回原终态，不能重复展示。correction 仅改变解释依据，不倒推学习者没有得到帮助。

X4 三个固定分支从同一个已正式提交历史结果 / ReplayManifest 快照开始。每支先验证合法 historical_reconstruct 与 reexecute 为 FULL；随后分别撤销 replay DataUseGrant、撤销并收窄原始材料读取的数据类型授权、或使用拥有操作权限但无对应 DataUseGrant 的 research 用途凭据。每支均尝试历史重建与重新执行，须得到 UNAVAILABLE / DataAuthorityDenied，无历史视图、生成内容或模型调用；原始字节和历史记录不变，SecuritySignal 可追溯当前 ReplayRequested。第一和第三分支要求零 payload read；第二分支允许内部读取仍有权限的 metadata / records，但不能读取未获准原始字节、形成 provider 输入或向调用者返回已收集内容。

replay grant 撤销分支还安装一个新的受信等范围 grant 验证恢复后可再次 FULL 重建 / 重新执行，不能恢复已撤销 grant 本身。每次合法 provider 输入、原始字节读取、权限拒绝和回放结果分别记录；模型输入次数是 fixture provider 调用计数，不是外部 LLM 调用。

两 Case 各执行一次完整声明范围；这是固定 fixture 的确定性组合，不以重复相同计算五次替代证据。全部声明路径、允许对照、拒绝效果、正式提交和历史不变性通过并审计后记组合 PASS；实现异常、缺失覆盖或归因未清记 INCONCLUSIVE；可信组合违例保留 FAIL 及设计后果。任何检查失败停止后续 Case，不追加变体或自动重跑。代码、fixture 和本方案在执行前冻结，完整证据独立保存，不改写既有 A/E/F/X 结论或 Gate 状态。
