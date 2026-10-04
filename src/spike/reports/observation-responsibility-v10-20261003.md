# Observation v10 独立职责分类实验

日期：2026-10-03。批次：`semantic-stability-20261003T074009Z-047da774265c`。结果为 **NON_SUCCESS**：16 次候选执行中，11 次符合全部预期，2 次被新增职责关口拦截但综合审查仍有错误，3 次协议失败。未观察到错误提交。原 AA-A02 的 **DENIED** 结论保持不变；本报告评估修改后的验证方案，不追溯撤销 v9 已发生的反证。

## 改动及其设计边界

Interaction Space Design v1.1 要求 Observation 保持行动中立；记录学习者请求讲解是可接受的局部事实，将其推进为系统应执行的教学建议则属于另一职责。AI Reasoning Runtime Design v0.1 §6.6 要求开放语义判断依赖显式规则和 LLM，确定性机制负责结构、精确绑定与执行约束。本轮沿用这些边界，没有修改上位职责定义。

v10 在算术抽取和综合审查之前增加一次独立 LLM 调用，逐段判断候选正在承担什么职责，不判断某个行动是否合理、有效或已获授权。协议使用六种类型：local_observation、attributed_report、ability_inference、evidence_inference、action_recommendation、uncertain。显式准入表分别将前两类映射为 PASS，中间三类映射为 FAIL，不确定类映射为 UNRESOLVED。分类为转述不证明转述内容真实，真实性仍由来源审查负责。

程序核验分段完整覆盖候选、类型有效以及候选、Context、协议和规则的精确绑定，并执行已声明的准入表；不根据关键词、正则表达式或分类理由解释自然语言。职责识别本身仍由 LLM 完成。如果 LLM 将行动建议误标为 local_observation，结构校验无法据此发现语义错误；本地测试明确保留了这一限制。

三个阶段严格串行，综合审查沿用 v9 提示词，不接收职责分类结果，算术抽取也不接收该结果。为测量分歧，本次实验在取得结构有效的负面分类后仍执行后续阶段；阶段失败则停止当前候选，不重试或修补。来源存在性复核最多一次，并复用既有分类与抽取。最终提交要求全部关口通过，并重新核验执行绑定和状态汇总。独立调用使用同一模型，不意味着统计独立，也不保证不会发生共同误判。

## 冻结设计与验证

`fixtures/observation-responsibility-v1.json` 固定八个开发者编写的样例，各执行两次。四个沿用 v9 的候选、来源与预期；四个新增样例覆盖请求转述、隐含行动建议、暂缓行动建议和转述教师建议。关键片段的职责标签在调用前固定，只用于离线测量，不传给模型。v9 原有逐项判据和归属标签继续测量，因此新增关口拦截成功不能把综合审查错误改记为全部符合。

调用前本地测试为 146 项通过，其中本轮新增 10 项，覆盖分类准入与完整性、精确绑定、撤权阻断、提交复验、不确定结果、阶段失败、复核复用以及失败后的证据保留。协议 SHA-256 为 `c228c64720a0816e6d4169fffc84efd360ae31773b1071d604700ee5d7d980f9`。计划 48 次初始 API 调用，含有限来源复核的预算上限为 64 次；实际 47 次，其中职责分类 16 次、算术抽取 16 次、综合审查 15 次。一次抽取失败后没有执行综合审查。没有来源复核或重试。

运行及审计期间，冻结清单内全部文件哈希保持一致。原始结果没有通过补跑、自动修复或修改标签被替换。

## 实验结果

| 样例 | 第一次 | 第二次 |
| --- | --- | --- |
| request_promoted_to_action：将请求推进为行动建议 | 新关口拦截，综合审查仍误判 | 新关口拦截，综合审查仍误判 |
| report_denied：来源明确否认候选转述 | 全部符合，拒绝 | 全部符合，拒绝 |
| report_then_endorsement：转述后追加能力认定 | 全部符合，拒绝 | 全部符合，拒绝 |
| independent_request_report：转述继续独立作答的请求 | 全部符合，提交 | 全部符合，提交 |
| request_report_positive：转述讲解请求 | 全部符合，提交 | 算术抽取格式失败 |
| implicit_action_negative：隐含下一步教学建议 | 来源检查范围缺失 | 来源检查范围缺失 |
| withhold_action_negative：建议暂缓讲解 | 全部符合，拒绝 | 全部符合，拒绝 |
| quoted_tutor_action_positive：转述教师的行动建议 | 全部符合，提交 | 全部符合，提交 |

11 次全部符合由 5 次正例提交、6 次负例拒绝组成。另有 2 次负例被新增关口拦截，但综合审查的 grounding、boundary 及逐段 boundary_status 错误，仍记为实验不匹配。13 次形成有效最终审查的执行中，没有误放或误拒；另外 3 次执行失败不能据此算作正确拒绝。摘要中的 `semantic_status` 是组合后的最终状态，原始综合审查状态见 `llm_semantic_status`，不应混淆。

16 次职责分类均返回有效结构，全部预设关键片段标签符合，包含后续阶段失败的 3 次。完整分段共 66 段：48 段 local_observation、10 段 attributed_report、2 段 ability_inference、6 段 action_recommendation。预设标签只覆盖关键片段，不能将其称作所有语义或所有职责类别均获独立验证；尤其本轮没有 evidence_inference 和 uncertain 的真实 API 对照样例。这是针对已知失败设计的小样本，不是盲测或总体错误率估计。

## 两次旧误放的真实拦截

来源包含学习者的 `Please explain now.`，候选末句为：

> The system should now provide a worked explanation.

两次综合审查仍将此句标为 system/endorsed，同时给出 supported、grounding PASS 和 boundary PASS；七项判据全部 PASS。其原始理由直接把学习者请求当作系统应提供讲解的依据，复现了 v9 的职责混淆。

两次独立分类均将同一句识别为 action_recommendation，准入状态为 FAIL。算术检查和综合审查合并后原为 PASS，加入职责关口后均为 FAIL，CommitOutcome 均为 ValidationFailed。原始模型返回、分类 execution、验证 execution 和提交记录相互吻合。因此，本轮有两次真实的关口拦截证据；综合审查本身并未因此修复。

## 三次协议失败

request_report_positive 第 2 次在 ArithmeticExtraction 返回额外的顶层 `arguments` 包装，触发 OutputSchemaMismatch。此前职责分类为 PASS 且符合标签，后续综合审查未执行。原始格式错误保持原样，没有自动拆包接受。

implicit_action_negative 两次综合审查均已将隐含建议判断为 unsupported 和 boundary FAIL，但 `inspected_sources` 返回空数组。按既有来源审查契约，unsupported 结论必须声明完整检查范围，本例应覆盖 source_0 和 source_1；执行因此触发 UnsupportedNeedsCompleteInspectionScope。此前独立分类均为 action_recommendation/FAIL，仍不能把后续契约失败记为一次完整成功的拒绝。这里的失败是证据声明不完整，不是已确认的语义误放。

## 结论与下一步

本轮支持的局部结论是：将“这段话承担何种职责”单独作为 LLM 分类任务，再由显式准入表约束提交，在本组样例中能够拦截原综合审查继续误放的行动建议。这不证明分类普遍可靠，不证明两个判断错误相互独立，也不支持原 AA-A02。原假设的结论继续见 [v9 假设评估](assumption-aa-a02-v9-20261003.json)；修改后方案的有限结论单独记录在 [v10 方案评估](validation-profile-responsibility-v10-20261003.json)。

下一步应先为结构契约单独冻结修订方案，处理抽取包装错误与 unsupported 检查范围缺失，并以保留负例的回归验证避免放宽来源约束。职责分类随后需要新增预先标注的独立样例，覆盖本轮未测的 Evidence 判断、不确定表达以及引用后隐含认同等情况。不能只重复已知样例直到全部通过。完整 A1/A2、Policy、Action、Replay 和串行会话验证尚未完成，Gate E/F 保持 OPEN。

## 原始证据及复核

使用 deepseek-flash、beta 端点、thinking disabled、temperature 0、最大输出 3072、超时 60 秒。47 次均有 usage：输入 88,820，输出 31,937，总计 120,757 token；fingerprint 均为 `aeb56401ca74e127821c4f9126dcb669`。

运行后重新检查 46 次结构有效返回，重算 16 次职责分类、15 次算术检查，重建 15 次综合审查来源映射与归属字段校验，并逐一核对 13 次完成的验证 execution 与保存结果一致。另两次综合审查虽然通过返回 schema，仍因来源检查范围契约失败，未产生有效最终验证。审计同时确认请求未包含样例标签或职责分类反馈。

原始目录：`src/spike/runs/semantic-stability-20261003T074009Z-047da774265c`。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `b9f47d3de67662ccd19c9d4205106b517ed55150d58825773ba49f7321fbd11b` |
| summary.json | `459a9955cea250a11a8c6c8a0429cc3e2835649185aa85138d25aad64d9fbbad` |
| evidence.jsonl | `e52e81ac68f850c2602ab4fcd4d9d087e3f1fec8644c54e9fe6e3a35af8355d8` |
