# 工作设计的协议与执行入口核查（2026-10-07）

本次已完成代码检查和一次现有本地测试核验。30 项串行、失败收束与活动转换机制测试通过，用时约 6 秒，网络连接在测试进程中显式禁止，真实模型调用为零。没有改动运行代码、协议或旧批次。[机器记录](working-design-entry-audit-20261007.json)保存测试结果及 23 个检查来源的摘要。

## 1. 当前实际执行链

ContextAssembly 选择精确 Protocol，绑定协议和规则版本，并检查来源权限、允许类型、用途和当前性。生成产生 Candidate；提交前检查字段合同和必需语义校验，确认 candidate digest、Context、Protocol、规则及受信执行匹配。Policy 的活动允许清单检查由声明的 legality_profile 开启。正式 commit 再检查权限、依赖、版本、生命周期、预期 head 和已绑定轮次。

ActionRuntime.create_intent 要求已正式提交的 Execute Policy，检查所选 canonical ActionSemantic 与依赖，并绑定 exact payload、executor_target、scope、purpose 和权限参数。派发时再次检查权限、有效期、当前前置条件以及已绑定轮次。ActivityRuntime 还检查原活动、episode 和 CURRENT 依赖，成功确认后才写 ActivityTransitionOccurred。SerialSession.effect_result 处理结果，continue_cycle 仅接受成功活动转换，普通展示不能开启同轮继续。

| 约束 | 实际位置 | 核查结果与范围 |
|---|---|---|
| 必需语义校验与精确绑定 | [boundary.py](../foundation/boundary.py) validate / commit | 缺失、FAIL、UNRESOLVED 或绑定错误不提交；不证明模型 PASS 内容正确 |
| 活动允许清单与精确行动 | [policy.py](../foundation/policy.py) policy_legality | 选定 policy-admission-v1 后检查允许动作及参数；不是所有任意 Protocol 的默认行为 |
| 正式 Policy 到 Intent | [actions.py](../foundation/actions.py) create_intent / execute | 需要真实 CommitOutcome、当前 Policy / action 和参数权限；目前为本地 mock executor |
| 普通输入排队与失败收束 | [session.py](../foundation/session.py) start / check_context_open / finish_close | 已注册 session 的输入不会提前进入新轮；旧轮迟到输出不能恢复提交；在途派发未收束不能释放队列 |
| 成功 Control 后继续 | [activity.py](../foundation/activity.py) execute；session.py continue_cycle | 原活动精确依赖与成功实际事件必需，失败、未知或普通展示不能代替转换 |

这里的“存在”是相应组件及已绑定局部路径有该检查，不是全系统所有入口已经强制采用。BoundaryRuntime.session 初始为 None；Action 和 Boundary 只在 coordinator 存在时检查轮次。部分机制 World 有意不注册 session，属于 Spike 裁剪。后续声明严格串行的工作入口必须明确强制创建并绑定 coordinator，不能把可选组件的存在等同于产品全入口已受约束。

## 2. 文档工作集没有自动改变协议

| 入口 | 当前固定绑定 | 与工作决定的关系 |
|---|---|---|
| A1 formation campaign | fixture 指定 observation-a1-v1.json | 保留旧批次与停止状态，不自动选用后续表达修订 |
| X5 ActivityWorld | initial 使用 observation-smoke-v11；request 使用 observation-x5-request-v1；new-work 使用 observation-x5-new-work-v1；Policy 使用 policy-x5-v1 | 仍是原完整转换实验，不是拟保留的无自动切换范围 |
| E1 campaign | fixture 指定 policy-e1-v1 | v2/v3/v4 通过显式 rule_revision 和声明 binding 使用；v4 局部实现不等于旧入口已切换 |
| 表达合同局部验证 | observation-expressions-v12.json | 独立可选检查，不证明真实 A1 或 X5 已按该协议完成 |

旧 campaign 的入口还检查冻结摘要与目录预约状态，不能通过覆盖其文件悄悄续跑。新工作合同须有独立、明确的组合入口，不能仅靠文档引用或改文件名代替 Protocol、规则、Context、allowed actions 的实际绑定。

## 3. X5 延后目前缺什么

原 ActivityWorld.run_path 明确注册 SwitchToTeaching 和 SwitchToIndependentPractice，给出参数绑定的执行 grants，并把动作放入该次活动允许清单，再创建 Intent、调用 control executor。因此它合法执行原实验目标，当前不存在工作决定要求的“禁用自动切换”配置。不能复用这个入口后声称 X5 已经延后。

拟保留范围需要一个独立、版本化、可选的入口，登记所用 Observation / Policy 协议、固定活动和允许的局部动作，强制创建 SerialSession；在 Context / 提交和 Intent / 派发处都限制自动 Control。限制按受信的类型、exact action refs 和注册执行目标实施，开放教学含义仍由规则与 LLM 判断，不添加措辞分类器。不能仅隐藏模型 Context 中的切换动作，却让既有 Intent 继续调用 ActivityRuntime。

该入口应复用现有 boundary、actions 和 session，不重写一套执行链。旧 World、协议、批次和 defaults 保留。接受检查限定为：允许的局部行动可执行；被禁止的转换不能正式提交或派发；已有 Control Intent 不能绕过范围限制；失败旧候选不能被复用；排队及失败收束仍成立。对于没有配置该范围的旧实验，不能强行改变其合法活动转换能力。

当前完成的是缺口定位，尚未实现上述入口。X5 仍 INCONCLUSIVE，不能记为完成 STAGED；A1/A2/E1 语义质量也未因本次机制测试改变。

## 4. 本次核验的限度与下一步

运行既有 test_turn_closure、test_serial、test_activity_composition，共 30 项测试，无失败、错误或跳过。它们使用脚本 transport 和同步 mock；LocalWorld 为机制测试将 Observation 协议替换为显式局部 fixture。因此结果验证已实现的串行与 Control 机制，没有验证真实 v11/v12 形成质量、v4 模型可用性、完整真实 X5 或远端取消恢复。旧真实模型断连与多结果缺口保持。

下一步实现独立的可选受限入口及上述有限检查，先证明工作功能范围在机械入口上成立，再决定受影响的真实语义补证计划。本次没有任何理由重新调提示词或追加 reviewer。原 Completion、9/17 和 Gate E/F OPEN 不变。

设计依据：[收口设计决定](../../../doc/system-design/DeerMind_Semantic_Validation_and_Spike_Exit_Decision_v0.1.md)、[路线图 v0.6](../../../doc/system-design/DeerMind_System_Design_Roadmap_v0.6.md)。
