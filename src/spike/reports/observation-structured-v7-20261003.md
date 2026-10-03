# Observation 严格结构输出 v7：实现与真实实验结果

日期：2026-10-03。当前状态：实现完成，运行前本地 119 项测试通过；用户明确同意继续后，真实批次已完成全部 16 次候选执行，15 次符合预期，1 次因远端断开未完成判定。实际发起 31 次 API 调用，30 次返回的结果均通过严格结构检查，未见 JSON 格式错误。整批为 NON_SUCCESS，不能将连接失败算作正确处理。

本批同时发现两次 LLM 语义误判，均在同一“错误否定”负例的两次重复中发生；程序精确算术将其拦截，未提交。最终无误放不代表 LLM 本身没有误判。

## 问题与变更范围

v6 的冻结批次在 16 次候选执行中有 13 次符合预期、两次无效 JSON 和一次远端断开。两次格式错误均出现在语义审查返回的来源字段，出现 `"field": "text": "..."` 这种不合法结构，且 finish_reason 为 stop。原始证据和限制见 [v6 报告](observation-arithmetic-v6-20261003.md)。这些失败继续保留，不以本轮实现或模拟测试替换。

v7 新增独立协议 `protocols/observation-smoke-v7.json` 与实验设计 `fixtures/observation-structured-v1.json`。沿用 v6 的八项样例、两次重复、调度顺序、预期、全部语义要求，以及提取、映射审查和精确算术流程；保留 validation_format 为 arithmetic-linked-v6，避免把传输变化误写为语义规则升级。提示仅追加固定结果包交付说明。

依据本日查阅的 DeepSeek 官方 [Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/) 与 [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)，本实验显式使用 `https://api.deepseek.com/beta`、关闭 thinking、strict 函数参数约束及指定函数名。函数只用作传回结构化数据的结果包，不执行任何模型提出的外部操作。结构定义完整存入版本化协议，全部对象字段必需且禁止额外字段。供应商在本批实际接受了提取与校验的完整 schema，包括引语的字符串／null 表示。生成阶段的 schema 只有本地测试，本批使用固定候选，没有调用生成阶段。

适配器要求唯一且名称正确的函数结果以及 tool_calls 完成标志，严格解析原始 arguments 后再进行本地结构验证。原始内容、函数结果、结构定义、调用状态均进入证据记录，不保存密钥、HTTP 请求头或 reasoning_content。结构有效之后，原有精确来源检查、全文覆盖、语义映射、算术和提交权限检查继续执行。没有普通文本回退、输出修复或网络重试。

## 本地验证与已知限制

运行前执行 `python -m unittest discover -s tests -q`，119 项全部通过，其中新增 8 项测试覆盖完整 schema、可空引语、错误状态枚举、缺失和额外字段、错误函数及多函数结果、JSON 解析失败、目标端点不匹配、供应商拒绝后的整批停止，以及结构正确但语义误判的算术拦截。测试还确认 v7 与 v6 的样例、预期、顺序和语义规则一致。测试中曾发现记录序列化会改变 properties 顺序，已修正本地 schema 定义检查：required 按完整集合和无重复约束核对，不依赖字段顺序。完整测试通过后冻结批次，运行期间未修改实现或实验设计。

离线预检结果为 ready=true，模型为 deepseek-flash，端点明确为 beta，单次输出上限 3072，计划初始调用 32 次，含条件复核最多 48 次。预检只确认本地配置和预算，不代表供应商可用或接受请求。`.env` 未修改。

供应商结构约束不能证明来源支持关系、说话人归属、否定理解或算术映射正确。当前本地结构校验器只实现本协议所需的有限 JSON Schema 子集，不声称支持通用 JSON Schema。字面覆盖仍不证明语义完整。v6 与 v7 同时存在端点、结果包及交付说明差异，不能从单批对比中分离每个因素的因果效果。本批是同一组开发者编写样例的重复，结果不构成独立总体错误率估计。

## 授权与执行记录

首次真实运行命令曾在进程启动前被自动审批拒绝，原因是此前授权未明确涵盖具体 beta 目的地及本批内部载荷；该次尝试没有产生 API 调用。随后向用户说明数据范围和目的地，用户回复“我已经放开审批，继续”，本批在该明确授权后启动。审批变更不改变实验设计和预算。

实际发送的数据包括本批合成的题目与作答、候选 Observation、来源标识，以及为提取和审查所需的协议提示、结构定义；第二阶段还包含第一阶段的结构化提取与程序验算结果。这些项目设计内容由 DeepSeek 处理。API key 仅用于认证，不写入实验结果；没有上传整个代码仓库。

冻结协议 SHA-256：`339d9baae97d471fb8dcfa3dd7d9a8021302d5d5220b93bc7accd9f4e3a9ac2d`。

在仓库根目录执行：

```powershell
python src/spike/run_semantic_stability.py --fixture observation-structured-v1.json --base-url https://api.deepseek.com/beta --max-calls 48 --max-output-tokens 3072 --run
```

停止规则是遇到声明的 HTTP 400、401、403、404、422 时停止整批，其他候选失败按固定顺序继续，不修改样例或补跑。本批没有命中整批停止条件。每个候选完成或失败后保存其全部 API 证据，尚不保证进程在候选两阶段之间被强制终止时已完成阶段立即落盘。

## 真实结果与证据核对

批次目录：`src/spike/runs/semantic-stability-20261003T020600Z-86be810a0da9`。

| 指标 | v6 | v7 |
| --- | ---: | ---: |
| 候选执行数 | 16 | 16 |
| 符合预期 | 13 | 15 |
| 正例通过并提交 | 8 | 9 |
| 负例正确阻止提交 | 5 | 6 |
| JSON／结构协议失败 | 2 | 0 |
| 远端断开 | 1 | 1 |
| 最终误放／误拒 | 0／0 | 0／0 |
| LLM 语义 PASS 被精确算术拦截 | 0 | 2 |
| 实际 API 调用 | 32 | 31 |

v7 的唯一未完成样例为 `reported_wrong_equality_positive` 第 2 次重复：ArithmeticExtraction 阶段出现 ProviderRemoteDisconnected，因此该候选没有第二次语义审查调用，没有判定或提交，没有自动重试。总调用数为 16 次提取尝试加 15 次审查；30 次成功返回均为指定函数的 tool_calls 结果，全部通过 JSON 解析和本地 schema 检查。未触发来源存在性矛盾或额外复核。

两次实际算术拦截均发生在 `wrong_negation_negative`。候选说“声称八乘十五等于 120 是不正确的”，即否定真实等式。LLM 提取正确保留了 multiply、8、15、120 与 asserted_false，语义审查的 arithmetic_mapping=PASS 是正确的；但审查同时把 grounding 判为 PASS，将忠实记录候选立场误当作支持该立场。第一轮理由明确把该句解释为对作答路线的立场判断。程序计算 8×15＝120 为真，因此对该等式的否定为假，最终 effective_status=FAIL、commit_status=ValidationFailed。原始 LLM PASS 和程序拦截结果分别保留，不能称为 LLM 正确识别了负例。

对全部 15 个成功提取的断言进行了原始输出检查：本组出现的数字、运算、正确／错误否定与 reported_only 归属均与预期相符。该人工检查由当前开发会话完成，不是独立盲审。运行后重新验证了 30 个返回结果的结构，并重新计算全部 15 份算术结果，与保存的 execution 一致。冻结清单中所有文件 SHA-256 均与运行时一致，没有中途调参或修改代码。

返回的用量合计为输入 61,141、输出 25,612、总计 86,753 token；断开的一次请求没有返回 usage，其实际计费未知。30 次成功响应均报告模型 deepseek-flash，fingerprint 为 `aeb56401ca74e127821c4f9126dcb669`。

| 证据文件 | SHA-256 |
| --- | --- |
| manifest.json | `3f542f965e936ca5cee54aaf482dbde3d463eeb29007a3d823c4c61f8e11f3b9` |
| summary.json | `73309a30279f0d91933b0ccd287731caa7bcf106002660234e480b36f43c7e65` |
| evidence.jsonl | `f9a26396fdee826fe4901fa7070d77c1a2f6fc93890b3ad16d95fd255bbd6b67` |

本批支持继续采用严格结构结果包开展后续实验，并提供了精确算术拦截真实 LLM 误判的证据；它没有证明模型语义校验可靠，也没有消除连接失败。下一步应使用新的冻结批次返回一般转述、否定和来源支持关系，覆盖此前 v5 的合法转述误拒；这些问题不能依赖算术计算解决。连接故障继续独立记录，不补跑覆盖本批失败。

完整 A1/A2、Policy、Action、Replay 与会话串行链仍待执行；Gate E/F 保持 OPEN。过去已经出现的具体误放与误拒证据继续有效。
