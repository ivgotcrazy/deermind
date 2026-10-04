# B1 / B2 正式提交与精确依赖验证

日期：2026-10-03。运行：`dependency-commit-20261003T133229Z-aed06791823e`。经执行和原始证据复核，**AA-B01、AA-B02 在本次声明的单进程、内存共享 Harness 依赖机制范围内均为 SUPPORTED**。B1 / B2 的规定状态转换已完成，不再仅记为 foundation 检查通过。该结论不涉及 A1/A2 的语义正确率、生产并发与性能或 Policy / Action 组合；AA-A02 保持 DENIED，Gate E/F 保持 OPEN。

## 补齐的证据缺口

旧 foundation 已验证 correction 后的传递失效和渐进恢复，但初始及替代派生记录都由 `seed_committed_fixture` 装入存储。它能说明 resolver 的局部行为，不能证明各 owner 经真实提交控制后仍保持同样结果。旧批次继续保留，没有被重新解释为完整通过。

本轮复用 BoundaryRuntime、SecurityRuntime 和 CurrentResolver。Observation 由 Interaction 凭据提交，Evidence / LearnerBelief 由 Evaluation 凭据提交；初始记录和所有替代版本都经过 Context、精确候选绑定、语义校验记录检查、权限检查及 commit-time dependency revalidation。读取不使用全局 ALLOW 的 EligibilityFixture。没有修改这些核心 runtime 的实现，也没有引入 reverse graph、push invalidation 或同步全量重算。

候选含义和 semantic PASS 明确标记为 SCRIPTED-DEPENDENCY-FIXTURE，用于隔离 B 维度的状态机制。受信预设提供事实、canonical、兼容性、grant 和 correction stimulus；correction 的授权生命周期不是本场景待测变量。此分工在调用前写入 `fixtures/dependency-commit-v1.json`，不因结果通过而声称测试过真实模型语义。每项确定性场景仅执行一次，不需要模型敏感场景的五次重复。

## B1：恢复必须逐级提交，旧依据不会自动更新

| 阶段 | 当前 Observation | 当前 Evidence | 当前 Belief |
| --- | --- | --- | --- |
| 初始链 | O:r1 | E-0:r1 | B-0:r1 |
| correction 后、无替代记录 | 不可用 | 不可用 | 不可用 |
| 仅提交 O:r2 | O:r2 | 不可用 | 不可用 |
| 再提交基于 O:r2 的 E-0:r2 | O:r2 | E-0:r2 | 不可用 |
| 再提交基于 E-0:r2 的 B-0:r2 | O:r2 | E-0:r2 | B-0:r2 |

15 次 resolution 的结果与表中预期一致。另在 correction 前分别准备 Evidence 和 Belief 候选，取得明确标记的 fixture PASS；在 O:r2 已提交之后尝试提交这两个旧候选，结果均为 CandidateStale，原因均为 Corrected。新 head 没有替换它们保存的旧依赖，也没有令旧 PASS 获得新依据。

B1 共 31 项检查通过，6 次正式提交成功、2 次旧候选提交被拒绝。旧 E-0:r1 继续精确依赖 O:r1，旧 B-0:r1 继续精确依赖 E-0:r1，历史内容未被 read path 或重新计算修改。没有观察到传递失效漏检、失效版本回退、静默重绑或对 authoritative push 的依赖，满足 §8.1 声明范围的支持条件。

## B2：立即拒绝旧状态，恢复可以逐步完成

初始通过正式提交建立一个 O 和 100 组 E / B，共 201 条派生记录。纠正 O:r1 后，没有先生成任何替代记录，全部 200 个下游读取立即拒绝旧依据。仅恢复 O:r2 后，这 200 个旧状态继续不可用；恢复 E-0:r2 后，B-0:r1 仍不可用；直到提交 B-0:r2，第 0 条完整分支才恢复，其余 99 条分支的 E 和 B 继续不可用。

B2 共 422 项检查通过，204 次正式提交成功；后续实际只追加了 O:r2、E-0:r2、B-0:r2 三条替代记录。五个阶段各读取 O 和全部 E / B，合计 1,005 次 resolution。读取没有修改派生存储，没有触发重算，也没有要求先恢复其余分支。旧的 201 条记录保持原样，满足 §8.2 的同步安全读取与渐进重算分离要求。这里的 100 分支用于验证机制，不是吞吐、延迟或生产容量指标。

## 复核、限制与设计后果

新增三项测试验证派生记录不能通过 seed 安装、错误 owner 和撤销后的 owner 不能提交，以及新上游 head 不能挽救绑定旧依据的在途候选。包含既有测试在内的 149 项本地测试通过。

运行后的证据复核重算了所有 snapshot 内容指纹，检查了各阶段历史记录在最终快照中保持原样，并核对全部 210 条派生记录都有对应成功 CommitOutcome、候选摘要、fixture review、正确 owner / principal 和精确依赖。所有失效 resolution 均沿精确引用报告被纠正的 O:r1，没有靠新 head 解释旧记录。运行时清单中的文档、代码和 fixture 哈希在复核时全部匹配。原始 runner summary 保持“待证据评审”，正式结论单独写入 [B 维度评估](assumption-b1-b2-20261003.json)，不回写原始结果。

支持结论保留当前设计选择：pull resolver 决定 current；重新计算由 owner 逐步产生并正式提交新版本；reverse index 如以后引入，只能辅助发现受影响对象和调度。追加的验证代码是测试场景装配，不是新的生产 owner、长期状态模型或调度框架。一致读取使用现有快照，正式提交仍依赖单进程内最后检查与 append 之间没有异步切换；多进程原子性和实际存储事务尚未验证。

本轮关闭 B1/B2 的限定机制验收，不关闭 X1 的 Policy 处理中 correction、X3 的帮助历史与 correction 组合，亦不扩展为 correction 授权、Evaluation 推断质量或真实 LLM 语义支持。这些限制在实验前已声明，后续组合场景若出现反证，必须记录新证据并重新审视受影响结论。

## 原始证据

批次目录：`src/spike/runs/dependency-commit-20261003T133229Z-aed06791823e`。模型调用为 0，不消耗 S1 / S2 的预算。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `979133618dc44533f1231fb126268c74ee31975146560aeb8040421aa0c50f55` |
| summary.json | `ac71af6caa62eb1bab615d321a5d393f77dbf3a283505012dd0b0f62aea5ef92` |
| B1.jsonl | `de9d3a9c25d65237a30e03227b1ebdcf2dfe3cd022fa7f6ff14212307df44f94` |
| B2.jsonl | `2e2fda409e7827219148e5e43fbc242b71c34b60e23ac94f39054ff2394ba0ca` |
