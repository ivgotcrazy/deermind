# DeerMind 系统设计文档入口

> **版本**：v0.2<br>
> **文档性质**：文档导航与使用说明<br>
> **状态**：当前设计与工作入口；历史验证按原基线解释<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：本轮模型及修改范围由用户确认；文档检查不代表模型效果或 Gate 通过<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-19<br>
> **修订说明**：更新系统入口的合同状态；同步现行交叉引用和导航。逐文件变更见[修订记录 §10](../concept-design/DeerMind_Learning_Model_Reassessment.md#10-默认四维评价框架的正式修订记录)。

---

当前设计合同为以下七份 v1.2，承接[概念设计与新模型](../concept-design/README.md)。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录的是旧 v1.0 的 Gate E/F 与 Build 准入依据；历史结论未重写，新模型未因此取得实证验证。[System Design Roadmap](DeerMind_System_Design_Roadmap_v0.8.md)的阶段规划保持。

**当前工作（2026-10-19）：Phase 4 进行中；Task Claim 单一状态及默认四维修订已传导设计合同，内容包和评测资产尚待迁移，G4 未通过。** 当前入口见 [MVP 文档](../mvp/README.md)。本轮 Phase 3 已按 G3-20261015-01 阶段性通过，批准输入保持原样；这次模型修订不改写该历史记录。

归档 MVP 基线中的[基础领域演化选择](../mvp/archive/DeerMind_MVP_Definition_v0.1.md#7-模型管理与运行可观察性)及其后续质量责任保留供新文档核对承接；明确确认的决定不因归档自动撤销。此次已同步修订领域/产品 owner、具体问题溯源、Claim 参照、版本依赖与发布路由；历史实验输入与结论保持，也不另开 Evolution Spike。

Architecture Validation Build 已收口，此前 G2 准入与能力分期见[统一 Validation Report §9](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md#9-build退出评审与能力分期决定)。原 R2 仍为 6/6 段完成路径、14/24 轮内容可用、EVAL-02/04 未满足及原条件 HOLD；R3/R4 失败不改写。Build 退出时 9 项定向机制及回归检查通过，未新增模型调用。R5 未启动，仍是后续工程候选输入，不再作为 Build 退出前置要求。

Build输出统一位于`build/`；[Build Plan v0.4](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md)保留原条件并在§9记录新准入范围，[Validation Report v0.3](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md)是唯一结果入口。默认服务仍使用R2语义、非思考配置与确定性总评汇总，最低纠错检查不表示交付了自动错误发现或专门维护接口。人工复测使用仓库根目录`deermind.cmd start`，参数见[实现README](../../src/architecture_validation/README.md)。

- [DeerMind_System_Design_v1.3](DeerMind_System_Design_v1.3.md)
- [DeerMind_Runtime_Event_Architecture_v1.3](DeerMind_Runtime_Event_Architecture_v1.3.md)
- [DeerMind_AI_Reasoning_Runtime_Design_v1.3](DeerMind_AI_Reasoning_Runtime_Design_v1.3.md)
- [DeerMind_State_Dependency_Architecture_v1.3](DeerMind_State_Dependency_Architecture_v1.3.md)
- [DeerMind_Interaction_Decision_Runtime_Design_v1.3](DeerMind_Interaction_Decision_Runtime_Design_v1.3.md)
- [DeerMind_Semantic_Version_Replay_Migration_Design_v1.3](DeerMind_Semantic_Version_Replay_Migration_Design_v1.3.md)
- [DeerMind_Evolution_Governance_Runtime_Design_v1.3](DeerMind_Evolution_Governance_Runtime_Design_v1.3.md)

`doc/` 当前文档对同一交付物保留最新工作版本，日常历史由 Git/GitHub 追溯。按本轮明确要求，`doc/mvp/archive/` 额外保留此次框架重建前的四份文档供参考，不作为新文档基线。`src/spike/` 允许保留多版本文档、代码快照和实验资料；校验所需的历史字节与索引继续保存在该目录。

[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)是唯一 Spike 实验结论入口。`spike/archive/` 保留不同过程文档各自的最新版本；Cross-Cutting Coverage Review 保留其历史审查范围，不替代本次 Phase 6 评审。
