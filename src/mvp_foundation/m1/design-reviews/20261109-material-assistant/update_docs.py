from pathlib import Path
import json,re

batch=Path(__file__).resolve().parent
root=batch.parents[4]
baseline=json.loads((batch/'baseline.json').read_text(encoding='utf-8'))
docs={r['path']:(root/r['path']).read_text(encoding='utf-8') for r in baseline['files']}
def replace(rel,old,new):
    assert old in docs[rel],(rel,old[:90])
    docs[rel]=docs[rel].replace(old,new)
def paragraph(rel,prefix,new):
    pattern=r'(?m)^'+re.escape(prefix)+r'[^\n]*(?:\n(?!\n)[^\n]*)*'
    assert re.search(pattern,docs[rel]),(rel,prefix)
    docs[rel]=re.sub(pattern,lambda m:new,docs[rel],count=1)

prd='doc/mvp/m1/PRD.md';content='doc/mvp/m1/design/Content_and_Model_Reference.md';interaction='doc/mvp/m1/design/Interaction_Design.md'
m1='doc/mvp/m1/README.md';design='doc/mvp/m1/design/README.md';mvp='doc/mvp/README.md';decisions='doc/mvp/DECISIONS.md'
engineering='doc/mvp/m1/engineering/README.md';validation='doc/mvp/m1/validation/Validation_Plan.md';validation_index='doc/mvp/m1/validation/README.md';prototype='doc/mvp/m1/prototype/README.md'
statuses={
    prd:'教材助手持续对话与候选采用已同步规格和mock截图；真实Agent、整册建模与工程接收另验',
    content:'教材对话引用、候选生命周期与入库交接已明确；模型、算法和试用门槛未变',
    interaction:'教材助手现行操作已逐步对应截图；跨章方法适配及LC-02–04页面交接仍有待办',
    m1:'教材助手交互已收束并同步图文；下一步进行工程接收核对，未宣布完整M1可实施',
    design:'教材助手操作、规格与截图已同步；真实识别和评价尚未接通',
    mvp:'M1教材助手交互已同步文档；继续收束主流程工程输入，不扩大界面范围',
    decisions:'记录教材助手原型收束、文档升版及后续接收安排；历史决定和验证结论保持',
    engineering:'已补充教材助手真实实现接收条件及当前测试入口；完整工程设计尚未创建',
    validation:'教材助手mock交互已复测；真实Agent纠错、概率校准及学习效果验证尚未执行',
    validation_index:'验证计划v0.2承接已完成的教材助手mock；真实验证报告尚未形成',
    prototype:'教材助手持续对话、引用、候选核对及采用已有mock；保留领域入库和章节关联'
}
for r in baseline['files']:
    rel=r['path'];s=docs[rel]
    assert f'> **版本**：{r["old"]}<br>' in s,rel
    s=s.replace(f'> **版本**：{r["old"]}<br>',f'> **版本**：{r["new"]}<br>',1)
    s=re.sub(r'(?m)^> \*\*状态\*\*：.*$',f'> **状态**：{statuses[rel]}<br>',s,count=1)
    s=re.sub(r'(?m)^> \*\*更新日期\*\*：.*$','> **更新日期**：2026-11-09<br>',s,count=1)
    s=re.sub(r'(?m)^> \*\*评审记录\*\*：.*$','> **评审记录**：用户确认教材助手原型暂告一段落并授权同步；作者复采截图与走查，不等于真实解析或M1工程Gate通过<br>',s,count=1)
    s=re.sub(r'(?m)^> \*\*修订说明\*\*：.*$',f'> **修订说明**：{r["old"]} → {r["new"]}，同步教材助手持续对话、引用、候选核对和采用，补充截图及实现边界；未改原型源码，逐文件记录见M1决定登记§26<br>',s,count=1)
    docs[rel]=s

replace(prd,'管理员通过原页、渲染后的候选及改动说明核对结果；采用后仅更新已说明范围，取消保留原结果。','''每次导入保留一段持续的教材助手对话，支持收起／展开和离开后继续。管理员点击某项“请助手修正”或“与助手讨论本章”，输入区显示明确的内容引用，可移除；浏览其他章节不会自动改换引用。未明确所指时先澄清。教材基本信息和章节关联仍用原有管理操作，不把配置表单也改成解析对话。

管理员通过原页、渲染后的候选及改动说明核对结果。候选显示待核对、已采用、未采用或已被后续候选替代；“继续修正”基于同一引用的当前候选继续，修改前内容仍可查看，尚未采用的候选不成为领域入库来源。“采用结果”才更新已说明范围，“不采用”保留现有解析结果。候选基于的原内容已变化时阻止覆盖，要求重新引用核对。''')
paragraph(prd,'> **操作与证据：**','> **操作与证据：** [交互§1.2](design/Interaction_Design.md#12-按章节核对与重新解析)已对应教材助手TA系列截图与mock走查，覆盖引用、连续修正、核对、采用／放弃及恢复；未新增手工内容编辑器。四例真实提取试验仍按原[试验报告](validation/Content_Representation_Trial.md)解释。当前原型只执行预设对话结果，“补充材料”只记录文件名，不上传或识别；不能据页面操作宣称真实Agent纠错、全册解析或无人核对导入已完成。')
replace(prd,'对既有四例与Agent对话，要求补图、拆解法或纠正结合次序；核对局部改动后采用／取消，测试歧义澄清和失败保留；只提交题目，再提交解法','对既有四例与Agent对话，引用单项／章节，补图、拆解法或纠正结合次序；核对修改前后与原页，继续修正，再采用／不采用；切换章节、刷新恢复、来源已变和失败重试；只提交题目，再提交解法')
replace(prd,'对话与改动范围可追溯，非目标内容不被改变；取消不覆盖；仅题不带解法','对话、引用与候选状态可追溯，浏览不改变引用，非目标内容不被改变；未采用或来源过时不覆盖；仅题不带解法')

replace(content,'[M1 PRD v0.20]','[M1 PRD v0.21]')
anchor='**四例纠错的预期。**'
addition='''**对话与候选的采用规则。** 一个教材导入记录承载一段持续对话；管理员消息、引用、候选与采用记录属于内容准备上下文。单项引用带上当前内容身份和版本，整章引用说明选定范围。查看其他章节不改引用；移除引用后，如仍不能确定所指，应重新澄清。刷新和返回后保留对话、未发送文字及助手展开状态；不重建一套独立会话管理。

| 候选状态 | 内容含义与允许动作 | 保存影响 |
| --- | --- | --- |
| 待核对 | 查看修改前、修正后和原页；继续修正、采用或不采用 | 旧解析结果继续作为当前内容，候选尚不能被当作已入库结果 |
| 被后续候选替代 | 同一明确引用继续修正时产生新版；旧版仍可查看 | 不再提供旧版采用入口，新版仍需核对，不能把两版拼接重复入库 |
| 已采用 | 对比来源后确认写入；保留当时结果快照 | 只改引用范围；同一题拆出多个解法仍引用同一父题，既有领域对象和章节采用不被覆盖 |
| 未采用 | 明确放弃本次候选，仍保留对话及候选记录 | 原解析结果不变，不误记为解析失败或学生负证 |

若候选形成后，源内容已经有新修订，采用必须被阻止并要求重新核对；不能只检查候选文本可渲染。已提交但尚未入库的内容在采用修正后标记过时，管理员重新提交新结果；已入库领域定义和实例继续走领域维护，教材Agent不代为更新。编号、父题引用及版本检查由程序执行，不要求管理员输入编号或手工改结构。

当前mock在`flow.assistant`保存消息、引用、输入及展开状态，候选保留修改前后快照与处置状态。这说明交互所需信息，不规定生产数据库Schema或消息协议。现有`reparseCandidate`仍是预设结果函数；识别少量演示措辞不等于LLM理解任意纠正要求。“补充材料”只记文件名，不保存文件内容或自动核销缺页，真实上传、读取、范围校验及候选语义检查必须由工程落实。

'''
replace(content,anchor,addition+anchor)
replace(content,'现有重新解析、提取模板与匹配都是固定mock，尚无本轮规定的教材导入Agent对话。','现有教材助手已表达持续对话、引用、候选修正与采用；解析结果、提取模板与匹配仍为固定mock，没有真实Agent推理和工具执行。')

replace(interaction,'[M1 PRD v0.20]','[M1 PRD v0.21]');replace(interaction,'[内容与模型规格 v0.19]','[内容与模型规格 v0.20]')
replace(interaction,'§1.2 Agent对话、§1.5方法适用范围的待承接修正','§1.2已落地的教材助手mock及§1.5方法适用范围的待承接修正')
replace(interaction,'![T02 整批书页及原型处理选项](assets/domain-material-v0.1/T02-batch-pages.png)','![TA01 必选领域及整批样例输入](assets/material-assistant-v0.1/TA01.png)')
paragraph(interaction,'**M1-D01-S03：','**M1-D01-S03：进入持续对话与章节内容工作区。** 整理完成后左侧为“教材助手”，右侧是可收起的章节目录以及“解析内容／章节关联”。助手可收起和展开；章节内容仍按“题目、教材解法、知识”显示。点击章节只改变浏览范围，不改变对话已引用的对象。每次导入保留自己的对话、输入草稿和助手展开状态，离开后可回来继续，不新增聊天列表。')
replace(interaction,'![T03 章节与三类解析内容](assets/domain-material-v0.1/T03-parsed-chapter.png)','![TA02 教材助手与按章组织的解析内容](assets/material-assistant-v0.1/TA02.png)')
a=docs[interaction].index('### 1.2 与教材导入 Agent 对话核对和纠错');b=docs[interaction].index('### 1.3 手动维护领域模型',a)
docs[interaction]=docs[interaction][:a]+'''### 1.2 与教材导入 Agent 对话核对和纠错

本节对应M1-R03／A03。当前已能在同一个工作区走查对话、引用、候选对照与采用，数据为固定mock，不执行真实解析。教材信息、领域入库和章节关联继续使用各自的管理操作；这里不增加手工公式、图表或内容块编辑器。

**M1-D01-S04：查看内容与原页。** 点击内容名称查看只读详情；候选核对时也可点“查看原页”，按页码切换。原页与渲染结果服务于核对，不把截图当成结构化内容。公式、表格和图形随其所属题目、解法或知识呈现。

![TA05 在候选核对中查看原页](assets/material-assistant-v0.1/TA05.png)

**M1-D01-S05：引用并提出要求。** 单项操作“请助手修正”将该项带入输入区；“与助手讨论本章”带入章节范围。输入框上方显示“已引用”及内容名称，可点击×移除。管理员输入“这里是两种解法，请分别提取”，发送后消息保留当时引用。浏览另一章不会悄悄改成对该章执行修改；引用不明时先澄清。

![TA03 明确引用后在对话中说明问题](assets/material-assistant-v0.1/TA03.png)

**M1-D01-S06：核对候选并继续修正。** 助手返回改动说明及结果卡，显示原内容与候选数量、候选名称和待核对状态。点“查看结果”在右侧展示内容；“修改前／修正后”切换比较，“查看原页”核对出处。“返回内容列表”只退出查看，不采用也不丢弃候选。下图将一条合并解法拆为两条，仍属于同一道题。

![TA04 同题两条解法的候选核对](assets/material-assistant-v0.1/TA04.png)

若仍有问题，点结果卡“继续修正”将原引用带回输入框，在同一次导入对话中继续说明。新版候选出现后，旧版标为“已由后续候选替代”，只能回看，不能再采用；新版仍须管理员决定。刷新页面后对话和候选保留，当前输入草稿也恢复，可再次点“查看结果”继续核对。

![TA06 继续修正、保留历史候选并刷新恢复](assets/material-assistant-v0.1/TA06.png)

统计图按结构化候选渲染，不能只用“已补齐”文字代表结果。TA10为右侧核对区域的完整截图，展示三张图及数据／单位；没有独立图表入库类型。

![TA10 三张统计图的完整候选渲染](assets/material-assistant-v0.1/TA10.png)

**M1-D01-S07：采用或放弃，再决定提交。** “采用结果”只将指定范围候选写为当前解析内容，结果卡显示已采用；“不采用”保留旧解析内容，并显示未采用。两种操作均保留对话记录。若形成候选后原内容已变化，阻止旧候选覆盖并提示重新引用核对。状态和引用含义见[内容规格§3.1](Content_and_Model_Reference.md#31-提取什么以及怎样保存图表和来源)。

![TA07 采用后只更新解析内容](assets/material-assistant-v0.1/TA07.png)

![TA11 未采用的候选保留记录，当前内容不变](assets/material-assistant-v0.1/TA11.png)

回到内容列表后再选择提交题目、解法或知识，进入领域管理。题目可单独提交；只选解法时需带上其父题或复用已入库同题。采用本身不生成模板、不建立章节关联。已采用新版本会使此前尚未入库的旧待办过时；已入库对象不随之改写。后续操作沿用§1.4。

![TA08 显式提交后进入领域待入库内容](assets/material-assistant-v0.1/TA08.png)

**失败与缺失材料。** 对话中说明失败或需要补充什么，保留已有内容和候选；失败消息提供“重试”，不能因失败而保存半份结果。缺附页时先请求材料，不猜测不可见条件；“补充材料”接受选择PDF或图片。当前mock只保存文件名和提示，没有上传或识别文件，也没有由此补全附页的结果，不得将这一画面标为真实补页成功。

![TA12 失败保留结果并允许重试](assets/material-assistant-v0.1/TA12.png)

![TA13 缺失附页先请求材料，不编造候选](assets/material-assistant-v0.1/TA13.png)

当前实现只对四例中的预设请求返回固定候选，未覆盖的要求保留在对话并说明限制；不把演示关键词匹配当成通用Agent能力。初次批量解析、真实等待／取消、文件持久化、任意内容的语义纠错与可靠版本事务仍须工程实现。采用结果不等于领域模型或整册教材已可供学生使用。

'''+docs[interaction][b:]
replace(interaction,'![T14 添加章节关联](assets/domain-material-v0.1/T14-add-chapter-link.png)','![TA09A 领域入库后添加章节关联](assets/material-assistant-v0.1/TA09A.png)')
replace(interaction,'![T15 在弹框编辑采用的方法](assets/domain-material-v0.1/T15-edit-chapter-link.png)','![TA09B 章节方法继续在关联弹框中编辑](assets/material-assistant-v0.1/TA09B.png)')
replace(interaction,'![T16 只读章节关联表](assets/domain-material-v0.1/T16-chapter-links.png)','![TA09 章节任务及方法采用结果](assets/material-assistant-v0.1/TA09.png)')
replace(interaction,'教材必选领域、批量样例、原页查看和重新解析','教材必选领域、批量样例、原页查看及教材助手对话纠错')
replace(interaction,'### 4.1 本轮替代的旧方案','''教材助手本批另采15张TA截图，对应§1.1／1.2及§1.4；[采集清单](assets/material-assistant-v0.1/capture-manifest.json)记录源码基线、步骤、独立浏览器及图片哈希，[自检记录](assets/material-assistant-v0.1/review.json)记录17项浏览器检查、截图核对和文档检查。原型源码本批未改，旧测试与真实提取报告不改写。

### 4.1 本轮替代的旧方案''')
replace(interaction,'目标侧旧“查看Belief更新与Evidence”','''教材单次“重新解析”弹框及T03／T04／T05／T08／T09的原操作说明由§1.2和TA系列替代；章节关联改用TA09系列表达现行工作区。旧图片保留在原清单，不能再作为当前助手的截图。

目标侧旧“查看Belief更新与Evidence”''')
paragraph(interaction,'本轮修订§1.2教材Agent对话','本轮将已完成的教材助手原型同步到§1.1／1.2及§1.4并复采截图；§1.5跨章节方法适用仍待实现，§1.7／2.4／3.1的课程应用、反馈与任务交接仍须在工程接收中标明缺口。学生源码及此前截图保持。真实Agent、意图识别、不可变事件、Evidence解释与概率服务未因mock对话完成而接通。目标侧Evidence查询仍以§3.2为准，不改算法或权限。')

replace(m1,'| M1-D01 | 独立原型：必选领域、批量样例、章节三类内容、原页查看、重新解析、选择提交、继续与删除；本批PRD／规格／截图已同步 | Agent对话解析纠错已确认；原型仍为旧单次重解析，未实现持续对话。真实识别、完整建模及人工负担待验证 |','| M1-D01 | 教材助手持续对话、单项／章节引用、候选核对、继续修正、采用／放弃及恢复已有mock；15张TA截图与规格同步，保留领域入库和章节关联 | 交互收束；真实Agent、文件上传识别、候选语义质量、整册建模与人工负担仍待验证 |')
replace(m1,'上一批同步已确认原型并重采截图；本批补课程交接规格，不改页面或截图；新Task角色约束仍待适配。','本批同步已确认教材助手并采集TA截图，未修改原型源码；课程应用和新Task角色等剩余差异按§6核对。')
paragraph(m1,'**本次交付与下一步。**','**本次交付与下一步。** 教材助手图文已同步，详见交互§1.2和决定登记§26。接下来按§6做一次有边界的工程接收核对：从管理员应用课程，到学生选用、教学／检测、评价反馈及主动任务返回，逐项确认输入输出、负责人和已有规格位置。LC-02–04语义实例已写明，不重复讨论已定规则；只处理阻塞真实主流程的问题，再形成首条工程实施路径。')
replace(m1,'教材Agent对话、跨章方法适用、帮助分类和学习机会输入已写入PRD与内容规格；原型未改。','教材Agent对话、跨章方法适用、帮助分类和学习机会输入已写入PRD与内容规格；教材助手mock现已同步截图，其他已登记适配差异不据此关闭。')
paragraph(m1,'**下一步顺序。**','**下一步顺序。** 先完成主流程工程接收核对，采用PRD v0.21、内容规格v0.20、交互规格v0.19和验证计划v0.2，区分产品待决、已定待实现、真实验证待取得三类事项。核对后编写首条真实路径的工程设计与分步交付计划：教材Agent读取原件、形成候选并采用，领域入库与课程应用，再衔接学生事件、评价和反馈。只在发现阻塞业务决定时请用户介入；本轮不继续扩大UI，不把整册或参数校准宣告通过。')

replace(design,'v0.20：教材Agent对话、帮助判定、目标章节方法及验收；既有评价规则保留','v0.21：教材助手持续对话、引用、候选处置与恢复；既有模型和评价规则保留')
replace(design,'v0.19：Agent候选与采用、跨章方法、帮助分类和学习机会输入；算法与门槛不变','v0.20：对话引用、候选生命周期、过时待办及mock／工程边界；算法与门槛不变')
replace(design,'v0.18：§1.2及§1.5明确Agent对话与方法适用范围待承接；既有截图注明历史边界，原型未改','v0.19：§1.2教材助手逐步对应TA截图；§1.5方法适用及其他交接差异仍单列')
replace(design,'| [领域与教材截图及检查]', '| [教材助手截图及检查](assets/material-assistant-v0.1/review.json) | 15张独立浏览器截图与17项mock检查，覆盖持续对话、引用、候选及入库关联交接；未调用模型 |\n| [领域与教材截图及检查]')
docs[design]+='\n教材助手本轮图文收束见[登记§26](../../DECISIONS.md#26-教材助手持续对话原型与文档同步)。TA系列替代旧单次重解析及章节工作区的操作截图，旧领域及其他业务截图仍按各自基线解释。下一步以M1主流程检查表为唯一问题清单，先核对工程输入，不另开交互优化专题。\n'

replace(mvp,'教材解析、待入库处理','教材助手持续对话、候选核对及采用、待入库处理')
docs[mvp]+='\n教材助手本轮已完成mock图文同步，当前版本及截图见[M1交互规格](m1/design/Interaction_Design.md#12-按章节核对与重新解析)。下一步按[M1主流程检查](m1/README.md#6-主流程闭环检查2026-11-09)核对工程接收输入；不把对话原型当作真实Agent、整册建模或评价服务完成。\n'

replace(engineering,'[PRD v0.20]','[PRD v0.21]');replace(engineering,'[内容规格v0.19]','[内容规格v0.20]');replace(engineering,'[交互规格v0.18]','[交互规格v0.19]');replace(engineering,'[验证计划v0.1]','[验证计划v0.2]')
replace(engineering,'原型单次重解析不是已实现Agent','已有持续对话与候选采用mock；预设措辞和结果函数不是生产Agent，补充材料只存文件名')
replace(engineering,'当前23个`tests/*.test.mjs`中，`test`列9个','当前24个`tests/*.test.mjs`中，`test`列10个')
replace(engineering,'本轮不改package或原型；工程接收时','教材助手测试已列入当前package脚本，本轮文档同步未改脚本；工程接收时')
docs[engineering]+='''
**教材Agent的第一条实现路径。** 接收前按PRD§3.3、内容§3.1及交互§1.2固定来源文件、导入身份和内容版本；工程设计须说明对话上下文和引用怎样传入、哪些工具能读原件／产生候选、结构校验和预览怎样执行，以及采用如何检查版本并写入。真实文件保存与读取、任意内容纠错、失败恢复和采用事务尚未实现，不能把原型的预设函数直接当成生产行为。领域待办、模板／实例关联及章节采用沿原职责连接，不让助手跨过这些操作自动写模型。

本批对当前构建复跑教材助手、教材主流程、导入生命周期和入库弹框四个测试文件，共17项通过；只证明有限mock的交互及关系，未执行上方另外9个未接线用例。证据见[教材助手复核](../design/assets/material-assistant-v0.1/review.json)。下一步先完成M1主流程输入输出核对，再创建工程设计与交付计划；本节不替代完整设计或宣布工程Gate通过。
'''
replace(validation,'[PRD v0.20]','[PRD v0.21]');replace(validation,'[内容与模型规格 v0.19]','[内容与模型规格 v0.20]');replace(validation,'[交互规格 v0.18]','[交互规格 v0.19]')
replace(validation,'[决定登记§25](../../DECISIONS.md#25-检视意见采纳与教材导入agent)','[决定登记§25／26](../../DECISIONS.md#26-教材助手持续对话原型与文档同步)')
replace(validation,'本轮纠错验证仍限于既有四例C02、C03、C05和C06，不再扩大样例范围。','本轮纠错验证仍限于既有四例C02、C03、C05和C06，不再扩大样例范围。教材助手的引用、候选、恢复及入库交接已有mock截图和浏览器检查，见[交互复核](../design/assets/material-assistant-v0.1/review.json)；这些预写结果不计入真实提取准确率或Agent纠错成功率，以下真实验证仍待执行。')
replace(validation,'本轮仅交付计划和文档自检，未新增真实模型调用结果、学生实验结果或截图。','本轮承接教材助手mock交互截图与浏览器复测，真实计划和门槛保持；未新增真实模型调用或学生实验结果。')
replace(validation_index,'| v0.1：教材Agent四例纠错','| v0.2：教材Agent四例纠错')
replace(validation_index,'本轮仅制定验证合同，未重新执行提取或模型调用。','教材助手mock交互已复测并同步TA截图；本轮未重新执行真实提取或模型调用。')

replace(prototype,'重新解析后采用结果，选择题目／解法／知识提交领域','在教材助手中引用内容、说明问题，核对候选并继续修正，采用后选择题目／解法／知识提交领域')
replace(prototype,'| 教材 | 必选领域、批量样例、章节三类内容、详情及原页、按说明重新解析、单独选择题目和解法、待入库、章节关联、继续与删除草稿 |','| 教材 | 必选领域、批量样例、持续助手对话、引用单项／章节、原页和候选对照、继续修正、采用／放弃、刷新恢复；分别提交题目和解法、领域待入库与章节关联仍保留 |')
replace(prototype,'| 真实服务 | 解析、重新解析、生成和语义匹配均为mock；本原型不调用LLM，不验收真实PDF／全册建模 |','| 真实服务 | 助手仅对预设情境返回mock结果，未覆盖要求说明限制；补充材料只存文件名、不上传识别。不调用LLM，不验收真实PDF／全册建模 |')
replace(prototype,'- `src/components/TextbookImport.vue`、`MaterialContents.vue`：导入、章节解析及关联。','- `src/components/TextbookImport.vue`、`MaterialContents.vue`、`MaterialAssistant.vue`：导入、助手对话、候选核对及章节关联；`src/model/material-assistant.ts`保存预设对话与候选状态，不是真实Agent。')
replace(prototype,'本轮不改原型源码，使用当前已有构建；运行下列学生相关检查共29项通过','此前学生批次使用当时构建，运行下列学生相关检查共29项通过')
replace(prototype,'结果见[本轮复核]','结果见[该批复核]')
docs[prototype]+='''
教材助手当前走查：载入四例样例并开始整理，在“教材解法”点“请助手修正”，输入“两种解法请分开”；查看修改前后和原页，继续要求核对公式与单位，再采用或不采用。三张统计图可走补漏，缺附页保持待补；浏览其他章节不改变引用，刷新保留消息和输入。采用只更新解析内容，提交领域、处理实例及回教材关联仍是明确操作。

本次文档同步复跑下列四个文件共17项通过；TA系列15张新截图及采集脚本见[清单](../design/assets/material-assistant-v0.1/capture-manifest.json)，结果见[复核](../design/assets/material-assistant-v0.1/review.json)。本轮使用已有构建，未修改源码或重新进行真实模型实验。

```powershell
node --test --test-concurrency=1 tests/material-assistant.test.mjs tests/material-flow.test.mjs tests/import-lifecycle.test.mjs tests/intake-dialog.test.mjs
```
'''

docs[decisions]+='''
## 26. 教材助手持续对话原型与文档同步

**2026-11-09，M1-DEC-019的交互落地。** 用户确认教材导入原型暂告一段落，授权将持续对话、引用内容、核对候选和采用结果同步到M1相关文档并补图。本轮未新定算法、领域关系或课程范围，也未修改原型源码。

- 每次导入保留一段教材助手对话。单项／章节引用明确可见，浏览章节不改变引用，离开和刷新后可继续；不增加聊天列表或手工解析编辑器。
- 候选可对照修改前后及原页，继续修正后保留历史版本；采用、未采用及被替代状态分明。来源已变阻止旧候选覆盖，采用只更新指定解析内容。
- 教材基本信息和章节关联仍用管理操作。采用不等于领域入库，题目和解法继续分别选择；旧待办过时、已入库对象不覆盖、解法指向父题及方法模板等约束保持。
- 对话、候选与错误反馈为mock。补充材料只记录文件名，预设结果不证明真实Agent纠错或整册建模完成；原真实试验和既有截图保留。

正文归属：PRD§3.3／A03规定使用行为，内容§3.1规定引用、候选及写入边界，交互§1.1／1.2／1.4逐步对应TA截图。工程与验证入口同步当前版本、测试和真实实现待办。

本轮独立浏览器采集15张截图，复跑四个文件17项mock检查；不访问用户浏览器数据或调用LLM。[截图清单](m1/design/assets/material-assistant-v0.1/capture-manifest.json)和[复核记录](m1/design/assets/material-assistant-v0.1/review.json)保留实际来源，[修改前基线](../../src/mvp_foundation/m1/design-reviews/20261109-material-assistant/baseline.json)保留文档与源码哈希。此记录不宣告工程Gate或真实质量通过。

| 文件 | 旧版 → 新版 | 修改内容 |
| --- | --- | --- |
'''
purposes=['持续对话、引用、候选处置和验收','引用、候选生命周期与程序／Agent边界','逐步操作与15张TA截图','D01当前进度和下一步接收核对','当前版本、资产及历史替代','M1当前入口与工作安排','本批修订、验证和范围记录','真实Agent实现接收、测试数量及交接','mock证据与真实验证区分、更新上游','验证计划入口及实际状态','现行助手用法、限制和复跑命令']
for r,purpose in zip(baseline['files'],purposes):
    docs[decisions]+=f'| `{r["path"]}` | {r["old"]} → {r["new"]} | {purpose} |\n'
docs[decisions]+='\n**下一步。** 按M1工作表§6核对管理员课程应用、学生选用、活动与题目、事件到评价、反馈及主动任务返回的输入输出。区分产品待决、已定待实现与真实验证事项；仅补工程前必需的业务缺口，再形成首条真实主流程的工程设计和交付计划。不重新开启外围UI打磨，也不因本轮图文完成而取消整册要求。\n'

for r in baseline['files']:
    p=root/r['path'];before=(batch/'before'/r['path']).read_bytes()
    ending='\r\n' if before.count(b'\r\n')==before.count(b'\n') and b'\r\n' in before else '\n'
    p.write_text(docs[r['path']],encoding='utf-8',newline=ending)
print(json.dumps({'updated':len(docs)},ensure_ascii=False))
