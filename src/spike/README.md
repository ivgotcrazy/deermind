# DeerMind Architecture Spike — deterministic foundation

实现范围为综合 Spike 设计的 Step 0–Step 2：不可变精确引用与记录、分离的事实 / 规范 / 派生 / 执行 / 审计存储、可控时钟、snapshot / branch、pull current resolution、按 scope / purpose 激活版本、显式兼容性 fixture，以及 Case Runner / JSONL 证据输出。只依赖 Python 3.13 标准库。

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

`seed_committed_fixture` 仅安装脚本预先定义的 owner 记录，不是 FormalCommit。Authority / Data Authority / Security 目前是显式的 ALLOW / DENY / UNKNOWN fixture，默认 UNKNOWN；兼容性也来自 exact version set 的 fixture。它们用于隔离依赖与版本机制，不能据此宣称已实现权限后端、语义判断或提交重验。没有开放语义的关键词规则，也没有模型调用。

CurrentResolver 每次对内存副本作同步检查：选取当前用途的待检 revision 后，沿 exact CURRENT refs 递归校验；失败不回退旧 revision，不改写依赖。新 revision 存在本身不使旧 exact ref 失效；仅在依赖明确声明 `require_head` 或 `require_active` 时检查最新提交 / 激活条件。PINNED 只检查历史引用存在，不将其当作未来 effect 的 CURRENT 保证。有效期、correction、用途不匹配、循环、不同 CURRENT 分支的依据冲突及未知资格均产生 non-resolution。

Snapshot 的深拷贝是第一版的一致读取实现，已计入运行清单的复杂度记录；没有生产规模性能结论。FailureInjection 提供文档约定的命名挂起点，供后续 commit / action 路径接入，目前测试其单次触发与分支隔离。事实 correction 通过新记录使旧 exact basis 不可用于 current，历史仍保留；正式 correction authority 与更完整的 lifecycle 变更仍待后续步骤。

**基础检查 PASS 不等于 Architecture Assumption SUPPORTED。** 当前没有 FormalCommit、真实权限后端、LLM、完整 replay 或会话 / Action 流程；运行结果保持 AA `UNVALIDATED`、Gate E / F `OPEN`。下一步按设计接入 Step 3 的 Authority / Data Authority，再实现 Step 4 的 Context / Candidate / Commit。真实模型的供应商、模型与预算在接入前另行固定。
