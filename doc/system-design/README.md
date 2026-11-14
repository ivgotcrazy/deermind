# DeerMind 系统设计文档入口

> **版本**：v0.32<br>
> **文档性质**：文档导航与使用说明<br>
> **状态**：总体架构问题清单待审；暂停展开Operation和接口字段，未编码<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：主流程职责、恢复保障及三项权限边界已确认；具体实现、其余质量目标及部署仍待讨论<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-14<br>
> **修订说明**：v0.31 → v0.32，同步M1不单独接入OCR及教材Agent对话修正边界，保留具体模型与验收待定项<br>

---

以下七份v1.4为既有系统设计基线，承接[概念设计入口](../concept-design/README.md)；其中旧模型摘要尚未全部按M1迁移，不是可直接照搬的新M1工程规格。当前Domain合同为[v1.5](../concept-design/DeerMind_Domain_Space_Design_v1.5.md)，Evaluation为[v1.9](../concept-design/DeerMind_Evaluation_Space_Design_v1.9.md)，具体产品规则以[M1 PRD](../mvp/m1/PRD.md)及设计规格为准，差异由M1-OPEN-04登记。[Phase 6 证据评审](DeerMind_System_Design_Evidence_Review_v1.0.md)记录的是旧 v1.0 的 Gate E/F 与 Build 准入依据；历史结论未重写，新模型未因此取得实证验证。[System Design Roadmap](DeerMind_System_Design_Roadmap_v0.11.md)的阶段规划保持。

**当前工作（2026-11-14）：M1总体架构问题清单待审，未编码。** 现行入口为[M1工程设计](../mvp/m1/engineering/README.md)，按[系统设计写作规范](../top/DeerMind_System_Design_Writing_Standard.md)组织九份设计。先审阅[总体问题清单](../mvp/m1/engineering/System_Design.md#72-总体架构问题清单)，主流程主要边界已确认，当前审阅总体收口结论及剩余选择；已有Operation草案保留，暂不深入字段。WebSocket及Temporal＋Pydantic AI＋NATS JetStream＋PostgreSQL已确认，生产沿用Kubernetes；组件选型见[登记§44](../mvp/DECISIONS.md#44-m1执行框架与事件组件选型)。Operation上下文与记忆职责已确认，见[登记§51](../mvp/DECISIONS.md#51-operation负责上下文与记忆)；入口路由方案已确认，见[登记§52](../mvp/DECISIONS.md#52-m1入口路由方案)。具体接线、取材与摘要机制、交接实现及部署布局仍待审，三项恢复目标已确认，见[登记§53](../mvp/DECISIONS.md#53-m1三项恢复目标)，四点保障方案已确认，见[登记§54](../mvp/DECISIONS.md#54-m1四点恢复保障方案)，资源不足按[登记§55](../mvp/DECISIONS.md#55-m1资源不足的简化处理)简化为直接报错并取消业务优先级，三项权限边界见[登记§56](../mvp/DECISIONS.md#56-m1读取工具与越权边界)，模型外发按[登记§57](../mvp/DECISIONS.md#57-m1模型外发的简化边界)由Operation负责内容、底座限制模型服务及保护凭据，已按[登记§58](../mvp/DECISIONS.md#58-m1可用性与备份恢复边界)确认短暂停机及备份恢复边界，日志与事件观测按[登记§59](../mvp/DECISIONS.md#59-m1日志与事件的可观测边界)确认，消息／事件分存及[总体收口检查](../mvp/m1/engineering/System_Design.md#722-总体收口检查2026-11-13)已完成文档同步，代码组织及Python＋FastAPI、Vue 3＋TypeScript＋Vite已确认；初期文件存储已定，模型API统一接入已确认，教材Agent解析与对话修正已确认不单独接入OCR，具体模型及量化验收安排仍待确认。旧M1草案见[归档](../mvp/archive/2026-11-11-before-swdd/README.md)，本目录旧设计均为历史参考；历史G3不等于新M1已通过架构或工程接收。

代码组织与前后端框架的确认范围见[登记§61](../mvp/DECISIONS.md#61-m1代码组织与前后端框架)：一个仓库、一套后端模块、API与Worker分别运行；前端一个工程两个入口。初期API与Worker按[登记§62](../mvp/DECISIONS.md#62-m1初期文件存储与同节点部署)同节点共用local-path＋PVC，保留文件存储隔离；具体版本、挂载和其他部署配置待详细设计。模型API按[登记§63](../mvp/DECISIONS.md#63-m1模型api统一接入与agent配置)由AI底座统一接入，各类Agent可分别配置或共用模型；不自建推理平台。教材解析与对话修正按[登记§64](../mvp/DECISIONS.md#64-m1教材agent解析与对话修正)由Agent调用多模态模型API完成，M1不单独接入OCR。

归档 MVP 基线中的[基础领域演化选择](../mvp/archive/2026-11-02-before-m1-prd/archive/DeerMind_MVP_Definition_v0.2.md#7-模型管理与运行可观察性)及其后续质量责任保留供新文档核对承接；明确确认的决定不因归档自动撤销。这些基线曾修订领域/产品owner、具体问题溯源、Claim参照、版本依赖与发布路由；当前M1的直接保存与应用、教材Agent及活动／评价合同须重新核对，不恢复旧审核发布流程；历史实验输入与结论保持，也不另开 Evolution Spike。

Architecture Validation Build 已收口，此前 G2 准入与能力分期见[统一 Validation Report §9](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md#9-build退出评审与能力分期决定)。原 R2 仍为 6/6 段完成路径、14/24 轮内容可用、EVAL-02/04 未满足及原条件 HOLD；R3/R4 失败不改写。Build 退出时 9 项定向机制及回归检查通过，未新增模型调用。R5 未启动，仍是后续工程候选输入，不再作为 Build 退出前置要求。

Build输出统一位于`build/`；[Build Plan v0.4](build/DeerMind_Architecture_Validation_Build_Plan_v0.4.md)保留原条件并在§9记录新准入范围，[Validation Report v0.3](build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md)是唯一结果入口。默认服务仍使用R2语义、非思考配置与确定性总评汇总，最低纠错检查不表示交付了自动错误发现或专门维护接口。人工复测使用仓库根目录`deermind.cmd start`，参数见[实现README](../../src/architecture_validation/README.md)。

- [DeerMind_System_Design_v1.4](DeerMind_System_Design_v1.4.md)
- [DeerMind_Runtime_Event_Architecture_v1.4](DeerMind_Runtime_Event_Architecture_v1.4.md)
- [DeerMind_AI_Reasoning_Runtime_Design_v1.4](DeerMind_AI_Reasoning_Runtime_Design_v1.4.md)
- [DeerMind_State_Dependency_Architecture_v1.4](DeerMind_State_Dependency_Architecture_v1.4.md)
- [DeerMind_Interaction_Decision_Runtime_Design_v1.4](DeerMind_Interaction_Decision_Runtime_Design_v1.4.md)
- [DeerMind_Semantic_Version_Replay_Migration_Design_v1.4](DeerMind_Semantic_Version_Replay_Migration_Design_v1.4.md)
- [DeerMind_Evolution_Governance_Runtime_Design_v1.4](DeerMind_Evolution_Governance_Runtime_Design_v1.4.md)

`doc/` 当前文档对同一交付物保留最新工作版本，日常历史由 Git/GitHub 追溯。按本轮明确要求，`doc/mvp/archive/` 额外保留此次框架重建前的四份文档供参考，不作为新文档基线。`src/spike/` 允许保留多版本文档、代码快照和实验资料；校验所需的历史字节与索引继续保存在该目录。

[统一 Spike Validation Report](spike/DeerMind_Architecture_Validation_Report_v0.1.md)是唯一 Spike 实验结论入口。`spike/archive/` 保留不同过程文档各自的最新版本；Cross-Cutting Coverage Review 保留其历史审查范围，不替代本次 Phase 6 评审。

**当前工程讨论。** 先沿[端到端主流程](../mvp/m1/engineering/System_Design.md#72-总体架构问题清单)确认模块交接、数据与事件、AI取材及结果返回。[九类非功能质量问题](../mvp/m1/engineering/System_Design.md#63-非功能质量属性待讨论清单)已登记，待框架清楚后讨论目标和保障方案。既定职责、选型和质量约束保留；本批仅改工程文档、导航和决定登记。
