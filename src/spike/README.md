# DeerMind Architecture Spike — deterministic foundation

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

**基础检查或连通验证 PASS 不等于 Architecture Assumption SUPPORTED。** 真实 API 已连通，首次语义误放已登记并形成定向回归。完整 A1/A2、Policy、Action、Replay 和会话串行链仍待执行，AA 保持 `UNVALIDATED`、Gate E / F 保持 `OPEN`。
