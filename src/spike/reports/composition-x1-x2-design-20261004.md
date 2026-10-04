# X1/X2 在途决策组合固定验证方案

日期：2026-10-04。依据 Spike §13.1–13.2。三分支各五次，最多 50 次模型调用，无重试或替补；所有分支从共享初始快照开始。X1/X2 是已有假设的组合场景，不新增 Architecture Assumption，也不改变 A2、E1、E2、F2 的既有结论。

X1-correction：在 T1 Context 冻结、Policy 请求已经构造、adapter 记录调用开始之后，由独立 Interaction owner 的受信输入撤回旧 Observation，并以脚本含义通过共享正式提交形成 r2。真实返回和内容校验仍绑定原 Context；原 Policy 因 Corrected 拒绝，没有 T1 ActionIntent。排队的新请求不能在 T1 收束前开始；T1 收束后，T2 重新形成引用 r2 的 Context，并运行真实 Policy / 校验和正式提交及其可选行动。最多四次调用。

X2-supersede：在同一注入位置由受信治理 fixture 激活 Policy protocol v2 供后续边界使用。v1 与 v2 使用同一冻结 E1 提示词、返回 schema 与内容规则，声明兼容；区别是精确版本及激活证据，不引入新的教学语义假设。T1 保持 v1，真实 Policy 须提交并在选择 Execute 时实际 mock 展示。当前轮次收束后，T2 通过 active resolution 形成绑定 v2 的新 Context，再真实生成、校验、提交并处理可选行动。最多四次调用。新版本启用本身不能导致旧决策 stale。

X2-revoke：同样在 T1 生成时启用 v2，T1 仍按 v1 正式提交并形成 Intent；随后显式撤销 v1 的当前 learning 用途，展示前重验须得到 NotOccurred / VersionIneligible，不能产生展示确认或 ActionOccurrence。最多两次调用。撤销是追加的、带 exact target / scope / purpose / source 的受信 Evolution fixture 事实，原 canonical record、Context、Policy 与 Intent 不改写；不把 revocation 当作 grant 撤销或版本 supersession。生产治理授权和跨进程撤销事务不在本轮范围。

真实 Policy、语义内容校验经同一 BoundaryRuntime；串行及结果收束复用 SerialSession，提交和 ActionRuntime 不另造旁路。Observation 及 correction 含义为明确脚本 fixture，mock 展示不能提供生产 UI 保证；校验 PASS 不被当作学习效果或 E1 有用性评分。T2 输入固定为请求再给局部提示，不强制任何 Policy 返回。X2 若真实模型未选择 Execute，则保留 effect 覆盖缺口，不能伪造行动或补跑。X1 的 stale 检查不要求模型选择 Execute。

支持条件：X1 五条完整 correction / stale / 串行重新决策路径；X2 两个变体各五条完整版本及对应 effect 路径；每条原始返回、精确协议绑定、正式提交、Intent / effect 和事件顺序可独立核对。语义 FAIL / UNRESOLVED、协议 / 网络失败以及模型未选中所需路径记未完成，不能与安全 invariant 失败混为一谈。可信越权、silent rebase 或错误 stale 则记录组合失败及设计后果。

首调用前冻结实现、fixture、E1 协议指纹和本方案；每分支再次核对。任何 invariant 失败立即停止后续分支；HTTP 400/401/403/404/422 或连续三次协议 / 运行失败停止，其他预定分支继续。单次输出至多 2048 tokens、超时 60 秒。完成后离线审计并收口，不为获得 PASS 自动追加批次。

注入是单进程可控交错，发生在 transport 发往 provider 之前，不能描述为远端模型计算期间的真实线程竞争。先到的新输入只排队，不触发旧 Context 变更；独立 owner 的 correction 与治理变更可在该轮次活动期间发生。历史精确版本保持绑定，同时当前资格在提交及 effect 边界重验；这里的“固定版本”不等于跳过资格检查的 PINNED dependency。
