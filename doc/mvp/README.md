# MVP 文档框架与交付入口

> **文档性质**：MVP 文档导航与阶段交付入口<br>
> **状态**：Phase 3 已形成 G3 待确认稿；作者审查建议通过，待用户整体范围确认；Phase 4/5 仍为大纲<br>
> **维护责任**：Codex 负责本轮整理与一致性检查<br>
> **写作规范**：[设计文档规范 v1.0（维护修订）](../top/DeerMind_Design_Document_Standard_v1.0.md)；[MVP 共同规则](MVP_Governance.md)<br>
> **版本与评审**：工作修订由 Git 追溯；准确基线与结论见 [Gate 记录](MVP_Gate_Reviews.md)<br>
> **更新日期**：2026-10-11

---

Phase 3 三份正文已形成可供 G3 整体确认的版本：产品定义说明价值、范围及可行性前提，需求规格展开三端业务，验证方案规定质量与后续证据责任。作者审查及准确输入见 [G3 记录](MVP_Gate_Reviews.md#2-g3--mvp-definition)。当前建议进入 Phase 4，用户尚未作出本轮整体范围确认，不将局部选择或作者检查冒充 G3 通过。

现有四份 MVP 文档保存在 [archive](archive/README.md)，供历史核对。明确确认的约束不因归档失效；具体承接仍须逐项核对，不能自动沿用旧版的“已冻结”状态。现有[原型](../../src/mvp_prototype/README.md)保留作参考，本轮不修改产品交互或实现。

## 1. 阶段对应

目录编号对应 [Development Roadmap](../top/DeerMind_Development_Roadmap_v0.3.md) 的项目阶段，不对应 System Design Roadmap 内部阶段。阶段目标与 Gate 含义保持。

| 目录与阶段 | 要回答的问题 | 阶段交接 |
| --- | --- | --- |
| `phase-3-definition/` · Phase 3 MVP Definition | 为谁解决什么问题，具体功能、业务对象和规则是什么，如何验收？ | G3：无需原型即可理解三端核心业务，足以支撑产品方案与领域准备 |
| `phase-4-product-and-domain-foundation/` · Phase 4 Product & Domain Foundation | 如何组织操作与反馈，依靠哪些实际领域内容、授权规则和评测参考？ | G4：流程可走查，实际资产及交换合同可交接，工程无需补定核心产品或领域含义 |
| `phase-5-engineering/` · Phase 5 MVP Engineering | 如何分步实现、验证、运行并交付完整 MVP？ | G5：真实核心价值链可用，软件、运行工具与证据可复现，可进入 Internal Alpha |

Phase 6 Internal Alpha & Evaluation、Phase 7 Controlled Pilot 是后续独立阶段。Phase 5 可分增量实施，局部增量不代替完整 MVP，也不新增 Roadmap 阶段。已关闭的架构 Spike、Build 和系统设计基线不因本次文档整理重开。

## 2. 交付物导航

保留十份主体文档，增加两份跨阶段共同文件；各阶段协同完善，按输入依赖交接，不为每轮讨论或实施步骤另建文档。

| 阶段 | 文档 | 主要职责 |
| --- | --- | --- |
| 共同 | [文档共同管理规则](MVP_Governance.md) | 信息归属、决定与约束、待决与风险、基线变更、公共术语及编号 |
| 共同 | [Gate 评审记录](MVP_Gate_Reviews.md) | 独立记录 G3/G4/G5 的对象版本、证据、遗留责任和结论 |
| Phase 3 | [产品定义](phase-3-definition/MVP_Definition.md) | 证据索引、需求决策表、价值、范围和可行性前提 |
| Phase 3 | [需求与验收规格](phase-3-definition/MVP_Requirements_and_Acceptance.md) | 产品对象、三端功能与业务规则、AI 边界、验收场景及唯一追溯主索引 |
| Phase 3 | [验证方案](phase-3-definition/MVP_Validation_Plan.md) | 验证责任地图、指标与校准、样本、有限执行和结论解释 |
| Phase 4 | [产品与交互设计](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md) | 活动、用户和运营流程、页面状态及原型 |
| Phase 4 | [领域与内容基础](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md) | 实际领域与内容包、教学评价依据、来源映射、质量规则及交换合同 |
| Phase 4 | [数据与权限设计](phase-4-product-and-domain-foundation/MVP_Data_and_Authority_Design.md) | 授权模型、数据用途与生命周期，细化已定范围 |
| Phase 4 | [评测资产规格与清单](phase-4-product-and-domain-foundation/MVP_Evaluation_Assets_Specification.md) | 确定性、语义及组合验证的实际案例、参考和版本 |
| Phase 5 | [工程设计](phase-5-engineering/MVP_Engineering_Design.md) | 技术取舍、运行与接口合同、AI 实现及维护 |
| Phase 5 | [分步实施与验证计划](phase-5-engineering/MVP_Incremental_Delivery_Plan.md) | 增量目标、依赖、工作项、资源与验证节点 |
| Phase 5 | [交付与运行交接](phase-5-engineering/MVP_Delivery_and_Handover.md) | 可运行产物、操作说明、工程结果与 G5 评审输入 |

文档之外，Phase 4 须有实际原型、领域内容、评测材料和审查记录；Phase 5 须有软件、配置与操作工具、执行证据。资产由对应文档索引，不以空清单代替完成。

Phase 3 承担产品范围、业务行为和验收承诺，Phase 4 承担具体产品方案及基础资产，Phase 5 承担工程实现。各文档的输入、输出、直接接收者和接收条件在文档开头与完成条件中明确；共同边界见 [Governance §1](MVP_Governance.md#1-信息归属与冲突处理)。Phase 4 的可检查材料不依赖 Phase 5 正式导入器才能成立，Phase 5 必须验证实际导入和执行。

## 3. 使用与后续工作

本次重点阅读[产品定义 §5–§7](phase-3-definition/MVP_Definition.md#5-完整-mvp-范围与能力边界)和[需求规格 §3](phase-3-definition/MVP_Requirements_and_Acceptance.md#3-三端功能与业务流程)，分别检查完整范围及三端如何工作；[验证方案](phase-3-definition/MVP_Validation_Plan.md)规定怎样分阶段取得质量和价值证据。Phase 4/5 仍为大纲，实际活动组织、页面与技术方案尚未交付，不把旧原型或章节提示当作新方案。

现行模型依据为 [正式概念与系统设计入口](../concept-design/README.md)，DEC-007 替代早期独立能力本体候选。DEC-011–016 已明确目标权限、已有空间更新、章节统计、必要基础回补及按需产品内介入；OPEN-002–004 保留实际教材、投入和服务条件核验，责任与不阻塞定义的理由见 Definition §7。模型有效性、内容质量和实际投入继续凭后续资产及测量判断。

[文档架构评审](MVP_Document_Architecture_Review.md) 保留调整依据，不作为第十一份主体交付物或新 Gate。G3 确认后进入 Phase 4，先用典型章节讲解贯通活动和共性能力设计，再展开其他学习活动及家长、管理员衔接，同步准备实际领域、权限和评测材料；不是只实现章节讲解，也不重新增加一轮无界限的准确率试验。

[学习模型复核稿](../concept-design/DeerMind_Learning_Model_Reassessment.md) 保留探索过程，当前结论与替代关系见其 §8。正式模型以 Domain Space v1.0、Learning Space v1.0、Concept / Evaluation / Interaction / Evolution v1.2 和 System Design v1.1 为准；实现与历史实验尚未按新模型迁移。
