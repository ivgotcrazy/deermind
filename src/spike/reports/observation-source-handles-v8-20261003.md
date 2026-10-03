# Observation v8 来源字段编号实验

日期：2026-10-03。批次：`semantic-stability-20261003T065754Z-59342328ef09`。结论为 NON_SUCCESS：14 次候选执行中，12 次符合冻结的预期，8 次正例提交、4 次负例拒绝；两次提取返回额外 arguments 包装，被本地结构检查拒绝，未形成语义判定。最终未出现错误提交。原始审查还显示一次未纳入原预设指标的 boundary 判断不一致，不能将“符合预设结果”解释为每一项语义判断都正确。

## 问题与实现

此前完整 v7 来源回归在 32 次候选执行中有 24 次符合预期、8 次格式或引用协议失败，见 [v7 来源回归报告](observation-support-structured-v7-20261003.md)。其中两次引用失败分别把题目原文标为 text 字段、把 text 字段写为 content.text；其余六次是 JSON 多余闭合括号或额外结果包装。这些失败没有被修补或重新计为成功。

v8 新增 `foundation/source_handles.py` 和独立协议 `protocols/observation-smoke-v8.json`。运行时在重新授权后的 exact Context 中，为每个字符串字段生成固定的 source_registry，包含本次编号、精确 ref/revision、字段及完整原文。模型为 sources 与 inspected_sources 选择编号，动态 schema 的枚举限定为本次已提供的编号。程序按预先确定的映射还原既有来源结构，不让模型重复抄写字段路径、版本或来源原文；引用粒度为完整原字段。未知或重复编号及旧式引用对象均拒绝，不猜测、不跨字段搜索重绑定。

每次审查的执行证据同时保存 wire_output、source_registry 与展开后的 details。提交时从同一 exact Context 重建映射，重新展开原始编号结果，与已保存审查核对，防止换源后重用判定。旧版协议继续使用原有引用结构。原文存在性矛盾最多一次复核、逐阶段授权重验、算术提取与映射审查、精确验算和提交权限检查均保留。

同时将三个阶段的结果交付说明统一为指定函数的参数，不再同时要求普通 JSON 文本返回。这里只调整来源表示与交付要求，来源支持、否定、说话人、归属及职责边界仍由显式规则和 LLM 判断。合法编号只证明引用位置合法，不证明材料支持候选；直接引语仍必须确实存在于所选来源。两个改动在同一版本组合验证，不能独立归因。

## 冻结设计与本地验证

`fixtures/observation-source-handles-v1.json` 选取 v7 出现故障的全部六种样例，并加入独立作答请求正例作为矛盾样例的配对，共七项各两次。候选、来源、全部预期均与 v7 中相同，不因旧失败而降低要求。该集合是在查看 v7 结果后选出的定向回归，不是未见样例或独立盲测，也不覆盖完整旧样例。

运行前 128 项本地测试全部通过。新增 9 项检查覆盖编号与 exact revision/field/原文绑定、未知和重复编号、限定本次枚举、原预期保留、原始及展开数据共同留证、篡改映射与原始编号后的提交拒绝、合法编号不能绕过直接引语存在性、unsupported 的完整范围声明，以及一次复核复用固定来源映射并保留两次原始输出。

计划初始 API 调用 28 次，含来源存在性复核最多 42 次，实际为 26 次：14 次提取尝试和 12 次语义审查。两次提取结构失败后不再审查该候选，没有网络重试、修复或补跑。没有传输失败，没有来源矛盾复核或算术覆盖语义 PASS。运行期间不修改代码、提示、样例或预期；结束时冻结清单的全部文件哈希一致。

协议 SHA-256：`a8b96724a5d07ef095308982d19f467d8aa767fa68914fd827c9b242a02a04bc`。

```powershell
python src/spike/run_semantic_stability.py --fixture observation-source-handles-v1.json --base-url https://api.deepseek.com/beta --max-calls 42 --max-output-tokens 3072 --run
```

## 真实结果

| 样例 | 预期 | 第一次 | 第二次 |
| --- | --- | --- | --- |
| 有来源自述 | PASS | PASS | PASS |
| 越界推断能力 | FAIL | 提取多余包装 | FAIL |
| 转述讲解请求 | PASS | PASS | PASS |
| 中文自述转述为英文 | PASS | PASS | PASS |
| 来源明确否认请求 | FAIL | FAIL | FAIL |
| 独立作答请求合法转述 | PASS | PASS | PASS |
| 独立作答请求被来源否定 | FAIL | FAIL | 提取多余包装 |

仅比较相同七项及相同预设结果，v7 为 6/14 符合预期、8 次协议失败，v8 为 12/14 符合预期、2 次协议失败。该对比仍不是因果或总体可靠性证明，提示、表示及运行时刻同时变化。原先完全没有有效判定的真实自述和跨语言自述，本批各两次通过；合法独立作答请求仍两次通过。六个负例执行中只有四个形成有效判定，另外两个不能计为正确拒绝。

两次失败均发生在 ArithmeticExtraction，分别为 latent_ability_negative 第 1 次与 independent_request_contradiction_negative 第 2 次。finish_reason 为 tool_calls，但原始函数参数形如 `{"arguments":{"segments":[...]}}`，而所需根结构为 `{"segments":[...]}`。因此报 OutputSchemaMismatch，没有解包后继续。统一交付提示仍不足以排除该问题。本批没有多余闭合括号、来源地址错误或未知编号，但不能由零次观察推断这些问题不会再出现；本地结构与来源验证仍是强制边界。

## 额外语义审查：来源矛盾与职责越界仍会混淆

`negated_request_negative` 的候选末句为 “The learner reported uncertainty about division and requested an explanation.”，原始来源明确否认学习者说过不确定除法或请求讲解。两次 grounding 均为 FAIL，符合来源矛盾预期，最终都拒绝提交。

然而两次 boundary 不一致：第 1 次 PASS，理由正确区分了学习者自述形式和系统能力推断；第 2 次 FAIL，理由将相同的候选称为未归属的系统推断。第二次理由没有保留候选明确标示的报告归属，将来源不支持与职责越界混在一起。这是审查者对原始输出的额外语义核查，未修改冻结标签。原 fixture 对该负例只要求 grounding FAIL 和 arithmetic_mapping PASS，因此摘要仍按预设指标计为符合预期；这一统计不能掩盖 boundary 子判断的问题。

后续应冻结单独的归属／来源／职责边界配对样例，分别检查“是谁的陈述”“来源是否支持”“是否为系统独立推断”三项，避免以最终拒绝掩盖错误理由或错误子判据。来源是否支持仍不能由关键词、编号存在或结构完整性推导。当前不增加新的自动重试，也不以不合规包装的事后解包冒充供应商遵守协议。

## 证据与限制

实际请求使用 deepseek-flash、beta 端点、thinking disabled、temperature 0、输出上限 3072、timeout 60 秒。26 次均有 usage，输入 51,238、输出 18,493、合计 69,731 token。全部响应 fingerprint 为 `aeb56401ca74e127821c4f9126dcb669`。

运行后重新验证了 24 个结构有效返回，并对全部 12 次语义审查，从实际发送的 Context 重建 registry、展开 raw wire、重新计算算术，与保存 execution 完全一致。未发现来源映射被改变或引用漂移。这些是结构与数据绑定证据，不替代语义正确性检验。原始运行目录为 `src/spike/runs/semantic-stability-20261003T065754Z-59342328ef09`，仍保留两次失败。

| 文件 | SHA-256 |
| --- | --- |
| manifest.json | `cb88982147dd08da3480a1e5ab1ac8c67d0d334cf8499a2ed1899a6305f4a69e` |
| summary.json | `112accc2f36e735d6544a6ff8321be8bbc1fddd8a0dfa319de2734f1e8b8aa06` |
| evidence.jsonl | `82e2c052103f8c6a891dd607e391f1bb46a6a66e907c9a7607de9ff6a84ea0b6` |

当前结果支持保留来源编号这个结构约束，并继续针对职责边界做独立语义实验，但不能宣称整体可靠。完整 A1/A2、Policy、Action、Replay 和串行会话验证未完成，Gate E/F 仍为 OPEN；过去的误放、误拒及新发现的子判据错误全部继续有效。
