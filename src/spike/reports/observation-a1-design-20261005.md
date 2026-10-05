# A1 无 Belief 的 Observation 形成：固定方案（2026-10-05）

本批覆盖 Consolidated Architecture Spike Design v0.1 §7.1 的 AA-A01。对同一道 6kg 苹果 42 元、求 15kg 价钱的题目，固定错误、正确和不完整三类作答，每类 5 次，按重复序号交错执行，共 15 次尝试、至多 60 次真实 DeepSeek Flash 调用。每次最多生成、职责分类、算术抽取、语义与有用性联合审查四次调用，输出上限 4096 tokens、超时 60 秒，无调用重试、无语义复核、无失败替补或自动新批次。额度是上限，不是必须用完的配额。

三类输入固定为 `42 ÷ 6 = 8; 8 × 15 = 120; Answer = 120`、`42 ÷ 6 = 7; 7 × 15 = 105; Answer = 105` 与 `42 ÷ 6 = ?`。三类共用同一 ObservationSemantics v1、A1ObservationProtocol v1、Context 白名单、模型与验证规则。协议为基于既有 v11 校验机制的独立实验 profile，生成和必要含义规则适配 A1 的三类输入；不修改 v11、X5 或原 AA-A02 结论，也不把 A1 当作它们的重试。现象及原文引用沿用 description 字段承载，当前没有新增正确答案类型或 authoritative 学习者模型。它验证语义含义和绑定，不声称已经具备完整生产 ontology 序列化。

错误作答必须有依据地描述单位量路线、除法错误和单独的最终结果错误。正确作答必须描述可见路线，不能虚构错误或宣告掌握。不完整作答必须保留原算式及缺失商、后续步骤和最终答案的事实，允许对完整策略不确定，不把缺失填写成学习者答案。判据由规则约束下的真实 LLM 检查含义、来源和职责，确定性代码只检查 schema、精确引用、逐段覆盖、算术及提交条件；不以关键词判断 method、WorkIncomplete 或 mastery。

运行环境显式装载三个禁止输入：历史 LearnerBelief、TargetAssessment、PolicyOutcome。它们具有可读权限，随后由 Protocol 的类型白名单阻止进入 Observation Context，避免把权限缺失误当作 Context Policy 生效。可选禁止输入必须排除；将它们改为 required 必须拒绝组装。允许的 Context 只有当前作答及同一 ObservationSemantics，协议、规则与语义版本显式激活并绑定。禁止输入的精确 refs 不得进入候选依赖，合成 marker 不得进入任何 provider messages；marker 检查是字节泄漏检测，不是开放语义裁决。

调用前核对所有输出 schema、语义判据 id 与允许枚举、职责角色与准入表的一致性，并对三类 Context 做本地检查。该检查必须能拒绝 X5 原请求协议中的判据枚举缺陷。然后冻结源码、协议、fixture、文档与本方案。固定批次位于 runs/observation-a1-v1，目录存在即禁止重新执行。所需校验失败或未决的候选不能提交，也不被脚本替换；输出与失败均保存。

所有预定运行均完成校验、正式提交并满足各自最低有用结果，且无 AA-A01 falsifier，才可在有限样例范围评为 SUPPORTED。单纯结果质量不足或格式失败，但未证明必须依赖 Belief，则评为 INCONCLUSIVE；不能由一次失败推断架构 DENIED。持续必须读取隐藏画像、无画像只能输出 learner trait 或 Context Policy 不能结构性排除 Belief，才按原文档评估反证。任一机制不变量失败、冻结输入改变、明确配置 HTTP 错误或连续三次协议/运行失败触发停止，剩余明确记为 NOT_RUN；普通语义 FAIL 不重试。

模型返回的 PASS 只是原始测量。批次结束逐条检查候选是否覆盖预声明含义，单独保存内容复核与正式结论；复核不得给未完成必要校验的候选补发 standing，也不得把失败删出分母。没有独立人工盲审：方案与离线复核由同一工作会话完成，模型检查来自同一 provider，相关错误风险保留。本轮不额外引入学习者画像、Policy、Evidence 推断或下游教学效果测试。AA-A02 DENIED、全部历史未决以及 Gate E/F OPEN 不因本批结果自动改变。
