# Context 字段用途投影：本地实现与范围评估

日期：2026-10-06。固定运行生成于 2026-10-05；本报告完成证据复核与实现归档，没有重新执行测试或调用真实模型。

## 实现结论

[下游内容准入与 Policy 责任提案](../../../doc/system-design/DeerMind_Downstream_Admission_Policy_Responsibility_Revision_v0.1.md)中的字段用途投影已完成局部实现。消费协议显式声明每类输入的字段、用途及精确合同版本，生产协议声明输出字段允许的用途；Context 只将双方合同允许的字段交给消费者。审计字段仍保存在原始记录中，但不能因为消费者可读取该记录，就自动进入正式推理输入。该能力需显式启用，未改写历史协议、历史记录或整体提案的完成状态。

实现位于 [content_projection.py](../foundation/content_projection.py)、[boundary.py](../foundation/boundary.py) 与 [policy.py](../foundation/policy.py)。消费协议使用 `context_projection`，格式为 `declared-fields-v1`，每条输入规则包含 `kind`、`mode`、`contract`、`fields`、`use`。正式派生输入采用 `formal` 模式，并依赖生产协议的 `output_field_uses`；原始事实采用 `source` 模式和独立的 `ContentUseContract.field_uses`。派生记录不能退回原始材料模式绕过正式来源证明。

正式来源必须能在当前 Boundary 中查到一致的候选、候选摘要、成功提交与有效校验记录。只有 DERIVED 标签、尚未提交的候选、缺失校验证明，均不足以成为正式输入。合同须绑定在 VersionContext 中，且满足当前兼容性和访问授权；CURRENT 与显式 PINNED 的历史引用仍遵循原有规则。必要输入投影失败会拒绝组装，可选输入失败会记录排除，不回退到完整原文。

ContextManifest 保存来源摘要、投影摘要、合同版本、字段用途及正式来源证明。发送模型请求前重新检查权限、合同和投影，提交前再次检查来源证明。生成请求、语义校验请求及引用检查使用相同的投影内容，Policy 的机械合法性检查也不能取回被省略的行动参数。这些检查只处理结构、精确引用、用途声明与授权，没有增加自然语言关键词分类器。

## 固定验证与证据

[固定运行摘要](../runs/context-projection-v1/summary.json)记录全套 279 项测试通过，无失败、错误或跳过，其中新增 17 项字段投影测试；真实模型调用为零，网络尝试为零。运行入口是 [run_context_projection.py](../run_context_projection.py)，用例见 [test_content_projection.py](../tests/test_content_projection.py)。本次没有为改善结果补跑批次。

[独立范围评估](context-projection-assessment-20261006.json)核对了 166 个冻结输入、19 个运行产物摘要、19 份快照摘要，以及原进度清单的 341 个证据条目。两个被修改源文件的原始字节已在[修改前归档](source-baseline-context-projection-20261005/index.json)中核对。六条脚本模型执行记录的出站 messages 均不含测试专用审计标记；这是精确字节隔离验证，不是语义安全评分。恶意引用测试的模拟响应可以包含被拒绝的标记，其含义不能混同于向模型泄漏源字段。

新增用例覆盖实际组装至生成、校验和提交链路，字段用途越权，可选输入排除，未提交或校验失败输入，伪造派生标签，证明缺失，原始事实独立合同，禁止派生输入降级，版本绑定，更正后的 CURRENT/PINNED 行为，授权撤销，Context 篡改，投影后的引用范围，以及 Policy 不得恢复被隐藏参数。

## 未解决范围与下一步

测试刻意保留一个反例：若错误教学建议已经被语义校验误放入合法的 description 字段，机械投影会保留该字段中的内容。投影只能收紧内容传播边界，不能证明获准字段中的含义正确。开放语义仍须由明确语义规则与 LLM 判断；本地注入的 PASS 不能证明真实模型可靠。因此原 A2 DENIED、E1 INCONCLUSIVE、完整验收 9/17 和 Gate E/F OPEN 均保持。

当前实现只投影顶层字段，并按协议选择启用；生产持久化后的候选、校验和提交证明恢复尚未实现，既有协议也未全部迁移。脚本 Evidence 链路与 Policy 参数检查不能替代 E1 教学选择质量或 X5 真实组合轨迹验证。上述限制与真正完成的本地机制分别记录，不将整个提案标记为已实现或已验证。

下一步将 E1 的决策依据、不确定性依据、受助定位与独立重算、预期披露与实际披露区分落实为独立版本的语义合同和测试专用评分规则，保留原四个评分争议及其原始结果。先完成规则与样例评审，再依据明确范围决定是否需要有限真实验证；不自动启动新模型批次。
