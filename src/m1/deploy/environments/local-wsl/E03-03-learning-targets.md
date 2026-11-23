# E03-03 学习目标

2026-11-23 在 `deermind-m1` K3s 部署 `e03-03-r1`。Helm 修订 49，数据库迁移 `0026_learning_targets`。

- 目标固定 Claim、章节、方法、评价方面和已校验的方面条件。每种方法保留实际采用它的章节，目标不单独保存概率。
- 当前合同用文字保存 Task 和目标的范围。旧请求中的独立取值字段会被拒绝。见[实施计划 Q14](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#3-待确认清单)。
- [浏览器用例](../../../tests/browser/evaluation/learning-targets.cjs)验证已有教材上一章两种方法、分别／任选、文字范围、错来源、非法取值、请求防重和旧修订读取。证据位于 `.artifacts/e03-03-k3s-20261123/browser/`。
- 两章分别用不同方法的规则由 [范围用例](../../../server/tests/test_learning_target_scope.py)核对。两章临时教材及应用 API 的组合场景沿 [集群回归](../../../tests/migrations/test_domain.py)复验。

## Task 正文与目标范围复验

同一 K3s 的 `deermind-app` 升级至 `e03-task-text-r1`，Helm 修订 55。干净业务库 `deermind_task_text` 从头迁移至 `0028_goal_results`，原试用库 `deermind` 保存在同一 PostgreSQL 实例。

复验证据放在 `.artifacts/e03-task-text-k3s-20261123/`。

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| Task 页面 | 参数入口已移除，文字条件可保存和回读，编辑冲突及新合同下的版本读取通过 | `browser/run.txt`、`browser/task-history.png` |
| 集群数据库 | 12 项通过，含两章目标、文字范围、目标派生和拒绝已移除的 Task 参数字段 | `domain-regression-passed.txt` |
| 本地与合同 | 83 项本地测试通过，源码、类型、Helm 和 OpenAPI 生成检查通过 | `local-tests.txt`、`check.txt` |

实时出题和实际作答证据覆盖分别在实施计划 E04-08 和 E05-07 验证。
