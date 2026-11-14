# DeerMind 概念设计入口

> **版本**：v0.11<br>
> **文档性质**：文档导航与使用说明<br>
> **状态**：本轮领域模型、原型及关联合同已修订，待用户审阅；真实服务与效果未验证<br>
> **维护责任**：Codex 维护与核对；用户决定重要模型与范围变更<br>
> **评审记录**：用户批准模型变更及完整实施；作者检查见MVP决定登记§68，不代表真实效果验收通过<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-14<br>
> **修订说明**：v0.10 → v0.11，同步新领域模型、现行文档版本、原型入口与检查边界；逐文件记录见MVP决定登记§68<br>

---

当前领域模型以Domain组织Task、Solution、KC及TaskInstance。Task明确认知责任，Solution直接关联多个KC；Task先导关系服务教学安排，题内参考解法保留来源。Task Claim仍绑定一个Task，按方法和四方面评价。M1具体采用见[PRD](../mvp/m1/PRD.md)与[本轮变更清单](../mvp/m1/design/Domain_Model_Revision_Checklist.md)。

| 文档 | 负责内容 |
| --- | --- |
| [Concept Architecture v1.6](DeerMind_Concept_Architecture_v1.6.md) | 整体架构、跨层归属、运行闭环与不变量 |
| [Domain Space Design v1.6](DeerMind_Domain_Space_Design_v1.6.md) | Task、Solution、KC、TaskInstance；多KC方法、Task先导、题内参考和d=v×t案例 |
| [Learning Space Design v1.4](DeerMind_Learning_Space_Design_v1.4.md) | LearningMaterial、LearningTarget、材料映射、定义与绑定、版本及权限 |
| [Evaluation Space Design v1.10](DeerMind_Evaluation_Space_Design_v1.10.md) | 条件性能力命题、Evidence、Belief 与目标达成评估 |
| [Interaction Space Design v1.6](DeerMind_Interaction_Space_Design_v1.6.md) | 既有空间职责基线；Observation及活动摘要待按M1迁移，不能强制新增Observation层 |
| [Evolution Space Design v1.6](DeerMind_Evolution_Space_Design_v1.6.md) | 模型失配、候选修订、验证与分属各 owner 的受治理变更 |

建议先读 Domain §2–6 和 Learning Space §2–6，用“理解d=v×t”核对任务、方法、知识与课程采用的关系，再回到概念总览核对全系统关系。TaskInstance及题内参考属于领域内容；学生作答和实际表现另由运行合同承接。

此前模型调整曾同步 [AI-Native Principles v0.7](../top/DeerMind_AI_Native_Architecture_Principles_v0.7.md) 与[七份既有 System Design](../system-design/README.md)：产品与领域的写入责任分别检查；运行时分开解析目标、材料映射与 Domain 版本；具体问题保留参数及呈现来源；参考方法不充当实际执行证据；目标变化与领域、Claim 变化采用不同失效路径。

当前确认的是语义结构与责任合同。Task粒度、KC 划分、映射和生成质量、教学及检测收益仍是需检验的假设。旧 Spike/Build 记录按原基线保留，本轮更新M1 mock原型，未运行真实模型实验，也未产生 G3/G4/G5 通过结论。下一阶段工作仍按 [Development Roadmap](../top/DeerMind_Development_Roadmap_v0.11.md) 进行：Phase 3 已按 G3-20261015-01 阶段性通过，2026-11-02 起按 M1–M3 分阶段定义、设计、实现和验证，当前先收敛 M1 的教材建模与教学核心闭环；历史 Phase 4 资产按当前范围复用。本轮语义修订需先传导内容包和评测参考，不另改历史 Gate。

[Reassessment](DeerMind_Learning_Model_Reassessment.md) 保留分析过程；其早期显式能力及问题族候选已被后续讨论替代，单Task多维的当前结论、逐文件变更及迁移边界见 §11；§1–10 保留历史分析和前次修订。当前导航指向采用版本，旧文件及验证引用保留原义；更早概念及系统合同可从 [Git 基线 eb7800b](https://github.com/ivgotcrazy/deermind/tree/eb7800b10da58bf3ee3ed4cbb27a3d484ebc1b94/doc) 查阅。历史报告链接仍指向当时版本，不以新设计替换旧实验输入。

**现行与历史的边界。** Domain v1.6、Evaluation v1.10是M1当前模型合同；本轮关联概念摘要已同步新Domain语义，历史系统基线仍按M1-OPEN-04核对，不自动取得相同成熟度。教材Agent对话、目标章节方法适用及学习机会的当前详细规定见[M1内容规格](../mvp/m1/design/Content_and_Model_Reference.md)。旧版文件作为历史基线保留，不批量改正文为“已废止”；当前导航不再把旧Domain／Evaluation版本作为新实现依据。
