# MVP 文档框架与交付入口

> **版本**：v0.3<br>
> **文档性质**：MVP 文档导航与阶段交付入口<br>
> **状态**：2026-10-15 G3 阶段性通过；Phase 4 设计、原型与内容准备进行中，G4 未通过；Phase 5 仍为大纲<br>
> **维护责任**：Codex 负责本轮整理与一致性检查<br>
> **版本与评审**：工作修订由 Git 追溯；准确基线与结论见 [Gate 记录](MVP_Gate_Reviews.md)<br>
> **写作规范**：[设计文档规范 v1.1](../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-20<br>
> **修订说明**：更新 MVP 工作入口；同步相关合同与现行引用。逐文件变更见[修订记录 §11](../concept-design/DeerMind_Learning_Model_Reassessment.md#11-单模板多维-claim-的正式修订记录)。

---

用户已于 2026-10-15 确认 Phase 3 阶段性审阅通过，批准基线为 [G3-20261015-01](MVP_Gate_Reviews.md#27-g3-阶段性审阅通过与-phase-4-交接)。Phase 4 依据该范围开展产品交互、实际内容、数据权限和评测准备；模型适用性疑问按 DEC-017、RISK-008 在实际工作中检验。

当前四份 Phase 4 文档已有工作稿。**本轮审阅[三端任务与信息架构](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#2-角色旅程与整体结构)及[连续学习对话入口](http://127.0.0.1:5178/structure.html?role=student#/chapter?chapter=fractions)**：用户基本认可整体方向，要求继续打磨内容与交互。首页已补齐学习摘要与直接输入；学习活动采用连续对话，图示、练习、检测和结果内嵌。预写情境保留对照，新增独立的真实 DeepSeek 模式供成人体验文字追问、动态出题及本次反馈，不更新章节状态。首条跨角色过程与合成目录仍可操作，完整功能迁移待继续。[原局部工具](http://127.0.0.1:5178/phase4.html)保留参考，启动和限制见[原型说明](../../src/mvp_prototype/README.md)。校内实际教材的领域与参考候选已准备，正式审核、校外材料和完整交接仍待完成；G4 尚未通过。

[归档](archive/README.md)和旧原型保留作历史参考，不自动成为本轮设计答案。旧原型中的整卷、旧统计和仅错题口径不属于当前范围，新入口与旧入口分开，避免混用。

当前设计承接 DEC-022 的 Task-only、DEC-024 的默认四维及 DEC-025 的单模板多维组织：四维是同一任务 Claim 内部方面，Belief 分方面维护。规范见 [Evaluation §3.1–4](../concept-design/DeerMind_Evaluation_Space_Design_v1.5.md#31-learner-state-model定义-deermind-可以相信什么)；实际领域、案例及实现迁移仍由 OPEN-010 承接，当前原型不冒充已完成新状态接入。

## 1. 阶段对应

目录编号对应 [Development Roadmap](../top/DeerMind_Development_Roadmap_v0.6.md) 的项目阶段，不对应 System Design Roadmap 内部阶段。阶段目标与 Gate 含义保持。

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

Phase 3 已批准的产品承诺由三份正文维护；Phase 4 的具体方案见[产品与交互设计](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md)，其余三份文档分别负责内容、权限与实际案例。交互工作已将任务与信息架构落实到首轮三端低保真稿；接下来审阅实际过程，按同一结构承接其余关键任务并补齐大量记录场景，不继续在旧导航中堆加演示页面。既有完整 MVP 范围保持，不缩减为单一活动。

本阶段按以下工作次序推进，存在依赖的部分先满足输入，能够独立准备的内容同时进行：

| 工作项 | 具体交付 | 当前状态与下一步 |
| --- | --- | --- |
| P4-01 产品结构与典型活动 | 三端任务与结构、ACT/FLOW/UI 合同及可运行走查 | 整体方向获用户基本认可；学生首页与连续学习对话完成本轮优化，等待细节审阅；首条跨角色过程和目录可操作，其余关键任务迁移与真实任务走查待完成 |
| P4-02 数据与权限 | AUTH-001、生命周期、关系失效和外部处理路径 | 首稿已形成；具体服务与适用条件仍待 OPEN-004 核实 |
| P4-03 实际内容与领域准备 | 两套材料的首批章节、对象与映射、目标、判断参考及维护记录 | 校内“分数的应用”的定义、映射、目标、51 条逐题参考与 8 幅关系图可在后台查看；审核与使用条件待核，校外材料后补 |
| P4-04 评测材料与联合交接 | CASE、参考、版本、资产审查和 G4 输入 | 四十八个交互案例、十二个语义参考及十二组权限允许／拒绝材料已编制；合同与内容复核、正式留出材料及完整维护影响仍待完成 |

这些是 Phase 4 内部工作项，不是新 Roadmap 阶段。只在出现新的产品取舍或需要材料、授权时请用户介入；已经明确的要求直接承接。

可以先按下列图示建立整体认识，再阅读所在章节的规范描述和验收条件。图是正文的对应视图，不是另一套精简需求或正式界面方案。

查验具体规则时，可直接阅读[行为验收 §6](phase-3-definition/MVP_Requirements_and_Acceptance.md#6-行为验收场景)：23 组场景分别列出前置情境和预期结果；质量目标见[指标目标 §2.1](phase-3-definition/MVP_Validation_Plan.md#21-指标目标)，计算条件、限制与准备责任见[测量口径 §2.2](phase-3-definition/MVP_Validation_Plan.md#22-测量口径与准备)。这些是尚待执行的要求，不是验收结果。

| 阅读问题 | 图示及所在位置 |
| --- | --- |
| 学生、家长和管理员各做什么 | [Definition §2](phase-3-definition/MVP_Definition.md#2-用户角色与使用情境)，图 DEF-01 |
| 主动求助和系统建议如何形成后续学习 | [Definition §5](phase-3-definition/MVP_Definition.md#5-完整-mvp-范围与能力边界)，图 DEF-02 |
| 教材、领域定义、个人记录和判断是什么关系 | [Requirements §1](phase-3-definition/MVP_Requirements_and_Acceptance.md#1-范围术语与需求组织)，图 REQ-01 |
| 讲解如何推进，独立检测求助后如何处理 | [Requirements §3.2](phase-3-definition/MVP_Requirements_and_Acceptance.md#32-学生求助检验与回看)，图 REQ-02、REQ-03 |
| 后台如何从案例查到模型与运行依据 | [Requirements §3.5](phase-3-definition/MVP_Requirements_and_Acceptance.md#35-管理员查看模型与实际运行)，图 REQ-04 |
| 章节状态与近期作答为何分开统计 | [Requirements §3.9](phase-3-definition/MVP_Requirements_and_Acceptance.md#39-章节学习情况与统计口径)，图 REQ-05 |
| 三端如何衔接教材发布、个人采用、学习及修订 | [Requirements §3.10](phase-3-definition/MVP_Requirements_and_Acceptance.md#310-三端贯通业务示例)，图 REQ-06 |
| 三端页面怎样组织，长期记录如何查找 | [Product §2](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#2-角色旅程与整体结构)，图 UX-10／11／12；§2.6 为关键路径，§2.7 为数据组织 |
| 定义、资产、工程、质量与使用价值怎样分阶段验证 | [Validation §1](phase-3-definition/MVP_Validation_Plan.md#1-验证问题与阶段责任)，图 VAL-01 |

现行模型依据为 [正式概念与系统设计入口](../concept-design/README.md)，DEC-007 替代早期独立能力本体候选。DEC-011–016 已明确目标权限、已有空间更新、章节统计、必要基础回补及按需产品内介入；OPEN-002–004 保留实际教材、投入和服务条件核验，责任与不阻塞定义的理由见 Definition §7。模型有效性、内容质量和实际投入继续凭后续资产及测量判断。

[文档架构评审](MVP_Document_Architecture_Review.md) 保留调整依据，不作为第十一份主体交付物或新 Gate。G3 已确认，Phase 4 按上述工作项推进；不重开已关闭的 Spike/Build。

[学习模型复核稿](../concept-design/DeerMind_Learning_Model_Reassessment.md) 保留探索过程，当前单模板多维结论与逐文件变更见其 §11。正式模型以 Domain / Learning Space v1.3、Concept / Evaluation / Interaction / Evolution v1.5 和 System Design v1.4 为准；实际资产与实现的迁移仍由 OPEN-010 跟踪，历史实验结论保留原范围。
