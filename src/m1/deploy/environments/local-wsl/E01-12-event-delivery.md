# E01-12 可靠事件交接

[环境目录](README.md) · [实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

> 2026-11-17源码位置已按[独立抽象整改](E01-15-boundaries.md)迁移。下文保留本增量当时的路径、命令和验证事实；当前归属见整改清单。

## 1. 交付范围

事件、生产者投影和发布安排一起提交。Worker将事件引用交给NATS，订阅方保存接收收据及后续工作安排后再确认收到；重复投递不会重复安排业务。

- 发布采用稳定投递身份；确认丢失沿原身份补发，租约过期可以接手。
- 订阅只接受程序登记的类型和范围。通知与数据库中的正式事实逐项核对，不信任外部正文或函数名。
- 业务接收失败全部回滚；明确拒绝先保存收据和原因，再终止投递。
- 失败通知持久接收，同时核对PG收据；不能把队列确认当成业务成功。
- 受控重送需指定原交接、操作人及批准依据。只补尚未接住的订阅，保留原事件和历史收据。
- DeliveryStateChanged保存关键控制快照；不会递归发布自身，也不参与业务投影重建。

本轮不增加页面或AI Operation。正式业务订阅随所属模块实现，当前生产登记为空；测试使用明确的隔离适配器。Temporal执行及业务失败恢复属于E01-13。

## 2. 代码和存储

| 位置（相对src/m1） | 职责 |
| :--- | :--- |
| `foundation/system/delivery/`（服务端包内） | 固定通知合同、原子安排、短租约、承接去重、失败留痕及重送 |
| `infrastructure/nats/`（服务端包内） | SDK适配、资源核对、Worker发布/订阅/采集/核对循环 |
| `bootstrap/messaging.py` | 程序登记订阅；不登记未实现的业务 |
| `bootstrap/events.py`、`events/store.py` | 生产者同事务保存发布安排；留痕使用独立不发布的登记 |
| `entrypoints/maintenance/messaging.py` | 维护凭据初始化及明确批准的重送 |
| `scripts/prepare-messaging-secret.py` | 显式集群中补齐两类凭据，已有密码不变、不打印秘密 |
| `tests/migrations/test_event_delivery.py` | 真实PG及NATS交接验证 |
| `server/tests/test_delivery_contracts.py` | 通知、订阅登记、凭据及日志边界 |

迁移`0007_event_delivery`新增四张既定控制表：handoffs、handoff_attempts、subscription_receipts、delivery_failures。表字段、索引和权限只由[Runtime字典§9—12](../../../../../doc/mvp/m1/engineering/database/Business_Runtime.md#9-runtimehandoffs)维护。当前实际20张表含alembic_version，规划表总数不变。

## 3. 已确认配置

使用nats-py 2.16.0，锁定在`server/uv.lock`；现有NATS Server 2.15.3及2GiB卷不变。

| 项目 | 本机配置 |
| :--- | :--- |
| 命名 | `DM_LOCAL_WSL_EVENTS`、`DM_LOCAL_WSL_DELIVERY_FAILURES`；subject为`dm.local-wsl.event.<event_type>` |
| 容量 | 业务768MiB、失败通知32MiB，单条通知64KiB |
| 保留 | InterestPolicy、DiscardNew、MaxAge=0；不删旧腾空间 |
| 承接 | 每次1条，MaxAckPending=1；总限20秒，AckWait 30秒，MaxDeliver 5 |
| 发布 | 单次5秒、最多5次、总预算90秒；租约30秒，间隔2/5/10/20秒 |
| 核对 | 每30秒；只保存缺失/异常依据，不自动重做业务 |
| 凭据 | maintenance负责初始化；application只可发布、查询、拉取和确认本环境消息，无建删资源权限 |

详细配置和处理口径见[基础设施§4.2—4.3](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#42-消息交接参数)。这些是功能测试配置，不代表100人容量或恢复SLA。

## 4. 部署与复核

所有命令在`src/m1`执行，明确选择目标；不修改全局默认集群。密码只从Secret或受控环境注入，不写入命令参数。

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_MESSAGING_SECRET=deermind-nats

server/.venv/bin/python scripts/prepare-messaging-secret.py
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" --context "$M1_CONTEXT" \
  --namespace "$M1_NAMESPACE" --release deermind-nats \
  --chart ../../.tmp/e01-02/charts/nats-2.15.2.tgz \
  --values deploy/environments/local-wsl/nats.values.yaml
```

随后使用构建镜像中的`deermind-messaging initialize`，显式配置M1_NATS_ADDRESS、M1_NATS_DEPLOYMENT、M1_NATS_USER及M1_NATS_PASSWORD；初始化使用维护凭据。先建失败通知流及采集器，再建业务流和已登记消费者；既有配置不一致立即拒绝，不自动删建。

迁移通过`database-migration` Chart单独运行，成功后部署`application` Chart。API无NATS凭据，Worker只注入应用凭据。应用后端为`deermind/server:e01-12-r4`；客户端沿用`e01-11-r1`。

复核测试：

```bash
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-12-r4
export M1_TEST_NATS_ADDRESS=nats://deermind-nats:4222
bash scripts/test.sh delivery
```

测试创建随机数据库及随机消息流；测试流各预留1MiB，其余交接配置沿正式值，避免重复占用正式容量。结束后只清理本次资源。运行证据位于`.artifacts/e01-12-20261116/`，不提交凭据或测试正文。

获准重送使用维护数据库凭据，并记录真实批准依据：

```text
deermind-messaging redeliver --handoff <原交接UUID> --operator <操作人> --authorization <批准记录>
```

此命令不等待AI、不删除原队列消息、不重做已接住的业务；重送安排保存成功不等于业务完成。

## 5. 验证与自检

2026-11-16，基线`1b88b21`上的本轮修改完成以下验证。自动测试共98项，全部通过；正式业务订阅未接入，不据此宣称学习业务完成。

| 验证组 | 数量 | 证据文件（相对本轮.artifacts目录） |
| :--- | :--- | :--- |
| 规范正反样例、部署目标校验、服务端单测 | 7＋4＋38 | `local-tests-final.txt` |
| 真实PG/NATS交接 | 9 | `delivery-package-tests.txt` |
| 迁移、原子事实、授权读取、请求收据回归 | 8＋13＋12＋1 | `database-package-tests.txt`、`facts-package-tests.txt`、`reads-package-tests.txt`、`receipts-package-tests.txt` |
| 已构建应用、API代理、共享卷及Worker接线 | 5 | `application-tests.txt` |
| NATS鉴权及重启持久化 | 1 | `nats-restart-test.txt` |

`check-final.txt`记录格式、lint、类型、Helm及OpenAPI漂移检查通过；`quality-copy-match.txt`核对178个源码/配置文件与检查副本一致。`messaging-permissions.txt`验证应用凭据不能创建或删除消息资源。`doc-check.txt`核对13份变更文档的版本记录及891个文件链接。

已部署应用release修订16，API/Worker使用`e01-12-r4`，客户端沿用`e01-11-r1`。服务端镜像manifest为`sha256:ebdd3e1283f6cc7a4e66a29f28c4d6ec3694ca77ed2d4dacf3f5a528e6a1021a`；Pod运行image ID为`sha256:b8ad538ce2601f8e4b03dc0822e293b57b54dcb5446d5f0a4aea1735d160e510`，两者分别标识manifest和镜像配置。`audit-final.txt`确认迁移为0007、三端Pod就绪、无测试库/测试消息流残留，正式账号及事件仍为空。

| 场景 | 核对内容 |
| :--- | :--- |
| 原子提交 | 回滚后事件、投影、交接均不存在；成功后原事实与安排留痕共用commit_id |
| 并发重复承接 | 同订阅、同事件只创建一份工作；安排失败时收据也回滚 |
| 发布确认丢失 | 原投递身份补发，队列与PG均不产生第二份业务 |
| 承接后未Ack | 重投查回原收据，不再次调用业务适配器 |
| 订阅缺失 | 不发布到无人接收的流，保留安排与故障依据 |
| 拒绝和重投耗尽 | 拒绝先落库再Term；真实NATS的5次上限产生持久失败通知 |
| 获准重送 | 普通应用拒绝；同批准号复用新安排，正式事件身份不变 |
| 迟加入订阅 | 不扩大原接收范围，记录ignored且不调用业务 |
| 无失败通知的丢失 | 按PG收据及传输记录发现缺失；重复核对不重复记故障 |

人工review已核对通知字段、事务边界、租约过期、重复承接、权限、日志及H类留痕。修正了核对计时起点（从实际发布成功算起）、旧租约晚到写入，以及测试流容量与清理边界，并通过相应测试。事件承接提交后才Ack；网络调用在事务外；H类留痕不重建业务或递归发布。用户评审状态只在实施计划维护。

## 6. 限制

- 正式账号、教材、聊天和学习事件均未接入本轮测试，当前只验证交接底座。
- 测试验证单节点功能，不验证100人容量、高可用、节点丢失或完整备份恢复。
- 未定位的失败通知保留等待核对；不会凭缺少通知推断业务失败。
- 后续工作执行由E01-13接线；本轮没有用MQ代替Temporal执行队列。
