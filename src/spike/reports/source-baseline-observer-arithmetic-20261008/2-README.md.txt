# DeerMind Architecture Spike — deterministic foundation

最新进展见 [单任务原型第一轮工程结果](../../doc/system-design/spike/DeerMind_Single_Task_Engineering_Round_1_Result_v0.1.md)：修订协议已接入并完成固定 6 个两回合会话，60 次真实调用、无网络失败；2 个会话完整执行，但尚无提示显示。当前优先处理算术抽取将学习者错误转述误作观察者认可的问题。本轮已结束，不自动追加整链测试。

阶段范围依据为 [问题定性与可行性决定](../../doc/system-design/spike/DeerMind_Spike_Issue_Disposition_and_Feasibility_Decision_v0.1.md) 和 [处置报告](reports/feasibility-triage-20261007.json)。有限可行性审查已结束，后续进入受限单任务原型工程验证。旧 9/17、A2 DENIED、原型 NO_GO 和 Gate E/F OPEN 保留为原合同结果，不再驱动无限语义调优。

原合同进度与停止条件见 [统一验收报告](reports/DeerMind_Architecture_Validation_Report_v0.1.md)。下文保留各历史运行器说明，不表示这些批次仍待执行。此次定性检查的记录位于 `runs/feasibility-triage-offline-v1` 和 `runs/feasibility-responsibility-v2`；运行器拒绝覆盖已有目录。

## 有界 Observation 收口 S1 / S2

从仓库根目录执行 `python src/spike/run_observation_closeout.py` 只做配置预检；增加 `--run` 执行唯一预留的两个批次。S1 为 24 项历史回归各五次，上限 480 次调用；S2 为 12 项新增表达各五次，上限 240 次。两份 fixture 和同一 v11 协议在 S1 前固定。新增表达由开发者预先标注，不称为独立盲测。原历史预期和全部失败继续保留。

v11 保留 v10 的语义规则和职责分类，只修订来源检查声明的表示及算术抽取交付说明。模型必须显式返回 `inspection_scope=COMPLETE_CONTEXT` 才会展开为当前精确来源清单；`NOT_DECLARED` 不被程序补成完整检查，unsupported 仍要求完整声明。这个声明不证明模型判断正确。额外 `arguments` 包装仍被拒绝，不拆包修补。程序不从 rationale 或自然语言推导分类。

执行器分别统计组件符合情况和最终组合结果；成功拦截不能把组件误判记为正确。出现不合格负例提交、不可恢复接口响应或连续三次协议／运行失败时立即结束当前批次，S2 不再自动启动。全部证据逐候选保存，协议与代码在两批之间重新核验指纹。固定目录 `runs/observation-closeout-v1` 一旦预留就拒绝自动重跑；中断需要先审计已有证据，不自动续跑或另开第三批。该实验不消除 AA-A02 的旧 DENIED，也不代替 A2 下游准入验证。

## C1 / C2 版本与诚实回放

从仓库根目录执行 `python src/spike/run_version_replay_validation.py`，按 `fixtures/version-replay-v1.json` 各执行一次确定性场景，保留独立原始批次。C1 使用文档允许的 selected reinterpretation fixture logic，候选经真实 owner 提交；验证同一事实的新旧语义版本并存、历史精确绑定，以及不同组件版本组合不要求全局版本代际。

C2 分开 historical_reconstruct 和 reexecute。前者只读取获当前权限许可的历史记录；后者产生明确标识的新 execution，不自动提交、不冒充历史。原模型版本不可用通过受控 provider fixture 注入，原 artifact 的实际字节从独立内存存储删除；缺失分别产生操作对应的 FULL / PARTIAL / UNAVAILABLE。FULL 表示该操作的依据完整，不保证模型输出一致。所有认知与 provider 行为均为显式 scripted fixture，外部 API 调用为 0，不消耗 S1/S2 预算；不提供真实模型、生产删除或 X2/X4 完整组合结论。

## B1 / B2 正式提交路径

从仓库根目录执行 `python src/spike/run_dependency_validation.py`，按 `fixtures/dependency-commit-v1.json` 各执行一次 B1 / B2，保存独立清单、逐项证据和摘要。该入口不调用模型，不消耗 Observation 两个后续批次的预算；执行 PASS 后仍需证据审查才能形成假设结论。

初始与替代 Observation / Evidence / Belief 全部经过共享 BoundaryRuntime 的 Context、候选绑定、后端授权和正式提交。B1 检查分阶段恢复以及已有新上游版本时旧候选仍不能提交；B2 检查 100 分支即时失效、只恢复一条分支及其他 99 条继续不可用。所有读取使用精确依赖和后端权限，不使用整体放行的资格 fixture，也没有 authoritative push graph。

候选含义与 semantic PASS 明确标为 SCRIPTED-DEPENDENCY-FIXTURE，仅隔离依赖机制；事实、规则、grant 和 correction stimulus 为受信测试预设。该入口不提供 A1/A2 语义可靠性、correction 授权生命周期、生产并发或性能结论。旧 foundation 批次保持原样。

实现范围包括综合 Spike 设计的 Step 0–Step 4 基础路径，以及 Step 5 的两次真实模型调用连通入口。已有不可变记录、精确依赖、版本激活、后端权限与数据使用检查、ContextManifest、exact-candidate 语义校验绑定和提交重验。只依赖 Python 3.13 标准库。

在 `src/spike` 下运行：

```powershell
python -m unittest discover -s tests -v
python run_foundation.py
```

也可从仓库根目录运行 `python src/spike/run_foundation.py`。每次创建独立的 `src/spike/runs/<UTC时间>-<随机标识>/`；`--output <目录>` 可更改输出父目录。输出不会覆盖已有批次，默认 runs 目录已被 Git 忽略。`manifest.json` 保存 HEAD、工作区状态及实际文档 / Python 文件内容哈希；`summary.json` 保存基础检查结果，每个 Case 的 JSONL 保留输入 snapshot、精确引用、解析轨迹、检查结果和异常。

| 场景 | 当前检查 |
|---|---|
| B1-foundation | O:r1 correction 后，分别检查无 replacement、仅 O:r2、再 E:r2、最后 B:r2；旧引用保持原样 |
| B2-foundation | 100 条 Evidence / Belief 分支立即拒绝失效依据；只重算一条分支时其余 99 条保持不可用 |
| C1-foundation | canonical commit 不自动 activation；旧 Context 保留 v1，新边界采用 v2，合法旧结果仍可使用 |
| ContextCommit-foundation | Observation 排除历史 Belief；校验、授权后取得 standing；权限撤销、上游 correction 与重复提交均被拒绝 |
| F2-injected-foundation | 注入跨学习者、资源、用途、操作与参数的越权请求，backend 拒绝并保留 source-linked SecuritySignal |

`seed_committed_fixture` 仅安装预先定义的 owner 记录。B/C 基础 Case 继续使用显式资格 fixture 来隔离状态机制；新增 Context / Commit / Security 路径使用真实后端检查，按 principal、purpose、subject、resource、operation、参数、有效期和撤销状态授权，数据授权另检查类型、目的地、retention 与 disclosure。Grant 配置来自测试预设，不包含生产 IAM 或治理运营。兼容性仍使用 exact version set fixture。

普通 `run_foundation.py` 不调用模型，语义检查明确标记为 `SCRIPTED-VALIDATION-FIXTURE`，仅验证 gate 的执行和绑定。生产式入口只能由独立模型调用生成语义校验记录；候选自报 PASS、复用其他候选的 PASS、校验未决、候选被改写、依赖失效或权限撤销，均不能取得 standing。拒绝结果保留在 execution / audit history，不写入派生语义记录；没有基于关键词的语义判定。

CurrentResolver 每次对内存副本作同步检查：选取当前用途的待检 revision 后，沿 exact CURRENT refs 递归校验；失败不回退旧 revision，不改写依赖。新 revision 存在本身不使旧 exact ref 失效；仅在依赖明确声明 `require_head` 或 `require_active` 时检查最新提交 / 激活条件。PINNED 只检查历史引用存在，不将其当作未来 effect 的 CURRENT 保证。有效期、correction、用途不匹配、循环、不同 CURRENT 分支的依据冲突及未知资格均产生 non-resolution。

Snapshot 的深拷贝是第一版的一致读取实现，已计入运行清单的复杂度记录；没有生产规模性能结论。FailureInjection 已接入 context freeze、candidate validation 和 commit revalidation，其余 Action / Replay 挂起点待后续路径接入。事实 correction 通过新记录使旧 exact basis 不可用于 current，历史仍保留；正式 correction authority 与更完整的 lifecycle 变更仍待后续步骤。

## DeepSeek 配置与真实连通验证

仓库根目录使用 `.env`，可由根目录的 `.env.example` 复制；若已有 `.env`，仅补充对应项。填写 `DEERMIND_LLM_API_KEY`，其余默认配置为官方 `https://api.deepseek.com`、`deepseek-flash`、最多 2 次调用、每次最多 1024 个输出 token、60 秒网络超时、无自动重试。环境变量优先于 `.env`；缺少 Key 不调用网络，Key 不进入日志或 RunManifest。

在 `src/spike` 下：

```powershell
python run_llm_smoke.py --check-config
python run_llm_smoke.py --run
```

第一条只检查本地配置，默认不带参数也只做预检。第二条会真正调用模型：先生成 Observation，再独立校验 exact candidate，最后由现有 backend 执行提交重验；只发送合成苹果题 fixture，不发送代码、历史 Belief 或工作区文档。该 fixture 将题面作为提交材料的一部分保留，尚未实现完整 Task / Claim 链。调用采用 JSON 输出、关闭 thinking；保留请求、输出、响应标识、usage、fingerprint、失败和提交记录，不保存模型的 reasoning_content。超时、HTTP 失败、空输出、JSON 不合法和截断均为明确失败，不替换成脚本成功。

生成与校验规则在 `protocols/observation-smoke-v*.json` 中版本化，并纳入内容哈希。当前默认 v2，历史 v1 可用 `--protocol-version v1` 显式选择，原文件与运行证据保留。此入口只验证真实调用到提交的集成，不代替 A1 三组输入的重复运行、A2 配对注入、Policy 判断或完整组合场景。使用相同模型做独立校验不构成正确性证明；结果需要结合保存的候选与规则复核。调用次数和输出 token 的上限不等于金额预算；此时不作费用估计。

## 语义误放回归

首次 v1 连通中，候选指出除法错误并复述最终答案 120，却没有表达最终总价不符；校验模型误称候选已指出 120 与正确值 105 不符并返回 PASS。运行时接受了该记录。原始批次 `llm-smoke-20260930T062159Z-a186de65d4e4` 保留其 PASS 与提交结果，附加复核记录指出语义误放，不改写历史。

v2 保持生成提示不变，只修改校验合同：按 method、division、final_result、grounding、boundary 五项分别返回 PASS / FAIL / UNRESOLVED；正向内容判据的 PASS 必须引用候选中的原文。完整性检查覆盖全字段；对整体 grounding / boundary 的否定须定位违规原文。程序核验引用存在性、候选字段、判据完整性，并按任一 FAIL → FAIL，否则任一 UNRESOLVED → UNRESOLVED，否则 PASS 汇总；不接受模型直接给出的全局 PASS。

引用存在不证明语义支持。引用 `Answer = 120` 的确可能来自候选，但它是否表达“答案错误”仍由语义规则 + LLM 判定。格式错误或虚构引用属于校验协议失败，不能当作成功识别了负例。引用检查与结果汇总在提交时再次执行，并仍绑定 exact candidate、Protocol / rule revision、Context 与 execution。

固定回归数据存于 `fixtures/observation-omission-v1.json`，内含原始候选及来源摘要，不依赖本地 runs 目录。正例只在原候选后补充最终总价错误与 105 的说明。运行以下命令可预检或执行一批两次调用（每个候选各校验一次，不重新生成候选、不自动重试）：

```powershell
python run_semantic_regression.py
python run_semantic_regression.py --run
```

仅当原负例的 final_result 被判 FAIL 且提交被拒、修复正例全部通过且可提交时，该批回归通过。模型失败或不合法输出记 INCONCLUSIVE，误放和误拒分别记录；全部输出、预设期望与失败保留在独立批次。该配对样例是定向回归，不是完整 A1 / A2 验证或统计可靠率估计。

## 新样例与重复运行

`fixtures/observation-stability-v1.json` 固定 8 个新样例，每个执行 5 次，共 40 次校验。正例覆盖英文改写、中文表述、真实且带归属的自述；负例覆盖最终判断遗漏、能力越界、教学建议、额外算术错误和虚构引用。同一自述候选分别配有／没有对应原话的来源，检查归属是否真正依据 Context。期望结果在执行前按文档边界固定，不发给被测模型。

该批直接固定 v2 文件内容哈希，不修改生成提示或校验规则，按固定种子安排五轮顺序执行。保留每次调用、逐项结果、失败与提交记录，并逐次更新 summary；不重试、不丢弃未决或中途修改期望。每项必须完成五次且符合预期，整批才能通过；全拒绝策略会计入正例误拒。相同输入与 temperature=0 的重复结果不能当作独立同分布统计样本。

```powershell
python run_semantic_stability.py --max-calls 40
python run_semantic_stability.py --max-calls 40 --run
```

第一条仅预检；第二条使用显式的本批调用上限，`.env` 默认值保持不变。预算不足会在调用前停止，不能靠逐次重建 adapter 绕过上限。摘要分别报告误放、误拒、未决、协议／运行故障、判据或提交不匹配，以及每个样例的结果分布；任何失败都保留原批次。样例由当前开发会话编写，未参与 v2 修改，但不是第三方盲测；范围仍是同一道题的候选校验，不代表完整 A1 / A2、跨题泛化或真实生成质量。

模型标识与请求格式依据 2026-09-30 查阅的 DeepSeek 官方 [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/) 和 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。别名可能随供应商升级，运行证据会同时保留实际返回的 model 和 fingerprint。

## 来源对应校验 v3

v2 的 40 次运行发现 5 次误放，全部是同一“虚构学习者自述”负例，且均提交为 Observation。实际请求中的来源没有那句话；保留的原始批次为 `semantic-stability-20260930T064409Z-bbdc564fa1c2`。当前 v2 对该来源真实性检查的失败不因后续修复而撤销。

v3 使用独立的 `protocols/observation-smoke-v3.json`。校验模型在五项判据之外，必须把候选全文划分为有序原文片段，为每段提供来源 ref / revision、字段及原文，并判断断言支持关系。程序要求片段覆盖全部候选非空白内容，精确来源属于已获准的 Context，且来源摘录确实存在；直接引语通过还要求被引原话存在于其引用的来源中。转述、翻译、说话人、否定含义及推导是否成立仍由显式规则 + LLM 判断，不用关键词分类。

来源检查与校验 execution 绑定，并在提交时再次核验。缺少覆盖、虚构来源或判据与断言结果矛盾都属于协议失败，不能当作成功识别负例。完整字面覆盖不证明每个逻辑断言都被正确拆解，存在的来源片段也不证明支持关系；这些仍是需要用反例检验的 LLM 语义职责。

`fixtures/observation-grounding-v1.json` 冻结 12 个样例，各运行 2 次，共 24 次：保留原 8 个样例，新增转述请求、错误说话人、跨语言自述和明确否认请求。5 个正例、7 个负例；正负例均要求语义结果与提交结果符合预期。新样例由开发会话编写，不是第三方盲测。运行期间不调参、不重试，也不修改预期：

```powershell
python run_semantic_stability.py --fixture observation-grounding-v1.json --max-calls 24 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-grounding-v1.json --max-calls 24 --max-output-tokens 3072 --run
```

第一条只预检；第二条执行真实调用。来源对应信息比 v2 输出更长，因此该批每次输出上限显式提高到 3072；`.env` 不变。未指定 `--fixture` 仍运行原 v2 设计，连通 smoke 默认也保持 v2。历史协议、fixture 与运行结果不被替换。

## 原文不存在判断与一次复核 v4

v3 取得了原虚构自述反例两次拒绝的证据，但真实自述正例出现一次“原话存在却被判不存在”的误拒；另有 7 次传输失败，整批 NON_SUCCESS。原始结果与限制见 `reports/observation-grounding-v3-20261002.md`。

v4 新增明确的支持／否定原因：supported、text_absent、speaker_mismatch、meaning_mismatch、uncertain。原文不存在只能用于直接引语；转述／翻译仍判断语义支持，不能因字面不同而否定。说话人或含义不支持必须引用来源。程序仅对 text_absent 在已获准 Context 的字符串字段中做精确查找，不扫描其他存储，也不以关键词解释含义。

如果找到模型声称不存在的原话，原始输出保持不变，其校验记录的有效结论为 UNRESOLVED。运行时最多发起一次专门复核，附上原话所在的精确来源字段与上下文，要求重新判断全部候选。复核前重新授权读取；每次结果均保存，新记录关联 previous_review_id。原文存在不自动产生 PASS。复核仍有矛盾、输出不合法、网络失败或预算不足时阻止提交；同一已注册候选重复调用不会开启第三次校验或暗中重试。该实现采用当前 Spike 内存 Runtime 的候选及执行记录，不声称完成了跨进程恢复。

传输失败使用固定脱敏类别区分超时、DNS、TLS、连接重置／拒绝、远端断开和响应不完整；不保留异常原文，不自动重试。

`fixtures/observation-absence-v1.json` 保留 v3 的 12 个样例及预期，每项 2 次，共 24 次初始校验；每个候选最多一次条件复核，全批最多 48 次模型调用。不是未参与设计的独立测试集。摘要同时记录初次矛盾数、复核调用数和复核失败数；24 次最终判定全部符合预期才可报告本批 PASS，初次错误仍保留：

```powershell
python run_semantic_stability.py --fixture observation-absence-v1.json --max-calls 48 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-absence-v1.json --max-calls 48 --max-output-tokens 3072 --run
```

第一条仅预检；第二条执行真实调用。未发生矛盾时不消耗额外复核预算，`.env` 不变。默认 smoke 和默认 stability fixture 保持既有版本。

## 支持不足、含义矛盾与未决 v5

v4 的 24 次实验中，10 次正例通过、7 次负例正确拒绝，但有 4 次协议错误和 3 次远端断开；未触发真实存在性复核，整批 NON_SUCCESS。见 `reports/observation-absence-v4-20261002.md`。

v5 增加 `unsupported → FAIL`，表示模型检查本次提供的完整材料后，能够判断该非引语断言缺少支持；不宣称断言在现实中必然为假。`meaning_mismatch` 继续表达来源与陈述矛盾，`uncertain → UNRESOLVED` 表示无法判断支持关系。对转述／翻译，字面措辞不同不能推出 unsupported；对直接引语，不允许用 unsupported 绕过精确原文存在性检查。

每个片段增加 `inspected_sources`，用精确 ref / revision 与字段声明已检查范围。unsupported 必须覆盖本次 Context 所有字符串字段，不得遗漏、重复或引用范围外记录；可不捏造用于证明缺失的原文摘录。其他类别可使用空范围声明，但仍遵守其原有引用要求。程序只检查这个声明的结构和范围，不把它当作语义推理正确性的证明。职责越界由 boundary 单独判断：支持关系未决与明确的职责违规可以并存。

v5 保留 v4 的原文矛盾处理与一次复核上限。完整的旧协议、fixture 和运行结果保留。新增设计 `fixtures/observation-support-v1.json` 包含原 12 个样例，加上第二种解法有／无来源、独立作答请求转述被支持／被否定两组新样例；16 项各 2 次，共 32 次初始调用，最多 64 次（仅矛盾可复核，无网络重试）。7 个正例、9 个负例；这些仍是开发者编写的数据，不是独立盲测。

```powershell
python run_semantic_stability.py --fixture observation-support-v1.json --max-calls 64 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-support-v1.json --max-calls 64 --max-output-tokens 3072 --run
```

第一条仅预检，第二条运行冻结批次。逐次保存原始模型输出、有效判断、协议错误、初次矛盾和条件复核，失败不以新调用替换。

## 算术提取、语义映射审查与精确验算 v6

v5 出现“理由已说明 8×15＝125 错误，但状态仍为 PASS 并提交”的误放，以及合法请求转述误拒，详见 `reports/observation-support-v5-20261002.md`。v6 聚焦前者，尚不解决一般转述支持关系的可靠性问题。

每个候选先用一次独立 LLM 调用提取算术断言：带 exact candidate 原文定位的有序全文片段，以及 operator、left、right、value 和 stance。stance 区分 asserted_true、asserted_false、reported_only。提取必须保留候选实际声称值，不能先修正为正确值。程序使用有理数精确执行四则运算，不用 float 比较，不执行模型生成代码；数字仅接受有界十进制字符串。语义提取仍由 LLM 完成，数字格式语法检查不解释自然语言。

随后第二次 LLM 调用执行来源／边界校验，并新增 arithmetic_mapping 判据，检查提取是否完整且忠实，包括数字、操作、否定及转述关系。提取遗漏或失真时有效结论为 UNRESOLVED，不能拿错误提取计算出的结果否定候选。映射通过后，精确算术 FAIL 可以覆盖 LLM 的语义 PASS。原文存在性矛盾仍记 UNRESOLVED，并最多复核一次；复核复用已绑定提取，不重做提取或无限调用。各阶段之间重新验证数据访问权限。

提交时重新读取绑定 exact candidate / Context / Protocol / rule 的提取 execution，执行相同精确计算并核对保存结果。LLM 判断、算术判断和最终有效状态分别保留。完整字面覆盖不证明提取忠实；映射审查本身仍可能错误，这是单独的语义风险。除零或无法在本版有界二元四则运算内表达的断言保留为未决，不默认为通过。仅转述来源里的错误等式不等于候选自己断言该等式正确。

`fixtures/observation-arithmetic-v1.json` 固定 8 项算术样例，各 2 次，共 16 个候选执行：基线、错误／正确乘法、正确／错误否定、转述错误等式、正确／错误十进制加法。每个候选通常两次模型调用，共计划 32 次；至多 16 次条件复核，总上限 48 次。提取失败则该候选停止，不追加调用或补跑。旧 runner 的 fixture 字段 planned_model_calls 在该设计中仍用于候选执行数；initial_model_calls、manifest 的 planned_calls 和实际 model_calls 分别标明计划初始 API 数与实际 API 数。

```powershell
python run_semantic_stability.py --fixture observation-arithmetic-v1.json --max-calls 48 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-arithmetic-v1.json --max-calls 48 --max-output-tokens 3072 --run
```

第一条仅预检，第二条执行固定批次。摘要新增 extraction_calls 与 arithmetic_overrides；逐项记录 llm_semantic_status、arithmetic_status、effective_status，避免将程序拦截误报为 LLM 正确判断。v6 校验提示为容纳独立提取结果而重新组织、缩短；本批是组合方案实验，不能将效果差异仅归因于精确计算机制。

## 严格结构输出实验 v7

v6 的 16 次执行中，13 次符合预期，另有两次无效 JSON 和一次远端断开，详见 `reports/observation-arithmetic-v6-20261003.md`。v7 保留 v6 的全部语义规则、算术提取与映射审查、八项样例、预期和顺序，只增加结果交付说明及 JSON Schema，实验范围是结构输出稳定性。

依据 2026-10-03 查阅的 DeepSeek 官方 [Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/) 与 [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)，使用显式的 `https://api.deepseek.com/beta` 端点、关闭 thinking、`strict: true` 和强制指定函数名。本实验的函数仅是固定结果包，不执行外部操作。协议保存 generation、extraction、validation 三个结构定义；对象字段全部必需且不允许额外字段。直接引语的 reported_quote 保留字符串／null 表示，供应商是否接受完整 schema 必须以真实调用验证，不能由本地模拟测试推出。

适配器只接受一个指定函数的结果，要求 finish_reason 为 tool_calls，并严格解析 arguments；本地再次检查 schema、精确引用、候选覆盖、算术及提交权限。缺失、额外字段、未知函数、多函数、无效 JSON、截断及连接失败都保留失败证据，不回退到普通文本、不修复输出、不自动重试。结构正确不证明语义正确，原有误放反例仍有效。

`fixtures/observation-structured-v1.json` 固定 16 个候选执行，计划 32 次初始调用，含条件复核的上限 48 次。首次调用也属于本批次；遇到声明的 HTTP 400、401、403、404、422 时停止整批，保留失败并列明剩余未运行样例，避免反复发送供应商不接受的请求。其他候选失败按固定顺序继续。所有 API 结果在本候选结束时写入证据；目前不保证进程在两阶段之间被强制结束时，当前候选的已完成调用已经落盘。

```powershell
python run_semantic_stability.py --fixture observation-structured-v1.json --base-url https://api.deepseek.com/beta --max-calls 48 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-structured-v1.json --base-url https://api.deepseek.com/beta --max-calls 48 --max-output-tokens 3072 --run
```

第一条仅预检，第二条执行冻结批次。端点通过本批显式参数与协议一致性检查，授权数据目的地同步绑定该端点；`.env`、旧协议和历史批次保持原样。变化包含 beta 路径、结果包及交付说明，不能把与 v6 的差异仅归因于某一个因素。

## 使用 v7 复查完整来源支持样例

v7 算术批次的真实结果为 15/16 符合预期，一次远端断开；30 个返回结果均无结构错误，但错误否定样例两次被 LLM 判为语义 PASS，最终由精确算术拦截。见 `reports/observation-structured-v7-20261003.md`。这不足以解决一般转述支持关系，后续回归使用独立的 `fixtures/observation-support-structured-v1.json`。

该设计保留 v5 全部 16 项候选、来源、预期和调度顺序，每项 2 次；直接使用冻结的 v7 协议，不改语义规则。每次新增算术提取与映射审查，共计划 64 次初始 API 调用，含最多一次来源存在性复核的总上限为 96 次。原有 grounding、boundary 等预期全部保留，另要求 arithmetic_mapping=PASS 和对应算术预期；即使程序成功阻止错误提交，若原有判据判断错误，仍记录判据不匹配，不能把该样例报告为完全符合预期。重点包括此前误拒的独立作答请求转述及其来源矛盾配对、错误说话人、跨语言自述、明确否定、虚构自述与第二解法有无来源。

```powershell
python run_semantic_stability.py --fixture observation-support-structured-v1.json --base-url https://api.deepseek.com/beta --max-calls 96 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-support-structured-v1.json --base-url https://api.deepseek.com/beta --max-calls 96 --max-output-tokens 3072 --run
```

第一条只预检，第二条执行新批次。沿用 v7 的供应商配置失败停止规则，无网络重试和输出修复。相较 v5，协议内容、算术流程与传输方式已有变化，结果只用于定位现存问题，不单独证明某项改动的因果效果，也不代替新样例或独立盲测。

## 来源字段编号与统一交付说明 v8

v7 完整来源支持回归为 24/32 符合预期，五次多余闭合括号、一次额外 arguments 包装、两次错误来源字段，详见 `reports/observation-support-structured-v7-20261003.md`。严格接口仍可能返回不合法结果，本地检查不可省略。

v8 由运行时在获准读取的 Context 中，为每个字符串字段生成本次调用内的 source_registry：handle、exact ref/revision、field、完整原文。模型的 sources 和 inspected_sources 仅选择该表中的编号；实际发送的 schema 枚举限于本次编号。程序按固定映射还原既有来源结构，保留原始 wire_output、source_registry 与展开后的 details，提交时从 exact Context 重新生成映射并核对展开结果。这是调用前声明的数据表示，不是错误返回后的修补；未知或重复编号、旧版 ref 对象都拒绝，不搜索字段、不猜测或重绑定引用。来源引用使用完整原字段，直接引语存在性和完整检查范围要求继续生效。

编号只确定所指材料，模型仍须判断材料是否支持候选，包括说话人、否定、转述和边界。选择有效编号不证明语义支持；原文存在性矛盾仍最多复核一次，保存两次原始结果，复核前重新授权。算术提取、映射检查和精确验算继续执行。各阶段交付提示统一为调用指定结果函数，不再同时要求普通 JSON 文本回复；任何不合规结果继续保留失败，不自动删除括号或解包。

`fixtures/observation-source-handles-v1.json` 选取 v7 发生故障的六种样例及独立作答请求正例配对，共七项，每项两次，14 次候选执行、28 次计划初始 API、最多 42 次（含条件复核）。样例及全部预期保持原样；这是看过失败后的定向回归，不是盲测，也不覆盖全部旧样例。两个表示／交付改动共同实验，不能分离各自效果。

```powershell
python run_semantic_stability.py --fixture observation-source-handles-v1.json --base-url https://api.deepseek.com/beta --max-calls 42 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-source-handles-v1.json --base-url https://api.deepseek.com/beta --max-calls 42 --max-output-tokens 3072 --run
```

## 逐断言归属、来源支持与职责边界 v9

v8 的定向回归为 12/14 符合当时预设指标，两次额外包装失败；额外审查发现同一个被来源否认的自述候选，boundary 一次 PASS、一次 FAIL，见 `reports/observation-source-handles-v8-20261003.md`。v9 据此补足逐片段测量，沿用 Interaction Space §3 的自述归属边界和 AI Runtime §6.6 的语义／确定性分工，不修改上位文档或 owner。

新协议要求每个 claim 增加 attribution（speaker: system/learner/other/unresolved；stance: reported/endorsed/unresolved）及 boundary_status。归属描述候选将陈述归给谁、是否仅为转述；原材料缺失、否认或属于另一说话人，改变的是来源支持，不能自动把候选改判为系统独立认定。转述后追加系统结论必须分段。系统对本次步骤或算术的局部观察可以在职责内，系统独立能力结论或教学决策属于越界；这些内容判断全部由规则约束下的 LLM 作出。

程序只校验枚举、完整结构和汇总一致性：boundary 等于各 claim 的 boundary_status 汇总；新增 attribution 判据仅表示所有片段归属已确定，遇到 unresolved 则为 UNRESOLVED，不表示被报告的事情真实。来源支持沿用 grounding。原始元数据连同来源映射保留，并在提交时复核。合法枚举及汇总一致也不能证明模型分类正确。

`fixtures/observation-claim-axes-v1.json` 冻结十项、每项两次，共 20 次候选执行、40 次计划初始 API、最多 60 次。前四项使用完全相同的候选自述，分别提供支持、否认、缺失和错误说话人的来源；另覆盖学习者／教师的能力报告、系统直接能力认定、转述后追加认定、请求被升级为系统行动建议，以及独立作答请求。各例明确给出所有判据及关键候选片段的 speaker、stance、boundary_status 预期。

runner 在得到审查结果后按候选原文定位离线标签，不将标签、样例名称或预期发送给模型；它既不以关键词作生产语义判断，也不改写模型结果。跨越多个预标注片段的大 claim 必须同时满足各片段预期，不能把混合归属藏在一句理由中。任何标注片段不匹配都会降低 matched_runs，另记 claim_axis_mismatches，即使最终拒绝正确也不能被计作完整通过。旧 fixture 没有此指标，跨版本总分不能直接等同。

```powershell
python run_semantic_stability.py --fixture observation-claim-axes-v1.json --base-url https://api.deepseek.com/beta --max-calls 60 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-claim-axes-v1.json --base-url https://api.deepseek.com/beta --max-calls 60 --max-output-tokens 3072 --run
```

这些样例由开发会话根据已知反例编写，不是独立盲测。额外结果包装、来源错误或网络失败仍然拒绝且不自动修复；语义正确率与协议执行成功率分开报告。

## 独立职责分类与准入 v10

v9 的学习者请求升级为系统教学建议样例两次误放并提交，已命中 AA-A02 的预注册 falsifier，结论见 `reports/assumption-aa-a02-v9-20261003.json` 与 `reports/observation-claim-axes-v9-20261003.md`。原 AA-A02 保留 DENIED。v10 是新增必要检查的修订实验，不能把后续局部成功回填成原假设获支持。

每个候选先调用一次专门的 LLM 职责分类，只判断完整候选各段表达的是 local_observation、attributed_report、ability_inference、evidence_inference、action_recommendation 或 uncertain，不回答某个行动是否合理、受欢迎或得到请求。分类器读取同一获准原材料与候选，不读取其他模型审查结果。自然语言归类仍由语义规则与 LLM 完成；程序仅核验全文覆盖、标签结构并执行协议显式声明的准入表：前两类允许，三种推断／建议类别拒绝，uncertain 未决。没有从措辞或关键词直接推导类别的分支，错误 LLM 分类仍是剩余风险。

后续依次进行原有算术提取和未经改写的 v9 综合审查，综合审查看不到前置职责分类。该实验在有效的负面分类后仍继续原审查，以测量分歧，不代表产品必须采用相同调用成本。任一步骤执行失败停止该候选；有效的分类记录保留，不能把后续失败算作端到端成功。提交要求原有检查和独立职责准入均通过。分类记录绑定 exact Candidate/Context/Protocol/rule，提交重算准入并核对绑定；每次新外发调用前重验数据访问。来源存在性复核复用同一分类与算术提取，不重做分类或隐藏重试。

`fixtures/observation-responsibility-v1.json` 包含八项各两次：保留 v9 的请求升级反例、被否认的自述、转述后追加能力认定、独立作答请求，新增同源讲解请求报告、委婉教学建议、暂缓讲解建议、教师教学建议的纯转述。全部旧预期保留，并为关键片段增加职责类别及准入预期。程序拦截后，错误的综合审查判据仍计为不匹配；不能把组合门拦截说成原审查已改正。

计划 16 次候选执行、48 次初始 API、含最多一次来源复核的总上限 64 次。摘要增加责任分类调用数、逐片段类别不匹配，以及原审查与算术已通过但被职责准入阻止的次数。模型相同，只隔离调用任务与结果输入，不声称统计独立；样例是开发者编写的定向回归。

```powershell
python run_semantic_stability.py --fixture observation-responsibility-v1.json --base-url https://api.deepseek.com/beta --max-calls 64 --max-output-tokens 3072
python run_semantic_stability.py --fixture observation-responsibility-v1.json --base-url https://api.deepseek.com/beta --max-calls 64 --max-output-tokens 3072 --run
```

## D1/D2 行动与帮助披露机制

`python run_action_exposure_validation.py` 执行 `fixtures/action-exposure-v1.json` 固定的 D1/D2 机制范围，不调用模型。Observation、Policy 选择及 Evaluation 意义均明确使用脚本 fixture，PolicyOutcome 和 Claim-relative Evidence 通过共享正式提交；`ActionRuntime` 负责 exact intent、执行前权限及依据重验、mock 展示确认、Occurred / NotOccurred / Indeterminate 和终态幂等性。

只有实际确认展示的内容进入 ActionOccurrence。按响应重建的 exposure view 不持久化为独立 authoritative Model，也不推断学习者确实使用了提示。D2 分别保留任务非独立成功、帮助前已存在策略、局部算术仍可能有正面证据三种解释，不冻结 strength。当前受控时钟、单进程 mock 和整个 Policy 依据被列作 effect-critical 的范围见 `reports/action-exposure-design-20261004.md`；这不提供真实 Policy、真实 UI 或 A2 语义结论。

## E1 真实 Policy 有界验证

`python run_policy_validation.py` 只做配置预检；加 `--run` 预留唯一 `runs/policy-e1-v1` 并运行 open / help / wait 各五次，总预算 45 次模型调用，无重试或替补。真实 Policy、内容校验和独立测试评分经共享 Runtime 留存，固定 Observation 输入及 mock 展示边界明确标注。ActivityConstraints 的 exact action 范围在共享正式提交时重验，NoIntervention / Defer 不创建 ActionIntent；测试评分发生在提交和可选 effect 之后，不能代替生产校验。规则、停止条件和支持范围见 `reports/policy-e1-design-20261004.md`。此入口不重开 Observation S1/S2。

## E2 单会话完整轮次串行

`python run_serial_validation.py` 只预检；加 `--run` 预留唯一 `runs/serial-e2-v1`。三个同源快照分支各五次，总上限 40 次真实 Policy / 校验调用：普通输入在 reasoning 期间排队；外部 owner 在提交前更新 shared Belief；以及 Intent 形成后、effect 前更新依据。`SerialSession` 把排队、Context、正式 outcome、Intent、行动结果处理与轮次收束关联；CURRENT + require_head 在 Context 形成和正式提交 / effect 时检查。不得靠强行选择 Execute 填满覆盖，具体范围和停止条件见 `reports/serial-e2-design-20261004.md`。

## F1/F2 语言自授权限与委托范围

`python run_security_validation.py` 只预检；加 `--run` 预留唯一 `runs/security-f-v1`，十个变体各五次、最多 50 次真实模型调用。真实候选通过共享 BoundaryRuntime 生成，在 `ToolBoundary` 经同一个 SecurityRuntime 检查。模型自称权限、身份或工具结构都不安装 grant。模型拒绝、模型实际请求及显式脚本攻击分开记账，每分支包含合法读取和合法候选暂存正对照；execute / 治理接收器为 mock。记录不会获得正式 Policy standing，完整范围、控制组与停止条件见 `reports/security-f-design-20261004.md`。固定离线审计入口为 `python reports/audit_security_f.py`。

## X1/X2 在途决策组合

`python run_composition_validation.py` 预检；加 `--run` 预留唯一 `runs/composition-x1-x2-v1`。correction、兼容版本启用、显式版本撤销三分支各五次，最多 50 次真实 Policy / 校验调用。前两条完整路径还包含收束后的新 Context 和真实重新决策。追加的 `VersionRevocationOccurred` 受信治理 fixture 保留 exact target / scope / purpose / source，提交及 effect 的共享 resolver 检查当前资格，不改写旧版本记录。范围见 `reports/composition-x1-x2-design-20261004.md`；离线审计为 `python reports/audit_composition_x1_x2.py`。激活和撤销都是治理输入 fixture，不是生产治理授权验收。

## X3/X4 实际披露与受权限约束的历史回放

`python run_history_composition_validation.py` 预检；加 `--run` 执行唯一 `runs/composition-x3-x4-v1`，无外部模型调用。X3 经正式 O/E/B 提交、受信 correction 和逐项重算检查实际帮助历史不变；X4 三个同源分支分别拒绝 replay 数据授权、原始材料读取和未获数据授权的用途，并包含合法回放与重新授权恢复对照。认知及 provider 为明确脚本 fixture，机制复用现有 Runtime。范围见 `reports/composition-x3-x4-design-20261004.md`，离线审计为 `python reports/audit_composition_x3_x4.py`。

**基础检查或连通验证 PASS 不等于 Architecture Assumption SUPPORTED。** 完整 A1/A2 和跨边界组合只按各自报告的范围评估，Gate E / F 保持 `OPEN`。运行清单中的整体 `UNVALIDATED` 不覆盖已有具体失败证据；正式假设审查必须纳入反例，命中声明的 falsifier 时按设计判为 `DENIED`，不能用后续修复抵消。
