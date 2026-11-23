# E03-03 学习目标

2026-11-23 在 `deermind-m1` K3s 部署 `e03-03-r1`。Helm 修订 49，数据库迁移 `0026_learning_targets`。

- 目标固定 Claim、章节、方法、评价方面和已校验的方面条件。每种方法保留实际采用它的章节，目标不单独保存概率。
- 当前 Task 参数为文字时，可保存文字范围。API 拒绝为此类参数填写结构化取值。
- [浏览器用例](../../../tests/browser/evaluation/learning-targets.cjs)验证已有教材上一章两种方法、分别／任选、文字范围、错来源、非法取值、请求防重和旧修订读取。证据位于 `.artifacts/e03-03-k3s-20261123/browser/`。
- 两章分别用不同方法的规则由 [范围用例](../../../server/tests/test_learning_target_scope.py)核对。两章临时教材及应用 API 的组合场景沿 [集群回归](../../../tests/migrations/test_domain.py)复验。
