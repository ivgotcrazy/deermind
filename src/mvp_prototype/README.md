# DeerMind MVP 交互原型

> **版本**：v0.19<br>
> **文档性质**：当前原型入口、运行说明与切换记录<br>
> **状态**：Phase 4 交互原型；统一目录，G4 尚未通过，不代表正式 MVP 实现<br>
> **维护责任**：Codex 维护；用户确认产品取舍及界面调整<br>
> **上游依据**：用户于 2026-10-25 授权以新版替换旧原型，原始来源及未迁入能力通过 Git 保留<br>
> **写作规范**：[设计文档规范](../../doc/top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-29<br>
> **修订说明**：v0.18 → v0.19：学生菜单简化为“首页、学习、教材、题目”，更新入口与走查说明；页面职责及持续对话保持不变。

---

当前学生审阅入口：[持续对话与四页](http://127.0.0.1:5181/student/?preview=pages)。启动脚本以学生角色打开时进入该地址；普通 `/student/` 保留早期真实模型／课程专项路径，不是当前持续对话演示。

## 1. 当前入口与运行

在仓库根目录执行，也可双击根目录的 `prototype.cmd`：

```powershell
.\prototype.cmd start -Role admin
.\prototype.cmd status
.\prototype.cmd restart -Role admin -NoBrowser
.\prototype.cmd stop
```

本目录的 `prototype.cmd` 使用同一启动脚本。默认端口保持 **5181**，学生、家长、管理员由同一后台服务提供：

- [学生端](http://127.0.0.1:5181/student/)
- [四页流程审阅](http://127.0.0.1:5181/student/?preview=pages)：本轮推荐入口，默认示例数据、预写页面对话，不调用真实模型。菜单为“首页、学习、教材、题目”；“学习”查看学习情况，“题目”查看题目记录。
- [三种学生教学情境](http://127.0.0.1:5181/student/teaching.html)：本轮审阅入口；在对话顶部“演示工具”填入预设回答，再在底部提交。原页面布局保留，全部为 mock。
- [管理员端](http://127.0.0.1:5181/admin/)
- [家长端](http://127.0.0.1:5181/parent/)

首次启动安装依赖、检查类型并构建三端；`restart` 重新构建并启动。页面使用静态构建，无 HMR，代码变更后需要刷新。旧 5178 页面入口已退役，不能再使用 `structure.html`、`phase4.html` 或旧版 `-Structure`、`-Foundation` 参数。

模型配置仍读取仓库根目录 `.env` 的 `DEERMIND_LLM_*`，服务端会话仍在 `.tmp/mvp-live/`。浏览器来源、存储键和会话归属保持不变，不需要清理浏览器数据。`.tmp/mvp-prototype-next/` 继续存放既有运行状态与检查证据；其中的名称是历史存储标识，不是对旧源码目录的依赖。

## 2. 目录与能力边界

| 位置 | 用途 |
| --- | --- |
| `student/` | 基于原 V2 的学生界面、连续对话、课堂进度和当前学习流程 |
| `admin/` | 当前模型、课程、账号及运行观测原型 |
| `parent/` | 保留此前迁入的家长界面，本轮仅移除退役的“旧流程工具”链接 |
| `shared/` | 当前 mock 课程流程和图文教材呈现 |
| `scripts/` | 三端服务、模型连接、会话保存及启动管理 |
| `tests/` | 服务检查与浏览器走查，测试依赖由本目录独立安装 |

真实 LLM 对话已有连接，但不代表接入完整 DeerMind 模型。后台及教材整理继续使用 mock。真实书页 49—50、91—93 已内置：教材管理 → 导入教材 → 载入真实教材书页 → 上传并开始整理。自选文件不进行真实 OCR。取消、删除未完成导入、保存和应用均为当前本地走查能力。

家长端仅保留，不在本轮继续打磨；学生多模态、正式模型运行、真实账号权限及未接通的评价仍须后续设计或工程实现。迁移不恢复旧审批流程，也不把旧预写结果变成当前真实判断。

### 2.1 本轮先审阅这条路径

同一案例的逐步操作、设计理由及截图见 [产品与交互设计 §3](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#3-按真实操作展开的交互规格)。

1. 管理员在教材管理导入内置真实书页，核对第49—50页并合并跨页解法，采用模型关联建议，生成目标建议，应用并供学生选用。91—93页仍用于图表整理检查。
2. 学生从右上角新建学习空间，选用该教材与目标，在“分数的应用（一）”进入讲解。对话保留在左侧，教材上下文在右侧。
3. 可点击预设追问、做练习，再准备两题检测。“Mock 场景选择”可选三组表现或题目准备失败；每题展开“Mock 作答判定”，点击“填入本场景示例作答”后提交。
4. 默认样例展示：文字解释已达标、区域图迁移需加强、独立及延迟保持待确认。点击“查看标准与依据”，核对要求、原作答及帮助背景，再查看学习情况或管理员活动详情。

这三组表现是供评审的替代情形，不是学生进步记录。自由输入不进行语义判定，也不会自动套上预写的正向评价；预设样例按钮只供走查，不属于正式学生功能。已有导入采用旧目标时，不会被本次代码更新偷偷改成新标准；可新建导入审阅本轮完整样例。真实 LLM 模式仍是另一路入口，本路径不调用模型。

### 2.2 按比例增加：本轮建议审阅路径

本轮用自编教材示例，先说明一个完整 Task 如何进入实际教学与评价；不把它冒充北师大版49—50页原题。逐步文字与截图见 [Product §3.11](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#fraction-walkthrough)。

1. 打开[教材章节](http://127.0.0.1:5181/admin/#/textbooks?id=BOOK-MATH&chapter=CH-INCREASE&tab=content)，点击“记录核对结果”，选择通过、保存，再“应用更新”。Task fraction、方法 S1-A/B、CLAIM-FRACTION 及目标要求已有 mock，可在所属页面查看和修改。
2. 学生右上角新建空间，选“小学数学·教材管理示例”和目标，进入“按比例增加后的数量”讲解；80米例题和两种方法在同一对话中。
3. 点击“准备检测”；“Mock 场景选择”可选文字正确／图示错误、两种方法成功、只有数值答案、信息不足。题内“演示工具”填入样例，在底部唯一输入框提交；自由输入仍保留未决。
4. 结束后展开各方面“查看要求、依据与变化”，再看学习情况。只给局部依据，不将当前全对冒充独立或持久掌握。
5. 管理员从 Task 的“实例 → 使用记录 → 查看过程”进入本次活动。选择具体检测题可“作废本题评价依据”，填写原因并确认；学生侧排除该依据、显示纠错说明，原作答保留，题库旧版本停用。此操作只影响本地 mock。

检查命令：`node tests/capture-fraction-flow.mjs`。隔离浏览器存储，固定数据，不调用模型；F01–F18 及检查结果存于文档 assets/product-interaction/fraction-flow。旧有三种教学情境和真实 LLM 入口继续保留。

### 2.4 学生四页审阅

首页更新课堂进度后，进入本章学习情况，点“需加强1项”并展开依据，再打开长度图题、查看原作答及所属检测活动。返回时原筛选和展开状态保留。教材中选择章节阅读或勾选本次检测范围，进入对话后右侧保留原页。“题目 → 错题”可看到订正后的48米题仍保留原错误；未作答、待判定分别筛选。

默认数学例子统计截至2026-10-29：8道题、2道有错误历史的题；近7天6个学习日、3次讲解、2次已结束检测。比例应用章有6项示例要求（3已达标／1需加强／2待确认），同期4次合格独立作答中3次正确。两套数字含义不同，不据此给出章节掌握率。课堂进度未填写不妨碍使用。

页面按钮的预写对话只用于确认去向和上下文，后续输入仅保留。已创建课程的数量增加／连续比例活动、三种学生情境继续走既有 mock 教学；日常入口原有的真实对话服务没有并入这组示例评价。旧 FlowCoursePage、TeachingCoursePage 文件保留供历史参考，当前四页由 StudentPages 统一呈现；不再作为当前页面入口。

文字、截图与限制见 [Product §3.12](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#student-pages)。每次文字或界面改变，都应更新对应截图与采集清单，不能只更新其中一项。

## 3. 检查方式

在本目录执行：

```powershell
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd test
npm.cmd run test:learning
node tests/browser-controls.mjs
node tests/browser-parent.mjs
node tests/capture-product-spec.mjs
node tests/capture-student-pages.mjs
node --test tests/student-page-metrics.test.mjs
python tests/check-product-spec.py
```

浏览器检查使用本机 Edge，测试服务使用独立临时目录和固定模型响应，不消耗真实模型调用、不删除用户浏览器资料。`browser-parent.mjs` 从下述 Git 提交读取来源，校验历史迁入清单；不再依赖旧工作目录。`--compare-legacy` 只供另行检出历史源码并运行 5178 服务时进行历史对照，不属于当前启动或检查前提。

## 4. 历史与未迁入内容

清理前已核对旧目录工作树无待保存源码，基线提交为 `e0895562acb4757e9f80af888643ab1e27d48506`。旧源码通过 Git 查看或另行检出，不设长期归档。

**清理尚未完成：** 新版目录及启动入口已切换，但自动审批审查拒绝了旧目录的递归删除，未返回具体原因。以下三处暂存旧文件仍待删除，当前服务和默认测试均不依赖它们：

- `.tmp/prototype-consolidation-20261025/old-mvp-prototype/`（仓库根目录下）
- `src/mvp_prototype_v2/`
- `src/mvp_admin_prototype/`

| 历史内容 | 固定引用 |
| --- | --- |
| 原 `mvp_prototype` | [旧实现](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype) |
| 原学生 V2 | [学生原始基线](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype_v2) |
| 原管理员 V2 | [管理员原始基线](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_admin_prototype) |
| 本次替换前的新原型及迁入清单 | [原型 v0.12 说明](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype_next/README.md) |

M01–M16 的早期状态和作者评审按原时间阅读，不反写为当前完成状态。当前已接入的流程以现行源码和检查为准；旧多模态工具、未承接的历史记录操作、旧家长事项回传等只保留为参考，删除目录不表示批准迁入或取消对应需求。正式归并仍遵守 MVP 的文档职责。

`BASELINE_MANIFEST.json` 与 `parent/BASELINE_MANIFEST.json` 保留复制当时的源、目标路径和哈希；其中 `mvp_prototype_next` 是历史路径。旧说明、旧代码、归档设计与评测结果应连同其 Git 基线阅读，不能因为当前目录同名就引用当前实现解释旧结果。

v0.13 统一目录、依赖及入口，保留此前删除导入等已授权改动；v0.14 在此基础上增加 §2.1 的 mock 场景与截图。具体变更和文档升版见 [共同管理记录 §5.3](../../doc/mvp/MVP_Governance.md#53-原型目录统一2026-10-25)。G4/G5 未因此通过。

## 5. 三种学生教学情境（v0.15）

本轮实现基础含义不清、会算但理由不足、已有文字理解后检测图示的三种独立情境。教学材料、练习、检测、反馈都在原 V2 对话区内，底部唯一输入框根据状态发送消息或提交作答，右侧保留进入页面。逐步规格及 S01–S25 见 [Product §3.10](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#student-teaching)。

演示入口先选情境和右侧页面；预设回答、准备失败和材料缺陷通过“演示工具”操作。普通自由输入未覆盖时保留未决，不用关键词判定。每个情境的交流和草稿只在当前标签页保存；重置在工具内执行，不清理其他真实会话或课程记录。后台模型的编辑不会自动改变固定 v1 学生脚本。

验证命令：在本目录执行 `node tests/capture-student-teaching.mjs`。本批13组行为检查通过，25张截图、无页面异常、无模型调用。学生类型检查及构建通过。该走查不涵盖 Android 软键盘／笔输入、真实生成、教学引擎或 Belief 计算；真实模型入口保持独立。旧固定两题流程仍可用于较早教材联动走查，不作为当前教学交互的最终方案。

## 6. 持续对话的本轮走查

1. 打开当前审阅入口，在首页底部输入“为什么增加四分之一还要加原量？”。左侧追加解释，右侧保留首页，旧交流不清空。
2. 在右侧教材查找“圆柱的表面积”；浏览不会切换讲解，点击“讲解”才保留旧进度、改学当前内容。
3. 对话标题栏“历史”搜索“图里的原长”，定位原文并点击“接着聊”。引用和未发草稿并存；发送“继续上次进度”恢复未完成活动。追问已结束检测不会重开提交。
4. 发送“出一道题检测一下”，确认开始，检查切换内容的确认、取消、求助及结果。底部“试用示例”可填入固定答案，再由你提交；其他输入不套用示例判定。
5. 切换空间并返回，检查消息和草稿隔离；刷新后仍保留。收起只影响显示，“本次先到这里”只结束活动，输入仍可使用。

数据使用本浏览器的 `deermind-space-conversations-v1` 本地示例记录。没有新LLM调用、真实语义检索、正式长期记忆或跨设备保存；不覆盖早期真实会话。默认活动和题目为合成记录，新增演示活动与作答在相应页面可追溯，能力要求状态不会因固定回复自动变化。

验证：`node --test tests/conversation.test.mjs`；`node tests/capture-conversation.mjs`；`python tests/check-product-spec.py`。实际截图和逐步规格见 [Product §3.13](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md#continuous-conversation)。
