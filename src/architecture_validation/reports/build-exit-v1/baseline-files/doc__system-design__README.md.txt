# DeerMind 系统设计文档入口

当前实现合同为以下七份 v1.0。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录冻结依据、Gate E/F 与后续 Build 范围；[System Design Roadmap](DeerMind_System_Design_Roadmap_v0.6.md)保持阶段规划。

当前工作处于Development Phase 2。Build输出统一放在`build/`；[Build Plan v0.4](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md)保留原验收条件和各批次边界，[Build Validation Report v0.3](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md)是统一结果入口。完整验收R2已结束：75项离线检查通过，6/6段完成预定路径，14/24轮内容可用，EVAL-01/03满足、02/04未满足，G2 HOLD。剩余缺口集中在缺失材料被误当反证、方法帮助跨题影响及错误Evidence传播；网络失败全部恢复、格式阻塞已修复。随后R3专项修复未准入新完整复验，实验语义Profile已撤回，默认恢复R2并保留确定性总评汇总修复；最终81项离线检查通过。随后R4固定输入的非思考/思考high对照亦已关闭：Evaluation标签5/10与7/10，生成目标1/4与0/4，两组均未达后续实验筛选条件；90项离线检查通过，默认非思考配置不变。当前不进入MVP Definition，R2/R3/R4均已关闭，不追加这些批次的模型调用。后续[Evaluation改造方案](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md#8-evaluation任务拆分与错误evidence更正方案)已完成，尚未实现或实测；先做30次计划逻辑请求的语义专项，满足条件后再接入单Claim编排与定向更正。人工复测使用仓库根目录`deermind.cmd start`，参数见[实现README](../../src/architecture_validation/README.md)。

- [DeerMind_System_Design_v1.0](DeerMind_System_Design_v1.0.md)
- [DeerMind_Runtime_Event_Architecture_v1.0](DeerMind_Runtime_Event_Architecture_v1.0.md)
- [DeerMind_AI_Reasoning_Runtime_Design_v1.0](DeerMind_AI_Reasoning_Runtime_Design_v1.0.md)
- [DeerMind_State_Dependency_Architecture_v1.0](DeerMind_State_Dependency_Architecture_v1.0.md)
- [DeerMind_Interaction_Decision_Runtime_Design_v1.0](DeerMind_Interaction_Decision_Runtime_Design_v1.0.md)
- [DeerMind_Semantic_Version_Replay_Migration_Design_v1.0](DeerMind_Semantic_Version_Replay_Migration_Design_v1.0.md)
- [DeerMind_Evolution_Governance_Runtime_Design_v1.0](DeerMind_Evolution_Governance_Runtime_Design_v1.0.md)

`doc/` 及其子目录对同一文档只保留最新版本，旧版本由 Git/GitHub 历史追溯。`src/spike/` 允许保留多版本文档、代码快照和实验资料；校验所需的历史字节与索引继续保存在该目录。

[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)是唯一 Spike 实验结论入口。`spike/archive/` 保留不同过程文档各自的最新版本；Cross-Cutting Coverage Review 保留其历史审查范围，不替代本次 Phase 6 评审。
