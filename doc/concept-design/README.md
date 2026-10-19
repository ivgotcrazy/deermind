# DeerMind 概念设计入口

> **版本**：v0.1<br>
> **文档性质**：文档导航与使用说明<br>
> **状态**：当前设计与工作入口；历史验证按原基线解释<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：本轮模型及修改范围由用户确认；文档检查不代表模型效果或 Gate 通过<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-19<br>
> **修订说明**：ProblemTemplate / ProblemScope 改为 TaskTemplate / TaskScope，统一任务术语；语义正文与例子同步；更新现行文档引用及导航。逐文件变更见[修订记录 §9](DeerMind_Learning_Model_Reassessment.md#9-task-claim-单一能力状态的正式修订记录)。

当前设计承接领域与课程空间分离，并纳入 2026-10-19 的 TaskTemplate 与 Task Claim 单一能力状态修订。**Domain Space 定义问题、方法与知识；Learning Space 定义材料、范围与目标；Evaluation 维护个人能力认识。** 核心架构仍由 Domain、Evaluation、Interaction、Evolution 四个 Space 构成。

| 文档 | 负责内容 |
| --- | --- |
| [Concept Architecture v1.3](DeerMind_Concept_Architecture_v1.3.md) | 整体架构、跨层归属、运行闭环与不变量 |
| [Domain Space Design v1.1](DeerMind_Domain_Space_Design_v1.1.md) | TaskTemplate、SolutionTemplate、KnowledgeComponent；结构关系、递归方法、知识依据与现实示例 |
| [Learning Space Design v1.1](DeerMind_Learning_Space_Design_v1.1.md) | LearningMaterial、LearningTarget、材料映射、定义与绑定、版本及权限 |
| [Evaluation Space Design v1.3](DeerMind_Evaluation_Space_Design_v1.3.md) | 条件性能力命题、Evidence、Belief 与目标达成评估 |
| [Interaction Space Design v1.3](DeerMind_Interaction_Space_Design_v1.3.md) | Observation、当前状态、目标绑定、实际帮助与行动决策 |
| [Evolution Space Design v1.3](DeerMind_Evolution_Space_Design_v1.3.md) | 模型失配、候选修订、验证与分属各 owner 的受治理变更 |

建议先读 Domain §2–6 和 Learning Space §2–6，查看对象如何映射到数学及 Kubernetes 示例，再回到概念总览核对全系统关系。规范对象图不单列运行时实例；具体问题、方法应用与实际表现的来源和版本仍由运行合同承接。

本轮同时更新 [AI-Native Principles v0.4](../top/DeerMind_AI_Native_Architecture_Principles_v0.4.md) 与[七份 System Design v1.2](../system-design/README.md)：产品与领域的写入责任分别检查；运行时分开解析目标、材料映射与 Domain 版本；具体问题保留参数及呈现来源；参考方法不充当实际执行证据；目标变化与领域、Claim 变化采用不同失效路径。

当前确认的是语义结构与责任合同。模板粒度、KC 划分、映射和生成质量、教学及检测收益仍是需检验的假设。旧 Spike/Build 记录按原基线保留，本轮未迁移实现、未运行新模型实验，也未产生 G3/G4/G5 通过结论。下一阶段工作仍按 [Development Roadmap](../top/DeerMind_Development_Roadmap_v0.4.md) 进行：Phase 3 已按 G3-20261015-01 阶段性通过，当前在 Phase 4 准备实际领域与产品资产，之后由 Phase 5 实现并验证。本轮语义修订需先传导内容包和评测参考，不另改历史 Gate。

[Reassessment](DeerMind_Learning_Model_Reassessment.md) 保留分析过程；其早期显式能力及问题族候选已被后续讨论替代，当前结论、逐文件变更及迁移边界见 §9；§1–8 为历史分析。正式文档目录只保留当前版本；原概念及系统合同可从 [Git 基线 eb7800b](https://github.com/ivgotcrazy/deermind/tree/eb7800b10da58bf3ee3ed4cbb27a3d484ebc1b94/doc) 查阅。历史报告链接仍指向当时版本，不以新设计替换旧实验输入。
