# MVP 评测资产规格与清单

> **版本**：v0.16<br>
> **文档性质**：评测资产规格与清单；Phase 4 — Product & Domain Foundation<br>
> **状态**：已归档；正文状态仅反映归档前，不能作为新M1 PRD完成结论<br>
> **上游依据与基线**：DEC-039 与 Definition §5 的 M1–M3 范围；历史 [G3-20261015-01](../MVP_Gate_Reviews.md#27-g3-阶段性审阅通过与-phase-4-交接) 及其后有效模型／产品决定；当前 M1 接收范围尚待核对。<br>
> **维护责任**：Codex 编制与检查，内容和评分参考由实际承担者复核；未发生的复核不得填成通过<br>
> **评审记录**：当前案例为作者编制的开发走查材料，不是独立质量评测或学习效果结果<br>
> **写作规范**：[设计文档规范 v1.1](../../../../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-02<br>
> **修订说明**：v0.15 → v0.16：归档状态与路径修订，历史正文及评审结论保持原义；逐文件记录见[本次目录变更](../../../DECISIONS.md#4-本次目录变更记录)。

---

**归档说明（2026-11-02）。** 本文是旧MVP资料的可读副本，只修订归档提示、版本与导航。精确原文保存在[原文快照](../original-markdown.zip)；旧决定须按[新承接登记](../../../DECISIONS.md)核对，当前工作从[新MVP入口](../../../README.md)进入。

本文将 [Validation](../phase-3-definition/MVP_Validation_Plan.md) 的问题和判据落实为可取得的案例与参考。输入为 AC、MET、[交互设计](MVP_Product_and_Interaction_Design.md)、[领域材料](MVP_Domain_and_Content_Foundation.md)与[权限合同](MVP_Data_and_Authority_Design.md)，输出为 CASE、输入、参考、分组版本和执行要求。本文不另定通过阈值，也不将测试脚本存在等同于系统通过。

**分期后的资产使用。** 现有 CASE、教学情境、截图和旧教材参考都是可复用输入，不自动变成北师大版 2026 年教材或 M1 的合格资产。M1 依据 Definition §5.3、Requirements §7 和 Validation §1.1 选取、补齐并固定案例；不以全量原型案例执行完毕作为 M1 开工条件。后置能力的案例保留，但不混入本阶段通过率分母。

## 1. 评测对象与覆盖要求

| 证据类别 | 需要取得什么 | 当前进度 |
| --- | --- | --- |
| 产品流程与确定性行为 | 输入、反馈时机、活动结束、恢复、只读及版本展示的正反路径 | 六批共四十八例，涵盖局部学习、维护与运行流程 |
| 数据与权限机制 | 允许、拒绝、关系失效、隐藏、事项范围及重试对照 | CASE-061–072 已编制，含多孩子、多家长与按事项访问的合成输入；合同审阅及服务端验证未完成 |
| 教学与评价语义 | 真实教材、题意、合法方法、帮助条件、评价及生成题参考 | 校内八道原创题、51 条教材定位参考、8 幅关系图及十二个案例已编制；独立复核与留出集待准备 |
| 对象维护与实际使用 | 所属页面新增、修改、保存，引用及版本检查、历史保留、实际读取与失败 | 新后台十项浏览器情境覆盖本地行为；真实使用和 DEC-032 的应用更新尚未验证 |
| 设备、时间及成本 | APK、多模态、真实请求起止、未知和重试、人工投入 | Phase 5/6 按既定责任准备与执行 |
| 真实使用价值 | 获准的个体实际表现、延迟检查及负担 | G6 以后方可开展相应 Pilot，不由原型代替 |

RISK-008 的变化题目、多解、组合及映射缺口按 Validation §3.1 融入语义和维护材料，不新增一轮独立模型 Spike。

M1 按 DEC-040 接收整册建模结果。内容覆盖核查以实际全册目录逐章列项；真实语义案例覆盖各章及主要不同任务／方法和版面内容，不能只使用既有“分数的应用”样例。结构覆盖和语义样本是两份不同的证据，具体材料按 Validation §1.1 准备，不虚构尚未取得的全册案例。

### 1.1 M1 必备案例组

| 案例组 | 输入与预期参考 | 需要区分的结果 |
| --- | --- | --- |
| 教材导入与建模 | 指定教材实际扫描件，含文字、公式、必要图／表和跨页内容；人工核对的整理及模型关联结果 | 原始识别、人工修正、最终应用分别记录；旧样例不冒充本教材 |
| 教学与提问 | 已准备章节、教学定义、学生基础不足／会算但理由不清／已有较好基础的输入及合法帮助参考 | 合适讲解、必要追问与教学切换；无依据或无材料不强行讲解 |
| 测验和个人评价 | 已核对题库、合法多种方法、独立／受助／错误／未决表现及当前 Claim 方面 | 当题反馈、Evidence、多维 Belief、目标结果分别核查；迁移与延迟未测不能被补成达标 |
| 主动任务 | 学习后缺口、需要回补、到期条件、无必要任务、已有待办或已完成任务 | 创建、适用性核对、接受、暂缓、结束及重复触发；模拟到期不当作真实保持证据 |
| 维护与运行 | 管理员修订应用、旧活动、重启、重复提交、调用失败、权限／空间对照 | 定义和状态可追溯；失败不生成假成功，历史不被覆盖，任务不重复执行 |

上述是完整材料清单；首个增加关系切片已编制 CASE-M1-001–013，均未执行，不表示整组已备齐或通过。Phase 4 确定真实材料和预期结果，Phase 5 接入后固定运行配置及样本计划；案例与 REQ 的唯一追溯关系仍在 Requirements §7。M1 留出参考需经独立于当次模型输出的核查，不能让生成模型自评作为真值；管理员一人可核对，不增加强制双人审批。

### 1.2 已编制的当前模型参考

按 DEC-041 采用链接教材，新增 [CASE-M1-001–013 v1](../../../../../src/mvp_foundation/m1/increase-reference/cases.json)，配套[当前模型包](../../../../../src/mvp_foundation/m1/increase-reference/package.json)；内容与来源详见[Domain §6.5](MVP_Domain_and_Content_Foundation.md#65-m1-当前模型的教材参考切片)。编号采用M1前缀，旧CASE-001–072及历史结果不重编号或覆盖。

13例分别检查两种允许方法、受助成功、只给结果、混淆增加量、理由矛盾、只换数字、明确表征变化、延迟条件充分／未知、识别未决、重复事件、ANY能力与ALL目标的区别。每例有采用的包／题目／Claim／目标版本、合成前置条件、输入、帮助、预期方面变化、未变方面及禁止外推。目标变体只用于方法覆盖对照，不引入第二个能力Claim。

资产检查已执行：引用和方面分区、六题精确数值、两张原页哈希，以及七类损坏输入的拒绝检查。它们只能说明参考材料内部的这些条件一致。所有 `execution.status` 为 `not_run`，没有真实LLM、推断算法或目标达标结果；`held_out=false`，不能作为正式留出集。合成的七天间隔不是统一任务周期，目标证据聚合和正式校准仍须在启用前完成。

## 2. 案例结构与输入材料

EVAL-001 为案例交换合同。每个案例至少包含稳定 CASE 编号及修订、所属分组、来源与适用范围、AC/MET 引用、前置状态、输入材料及版本、用户操作、允许结果、不可接受结果、判定方式、参考来源与复核状态。依赖其他案例的结果时明确引用，不能把执行顺序当成隐含前提。

首批实际结构见 [chapter-interaction-cases.json](../../../../../src/mvp_foundation/evaluation/chapter-interaction-cases.json)。新增流程见 [product-flow-cases.json](../../../../../src/mvp_foundation/evaluation/product-flow-cases.json)，沿用相同案例含义。这些是流程开发样例，`reference_status` 表达作者参考尚需审查；没有给全部案例伪造一个“已通过”字段。正式语义案例还需带规则、Domain 与目标版本、帮助背景、期望结论范围及不能推导的结论。

输入与参考分别授权使用。原型前端的预写参考仅适用于走查，不作为正式独立测量的隐藏参考存储方案。

[教材逐题参考](../../../../../src/mvp_foundation/content/fractions-application/source-references.json)包含页内条件摘要、作者解答及关系重绘。图中可能补入原题未给的推导量，因此资产标为 `answer_reference_only`；其本身不是无提示图文检测输入。准备实际识别案例时，须固定原图区域、图示缺失与完整输入的对应关系，并将参考答案隔离。不能用重绘包含的结果作为模型成功读取原图的证据。

## 3. 参考结果与评判准则

确定性规则对照已批准的产品行为，例如检测进行中不得展示对错、结束后不能恢复为同次检测。语义质量依据可核查题意、数学和评价条件审查，不能用当前模型输出反向定义正确。

允许多种正确解法与合理措辞，判定重点是要求、理由、条件及结论范围。识别争议、未作答、参考有争议和运行失败分开；如果系统实际没有接入评价，不能将“尚未判断”计入 MET-004 的成功样本。

未取得可靠参考时记录原因及后续责任，不从已有失败中悄悄删除材料。目标和评分参数仍归 Validation 管理；新增阈值或改变准入需另行决定。

Task Claim 及默认四维修订要求下列参考情景；§1.2 已落实其中13个对照，其余覆盖和实际审核／执行仍待完成；现有案例数量、执行结果及 G3 快照保持原义。确定性行为对应 AC-009、AC-014 等；证据适用性和推断质量作为语义案例准备，不把静态检查当语义测量。

| 情景 | 应核对的结果 |
| --- | --- |
| ANY 允许 A、B，学习者仅完成 A | 支持该任务责任；不推断 B 或相关 KC 已掌握 |
| 目标要求 A、B 分别覆盖，仅观察 A | B 覆盖不足，不判 B 已失败；目标与 Claim 版本明确 |
| 定位提示后订正正确 | 保存受助与原错事实，不升级为独立完成 |
| 正确作答但没有要求解释 | 求解可能正向；解释没有信息，不记反向 |
| 延迟、新表征与重复题 | 保留实际间隔、变化与同源依赖，不自动获得普遍保持或迁移结论 |
| 旧 KC Belief 与新 Task Claim 并存历史 | 当前读取与写入只用新合同；旧状态只按历史查询，不兼容回退、不直接改标签 |
| KC 诊断参与讲解 | 能追溯具体表现和知识依据，没有隐性持久 KC 掌握分数 |
| 默认维度已采用但无对应 Claim 内部方面定义 | 报告内容准备缺口，不自动记为学习者失败或不适用 |
| 同一 Claim 的独立方面有支持，其他方面未测或未到保持时点 | 一个多维 Belief 保留各自判断与未知，不复制或平均；局部更新不刷新其他方面时间 |
| 图示或辨析正确，但口头表达不流畅 | 按理解责任判断，不用表达流利度替代理解质量 |
| 仅换数字，或表格形式已反复练习 | 不自动满足迁移方面规定的“首次表征变化”条件，引用实际学习背景 |
| 延迟成功但缺少先前表现，或期间有练习／帮助 | 按保持方面的实际条件解释；不宣称无强化保持或长期不忘 |
| 同一表格延迟题同时用于迁移与保持 | 保存共同来源和归因限制；失败不自动归因任一维度，不重复增强置信度 |
| 有依据裁剪与因表现差临时裁剪对照 | 前者按权限与版本更新目标派生判断，后者不得直接生效；均不改写原 Belief 为能力提升 |
| 扩展效率等要求 | 优先用现有方面质量条款表达，必要时有依据增加内部方面，随 Claim 版本核对并保存；不新增隐性 KC 状态 |
| 同一 Claim 绑定两个模板，或只给根 Claim 的无范围证据 | 拒绝规范绑定或不完整候选，不能默认更新所有任务／方面 |
| 某方面失效，另一些方面仍有效 | 按消费者所需方面解析，失效项不得由其他方面或旧缓存填充；不足与失效分开 |
| A 学习后的 B 迁移表现，或母任务含已映射子任务 | B 方面只评价 B；子任务须实际表现与适用映射，不能从母任务成功自动填满全部节点 |
| 旧 C1–C4 合并与旧多模板 Claim 拆分 | 核对语义、来源和依赖；不拼接旧分数、不复制综合状态，同源证据去重；不兼容方面未知 |

Task-only 例子的语义参考见 [Evaluation §6.8](../../../../concept-design/DeerMind_Evaluation_Space_Design_v1.5.md#68-分数应用一个-claim-的多维-belief-更新实例)。旧 `EVAL-CONTENT-FA-001 v1` 与内容包中的 KCClaim 参考须在新资产中迁移，不能仅由本文升版认定案例已完成。

**KC 对应关系的新增参考要求。** 按 [Domain Foundation §2.5](MVP_Domain_and_Content_Foundation.md#25-kc-的任务与方法对应关系) 和 AC-014，后续资产须分别覆盖：

- 同一 KC 对应多个任务和方法，反查不丢失来源；方法裁剪后只保留适用路径。
- KC 已有知识使用路径，但课程缺少针对性理解任务；须报告覆盖不足，不从“被引用”推断“已检测”。
- 基础知识理解任务可以取得表现依据；复杂任务的成功不自动支持全部关联知识，系统提供的图示解释不计为学生独立完成。
- 无对应路径的候选保留关系待补；准备缺口不被写成学生能力不足。

KC反查与针对性检测的完整对照仍待补齐；§1.2的新切片只落实本次路径和评价边界。旧案例与历史结果不改写，本批没有运行语义测量或补记通过结果。

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
| 合成章节内容 v1 | [chapter-lesson.json](../../../../../src/mvp_foundation/examples/chapter-lesson.json) | 分段、追问、练习及检测反馈的交互；不证明教材覆盖或语义质量 |
| CASE-001–008 | [chapter-interaction-cases.json](../../../../../src/mvp_foundation/evaluation/chapter-interaction-cases.json) | 正常推进、恢复、受助边界、检测求助、自由输入、三端查看及结束回看 |
| 可运行章节交互与检查 | [原型说明](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/README.md)、[定向检查](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation.spec.ts) | 实际执行与结果单独记录；网页交互不代表 APK、后端权限或模型有效性 |
| CASE-009–019 与合成展示输入 | [product-flow-cases.json](../../../../../src/mvp_foundation/evaluation/product-flow-cases.json)、[product-flow-fixtures.json](../../../../../src/mvp_foundation/examples/product-flow-fixtures.json) | 提示边界、未判题、删除可见性、状态统计、空间与家长输入隔离、候选检查和版本采用 |
| 新增流程定向检查 | [foundation-flows.spec.ts](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation-flows.spec.ts) | 允许及拒绝分支、恢复与响应布局；不是后端或正式语义测量 |
| CASE-020–027 与课程准备样例 | [course-setup-cases.json](../../../../../src/mvp_foundation/evaluation/course-setup-cases.json)、[course-setup-fixture.json](../../../../../src/mvp_foundation/examples/course-setup-fixture.json) | 教材采用、范围与题量、检测历史、建议失效、核对审核、身份关系及首次说明 |
| 新增跨端走查脚本 | [foundation-journeys.spec.ts](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation-journeys.spec.ts) | 七项浏览器检查组织八个案例及三种宽度；不证明真实权限或语义质量 |
| CASE-028–035 与输入样例 | [input-record-cases.json](../../../../../src/mvp_foundation/evaluation/input-record-cases.json)、[input-fixture.json](../../../../../src/mvp_foundation/examples/input-fixture.json) | 多模态输入核对、更正与订正、隐藏副本、事项追溯和课程指定采用 |
| 输入及记录检查脚本 | [foundation-records.spec.ts](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation-records.spec.ts) | 八项浏览器检查；不代表实际识别、录音、播放、语义或权限测量 |
| CASE-036–041 与后台状态样例 | [home-operations-cases.json](../../../../../src/mvp_foundation/evaluation/home-operations-cases.json)、[operations-fixture.json](../../../../../src/mvp_foundation/examples/operations-fixture.json)、[foundation-home.spec.ts](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation-home.spec.ts) | 首页进入、空间隔离、配置核对和原任务处理；不代表真实模型执行与去重 |
| CASE-042–048 | [parent-input-cases.json](../../../../../src/mvp_foundation/evaluation/parent-input-cases.json)、[foundation-parent-input.spec.ts](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype/tests/foundation-parent-input.spec.ts) | 家长只读、私人咨询与整段删除，检测核对、取消、求助和三端追溯 |
| CASE-049–060 | [fractions-content-cases.json](../../../../../src/mvp_foundation/evaluation/fractions-content-cases.json)、[内容候选](../../../../../src/mvp_foundation/content/fractions-application/package.json) | 合法多解、结果与理解、提示责任、换向基准、图示缺失、份额结构、规则反例、整数约束、生成参数、重复、库外方法与版本效力；未运行真实模型 |
| 教材逐题与图示参考 | [source-references.json](../../../../../src/mvp_foundation/content/fractions-application/source-references.json) | 51 条定位记录、58 项数值与 8 幅关系重绘，供复核题意、答案与表现要求；开发可见，不追加到独立 CASE 或测量分母 |
| CASE-061–072 | [authority-cases.json](../../../../../src/mvp_foundation/evaluation/authority-cases.json) | 主体与空间、逐段关联失效、私人咨询、更正分工、身份恢复、事项访问、两种删除、必要确认、候选发布、指定采用与秘密边界；未执行真实服务端检查 |
| 资产引用检查 | [evaluation/verify.py](../../../../../src/mvp_foundation/evaluation/verify.py) | 核对 CASE/资产编号、AC/MET 引用及权限合成输入的关联；不判定真实授权实现是否正确 |
| 正式领域、权限、维护与语义材料 | 尚未取得完整可复核资产 | 不满足 G4 联合交付条件；分别依内容、权限与完整流程准备 |

当前共有七十二个 CASE 编号：前四十八例是交互开发材料，CASE-049–060 为语义开发参考，CASE-061–072 为权限合同场景组；不能把合计数当成独立测量样本数。自动化检查可合并相关案例的操作；覆盖到哪条规则和未覆盖什么须如实说明。CASE-053 只模拟关键图示缺失，不含真实照片，不能计入 MET-002 的识别质量测量。

**较早后台直接维护的检查资产。** [admin-workbench.test.mjs](../../../../../src/mvp_prototype/tests/admin-workbench.test.mjs) 对应 AC-014、015、022，覆盖直接编辑、结构拒绝、旧草稿迁移、历史保护、个人依据处理及真实来源隔离。案例为开发可见的合成数据，结果索引见[原型说明 §7.2](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype_next/README.md#72-取消审核发布并直接保存v09)。不调用真实模型，不算学习效果或服务端权限验证。

上述 CASE-016–018、024–025、061–072 中包含的候选审批发布步骤保留历史内容，但不再作为 DEC-026 之后的强制验收。其身份、版本、范围和历史保护责任仍有效；既有空间采用的产品选择按 DEC-032 已收口，正式机制案例仍待交付，不改写旧通过结果冒充新流程已验证。

### 6.1 当前后台的交互检查资产

本轮各页使用当前 mock 模型。以下脚本和走查材料可用于核对界面行为，不能代替实际教材、真实语义分类、Belief 推断或服务端权限验证，也不加入前述 CASE 的独立样本数。

| 页面与合同 | 当前资产 | 主要检查内容 |
| --- | --- | --- |
| 领域与任务 | [domain-mock.ts](../../../../../src/mvp_prototype/admin/src/workbench/domain-mock.ts)、[TaskWorkspace.vue](../../../../../src/mvp_prototype/admin/src/components/TaskWorkspace.vue)、[TaskInstances.vue](../../../../../src/mvp_prototype/admin/src/components/TaskInstances.vue)；原型说明 §7.5 的走查目录 | 三类对象、分区编辑、直接方法、递归 KC、实例保存拒绝；归类结果为 mock，不能测准确率 |
| Task Claim | [evaluation-management.test.mjs](../../../../../src/mvp_prototype/tests/evaluation-management.test.mjs) | 唯一 Task、方法条件、内部方面、解释及推断说明、直接保存 |
| 教材与章节 | [textbook-management.test.mjs](../../../../../src/mvp_prototype/tests/textbook-management.test.mjs) | 章节上下文、当前任务与方法选择、KC 汇总及来源定位 |
| 学习目标 | [target-management.test.mjs](../../../../../src/mvp_prototype/tests/target-management.test.mjs) | 章节与 Claim 引用、要求项、标准、方法条件和缺口 |
| 学习空间 | [learning-space-management.test.mjs](../../../../../src/mvp_prototype/tests/learning-space-management.test.mjs) | 课程范围、要求、采用快照、个人状态及版本区别 |
| 交互审查 | [activity-review.test.mjs](../../../../../src/mvp_prototype/tests/activity-review.test.mjs) | 活动／轮次／步骤、瀑布图、执行／审查／评价分别显示及追溯 |
| 空间观测 | [runtime-observation.test.mjs](../../../../../src/mvp_prototype/tests/runtime-observation.test.mjs) | 范围、期间变化、当前快照、对象与活动追溯、侧栏空间切换 |
| 学生状态 | [student-state.test.mjs](../../../../../src/mvp_prototype/tests/student-state.test.mjs) | 学生／空间／Claim 三级、个人 Belief 与目标结果、证据变化 |
| 运行总览 | [runtime-overview.test.mjs](../../../../../src/mvp_prototype/tests/runtime-overview.test.mjs) | 统计对象、去重、日期范围、执行问题与评价结果分开、下钻 |
| 用户管理 | [user-management.test.mjs](../../../../../src/mvp_prototype/tests/user-management.test.mjs) | 独立账号、无空间学生、逐条亲子关系、找回原账号及关联跳转 |

原始 V2、较早统一工作台和本轮页面的脚本保留各自适用范围。历史 `space-observation.test.mjs`、`interaction-review.test.mjs` 或 `admin-workbench.test.mjs` 通过，不等于上表当前页面已执行全套检查。实际执行结果须注明脚本和当时版本；该段记录 2026-10-24 的文档批次；2026-10-27 教学页及相邻页的复核另见 §6.2 和 Product §7.1，不将历史通过自动延续。文档检查记录见 Governance §5.2。

配置页面未新增检查场景：用户尚未决定配置内容，旧 CASE-039 等只说明当时样例，不构成新配置设计获准或服务已接通。新实例表格的生成和归类也是固定 mock，不得混入真实模型质量测量。

### 6.2 教学模型管理与三种情境的开发资产

| 资产 | 位置与内容 | 用途及限制 |
| --- | --- | --- |
| 教学定义和预写情境 | [teaching-mock.ts](../../../../../src/mvp_prototype/admin/src/workbench/teaching-mock.ts)：六阶段、十三条初始连接、六类策略、四条通用规则及三种情境 | 开发可见；保存修改为内存 mock，情境固定依据初始 v1；不是执行引擎或正式教学规范包 |
| 管理页面 | [TeachingWorkspace.vue](../../../../../src/mvp_prototype/admin/src/components/TeachingWorkspace.vue)、[TeachingBlueprint.vue](../../../../../src/mvp_prototype/admin/src/components/TeachingBlueprint.vue) | 核对编辑、引用、停止和切换的产品逻辑；不证明真实 Policy、Evaluation 或后端权限 |
| 操作检查 | [teaching-management.test.mjs](../../../../../src/mvp_prototype/tests/teaching-management.test.mjs)：10 项子检查 | 覆盖蓝图、策略、规则、历史、mock 隔离、三种情境和较窄视口；该批通过，无模型调用，不计入独立语义样本数 |
| 截图及可复现操作 | [capture-teaching-spec.mjs](../../../../../src/mvp_prototype/tests/capture-teaching-spec.mjs)、[T01–T24 采集清单](assets/product-interaction/teaching-model/capture-manifest.json) | 实际页面截图逐项对应 Product §3.9；清单保留源码哈希及采集时的状态，不以 HEAD 冒充未提交文件 |

三种情境分别检查基础含义不足、正确结果但理由不足、已有熟悉条件理解后的迁移检验；后续分支包含同阶段换策略、直接解释、检测求助、材料歧义及提前收束。相同输入允许多个有依据的合理教法，不能把必须复现脚本当成真实语义准确率判据。

AC-025 的正式接收还需补实际定义包、目标和内容版本、允许策略与禁止行为参考、实际动作及帮助记录。真实测量须用未参与调整的材料，区分选择适切性、数学正确性、状态转换与 Evaluation 的结论范围；指标和校准仍由 Validation 维护。管理员情境已有对应的学生 mock 交互，见 §6.3；尚未接通真实动态教学，因此本节不授予 G4 或实际能力通过。

旧 CASE 涉及逐空间手动采用、长期选章或审批发布的部分，仅按原基线解释；当前验收以 DEC-031–035、Requirements AC-022／023 和 Product 的 I／Q／C／U 系列操作为准。不得拿旧脚本通过替代新版采用或真实生成检查。

### 6.3 三种学生情境与必要分支

[Product §3.10](MVP_Product_and_Interaction_Design.md#student-teaching)是当前学生教学交互规格。旧固定两题路径继续用于教材及后台联动检查，不以其结果选择器或题内输入框作为新版教学设计。

| 资产 | 内容与限制 |
| --- | --- |
| [teaching-session.ts](../../../../../src/mvp_prototype/student/src/teaching-session.ts) | 基础回补、对比辨析、图示检测的独立情境及明确响应；精确匹配预设输入，不是语义分类器 |
| [TeachingLesson.vue](../../../../../src/mvp_prototype/student/src/components/TeachingLesson.vue) | V2 对话内材料、作答、检测、反馈和小结；底部统一输入；演示工具与学生操作分开 |
| [走查与采图脚本](../../../../../src/mvp_prototype/tests/capture-student-teaching.mjs) | 13组行为检查、25张图；包含求助先结束、未提交不计错、材料未决、未覆盖自由输入、刷新草稿、1024×768；不调用模型 |
| [S01–S25 清单](assets/product-interaction/student-teaching/capture-manifest.json) | 当前完成状态、检查项、源码及图片哈希；与 Product 的每步说明对应 |

三个情境不构成前后连续的同一学习者历史。图示成功只支持本例图示条件；受助练习不冒充独立掌握，未检测方面不抹去已有认识。真实语言变体、真实策略选择、正式题库检查和持久效果留待后续测量，不增加 CASE/MET 的独立样本数量。

### 6.4 按比例增加：内容到评价的完整走查

[采集脚本](../../../../../src/mvp_prototype/tests/capture-fraction-flow.mjs)通过隔离浏览器存储执行管理员准备、学生选用、讲解、两题检测、反馈及纠错。数据定义见 Domain Foundation §2.6，界面规格见 [Product §3.11](MVP_Product_and_Interaction_Design.md#fraction-walkthrough)；[采集清单](assets/product-interaction/fraction-flow/capture-manifest.json)记录实际结果、源码哈希和 F01–F18。

- 内容：两种合法方法、递归汇总 KC、单 Task Claim 四方面、课程目标采用。
- 题目：先保存后展示、题面和参考采用快照、题目新版不改历史作答。
- 评价：只有答案不等于解释，紧邻教学的全对不等于稳定独立或保持，自由输入不套预写结论。
- 退出与失败：准备失败未开测，求助结束整场检测，未提交不计错，刷新后草稿保留。
- 纠错：精确作废题目版本、保留原记录、排除错误依据、其他方面仍保留有效来源。
- 交互：底部单一输入，平板下对话与右侧页面保留，无真实模型调用。

这些是开发走查用例与作者参考，不是留出评测，不测模型语义准确率、普遍教学效果或真实多维推断。代码中的预设匹配只防止任意输入获得虚假评价，不是后续正式评分方案。正式包迁移和独立参考仍由 OPEN-010 承接。

## 7. 工程接入与后续报告

执行记录应引用 CASE 修订、实际输入、使用的内容与规则、运行配置及实现版本，保留实际输出、事件、耗时、错误、重试和人工介入；判定单列参考、判断者和结果。不能只保留一个 PASS 标签。该结构将由 Phase 5 执行工具实现，当前原型测试结果按其工具格式留存。

权限案例在 Phase 5 从正式认证主体进入实际后端路径，覆盖读取、写入、检索、附件和上下文装配。逐分支保留主体、对象与空间、当前授权依据、实际返回、写入副作用及审计引用；外部调用可用不出网的假适配器检查发送边界。只检查拒绝会掩盖功能不可用，因此每组还须验证其合法路径。当前没有对应后端，全部保持未执行；浏览器原型不替代这些结果。

结果分别说明资产是否具备、参考是否审核、工具是否可运行、实际执行是否满足规则及能够支持的结论。Phase 4 的作者走查不冒充 Phase 6 质量评估或 Phase 7 真实使用结果。

**学生四页检查资产。** [P01–P18 采集清单](assets/product-interaction/student-pages/capture-manifest.json)对应 [Product §3.12](MVP_Product_and_Interaction_Design.md#student-pages)。[采集脚本](../../../../../src/mvp_prototype/tests/capture-student-pages.mjs)检查课堂进度、要求到原题及所属活动的追溯、返回保留筛选、日期过滤不改学习判断、订正后错误历史保留、教材按次选择、对话来源页面和空间隔离。[统计边界检查](../../../../../src/mvp_prototype/tests/student-page-metrics.test.mjs)核对自然日窗口、未知日期、合格分母、重复题和失效依据。固定记录的算术一致性不是评价模型准确率或学习效果证据；既有教学及教材导入截图按新页面重采。

**持续对话检查资产。** [H01–H18采集清单](assets/product-interaction/conversation/capture-manifest.json)对应 [Product §3.13](MVP_Product_and_Interaction_Design.md#continuous-conversation)。[浏览器走查](../../../../../src/mvp_prototype/tests/capture-conversation.mjs)检查自然输入、右侧浏览与显式切换的区别、日期章节类型查询、引用及取消、已结束检测不复活、求助收束、空间隔离、草稿恢复与平板唯一输入。[状态边界检查](../../../../../src/mvp_prototype/tests/conversation.test.mjs)补充活动身份及追加记录、准备不等于开始、引用旧检测、自由回答不套结论等情形。mock 固定分支不验证语义分类准确率或检索召回率，不增加正式评测样本数。

## 8. 文档完成条件

| 检查项 | 当前状态 | 待完成 |
| --- | --- | --- |
| 关键流程有实际案例 | 六批共四十八例交互案例及十二组权限合同材料已编制 | 权限合同审阅，真实识别、含糊请求澄清、音频及复杂材料与完整维护影响 |
| 实际语义输入和经复核参考 | 校内候选及十二个语义开发参考已编制，未独立复核 | 校内内容复核、正式留出材料及校外内容 |
| 分组、版本和用途可查 | 开发走查已标明 | 正式材料及独立性保护 |
| 接入合同与运行边界明确 | 首稿与实际交互样例已形成 | 全量案例交接、正式工具和运行记录 |

本文不据局部原型检查授予 G4 或后续 Gate 通过。
