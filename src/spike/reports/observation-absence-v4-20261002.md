# Observation v4：原文不存在判断与一次复核

日期：2026-10-02。审查者：Codex。批次：`semantic-stability-20261002T080729Z-88bcd858239c`。

## 交付与结论

已实现用户确认的合同：程序核验直接引语的字面存在性，LLM 判断归属与含义；模型声称原话不存在但程序找到原话时，原始输出保留，有效校验结果为 UNRESOLVED；最多发起一次专门复核，仍有矛盾、失败或未决则不提交。字面存在不自动产生 PASS。

**真实批次 NON_SUCCESS**。共 24 次初始调用，17 次符合预期（10 次正例通过、7 次负例拒绝），4 次结构协议错误，3 次传输失败。没有有效语义结果中的误放或误拒；不能把其余 7 次失败算作语义正确。

未观察到原文存在性矛盾，因此本批实际复核调用为 0。真实自述正例两次通过，v3 的该误拒未在本批复现；这不撤销旧反例，也不能据此证明复核会稳定纠错。复核分支目前取得的是本地故障注入测试证据，尚无本批自然触发的真实模型复核证据。

## 实现合同

- 使用独立 v4 协议及 fixture，不修改 v1–v3 协议、样例和历史运行。
- 每个片段附带 support 分类：supported / text_absent / speaker_mismatch / meaning_mismatch / uncertain，分别约束 PASS、FAIL 或 UNRESOLVED。字面不存在仅适用于 direct_quote；转述、翻译仍需语义判断。说话人或含义不符必须给出原始来源。
- 程序只在本次已获准 Context 的字符串字段内精确查找，不扩读其他存储。找到原话时，保留原始 FAIL 输出，同时形成有效结论为 UNRESOLVED 的可信校验记录和 source_conflicts。
- 一次复核传入发现原话的精确来源及上下文，重新检查整个 exact candidate。复核前再次验证授权及数据使用权限；新执行关联 previous_review_id。
- 初次失败、复核失败、持续矛盾、预算不足均不会产生隐式重试。相同已注册候选再次调用也不会开启第三次校验；错误记录不被删除。
- 提交时重新执行结构、来源、矛盾及候选绑定检查。该上限实现于当前内存 Runtime，不声称具备跨进程恢复保证。
- 传输错误采用固定脱敏标签区分 timeout、DNS、TLS、连接重置／拒绝、远端断开及读取不完整；不保留异常原文、密钥或响应头，不自动重试。

本地 **88 项测试通过**。覆盖首次矛盾转未决、一次复核通过、复核仍失败／未决、权限撤销、网络失败、预算不足、禁止第三次调用、旧记录不可提交、复核前后证据保存和传输分类脱敏。`git diff --check` 通过。脚本测试的语义意见是显式注入，不充当真实模型语义效果。

## 冻结实验

使用 v3 的 12 个已有开发者样例，各执行 2 次。共 24 次初始校验，只有原文存在性矛盾才允许一次复核，预声明最大调用数 48；实际调用 24。未进行网络重试、调参或失败样例替换。不是新的独立盲测数据，也不评估跨题泛化或生成质量。

- 模型：deepseek-flash；temperature 0；thinking disabled；每次输出上限 3072 tokens；60 秒 timeout。
- 协议 SHA-256：`03722a159c6d04d9fec40ca36bfef952a6d382b9fbd64be797b50d5e961a188d`。
- 完成后复核 manifest 中全部冻结文件哈希，无差异。本报告在批次完成后新增。
- 21 个收到的模型响应均报告 fingerprint `aeb56401ca74e127821c4f9126dcb669`。
- 已报告输入 41129、输出 15902，合计 57031 tokens；3 次失败未返回 usage，其计费情况未知。`.env` 保持不变。

| 样例 | 预期 | 第一次 | 第二次 |
| --- | --- | --- | --- |
| 英文同义表达 | PASS | PASS | PASS |
| 中文表达 | PASS | PASS | PASS |
| 有来源的学习者自述 | PASS | PASS | PASS |
| 缺少最终答案判断 | FAIL | FAIL | 远端断开 |
| 越界推断潜在能力 | FAIL | 远端断开 | 远端断开 |
| 越界提出教学行动 | FAIL | 协议错误 | 协议错误 |
| 附加错误算术断言 | FAIL | FAIL | FAIL |
| 虚构学习者自述 | FAIL | 协议错误 | 协议错误 |
| 转述真实讲解请求 | PASS | PASS | PASS |
| 将教师发问误归给学习者 | FAIL | FAIL | FAIL |
| 中文自述转述为英文 | PASS | PASS | PASS |
| 来源明确否认请求 | FAIL | FAIL | FAIL |

10 次有效 PASS 均提交，7 次有效 FAIL 均被提交门拒绝。其余 7 次未取得可用的校验记录，不进入提交。summary 中 `unresolved_reviews=0` 指模型有效校验记录无 UNRESOLVED，**不表示没有未决实验**：4 次协议错误及 3 次传输错误的单次实验结果均为 INCONCLUSIVE。

## 协议错误复核

虚构自述的两次响应均正确指出直接引语不在来源，但把紧随其后的“这是学习者自述而非独立能力判断”这个转述片段也标为 `support=text_absent`。v4 明确限制该分类仅用于直接引语，故产生 `VerbatimAbsenceOnlyForDirectQuote`。这能阻止提交，但不是完整、可接受的负例校验成功。

教学行动负例第一次把无来源的教学建议标为 paraphrase + text_absent，也触发上述错误；第二次给出 `status=FAIL` 与 `support=uncertain`，违反 uncertain 必须对应 UNRESOLVED 的合同，触发 `SupportClassificationStatusMismatch`。

这些错误说明输出分类的一致性仍不足，也暴露出需要继续审查的表达问题：原文字面缺失、某断言缺少足够支持、与来源含义相矛盾和职责越界是不同关系。当前理由字段对“无依据的非引语断言”表达不够顺畅；不能简单放宽 text_absent 到转述后用字面匹配代替语义判定，也不能把模型已表达的局部否定包装成整条校验通过。

## 传输问题

3 次均分类为 `ProviderRemoteDisconnected`，比 v3 的笼统 ProviderTransportFailure 提供了更具体的故障位置。该结果仅表明连接对端断开，不能确定是供应商服务、代理还是其他链路环节。没有为这些失败自动追加调用，也没有将未使用的复核预算拿来重跑失败样例。

## 后续边界

需要先明确非引语断言的“支持不足”如何表达，以及它与 meaning_mismatch、uncertain、boundary FAIL 的组合关系，再建立新协议与独立批次。复核流程的真实模型效果仍需取得单独证据，不能从本批 0 次触发推断它有效。所有旧误放、误拒和协议失败继续保留。

完整 A1/A2、Policy、Action、Replay 和会话串行链尚未完成，Gate E/F 保持 OPEN。批次结果和本地测试都不构成整体 Architecture Assumption SUPPORTED；正式假设审查必须继续对照原 falsifier 处理旧反例。

## 原始证据

本地目录：`../runs/semantic-stability-20261002T080729Z-88bcd858239c/`。runs 默认被 Git 忽略；本报告、协议、fixture、代码和测试属于工作区版本管理范围。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | c56086105ae4a95da2e6431d75d00afb02f278f0b76e721843b6d41d62eb2e75 |
| summary.json | 5c0cee0061075ebb7bfe5060640328e205c3ff5c878c0bde9c0cca312ec144db |
| evidence.jsonl | 4dc379371a168dd27b59b166e4afaa90051de4a165efb517456ded8b6af94dfa |
