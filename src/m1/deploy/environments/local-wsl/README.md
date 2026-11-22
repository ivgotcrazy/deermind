# 本机测试环境与增量交付记录

本目录对应独立的`DeerMind-M1` WSL／单节点K3s测试环境，仅用于低并发功能验证，不代表100人试用容量。部署配置保存在本目录的values文件中，交付记录按增量编号组织。

## 增量目录

| 编号 | 交付内容 | 记录 |
| :--- | :--- | :--- |
| E01-01 | 本机测试集群、访问与环境复核 | [E01-01-local-cluster.md](E01-01-local-cluster.md) |
| E01-02 | PostgreSQL、Temporal、NATS及共享卷 | [E01-02-components.md](E01-02-components.md) |
| E01-03 | API、Worker、客户端与应用构建 | [E01-03-application.md](E01-03-application.md) |
| E01-04 | 模块schema、数据库迁移和权限 | [E01-04-database.md](E01-04-database.md) |
| E01-05 | 事件、生产者投影与请求收据原子保存 | [E01-05-facts.md](E01-05-facts.md) |
| E01-06 | 文件、事实附件完整性与引用提交 | [E01-06-files.md](E01-06-files.md) |
| E01-07 | 事实授权查询、分页与附件正文读取 | [E01-07-reads.md](E01-07-reads.md) |
| E01-08 | 业务投影生成、五表按范围重建及维护结果 | [账号投影重建交付](E01-08-rebuild.md) |
| E01-09 | 登录、Cookie会话与身份隔离 | [E01-09-auth.md](E01-09-auth.md) |
| E01-10 | 合成账号维护、首次确认与密码恢复 | [E01-10-account-usage.md](E01-10-account-usage.md) |
| E01-11 | 公共收据查询、统一错误和类型化客户端 | [E01-11-request-receipts.md](E01-11-request-receipts.md) |
| E01-12 | 可靠事件发布、订阅承接与失败重送 | [E01-12-event-delivery.md](E01-12-event-delivery.md) |
| E01-13 | 后台工作、步骤保存与执行恢复 | [E01-13-execution.md](E01-13-execution.md) |
| E01-14 | 结果登记、等待及通知接续 | [E01-14-waits.md](E01-14-waits.md) |
| E01-15 | 受控模型调用、授权工具及结构化候选 | [E01-15-ai.md](E01-15-ai.md) |
| E01-15-B | 独立抽象、实现解耦与依赖检查整改 | [E01-15-boundaries.md](E01-15-boundaries.md) |
| E01-16 | Temporal 载荷外置、重启与故障复核 | [E01-16-payload-codec.md](E01-16-payload-codec.md) |
| E01-17 | 浏览器实时连接、通知和补读 | [交付与验证](E01-17-realtime.md) |
| E01-18 | 固定输入到结果的端到端验证与恢复 | [交付与复验](E01-18-foundation-chain.md) |
| E02-01 | 管理员新建、查找和选择领域 | [领域管理交付与复验](E02-01-domain-management.md) |
| E02-02 | 文字、公式、表格和图形的统一结构及展示 | [内容结构交付与复验](E02-02-rich-content.md) |
| E02-03 | 知识成分保存、版本、移除和原收据 | [知识成分交付与复验](E02-03-kc-management.md) |
| E02-04 | 任务定义、条件、草稿及版本 | [任务管理交付与复验](E02-04-task-management.md) |

## 查阅规则

- 文件命名统一为`EXX-XX-主题.md`，编号与[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#1-范围与顺序)一致。
- 每份记录保留对应增量的交付范围、复核命令、测试证据和限制。历史命令反映当时版本；当前部署镜像由[应用配置](application.values.yaml)维护。
- 进度及评审状态只在实施计划维护，本目录不另建状态表。
- 编程检查工具与规范回归见[quality说明](../../../quality/README.md)。
