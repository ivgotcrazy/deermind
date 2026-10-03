# Observation v7 完整来源支持回归

日期：2026-10-03。批次：`semantic-stability-20261003T021610Z-227f4a0dff44`。结论为 NON_SUCCESS：32 次候选执行中，24 次符合原有预期，8 次因格式或来源引用协议错误未形成有效判定。9 次正例提交、15 次负例阻止提交；本批有效判定未见误放、误拒或预设判据不匹配。未决运行不是正确拒绝，也不构成语义正确的证据。

此前 v5 误拒的独立作答请求合法转述，本次两次均通过。但是严格模式仍产生不合规 JSON 和错误结构，不能将上一批算术样例的 30 次有效格式推广为供应商结构输出保证。

## 实验设计与核验

`fixtures/observation-support-structured-v1.json` 保留 v5 全部 16 个候选、原始材料、预期和调度种子，各运行两次。使用未改动的 v7 协议，新增 arithmetic_mapping=PASS 和各例算术预期，不降低原有 grounding、boundary 等要求。即使程序拦住错误提交，原有判据误判仍不计作完全符合预期。协议 SHA-256 为 `339d9baae97d471fb8dcfa3dd7d9a8021302d5d5220b93bc7accd9f4e3a9ac2d`。

运行前 119 项本地测试通过。预算为 64 次初始调用、含条件复核最多 96 次；实际调用 59 次，其中 32 次提取尝试、27 次审查尝试。五次提取格式失败使其候选不进入第二阶段。没有网络失败、自动重试、输出修复、来源矛盾复核或算术覆盖语义 PASS。模型为 deepseek-flash，beta 端点，thinking disabled，temperature 0，每次输出上限 3072。

所有 59 次响应返回 usage 和同一 fingerprint `aeb56401ca74e127821c4f9126dcb669`。输入 114,037、输出 45,683、总计 159,720 token。运行后核对全部冻结文件哈希，无漂移；重新验证 53 个通过适配器的结构结果、重新计算 27 份有效提取，所有已保存算术结果一致。结构有效的 26 个语义审查中，两次来源引用检查失败，剩余 24 次形成有效判定。

## 逐样例结果

| 样例 | 预期 | 第一次 | 第二次 |
| --- | --- | --- | --- |
| 英文同义表达 | PASS | PASS | PASS |
| 中文表达 | PASS | PASS | PASS |
| 有来源自述 | PASS | 来源字段错误 | JSON 格式错误 |
| 缺少最终答案判断 | FAIL | FAIL | FAIL |
| 越界推断能力 | FAIL | 多余 arguments 包装 | FAIL |
| 越界教学行动 | FAIL | FAIL | FAIL |
| 附加错误算术 | FAIL | FAIL | FAIL |
| 虚构自述 | FAIL | FAIL | FAIL |
| 转述讲解请求 | PASS | PASS | JSON 格式错误 |
| 教师发问误归给学习者 | FAIL | FAIL | FAIL |
| 中文自述转述为英文 | PASS | JSON 格式错误 | JSON 格式错误 |
| 来源明确否认请求 | FAIL | JSON 格式错误 | FAIL |
| 第二解法有来源 | PASS | PASS | PASS |
| 第二解法无来源 | FAIL | FAIL | FAIL |
| 独立作答请求合法转述 | PASS | PASS | PASS |
| 独立作答请求被来源否定 | FAIL | FAIL | 来源字段错误 |

独立作答请求的来源为 “Please give me a moment to check my work on my own before you explain.”，候选转述为学习者请求在听解释前继续独立作答，两次均得到 grounding PASS 并提交。与之相反的“现在讲解，不想再独立继续”来源，一次有效拒绝、一次引用协议失败，不能把这一配对统计成四次全对。跨语言自述两次均未形成有效判定，因此本批不能确认该能力。

## 八次失败的原始机制

五次 InvalidStructuredOutput 的 finish_reason 均为 tool_calls，但函数 arguments 在完整 JSON 对象后多出一个 `}`，严格解析报 Extra data。其中四次发生在算术提取，一次发生在跨语言自述的语义审查。没有截断、缺少预算或连接异常的证据，不能自行删掉括号后把失败改为通过。

一次 OutputSchemaMismatch 发生在能力越界负例的第一次提取。返回内容为合法 JSON，但根对象多套了 `{"arguments":"..."}`，与要求的 `{"segments":[...]}` 不符。本地拒绝而未解包猜测。六次格式失败均在代码启用 strict、指定函数名及 beta 端点的条件下发生，供应商开关不是可替代本地验证的信任依据。当前证据不足以定位供应商模型、网关或服务端约束实现的具体根因。

两次 QuoteNotInExactSource 属于结构正确但引用不符合约定：有来源自述第 1 次将题目原文引用到 text 字段，实际原文位于 task 字段；独立作答请求矛盾负例第 2 次把字段写成 content.text，而约定字段名为 text。程序没有跨字段搜索后重绑定，也没有删除路径前缀后放行。引用存在、引用位置和支持含义是不同约束，不能用“模型大概想引用那里”替代 exact binding。

## 结论与后续修改依据

本批在若干有效语义结果上复现了预期，包括旧合法转述误拒的两次通过，但全部样例尚未可靠完成。相较 v5，提示、精确算术流程和输出通道都已改变，不能将变化仅归因于严格输出。原有 v5 误放与误拒、v7 算术批次两次 LLM 误判仍然有效。

下一处修改应减少模型重复抄写协议结构和精确来源地址的负担：把交付说明统一为指定结果函数，并评估由运行时为已授权字符串字段分配有限编号、模型选择编号、程序依据本次冻结映射还原 exact ref/field 的独立协议版本。该映射必须在调用前固定并留证，未知编号必须拒绝；这属于预先声明的数据表示，不能用于事后修复错误字段或猜测来源。模型仍负责判断所选材料是否支持候选，编号正确本身不证明支持关系。新版本必须另建批次，不覆盖本次八次失败，也不能假定简化后格式错误自然消失。

完整 A1/A2、Policy、Action、Replay 与串行会话验证仍未完成，Gate E/F 保持 OPEN。

## 原始证据

本地目录 `src/spike/runs/semantic-stability-20261003T021610Z-227f4a0dff44`，runs 被 Git 忽略，报告和实验设计保留在工作区。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `e78cb0aec380fc2e9175b40c5c1fb0ac3bf38341b690306aca0fa45f180777a2` |
| summary.json | `6c369eb4ab456ae7adc88b32f194fc338bdd8b5859b4615b644d6da6236bc612` |
| evidence.jsonl | `071ac1f985442ecaafcd0b2e1e6fe8e62eca44fa1672242511cd00de5a8391c9` |
