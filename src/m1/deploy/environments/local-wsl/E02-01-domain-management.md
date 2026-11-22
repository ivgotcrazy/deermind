# E02-01 领域管理

> **版本**：v0.2<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

管理员在正式管理端创建、按名称查找和选择领域。创建只填写名称，保存后打开首版详情。

| 环节 | 行为 |
| :--- | :--- |
| 查询 | D01 列出有效领域，D04 校验领域及对象归属后读取首版事实正文 |
| 保存 | D02 同事务追加 `DomainDefinitionSaved`，生成领域身份、首版投影及收据 |
| 恢复 | 结果不确定时，按原账号和请求编号查询 R04。查到即打开原领域。未查到时，可以原样重试 |
| 迁移 | `0012_domain_roots` 在 `domain` schema 增加领域身份、对象版本和请求收据 |

规则见[领域 API](../../../../../doc/mvp/m1/engineering/contracts/Domain_API.md)和[领域数据字典](../../../../../doc/mvp/m1/engineering/database/Business_Domain.md)。浏览器类型由 FastAPI 的 OpenAPI 生成。

## 2. 集群部署

部署目标为 WSL 的 `deermind-m1` context 和 namespace。沿用 [BuildKit 构建与本机镜像导入](E01-03-application.md#2-安装检查与构建)，镜像以[应用配置](application.values.yaml)为准。先运行数据库迁移 Job `deermind-migrate-domain-0012-r1`，确认 `0012_domain_roots` 后升级应用 release `deermind-app`。应用使用现有 PostgreSQL、文件卷、Temporal 和 NATS。

| 部署项 | 实际结果 |
| :--- | :--- |
| 后端镜像 | `deermind/server:e02-01-r1`，manifest `sha256:b6d80b71bb5c38be95267b68a1d26600907dcb92843b5de4fab6311d16be80e0` |
| 前端镜像 | `deermind/client:e02-01-r1`，manifest `sha256:89c1934c66ca44e7ee7792682a4d069cba2287da461b3e9e2cc0f21f0ee59ef1` |
| 数据库 | `0011_ai_calls` → `0012_domain_roots`，原 PostgreSQL 和文件 PVC 继续使用 |
| Helm | `deermind-app` revision 22，API、Worker 和客户端各一份就绪 |

管理端入口为 [127.0.0.1:5184/admin](http://127.0.0.1:5184/admin/)。端口转发只监听本机，连接集群中的客户端 Service。原临时预览已关闭。

### 集群验收

| 场景 | 实际结果 |
| :--- | :--- |
| 领域工作台 | Chromium 在集群管理端新建两个合成领域，验证查找、切换、刷新后读取 v1 |
| 请求恢复 | 写入前断线用同一请求重试，提交后丢失响应通过 R04 恢复原结果。两个领域各有一个首版事实、投影收据和业务收据 |
| 权限隔离 | 学生写入返回 403，跨领域详情和跨账号收据都返回 404 |
| 事实附件 | 大正文按部署配置保存到 PVC。详情完整读取，数据库登记与事件引用的哈希一致 |
| 基础能力 | 已部署浏览器 WebSocket 握手通过，集群应用 5 项通过（含 Worker、Temporal 和共享卷探测），事件交接的 9 项 PostgreSQL／NATS 回归通过 |

两个合成领域和评审账号保留供用户核对。集群证据位于 `src/m1/.artifacts/e02-01-k3s-20261122/`，包括 `deploy.txt`、`oci-sha256.txt`、`browser/`、`fact-check.txt` 和 `foundation-*.txt`。

基础回归首次并行运行时，错误 Temporal 地址的启动拒绝探测在外层 30 秒超时。交接测试结束后，使用相同镜像及判据串行重跑，应用 5 项均通过。两次日志为 `foundation-application.txt` 和 `foundation-application-rerun.txt`。

## 3. 开发自检

使用指定 K3s PostgreSQL 中的随机测试库、合成账号和独立文件目录。正式 Vue 构建通过本机 HTTPS Nginx 访问隔离 API。

| 场景 | 核对项 |
| :--- | :--- |
| 创建和查找 | Chromium 新建两个领域，分别读取 v1。按名称筛选、切换和刷新后均可读取 |
| 写入前断开 | R04 返回 `not_found`，刷新保留请求。显式重试复用相同编号和正文 |
| 提交后响应丢失 | R04 找回原结果，浏览器打开领域详情，未再次发送写请求 |
| 权限、范围与回滚 | 学生无法保存，跨领域详情及跨账号收据返回 404。故障发生在追加事件之后，业务写入全部回滚，原请求随后可重试 |
| 数据迁移和附件 | 从 `0011_ai_calls` 升级后既有事件和账号仍可读取。超过 32 KiB 的事实正文外置，详情可完整取回 |

真实 PostgreSQL 通过 5 项领域测试及 1 项既有 Product 回执回归。本地回归 75 项、集群目标检查 5 项及编程规范检查均通过。

证据位于 `src/m1/.artifacts/e02-01-20261122/`。数据库记录为 `postgres.txt`，浏览器记录及截图位于 `browser/`，构建及检查记录为 `browser-build.txt`、`check.txt`、`local.txt` 和 `target.txt`。

## 4. 复验

在 `src/m1` 执行。数据库验证需要显式设置 `M1_DB_HOST`、`M1_DB_PORT` 和 `M1_TEST_{ADMIN,MIGRATION,APP}_PASSWORD`。用例自行建立及清理测试库。

```bash
bash scripts/check.sh
bash scripts/test.sh local
export PYTHONPATH=server/src:tests/migrations
server/.venv/bin/python -m unittest -v test_domain test_receipts
```

使用[应用交付§3](E01-03-application.md#3-本机部署与访问)中的端口转发访问已部署应用。浏览器复验使用合成账号，设置 `M1_TEST_DOMAIN_LOGIN/PASSWORD` 和 `M1_TEST_DOMAIN_STUDENT_LOGIN/PASSWORD`，证据不记录密码。每轮使用独立标签，可以在已有领域的集群中重跑。

```bash
M1_TEST_DOMAIN_ORIGIN=http://127.0.0.1:5184 \
  M1_TEST_DOMAIN_CLUSTER_LABEL='E02-01 验收 本轮编号' \
  node tests/browser/domain/walkthrough.cjs
```

在已安装 Playwright 的环境运行浏览器用例。可选 `M1_TEST_BROWSER_EXECUTABLE` 指定浏览器、`M1_TEST_DOMAIN_BROWSER_EVIDENCE` 指定证据目录。

## 5. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记领域首版、查询、原请求恢复和复验入口 |
| v0.2 | 2026-11-22 | 补齐 K3s 部署与集群复验，附件使用部署配置的存储类型 |
