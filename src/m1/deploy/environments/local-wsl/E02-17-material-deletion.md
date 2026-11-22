# E02-17 删除未完成教材导入

## 1. 交付范围

确认删除时复核导入修订，生成删除事实并取消当前教材助手任务。Domain 从删除事件撤下同一来源的待办。已入库对象、历史事实和原件保留，迟到的入库检查必须重新确认来源有效。

若存在助手工作，删除与工作收尾都先锁住运行记录，再锁教材。取得教材锁后核对确认修订和当前工作；先完成的工作变化会使原删除确认过期。

## 2. 集群验证

2026-11-22 在本机 K3s 使用 `e02-17-r1` 验证浏览器删除、过期范围拒绝、重复请求返回原收据、教材列表移除和原件回读。证据位于 `.artifacts/e02-17-k3s-20261122/browser/`，入口为 `tests/browser/materials/deletion.cjs`。

隔离的真实 PostgreSQL 验证教材锁被占用时删除等待提交。删除后章节写入拒绝，曾关联的领域 Task 仍可回读。使用实际删除事件调用 Domain 处理器，只有该教材的未入库待办被撤下，已处理项、其他教材待办均保留。重复处理无变化。见 `domain-integration-r4-invalidation.txt`。

`e02-17-r4`（Helm revision 40）使用短暂停止 Worker 的方式固定已受理请求，浏览器确认删除后原助手收据返回 `cancelled`，原件仍可回读。验证后恢复 Worker。证据见 `browser/material-cancelled-receipt.json` 和 `browser/deletion-cancel-r4.txt`。
