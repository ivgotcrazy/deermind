# MVP 文档框架与交付入口

**当前状态：2026-10-11，领域模型复核的阶段性语义结论已纳入正式设计：Domain 定义问题模板、解法模板和 KC；Learning Space 定义材料、范围和目标；个人状态仍属 Evaluation。OPEN-006 的概念归属已明确，可恢复 Phase 3 内容评审；本轮没有 G3/G4/G5 通过结论。**

现有四份 MVP 文档保存在 [archive](archive/README.md)，供历史核对。明确确认的约束不因归档失效；具体承接仍须逐项核对，不能自动沿用旧版的“已冻结”状态。现有[原型](../../src/mvp_prototype/README.md)保留作参考，本轮不修改产品交互或实现。

## 1. 阶段对应

目录编号对应 [Development Roadmap](../top/DeerMind_Development_Roadmap_v0.3.md) 的项目阶段，不对应 System Design Roadmap 内部阶段。阶段目标与 Gate 含义保持。

| 目录与阶段 | 要回答的问题 | 阶段交接 |
| --- | --- | --- |
| `phase-3-definition/` · Phase 3 MVP Definition | 为谁解决什么问题，完整范围是什么，为什么值得做，如何判断结果？ | G3：定义足以支撑产品与领域基础 |
| `phase-4-product-and-domain-foundation/` · Phase 4 Product & Domain Foundation | 用户与运营者如何完成目标，需要哪些领域内容、数据权限与评测材料？ | G4：设计与实际基础资产足以支撑工程 |
| `phase-5-engineering/` · Phase 5 MVP Engineering | 如何分步实现、验证、运行并交付完整 MVP？ | G5：真实核心价值链可用，可进入 Internal Alpha |

Phase 6 Internal Alpha & Evaluation、Phase 7 Controlled Pilot 是后续独立阶段。Phase 5 可分增量实施，局部增量不代替完整 MVP，也不新增 Roadmap 阶段。已关闭的架构 Spike、Build 和系统设计基线不因本次文档整理重开。

## 2. 交付物导航

保留十份主体文档，增加两份跨阶段共同文件；各阶段协同完善，按输入依赖交接，不为每轮讨论或实施步骤另建文档。

| 阶段 | 文档 | 主要职责 |
| --- | --- | --- |
| 共同 | [文档共同管理规则](MVP_Governance.md) | 信息归属、决定与约束、待决与风险、基线变更、公共术语及编号 |
| 共同 | [Gate 评审记录](MVP_Gate_Reviews.md) | 独立记录 G3/G4/G5 的对象版本、证据、遗留责任和结论 |
| Phase 3 | [产品定义](phase-3-definition/MVP_Definition.md) | 证据索引、需求决策表、价值、范围和可行性前提 |
| Phase 3 | [需求与验收规格](phase-3-definition/MVP_Requirements_and_Acceptance.md) | 行为、AI 边界、验收场景及统一需求追溯主索引 |
| Phase 3 | [验证方案](phase-3-definition/MVP_Validation_Plan.md) | 验证责任地图、指标与校准、样本、有限执行和结论解释 |
| Phase 4 | [产品与交互设计](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md) | 活动、用户和运营流程、页面状态及原型 |
| Phase 4 | [领域与内容基础](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md) | 实际领域和内容包、来源映射、审查及维护 |
| Phase 4 | [数据与权限设计](phase-4-product-and-domain-foundation/MVP_Data_and_Authority_Design.md) | 授权模型、数据用途与生命周期，细化已定范围 |
| Phase 4 | [评测资产规格与清单](phase-4-product-and-domain-foundation/MVP_Evaluation_Assets_Specification.md) | 确定性、语义及组合验证的实际案例、参考和版本 |
| Phase 5 | [工程设计](phase-5-engineering/MVP_Engineering_Design.md) | 技术取舍、运行与接口合同、AI 实现及维护 |
| Phase 5 | [分步实施与验证计划](phase-5-engineering/MVP_Incremental_Delivery_Plan.md) | 增量目标、依赖、工作项、资源与验证节点 |
| Phase 5 | [交付与运行交接](phase-5-engineering/MVP_Delivery_and_Handover.md) | 可运行产物、操作说明、工程结果与 G5 评审输入 |

文档之外，Phase 4 须有实际原型、领域内容、评测材料和审查记录；Phase 5 须有软件、配置与操作工具、执行证据。资产由对应文档索引，不以空清单代替完成。

## 3. 使用与后续工作

当前已有[产品定义内容草案](phase-3-definition/MVP_Definition.md)和[主要决定、待决与风险记录](MVP_Governance.md)，另已形成[行为与验收草案](phase-3-definition/MVP_Requirements_and_Acceptance.md)和[验证方案首稿](phase-3-definition/MVP_Validation_Plan.md)；Phase 4/5 仍为大纲。活动划分和具体技术方案仍由后续依据推导，不把现有原型直接作为新需求。大纲采用通用的问题结构，同时显式覆盖适用的 AI、领域内容、数据与运营责任。章节提示的替换、状态和基线维护遵循[共同规则](MVP_Governance.md)；主体文档最后一章仅判断自身完成情况，整个阶段在独立 Gate 记录中评审。

当前依照 [正式概念与系统设计入口](../concept-design/README.md) 恢复 Phase 3，继续核对范围、成功标准与验证条件。DEC-007 替代早期独立能力本体候选；OPEN-001 等其他待决保留。领域实例、模板粒度和映射质量由 Phase 4 的实际资产及后续验证检验，不能用旧 Spike/Build 的机制证据代替。

[学习模型复核稿](../concept-design/DeerMind_Learning_Model_Reassessment.md) 保留探索过程，当前结论与替代关系见其 §8。正式模型以 Domain Space v1.0、Learning Space v1.0、Concept / Evaluation / Interaction / Evolution v1.2 和 System Design v1.1 为准；实现与历史实验尚未按新模型迁移。
