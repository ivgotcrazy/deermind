# MVP 内容与评测准备资产

> **文档性质**：Phase 4 资产入口与使用说明<br>
> **状态**：已有 G3 批准快照、合成交互材料、开发案例及校内实际单元候选；正式内容审核与领域发布待完成<br>
> **维护责任**：Codex 维护本轮资产；管理员复核实际内容<br>
> **写作规范**：[设计文档规范](../../doc/top/DeerMind_Design_Document_Standard_v1.0.md)<br>
> **版本与评审**：各资产分别记录修订、来源与用途；[阶段记录](../../doc/mvp/MVP_Gate_Reviews.md)<br>
> **更新日期**：2026-10-17

---

| 路径 | 用途与状态 |
| --- | --- |
| [baselines/G3-20261015-01/manifest.json](baselines/G3-20261015-01/manifest.json) | 批准前实际内容及依赖的文件、版本和哈希；同目录 inputs.zip 可恢复准确内容，不覆盖旧快照 |
| [materials/material-intake.json](materials/material-intake.json) | v3：校内第四单元八页已读，内容候选已形成；审核与具体出版年／印次待核，校外材料后补 |
| [content/fractions-application/package.json](content/fractions-application/package.json) | 实际单元候选 v1：21 组教材定位、5 类问题、9 种方法、9 个 KC、6 项候选要求、7 个 Claim、8 道原创题；待审核、未发布 |
| [content/fractions-application/source-references.json](content/fractions-application/source-references.json) | 51 条逐题作者参考、8 幅数量关系图的数据及来源页哈希；计算、画图和说理要求分列，开放问题不强设唯一答案；未独立复核 |
| [content/fractions-application/verify.py](content/fractions-application/verify.py) | 本包引用、来源范围、精确数值及参数约束检查；不证明语义有效或教学质量 |
| [evaluation/fractions-content-cases.json](evaluation/fractions-content-cases.json) | CASE-049–060：12 个语义开发参考，未独立审核、未运行模型；不是留出集 |
| [evaluation/authority-cases.json](evaluation/authority-cases.json) | CASE-061–072：12 组权限允许／拒绝对照及多孩子、多家长合成输入；等待合同审阅与 Phase 5 后端执行 |
| [evaluation/verify.py](evaluation/verify.py) | 评测资产与 CASE 编号、AC/MET 引用和合成权限输入关联检查；不执行授权判定 |
| [examples/chapter-lesson.json](examples/chapter-lesson.json) | Codex 自编的章节交互示例，版本 1；不是实际教材映射、正式 Domain 或评价规则 |
| [examples/product-flow-fixtures.json](examples/product-flow-fixtures.json) | 自编题目、预设评价状态及作答、维护定义样例；不来自原型的实际模型运行 |
| [evaluation/product-flow-cases.json](evaluation/product-flow-cases.json) | CASE-009–019：问题求助、状态、隔离及维护的开发走查，尚未独立复核 |
| [examples/course-setup-fixture.json](examples/course-setup-fixture.json) | 合成材料两页、范围与题单、目标及建议依据，用于课程与后台衔接 |
| [evaluation/course-setup-cases.json](evaluation/course-setup-cases.json) | CASE-020–027：教材采用、检测建议、任务核对和身份关系，开发走查而非语义留出集 |
| [examples/input-fixture.json](examples/input-fixture.json) | 两页文字、几何条件、错误识别与语音原话脚本，无真实多模态处理 |
| [evaluation/parent-input-cases.json](evaluation/parent-input-cases.json) | CASE-042–048：家长只读与私人咨询，检测内输入核对、取消及求助，开发材料未独立复核 |
| [evaluation/input-record-cases.json](evaluation/input-record-cases.json) | CASE-028–035：输入核对、跨来源记录与订正、事项追溯、课程指定采用 |
| [evaluation/chapter-interaction-cases.json](evaluation/chapter-interaction-cases.json) | 八个实际开发走查案例；作者参考尚未独立复核，不是留出语义评测集 |

实际教材的首批候选及剩余核查按[领域交付规格 §6](../../doc/mvp/phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md#6-首批领域与内容资产清单)查阅。后台可只读查看分数应用草案；候选未经审核不发布为真实课程，也不得从原型操作生成实际能力结论。

DEC-019 已确认非整除运次只作可选练习或迁移探针，不作为首批章节达标必测；该决定已写入目标、ITEM-FA-07 与 CASE-056，不等同题目已发布。可在仓库根目录运行 `python -X utf8 src/mvp_foundation/content/fractions-application/verify.py` 和 `python -X utf8 src/mvp_foundation/evaluation/verify.py` 核对当前引用与数值。

此目录允许保留准确资产基线与历史快照；`doc/` 中仍只维护各文档的当前版本。具体准备责任和范围以 Phase 4 文档为准。

## 学习入口与后台运行增量

2026-10-16 新增 [CASE-036–041](evaluation/home-operations-cases.json) 和 [后台状态样例](examples/operations-fixture.json)。前者记录首页进入、同名空间与材料草稿隔离、配置与原任务处理；后者为四条人工编写的任务，不来自实际服务。与当前浏览器的教材任务及复核事项分开呈现，未决及未知费用不伪装为失败或零值。案例属于开发走查材料，参考仍待独立审阅。
