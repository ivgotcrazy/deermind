# E01-15-B 独立抽象与跨层边界整改

> **版本**：v0.1<br>
> **日期**：2026-11-17<br>
> **进度**：[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md)是唯一状态来源

[环境目录](README.md) · [源码组织](../../../../../doc/mvp/m1/engineering/Source_Organization.md#4-模块依赖与装配)

## 1. 范围与迁移

基线`b911e24`。本轮整改源码依赖与职责，不改变数据库迁移、事件正文、运行身份或业务规则。E01-16未开始。

| 原位置 | 当前归属 | 调用与验证 |
| :--- | :--- | :--- |
| foundation/system/events/contracts.py、reading.py | abstractions/events.py、event_reading.py | 事件生产、授权读取及投影重建 |
| foundation/system/files/ports.py | abstractions/files.py | local/PVC实现及装配 |
| infrastructure/files/records.py | abstractions/file_records.py；foundation/system/files/records.py | DTO与文件登记/投影分离；附件往返 |
| foundation/system/delivery/contracts.py | 数据进入abstractions/delivery.py，事务订阅与注册器保留 | 通知身份和订阅快照不变 |
| infrastructure/nats/bridge.py | foundation/system/delivery/bridge.py | 传输端口隔离SDK；保存接收收据后确认 |
| infrastructure/temporal/relay.py | foundation/system/executions/relay.py | 独立执行控制端口；原派发与收尾规则 |
| infrastructure/temporal/waits.py中的补查 | foundation/system/waits/reconcile.py | SDK等待与底座补查分离 |
| SDK生命周期、等待Activity | 外壳保留；底座事务服务经bootstrap/runtime.py注入 | 名称、参数及错误分类保留 |
| foundation/ai/contracts.py及跨层请求/工具数据 | abstractions/ai/ | 模型适配只使用CallService、ToolService |
| 数据库版本和维护锁 | infrastructure/database配置，Bootstrap显式注入维护服务 | 维护锁与版本检查保留 |

旧路径不保留转发壳。事件编码与内容哈希统一使用独立纯函数；模块内部注册器和SQL事务回调不进入抽象层。各业务投影仍由原所有者实现。

## 2. 自检与证据

验证证据保存于`src/m1/.artifacts/boundary-refactor-20261117/`。本轮不外发真实模型请求。

使用独立测试库、测试队列和临时Pod，不替换现有API/Worker。候选包为`deermind/server:e01-15-boundaries-r3`；OCI manifest为`sha256:576fbed9770010b6325566a4676bf319db6f718d239955305f2b40a88cd902b2`。

| 检查 | 结果 | 证据文件 |
| :--- | :--- | :--- |
| 工程检查 | Ruff、Pyright、依赖边界、脚本/YAML/Vue/Helm及生成合同检查通过 | `check.txt`、`final-python-check.txt` |
| 本地测试 | 质量8项、部署目标4项、最终后端46项，共58项通过 | `local-tests.txt`、`final-server-tests.txt` |
| 原子事实保存 | 13项通过 | `facts-package-tests.txt` |
| 文件与事实附件 | 14项通过 | `files-package-tests.txt` |
| 授权读取 | 12项通过 | `reads-package-tests.txt` |
| 投影重建 | 19项通过 | `rebuild-package-tests.txt` |
| 消息交接 | 9项通过 | `delivery-package-tests.txt` |
| 执行恢复 | 11项通过 | `execution-package-tests.txt` |
| 等待与通知 | 12项通过 | `waits-package-tests.txt` |
| AI与工具接线 | 5项通过，1项真实模型调用按范围跳过 | `ai-package-tests.txt` |
| 包与源码一致性 | 124个Python文件（含迁移）逐字节一致 | `package-source.json` |
| 合同与文档核对 | 50个迁移数据模型的字段定义、8个Temporal注册标识保持；本次新增引用无失效 | `consistency.json` |

复核入口为`bash scripts/check.sh`、`bash scripts/test.sh local`及`bash scripts/test.sh <分组>`（facts、files、reads、rebuild、delivery、execution、waits、ai分别执行）。集群测试显式指定local-wsl的kubeconfig、context、namespace、测试镜像及原有组件；凭据从既有Secret读取。

前五组在r2验证；最后仅恢复了SDK外壳对无效输入的原有异常处理，r3复验执行、等待、AI和后端测试。r3构建包与最终源码一致。并行构建/检查期间，重建与执行组各触发过一次测试脚本150秒总超时；停止并行重负载后按原上限重跑通过，未放宽业务期限或断言。失败输出保留为`rebuild-timeout.txt`、`execution-timeout.txt`；早期r1旧包与新测试不匹配的输出单独保存在`r1/`，不计作通过证据。

人工走查结论：

- 抽象层只保留接口、数据和确定性格式处理；调用者权限检查、事务、订阅资格、执行收尾仍在底座实现。
- NATS/Temporal/模型适配只通过注入接口协作；没有Foundation与Infrastructure相互导入，也未增加转发壳。
- 文件登记、消息确认顺序、等待截止时间及业务投影归属保留；测试覆盖回滚、重复、失败、恢复和越权。
- 数据库仍为`0011_ai_calls`；数据库结构、依赖锁、生成API和部署配置未改。
- 文档旧路径仅保留在明确标注的历史交付记录或迁移对照中。DECISIONS既有的“消息交接参数草案”历史锚点失效，本轮未改该历史问题。

未覆盖：真实模型效果、升级前在途Workflow历史回放及100人容量。现有运行服务仍为原E01-15部署；本轮交付代码、候选镜像与验证记录，尚未升级该服务。

## 3. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-17 | 登记独立抽象迁移、职责分离及回归验证 |
