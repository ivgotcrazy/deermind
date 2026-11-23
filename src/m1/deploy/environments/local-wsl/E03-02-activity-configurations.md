# E03-02 活动配置

2026-11-23 在 `deermind-m1` K3s 验证。`deermind-app` 修订 48 使用 `e03-02-r1`，数据库迁移到 `0025_activity_configs`。从管理端「交互活动」进入四类蓝图。

- 首次保存蓝图时，蓝图、空绑定、解析配置和收据一同提交。活动级规则空缺在保存后展示。
- 节点仅显示本地绑定。程序合并活动级与当前节点的有效定义。
- 旧配置可按固定 ID 读取。删掉预置结束节点或提交过期修订会被拒绝。

[浏览器用例](../../../tests/browser/interaction/activity-configurations.cjs)的截图及固定配置引用位于 `.artifacts/e03-02-k3s-20261123/browser/`。[后端用例](../../../server/tests/test_activity_blueprints.py)覆盖路径、作用域和继承规则。
