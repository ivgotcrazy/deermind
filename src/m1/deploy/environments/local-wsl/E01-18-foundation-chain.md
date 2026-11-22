# E01-18 首条基础链验证

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 验证范围

用合成账号、固定输入和两步测试任务贯通已有模块。测试运行在 WSL 和指定的本机 K3s 环境，使用随机测试库、独立消息主题与执行队列、隔离文件目录。浏览器经 Nginx 走 HTTPS 和 WSS。测试动作、故障控制和结果视图在隔离应用登记。

1. API 先可靠保存输入事实、收据和待投递记录，再确认受理。
2. JetStream 投递。订阅者保存消费收据和执行安排，提交后才 Ack。Temporal 按固定身份派发 Worker。
3. 保存第一个步骤及外置载荷；第二步取回内容、核对哈希并保存最终结果和事实。
4. 提交后发出 Core NATS 刷新提示。浏览器通过 R04 按原请求补读，再从所有者查询入口读取正式结果。

## 2. 验收对照

| 场景 | 实测结果 |
| :--- | :--- |
| 完成后原样重提 | 收到 Core NATS 触发的刷新帧。重复请求的独立回执返回原收据和执行编号；数据库复查只产生一份工作和一次业务结果 |
| 第一步提交后停止隔离 Worker | 进程 `1227577` → `1227653`，工作、执行尝试、Temporal Run 和外置引用保持一致。历史只记录一次第一步完成，第二步读回内容的 SHA-256 一致 |
| 服务端受理后丢回执并断线 | Chromium 重连后按原编号通过 R04 和所有者查询取回结果。发出写请求 1 次，重连后写入 0 次 |
| 受理前资源不足 | 收到 `resource_busy`。拒绝前后均为 3 份收据、3 条输入事实、3 份工作、6 条交接；原请求无收据，已有结果可查。手动重提后只新增一份工作和一次结果 |

最终逐一对照 4 个 Chromium 请求编号与数据库、Temporal 记录。4 份正向结果各有一条输入事实、一份发布及消费记录、一份执行、一个尝试及一条结果事实和投影。末次总量为 4 份收据、4 条输入事实、4 份工作、8 条交接。

集群目标检查 5 项、本地回归 75 项、投影重建和结果等待 32 项均通过。资源不足用确定性故障验证拒绝和重提语义，试用容量另按实施计划 V01 验收。

证据在 `src/m1/.artifacts/e01-18-20261122/`。`browser/foundation-chain.json` 保存 Chromium 的请求和授权读取结果。`chain-api.txt` 保存请求、事实、收据、执行、步骤、外置引用和最终计数。`correlation.txt` 保存跨端关联核对结论。`check.txt`、`local.txt`、`target.txt` 和 `rebuild-and-wait.txt` 保存检查与回归结果。

## 3. 复验入口

在 `src/m1` 执行。为指定测试目标提供 `M1_DB_HOST`、`M1_DB_PORT`、`M1_TEST_{ADMIN,MIGRATION,APP}_PASSWORD`、`M1_TEST_NATS_ADDRESS`、`M1_TEST_NATS_PASSWORD`、`M1_TEST_TEMPORAL_ADDRESS`、`M1_TEST_TEMPORAL_NAMESPACE` 和 `M1_TEST_FILES_ROOT`。文件路径须指向可写的测试卷，测试在其下新建临时目录。

```bash
bash scripts/check.sh
bash scripts/test.sh local
export PYTHONPATH=server/src:tests/migrations
server/.venv/bin/python -m unittest -v test_projection_rebuild test_waits
server/.venv/bin/python -u tests/migrations/foundation_chain_harness.py
```

隔离 API 默认监听 `127.0.0.1:5197`，使用 `https://127.0.0.1:5196` 作为允许来源。用应用 Chart 的 Nginx 配置向该 API 代理 `/api/m1/` 和 `/ws`，以本机测试证书提供 HTTPS。用 Vite 将 `tests/browser/foundation-chain` 构建到 Nginx 的 `student/`，构建参数为 `--base /student/`。在已安装 Playwright 的环境运行 `node tests/browser/foundation-chain/walkthrough.cjs`。可用 `M1_TEST_BROWSER_EXECUTABLE` 指定浏览器、用 `M1_TEST_E0118_BROWSER_EVIDENCE` 指定 JSON 证据路径。

浏览器用例结束且 API 已输出四条完成记录后，向隔离 API 发送 SIGTERM 或按 Ctrl+C。退出时输出最终计数，再清理本次测试资源。

## 4. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记首条基础链的实现、验收结果和复验入口 |
