# E02-03 知识成分管理

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

管理员在领域详情查找、新建、修订或移除知识成分。含义和适用条件必填，正例和反例可选。表单接收纯文本，已有公式、图表等内容可展示，并随其他字段的修改原样保存。

修订和移除都追加固定版本。移除后默认列表隐藏，精确版本仍能读取。一次提交将事件、对象版本、派生头、目录修订和收据原子保存。回执按原管理员和请求编号查询，后续版本不会改变原结果。

[领域接口](../../../../../doc/mvp/m1/engineering/contracts/Domain_API.md)维护请求与结果。[数据字典](../../../../../doc/mvp/m1/engineering/database/Business_Domain.md)维护版本存储。

## 2. 集群验证

使用 [现有管理端](http://127.0.0.1:5184/admin/)，目标为 `deermind-m1` K3s。

| 部署项 | 实际版本 |
| :--- | :--- |
| 后端镜像 | `deermind/server:e02-03-r2`，manifest `sha256:9a9affbe49891f6be5388fa2dc86e9c8771f3732486be30a0862fd93df31253e` |
| 前端镜像 | `deermind/client:e02-03-r2`，manifest `sha256:e6f02b94eeb822499311139c9d532d4b021b31cfda9a04147927873d225da17f` |
| Helm 和数据库 | `deermind-app` revision 24，API、Worker、前端就绪；数据库 `0013_kc_versions` |

同一集群的隔离 PostgreSQL 用例通过 6 项，覆盖历史迁移、并发修订 200/409、软删除与旧版、跨领域拒绝、目录变化、回执重放和事务回滚。本地测试 76 项通过，编码规范和生成合同校验通过。

Chromium 在已部署的管理端创建知识成分。服务端成功保存后故意丢弃响应，页面从 R04 查回原版本。随后修订「四分之一」的适用条件，公式正文与首版相同。移除后搜索无该项，留在详情可打开 v1 并查看原公式与适用条件。验收领域为 `E02-03 验收 20261122-kc`，保留「等分和单位分数」供评审。

运行证据位于 `src/m1/.artifacts/e02-03-k3s-20261122/`，含 `check.txt`、`local.txt`、`deploy.txt`、`domain-integration.txt` 和 `browser/`。截图核对了当前版、已移除提示、旧版原文和 MathML。人工自检核对了短事务锁序、版本表权限、原请求作用域和前端保留原文的分支。

## 3. 复验

在 `src/m1` 使用现有 K3s 环境。数据库组沿用[显式目标参数](E01-04-database.md#3-验证与自检)，测试使用随机测试库；管理端使用合成领域、知识成分和账号。

```bash
bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh domain
node tests/browser/domain/knowledge-components.cjs
```

浏览器脚本读取 `M1_TEST_DOMAIN_ORIGIN`、`M1_TEST_RICH_DOMAIN_NAME`、`M1_TEST_DOMAIN_LOGIN`、`M1_TEST_DOMAIN_PASSWORD` 和 `M1_TEST_DOMAIN_BROWSER_EVIDENCE`。密码由测试进程通过环境取得。

知识成分与 Solution 的真实引用写入随 E02-05 接入。本步验证精确旧版保留、归属和移除后仍可读取。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 记录知识成分管理交付、同一 K3s 部署与复验结果 |
