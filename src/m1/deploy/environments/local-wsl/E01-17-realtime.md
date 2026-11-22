# E01-17 WebSocket 与断线补读

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **状态**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 实施范围

浏览器通过同源 `/ws` 和 `deermind.v1` 与 API 连接。会话、订阅、命令和发送采用服务端授权。S01–S07 在[基础设施设计](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)维护。

数据所有者在提交后发出 Core NATS 事件 ID。各 API 据正式事件和连接授权提示刷新；查询走现有 HTTP。客户端保留未知受理的原请求身份，重连恢复订阅后补读。发送缓冲按连接限额，健康连接可继续接收。

正式业务由各模块在接线时登记动作、视图和授权。集成验收在隔离应用中复用 Product 的本人使用确认事务和 R04 收据。

## 2. 验证记录

| 层次 | 环境与结果 |
| :--- | :--- |
| API | 本地回归 75 项通过，其中 10 项覆盖 WS 来源、会话、超时、连接及订阅限额、提示合并、慢连接与缓冲边界 |
| 真实接线 | WSL、K3s PostgreSQL 及 Core NATS，4 项通过。两台 API 独立收到提交提示。非读连接因真实 TCP 背压关闭，健康连接继续收取；分片超限拒绝；丢回执及重启后查回原结果，重复提交无额外事实 |
| 客户端 | Node 回归通过，覆盖通知合并、旧身份响应、重连次数上限、HTTP 补查和显式原样重试。学生端及管理端生产构建通过 |
| 浏览器 | Chromium 157 经 Nginx 验证 HTTP＋WS 和 HTTPS＋WSS。WSS 核对 Secure、HttpOnly Cookie。保存后丢弃回执，浏览器重连并按同一编号查回结果，仅发出一次写入。正式管理端的双标签页退出与换账号验证通过 |

从 `src/m1` 复验。用隔离环境提供 `M1_DB_HOST`、`M1_DB_PORT`、`M1_TEST_{ADMIN,MIGRATION,APP}_PASSWORD`、`M1_TEST_NATS_ADDRESS` 和 `M1_TEST_NATS_PASSWORD`。测试为每个用例创建随机业务库和独立提示主题，并清理该库。

```bash
bash scripts/check.sh
bash scripts/test.sh local
node --test clients/tests/unit/realtime.test.mjs
server/.venv/bin/python -m unittest discover -s tests/migrations -p test_realtime_integration.py -v
```

浏览器接线入口在 `tests/migrations/realtime_browser.py`，测试页在 `tests/browser/realtime`。走查通过渲染后的应用 Nginx 配置执行，以 `walkthrough.cjs` 核对请求及收据。

运行证据在 `src/m1/.artifacts/e01-17-20261122`。检查及测试日志见 `check.txt`、`local.txt`、`client.txt` 和 `integration.txt`，浏览器录像及收据见 `browser/tls-reconnect.gif`、`browser/tls.txt`。同源 HTTPS 使用本机测试证书。正式部署沿用既有 HTTPS 入口，业务动作和视图随模块接线。

## 3. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记 E01-17 接线、复验命令及验证证据 |
