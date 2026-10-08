# DeerMind 系统设计文档入口

当前实现合同为以下七份 v1.0。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录冻结依据、Gate E/F 与后续 Build 范围；[System Design Roadmap](DeerMind_System_Design_Roadmap_v0.6.md)保持阶段规划。

当前工作处于Development Phase 2。Build输出统一放在 `build/`；[Build Plan v0.4](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md)保留原验收标准、R1安排及后续有限合同边界检查。[Build Validation Report v0.3](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md)整合首次B2–B5、R1和最新两轮检查：格式实现问题已修复，补测两轮均完成，含完整讲解后的Evaluation/Policy；已知语义误放单独保留，G2保持HOLD，正式复验未启动。人工复测可用仓库根目录 `deermind.cmd start`，参数见[实现README](../../src/architecture_validation/README.md)。当前不进入MVP Definition；发现实现缺陷即修复并复验，涉及设计取舍才进入讨论，正式验收条件不降低。

- [DeerMind_System_Design_v1.0](DeerMind_System_Design_v1.0.md)
- [DeerMind_Runtime_Event_Architecture_v1.0](DeerMind_Runtime_Event_Architecture_v1.0.md)
- [DeerMind_AI_Reasoning_Runtime_Design_v1.0](DeerMind_AI_Reasoning_Runtime_Design_v1.0.md)
- [DeerMind_State_Dependency_Architecture_v1.0](DeerMind_State_Dependency_Architecture_v1.0.md)
- [DeerMind_Interaction_Decision_Runtime_Design_v1.0](DeerMind_Interaction_Decision_Runtime_Design_v1.0.md)
- [DeerMind_Semantic_Version_Replay_Migration_Design_v1.0](DeerMind_Semantic_Version_Replay_Migration_Design_v1.0.md)
- [DeerMind_Evolution_Governance_Runtime_Design_v1.0](DeerMind_Evolution_Governance_Runtime_Design_v1.0.md)

`doc/` 及其子目录对同一文档只保留最新版本，旧版本由 Git/GitHub 历史追溯。`src/spike/` 允许保留多版本文档、代码快照和实验资料；校验所需的历史字节与索引继续保存在该目录。

[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)是唯一 Spike 实验结论入口。`spike/archive/` 保留不同过程文档各自的最新版本；Cross-Cutting Coverage Review 保留其历史审查范围，不替代本次 Phase 6 评审。
