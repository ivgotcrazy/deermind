# Observation 条件规则与分项校验：本地实现和验证 v1

日期：2026-10-05。限定结论：本地记录与准入机制 PASS；条件规则的真实语义质量尚未验证。

## 1. 交付与行为

[Observation Validation Profile v0.1](../../../doc/system-design/DeerMind_Observation_Validation_Profile_v0.1.md)已明确方法、局部算术和最终答案分别依据原材料适用。A1 已有完整与不完整作答规则，本次将其与未求值表达合同结合，形成独立 [v13 实验协议](../protocols/observation-validation-v13.json)。全部七项判据仍必需，不按关键词分流，不在失败后降级 profile。没有中间步骤不能免除对已提交最终答案的判断；来源确有缺失或局部歧义时，候选可以忠实保留它们，不能替学习者补出作答。

分项记录区分内容检查、必要含义检查和执行状态。已经完成的 FAIL 或 UNRESOLVED 保留为有效检查结果；断连、超时和字段违约记录 FAILED，结论为 null，后续未执行项保留 NOT_RUN。部分执行的聚合状态为 INCOMPLETE。各项结果保留 exact 来源，复核失败另留失败引用，不覆盖先前有效审查。

新增 ValidationAssessment 只是原检查记录的审计汇总。正式提交仍重验原语义、职责、算术和所有资格，不能靠修改汇总取得 standing。正常路径不增加模型调用。ValidationAttemptFailed 已与同轮次关闭接口衔接，无需先制造一次 Policy 决策。

## 2. 固定离线结果

一次 [validation-dimensions-v1](../runs/validation-dimensions-v1/summary.json) 完成 262 项测试，失败、错误、跳过均为零，其中新增 12 项定向测试。范围包括未执行、部分执行、内容通过但必要含义缺失、职责失败、完成但未决、三个阶段的执行故障、错误字段、来源复核失败、缓存读取、伪造汇总与失败轮次关闭。

运行阻断网络，外部模型调用和网络连接尝试均为零。36 份 adapter 记录来自明确的本地脚本 transport，不能计为真实认知结果。[测试输出](../runs/validation-dimensions-v1/unit-tests.txt)和 12 份 JSONL 已保留；162 个冻结输入、14 个运行文件指纹、13 份历史快照和 13 份实际汇总记录经核对。先前 312 条证据通过原文件或归档源码复核，三个变更前源码已[保存](source-baseline-validation-dimensions-20261005/index.json)。具体数据见[限定评估](validation-dimensions-assessment-20261005.json)。

本地最大输入为 15597 字符，距离当前 16000 字符上限较近。这里只验证了这些 fixture；较长候选、来源和复核材料可能超限，真实验证前仍需明确输入预算和失败处理，不能据此声称新 profile 已具备产品可用性。

## 3. 仍未解决的问题

九个[必要含义设计样例](../fixtures/validation-required-meaning-v1.json)仅冻结了开发者预期，没有真实模型执行，不算通过。条件判断错误、完整作答被误当作不完整、实际答案因步骤缺失而被跳过，以及提取和审查共同误判，仍需真实语义证据。当前汇总不会消除这些风险。

v13 需要显式选择，没有替换历史 A1/X5 入口。原 A2 DENIED、A1/E1/E2/F2 未决及 X1/X2/X5 未决均保持；完整验收仍为 9/17，Gate E/F OPEN。此次完成了修订草案中关闭、表达类型、校验分项记录的本地机制，但不等于整份合同已验收。下一步转向 A2 错误内容下游准入及 E1 评分责任的具体设计后果，不自动追加模型批次。远端停止、晚到效果对账、崩溃恢复和经认证用户中断仍未实现。
