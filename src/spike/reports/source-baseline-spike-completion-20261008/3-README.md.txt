# Spike 文档目录

最新进展见 [算术抽取观察者立场修订结果](DeerMind_Observer_Arithmetic_Fix_Result_v0.1.md)：21 次真实调用、约 74 秒、无网络失败。4 个原候选的特定算术误拒未再出现；映射审查仍漏掉 1 个注入反例，另有 1 个输出格式失败。本轮已收口为局部改善，不追加调参；下一项处理 T03 最终结果判断遗漏，并限定检查一个实际定位提示会话。

本目录集中存放综合 Spike 方案、实验合同、证据驱动的修订及收口决定。总体设计、运行时专项、路线图和跨专项审查保留在上级目录。

阶段范围依据为 [问题定性与可行性决定 v0.1](DeerMind_Spike_Issue_Disposition_and_Feasibility_Decision_v0.1.md)：逐项区分核心机制、简单工程修复、后续质量优化和尚未验证的能力，记录本次修复与实际验证结果。当前可行性工作已形成有限结论，转入受限单任务原型工程验证；不再为补齐旧批次或消除全部语义误判而停留。

旧完整合同的 9/17、A2 DENIED、原型 NO_GO 和 Gate E/F OPEN 保留，不等同于当前阶段进度。旧 [退出清单与预算](DeerMind_Spike_Exit_Checklist_and_Budget_v0.1.md) 与 [退出验证准备](DeerMind_Spike_Exit_Preparation_v0.1.md)属于已执行批次的历史依据，不再作为当前运行计划。

## 文档

- [算术抽取观察者立场修订方案](DeerMind_Observer_Arithmetic_Fix_v0.1.md)
- [算术抽取观察者立场修订结果](DeerMind_Observer_Arithmetic_Fix_Result_v0.1.md)
- [问题定性与可行性决定 v0.1](DeerMind_Spike_Issue_Disposition_and_Feasibility_Decision_v0.1.md)
- [网络重试结果 v0.1](DeerMind_Network_Retry_Result_v0.1.md)
- [原冻结方案终局评估 v0.1](DeerMind_Spike_Terminal_Assessment_v0.1.md)
- [DeerMind_Arithmetic_Expression_Contract_v0.1.md](DeerMind_Arithmetic_Expression_Contract_v0.1.md)
- [DeerMind_Consolidated_Architecture_Spike_Design_v0.1.md](DeerMind_Consolidated_Architecture_Spike_Design_v0.1.md)
- [DeerMind_Downstream_Admission_Policy_Responsibility_Revision_v0.1.md](DeerMind_Downstream_Admission_Policy_Responsibility_Revision_v0.1.md)
- [DeerMind_Observation_Validation_Profile_v0.1.md](DeerMind_Observation_Validation_Profile_v0.1.md)
- [DeerMind_Observation_Validation_Turn_Closure_Revision_v0.1.md](DeerMind_Observation_Validation_Turn_Closure_Revision_v0.1.md)
- [DeerMind_Policy_Review_Disposition_Revision_v0.1.md](DeerMind_Policy_Review_Disposition_Revision_v0.1.md)
- [DeerMind_Policy_Semantic_Utility_Contract_v0.1.md](DeerMind_Policy_Semantic_Utility_Contract_v0.1.md)
- [DeerMind_Semantic_Validation_and_Spike_Exit_Decision_v0.1.md](DeerMind_Semantic_Validation_and_Spike_Exit_Decision_v0.1.md)
- [DeerMind_Spike_Closeout_Decision_Draft_v0.1.md](DeerMind_Spike_Closeout_Decision_Draft_v0.1.md)
- [DeerMind_Spike_Closeout_Decision_v0.2.md](DeerMind_Spike_Closeout_Decision_v0.2.md)
- [DeerMind_Validation_and_Interaction_Closure_Revision_v0.1.md](DeerMind_Validation_and_Interaction_Closure_Revision_v0.1.md)

## 实现与历史证据

字段引用修复的当前实现及本地验证见 [Policy 字段引用实现 v0.1](DeerMind_Policy_Field_Reference_Implementation_v0.1.md)。

代码、Protocol、运行记录及验证报告继续位于 [src/spike](../../../src/spike/README.md)。历史实验结论不随新接口和阶段目标的修订而重写。

历史 manifest 和协议中的路径按冻结时的位置保留。需要核对旧路径和 SHA256 时，使用[迁移映射](../../../src/spike/reports/spike-document-layout-20261007.json)所列的迁移前原文副本；活跃文档链接和验证台账使用新位置。
