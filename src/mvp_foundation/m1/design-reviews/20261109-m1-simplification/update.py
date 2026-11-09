from pathlib import Path
import re, json, hashlib, subprocess

root = Path(__file__).resolve().parents[5]
batch = Path(__file__).parent
paths = [
 'doc/mvp/m1/PRD.md','doc/mvp/m1/design/Content_and_Model_Reference.md',
 'doc/mvp/m1/design/Interaction_Design.md','doc/mvp/m1/README.md',
 'doc/mvp/m1/design/README.md','doc/mvp/README.md','doc/mvp/DECISIONS.md',
 'doc/mvp/m1/engineering/README.md','doc/mvp/m1/validation/Validation_Plan.md',
 'doc/mvp/m1/validation/README.md','doc/mvp/m2/README.md',
 'doc/concept-design/README.md','doc/system-design/README.md']
texts = {p:(root/p).read_text(encoding='utf-8') for p in paths}
before = dict(texts)
versions = {}
for p,s in texts.items():
 old = re.search(r'> \*\*版本\*\*：(v\d+\.\d+)',s)[1]
 major,minor = old[1:].split('.')
 versions[p] = (old, f'v{major}.{int(minor)+1}')

def rep(p,a,b):
 assert a in texts[p], (p,a[:100])
 texts[p]=texts[p].replace(a,b)
def para(p,start,new):
 pattern=r'(?m)^'+re.escape(start)+r'[^\n]*(?:\n(?!\n|#|\||>)[^\n]+)*'
 assert re.search(pattern,texts[p]), (p,start)
 texts[p]=re.sub(pattern,lambda m:new,texts[p],count=1)

prd,content,interaction,m1,design,mvp,dec,eng,validation,validindex,m2,concept,system=paths

# PRD: current behavior, not an appendix overriding contradictory requirements.
para(prd,'第一版可以先以管理员核对的小型题库运行。','M1同时支持选用已核对实例和教学中按已准备的TaskTemplate实时生成。现有题库可帮助冷启动，但没有备用题不等于不能检测。两条供题路径共用下列信息：')
rep(prd,'没有合适题目时说明尚不能检测该要求，管理员补齐；','没有合适实例时先按合格模板生成；生成检查失败且无可用替代题时，才说明该要求暂不能检测，并保留缺口供管理员补齐；')
para(prd,'自动生成广泛变式、原生题和复杂组卷优化','教学中自动出题属于M1：候选通过题意、参数、答案、范围、归类及本次用途检查后保存并使用，无须管理员逐题批准；失败候选不交付学生。自动出题以已准备的模板、方法和检查参考为边界，不临时扩大任务定义。广泛原生题探索、复杂组卷优化和大型题库运营后置。')
rep(prd,'### 3.9 查看一次运行并纠错（M1-R09）','<a id="39-查看一次运行并纠错m1-r09"></a>\n\n### 3.9 查看运行与维护内容（M1-R09）')
rep(prd,'证据引用及纠正关系','证据引用')
rep(prd,'被替代的Evidence保留在历史折叠区，不混入当前有效依据。','M1不实现错误评价的替代Evidence、纠正操作或历史重算；旧原型相关示例属于后续阶段参考。')
para(prd,'管理员记录“预期是什么、实际是什么”','管理员可以查看原始事件和评价依据，定位问题并维护教材、领域定义、Claim和目标，修订用于后续适用的内容。M1不提供已生成错误评价的纠正工作流、替代Evidence、历史重算及配套管理操作；该能力转入M2规划，具体范围届时确认。不得直接手改学生概率或达标结果。未映射题补齐后不追补旧作答评价。发现不可靠判断时不能继续宣称可靠；必要时停止受影响的自动决策，但不借此在M1另建逐条失效与修复平台。')
para(prd,'Evolution 在本阶段','M1保留可追溯记录及内容、模型定义的正常维护；不据此声称已能纠正历史个人评价。后续评价纠正与自动诊断分别规划，不影响本阶段教材助手通过对话修正解析候选。')
insert='''**自然提问的范围。** 本次讲什么跟随学生明确请求及当前活动，不受阅读器位置约束。目标是分数应用时，学生仍可询问本教材中的圆；存在影响讲法的歧义才澄清，不要求每次先选章。求解遵守教材采用的方法及适用章节关系，必要基础回补沿已定义依赖进行，不随意调用领域中超出课程的方法。有适用Claim和合格表现时可更新本空间Belief；只有符合当前目标的证据才参与目标达成，不因一次提问自动添加目标项。无适用评价定义时仍可按可靠内容帮助，保留正式评价限制。

'''
rep(prd,'这些是讲解活动的不同起点。',insert+'这些是讲解活动的不同起点。')
rep(prd,'手动维护、教材提取或后续生成；管理员核对及建立模板关系','手动维护、教材提取或M1实时生成；按来源核对、检查并建立模板关系')
rep(prd,'当前有效依据是对已有记录的投影，纠正不覆盖旧事件；','当前依据是对已有记录的只读投影；错误评价纠正及历史重算后置，')
para(prd,'Belief表示学生在本Learning Space内','Belief表示学生在本Learning Space内对明确Task Claim的概率性判断。每个学生、空间、Claim版本一份Belief，内部默认只按方法和四个评价方面记录分项概率。题目参数、帮助、表征和时间用于证据资格与覆盖检查，不按其组合新增概率格子。一个模板内四分之一和五分之一采用相同方法和判据时更新同一分项；实际测过什么仍由Evidence保留，目标另按范围核对。参数相近不自动证明所有变化都掌握；分项聚合是待验证的M1简化假设。裁剪和扩展评价方面仍按已确认的Claim规则，不由运行LLM临时创建条件分项。')
para(prd,'管理员看到的Evidence列表由当前Belief','管理员看到的Evidence列表由当前Belief采用的累计依据形成，不是整个Task的事件列表，也不只取最后一次更新。选择某个目标时还要按目标范围筛选证据，不能把共享概率当成特定范围已达标。更新事实不作为新的能力Evidence。正常记录与旧原型纠正示例的阶段界限见[内容规格§4.22](design/Content_and_Model_Reference.md#422-evaluation处理留痕与只读证据投影)。')
rep(prd,'| 纠错 | 可辅助分析具体记录和提出修订 | 管理员决定内容改动，系统保留记录；不建设自主改模 |','| 内容维护与问题追溯 | 辅助分析记录、修正教材候选和提出定义修订 | 管理员核对与采用，系统保留记录；错误评价纠正、替代Evidence与历史重算后置M2，不建设自主改模 |')
rep(prd,'| 发现已展示的错误内容或判断 | 管理员可定位并处理，用户获知影响其学习的实质更正 | 旧事实保留；不可靠判断退出当前使用，不依赖其继续推断 |','| 发现已展示内容或评价存在问题 | 原始记录和依据可查；教材、定义可正常修正，说明本次判断的限制 | 不继续依赖已知不可靠判断；错误评价的替代和历史重算不在M1实现，不把后置称为已修复 |')
rep(prd,'| M1-A07／R07 |', '| M1-A07／R07 |')
# Update complete acceptance rows with stable IDs.
para(prd,'| M1-A07／R07 |','| M1-A07／R07 | 选用已有合格题；题库为空或题目已暴露时按模板生成；另测生成或检查失败 | 合格候选先检查、保存再使用，不逐题人工批准；归类、答案或用途不合格且无替代题时不启动相关检测；题面、帮助及版本留痕 |')
para(prd,'| M1-A09／R09 |','| M1-A09／R09 | 从目标查Evidence与源事件，从空间事件查看一次评价更新，再定位相关内容定义 | 前后值、实际方法／方面、版本和依据可追溯；可维护源内容和定义，不提供改分、替代Evidence或历史重算；旧纠正mock不作为M1验收 |')
rep(prd,'| M1-A11／R11、R12 | 学生讲解中追问','| M1-A11／R11、R12 | 目标为分数但询问教材中的圆，核对讲解范围与目标不变；学生讲解中追问')
rep(prd,'| M1-A13／R14 | 独立正确','| M1-A13／R14 | 四分之一和五分之一符合相同定义时更新同一分项，特定目标只取适用Evidence；独立正确')

# Content: shared estimate versus conditional evidence; no algorithm change.
para(content,'允许方法的交集来自','本次允许方法根据任务方法、教材采用关系、本次明确请求及检测目标确定。按章教学核对该章采用关系；无书页引用时不把阅读器位置强加给请求。当前目标之外的教材内帮助仍可开展，但不自动扩展目标。目标要求分别说明两法时须取得各自表现，不能只改标签。没有合格实例时可按模板生成、检查并保存；供题失败不临时放宽标准。')
para(content,'M1先复用核对题库。','M1可复用已核对题库，也必须支持教学中在已准备模板范围内自动出题。两条路径都检查题意、参数、答案、归类和用途；通过后保存并使用，无须管理员逐题确认。复杂组卷和广泛新题探索后置。')
rep(content,'Observation描述表现及帮助背景；不能直接宣布独立掌握','空间事件记录实际表现及帮助背景，Evaluation据此提取Evidence；不要求独立Observation层，不能直接宣布掌握')
rep(content,'不同变化不能无条件合并','不同变化的覆盖不可互相冒充；按本方面已定义的资格核对，不为每种变化另建概率')
rep(content,'实际方法引用、评价方面及适用条件。只建立有明确评价定义、当前需要的分项；不是每种条件组合都建一个 Claim','实际方法引用和评价方面；条件是证据资格及覆盖信息，不是第三层概率索引。只建立已定义、当前需要的方法／方面分项')
para(content,'“增加四分之一”只提供该参数子范围的证据','''**M1的条件简化。** 同一Task／方法／方面采用相同判据时，合法题目参数变化更新同一概率。两种方法默认对应八个边际概率，不因分母、题号、目标、表征或时间组合继续分裂；不是256个联合状态。保留共同来源但不相乘或平均成总掌握率。题目之间条件可比是试用假设，真实难度差异与相关性须验证。

以分步法A的独立完成为例：Task允许原量和分率变化，两题原量均为正整数且结果整除；学生无当题帮助、完整作答，两题之间没有新增教学机会。120增加1/4得到150后，概率由0.50更新为0.772727；100增加1/5得到120后，继续更新同一分项为0.920382。公式和参数仍见§4.18；未说明理由不自动更新理解，只换分率不自动更新迁移，未满足间隔不更新保持。

Evidence分别保留r=1/4、r=1/5、原量、过程、帮助和表征。共享概率是对方法能力的估计，不是所有参数范围都已验证的证明。目标若要求两道1/4新题，上述混合两题只提供一道适用题；目标若要求至少一次1/5表现，仅有1/4证据仍不足。目标使用对应Evidence及条件核对，不能从共享高概率凑齐覆盖；换目标不复制Belief。

条件未知先保留未决；明确不符合某方面资格则不更新该方面。确有不能混用的评价责任，应先修订并确认评价定义，不能由LLM运行时创建条件分项。默认四方面的有依据裁剪和扩展仍保留。''')
rep(content,'Claim／方法／方面／适用分项','Claim／方法／方面')
rep(content,'方面／适用分项','方面')
rep(content,'| 已发现系统在轮内泄露答案或提示 | 记录实际展示及受影响时间，停止该轮继续作为独立检测，按纠正规则处理 |','| 已发现系统在轮内泄露答案或提示 | 记录实际展示及受影响时间，停止该轮继续作为独立检测；尚未更新的表现按实际帮助核对，已产生错误评价的纠正后置 |')
rep(content,'失误后的事实与纠正路径保留','失误事实保留；错误评价的纠正工作流后置M2')
rep(content,'具体重算机制由工程接收定义，M1不新增批量历史重算平台','M1不实施错误评价纠正、替代Evidence或历史重算，后续机制在M2规划')
rep(content,'每次形成、更新或纠正都留下新的空间事件','M1每次形成或正常更新都留下新的空间事件')
rep(content,'| 纠正事件及替代记录 | 发现先前解释错误并完成核对后 | 被纠正记录、理由、替代关系和新修订；原始事件及旧解释仍保留，不制造新的学生作答 |','| 错误评价纠正及替代记录（M2规划） | 不属于M1处理链或验收 | 后续讨论如何替代和重算；M1仅保留已有事件与依据，不提供纠正操作 |')
para(content,'**当前依据如何读取。**','**当前依据如何读取。** 按学生、空间、Claim版本、实际方法和评价方面定位分项，沿正常更新链取得累计Evidence，按标识去重；查看特定目标时另核对范围与条件。不能只取最后一次更新，也不能把所有与Task有关的事件拿来充数。无合格Evidence仍待确认，先验不作为测得能力展示。M1不实现错误解释替代后的重算投影。')
para(content,'**纠正如何显示。**','**错误评价纠正后置。** M1不提供错误评价纠正、替代Evidence、历史重算或相应管理操作；纳入M2候选范围再设计。不因此取消教材Agent纠错、领域定义维护、目标标准变化后的正常对照、更新失败重试及新表现带来的正常概率更新。原事件不可改，管理员不能直接改分。保留追溯以便发现问题，不声称M1已能修复历史个人判断。')
rep(content,'**当前后台原型的另一组“四分之一”经历。** 下表用于追溯与纠正交互；','**保留的旧原型示例，不全属于M1交付。** 下表记录现有固定mock；其中R3的错误解释替代与重算已经后置，不能作为M1必须实现或已实现的行为。正常事件与Evidence查看仍可复用；')
rep(content,'解释错误另按纠正合同追加处理','疑似解释错误保留事实及限制，M1不提供历史评价纠正流程')

# Interaction: preserve screenshots verbatim, declare historical correction scope.
rep(interaction,'### 3.2 从学习目标查看判断依据','### 3.2 从学习目标查看判断依据')
rep(interaction,'**M1-D06-E06：区分有效与被替代依据。**','**历史参考E06，后置M2：区分有效与被替代依据。**')
rep(interaction,'纠正场景中，保持项实际由77.3%改为16.7%，另列50.0%重算基线；不能把重算基线冒充实际更新前值。','原图EV09包含错误评价纠正和重算基线，这是保留的后续阶段示例，不纳入M1验收；M1只要求正常更新的实际前后值及依据。')
rep(interaction,'**M1-D06-E09：分清当时与当前。**','**历史参考E09，后置M2：纠正后的当时与当前。**')
rep(interaction,'### 3.2 从学习目标查看判断依据\n','### 3.2 从学习目标查看判断依据\n\n**本轮范围调整。** 正常的目标→Evidence→源事件和更新追溯保留；错误评价纠正、替代Evidence和历史重算已后置M2。EV06、EV07、EV09、EV10及LS-001中涉及纠正的内容仍保留原截图和mock，不作为M1功能要求；混合截图中的普通查看结构可复用。本轮不修改原型或重采截图。\n')
rep(interaction,'后者按只追加的事件检查处理、更新和纠正。','后者按只追加的事件检查处理和正常更新；历史纠正示例按§3.2的后置范围解释。')
rep(interaction,'### 2. 学生选用并完成一次学习','### 2. 学生选用并完成一次学习') if '### 2. 学生' in texts[interaction] else None
rep(interaction,'## 2. 学生选用并完成一次学习\n','## 2. 学生选用并完成一次学习\n\n本次范围补充：目标是分数时仍可讨论教材中的圆；请求和活动决定本次内容，教材采用关系约束方法，目标只限定达成判断。有适用Claim的合格表现可更新Belief，不能自动新增目标项。无合适题目可按已准备模板生成、检查并保存后使用。这些是工程须承接的规则，本轮未新增界面或真实生成演示。\n')

# Validation and delivery scope.
rep(validation,'| 两种方法中只展示方法A的过程 |','| 同一方法用1/4及1/5两道合格新题，期间无教学 | 更新同一独立分项：0.50→0.772727→0.920382；特定1/4两题目标只有一道适用Evidence，不达标 |\n| 两种方法中只展示方法A的过程 |')
rep(validation,'## 3. Evidence、学习机会与算法实现验证\n','## 3. Evidence、学习机会与算法实现验证\n\nM1仅验证正常Evidence形成、更新与失败重试；错误评价纠正、替代Evidence和历史重算转入M2，不以旧纠正mock要求M1实现。题目参数／帮助／表征／时间是资格及覆盖信息，默认不新增概率分项；校准分析可以按条件分组，但分组统计不改变产品状态结构。\n')
rep(validation,'## 2. 教材导入Agent与整册建模验证\n','## 2. 教材导入Agent与整册建模验证\n\n教学中自动出题另按PRD R07验证：空题库或已暴露题目时，从已准备模板生成，题意、参数、答案、归类和本次用途检查通过后保存使用；不逐题人工批准。检查失败且无替代题时不得交付。初次生成、检查和保存须能追溯，真实内容质量单独测量。教材解析纠错仍是M1必做，与后置的个人评价纠正不同。\n')
rep(validation,'## 5.', '## 5.') if '## 5.' in texts[validation] else None
texts[validation] += '\n自然提问的验收同时覆盖：目标为分数、询问教材中的圆、教材收起及浏览另一章；讲解遵守教材方法，目标不变。若有合格表现和Claim则更新对应Belief；不适用目标的Evidence不凑目标达标。\n'
rep(eng,'覆盖边界、重复、跳过与纠正重算','覆盖边界、重复、跳过及同方法跨参数更新；错误评价纠正与历史重算不纳入M1')
rep(eng,'本批对当前构建复跑','教材助手上一批对当时构建复跑')
para(eng,'本批对当前构建复跑','本批不运行或修改原型。此前教材助手四文件17项mock检查见[原记录](../design/assets/material-assistant-v0.1/review.json)，不作为本轮算法或真实系统验证。') if '本批对当前构建复跑' in texts[eng] else None
texts[eng] += '''

## 4. 已确认范围下的工程实施顺序

本轮四项决定见[登记§27](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)。下表是实施顺序及交接标准，不是完整工程设计、工期承诺或开工验收。先编写Engineering_Design.md及Delivery_Plan.md，接收PRD与设计中的已定输入；不再把完善外围UI作为前置。

| 顺序 | 实现内容与依赖 | 可核对的交付与完成条件 |
| --- | --- | --- |
| E01 运行与数据基础 | 身份和空间隔离；受保护模型连接；文件／记录持久化；版本引用、只追加事件、失败恢复及基本调用记录 | 管理员和学生独立登录；原件、配置和事件可恢复；重复请求不产生重复事实。各Space可在一个部署中分模块，不先建微服务或通用Agent平台 |
| E02 领域管理与教材Agent | 先建立Domain及TT／ST／KC／TI／SI手动管理和依赖检查；再接原件读取、结构化解析、持续对话、引用、候选校验与采用 | 用既有四例完成真实解析及对话纠错；候选提交领域、复用／补建模板、实例关联、章节TT／ST采用可追溯。管理员核对，无手工解析编辑器 |
| E03 评价定义、目标与课程应用 | 依赖E02；建立Claim、方法执行判据和四方面规则；目标选取教材范围，应用明确版本 | 管理员保存并应用教材＋目标，学生选用建空间；草稿不泄露为可用课程，缺口与学生未知分开；目标变化不自动提高能力 |
| E04 真实学习活动与题目供给 | 依赖E03；四类蓝图、活动树、持续聊天、教材独立浏览；选择已有题或模板生成、检查、保存 | 用四分之一完成分段讲解、追问、主动检测与轮后帮助；无推荐策略仍可合法继续，求助先结束检测轮。真实展示、提交及帮助留痕，失败不造学生反证 |
| E05 Evidence、Belief与目标反馈 | 纯数值函数可在E02期间用固定输入提前实现；真实接线依赖E04事件与E03定义 | 先资格与去重，再按方法×方面更新，明确子Task证据才联动；1/4与1/5共享分项但目标按实际覆盖；结果返回聊天，后台可读依据。保留既定公式和初值；不实现错误评价纠正和历史重算 |
| E06 主动任务与主流程验证 | 依赖E05有效结果；接进入空间／活动结束／时间条件及接受、暂缓、拒绝 | 受助后补证及延迟检测任务可回到活动，评价返回后重查必要性；不重复催促、不抢占、不以失败降低能力。用提醒代替30分钟强制退出 |
| E07 整册内容与M1验收 | E02–E03稳定后即可逐章准备，与后续工程并行；最终依赖E04–E06真实运行 | 全册内容、模型、Claim、目标及供题条件完成；逐章核查与有限真实案例质量验证，报告未决和成本。不是只完成四分之一示例，不要求学生做完整册 |

首条纵向联调使用“四分之一”，各步骤交付真实输入输出再扩章。测试数据可用于开发，但不冒充教材正式内容或真实学生证据。学习机会资格和去重未通过时不启用L转移；保持既定参数，未满足的输入不更新。真实质量、校准及试用条件按验证计划逐项获得证据，不以工程步骤完成代替效果验证。

错误评价纠正由M2重新确认具体范围；M1保留可追溯事实和定义维护，不建设替代Evidence／历史重算。实际服务与材料条件、逐章标准和校准参考仍在对应接入前落实，但不重新打开已确认产品范围。
'''
rep(m2,'当前不为这些方向逐项展开交互','新增后续议题：错误评价纠正，包括纠正发起、核对、替代Evidence、受影响Belief及目标的历史重算和管理操作。M1仅保留追溯，不实现该工作流；M2开始时结合真实错误决定最小范围，复杂批量能力可再评估是否进入M3。教材解析纠错与正常定义维护不在此后置范围。\n\n当前不为这些方向逐项展开交互')

# Current indices and progress. Historic decision sections are not rewritten.
rep(m1,'| 失败／纠正→当前有效状态与历史 | 事件只追加，旧依据保留；处理失败不是学生不会；纠正与当前投影分别可查 | 既有产品边界保留。原型localStorage不是不可变事件实现；事务、去重、权限、重试与版本落盘属于工程责任 |','| 失败／后续新表现→当前状态与历史 | 事件只追加，失败不是学生不会；新表现正常更新，教材与定义可维护 | 错误评价纠正、替代Evidence与历史重算已后置M2；保留追溯，不要求实现旧纠正mock |')
rep(m1,'修正内容、应用新版和失效结果退出当前使用','维护内容和定义、应用新版；个人错误评价纠正后置')
rep(m1,'管理员能沿一次活动找回依据并修正','管理员能沿一次活动找回依据并维护内容定义')
para(m1,'**下一步顺序。**','**下一步顺序。** 本轮四项业务决定已经确认：M1实时出题、方法×方面概率、自然提问范围、错误评价纠正后置M2。对应规格与验收已同步，不再将这些事项列为待讨论。下一步编写工程设计与分步交付计划，按[工程顺序E01–E07](engineering/README.md#4-已确认范围下的工程实施顺序)推进：运行基础→领域与教材Agent→课程应用→学习与出题→评价反馈→主动任务→整册验证。LC-01–04未接线属于实现工作，不是新的产品断层。')
rep(m1,'**本次结论。** 主链的责任已经能够串起来：','**本次结论。** 本轮检查的四项决定已收束，见登记§27；下表保留此前交接说明，不以原型未接线重开产品问题。主链的责任已经能够串起来：')
rep(m1,'当前剩余问题不是需要再发明一套模型，而是部分交接还不能让工程人员只看规格就确定输入和返回结果。','已补齐的交接作为工程输入，尚未实现不等于业务不通。')
para(m1,'**本次交付与下一步。**','**本次交付与下一步。** 已同步四项简化规则和验收，教材助手截图沿用上一批。按§6收束结果进入工程设计与交付计划，不再扩大UI。工程顺序及每步交付见engineering/README.md §4。')
rep(design,'事件侧概率更新与纠正；均为固定mock','事件侧概率更新；图中错误评价纠正已后置M2，保留历史mock')
texts[design] += '\n本轮四项简化见[登记§27](../../DECISIONS.md#27-m1主流程简化与工程实施顺序)。未改原型或截图；EV系列纠正示例不再属于M1验收，普通追溯仍保留。下一步直接整理[工程设计与实施计划](../engineering/README.md#4-已确认范围下的工程实施顺序)，不再扩展页面。\n'
texts[mvp] += '\n当前主流程规则已收束，见[登记§27](DECISIONS.md#27-m1主流程简化与工程实施顺序)：M1具备模板实时出题，Belief按方法与方面简化，提问不受阅读位置和目标章节限制，错误评价纠正后置M2。下一步按[工程实施顺序](m1/engineering/README.md#4-已确认范围下的工程实施顺序)准备工程设计；原型与历史截图保持。\n'
rep(dec,'M1允许先用已核对的小型题库；题目来源、适用方法、实际帮助和使用须可查，自动出题优化后置','M1可选已有题或按已准备模板实时生成，检查通过后保存使用，无须逐题人工批准；复杂出题优化后置')
rep(dec,'纠正采用重新解析，不建设复杂块编辑工作区','通过教材助手持续对话解析纠错，不建设手工内容编辑器')
rep(dec,'一个Belief保留条件；目标核对方法覆盖','一个Belief按方法×方面记录概率，条件用于证据资格和覆盖；目标核对实际证据')

# Scope current conceptual definition by a new version; preserve v1.7 as history.
old_eval='doc/concept-design/DeerMind_Evaluation_Space_Design_v1.7.md'
new_eval=old_eval.replace('v1.7','v1.8')
e=(root/old_eval).read_text(encoding='utf-8')
e=e.replace('# DeerMind Evaluation Space Design v1.7','# DeerMind Evaluation Space Design v1.8',1)
e=e.replace('> **版本**：v1.7','> **版本**：v1.8',1)
e=e.replace('Belief_t(L,S,C@v)=\\{(m,a,c)\\mapsto(Assessment_{t,m,a,c},EpistemicUncertainty,EpistemicStatus,EvidenceBasis)\\}', 'Belief_t(L,S,C@v)=\\{(m,a)\\mapsto(Assessment_{t,m,a},EpistemicUncertainty,EpistemicStatus,EvidenceBasis)\\}')
e=re.sub(r'(?m)^其中m为实际方法引用，a为评价方面，c为[^\n]+', '其中m为实际方法引用，a为评价方面。M1默认按方法与方面建立分项，条件保存在Evidence和覆盖信息中，服务资格、适用性及目标对照，不作为第三层概率索引。相同定义内的1/4、1/5题更新同一分项；不同参数实际检验范围仍保留。两个方法默认八个边际概率，LLM不临时建立条件分项。方面扩展须按既定定义管理，不枚举联合状态。',e)
e=e.replace('## 1. 文档定位与设计命题','''**M1采用范围（M1-DEC-020）。** 当前M1按方法×评价方面记录概率；题目参数、帮助、表征和时间用于证据资格及目标覆盖，不继续拆概率。目标外但教材适用的表现仍可更新Belief，目标只对照自身要求。错误评价纠正、替代Evidence和历史重算后置M2；本文后续通用可修正性、替代及重算机制是长期架构约束，不列入M1实现。M1保留原始事件、正常更新、失败重试、只读追溯及教材／定义维护。完整M1规则以[内容规格](../mvp/m1/design/Content_and_Model_Reference.md)为准。

## 1. 文档定位与设计命题''',1)
e += '\n\nv1.7 → v1.8（2026-11-09）：落实M1-DEC-020，将M1概率索引收敛为方法×方面，保留条件证据及目标覆盖；明确错误评价纠正与重算是M2后续范围。未改贝叶斯公式、参数或全册要求，v1.7文件保留历史。\n'
texts[new_eval]=e
versions[new_eval]=('v1.7','v1.8')
for p in [prd,content,m1,mvp,concept,system]:
 texts[p]=texts[p].replace('Evaluation v1.7','Evaluation v1.8').replace('Evaluation为[v1.7]','Evaluation为[v1.8]').replace('Evaluation Space Design v1.7','Evaluation Space Design v1.8').replace('DeerMind_Evaluation_Space_Design_v1.7.md','DeerMind_Evaluation_Space_Design_v1.8.md').replace('v1.5／v1.7','v1.5／v1.8')
# Only current boundary table in decisions updates its conceptual link text.
head,sep,history=texts[dec].partition('## 2.')
texts[dec]=head.replace('Evaluation v1.7','Evaluation v1.8')+sep+history

for p in texts:
 old,new=versions[p]
 texts[p]=re.sub(r'(?m)^> \*\*版本\*\*：[^\n]+',f'> **版本**：{new}<br>',texts[p])
 texts[p]=re.sub(r'(?m)^> \*\*更新日期\*\*：[^\n]+','> **更新日期**：2026-11-09<br>',texts[p])
 texts[p]=re.sub(r'(?m)^> \*\*修订说明\*\*：[^\n]+',f'> **修订说明**：{old} → {new}，同步实时出题、Belief分项简化、自然提问范围及错误评价纠正后置；本轮未改原型，逐文件记录见MVP决定登记§27<br>',texts[p])
 texts[p]=re.sub(r'(?m)^> \*\*评审记录\*\*：[^\n]+','> **评审记录**：用户确认四项简化并授权同步；本轮为文档一致性与算例自检，不代表工程或真实效果通过<br>',texts[p])
 texts[p]=re.sub(r'(?m)^> \*\*状态\*\*：[^\n]+','> **状态**：已承接本轮四项简化；工程实现与真实验证待开展，原型及历史截图未改<br>',texts[p])
 # Live upstream references only; historical decision ledger remains intact.
 if p != dec:
  for name,a,b in [('PRD','v0.21','v0.22'),('内容规格','v0.20','v0.21'),('内容与模型规格','v0.20','v0.21'),('交互规格','v0.19','v0.20'),('验证计划','v0.2','v0.3')]:
   texts[p]=texts[p].replace(name+' '+a,name+' '+b).replace(name+a,name+b)

texts[dec]+='''

## 27. M1主流程简化与工程实施顺序

**M1-DEC-020，2026-11-09。** 用户确认以下四项并授权同步文档，暂不改原型。本决定取代当前正文中将自动出题后置、按条件扩展概率索引及要求M1纠正历史评价的表述；此前决定和截图保留原始含义。

1. **实时出题属于M1。** 优先可用实例；不足时依据已准备模板生成、检查、保存再使用，无须逐题人工批准。失败且无替代题才暂不能检测；复杂组卷后置。
2. **Belief默认按方法×四方面记录。** 参数、帮助、表征和时间是证据资格与覆盖信息，不按条件组合新增概率；同定义内1/4与1/5更新同一分项，目标仍按实际证据范围达标。公式、初值、子Task明确证据更新及方面的有依据扩展保持。
3. **自然提问跟随请求。** 不受阅读器位置或目标章节限制；求解遵守教材采用的方法，必要回补沿已定义依赖。合格表现和Claim可支持Belief，目标只对照自己的要求，不自动扩大目标。
4. **错误评价纠正后置M2。** 不实现替代Evidence、历史重算及配套管理流程；M2再定具体范围。M1保留事件、评价依据、正常更新和教材／定义维护，不把教材Agent纠错一并删除。

正文归属：PRD维护范围与验收；内容§4.16维护分项与混合分率例，§4.22划清旧纠正示例；交互保留原图并明确后置部分；Evaluation v1.8同步模型采用边界，v1.7保留历史。M2入口承接后置事项。

工程顺序见[M1工程入口§4](m1/engineering/README.md#4-已确认范围下的工程实施顺序)：E01基础、E02领域与教材Agent、E03定义及应用、E04学习与供题、E05评价反馈、E06主动任务、E07整册验证。数值纯函数和逐章内容可在依赖具备后并行；不据菜单数量排工期。下一步输出Engineering_Design.md和Delivery_Plan.md，尚未开始生产实现。

本批仅文档修改；未调用LLM、未改原型或截图、未重跑浏览器。算例、链接、版本及冻结文件核对见[自检](../../src/mvp_foundation/m1/design-reviews/20261109-m1-simplification/review.json)，修改前内容及哈希见[基线](../../src/mvp_foundation/m1/design-reviews/20261109-m1-simplification/baseline.json)。

| 文档 | 旧版 → 新版 |
| --- | --- |
'''+''.join(f'| `{p}` | {a} → {b}'+('（新文件，保留旧版）' if p==new_eval else '')+' |\n' for p,(a,b) in versions.items())

# Freeze inputs before first write; source and historical evidence never edited.
baseline_path=batch/'baseline.json'
assert not baseline_path.exists(), 'Do not overwrite the batch baseline'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for p in paths:
 dest=batch/'before'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/p).read_bytes())
 records.append(dict(path=p,old=versions[p][0],new=versions[p][1],sha256=sha(root/p)))
frozen=[]
for base in ['doc/mvp/m1/prototype','doc/mvp/m1/design/assets']:
 for p in (root/base).rglob('*'):
  if p.is_file() and not (set(p.parts)&{'node_modules','dist','.tmp','.vite','test-results'}):
   frozen.append(dict(path=p.relative_to(root).as_posix(),sha256=sha(p)))
for p in [old_eval,'doc/mvp/m1/validation/Content_Representation_Trial.md']:
 frozen.append(dict(path=p,sha256=sha(root/p)))
baseline_path.write_text(json.dumps(dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),files=records,newFiles=[dict(path=new_eval,old='v1.7',new='v1.8')],frozen=frozen),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p,s in texts.items():
 original=(root/p).read_bytes() if (root/p).exists() else (root/old_eval).read_bytes()
 (root/p).write_bytes(s.replace('\n','\r\n').encode('utf-8') if b'\r\n' in original else s.encode('utf-8'))
print(json.dumps(dict(updated=len(texts),versions=versions),ensure_ascii=False))
