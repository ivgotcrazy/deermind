# 算术表达与精确字段合同：实现和本地验证 v1

日期：2026-10-05。结论：声明的本地机制范围 PASS，真实语义质量未验证。

## 1. 本次交付

[算术表达合同 v0.1](../../../doc/system-design/DeerMind_Arithmetic_Expression_Contract_v0.1.md)与独立的 [v12 实验协议](../protocols/observation-expressions-v12.json)已实现。新表示明确区分 NumericAssertion、UnevaluatedExpression、UnresolvedNumericMapping。`42÷6=?` 可保留未给出的结果为 null；程序不会补成 7，也不会用问号等文本特征决定表达类型。

候选全文按 exact field 和原文覆盖；表达引用唯一定位到所属片段，结果保留字符位置和 exact Context 来源字段。候选字段在职责分类、表达抽取及综合审查 schema 中均显式限定为 `description`，不接受 `candidate.description` 等别名。协议注册预检查字段、类型、必要判据和实际规则的对应关系；正式提交重新核算绑定的表达结果，不能复用其他候选的提取或伪造计算结果。

计算检查和语义映射继续分工。未求值项的单项计算状态为 NOT_APPLICABLE，整体提交仍必须通过 arithmetic_mapping 及其他所有必要检查。准确转述错误等式与系统认可其正确性分开处理。测试显式注入“把错误断言标为未求值”和“空列表遗漏算术项”，证明语义映射失败或未决会阻止提交；这不证明 LLM 一定能发现这些错误，提取与审查同时误判仍是保留风险。

## 2. 固定离线验证

唯一运行目录为 [expression-contract-v1](../runs/expression-contract-v1/summary.json)。一次完整回归完成 250 项测试，失败、错误、跳过均为零；包含新增 14 项定向测试、九组固定的[手工映射](../fixtures/expression-contract-v1.json)。[测试输出](../runs/expression-contract-v1/unit-tests.txt)、14 份 JSONL 与[冻结清单](../runs/expression-contract-v1/manifest.json)已保留。运行入口 [run_expression_validation.py](../run_expression_validation.py)阻断网络并拒绝覆盖原目录。

53 份 adapter 记录全部来自显式本地脚本 transport，真实模型调用和网络连接尝试均为零。最大 fixture 输入为 14640 字符，未超过当前 16000 字符限制；这只是这些样例的观测，不代表更长候选或来源已经验证。定向范围包括三种表达、混合报告与补充计算、错误字段、错误与重复来源、片段缺失或歧义、缺少必要含义、未决映射、跨候选复用及提交重算。

离线复核确认 156 个冻结输入、16 个运行文件指纹、18 份历史快照一致；另有 18 条计算记录供检查。此前 284 条证据索引经原文件或归档源码核对通过。修改前的两个共享源码已[归档](source-baseline-expression-20261005/index.json)，历史批次、协议和评估没有重写。完整统计见[限定评估](expression-contract-assessment-20261005.json)。

## 3. 结论的边界与后续工作

新协议需要显式选择，没有切换既有 A1/X5 或其他固定运行入口的默认协议。v11 的生成要求、职责准入及原有必要判据保留，仅扩展算术映射要求和表示合同。局部脚本通过不能被计为真实模型接受率、内容正确率或语义误放修复；原 A2 DENIED、X5 INCONCLUSIVE、完整验收 9/17 及 Gate E/F OPEN 均保持不变。

不完整作答的 profile 仍需明确必要含义的适用条件：不能要求输入中不存在的最终作答判断，也不能在输入确有完整作答时省略最终结果判断。该问题应在规则与语义样例层处理，不由代码搜索“?”或固定词语决定。下一步应将内容成立、必要含义完成、校验执行状态分开记录，并据此明确完整与不完整作答的适用规则；随后处理 A2 下游准入及 E1 评分责任。真实远端停止与效果对账继续属于未实现范围。本次未启动追加真实批次。
