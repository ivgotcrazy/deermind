# DeerMind Arithmetic Expression Contract v0.1

日期：2026-10-05。状态：实验协议及本地机制实现；未取得真实语义验收，不替换现行基线。

## 1. 范围与既有要求

本合同落实[Observation 校验与轮次关闭修订草案](DeerMind_Observation_Validation_Turn_Closure_Revision_v0.1.md)中的算术表达和精确字段部分。A1 曾将尚未求值的 `42÷6=?` 中的问号放入数值槽，使必须完成的校验无法执行。本次通过明确表达类型消除合同本身的混淆，不将未求值结果补成正确答案，也不降低校验要求。

实现采用独立的 [observation-expressions-v12.json](../../../../src/spike/protocols/observation-expressions-v12.json)，以 `arithmetic_extraction_format=typed-expressions-v1` 选择新表示。旧协议与固定批次保持原样。新协议保留 v11 的生成要求、职责准入表和全部判据，进一步明确 `arithmetic_mapping` 的类型、归属与来源完整性要求。完整作答的 method、division、final_result 要求没有改写；因此，本合同本身不意味着旧完整作答 profile 已适用于所有不完整作答。

## 2. 精确表示

提取结果由覆盖候选全部字符串字段的有序 segments 组成，每段包含 `field`、`text`、`coverage`、`expressions`。`field` 必须是候选真实字段名，当前为 `description`；`candidate.description` 与 `content.description` 均不接受，也不自动修正。没有算术含义的段仍须保留，表达项可以为空。全文覆盖只证明没有遗漏文本段，不证明段内含义已被正确识别。

每个表达项包含 `type`、`text`、`speaker`、`sources`、`stance`、`operator`、`left`、`right`、`value`、`reason`。表达原文必须在所属段中精确且唯一定位；重复短句可以通过拆分段或扩大引用来区分，程序不猜测发生位置。检查结果保留从零开始、左闭右开的候选字段字符位置。sources 引用同一冻结 Context 的原始字段 handle，程序展开为 exact ref、字段和原文；handle 有效只证明位置存在，不证明语义来源正确。

| 类型 | 必需约束 | 确定性结果 |
| --- | --- | --- |
| NumericAssertion | 支持的二元运算；操作数和声称结果为有界十进制字符串；极性为肯定、否定或纯转述；至少一个来源 handle | 精确计算并保留数值关系是否成立。准确转述错误等式不因其数值错误而自动失败，是否为准确转述由语义检查决定 |
| UnevaluatedExpression | `value=null`；仅允许尚未断言结果或纯转述；已知操作数可保留，未知操作数为 null；至少一个来源 handle | 不求值，不补全，单项计算状态为 NOT_APPLICABLE |
| UnresolvedNumericMapping | 原文和非空原因必须保留；操作、操作数与结果全为 null，不伪造映射 | 必需映射未决，不能取得提交资格 |

操作支持加、减、乘、除，数值沿用至多十二位整数和八位小数的十进制字符串合同。除数为零的系统断言保持未决。speaker 区分 system、learner、other、unresolved；不确定归属不能得到整体通过。带未知变量但已经肯定或否定的关系不属于“尚未求值”：当前工具无法精确表示时，应记录 UnresolvedNumericMapping。

例如，候选报告“学习者写了 `42÷6=?`”，该表达可以保留为未求值项；如果候选接着断言“正确商为 7”，后半句必须作为系统数值断言另行映射。是否允许补充该解释，仍由当前 Observation profile 判断。

## 3. 语义责任与提交条件

类型、操作数映射、来源含义、speaker、stance 和表达项完整性由明确规则与 LLM 判断。代码没有根据问号、等号或特定词语选择类别的路径。综合审查必须独立检查整个 exact candidate 的 `arithmetic_mapping`，不能把提取者的 COMPLETE 或计算器的 PASS 当作映射证据。

完整数值断言被错误标成未求值，或者被隐藏在空 expressions 中，结构检查可能成立。因此即使没有需要计算的数值项，映射判据仍须通过。映射失败或未决时，组合结果为 UNRESOLVED 并阻止提交；错误提取不能证明候选自身数值错误。映射忠实但系统肯定错误等式时，精确验算给出 FAIL。其他必要含义缺失、职责越界和来源不成立仍独立阻止提交。

提取记录绑定同一 Candidate、Context、Protocol 与规则版本，正式提交时重新核算并比对结果。生成、职责分类、算术提取和综合审查的候选字段合同明确列出 `description`。新协议在注册时检查 schema、判据集合、表达格式及规则绑定，不为错误字段提供别名回退。

## 4. 验证范围与保留问题

本地验证固定使用九组手工表达映射及定向边界检查，覆盖未求值、未知操作数、错误等式的转述与认可、否定、混合补充正确值、未知变量关系、除零和无算术文本。语义 PASS、FAIL、UNRESOLVED 都是明确注入的 fixture。测试检查执行这些判断后的准入行为，不能证明模型会作出正确判断，也不能排除提取与审查同时误判。

本次新增的表示提高了表达能力，同时增加错误类型绕过计算的风险。真实模型对新 schema 的遵守率、未求值与未知关系的分类质量、来源与归属映射质量均待验证；不同调用仍可能发生相关错误。完整作答和不完整作答的必要含义边界、校验维度分开记录、A2 下游准入、E1 评分责任，以及远端执行关闭仍需后续设计。不得用本地通过关闭这些问题或重写历史反证。
