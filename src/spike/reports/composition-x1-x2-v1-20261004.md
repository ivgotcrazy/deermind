# X1/X2 在途决策组合验证报告

日期：2026-10-04。固定批次：`src/spike/runs/composition-x1-x2-v1`。**预定十五条路径已执行，十三条完整通过；X1、X2 的组合结论均为 INCONCLUSIVE。** 两次 ProviderRemoteDisconnected 留下覆盖缺口，未观察到错误提交、silent rebase、错误版本失效或撤销后的展示。本轮不补跑，不以完成后的局部成功替换失败样本。

## 结果与分类

按[运行前方案](composition-x1-x2-design-20261004.md)，三分支各五次，从同一初始快照开始，复用共享 Context / BoundaryRuntime、SerialSession、正式提交与 ActionRuntime。实际 47 次调用，低于 50 次硬上限；45 次完成、两次断连，网络执行约 2 分 17 秒。202 项本地测试在冻结前通过。没有新增有用性评分，也未修改 E1 的冻结提示词。

| 分支 | 完整 / 计划 | 已观察到的结果 |
| --- | ---: | --- |
| X1-correction | 4/5 | 原 Policy 因 Corrected 被拒绝且无 T1 Intent；收束后四次重新决策成功 |
| X2-supersede | 5/5 | v2 启用不使 T1 的 v1 决策 stale；五次实际展示，随后五次新决策绑定 v2 |
| X2-revoke | 4/5 | T1 已提交并形成 Intent，随后撤销 v1，四次展示前拒绝且无实际披露 |

X1 第一次在 Policy 生成调用断连；独立 owner 的 correction 和 r2 正式提交已经发生，但 T1 没有候选返回，T2 保持排队。X2-revoke 第五次在内容校验调用断连；v2 已启用，模型已生成候选，但没有校验完成、Policy 正式提交或 Intent，所以“Intent 之后撤销 v1”的注入点尚未到达。该路径不能计为撤销验证通过。两条失败路径均无 ActionOccurrence 或展示确认，不提供异常恢复结论。

175 项已执行检查全部通过，其中包含失败路径中已经完成的前置检查。原始汇总仍为 NON_SUCCESS / PENDING_EVIDENCE_REVIEW；正式[组合评估](composition-x1-x2-assessment-20261004.json)另行保存。X1 完整 4/5，X2 完整 9/10，按预声明覆盖条件均保留未决。X1/X2 不新增 Architecture Assumption，不改变既有假设分类计数。

## 组合证据

X1 的五次 correction 都来自独立 owner 的受信输入，旧 Observation 保留原记录，r2 通过 Context、脚本校验和正式提交形成，没有直接安装派生结果。四条完整路径的真实 Policy 和真实内容校验继续引用旧 Context，提交因精确旧依据被纠正而拒绝。典型时序为：T1 绑定 Context 在 32，correction / r2 提交在 36，T1 的拒绝结果处理在 37，收束在 38，T2 启动在 39，新 Context 绑定在 40。T2 消费 r2，经过真实 Policy / 校验后正式提交并实际展示局部提示。不能把接收到下一条普通输入当作已经处理它。

X2 十条路径都在 T1 请求已经构造后启用 v2。五条 supersede 路径保持 v1 的原始协议和 VersionContext，提交、Intent、展示均完成；结果处理及轮次收束之后，新 Context 通过 active resolution 取得 v2 及其 activation basis，再形成真实候选。T2 两次 NoIntervention、三次 Defer，均正式提交并收束，没有强行制造额外行动。v1/v2 使用同一 E1 提示词与规则并明确声明兼容，本轮验证精确版本绑定和生命周期组合，不验证任意变化后的语义兼容性。

四条完整 revoke 路径中，受信 Evolution fixture 追加 VersionRevocationOccurred，绑定 exact v1、当前 scope / learning purpose 及已有治理输入。典型时序为：v1 Policy 已提交，Intent 在 35 形成、36 绑定，撤销事实在 38；同一执行边界检查资格后得到 NotOccurred / EffectPrecondition:VersionIneligible，结果处理在 39，轮次收束在 40。未发生展示确认或 ActionOccurrence。旧 canonical record、Policy、Intent 保持不变；撤销不等同于启用 v2，也不等同于删除历史或撤销 workload grant。

总计十八次正式 Policy 提交、四次 stale 拒绝、九次实际 mock 展示、四次明确未展示。九条完整两轮路径均满足先处理 T1 结果并收束，再开始 T2。完成的二十二组 Policy / 内容校验都有 exact candidate / Context / protocol 绑定；另一个已经生成但校验断连的候选仅保留执行历史。

## 审计与后续

[离线审计](composition-x1-x2-audit-20261004.json)核对 125 个冻结输入、十五个一致的初始快照、全部结束快照指纹、旧记录不可变、模型原始输出与候选内容、正式提交谱系和九条两轮时序。补充逐条核对五次 owner r2 正式提交、十次在途版本激活以及两条失败路径无 Intent / Policy standing。受控时钟允许同一个同步边界内时间相同，跨边界的先后还由固定调用位置与执行记录确定，不能仅凭相等时间戳推断并发。

本实现新增精确版本撤销的共享资格检查，采用追加事实保留 target / scope / purpose / source。撤销事件是经过 fixture 入口结构校验的受信治理输入；不提供生产治理授权、分布式撤权或线程竞争保证。注入点位于 adapter 记录调用开始、请求构造完成后、transport 发往 provider 之前。Observation / correction 含义为脚本，Policy 与内容校验为真实模型，展示为 mock；没有用关键词实现开放语义判断，也没有新增持久 Exposure Model 或 learner-wide lock。

当前证据支持继续沿用“当前轮次严格串行、精确版本固定、提交和 effect 重验”的实现方向，但覆盖缺口仍保留。总体完整验收维持 7/17，X1/X2 的固定执行与评估已交付，不等于完整覆盖通过。A2 DENIED、E1/E2/F2 INCONCLUSIVE 和 Gate E/F OPEN 均保持。下一步推进 X3/X4 的机制组合：帮助发生后依据被纠正时保留实际披露；历史材料仍存在但当前无权访问时拒绝回放。暂不重开已收口模型批次。
