# C1 / C2 版本边界与诚实回放验证

日期：2026-10-03。批次：`version-replay-20261003T134732Z-4296409a3b3f`。C1 的 21 项检查、C2 的 22 项检查全部通过，并完成原始记录复核。**AA-C01、AA-C02 在预先声明的单进程内存版本与回放机制范围内为 SUPPORTED**。本轮不提供真实模型语义正确性或 provider 输出可复现的证据，AA-A02 的 DENIED 和 Gate E/F 的 OPEN 保持不变。

## 范围与实现

旧 C1 foundation 只检查预设版本记录的共存与 activation，没有完整覆盖同一事实在新边界的正式提交及历史重建。本轮复用共享 CanonicalRegistry、BoundaryRuntime、SecurityRuntime 和 CurrentResolver，将两个版本的候选分别正式提交，并按保存的 exact refs 构建历史视图。

依据综合 Spike §4.10 允许的 selected reinterpretation fixture logic，本轮候选含义和 semantic PASS 使用显式脚本预设。provider 的 revision 可用性和新输出也由受控 fixture 提供，用来隔离 C2 的记录与能力判定机制。事实、版本、grant 和 retention 事件是预先声明的实验条件；本轮没有调用外部 LLM，不消耗 S1/S2 预算。固定场景及限制见 `fixtures/version-replay-v1.json`，每个确定性场景只运行一次。

新增 ReplayRuntime 分开 historical_reconstruct 和 reexecute。前者只读取保存的 execution、ContextManifest、validation、CommitOutcome、事实、版本和原始 artifact，不调用 provider；后者显式接收目标环境，产生新的 execution，记录历史环境、实际环境、差异原因和新输出，且不自动正式提交。C1 的 reinterpret 由场景中的独立入口组织，使用相同事实、目标活动版本和共享 owner 提交机制；它是选定的 reinterpretation fixture，没有声称实现通用的生产重解释服务。

原始 artifact 的元数据、摘要和精确引用保留在历史中，字节放在独立内存 artifact store。retention 刺激实际移除该 store 中的内容，保留删除原因；不会把已保存的 Observation 输出拿来重建丢失的原始字节。这不是生产环境中删除所有副本或备份的实现。

## C1：版本发布、激活与历史使用分离

在 v1 活动时，从同一事实 work:2 形成并正式提交 O:r1。提交 v2 canonical 后，活动版本仍为 v1；显式激活新 profile 的 protocol 与 rule 后，新边界形成并提交 O:r2。O:r1 的内容、依赖和 VersionContext 保持不变，两条 revision 物理共存。

激活 v2 后，按旧 exact ref 解析 O:r1 仍然有效，因为其声明的旧版本组合继续兼容；新的活动版本没有触发全局失效。两次 historical reconstruction 分别还原 v1 和 v2，不改用当前 head 或当前活动版本。两个视图均为 FULL，provider 调用数为零。随后以 Evidence v1 的 profile 消费 O:r2 并正式提交 E-0:r1，说明本次组合无需统一的全局 semantic generation。

C1 共三条派生记录，全部具有对应正式 CommitOutcome。没有观察到必须引入全局原子版本代际才能完成合法边界或历史重建的反例。结论限于声明的 per-boundary 机制；X2 的在途 Policy 版本变化仍需单独执行。

## C2：缺失对不同操作产生不同结果

| 条件及请求 | 结果 | 输出性质 |
| --- | --- | --- |
| 完整记录，重建历史 | FULL | 保存的原始输出及精确来源记录 |
| 完整记录，同环境重新执行 | FULL | 新 execution 的不同脚本输出，未验证、未提交 |
| 原模型 revision 不可用，重建历史 | FULL | 仍可读取保存的历史，不调用模型 |
| 原模型 revision 不可用，请求该模型重新执行 | UNAVAILABLE | 明确报告 RequestedModelRevisionUnavailable，不自动替换 |
| 显式请求另一可用环境 | PARTIAL | 新 execution，记录环境差异，不称为旧模型输出 |
| 恢复原模型后移除原始字节，重建历史 | PARTIAL | 已保存的输出和元数据仍在，原始材料为空且注明删除 |
| 原始字节缺失，请求重新执行 | UNAVAILABLE | 不以旧输出补造输入，也不调用 provider |

模型不可用和原始材料缺失分别注入，retention 阶段先恢复原模型，避免混淆原因。只发生两次明确请求的脚本重新执行，所有历史重建均未调用 provider。FULL 表示该操作要求的环境与依据完整，不代表输出与过去相同；测试刻意让同环境新输出不同于历史输出。

删除原始字节没有自动抹去历史 Observation，也没有使保存的语义记录自动失效。全部原历史记录保持不变，C2 最终仍只有一条正式派生记录，两个新输出仅保存在明确标注 EXECUTION_ONLY_NOT_HISTORICAL_OUTPUT 的 execution 中，其 validation 为 NOT_PERFORMED_NO_FORMAL_COMMIT。没有观察到必须重跑模型才能解释历史、以新输出冒充历史、或掩盖缺失依据的反例。

## 验证与设计后果

新增七项本地测试覆盖未激活版本不得使用、精确历史版本、当前权限与 Data Authority 拒绝、原 provider 缺失不自动 fallback、原始字节移除与不可重装、摘要不匹配、以及重新执行期间撤权或删除输入后不返回新输出。全套 156 项测试通过。当前权限检查已接入；这组单元测试不代替 X4 的正式组合验收。

运行后重新计算 snapshot 指纹和原始 artifact 摘要，逐个将历史视图中的记录与最终不可变历史核对，确认版本上下文和历史输出直接来自保存记录。另核对四次正式提交，以及七个 C2 操作的能力结果、新输出的 execution-only 标记和未正式提交状态。冻结清单中的全部文件哈希匹配，原始 runner summary 保持待证据审查，不回写为假设结论。正式评估另存于 [C1/C2 评估](assumption-c1-c2-20261003.json)。

设计上保留 per-boundary versioning、精确历史引用及 operation-specific capability；provider 不可用影响重新执行能力，不影响已保存事实的存在。新的必要机制是 replay manifest 对精确历史记录的索引、独立原始字节存储和能力缺口报告。manifest 只保存历史引用，不是新的 Observation standing 来源；artifact 删除不自动执行语义 invalidation。当前未实现生产 retention、跨进程恢复、通用数据迁移或反事实评估，也未关闭 X2/X4。

## 原始证据

目录：`src/spike/runs/version-replay-20261003T134732Z-4296409a3b3f`。外部模型调用为 0。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `d837b6f6850a8f414d0244e78711d936cc592c7409e52ae79a2e255accab31b1` |
| summary.json | `96e686571b93a3d81d6fad70110b8a4f1cf44238e9edefb017c98f00e84f410c` |
| C1.jsonl | `fbbfa65ed8e0ab114bd595d06c46e1bbb5ea047c41b4156f99859bd2bf1badb2` |
| C2.jsonl | `dd3d3009111529e616de832e0b782f7057a1924380cc577ca60434759b47f7c1` |
