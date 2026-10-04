# X3/X4 实际帮助历史与回放授权组合报告

日期：2026-10-04。固定批次：`src/spike/runs/composition-x3-x4-v1`。**X3、X4 均在预声明的确定性机制范围内通过（组合 PASS）。** 本轮外部模型调用为零，205 项本地测试通过；固定执行的 X3 42 项、X4 98 项检查全部通过，130 个冻结输入及完整证据审计通过。认知含义和回放 provider 均为显式脚本 fixture，不能扩展为真实模型语义质量结论。

## X3：解释改变，已发生的帮助保留

通过共享正式提交形成 Policy，再产生 exact Intent、mock 展示确认及 ActionOccurrence。提示发生后保存学习者新作答，依次正式提交 Observation:r1、Evidence:r1、Belief:r1。受信 owner correction 撤回 Observation:r1 后，旧 Evidence / Belief 立即 current-unusable；提前准备的旧依据 Evidence 候选因 Corrected 拒绝。

恢复按明确顺序进行：仅提交 Observation:r2 时，下游仍不可用；提交 Evidence:r2 后 Belief 仍不可用；最后 Belief:r2 形成完整可用链。三个旧 exact revision 始终存在，但没有因新 revision 出现而重新取得 current 资格。全部八条派生记录都有真实正式提交，旧候选未被静默绑定到新 Observation。

重新构建的 exposure view 与 correction 前完全相同，仍引用同一次帮助、同一响应和同一 actual disclosure；payload、completeness、rendered_at、Intent、确认及终态结果均未改变。新 Evidence 保留该原始 ActionOccurrence，新 Belief 绑定新 Evidence。重复执行已完成 Intent 只返回原终态，最终仍只有一次实际披露，没有重复展示，也没有新增 authoritative Exposure Model。

这里使用脚本为同一可见作答补充更精确的步骤描述，验证的是旧依据撤回、下游失效和重算与实际帮助历史之间的组合。没有声称模型能自行判断 correction 是否正确，也没有把重新解释当成学习者撤销了已接收的帮助。

## X4：历史存在，访问仍受当前授权约束

三个分支从相同的正式历史结果及 ReplayManifest 快照开始。每支先验证合法历史重建与重新执行均为 FULL，然后施加以下固定变更：

| 分支 | 当前权限变化 | 拒绝效果 |
| --- | --- | --- |
| replay-data-revoked | 撤销该回放操作的 DataUseGrant | 两种操作均在任何 payload 读取前拒绝 |
| raw-data-denied | 撤销旧 read DataUseGrant，另授不包含 GroundingArtifact 的有限读取权限 | 可内部读取仍获授权的记录，但不能加载未获准原始字节、调用 provider 或返回已收集内容 |
| purpose-data-denied | research 用途有匹配的 credential 和操作 AuthorityGrant，却没有对应 DataUseGrant | 两种操作均在任何 payload 读取前拒绝，不用操作权限替代数据用途授权 |

六次被拒操作均返回 UNAVAILABLE / DataAuthorityDenied，historical_view 和 generated_output 均为空，原始字节读取及 provider 输入增量均为零。六条 SecuritySignal 可回溯对应 ReplayRequested、具体历史 root 和实际请求用途。全部原始记录和真实 fixture 字节保持不变，不把拒绝访问误报成历史删除或缺失。

撤销 replay grant 的分支再安装一个新身份、相同有限范围的受信 grant，历史重建和重新执行恢复 FULL；原 grant 保持已撤销。总计八次允许回放操作：四次历史重建、四次 fixture provider 重新执行。新输出仅进入执行历史，不获得历史输出或正式派生 standing。四次 provider 调用是本地脚本，外部 LLM 调用仍为零。

## 范围、结论与后续

[运行前方案](composition-x3-x4-design-20261004.md)固定了 X3 单条完整链与 X4 三个授权分支；确定性场景各执行一次，不通过重复同一 fixture 增加“模型成功率”。[离线审计](composition-x3-x4-audit-20261004.json)验证原始快照指纹、正式提交、帮助与后续作答 / correction / 重算的顺序、同一披露的精确谱系，以及回放允许、拒绝、恢复的独立记录。正式[组合评估](composition-x3-x4-assessment-20261004.json)与原始运行汇总分开保存。

本轮没有修改生产机制，组合场景复用现有依赖解析、Action 和 ReplayRuntime。新增原始字节读取 / provider 输入计数仅用于证据捕获；不存在新的语义分类器。当前单进程受控 fixture 不提供生产治理授权、分布式撤权、真实 provider 数据外发或真实 UI 的保证；回放拒绝也不意味着内部从未读取任何仍被授权的记录。这个区别在原始材料单项拒绝分支明确保留。

总体完整验收从 7/17 增至 9/17，新增 X3、X4；Architecture Assumption 分类不变。A2 DENIED、E1/E2/F2 及 X1/X2 的未决均保留，Gate E/F 仍 OPEN。下一步进入 X5：诊断结束转教学、实际讲解，以及新的独立作答机会；随后还需 A1 与现有未决项的设计收口。当前不自动重开任何已结束模型批次。
