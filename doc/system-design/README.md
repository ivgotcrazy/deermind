# DeerMind 系统设计文档入口

当前实现合同为以下七份 v1.0。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录冻结依据、Gate E/F 与后续 Build 范围；[System Design Roadmap](DeerMind_System_Design_Roadmap_v0.6.md)保持阶段规划。

Architecture Validation Build已收口。当前项目G2 PASS，限定准入Development Phase 3 MVP Definition；语义质量与完整维护能力按明确责任分期，见[统一Validation Report §9](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md#9-build退出评审与能力分期决定)。原R2完整测量仍为6/6段完成预定路径、14/24轮内容可用、EVAL-02/04未满足及原条件HOLD；R3/R4失败不改写。本次9项定向机制及回归检查通过，无新增模型调用。R5未启动，转为后续工程候选方案；不将其作为Build退出的前置要求。

Build输出统一位于`build/`；[Build Plan v0.4](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md)保留原条件并在§9记录新准入范围，[Validation Report v0.3](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md)是唯一结果入口。默认服务仍使用R2语义、非思考配置与确定性总评汇总，最低纠错检查不表示交付了自动错误发现或专门维护接口。人工复测使用仓库根目录`deermind.cmd start`，参数见[实现README](../../src/architecture_validation/README.md)。

- [DeerMind_System_Design_v1.0](DeerMind_System_Design_v1.0.md)
- [DeerMind_Runtime_Event_Architecture_v1.0](DeerMind_Runtime_Event_Architecture_v1.0.md)
- [DeerMind_AI_Reasoning_Runtime_Design_v1.0](DeerMind_AI_Reasoning_Runtime_Design_v1.0.md)
- [DeerMind_State_Dependency_Architecture_v1.0](DeerMind_State_Dependency_Architecture_v1.0.md)
- [DeerMind_Interaction_Decision_Runtime_Design_v1.0](DeerMind_Interaction_Decision_Runtime_Design_v1.0.md)
- [DeerMind_Semantic_Version_Replay_Migration_Design_v1.0](DeerMind_Semantic_Version_Replay_Migration_Design_v1.0.md)
- [DeerMind_Evolution_Governance_Runtime_Design_v1.0](DeerMind_Evolution_Governance_Runtime_Design_v1.0.md)

`doc/` 及其子目录对同一文档只保留最新版本，旧版本由 Git/GitHub 历史追溯。`src/spike/` 允许保留多版本文档、代码快照和实验资料；校验所需的历史字节与索引继续保存在该目录。

[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)是唯一 Spike 实验结论入口。`spike/archive/` 保留不同过程文档各自的最新版本；Cross-Cutting Coverage Review 保留其历史审查范围，不替代本次 Phase 6 评审。
