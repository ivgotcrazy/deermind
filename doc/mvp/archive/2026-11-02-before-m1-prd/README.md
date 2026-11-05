# MVP 文档框架与交付入口

> **版本**：v0.14<br>
> **文档性质**：MVP 文档导航与阶段交付入口<br>
> **状态**：已归档；正文状态仅反映归档前，不能作为新M1 PRD完成结论<br>
> **维护责任**：Codex 负责本轮整理与一致性检查<br>
> **版本与评审**：工作修订由 Git 追溯；准确基线与结论见 [Gate 记录](MVP_Gate_Reviews.md)<br>
> **写作规范**：[设计文档规范 v1.1](../../../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-03<br>
> **修订说明**：v0.13 → v0.14：仅更新路线图导航；原业务正文、模型结论和历史评审含义不变；见[本轮记录](../../DECISIONS.md#11-产品设计同步推进与分包计划)。<br>

---

**归档说明（2026-11-02）。** 本文是旧MVP资料的可读副本，只修订归档提示、版本与导航。精确原文保存在[原文快照](original-markdown.zip)；旧决定须按[新承接登记](../../DECISIONS.md)核对，当前工作从[新MVP入口](../../README.md)进入。

2026-11-02 已按用户授权调整为三个产品阶段，当前收敛 M1 的范围与交接。2026-10-15 的 Phase 3 阶段性审阅通过作为历史记录保留，批准基线为 [G3-20261015-01](MVP_Gate_Reviews.md#27-g3-阶段性审阅通过与-phase-4-交接)。本轮以 DEC-039 分期范围准备实际内容、必要设计、数据权限和评测；模型适用性疑问按 DEC-017、RISK-008 在实际工作中检验。

当前四份 Phase 4 文档已有工作稿。[新原型](http://127.0.0.1:5181/admin/#/domain)以原始 V2 学生端和新版后台为基线，家长端保留旧版；迁入范围、启动和限制见[原型说明](../../../../src/mvp_prototype/README.md)。此前按 DEC-026 撤销维护中心及审核发布流程，在对象所属页面直接编辑保存。已有学生教学交互和家长界面保留；本轮只调整规划。M1 的模型正式运行、实际内容质量与交接仍待完成；校外材料后置 M2；M1/G4 未通过。旧 5178 服务已退役；旧版源码从 Git 历史查看，现行原型统一为 `src/mvp_prototype`，服务继续使用 5181。

[归档](archive/README.md)和 Git 中的旧原型作历史参考，不自动成为本轮设计答案。旧原型中的整卷、旧统计和仅错题口径不属于当前范围。目录切换已完成，旧目录删除受自动审批审查阻塞，具体位置见[清理记录](MVP_Governance.md#53-原型目录统一2026-10-25)。

当前设计承接 DEC-022 的 Task-only、DEC-024 的默认四维及 DEC-025 的单模板多维组织：四维是同一任务 Claim 内部方面，Belief 分方面维护。规范见 [Evaluation §3.1–4](../../../concept-design/DeerMind_Evaluation_Space_Design_v1.5.md#31-learner-state-model定义-deermind-可以相信什么)；实际领域、案例及实现迁移仍由 OPEN-010 承接，当前原型不冒充已完成新状态接入。

本轮后台讨论已归并到以下入口，无需逐段翻找历史对话：

- [后台页面与导航](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#25-管理端编辑定义与观测运行分别组织)：领域、评估、课程、观测、学生状态和账号管理。
- [模型与内容关系](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md#2-核心概念与领域规则)：Task 经 Solution 汇总 KC，模板字段、实例保存、Task Claim 与课程采用。
- [本轮决定及版本记录](MVP_Governance.md#52-后台逐页讨论结论归并2026-10-24)：DEC-027–030、修改范围及待完成事项。

系统配置页面保留现状；M1 必需的 AI 运行配置与工具仍需交付。当前后台主要使用内存 mock；真实教材包、正式评价与权限服务尚未同步完成，不能据页面走查通过 G4。

## 1. 产品阶段与文档分工

按 [Development Roadmap](../../../top/DeerMind_Development_Roadmap_v0.10.md)，MVP 现在分 **M1 教材与教学核心闭环、M2 日常学习与多角色完善、M3 持续学习与效果验证**。每个产品阶段都要定义、设计、实现和验证；当前只细化 M1，不再等全量产品设计齐备才进入工程。

原目录继续表示工作职责，不另复制三套文档：

| 目录／工作职责 | 当前应完成的工作 | 本阶段准入 |
| --- | --- | --- |
| `phase-3-definition/` | 当前 M 阶段范围、具体行为及验证办法 | M1/G3 等：本阶段业务与验收清楚 |
| `phase-4-product-and-domain-foundation/` | 当前阶段必要交互、真实内容、权限和评测参考 | M1/G4 等：工程无需补定本阶段核心产品含义 |
| `phase-5-engineering/` | 当前阶段实现、运行、检查与交付 | M1/G5 等：本阶段必做链真实完成 |

Phase 6 内部质量及 Phase 7 受控使用仍保留其证据职责；每轮按实际范围判断，需要真实儿童参与时须满足相应 G6 与参与条件。历史 G3 不自动证明 M1 新范围就绪；M1 局部试用也不等于可公开发布。已关闭 Spike/Build 不因本次规划重开。

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

**本轮教学模型入口。** [Product §3.9](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#teaching-model)给出蓝图、策略、规则、三种情境及逐步截图；上游合同为 [Requirements §3.13](phase-3-definition/MVP_Requirements_and_Acceptance.md#313-管理员维护教学方法系统按实际情况教学)，理论与内容参考见 [Domain §6.4](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md#64-教学策略的依据与内容准备)。定义编辑和预写推演已可审阅，学生端动态采用及真实效果尚未验证；学生侧固定情境的逐步操作、25张截图见 [Product §3.10](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#student-teaching)，可从[教学走查入口](http://127.0.0.1:5181/student/teaching.html)体验。完整版本和未决见 Governance §5.4–5.5、OPEN-013。

## 3. 当前工作与后续顺序

先阅读[产品定义 §5](phase-3-definition/MVP_Definition.md#mvp-stages)：它集中列出 M1 必做、简化、后置和完成条件。具体需求阶段分配只在[需求追溯 §7](phase-3-definition/MVP_Requirements_and_Acceptance.md#7-统一追溯主索引与交接)维护，执行顺序见[实施计划 W1–W6](phase-5-engineering/MVP_Incremental_Delivery_Plan.md#3-m1-工作项依赖和产物)。

1. M1 已确定完成整册建模（DEC-040）。[教材核验、全册目录与逐章清单](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md#11-实际教材核验结论)已整理：所给链接为北师大版六上数学，含 13 项目录和 4 份附页；用户已按DEC-041指定使用此前电子源，版权页后补。当前合同的[增加关系参考](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md#65-m1-当前模型的教材参考切片)已备：两张原页、对象及方法、六题、13个评价对照；未完成正式应用或整册建模。
2. 只核对 M1 主链的产品输入输出、模型包、教学定义、主动任务、权限和验收参考；处理影响当前工程的 OPEN-010／012／013。
3. 通过本范围必要交接后，完成最小运行底座、真实管理员内容链、学生教学评价与主动任务；再进行有限联合验证并交付。
4. 依据真实结果确定 M2；完整家长端、错题／题目管理、首页统计及未纳入的交互细节保留后续，不继续提前打磨。

**原型及资产现状。** 现有 V2 布局、持续对话、教学 mock 与截图保留参考。本轮不修改任何页面或截图，也不把已有图文走查当作真实模型运行。原型入口仍为 [学生端](http://127.0.0.1:5181/student/?preview=pages)与[管理员端](http://127.0.0.1:5181/admin/)，使用说明见[原型 README](../../../../src/mvp_prototype/README.md)。旧教材开发资产、三种教学情境及评测案例分别见领域、产品和评测文档，采用前需核对是否满足 M1 当前合同。

**规划与证据。** DEC-039 记录本次分期，DEC-040 明确整册建模并关闭 OPEN-014；DEC-041确定电子工作源；OPEN-002继续跟踪后补元数据、原文件完整性及实际处理条件，版权页不阻塞独立准备。历史 G3 及原型检查保留；当前 M1/G4、G5 未通过。系统配置页面暂缓，但 M1 必需的模型连接、密钥保护、超时失败和调用查看可由运行配置与工具承担，不能因无配置页而漏掉 AI 运行能力。

[学习模型复核稿](../../../concept-design/DeerMind_Learning_Model_Reassessment.md) 保留探索过程，当前单模板多维结论与逐文件变更见其 §11。MVP 管理操作按 DEC-026 收缩为直接维护；独立 Evolution 审核发布工作流后置，不改变下述模型语义所有权。既有模型基线为 Domain / Learning Space v1.3、Concept / Evaluation / Interaction / Evolution v1.5 和 System Design v1.4。本轮 MVP 的 Task–Solution–KC 关系以领域与内容基础 §2 为准；概念图仍含直接 Task–KC 关系，后续同步见 OPEN-012。实际资产与实现的迁移由 OPEN-010 跟踪，历史实验结论保留原范围。
