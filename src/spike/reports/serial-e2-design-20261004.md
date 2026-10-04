# E2 单会话串行与外部关键依据变化：运行前方案

日期：2026-10-04。依据 Architecture Spike Design §11.2。冻结 `fixtures/serial-e2-v1.json` 和执行代码后运行，不变更 E1 的 Policy 提示词与内容校验规则，也不追加 E1 有用性评分。

一个共享初始世界包含已正式提交的 Observation、Evidence、LearnerBelief:r1 和已冻结的 T1 Context，当前请求为“请帮我检查哪一步有问题，不要直接给答案”。Observation / Evaluation 是明确声明的脚本 fixture；Policy 生成与内容校验是真实 deepseek-flash 调用，effect 使用既有 mock。Belief 的上下文使用要求明确声明 CURRENT + require_head；新 head 使这个使用不再成立，但不删除、纠正或改写 r1 历史。这不主张所有新 revision 都自动使旧语义版本失效。

每个分支、每次重复都从相同初始快照独立克隆。A 分支在 T1 的真实 Policy 请求已构造、模型调用执行已开始而尚未返回时接收 C/T2 普通输入。收到事实与 InputQueued 立即保存；T2 内容不得进入已经冻结的 T1 Context，T2 不做 Observation / Policy。分别在 reasoning、Intent 等待 effect、effect 已返回但结果未处理、结果处理完成但轮次尚未收束四个位置尝试启动同会话下一轮，都应拒绝。T1 处理实际结果并 TurnSettled 后，T2 才开始形成自己的正式脚本 Observation、包含实际披露的 Context、真实 Policy 与内容校验，并完成其 outcome / 可选 effect。

B 分支由独立 Evaluation owner 在 C-external 来源驱动下，于真实 Policy 生成期间正式提交共享 Belief:r2。该操作不依赖 C 的轮次锁，也不消费 C/T2 尚未处理的输入。旧 Candidate 及原始模型调用仍绑定 r1，提交应返回 CandidateStale / RequiredHeadChanged，不形成 ActionIntent，不静默改绑 r2；T1 收束后才允许新的 DecisionCycle。权限撤销具有单独的 authorization failure，本分支不将其冒充 stale。

C 是额外 effect 边界检查：先让真实 Policy 的合法 Execute 完成提交并形成 Intent，再由同一独立 owner 更新 Belief:r2。执行器应在展示前返回 NotOccurred / EffectPrecondition:RequiredHeadChanged，不产生展示确认或 ActionOccurrence，随后处理结果并收束轮次。它复用现有 ActionRuntime，不把已经形成的 Intent 当作已发生的帮助。

A/B/C 各五次，共十五个分支执行。A 最多四次调用（T1 与 T2 各生成、校验一次），B/C 各两次，总上限 40 次；单次输出上限 2048、超时 60 秒，temperature 0、thinking disabled、无重试。使用唯一目录 `runs/serial-e2-v1`，不自动续跑或替补。A/C 必须由真实 Policy 自然选择 Execute 才能覆盖所需 effect 边界；若未选择，记覆盖未完成，不用脚本强行补选。B 不要求特定教学 outcome，但需要得到真实候选及有效校验后观察 stale 拒绝。

支持 AA-E02 的本轮范围要求十五次全部满足预声明检查，保留输入、轮次、Context、模型执行、Candidate、Commit、Intent、effect result 和收束事件的关联。出现 invariant 检查失败立即停止并保留缺口；HTTP 400/401/403/404/422 或连续三次协议/运行失败也停止。未完成或执行失败不算成功，假设结论另经证据审计形成；架构 falsifier 仍按原文档归因，不把单次实现缺陷或模型失败自动等同于架构否定。

这是一致快照、单进程可控交错实验；transport hook 只注入预声明的排队或独立 owner 提交，不替换真实 provider 响应。每个会话只有一个活动轮次，不引入 learner-wide lock；不同会话可以各自启动，独立 owner 可以在 Policy 返回前提交。会话队列为内存投影，实际生命周期事件保存在已有执行历史，不提供生产线程 / 分布式事务 / 崩溃恢复结论。用户主动中断、异常恢复交互、A1/A2、E1 评分争议和 F/X 完整组合不在本轮闭合范围。Gate E/F 保持 OPEN。
