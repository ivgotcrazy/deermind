# E02-05 领域方法与先导关系

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

在领域详情维护方法的思路、依据、适用条件、关键过程和直接知识成分。任务可关联多种方法及已有先导任务。先导需要理由，可适用于全部或指定方法。

每条关系固定到对象版本。程序在领域写锁内校验同领域、版本存在、是否已移除、重复和先导环。版本事实与引用索引同事务保存，移除对象后原关联仍能按历史版本查询。任务详情可按方法查看知识成分来源和适用先导。

[D05 查询合同](../../../../../doc/mvp/m1/engineering/contracts/Domain_API.md#d05)记录按方法过滤。KC 直接检验路径确认归 E02-06。

## 2. 集群验证

使用原 `deermind-m1` K3s 和[管理端入口](http://127.0.0.1:5184/admin/)。

| 部署项 | 实际版本 |
| :--- | :--- |
| 后端镜像 | `deermind/server:e02-05-r1`，manifest `sha256:76acda8eb3086aff1e113267a6804a3fbdd76c4e7c9c65686af6953b9cb4d06c` |
| 前端镜像 | `deermind/client:e02-05-r1`，manifest `sha256:68548708ec11ca16c15f524156cfa7b82c496e64bf8804aeefc1fea9b460f290` |
| Helm 和数据库 | `deermind-app` revision 27，API、Worker 和前端就绪，迁移 `0014_domain_references` |

集群 PostgreSQL 通过 8 项测试，覆盖同一 Task 多法、一个方法多 KC、同一 KC 的不同版本、分方法先导、跨领域拒绝、跨版本先导环，以及旧版和已移除目标的历史关系。包含领域、知识成分和任务回归。本地测试 76 项、源码和生成合同检查通过。

Chromium 在「E02-05 验收 20261122-review」领域创建两种方法，为「增加四分之一」关联方法和先导。全部方法视图显示各 KC 的来源及先导适用范围。切到「直接乘新比例」，只显示该方法的 KC，另一方法的指定先导随筛选消失。

管理端新增关联从当前目录选取版本，已有引用保留原版。D02 可明确提交仍可采用的旧版。自检复核了同领域锁内检查、版本与索引同事务、旧收据重放及每个方法的知识来源。

证据位于 `src/m1/.artifacts/e02-05-k3s-20261122/`。部署、数据库和代码检查见 `deploy.txt`、`domain-integration.txt`、`local.txt` 和 `check.txt`。浏览器断言与截图在 `browser/`。

## 3. 复验

在 `src/m1` 使用原 K3s 环境。数据库组沿用[显式集群参数](E01-04-database.md#3-验证与自检)并在随机库运行。浏览器用现有管理端和合成领域。

```bash
bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh domain
node tests/browser/domain/relationships.cjs
```

浏览器环境变量见[领域维护复验](E02-03-kc-management.md#3-复验)。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记领域关系交付、迁移和集群验证 |
