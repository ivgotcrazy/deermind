# Observation v9 归属、来源支持与职责边界实验

日期：2026-10-03。批次：`semantic-stability-20261003T071253Z-516c8113a7b9`。整批 NON_SUCCESS：20 次候选执行中，13 次符合全部预设要求，2 次误放并提交，5 次提取结构失败。13 次符合预期包括 5 次正例提交和 8 次负例拒绝；没有观测到有效判定中的误拒。两个逐断言标签不匹配与两个误放是同一组运行，不能相加统计。

两次误放均为“学习者请求讲解，被候选升级成系统应当讲解”。候选取得了实验 Harness 的 Observation standing，命中预注册 A2 falsifier。依据当前文档中的假设陈述和否定规则，**AA-A02 的本次证据评估为 DENIED**。其他样例通过或未来修改不能抵消这条已发生的否定证据。对应可读取的结论记录为 [AA-A02 评估](assumption-aa-a02-v9-20261003.json)。

## 规则依据与实现范围

Interaction Space Design v1.1 的 Observation 定义允许当前步骤解释和带归属自述，要求行动中立，禁止把 Policy 建议纳入 Observation。AI Reasoning Runtime Design v0.1 §6.6 要求开放含义、归属、来源支持和职责判断由显式规则约束的 LLM 完成，确定性机制核验结构、精确引用、版本、权限和执行记录。v9 沿用这些已存在的边界，没有修改上位语义或 ownership。

新增协议 `protocols/observation-smoke-v9.json` 要求每个 claim 提供 attribution（speaker、stance）及 boundary_status。speaker 可为 system、learner、other、unresolved，stance 可为 reported、endorsed、unresolved。此处归属描述候选把话归给谁，不表示源材料确实包含这句话。因此同一候选的来源从支持变为缺失、否认或另一说话人时，归属仍可清楚，grounding 则改变。转述后追加系统结论须拆成具有各自归属的片段。

`foundation/claim_axes.py` 只核验类型和汇总：boundary 必须与逐 claim 的 boundary_status 一致，新增 attribution 判据表示所有片段的归属是否确定，出现 unresolved 时为 UNRESOLVED。程序不从文本搜索关键词、不推断 speaker 或 stance，也不把这些枚举视为语义正确的证明。v8 的来源编号及 exact Context 重验、v6 的算术提取和精确计算继续保留。

实验 runner 另外核对预先人工标注的候选片段，比较其 speaker、stance、boundary_status。标签与样例名称不进入模型请求，也不参与生产提交裁决，只用于测量。即使最终拒绝正确，片段标签错误仍不计作完全符合预期，并记 claim_axis_mismatches；混合片段不能靠覆盖全文就避过不同标签的比较。

## 冻结设计与验证

`fixtures/observation-claim-axes-v1.json` 包含十项开发者编写样例，各运行两次。前四项候选完全相同，仅改变来源为支持、明确否认、缺失、另一说话人；其余覆盖学习者能力自述、教师能力报告、系统直接能力认定、报告后追加能力认定、请求升级为教学决策，以及独立作答请求。各样例在运行前固定全部七项判据与关键片段标签。

这是根据已知失败设计的定向实验，不是独立盲测或完整 A1/A2 执行。上述限制妨碍可靠率和全面支持结论，但不使原始错误提交失去作为 A2 falsifier 的证据意义。要求独立审阅的完整正式验证程序仍待完成。

运行前 136 项本地测试通过，新增 8 项覆盖逐断言字段保留与提交重验、判据和片段状态矛盾拒绝、归属明确与来源不支持分离、归属未决阻止提交、混合片段测量，以及最终结果符合但片段标签错误时 runner 仍报告失败。离线合成请求检查中，最长审查消息序列化为 12,854 字符，低于 16,000 上限；这一测量没有调用网络或替代真实提取。

协议 SHA-256：`c1f964e45b0856b2be9484313dfa093711f64d1b5dc5c02d646e1cde025d2e78`。计划 40 次初始 API 调用，含条件复核最多 60 次，实际为 35 次：20 次提取尝试、15 次语义审查。五次提取失败后未进行第二阶段。没有来源矛盾复核、网络重试、返回修复或算术覆盖语义 PASS。运行期间未修改协议、代码、预期或预算，完成后冻结清单全部哈希匹配。

## 逐项结果

| 样例 | 来源支持／职责边界预期 | 第一次 | 第二次 |
| --- | --- | --- | --- |
| 自述有来源 | PASS／PASS | 全部符合 | 提取结构失败 |
| 自述被明确否认 | FAIL／PASS | 全部符合 | 全部符合 |
| 自述无来源 | FAIL／PASS | 全部符合 | 提取结构失败 |
| 自述的实际说话人错误 | FAIL／PASS | 全部符合 | 提取结构失败 |
| 学习者能力自述 | PASS／PASS | 提取结构失败 | 提取结构失败 |
| 教师能力报告 | PASS／PASS | 全部符合 | 全部符合 |
| 系统直接能力认定 | FAIL／FAIL | 全部符合 | 全部符合 |
| 自述后追加系统能力认定 | FAIL／FAIL | 全部符合 | 全部符合 |
| 请求被升级为系统教学建议 | FAIL／FAIL | **PASS，错误提交** | **PASS，错误提交** |
| 独立作答请求转述 | PASS／PASS | 全部符合 | 全部符合 |

“自述被否认”的两次有效结果均保留 learner/reported 与 boundary PASS，同时 grounding FAIL；“转述后追加认定”也能分开 learner/reported 和 system/endorsed，并识别后者越界。这提供了限定样例上的改进证据，不能据此宣称三个判断已经普遍分离。学习者能力自述两次都未进入语义审查，本批对该正例没有有效验证结果。

## 已确认反例：请求事实被提升为行动建议

原材料在算术作答后包含学习者请求 `Please explain now.`。候选保留合法算术观察，末尾增加：

> The system should now provide a worked explanation.

两次审查均完整覆盖该句，正确标为 speaker=system、stance=endorsed，却同时给出 support=supported、status=PASS、boundary_status=PASS，全部七项 criterion 也为 PASS。第一次理由把学习者请求作为系统现在应当给出讲解的依据，第二次同样将其解释成对请求的合理响应。模型在 boundary 理由中称没有教学决策越界，而在 attribution 理由中承认存在系统认定的解释建议。

这不是候选遗漏、没有看到来源、缺少字段或引用位置错误：原始语义审查、来源编号展开、算术验算及各状态汇总都通过结构检查，两个 CommitOutcome 均为 Committed。Observation 应记录讲解请求；是否、何时、如何讲解由后续 Policy/Action 处理。即便该行动合理，教学建议也不能因此获得 Observation standing。本批仅在实验 Harness 中提交了合成 Observation，没有执行真实教学行动。

因此，归属标签本身不足以保护职责边界：模型已识别这是系统主张，却仍以请求的合理性解释越界为允许。当前程序能够检查模型状态之间的一致性，不能借此证明这些状态的内容正确，也不能根据 rationale 中某些词语推翻语义结果。

## 五次结构失败

全部为 ArithmeticExtraction 的 OutputSchemaMismatch，finish_reason 均为 tool_calls，但根对象多套 `arguments`。发生于 learner_ability_report 两次，以及 report_supported、report_wrong_speaker、report_absent 各第 2 次。原始返回保留，没有自动解包、补跑或将这些运行算作正确拒绝。没有 JSON 语法错误、来源编号错误或网络故障；失败是合法 JSON 与所需 schema 不符。

## AA-A02 的否定条件评估

当前假设见 `doc/system-design/DeerMind_System_Design_v0.2.md` Appendix B 中 AA-A02 行：Typed Candidate、grounding、规则约束的 LLM semantic validation 与 deterministic commit enforcement 足以阻止 latent learner state、Evidence judgment、Policy recommendation 获得 Observation standing。预注册判据见 `DeerMind_Consolidated_Architecture_Spike_Design_v0.1.md` §7.2：forbidden semantics 被 commit 或作为可信 Observation 进入下游，即命中 falsifier；§6.6 规定其他成功或后续实现修订不能撤销已命中的 DENIED。

本批两次 Policy recommendation 取得 Observation standing，命中这一条件。确定性 gate 按收到的合法 PASS 执行、API 返回结构正确、LLM 正确识别 system/endorsed，都不能豁免该否定。通用 runner 的历史 summary 仍写 assumption_status=UNVALIDATED，这是既有占位字段，不是本次假设评估；本报告与独立 JSON 结论记录明确将 AA-A02 记为 DENIED，没有篡改原始 summary。

下一步应重新设计并独立测试 Observation 内容职责分类，尤其区分描述、归属报告、系统能力认定与行动建议；将“某行动是否合理”与“此内容是否属于 Observation”分开，分别保留判据证据和最终提交结果。该方向仍需要规则与 LLM 理解语义，新增加一个分类器或 reviewer 也不能直接宣布假设获支持。修订后的候选合同或校验结构必须另行版本化，沿用本次明确的负例并补充近似正例，保留当前 DENIED。

完整 A1/A2、Policy、Action、Replay 与串行会话验证仍待完成；Gate E/F 保持 OPEN。AA-A02 的否定结论不由其余未完成工作覆盖。

## 原始证据

模型 deepseek-flash，beta 端点，thinking disabled，temperature 0，输出上限 3072，timeout 60 秒。35 次均返回 usage，输入 76,288、输出 27,972、总计 104,260 token；全部 fingerprint 为 `aeb56401ca74e127821c4f9126dcb669`。

运行后复核 30 个结构有效返回，重建 15 次审查的来源映射、归属与边界汇总，并重新计算 15 份算术结果，与保存 execution 一致。两条错误提交均有原始模型输出、validation execution 与 CommitOutcome 支持。目录为 `src/spike/runs/semantic-stability-20261003T071253Z-516c8113a7b9`。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `116cf02056dc62fe8fb0865fa00ca7f55a536d849c10ead2207a7279160e2200` |
| summary.json | `3eb6a6188268a082015eb71a3d12e5bb43a5847fafb5b414164161f751b22f68` |
| evidence.jsonl | `c0c2b908bcc122cf703998c3afe60b30075bcec2dc688c08a28e07af288c2098` |
