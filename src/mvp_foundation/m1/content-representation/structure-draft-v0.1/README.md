# 四例统一内容结构稿

> 版本：v0.1  
> 日期：2026-11-14  
> 性质：独立、可审阅的格式草案与验证材料；不是正式产品规格，也不是M1原型变更。  
> 修订记录：v0.1，首次建立最小Schema、四例结构稿、校验器和重建页面。

本批回答：已讨论的文字、公式、表格和图形如何落到可保存的结构，以及这些结构能否在既有四例中检查并重建。没有调用LLM，没有改写历史模型输出，没有增加原页或样例。

可浏览：[四例原件与重建对照](http://127.0.0.1:5184/structure-draft-v0.1/)。左侧为既有来源裁剪，右侧按用途显示重建内容。题面、教材解法、教学辅助、派生数据表分别读取；这是审阅工具中的分离演示，不是生产授权机制的验证。

## 1. 交付物

| 文件 | 职责 |
| --- | --- |
| [schema.json](schema.json) | JSON Schema 2020-12，实际可执行的最小结构约束 |
| [C02](cases/C02.json)、[C03](cases/C03.json)、[C05](cases/C05.json)、[C06](cases/C06.json) | 四份结构稿；不是模型原始提取结果 |
| [build_schema.py](build_schema.py)、[build_cases.py](build_cases.py) | 可复现的Schema和结构稿生成脚本；生成物也单独保存便于审阅 |
| [validate.py](validate.py)、[checks.json](checks.json) | 结构、引用、单位、图形等检查及20个反例结果 |
| [review-plan.json](review-plan.json) | 作者对照既有原图建立的内容数量清单；用于暴露“JSON合法但漏图” |
| [render.js](render.js)、[viewer.js](viewer.js) | 由结构生成MathML、HTML表格、SVG；不执行模型生成的HTML/JS |
| [review.mjs](review.mjs)、[浏览器结果](review/browser-review.json) | Chrome浏览器走查与8张截图 |

原材料继续引用`../round2/inputs/`和`../source/`，四例范围沿用[原范围清单](../round2/cases.json)。原页、裁剪图SHA-256和像素范围记录在各例`sources`中；图片文件没有重写。C05数据从历史作者核对副本复用，并再次对照第93页裁剪；其他表达由本轮作者按原图及既有核对材料整理。

## 2. 最小结构

```text
ContentDraft
  schema_version           格式版本
  content_revision         当前候选内容修订
  binding_status           pending_domain_match，尚未匹配正式领域对象
  sources[]                原页/裁剪文件、哈希、印刷页码、像素范围
  documents[]              同一道题的各用途内容
    id / role / title
    blocks[]
      id / type / provenance
      按type填写内容
  data_tables[]            图表/数据表共用的数据；属于本内容包
  notes[]                  本例审阅说明与已知边界
```

候选内容尚未入库，故不编造Task、Solution编号，也不宣称已完成领域归类。入库后将statement放入TaskInstance题面、reference放入题内参考解法，固定所属对象版本；教学辅助不进入题面。document、block及数据表的ID是内容内部定位，不是新的Domain实体或独立SolutionInstance。标识由脚本生成。

`schema_version`与领域对象版本不同；`content_revision`是候选内容修订，不能冒充TaskInstance的正式版本号。实际保存由所属模块完成，本批未接数据库或入库流程。

| type | 主要字段 | 约束 |
| --- | --- | --- |
| paragraph | content：文字、行内公式、response_blank | 答句空白不附答案；保留顺序 |
| math_sequence | purpose、lines：关系符、expression、suffix | given_work是题面待辨析材料，不是正确性判断；reference_work不得进入题面 |
| table | data_ref、caption | 本批只验证简单表头/行列；来源派生表另放derived_view |
| chart | kind、data_ref、category_column、series、unit、axis等 | 不将未知值记零；保留类别、单位、数值显示精度及非堆叠关系 |
| diagram | objects、relations、layout_role、view_box | 显示坐标不作为数学条件；本批关系仅覆盖可见点在图内 |

公式只有一份表达树。节点包括数字、符号、括号、分数、乘除加减及等式；运算参数数目固定。`cancel_to`记录被划去数字上依次写出的替换数字，例如12→4→1；它是原有书写标记，不替换算式操作数，不触发自动求值或纠错。MathML由程序生成，不保存第二份可独立修改的LaTeX。

每个内容块及数据表的provenance保存`source_refs`、`transformation`与说明。`extracted`表示按来源内容整理，并不表示机器提取通过；`normalized`表示改排版或写法并记录原因；`derived`表示由原内容加工出的视图。本批均由作者准备，没有新的模型生成内容。

数据表单元格区分provided、response_blank、source_missing、unreadable。decimal列以十进制字符串保存，保留原图1.30、5.20等精度。图表引用数据表及列，不能再存一套重复数值。未知单元格可以作为表格状态存在，本批图形渲染遇到它必须停止，不能用零补齐。

结构合法、数值/关系一致、原件完整性是不同检查。只用Schema不能发现整块内容遗漏；本批另用作者清单检查四例的组成。该清单不能作为未来未知教材的自动完整性判定算法。

## 3. 四例核对结论

| 例 | 保存及重建 | 校验重点 | 结论与限制 |
| --- | --- | --- | --- |
| C02：49–50页双解法 | 跨页条件、两种教材解法、两列三行演算、约分标记、答句空白、独立旁注 | 分数、分组、两法分离、空白不补答案；约分替换合计6次 | 选定范围内题目与解法的教学信息可以表达和重建；人物外观与笔迹形状不做像素复刻；不包含范围外线段图 |
| C03：错误演算 | 三行原算式和两处约分标记；保留÷1/3→×1/3及7/32 | 原表达树从左向右结合；数值不成立不属于格式错误 | 第一行值63/32，后两行值7/32，原错误被保留；正确值仅在校验报告中作对照，未写入题面 |
| C05：第93页三种统计图 | 柱图、折线图、扇形图；原标签、单位、图例、轴；同数据生成两张派生表 | 三图齐全、单位一致、重叠年龄人群不能相加堆叠；旁注分离 | 可以重建图中数据与关系。表格是同数据的另一视图，并非新增识别的教材原表；不证明合并单元格或跨页表格能力 |
| C06：六种平面图 | 六形状、六点、顺序和剪图要求 | 正方形宽高一致；不得从布局产生圆心/等边等断言 | 选定图形可示意重建。点的数学意义未被原文确定；附页缺失保留，不能据此宣称完整剪图活动材料齐备 |

源图与重建截图见[review](review/)。C06的多边形采用固定示意布局；不把规则排版当成原题已给出的等边条件。本批还没有支持任意几何约束求解、方向图、三维对象、合并表格或所有数学符号，这些不能因为四例通过而被宣布支持。

本批没有独立KC定义样例。内容协议能承载文字和公式，不等于已验证KC的提取、直接检验路径或领域匹配。上述范围外内容保留为后续覆盖事项，不在本次扩大测试。

## 4. 检查与复验

在仓库根目录执行，均不调用模型：

```powershell
.venv/Scripts/python.exe src/mvp_foundation/m1/content-representation/structure-draft-v0.1/build_schema.py
.venv/Scripts/python.exe src/mvp_foundation/m1/content-representation/structure-draft-v0.1/build_cases.py
.venv/Scripts/python.exe src/mvp_foundation/m1/content-representation/structure-draft-v0.1/validate.py
```

本地查看复用只读静态服务：

```powershell
.venv/Scripts/python.exe src/mvp_foundation/m1/content-representation/serve.py --port 5184
```

浏览器走查使用既有M1原型依赖中的Playwright和本机Chrome，以独立浏览器上下文运行，不读取用户登录状态：

```powershell
node src/mvp_foundation/m1/content-representation/structure-draft-v0.1/review.mjs
```

程序检查：4个样例、20个变异反例；包括未知类型、非法公式参数、答句夹带答案、来源悬空、题面夹带解法、提示用途被调换、漏图、单位冲突、未知记零、错误堆叠、显示范围截断及几何错误。反例在内存中生成，不改变样例文件，也不增加教材样本。提示用途和完整性核对依赖本批独立作者清单，不代表程序能自行理解任意提示。

浏览器检查：1500px和900px桌面浏览器宽度、来源图加载、题面与解法/提示/派生表分离、关键公式和图形数量、无横向溢出。截图用于作者再次对照原件，自动检查不替代语义核对。

## 5. 如何接给Agent与正式保存

1. Agent收到限定来源、Schema及提取规则，先产出内容候选；本批JSON可作为目标输出形状，不作为真实提取准确率。
2. 程序生成/核对内部编号和来源引用，执行结构及确定性约束检查。Agent对照原件检查漏项；管理员用对话提出修正，产生新候选修订，不改写已采用内容。
3. 采用内容后再匹配或补建Domain对象。题面和两条参考分别归入题目对应字段，引用确定版本；本批不自动创建这些业务关系。
4. 已保存版本交给对应渲染器读取。纯重排不调用LLM；新增提示、推导、辅助图或答案另保存加工来源及用途，不能覆盖原题。

建议审阅重点：表达树加约分标记是否合适；图表共用数据与派生表的区分是否清楚；几何示意与数学条件是否分清。确认后再同步正式合同，本批不自动改动正式文档或原型。
