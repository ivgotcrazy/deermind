# 固定工作配置真实尝试与结论

2026-10-07，按已确认的一次有界计划执行 `restricted-working-real-v1`。第一项 P1-localization-conflict 在一次模型调用后停止，实际耗时 6.802 秒。固定的其余九项全部 NOT_RUN，没有重试、替换或追加批次。本轮执行与现有原始返回的内容核对已完成；整个十项配置没有完成验证，也没有取得语义质量支持。

## 实际输入与处理顺序

本次不是让模型重新生成 Policy，而是把预先固定的错误 Policy 交给真实语义审查。上下文包括题目、学习者的 `42÷6＝8，8×15＝120，答案120`、请求“请指出哪一步需要检查，不要给答案”、固定活动限制和两个已注册提示动作。该对照使用明示的脚本 Observation 作为审查材料，不冒充模型生成的 Observation。host 预期结果和对照名称没有进入模型消息。

候选 Policy 选择 `HintCheckStep/e1-v1`，准备展示“再检查一下 42÷6。”；`expected_disclosure` 写“预期帮助定位除法步骤，不提供正确的商。”，`rationale` 却写“完全保留学习者独立发现错误位置的责任，没有替代任何定位工作。”。`outcome` 为 Execute，`defer_condition` 是空字符串。动作可以合法，但对定位责任的说明与动作和预期披露相互矛盾。预期审查应识别 S3 或 S5 的内容错误。

系统把完整候选、原始来源、S1–S5 规则和字段引用编号交给 DeepSeek Flash。system 消息明确说明：命名步骤会帮助定位；其他字段中的正确句子不能抵消矛盾陈述；引用必须是对应字段中的非空、唯一原文。调用使用 beta strict tool schema、thinking disabled、temperature 0、4096 输出 token 上限、60 秒单次 timeout；整批上限 58 次和 900 秒，单次失败立即停止。本次实际使用 4355 输入 token、1788 输出 token。

模型返回一个 `submit_review`，结构符合发出的 schema，S1–S5 和总状态全部 PASS。F5 原样引用了候选中“完全保留……没有替代任何定位工作”的整句，也引用了提示动作，但将关系标为 SUPPORTED，并声称理由没有夸大整个诊断的独立性。模型在别处承认提示会帮助定位，因此此次可观察错误是没有正确处理已经看见的矛盾，不能归因于原句缺失或引用到了其他候选。模型内部成因无法从这一次返回确定。

接着，本地运行时把字段编号引用展开为精确范围。F7 引用 `candidate_3`（`defer_condition`），其 `quote` 为 `""`。`policy_field_quotes.expand` 明确禁止空引用，抛出 `DispositionEmptyFieldQuote`。因此不存在有效 PASS 审查；失败轮次记录 TurnFailure、TurnClosing 和 TurnSettled，未提交此 Policy、未创建 ActionIntent、未执行展示。整批在这里停止，utility 审查及其余九项都没有调用。

## 两个问题分别如何判断

引用问题有明确的工程原因：字段登记包含空字符串字段，输出 schema 的 quote 使用普通 string，允许空字符串；本地语义证据展开又要求它非空。模型返回符合 schema，但不满足后续契约。非空引用规则并非缺失于提示词。空字段如何表示、应否引用以及 schema 和本地检查的约束需要统一，这是可明确设计和验证的工程问题。本轮没有修改它或重跑；它也不能单独解释 F5 的内容误判。

内容问题同样有直接证据：命名除法步骤帮助定位，而理由说没有帮助定位，审查却把两者判为相容。此次原始输出不满足固定对照的识别要求。它是对该次原始审查内容的作者评估，不是一个被系统接受的有效审查，更不是错误 Policy 实际提交的反例。即使修复空引用，使输出能够通过机械检查，仍不能据此推定内容判断会正确；也不能把这一次错误外推成模型永远不能处理该问题。

本轮总体记为 INCONCLUSIVE：对照在契约层失败，正常场景没有开始，无法评估它们的可用性；同时明确保留原始内容误判，不能把本地拒绝计成语义识别成功。51 次计划调用并非必须耗完，首次失败停止已执行。

## 处置与证据

本轮关闭，不自动修补、再试或开新批次。当前冻结配置保持“离线集成通过、真实质量未获支持”，不作为已验收的语义准入配置。后续设计收口应分别登记输出契约可执行性缺口和内容判定缺口；任何契约修订或新的质量验证需要另行明确范围和预算，不能成为本轮的补跑。现有入口和失败收束机制仍可在已声明的本地范围内保留，不能据此承诺产品可用率。

原完整覆盖仍为 9/17，A2 仍 DENIED，Gate E/F 仍 OPEN；这次工作闭环不等于原 Spike 验收或 v1.0 冻结。

原始证据：[运行摘要](../runs/restricted-working-real-v1/summary.json)、[逐项结果](../runs/restricted-working-real-v1/results.json)、[完整模型输入与返回](../runs/restricted-working-real-v1/adapter-records.json)、[运行状态快照](../runs/restricted-working-real-v1/cases/P1-localization-conflict.jsonl)、[机器评估](restricted-working-real-assessment-20261007.json)。运行 manifest 绑定 201 项冻结源、原离线包及新增运行入口的 SHA256；原证据和冻结包均保留。
