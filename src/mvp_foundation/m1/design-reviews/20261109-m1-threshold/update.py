"""Apply the confirmed threshold decision to the captured working baseline."""
from pathlib import Path
import json
import re

batch = Path(__file__).resolve().parent
root = batch.parents[4]
baseline = json.loads((batch / 'baseline.json').read_text(encoding='utf-8'))
texts = {r['path']: (batch / 'before' / r['path']).read_text(encoding='utf-8') for r in baseline['files']}
prd, content, interaction, m1, design, mvp, dec, eng, validation, validindex, m2, concept, system = texts

def rep(p, old, new):
    assert old in texts[p], (p, old[:100])
    texts[p] = texts[p].replace(old, new)

def para(p, start, new):
    pattern = r'(?m)^' + re.escape(start) + r'[^\n]*'
    assert re.search(pattern, texts[p]), (p, start)
    texts[p] = re.sub(pattern, lambda _: new, texts[p], count=1)

def section(p, number, new):
    pattern = rf'(?ms)^### {re.escape(number)} .*?(?=^### |^## |\Z)'
    assert re.search(pattern, texts[p]), (p, number)
    texts[p] = re.sub(pattern, lambda _: new.strip() + '\n\n', texts[p], count=1)

# Product rule and stage boundary.
para(prd, '目标按Belief的有效判断和证据基础逐方法、逐方面核对', '目标按实际方法及所需方面分别判断：有对应有效Evidence且适用条件成立时，以最近一次合格证据更新所得的概率与全局阈值0.90比较，达到或超过阈值即达标；已有适用证据但低于阈值为需加强，没有对应证据或条件无法核对为待确认。仅教学预测上升不触发达标。任选一种方法须由同一允许方法满足所有所需方面；分别达标须逐法满足，不取平均。固定题数门槛已由M1-DEC-021替代，迁移与保持的证据资格仍见[内容规格§4.10](design/Content_and_Model_Reference.md#410-试用达标标准belief更新与学生反馈)。')
para(prd, '同一次作答可支持父子及多个方面', '同一次作答可支持父子及多个方面，但对同一判断分项只更新一次；共同来源、重复引用和重试可查，后验Belief不能回灌成新Evidence。未答、含糊、识别故障或条件不足不是负证。M1全局达标阈值为0.90，对每个方法／方面分别生效；不设逐Task或逐目标阈值，不新增阈值配置页面。有目标适用Evidence才可判断，题数用于解释依据，不再设“两题达标”的额外门槛。证据、算法及目标规则见[内容规格§4.16–4.21](design/Content_and_Model_Reference.md#416-m1-belief按方法和方面保存分项概率)。')
rep(prd, '用户以M1-DEC-004确认门槛；正式内容采用与其他章节标准仍需准备，不能机械套用样例', '原题数门槛已由M1-DEC-021的全局0.90替代；其他章节仍需准备判据、迁移条件和保持间隔，不再逐章另定概率阈值')
rep(prd, '本例试用门槛经M1-DEC-004确认，细则见准备参考§4.10', '当前达标门槛采用M1-DEC-021的全局0.90，证据资格细则见内容规格§4.10')
rep(prd, '旧概念／系统设计及 Learning Space 基线的相关摘要、原型和内容包仍需按[决定登记§19](../DECISIONS.md#19-kc-task复合-task-与依赖更新合同)迁移，不能照旧直接使用', '工程须识别旧摘要、原型和内容包与[现行合同](../DECISIONS.md#19-kc-task复合-task-与依赖更新合同)的差异，不照旧直接实现；这是工程输入适配，不是Evolution版本演进功能')
rep(prd, '新模型合同冻结、资产正式使用前', '对应模块工程设计和旧资产复用前')
rep(prd, '工程接收前需确认每项必要输入有生产入口', '工程设计属于工程阶段；工程阶段包含工程设计、编码实现、集成与验证，不将编写工程设计称为“工程前准备”。开始工程设计不代表编码已经开始或全部产品验收通过。工程接收前需确认每项必要输入有生产入口')
rep(prd, '如目标要求变化引起重新对照', '如目标要求变化引起重新对照') if '如目标要求变化引起重新对照' in texts[prd] else None

# Core content: replace criteria in place, do not add a contradictory appendix.
para(content, '第三例有意使用不改变评价含义的修订。', '第三例仅说明普通内容维护。Evolution相关的定义演进、跨版本兼容判定、Belief迁移及历史重算后置M2/M3，不再作为M1产品讨论或工程前置。M1保留实际使用的内容依据与只追加事件；不改写旧事实，不据此建设版本迁移平台。管理员更换目标身份仍不属于同组合普通更新。')
para(content, '这些研究不提供本任务', '这些研究不提供本任务的统一掌握阈值或保持间隔。M1-DEC-021采用0.90作为全局试用阈值，替代M1-DEC-004的固定题数门槛；本例七天仍是保持证据的资格条件，不是已验证的自然遗忘规律。数值、资格判据和实际教学效果均须真实验证。')
para(content, '本表固定的是解释边界。', '本表固定的是解释边界；达标统一使用§4.20的0.90阈值，不再逐章另设题数门槛。逐章仍须准备执行判据、迁移变化和保持条件，验证工作检查解释及预测质量，不由实现者临时猜测。')
section(content, '4.10', '''### 4.10 试用达标标准、Belief更新与学生反馈

**M1-DEC-021确认全局阈值θ=0.90。** 每种方法的独立、理解、迁移和保持分别判断，不合成一个总概率。原M1-DEC-004的“两题求解解释、一次迁移、一次保持即达标”计数规则被替代；本例的判据、迁移条件和七天间隔仍用于判断Evidence是否合格。0.90是试用决策，不是已校准的科学常数。正式题目及其他章节内容仍需核对，不能因门槛确定而宣布整册就绪。

| 方面 | 合格Evidence必须表达什么 | 达标与反馈 |
| --- | --- | --- |
| 独立完成 | 无当题实质帮助，按适用方法完整求出增加后的数量；单个答案不足以识别方法时不归因 | 对应证据更新后的概率≥0.90；学生看到“你能独立完成这类任务”，注明实际范围，不显示学会百分比 |
| 理解与解释 | 能结合具体数据说明参照量、增加量与总量关系；机械照读、没解释或只算对不构成理解正证 | 本方面单独达到0.90；不能借独立概率代替理解 |
| 迁移 | 在明确的新变化下自行使用方法，参照经历及本次条件可核对；仅换数、重复已教表格不自动是迁移 | 合格迁移Evidence更新该概率，达到0.90才达标；一次成功仍可先肯定当次表现 |
| 保持 | 以独立和理解达到阈值时所用的最近合格表现为本例基准；至少7×24小时后，在未展示解法的新题中再次完整求解与解释 | 合格保持Evidence更新该概率，达到0.90才达标；到时不等于达标，一道成功也不自动达标 |

期间练习如实记录，不把“七天后仍能做”说成“七天没有复习也不会忘”。保持基准使用实际表现时间，后续验证沿用该检查依据，不按每条消息或查看记录重启计时。初次达标后出现新反证，正常更新概率并按同一阈值判断，不删除旧证据，也不另设重新做两题的恢复流程。

迁移的新颖性必须有依据；系统内没有旧练习不等于校外从未接触。当前表格例只提供一次合格迁移时，从先验更新为约0.773，仍未达标。下一次必须是符合所选迁移条件的另一条有效表现，不能重复同一已教表格凑次数；若当前内容不能提供，就保留未达标和供题限制。其他章节需准备可实际取得证据的迁移条件，这属于内容准备，不另建概率维度。

同一次作答可以分别更新多个方面，但对同一方法／方面只更新一次。没有有效证据时为待确认；已有适用证据但概率低于0.90时为需加强，反馈可说明“已有成功表现，还需确认”，不把低于阈值一律说成做错。未决、不适用、处理失败均不作负证。达标比较使用证据更新后的概率，教学L形成的预测只供后续更新及教学选择，不能单靠讲解次数使目标达标。

| 实际情形（从0.50开始，期间无L转移） | 分项与目标结果 |
| --- | --- |
| 听例题并在提示下完成练习 | 不形成独立成功，不用受助表现填迁移或保持 |
| 两题独立完成且解释清楚，其中一题满足指定表格迁移 | 独立、理解各约0.920，达标；迁移约0.773，未达标；保持无证据，待确认 |
| 只给正确答案，没有足够方法过程或解释 | 保留当题正确；无法归因的方法及理解不更新 |
| 基准七天后首次合格保持表现 | 保持约0.773，仍未达标，不宣称永久保持 |
| 达标后出现明确反证，随后取得新的合格表现 | 继续更新原概率并与0.90比较；可以下降或恢复，没有另加固定题数要求 |

E2后的反馈示例：“这两题你都能独立完成，也解释清楚了原因。这次换成表格也做对了，但迁移还需要更多合格表现来确认；隔一段时间能否继续完成，还没有检验。”当题反馈、分项状态和整个目标是否达成分别说明，不要求学生看原始概率。''')
para(content, 'Evidence分别保留r=1/4', 'Evidence分别保留r=1/4、r=1/5、原量、过程、帮助和表征。同一定义下这两题共同使该方法独立概率达到约0.920，可按全局阈值判断；不再要求目标累计两道1/4题。目标仍核对实际适用范围：只有1/4表现不能凭共享概率声称取得了1/5的实际证据；所需范围没有对应Evidence时为待确认。范围覆盖不是新概率索引，换目标不复制Belief。')
rep(content, '学习预测不能补足两题／迁移／七天的证据门槛', '学习预测不单独触发0.90达标；迁移与七天保持的Evidence资格仍须满足')
section(content, '4.20', '''### 4.20 从 Belief 与证据基础派生目标达成

M1所有Task、方法及评价方面共用θ=0.90，不按任务或目标另设阈值，不开放后台阈值配置。LearningTarget继续选择Task Claim、要求的方法及方面，并说明适用范围和证据条件；不新增TargetBelief或学习要求实体。

1. 定位实际方法／方面的Belief及适用于目标的Evidence。没有对应有效证据、所需范围未覆盖或资格无法核对时为待确认；先验0.50不是测得能力，课程缺口和处理失败另列。
2. 有适用证据时，比较最近一次有效Evidence更新后的观测概率p_obs：p_obs≥0.90为已达标，p_obs<0.90为需加强。原题数门槛和“历史反证永久阻止达标”均取消；正负证据由既定算法正常累计，未决不作负证。未四舍五入的实际值用于比较。
3. 学习转移后的计算概率用于下次更新，不能单靠L跨过阈值宣布达标。迁移和保持本来就不加L；其Evidence仍须满足新变化、间隔及实际表现条件。
4. 指定A只看A；任选A或B，须有同一种允许方法的所有所需方面达标；要求两法分别达标，则逐法满足。不能平均八项概率，也不能拼接A的独立与B的理解。所需项未全达标时整个目标未完成。
5. 保留当次依据与状态事件。新证据使概率降到阈值以下就更新为需加强，后来升回阈值就恢复达标，不清空概率、不另加答错恢复流程。Evolution版本演进和历史重算后置，不在M1定义跨版本承接算法。

按§4.19，E2后A只有独立、理解达标；迁移0.772727未达标、保持待确认。E4后A独立、理解仍达标，迁移和保持均为0.772727，目标尚未完成。若以后取得另一条真正符合各自条件的正证，对应概率可升到0.920382；是否安排与接受继续检测沿既有任务及学生控制规则，不能为了越阈值无限出题。

0.90只是全局试用门槛，不代表算法或参数已经校准。它与PRD质量验收中的“判断准确率至少90%”是两个概念：前者决定个人目标状态，后者检验系统质量。''')
rep(content, '参数或解释规则改变时生成新版本并记录采用范围，不覆盖旧结果；', '参数校准使用隔离验证记录，不据此建设M1版本迁移流程；Evolution的参数／定义演进、兼容判定和旧Belief迁移后置M2/M3。实际采用依据与原事件仍保留；')
rep(content, '各有一次合格新题，尚不足两题要求', '各有一次合格新题，概率低于当前0.90阈值；旧图仍按原计数门槛展示')
para(content, '| 3. 对照目标、反馈 |', '| 3. 对照目标、反馈 | Evaluation核对方法与Evidence资格，分别将观测概率与0.90比较；Interaction据有效结果表达 | “独立求解和解释已达到本次要求。这次表格也做对了，但迁移还需要合格表现确认；保持尚未检验。”迁移0.772727未达标，不宣称整章或两法都掌握 |')
para(content, '| 7. 更新并结束后续任务 |', '| 7. 更新并结束后续任务 | Evaluation按E4及实际间隔、练习背景更新；Interaction记录本次任务执行结局，再检查目标是否达成 | A独立／理解0.975189，迁移及保持各0.772727。检测执行完成，但保持目标仍未达标；不能宣布原目标已解决。继续检查需有必要性及学生选择，不立刻连续催测；B不凭A达标 |')
para(content, 'E1／E2／E4同时服务多个方面时', 'E1／E2／E4同时服务多个方面时，共同作答身份不变。目标使用0.90阈值及适用Evidence资格，不要求学生查看概率，也不再用固定题数另设门槛。保持基准取实际表现时间，不取后台处理或重新打开页面的时间。')
rep(content, '一次独立正证也不满足两题门槛', '从先验开始的一次独立正证约0.773，未达到0.90')
rep(content, '本例E4属于此情况', '本例E4保持概率仍低于0.90，不属于此情况')

# Visible descriptions must not keep the old success conclusion; screenshots are historical.
para(interaction, '本例两题、表格迁移及至少七天保持的试用标准', '本例现用全局0.90阈值；迁移及至少七天保持的Evidence资格见[内容规格§4.10](Content_and_Model_Reference.md#410-试用达标标准belief更新与学生反馈)。现有截图仍来自旧固定题数规则，不证明新阈值已实现。未改原型、重采截图，活动结束也不等于达标。')
para(interaction, '正常算例应呈现', '按当前阈值，E2反馈为“独立求解、解释达到要求；表格这次做对，但迁移尚未达标；保持未检验”；E4的保持0.773仍未达标。只有答案不编造方法，有算式无解释不宣布理解；服务失败与个人不足分开。原型尚未实现新阈值及FB01–03全部状态，既有截图是历史mock，工程按内容§4.20／4.24实现，不据旧图恢复题数门槛。')
rep(interaction, '**本轮范围调整。**', '**本轮阈值调整。** 本节EV截图保留原样；含旧题数门槛、一次迁移／保持即通过的文字不再是M1判定规则。目标和Evidence展示结构继续使用，实际状态按内容§4.20的0.90阈值计算。\n\n**本轮范围调整。**')

# Validation cases: new decision, same formulas/parameters; no invented real result.
para(validation, '| 同一方法用1/4及1/5', '| 同一方法用1/4及1/5两道合格新题，期间无教学 | 更新同一独立分项：0.50→0.772727→0.920382；已有目标适用证据且资格成立时达标，不再额外要求两道1/4题；完全没有目标所需范围证据则待确认 |')
rep(validation, '| 两种方法中只展示方法A的过程 |', '| 无证据、阈值相等及阈值两侧 | 无证据不显示先验为测得能力；有适用证据时0.899999未达标，0.900000达标，按未舍入值比较 |\n| E2、E4后迁移和保持 | E2独立／理解达标、迁移未达标、保持待确认；E4保持0.772727仍未达标，不按一次保持成功宣布完成 |\n| 达标后出错，再取得新正证 | 0.920382→0.698068→0.887147→0.963935，按同一阈值降级与恢复；不另设固定恢复题数，不清空历史 |\n| 两种方法中只展示方法A的过程 |')
rep(validation, '不增加成功题数或最近验证时间', '不增加成功证据或最近验证时间，也不单靠L跨阈值触发达标')
rep(validation, '按本例目标条件处理未知、待检与反证，概率高也不能越过条件', '按本例Evidence资格处理；有效反证更新概率后统一比较0.90，未决不作负证，概率高不能越过证据资格')
rep(validation, '真实计划和门槛保持', '真实验证计划保留，个人达标判定改为全局0.90')

# Engineering design is explicitly part of engineering, not a pre-engineering limbo.
rep(eng, '## 2. 进入工程的条件', '## 2. 进入工程的条件')
rep(eng, '按拟接收范围核对业务规则', '**工程设计属于工程阶段。** 工程阶段依次包含工程设计、编码实现、集成与验证。开始撰写Engineering_Design.md和Delivery_Plan.md就是开始工程设计，不再称为“进入工程之前”；本次仅更新产品文档与工程入口，尚未创建这两份工程正文。\n\n按拟接收范围核对业务规则')
rep(eng, '正式实现须满足对应范围的G3／G4责任和接收记录', '编码实现须满足对应范围的产品与设计接收记录')
rep(eng, '不重新定义谁可以应用教材', '不重新定义谁可以应用教材；Evolution版本兼容、迁移和历史重算不在M1展开')
rep(eng, '保留既定公式和初值；不实现错误评价纠正和历史重算', '保留既定公式和初值，使用全局0.90及Evidence资格判断；不实现错误评价纠正、Evolution版本迁移和历史重算')
rep(eng, '1/4与1/5共享分项但目标按实际覆盖', '1/4与1/5共享分项，目标核对适用证据并比较0.90')
rep(eng, '错误评价纠正由M2重新确认具体范围', '错误评价纠正及Evolution版本演进由M2/M3重新确认具体范围')
rep(eng, '版本及事务实现', '必要来源记录及事务实现') if '版本及事务实现' in texts[eng] else None

# Current indices; past decision records stay unchanged.
rep(m1, '公式、初值和门槛', '公式和初值')
rep(m1, '目标标准已有详规', '目标标准已有详规，当前使用全局0.90')
rep(m1, '当前没有新建统计首页', '全局0.90与工程阶段边界已由M1-DEC-021确认。Evolution版本演进不作为M1阻塞项；计时空闲口径可在工程设计中提出并确认，内容与服务条件在对应接入前落实。当前没有新建统计首页')
rep(m1, '**下一步顺序。**', '**阶段边界。** 工程设计属于工程阶段；接下来撰写工程设计和交付计划即进入工程设计工作，不等于开始编码或产品验收全部通过。\n\n**下一步顺序。**')
rep(design, '“增加四分之一”的两题及七天标准只在内容规格§4.10完整维护', '全局0.90及“增加四分之一”的证据资格、七天条件只在内容规格§4.10／4.20完整维护')
rep(design, '既定公式、初值和门槛保留', '既定公式及初值保留；达标统一为0.90，题数不再另设门槛')
rep(mvp, '工程定义技术机制', '工程设计属于工程阶段，负责定义技术机制')
rep(m2, '新增后续议题：错误评价纠正', '新增后续议题：Evolution相关定义演进、跨版本兼容、Belief迁移及历史重算，M2/M3再定具体范围；不作为M1前置。文档修订版本和原始事件留痕不因此取消。错误评价纠正')
rep(validindex, '补充同方法跨参数更新及目标覆盖', '核对同方法跨参数更新、全局0.90阈值和Evidence资格')

# New architecture file preserves v1.8 as its historical source.
new_eval = baseline['newFiles'][0]['path']
texts[new_eval] = (root / 'doc/concept-design/DeerMind_Evaluation_Space_Design_v1.8.md').read_text(encoding='utf-8')
rep(new_eval, '# DeerMind Evaluation Space Design v1.8', '# DeerMind Evaluation Space Design v1.9')
para(new_eval, '具体状态表示暂不冻结成enum', 'M1按M1-DEC-021统一采用0.90阈值：每方法／方面有适用有效Evidence时，最近一次证据更新后的观测概率≥0.90为达标，低于阈值为需加强；没有对应证据或资格无法核对为待确认。仅教学L预测跨阈值不触发达标，原固定题数及历史反证额外否决规则取消。任选方法须同一方法满足全部所需方面，分别达标须逐法满足，不平均。完整规则见[M1详规§4.20](../mvp/m1/design/Content_and_Model_Reference.md#420-从-belief-与证据基础派生目标达成)。')
rep(new_eval, '**M1采用范围（M1-DEC-020）。**', '**M1采用范围（M1-DEC-020／021）。** 全局达标阈值0.90，原题数门槛不再使用；迁移与保持资格保留。Evolution的版本演进、兼容迁移和历史重算均后置M2/M3，后文通用演进描述不是M1工程前置。')
texts[new_eval] += '\n\nv1.8 → v1.9（2026-11-09）：按M1-DEC-021采用每方法／方面共用的0.90达标阈值；固定题数不再决定达标，未知及Evidence资格保留；Evolution版本迁移后置M2/M3。既定更新算法与初值不变，旧文件保留。\n'
for p in [prd, content, m1, mvp, concept, system]:
    texts[p] = texts[p].replace('Evaluation v1.8', 'Evaluation v1.9').replace('Evaluation Space v1.8', 'Evaluation Space v1.9').replace('DeerMind_Evaluation_Space_Design_v1.8.md', 'DeerMind_Evaluation_Space_Design_v1.9.md')
# DECISIONS current summary only; sections 2 onward are preserved as historical records.
head, history = texts[dec].split('## 2.', 1)
head = head.replace('Evaluation v1.8', 'Evaluation v1.9')
head = head.replace('目标核对实际证据', '目标核对适用证据并按全局0.90逐项判定')
texts[dec] = head + '## 2.' + history

# Version and reference pass.
records = baseline['files'] + baseline['newFiles']
versions = {r['path']: (r['old'], r['new']) for r in records}
for p, (old, new) in versions.items():
    s = texts[p]
    s = s.replace(f'> **版本**：{old}<br>', f'> **版本**：{new}<br>', 1)
    s = re.sub(r'(?m)^> \*\*状态\*\*：.*$', '> **状态**：已同步M1全局0.90阈值及工程阶段边界；未改原型，真实实现与校准未验证<br>', s)
    s = re.sub(r'(?m)^> \*\*评审记录\*\*：.*$', '> **评审记录**：用户确认全局阈值及简化范围并授权同步；本批为文档与算例自检，不代表工程或效果验收通过<br>', s)
    s = re.sub(r'(?m)^> \*\*修订说明\*\*：.*$', f'> **修订说明**：{old} → {new}，统一M1达标阈值、移除固定题数与额外恢复规则，明确Evolution版本演进后置及工程设计属于工程阶段；逐文件记录见MVP决定登记§28<br>', s)
    texts[p] = s
for p in [eng, validation, design, validindex]:
    for rel, label in [(prd,'PRD'), (content,'内容规格'), (interaction,'交互规格'), (validation,'验证计划')]:
        old,new=versions[rel]
        texts[p]=texts[p].replace(label+' '+old,label+' '+new).replace(label+old,label+new)
rep(design, '| v0.22：同步实时出题', '| v0.23：同步实时出题')
rep(design, '| v0.21：按方法×方面', '| v0.22：按方法×方面')
rep(design, '| v0.20：同步当前行为范围', '| v0.21：同步当前行为范围和0.90判定')
rep(validindex, 'v0.3：保留教材Agent', 'v0.4：保留教材Agent')
rep(validation, '[决定登记§27](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)', '[决定登记§28](../../DECISIONS.md#28-m1全局达标阈值与工程阶段边界)')

texts[dec] += '''

## 28. M1全局达标阈值与工程阶段边界

**M1-DEC-021，2026-11-09。** 用户确认先简化：每个Task内每种方法的四方面分别使用全局θ=0.90，不取平均、不设逐项阈值。该决定取代M1-DEC-004的固定成功题数和M1-DEC-020示例中的额外题数达标限制，保留方法／方面归因、证据资格和范围。没有对应有效Evidence保持待确认；有适用证据时，观测更新概率达到阈值即达标，低于阈值为需加强。教学预测本身不触发达标。负证后下降、正证后恢复仍用同一阈值，不清空概率或另设恢复规则。

现有参数使一次正证约0.773、两次约0.920，但“两题”是该合成序列的结果，不是额外门槛。E2迁移和E4保持都只有一次正证，因此仍未达标；正文反馈和任务结果同步修订。迁移须有真正符合条件的新表现，保持仍按本例七天资格取证，不能为了过阈值重复同源表现。0.90是试用假设，不是准确率或校准结果。

**范围与阶段。** Evolution相关版本演进、兼容判定、Belief跨版本迁移及历史重算后置M2/M3；M1不再据此要求新产品决定或建设平台。事件只追加、教材解析采用核对和实际来源留痕仍保留；文档本身继续逐批升版。工程设计明确属于工程阶段，随后才是编码与集成；本批未新建工程设计正文、未开始生产编码，也未宣布全部验收通过。

主规则在内容§4.10／4.20，数字例在§4.19，学生反馈和主动任务在§4.24；PRD、交互说明和验证计划同步引用。旧截图、旧原型及v1.8文件不反写，新阈值尚未在UI或引擎实现。既有OPEN登记按本决定解释：OPEN-03准备各章判据与Evidence资格，不另选概率门槛；OPEN-04仅承接当前工程合同和旧资产适配，不提前建设Evolution；OPEN-09校准仍待真实数据。

**后续事项。** 没有因本次阈值决定新增必须重开模型讨论的阻塞项。计时空闲口径在工程设计中提出并明确；整册判据与内容、教材材料和实际服务条件在对应使用前落实；阈值与参数的真实质量按验证计划检查。这些不要求先扩展页面。下一步撰写Engineering_Design.md和Delivery_Plan.md，即开展M1工程阶段的工程设计工作。

本批修改前快照见[基线](../../src/mvp_foundation/m1/design-reviews/20261109-m1-threshold/baseline.json)，自检见[记录](../../src/mvp_foundation/m1/design-reviews/20261109-m1-threshold/review.json)。未调用LLM、未改原型或截图，算例不是学生实验。

| 文档 | 旧版 → 新版 |
| --- | --- |
'''
for r in records:
    texts[dec] += f'| `{r["path"]}` | {r["old"]} → {r["new"]} |\n'

for p,s in texts.items():
    target=root/p
    source=(batch/'before'/p) if (batch/'before'/p).exists() else root/'doc/concept-design/DeerMind_Evaluation_Space_Design_v1.8.md'
    original=source.read_bytes()
    newline='\r\n' if original.count(b'\r\n')==original.count(b'\n') else '\n'
    target.write_text(s,encoding='utf-8',newline=newline)
print(f'Updated {len(texts)} documents; prototype untouched.')
