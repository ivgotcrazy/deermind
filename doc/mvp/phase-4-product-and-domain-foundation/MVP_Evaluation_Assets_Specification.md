# MVP 评测资产规格与清单

> **版本**：v0.2<br>
> **文档性质**：评测资产规格与清单；Phase 4 — Product & Domain Foundation<br>
> **状态**：交互、实际单元语义和首批权限合同案例已编制；独立参考、正式留出材料及联合审查尚缺，G4 未通过<br>
> **上游依据与基线**：[G3-20261015-01](../MVP_Gate_Reviews.md#27-g3-阶段性审阅通过与-phase-4-交接)<br>
> **维护责任**：Codex 编制与检查，内容和评分参考由实际承担者复核；未发生的复核不得填成通过<br>
> **评审记录**：当前案例为作者编制的开发走查材料，不是独立质量评测或学习效果结果<br>
> **写作规范**：[设计文档规范 v1.1](../../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-19<br>
> **修订说明**：同步评测交接范围；补充四维定义、语义边界、同源证据与裁剪扩展的必需案例；同步现行交叉引用和导航。逐文件变更见[修订记录 §10](../../concept-design/DeerMind_Learning_Model_Reassessment.md#10-默认四维评价框架的正式修订记录)。

---

本文将 [Validation](../phase-3-definition/MVP_Validation_Plan.md) 的问题和判据落实为可取得的案例与参考。输入为 AC、MET、[交互设计](MVP_Product_and_Interaction_Design.md)、[领域材料](MVP_Domain_and_Content_Foundation.md)与[权限合同](MVP_Data_and_Authority_Design.md)，输出为 CASE、输入、参考、分组版本和执行要求。本文不另定通过阈值，也不将测试脚本存在等同于系统通过。

## 1. 评测对象与覆盖要求

| 证据类别 | 需要取得什么 | 当前进度 |
| --- | --- | --- |
| 产品流程与确定性行为 | 输入、反馈时机、活动结束、恢复、只读及版本展示的正反路径 | 六批共四十八例，涵盖局部学习、维护与运行流程 |
| 数据与权限机制 | 允许、拒绝、关系失效、隐藏、事项范围及重试对照 | CASE-061–072 已编制，含多孩子、多家长与按事项访问的合成输入；合同审阅及服务端验证未完成 |
| 教学与评价语义 | 真实教材、题意、合法方法、帮助条件、评价及生成题参考 | 校内八道原创题、51 条教材定位参考、8 幅关系图及十二个案例已编制；独立复核与留出集待准备 |
| 维护与实际生效 | 候选、检查、批准、启用、影响处理、旧版与失败恢复 | 已有本地候选、审核、发布与指定采用案例；真实生效及影响处理尚未执行 |
| 设备、时间及成本 | APK、多模态、真实请求起止、未知和重试、人工投入 | Phase 5/6 按既定责任准备与执行 |
| 真实使用价值 | 获准的个体实际表现、延迟检查及负担 | G6 以后方可开展相应 Pilot，不由原型代替 |

RISK-008 的变化题目、多解、组合及映射缺口按 Validation §3.1 融入语义和维护材料，不新增一轮独立模型 Spike。

## 2. 案例结构与输入材料

EVAL-001 为案例交换合同。每个案例至少包含稳定 CASE 编号及修订、所属分组、来源与适用范围、AC/MET 引用、前置状态、输入材料及版本、用户操作、允许结果、不可接受结果、判定方式、参考来源与复核状态。依赖其他案例的结果时明确引用，不能把执行顺序当成隐含前提。

首批实际结构见 [chapter-interaction-cases.json](../../../src/mvp_foundation/evaluation/chapter-interaction-cases.json)。新增流程见 [product-flow-cases.json](../../../src/mvp_foundation/evaluation/product-flow-cases.json)，沿用相同案例含义。这些是流程开发样例，`reference_status` 表达作者参考尚需审查；没有给全部案例伪造一个“已通过”字段。正式语义案例还需带规则、Domain 与目标版本、帮助背景、期望结论范围及不能推导的结论。

输入与参考分别授权使用。原型前端的预写参考仅适用于走查，不作为正式独立测量的隐藏参考存储方案。

[教材逐题参考](../../../src/mvp_foundation/content/fractions-application/source-references.json)包含页内条件摘要、作者解答及关系重绘。图中可能补入原题未给的推导量，因此资产标为 `answer_reference_only`；其本身不是无提示图文检测输入。准备实际识别案例时，须固定原图区域、图示缺失与完整输入的对应关系，并将参考答案隔离。不能用重绘包含的结果作为模型成功读取原图的证据。

## 3. 参考结果与评判准则

确定性规则对照已批准的产品行为，例如检测进行中不得展示对错、结束后不能恢复为同次检测。语义质量依据可核查题意、数学和评价条件审查，不能用当前模型输出反向定义正确。

允许多种正确解法与合理措辞，判定重点是要求、理由、条件及结论范围。识别争议、未作答、参考有争议和运行失败分开；如果系统实际没有接入评价，不能将“尚未判断”计入 MET-004 的成功样本。

未取得可靠参考时记录原因及后续责任，不从已有失败中悄悄删除材料。目标和评分参数仍归 Validation 管理；新增阈值或改变准入需另行决定。

Task Claim 及默认四维修订要求下列参考情景，尚待形成并审核实际案例资产；现有案例数量、执行结果及 G3 快照保持原义。确定性行为对应 AC-009、AC-014 等；证据适用性和推断质量作为语义案例准备，不把静态检查当语义测量。

| 情景 | 应核对的结果 |
| --- | --- |
| ANY 允许 A、B，学习者仅完成 A | 支持该任务责任；不推断 B 或相关 KC 已掌握 |
| 目标要求 A、B 分别覆盖，仅观察 A | B 覆盖不足，不判 B 已失败；目标与 Claim 版本明确 |
| 定位提示后订正正确 | 保存受助与原错事实，不升级为独立完成 |
| 正确作答但没有要求解释 | 求解可能正向；解释没有信息，不记反向 |
| 延迟、新表征与重复题 | 保留实际间隔、变化与同源依赖，不自动获得普遍保持或迁移结论 |
| 旧 KC Belief 与新 Task Claim 并存历史 | 当前读取与写入只用新合同；旧状态只按历史查询，不兼容回退、不直接改标签 |
| KC 诊断参与讲解 | 能追溯具体表现和知识依据，没有隐性持久 KC 掌握分数 |
| 默认维度已采用但无对应 Claim 定义 | 报告内容准备缺口，不自动记为学习者失败或不适用 |
| C1 已有支持，解释／迁移未测、保持时点未到 | 只支持适用命题，其他维度保留未知／待观察，不复制 Belief 或平均为掌握率 |
| 图示或辨析正确，但口头表达不流畅 | 按理解责任判断，不用表达流利度替代理解质量 |
| 仅换数字，或表格形式已反复练习 | 不自动满足“首次表征变化”的迁移命题，引用实际学习背景 |
| 延迟成功但缺少先前表现，或期间有练习／帮助 | 按保持 Claim 的实际条件解释；不宣称无强化保持或长期不忘 |
| 同一表格延迟题同时用于迁移与保持 | 保存共同来源和归因限制；失败不自动归因任一维度，不重复增强置信度 |
| 有依据裁剪与因表现差临时裁剪对照 | 前者按权限与版本更新目标派生判断，后者不得直接生效；均不改写原 Belief 为能力提升 |
| 扩展效率等要求 | 先核对是否能由既有责任／质量表达；另立命题须有独立证据和决策价值，不新增隐性 KC 状态 |

Task-only 例子的语义参考见 [Evaluation §6.8](../../concept-design/DeerMind_Evaluation_Space_Design_v1.4.md#68-分数应用task-claim-与-belief-更新实例)。旧 `EVAL-CONTENT-FA-001 v1` 与内容包中的 KCClaim 参考须在新资产中迁移，不能仅由本文升版认定案例已完成。

## 4. 资产形成与质量审查

1. 从实际业务和材料选取候选，登记来源、适用行为和版本。
2. 编制可核查参考及关键反例，区分作者推定、来源答案和实际复核。
3. 核对材料完整性、重复或过近样例、答案泄露、前置帮助及不同解法。
4. 对开发材料进行静态检查、原型走查或允许的工具检查，明确这是什么证据。
5. 正式测量前固定分组、参考、有效数量与配置；按 Validation 的期限完成校准及确认。

交互开发走查与实际领域参考分别推进。分数应用候选的数字和关系可通过本地精确计算交叉检查，但其教学意义、映射和评价结论仍需独立复核；不把作者自产参考与自检合成正式质量证据。

## 5. 分组、版本与变更

本轮 `EVAL-UX-CHAPTER-001 v1`、`EVAL-UX-FLOWS-001 v1`、`EVAL-UX-JOURNEYS-001 v1`、`EVAL-UX-RECORDS-001 v1` 、`EVAL-UX-HOME-001 v1` 与 `EVAL-UX-PARENT-INPUT-001 v1` 均属于公开给开发者的交互走查材料，`held_out=false`，不能以后改称未见过的正式评测集。正式语义测量材料在领域准备后另行建立并隔离访问；派生、重复和共用参考关系须可查。

材料变化形成新修订，保留原编号和变化理由，旧执行结果仍对应旧材料。运行配置或参考修订后，按受影响范围重测，不拼接不同配置的成功样例作为同批达标结果。

`EVAL-CONTENT-FA-001 v1` 是首批真实章节驱动的语义开发参考，仍为 `held_out=false`。其中学生话语和情境由作者编写，没有真实孩子数据。正式测量须另建未参与开发的材料；不得把这十二例换个名称后当成独立留出集。

DEC-019 已明确 CASE-056 的非整除运次变化仅作可选练习或迁移探针，不作为首批章节达标必测。案例仍检查计算与情境是否一致，并保留实际表现；不得因这个用途决定丢弃证据，也不得把探针失败单独作为本章未达标的依据。用途确认不将其内容参考状态提升为已审核。

`EVAL-AUTHORITY-001 v1` 是 AUTH-001 的确定性合同材料，含两个合成学生、三个课程空间、两位家长和独立管理账号。每个场景独立重建输入，分别列允许行为、拒绝行为及所需实际证据；同组的多个分支须分别检查。它不依赖待测 LLM 判断谁有权限，也不适用语义准确率的百分比分母。

## 6. 实际资产清单与准备状态

| 资产 | 位置 | 当前可支持的检查 |
| --- | --- | --- |
| 合成章节内容 v1 | [chapter-lesson.json](../../../src/mvp_foundation/examples/chapter-lesson.json) | 分段、追问、练习及检测反馈的交互；不证明教材覆盖或语义质量 |
| CASE-001–008 | [chapter-interaction-cases.json](../../../src/mvp_foundation/evaluation/chapter-interaction-cases.json) | 正常推进、恢复、受助边界、检测求助、自由输入、三端查看及结束回看 |
| 可运行章节交互与检查 | [原型说明](../../../src/mvp_prototype/README.md)、[定向检查](../../../src/mvp_prototype/tests/foundation.spec.ts) | 实际执行与结果单独记录；网页交互不代表 APK、后端权限或模型有效性 |
| CASE-009–019 与合成展示输入 | [product-flow-cases.json](../../../src/mvp_foundation/evaluation/product-flow-cases.json)、[product-flow-fixtures.json](../../../src/mvp_foundation/examples/product-flow-fixtures.json) | 提示边界、未判题、删除可见性、状态统计、空间与家长输入隔离、候选检查和版本采用 |
| 新增流程定向检查 | [foundation-flows.spec.ts](../../../src/mvp_prototype/tests/foundation-flows.spec.ts) | 允许及拒绝分支、恢复与响应布局；不是后端或正式语义测量 |
| CASE-020–027 与课程准备样例 | [course-setup-cases.json](../../../src/mvp_foundation/evaluation/course-setup-cases.json)、[course-setup-fixture.json](../../../src/mvp_foundation/examples/course-setup-fixture.json) | 教材采用、范围与题量、检测历史、建议失效、核对审核、身份关系及首次说明 |
| 新增跨端走查脚本 | [foundation-journeys.spec.ts](../../../src/mvp_prototype/tests/foundation-journeys.spec.ts) | 七项浏览器检查组织八个案例及三种宽度；不证明真实权限或语义质量 |
| CASE-028–035 与输入样例 | [input-record-cases.json](../../../src/mvp_foundation/evaluation/input-record-cases.json)、[input-fixture.json](../../../src/mvp_foundation/examples/input-fixture.json) | 多模态输入核对、更正与订正、隐藏副本、事项追溯和课程指定采用 |
| 输入及记录检查脚本 | [foundation-records.spec.ts](../../../src/mvp_prototype/tests/foundation-records.spec.ts) | 八项浏览器检查；不代表实际识别、录音、播放、语义或权限测量 |
| CASE-036–041 与后台状态样例 | [home-operations-cases.json](../../../src/mvp_foundation/evaluation/home-operations-cases.json)、[operations-fixture.json](../../../src/mvp_foundation/examples/operations-fixture.json)、[foundation-home.spec.ts](../../../src/mvp_prototype/tests/foundation-home.spec.ts) | 首页进入、空间隔离、配置核对和原任务处理；不代表真实模型执行与去重 |
| CASE-042–048 | [parent-input-cases.json](../../../src/mvp_foundation/evaluation/parent-input-cases.json)、[foundation-parent-input.spec.ts](../../../src/mvp_prototype/tests/foundation-parent-input.spec.ts) | 家长只读、私人咨询与整段删除，检测核对、取消、求助和三端追溯 |
| CASE-049–060 | [fractions-content-cases.json](../../../src/mvp_foundation/evaluation/fractions-content-cases.json)、[内容候选](../../../src/mvp_foundation/content/fractions-application/package.json) | 合法多解、结果与理解、提示责任、换向基准、图示缺失、份额结构、规则反例、整数约束、生成参数、重复、库外方法与版本效力；未运行真实模型 |
| 教材逐题与图示参考 | [source-references.json](../../../src/mvp_foundation/content/fractions-application/source-references.json) | 51 条定位记录、58 项数值与 8 幅关系重绘，供复核题意、答案与表现要求；开发可见，不追加到独立 CASE 或测量分母 |
| CASE-061–072 | [authority-cases.json](../../../src/mvp_foundation/evaluation/authority-cases.json) | 主体与空间、逐段关联失效、私人咨询、更正分工、身份恢复、事项访问、两种删除、必要确认、候选发布、指定采用与秘密边界；未执行真实服务端检查 |
| 资产引用检查 | [evaluation/verify.py](../../../src/mvp_foundation/evaluation/verify.py) | 核对 CASE/资产编号、AC/MET 引用及权限合成输入的关联；不判定真实授权实现是否正确 |
| 正式领域、权限、维护与语义材料 | 尚未取得完整可复核资产 | 不满足 G4 联合交付条件；分别依内容、权限与完整流程准备 |

当前共有七十二个 CASE 编号：前四十八例是交互开发材料，CASE-049–060 为语义开发参考，CASE-061–072 为权限合同场景组；不能把合计数当成独立测量样本数。自动化检查可合并相关案例的操作；覆盖到哪条规则和未覆盖什么须如实说明。CASE-053 只模拟关键图示缺失，不含真实照片，不能计入 MET-002 的识别质量测量。

## 7. 工程接入与后续报告

执行记录应引用 CASE 修订、实际输入、使用的内容与规则、运行配置及实现版本，保留实际输出、事件、耗时、错误、重试和人工介入；判定单列参考、判断者和结果。不能只保留一个 PASS 标签。该结构将由 Phase 5 执行工具实现，当前原型测试结果按其工具格式留存。

权限案例在 Phase 5 从正式认证主体进入实际后端路径，覆盖读取、写入、检索、附件和上下文装配。逐分支保留主体、对象与空间、当前授权依据、实际返回、写入副作用及审计引用；外部调用可用不出网的假适配器检查发送边界。只检查拒绝会掩盖功能不可用，因此每组还须验证其合法路径。当前没有对应后端，全部保持未执行；浏览器原型不替代这些结果。

结果分别说明资产是否具备、参考是否审核、工具是否可运行、实际执行是否满足规则及能够支持的结论。Phase 4 的作者走查不冒充 Phase 6 质量评估或 Phase 7 真实使用结果。

## 8. 文档完成条件

| 检查项 | 当前状态 | 待完成 |
| --- | --- | --- |
| 关键流程有实际案例 | 六批共四十八例交互案例及十二组权限合同材料已编制 | 权限合同审阅，真实识别、含糊请求澄清、音频及复杂材料与完整维护影响 |
| 实际语义输入和经复核参考 | 校内候选及十二个语义开发参考已编制，未独立复核 | 校内内容复核、正式留出材料及校外内容 |
| 分组、版本和用途可查 | 开发走查已标明 | 正式材料及独立性保护 |
| 接入合同与运行边界明确 | 首稿与实际交互样例已形成 | 全量案例交接、正式工具和运行记录 |

本文不据局部原型检查授予 G4 或后续 Gate 通过。
