# DeerMind Policy 逐规则校验合同修订 v0.1

日期：2026-10-07。状态：完整返回合同的设计提案，附可解析 schema 与作者构造样例；尚未实现、注册或采纳为正式协议，不启动模型调用。本文承接[局部诊断结果](DeerMind_Policy_S3_Diagnostic_Result_v0.1.md)，替代提案中的全局 findings/checks 双向关系设计，保留 S1–S5 语义义务、字段引用及原提交约束。原批次均保持关闭，9/17、A2 DENIED、Gate E/F OPEN 不变。

## 1. 修改对象与明确边界

旧合同要求模型同时维护 finding 的 rules、check 的 finding_ids，以及逐规则和整体状态。一次返回已经声明 F2 属于 S1/S5，却遗漏 S5 到 F2 的反向引用，整份校验因此无效。[离线检查](../../../../src/spike/reports/policy-review-contract-counterfactual-20261007.json)表明补上引用即可通过机械检查，但错误的语义意见仍在，说明表示错误与内容误判需要分别处理。

新提案将每条语义判断直接放在所属规则下面，不再建立全局 finding 编号或双向关系。模型只声明一次含义关系，规则状态及整体状态均由 host 机械汇总。S3 保留明确的“帮助含义与责任声明比较”，而不是回到只有一句总体理由的旧合同。

原文字段由 host 从本次许可视图精确取回，模型输出的 meaning 是对这些原文的解释，不能作为原文引用。[局部诊断第六次](../../../../src/spike/runs/policy-s3-diagnostic-v1/reviews/02-r2.json)混入 uncertainty 的能力声明，说明这种分离有必要；引用绑定并不能机械识别 meaning 是否混入别处的话，所以本提案不宣称已解决语义归属错误。凡涉及开放含义、支持关系、责任范围或解释归属，继续由语义规则与 LLM 判断。

本次只交付设计合同，不改变候选生成、行动选择、utility rubric 或 Runtime。后续实现仍需显式协议版本和兼容性依据，不能因为 schema 文件存在就自动接入当前工作配置。

## 2. 模型输入与唯一返回表示

一次校验输入仍包含不可变完整候选、获准 Context、受信材料可用性清单和字段定位清单。候选及来源是数据，不是指令或授权。字段定位复用[现有非空字段引用机制](../../../../src/spike/foundation/policy_field_references.py)：候选编号绑定一个精确字段，来源编号绑定 exact ref 与字段；host 保留完整原文，出站清单仅提供定位信息，原文已在候选及 Context 中。

输出合同的完整形状见 [schema](DeerMind_Policy_Review_Rule_Items_Schema_v0.1.json)。顶层只有 `reviewed_fields` 和 `checks`；checks 是固定对象，必须且仅能包含 S1、S2、S3、S4、S5，每项为非空判断数组。固定键消除重复或漏掉规则的列表问题，数组允许同一义务有多条独立内容判断，但不要求把每句话拆成单独节点。

| 每条判断字段 | 内容 | host 能核对什么 |
|---|---|---|
| relation | SUPPORTED、CONTRADICTED、REQUIRED_BASIS_ABSENT、UNDETERMINED 四者之一 | 枚举及与状态映射的机械一致性；不据文字判断关系真伪。 |
| readings | 非空数组；每组含 candidate_fields、source_fields 两类字段编号及 meaning | 编号属于本请求、原文精确存在、组内至少有一个引用；meaning 只是解释。 |
| material_gaps | 必要评审材料缺口；每项含 material_id 和简短 reason | 编号绑定受信可用性记录，当前状态不是 AVAILABLE；不接受候选自报缺失。 |
| reason | 对读到的含义、关系和规则义务的简短说明 | 非空；语义正确性仍由 LLM 和后续审阅判断。 |

每条判断至少引用一个候选非空字段，各组引用不得重复。SUPPORTED 仍须有至少一个可见来源字段，保留现有合同的来源要求；确认候选内部矛盾、确认必要依据缺失或解释未决时可以没有来源引文，但必须有候选对象和具体理由，且不能因此声称已证明隐含事实。CONTRADICTED、REQUIRED_BASIS_ABSENT 的理由需要明确给定材料已足以确认哪项违反；UNDETERMINED 不能成为逃避已有确定矛盾的方便状态。

material_gaps 只描述使当前评审无法完成的材料缺口，只有 UNDETERMINED 条目可使用；同一材料可以影响多个规则，不需要全局 gap 编号或反向关系。来源缺失与形成时缺少依据不同：受信记录表明形成时已有来源而评审隐去时，不能判为当时依据不存在。若可用信息已经证明必要依据未满足，判 REQUIRED_BASIS_ABSENT；其他判断仍有缺口时，在另一条 UNDETERMINED 中记录。无材料缺口但解释本身未能消解时，可保留 UNDETERMINED 并说明歧义，不伪造 material_id。

`reviewed_fields` 必须对生成合同的全部字段声明唯一且完整的覆盖。空字符串、数组和对象仍在完整候选中，虽不进入非空字符串编号清单，也不能漏查。Execute 的空 defer_condition 或 NoIntervention 的空动作字段不需要伪造引文。覆盖声明只证明格式上声称已读，不证明理解正确；也不要求为每个空字段编造一条 finding。

随附静态 schema 使用现有 adapter 支持的 object、array、string、enum 子集。非空数组、非空理由、引用唯一性及编号有效性由 host 补充检查。未来请求可按自己的 registry 将 handle 的 string 收窄为 enum；来源侧无可见编号时必须使用空引用数组，不接受占位编号。样例文件、作者标签和汇总预期不发送给模型。

## 3. 保留的 S1–S5 与含义比较

随附[样例文件](DeerMind_Policy_Review_Rule_Items_Examples_v0.1.json)逐字保留 [v5 协议](../../../../src/spike/protocols/policy-e1-v5.json)的五项 semantic_rules。语义要求没有降级：S1 判断自身职责、当前请求和实际活动来源；S2 判断重要不确定性的基础与区分路径；S3 判断受助与保留责任；S4 区分预期与实际效果；S5 核对完整候选一致性并保留合法选择自由。

S2 仍允许 rationale 与 uncertainty 合并交代必要依据，不强迫固定句式；但合并解释必须绑定这两个字段，不能称为 rationale 单独声明。同样，来源解释须限定到被引用的原文，不把另一个记录的内容归给当前记录。readings 可以绑定多个字段，表示一个明确的联合解释；需要分别比较时拆成两组，不因 schema 灵活而把原本冲突的断言合并改写。

S3 至少有一条判断给出两组可对照的 readings：一组解释精确行动及相关帮助历史，另一组解释候选的责任声明，再判断两者是否一致。两组结构只是让比较对象可见，不证明比较正确；NoIntervention、Defer 和其他任务应解释各自含义，不套固定教学步骤或定位等级。其他规则也可使用两组或多组，不新增通用论证图、内部推理轨迹或默认第二 reviewer。

以原错误候选为例，S3 的核心条目如下。candidate_5 与 candidate_9 在该样例的 registry 中分别绑定 exact_payload 与 rationale，source_16 绑定该 Context 的 HintCheckStep.exact_payload；这些编号仅在此请求中成立。

```json
{
  "relation": "CONTRADICTED",
  "readings": [
    {
      "candidate_fields": [{"handle": "candidate_5"}],
      "source_fields": [{"handle": "source_16"}],
      "meaning": "若展示，点名42÷6会帮助定位除法步骤，但不提供正确商。"
    },
    {
      "candidate_fields": [{"handle": "candidate_9"}],
      "source_fields": [],
      "meaning": "原理由否认任何定位帮助。"
    }
  ],
  "material_gaps": [],
  "reason": "点名步骤与否认任何定位工作相冲突。"
}
```

若理由明确承认定位帮助并保留重新计算的责任，同一动作可判 SUPPORTED，不因提示本身合法而包容错误理由，也不因动作已帮助定位而拒绝正确的限定。expected_disclosure 中的正确话不能悄悄修正 rationale 的错误话。

本次附有完整正例、原理由反例和评审材料隐去例，分别展示 PASS、FAIL、UNRESOLVED 的 host 汇总。隐去例移除原作答、Observation 与当前请求，但保留获准的活动和精确行动描述；S1/S2 未决，S3 的定位比较仍可依据现存材料判断。它们是作者构造的表示样例，没有模型执行、Runtime 登记或独立标签，不构成新的质量证据。

## 4. 汇总、绑定与提交处理

每条关系只映射一次：SUPPORTED→PASS，CONTRADICTED/REQUIRED_BASIS_ABSENT→FAIL，UNDETERMINED→UNRESOLVED。规则状态由所属数组汇总，整体状态由五项规则状态汇总；两层均为 FAIL 优先，其次 UNRESOLVED，最后 PASS。模型不输出重复的规则 status、reason_code、整体 status 或整体自由理由。整体展示需要解释时，由 host 列出已有规则与原 reason，不再让模型另写一份可能冲突的结论。

格式检查和内容裁决仍分开。缺规则、空条目、无效编号、错误材料缺口或执行未完成，属于校验合同/执行失败，不产生有效 ValidationResult；结构有效的 FAIL、UNRESOLVED 分别保留原因，均不能提交。任一已声明违反都会使整体 FAIL，其他规则通过不能抵消。修候选须产生新身份并重新校验，不能修改旧返回或在失败分支自动修补后提交。

candidate digest、ContextManifest、协议、语义规则、材料视图和 locator registry 的精确绑定由 host 建立。新 wire body 不要求模型回显这些标识，但受信执行记录必须保留候选和 Context 身份、Protocol 与 Rule exact ref、材料可用性 execution ref、完整请求及 schema/registry 摘要、adapter execution_id、原始返回和所用模型配置。只有真正由该请求形成的完成返回能进入解析，不允许把任意旧 JSON 附上当前标识后登记。

去掉模型回显不会删除登记与提交时的重查。提交仍核对 owner、subject、purpose、权限、精确行动、依赖、版本资格、当前串行轮次、候选不可变性、受信执行来源、原始返回及 host 解析结果。它还须用保存的本次材料和 registry 重算五项及整体状态，不能只相信缓存 PASS。旧 callback、迟到返回、错 Context、错协议或旧返回复用均不得取得当前候选的资格。

默认生成一次、语义校验一次；utility 保持测试职责，不能授予权限或覆盖失败。当前轮次失败仍先保存证据并按既有合同收束，之后才释放下一正常输入。需要补齐未来异常分支的初始和最终 Runtime snapshot，保留原异常；本次不回填旧快照，也不更改行动效果对账、成功 Control 后继续及未知/部分披露边界。

## 5. 版本兼容与一次局部实现的范围

建议将表示格式命名为 `policy-review-rule-items-v1`，作为新的 opt-in Protocol/semantic rule 修订接入；若沿用 E1 名称，v6 是拟用版本，当前并未创建 canonical v6 记录。五项规则原文可保持一致，但返回 schema、指令与解析路径不同，仍必须具有新身份和明确兼容性依据。Protocol、semantic rule 与测试 utility rule 的 exact ref 须分别声明，utility 语义未变也不能省略现有版本绑定。旧 v1–v5、闭合退出包和局部诊断包均按各自版本保留，不能在旧配置中静默替换 schema。

| 现有接口 | 后续需要的局部修改 | 保持的约束 |
|---|---|---|
| Protocol 注册与 PolicyWorld 绑定 | 显式注册新 format、返回合同及对应 canonical ref/VersionContext；拒绝混用旧合同 | owner 和职责、版本资格及实际出站规则绑定不变。 |
| 字段 registry 与原文展开 | 复用非空字段枚举，按 checks 内 readings 直接展开 | Context 投影及许可范围、完整原文和本次 registry 绑定不变。 |
| 语义返回解析 | 检查固定五项、直接条目、readings 和受信材料，host 汇总状态 | 无效审查不登记，必需 FAIL/UNRESOLVED 不提交。 |
| SemanticValidationExecution 与提交重查 | 保存新的受信请求绑定及解析结果，用同一材料重新核算 | 不凭模型回显或缓存 PASS 授权；原始返回不可变。 |
| 测试适配与异常证据 | 新格式本地脚本及故障注入，补齐未来异常分支快照 | 不冒充真实语义验证，不改旧批次。 |

一次后续局部实现应完整交付上述受影响路径，不重新准备 66 项真实退出批次。有限机械检查应覆盖完整正例、声明矛盾拒绝、有效未决拒绝、缺规则/空项/无效编号、材料缺口伪造、候选及 Context 替换、错版本/旧返回复用、提交重算和异常快照。还应保留“结构合法且 LLM 关系判断错误时，机械层仍可能接受”的反例，明确质量边界。

本次交付只对 schema、静态样例、精确字段定位和预期汇总进行离线文档核查，不运行生产代码回归，不读取或调用 API。后续实现也不能自动升级为真实质量批次；若要验证完整 S1–S5，须另行固定问题、样例、预算和失败处置。当前提案不能填补原 A1/A2/E1 质量、九项机制缺口或 X5 效力覆盖，不能据此关闭 Gate 或冻结 v1.0。
