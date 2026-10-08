# 可选固定活动入口实现（2026-10-07）

已实现独立的 [WorkingScope / RestrictedEntry](../foundation/working_entry.py)。配置显式登记 identity/revision、subject/scope/purpose、精确 Protocol refs、固定 ActivityConstraints ref 和允许的 ActionSemantic refs；安装一次后不可再次注册。它复用现有 BoundaryRuntime、SerialSession、ActionRuntime / ActivityRuntime，不新增语义 reviewer、不使用关键词分类。

## 1. 执行约束

安装时要求协议已注册、Policy 声明 policy-admission-v1，固定活动 envelope 的允许清单属于所登记动作，动作是带精确 payload 的 mock-display，不能带 activity_transition。入口强制使用现有或新建的 SerialSession，交互 Context 必须绑定当前开放轮次、声明协议与固定 envelope。未绑定、已结束、替换协调器或改用其他协议的交互不能继续。

Boundary 的生成、校验及最终提交检查复用该限制；Policy Execute 的 selected action 必须在工作清单内。ActionIntent 准入核实真实注册 candidate/commit 来源与工作 Context，权限执行路径再检查 exact action ref、executor 和 scope。因此限制不仅影响未来生成：启用前已正式创建但尚未执行的 Control Intent 也会被拒绝，记为 NotOccurred，不写活动转换事实。允许的局部提示仍可按原提交、Intent、展示和结果处理路径执行。

独立 Evidence / LearnerBelief owner 保留原有合同，不被交互协议清单禁用。更正使已有交互依据失效时仍走原 currentness barrier。该机制不取消已在途的远端 effect，不改写已有终端结果或实际历史。

## 2. 使用和协议边界

调用方在受信配置阶段构造冻结的 WorkingScope 并调用 RestrictedEntry(boundary, profile)。所有 refs 指向已登记对象，登记执行记录保存配置内容；配置 revision 是当前本地工作入口版本，不冒充新增 canonical 学习语义。随后按原 SerialSession 接收、排队、启动和绑定 Context，再用原 Boundary / Action API。

当前提供的是可选库入口及可执行机制测试，尚未新增产品服务入口或真实模型 campaign。测试显式使用现有 fixture 协议，不宣称已选择或验证最终工作协议组合。非安装入口的旧 World 与默认 Protocol 保留；旧完整 X5 实验仍可以执行其原合法转换。安装该限制不能自动证明文档中的 A1/A2/E1 最低质量已满足，允许的动作及帮助含义仍须受信登记和规则约束下的 LLM 判断。

## 3. 有限验证结果

新增 11 项测试覆盖：合法局部提示的完整正式路径；启用前候选的禁止动作拒绝；错误协议和 envelope；协调器被移除；缺少轮次绑定；重复安装；把 Control 登记为局部动作；从旧完整脚本路径取得的未执行 Control Intent 被拒绝；自动建立 coordinator；排队和失败收束；独立 Evaluation owner 提交。

最终完整本地回归为 322 项，无失败、错误或跳过，耗时约 18 秒，网络显式禁止且没有连接尝试，真实模型调用为零。[逐项测试源](../tests/test_working_entry.py)与[正式局部评估](restricted-working-entry-assessment-20261007.json)保留来源摘要。第一次定向执行中两项 fixture 缺少新提交 Policy 的读取 grants，已补齐；随后用真实 mock Control Intent 替代参数注入，并在最终回归中加入独立 owner 检查。没有更改生产语义判据来让测试通过。

旧 boundary.py 和 actions.py 的修改前逐字节来源保存在 source-baseline-working-entry-20261007，历史批次和旧证据没有覆盖。新增挂钩仅在显式安装入口时生效。

结论：固定活动限制在声明的本地脚本/mock 范围内通过，原 X5 的真实完整链路仍未通过；不能据此批准整个阶段化安排、生产恢复或 Gate。A2 DENIED、9/17 和 Gate E/F OPEN 不变。下一步明确独立工作配置所选 Observation/Policy 版本及输入，冻结有限的受影响语义补证计划；当前不自动调用模型。
