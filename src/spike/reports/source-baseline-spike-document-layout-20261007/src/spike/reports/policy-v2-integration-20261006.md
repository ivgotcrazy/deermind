# E1 v2 运行绑定与本地集成

日期：2026-10-06。局部运行机制已实现并验证，语义质量尚未验证。

[上一阶段合同](../../../doc/system-design/DeerMind_Policy_Semantic_Utility_Contract_v0.1.md)中的 v2 规则已显式接入 PolicyWorld 和 run_policy_case 的 `rule_revision='v2'` 路径。协议、语义规则及 utility 规则全部绑定 v2，并共同进入兼容性依据和 VersionContext。直接从默认 v1 入口加载 v2 或声明不一致引用会拒绝。v1 默认入口与旧协议文件保留，行动目录仍使用原有 e1-v1 精确引用；规则版本升级不暗中改变行动内容或授权。

测试评分开始前核对其精确引用、候选 Context 的协议与语义绑定，以及已注册协议内容；替换为 v1 评分规则会在调用模型前拒绝。该检查不把评分变成生产校验，也不改变评分不能授权行动的职责。[修改前源文件](source-baseline-policy-v2-20261006/index.json)保留，旧 manifest 和结论未改写。v2 JSON 和合同中的未集成标记是上一阶段冻结快照；当前局部实现状态由本报告和进度清单记录。

[固定本地运行](../runs/policy-v2-integration-v1/summary.json)全套 285 项测试通过，包括六项新增集成测试，无失败、错误或跳过。生成、语义校验及 utility 请求中的实际 system 内容逐字对照 v2 定义，评分 rubric 对照新版内容，设计预期标签不进入请求。Execute 完成提交和模拟展示；NoIntervention 与 Defer 不生成效果。注入语义 FAIL/UNRESOLVED 均阻止提交，utility PASS 不能覆盖；注入 utility FAIL 不撤销已经提交并发生的效果。旧 v1 绑定有正对照。

运行入口为 [run_policy_v2_integration.py](../run_policy_v2_integration.py)，新增测试为 [test_policy_v2.py](../tests/test_policy_v2.py)。入口使用脚本传输并阻断网络，不读取 API 配置；真实模型调用和网络尝试均为零。开发阶段曾从仓库根目录启动单项 unittest，因 Python 模块路径未包含 src/spike 而导入失败；改用正确工作目录后六项通过。其后固定全套运行一次通过，未补跑覆盖失败结果。

[证据审计](policy-v2-integration-audit-20261006.json)核对 171 个冻结输入、13 份快照、18 条脚本传输记录和原清单 373 个哈希。该组请求序列化后的最大长度为 7839 字符，仅为本地测量，不是 token 预算或真实服务可用性结论。

脚本回复只能证明版本接入和机械边界，不能证明 S1–S5 判断正确。十四个作者标注片段尚未转成完整、独立审阅的语义验证用例，四个旧争议未重判。E1 的字段用途投影也未因版本接入自动启用；其合同声明与正式来源链需单独接入。A2 DENIED、E1 INCONCLUSIVE、9/17 与 Gate E/F OPEN 保持。

下一步将完整候选、精确 Context 和预期判据整理成有限验证包，确认独立审阅要求和输入预算，再确定是否提出真实模型验证。没有启动或预约新批次，也不继续重复当前已通过的机械回归。
