# E02-06 KC 直接检验路径

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

管理员在任务详情核对某个方法直接引用的 KC，填写可观察表现和不足示例。系统验证三者的领域、精确版本、直接关系及必要正文。管理员判断学生能否在该任务中直接表现这项知识。

「解释 d=v×t」的可观察表现包括说明每单位时间经过相同路程、路程如何累加，以及公式成立的匀速条件。「只把 3 和 4 代入得 12」只能作为不足示例。依据不足会保存原问题和检查记录。确认成功时，依据和三版本一并留痕。

同一组合重复确认返回首次确认。定义升版后，已确认事实仍归原组合。确认只影响内容准备。接口见 [D05 与 D10](../../../../../doc/mvp/m1/engineering/contracts/Domain_API.md#d10)。

## 2. 集群验证

使用原 `deermind-m1` K3s 和[管理端入口](http://127.0.0.1:5184/admin/)。

| 部署项 | 实际版本 |
| :--- | :--- |
| 后端镜像 | `deermind/server:e02-06-r2`，manifest `sha256:3a697367ecfda20bf28088d3a47b0c9407a789fd59f29fdebe2337c01b32b304` |
| 前端镜像 | `deermind/client:e02-06-r2`，manifest `sha256:eea4f2f301a8809e7d473e4b3670f1be52eabd7cce047ab1708cc5e01cc97561` |
| Helm 和数据库 | `deermind-app` revision 29，API、Worker 和前端就绪，迁移 `0015_kc_test_paths` |

集群 PostgreSQL 通过 9 项测试，覆盖未关联方法、仅引用、缺少必要正文、记录不足、确认去重、原收据和版本历史。确认事实包含依据和路径记录。依据不足事实只保存依据。领域、知识成分、任务及关系回归通过。

Chromium 在「E02-06 验收 20261122-paths」验证正反例。代入数值只记录不足。解释任务保存确认后，故意丢弃响应，页面从原请求查回确认。随后修订任务，v2 显示待确认，v1 仍能展开原依据。

本地测试 76 项通过。最终源码、生成合同和部署配置检查通过。自检复核了三版本锁内重查、事件和投影原子保存、收据重放、切换任务时的加载状态。证据位于 `src/m1/.artifacts/e02-06-k3s-20261122/`。部署、数据库和源码校验见 `deploy.txt`、`domain-integration.txt`、`local.txt` 和 `check.txt`。浏览器日志和两例截图在 `browser/`。

## 3. 复验

在 `src/m1` 使用原 K3s。数据库组沿用[显式集群参数](E01-04-database.md#3-验证与自检)，运行在隔离库。浏览器使用合成领域及现有管理端入口。环境变量见[领域维护复验](E02-03-kc-management.md#3-复验)。

```bash
bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh domain
node tests/browser/domain/kc-test-paths.cjs
```

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记 KC 直接检验路径确认、迁移及集群验证 |
