# Policy 结构化裁决：局部实现与验证

日期：2026-10-06。局部机制实现与固定本地验证完成，真实语义识别质量未验证。

[裁决修订设计](../../../doc/system-design/DeerMind_Policy_Review_Disposition_Revision_v0.1.md)已通过 opt-in [E1 v3 协议](../protocols/policy-e1-v3.json)接入现有一次语义校验。S1–S5 各一项，check、finding 与整体状态必须一致；矛盾声明对应 FAIL，未决对应 UNRESOLVED，FAIL 优先于 UNRESOLVED。一次有效全 PASS 才能继续原准入路径。没有新增默认评审调用，也没有自然语言关键词处理。

实现位于 [policy_disposition.py](../foundation/policy_disposition.py)和 [boundary.py](../foundation/boundary.py)。结果绑定原 candidate digest、Context 身份、精确规则和运行时材料可用性执行记录；声明必须覆盖全部候选字段，每个必需义务必须引用已声明 finding，孤立 gap 或重复行会被拒绝。候选及来源引文核对字段、精确引用和 Unicode code point 切片；索引用十进制字符串表达，适配既有严格 schema 子集。存在引文并不证明它语义上支持结论。

运行时依据冻结 Context 生成 PolicyReviewMaterialAvailability，并绑定原 ContextManifest。受信主机可以在评审开始前显式隐去一组已经参与形成候选的来源；原形成上下文和依赖保留，评审消息去除这些内容，可用性记录标为 WITHHELD_FOR_REVIEW。候选无权把 AVAILABLE 来源改为缺失，评审开始后不能再配置视图。当前也记录 excluded 输入的 ACCESS_DENIED 或 UNKNOWN，不主动越权重新读取缺失材料。

整个设计中的可用性角色尚未全部落地：NOT_PROVIDED_TO_FORMATION、RETRIEVAL_FAILED 的独立元数据与生产恢复需后续接入。必需输入获取/权限失败继续由原组装和失败收束处理，不能据此称所有材料缺口状态已实现。

v3 规则、语义格式及 utility 引用显式绑定，v1/v2 入口保留。无效结构化结果不会注册为有效 SemanticValidation；错误调用仍保留执行审计。有效的 FAIL 和 UNRESOLVED 分别记录、均拒绝正式提交。每个候选的新格式只允许一次实际语义尝试，已取得结果可以复用；无效输出不能通过隐式重试恢复。提交时重新核对详情、精确证据与运行时材料记录，不能只信任顶层 PASS。测试 utility 的权限和作用没有改变。

[固定运行](../runs/policy-disposition-v1/summary.json)全套 299 项测试通过，无失败、错误或跳过，包含十四项新增裁决用例。它们覆盖实际生成至单次语义调用和正式提交、声明冲突仍 PASS 拒绝、总体状态不符、有效 FAIL/UNRESOLVED 拒绝提交、隐去视图与形成历史保持、伪造缺口拒绝、材料缺失不覆盖已声明冲突、来源不在可见字段中、精确 candidate 绑定、Unicode 引文、义务覆盖/重复，以及提交复核。

测试还刻意注入“没有定位替代”的错误含义和内部一致的全 PASS findings，此候选仍可提交。这个用例保留明确局限：机械机制不能重新解释含义或发现模型没有报告的冲突。新增用例只检查被模型显式声明的证据与裁决处理，不能宣称修复了此前真实误放。

[范围评估](policy-disposition-assessment-20261006.json)核对 181 个冻结输入、16 个运行产物、14 份快照和 17 条脚本模型记录，原清单 440 项通过历史字节/现行文件核对。两个改动源文件的[原字节归档](source-baseline-policy-disposition-20261006/index.json)保留。运行入口为 [run_policy_disposition.py](../run_policy_disposition.py)，用例见 [test_policy_disposition.py](../tests/test_policy_disposition.py)。真实模型调用与网络尝试均为零。

开发中曾将仓库相对路径用于错误工作目录，写入失败，后改用明确目录完成文件；单项用例最初两个正例因候选身份不在授权范围而拒绝，修正测试身份后十四项通过。固定全套批次在这些修改完成后运行一次通过，没有替换失败的真实模型结果。

本轮交付结束于局部机制支持：方案整体仍未完成，v3 未默认启用，E1 字段投影声明与生产持久化恢复仍为独立缺口。A2 DENIED、E1 INCONCLUSIVE、9/17 及 Gate E/F OPEN 保持。下一步应审阅 v3 的实际输入/输出预算与已知语义反例，明确是否需要一次固定范围的真实识别验证；不重开已关闭的 v2 批次，也不以脚本 PASS 冲销其反例。
