# Spike 文档目录

当前工作统一见 [Architecture Validation Report](DeerMind_Architecture_Validation_Report_v0.1.md)。项目仍处于总体 Phase 1 System Design，正在收口综合 Spike；原 Completion 尚未满足，Gate E/F OPEN。局部实验或单任务工程批次不构成阶段退出。W1–W5 计划及 17 项正式用例均由主报告统一维护。

本目录集中存放综合 Spike 方案、实验合同、证据驱动的修订及收口决定。总体设计、运行时专项、路线图和跨专项审查保留在上级目录。

阶段范围按上级两份路线图和综合 Spike 设计执行。下列过程文档保存原决定与实验上下文；其中与主报告阶段定位冲突的表述不再作为执行依据。最终归档在结论和证据迁移完整后进行。

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
