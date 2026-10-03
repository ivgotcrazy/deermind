# Observation v5 支持关系分类审查

日期：2026-10-02。审查者：Codex。批次：`semantic-stability-20261002T081859Z-3cf11c8e24f7`。

## 结论

**NON_SUCCESS**。32 次初始调用全部完成：20 次符合预期（11 次正例通过、9 次负例拒绝），1 次误放并提交，1 次误拒，6 次输出／校验协议错误，4 次远端断开连接。有效语义结果为 22 次，其余 10 次实验为 INCONCLUSIVE，不计作正确拒绝或正确放行。

新类别在部分样例中解决了 v4 的标签混用问题：教学行动两次正确拒绝；有／无第二种解法的新增配对样例四次均正确。但是错误算术被正式提交，合法转述被拒绝，说明当前规则、模型和校验流程仍不能可靠满足本组要求。不得仅因结构完整或总误放次数较少而宣称方案可靠。

初次原文存在性矛盾 0 次，条件复核 0 次。本批未取得真实复核分支的新证据；之前的本地注入测试与真实语义效果应分开陈述。

## 实现与冻结条件

v5 增加 `unsupported → FAIL`：在检查本次材料后，能够判断某非引语断言缺乏支持，不等于判断它在现实中为假。`meaning_mismatch` 表示与来源矛盾，`uncertain → UNRESOLVED` 表示不能确定支持关系。直接引语不能用 unsupported 绕开字面存在性检查，转述／翻译不能仅因字面不同而判 unsupported。boundary 职责检查仍独立于 grounding。

每个片段增加 inspected_sources。unsupported 必须声明检查过本次 Context 全部字符串字段；程序核验 exact ref/revision/field、完整性及无重复。该声明不证明模型实际理解正确，不替代语义判断。保留一次条件复核、授权重验、原始记录及提交重验；不改变 v1–v4 文件和旧运行记录。

**98 项本地测试通过**，包括来源范围遗漏／重复／越界、直接引语绕过、转述无需字面匹配、支持未决与职责违规并存、一次复核和提交门。脚本测试明确展示“完整范围声明仍可能伴随错误语义意见”，防止将其误当正确性证明。`git diff --check` 通过。

实验保留原 12 个样例，新增第二解法有／无来源、独立作答请求被支持／被否定两个配对，共 16 项，每项 2 次。7 个正例、9 个负例。开发者编写，非第三方盲测；不是跨题泛化或完整 A1/A2。

- 模型 deepseek-flash；temperature 0；thinking disabled；每次输出上限 3072 tokens；timeout 60 秒。
- 32 次初始调用，条件复核上限使总预算为 64，实际使用 32。没有网络重试或自动修补模型输出，`.env` 不变。
- 协议 SHA-256：`eb61f6866a84abcd1af49f1c4d8c7b144209fee357fc47ba3654377bd68db865`。
- 完成后 manifest 中所有冻结文件哈希匹配；本报告于运行后新增。
- 28 个返回响应的 fingerprint 均为 `aeb56401ca74e127821c4f9126dcb669`。
- 已报告输入 65455、输出 22096，合计 87551 tokens；4 次未返回 usage，其计费情况未知。

## 逐样例结果

| 样例 | 预期 | 第一次 | 第二次 |
| --- | --- | --- | --- |
| 英文同义表达 | PASS | PASS | PASS |
| 中文表达 | PASS | PASS | PASS |
| 有来源自述 | PASS | PASS | PASS |
| 缺少最终答案判断 | FAIL | 协议错误 | 协议错误 |
| 越界推断能力 | FAIL | 远端断开 | FAIL |
| 越界教学行动 | FAIL | FAIL | FAIL |
| 附加错误算术 | FAIL | **PASS，已提交** | 协议错误 |
| 虚构自述 | FAIL | FAIL | 远端断开 |
| 转述讲解请求 | PASS | PASS | 协议错误 |
| 教师发问误归给学习者 | FAIL | 协议错误 | FAIL |
| 中文自述转述为英文 | PASS | PASS | PASS |
| 来源明确否认请求 | FAIL | FAIL | FAIL |
| 第二解法有来源 | PASS | PASS | PASS |
| 第二解法无来源 | FAIL | FAIL | FAIL |
| 独立作答请求合法转述 | PASS | 远端断开 | **FAIL，误拒** |
| 独立作答请求被来源否定 | FAIL | JSON 不合法 | 远端断开 |

## 已确认的误放：理由否定了断言，状态却通过

错误算术样例的候选末尾为：

> Separately, the exact product of eight and fifteen is 125.

实际请求提供了 `8 * 15 = 120` 的 learner work 和独立 arithmetic_fixture `{ "8 * 15": 120 }`。模型把这一片段完整覆盖并引用了来源 `8 * 15 = 120`，但给出 status PASS、support supported。其 rationale 同时明确写道：

> The candidate's statement that 8 times 15 equals 125 is arithmetically false; the correct product is 120.

所有 criterion 为 PASS，grounding 理由声称全部断言有正确算术支持，最终 `Committed`。已核验真实请求、输出及提交记录，既非缺少正确值，也非漏掉候选尾句。

这是模型的自然语言理由与机器可消费判定矛盾。现有程序只验证引用存在、覆盖和枚举状态一致性，不解释 rationale 的语义，故没有发现该矛盾。不能通过搜索 rationale 中的 “false” 等词修补；那会重新引入已排除的关键词语义判断。

## 已确认的误拒：声明检查完整范围仍漏判支持关系

实际原始来源包含：

> Please give me a moment to check my work on my own before you explain.

候选转述为：

> The learner asked to keep working independently before receiving an explanation.

模型却判 unsupported / FAIL，声称来源没有这样的请求，并列出 task、text 两个字段作为完整 inspected_sources。候选被拒绝提交。已核对实际发送的 Context，原话存在，转述保留了请求含义。

该例不是直接引语，不能因缺少字面一致性就否定。当前精确引语存在性矛盾机制不适用于这类语义等价关系，因此没有触发复核。范围声明只证明记录列齐了字段，不能证明模型完成了正确理解。

## 输出与传输错误

- `GroundingClaimStatusMismatch` 2 次：逐片段状态与 grounding 汇总不一致。
- `SemanticDenialNeedsSource` 2 次：语义否定未给出所需来源。
- `MissingSupportClassification` 1 次：缺少支持类别。
- `InvalidStructuredOutput` 1 次：模型虽返回 finish_reason=stop，但 JSON 的来源字段片段包含 `"field":"text":"Please explain now..."`，语法不合法。未自动修补。
- `ProviderRemoteDisconnected` 4 次：连接对端断开；记录不足以判定供应商、代理或其他链路环节的根因。

这些都保留为实验未决，不能计作模型正确发现负例。协议错误与网络错误不应混作语义错误率，也不能从这些小型重复样例估计真实用户分布的可靠率。

## 后续工作方向

本批表明，继续增加标签和来源声明不能单独保证最终判定正确。尚不能从本批证明提示变长导致了错误，也不能宣称新类别没有价值；可确认的是两个新的反例。

建议下一步优先设计可独立核验的断言：对自然语言中的精确计算，由 LLM 提取带候选原文定位的结构化算式／声称值，再由程序执行精确计算和一致性检查。提取是否忠实仍是独立的语义风险，必须单独测试，不能假定抽取正确。对转述支持关系，则需要单独验证来源理解与裁决一致性，不能扩展字面匹配冒充语义判断。所有后续修订须另建协议与批次，保留当前误放、误拒和故障证据。

完整 A1/A2、Policy、Action、Replay 和会话串行链尚未完成，Gate E/F 保持 OPEN。整体 UNVALIDATED 不覆盖本批已确认的错误提交。正式假设审查仍需逐项核对预设 falsifier；本批不能作为 Architecture Assumption SUPPORTED 的依据。

## 原始证据

本地目录：`../runs/semantic-stability-20261002T081859Z-3cf11c8e24f7/`。runs 默认被 Git 忽略；本报告和可复现的协议、fixture、代码与测试保留在工作区版本管理范围。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | 72e8d0976d00c9023666fff38928a0af90402de83c9271fe933bd17b1740f89d |
| summary.json | 6aeedc123ad6a8725c45f6cff9e10be9adeb1eb7061a6deb318618ca5811a8ea |
| evidence.jsonl | 9fc9213a4ad5aa2e727e8e7dab411f0c2b4e055927a486266f06dfd16337e502 |
