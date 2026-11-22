# E01-16 Temporal 载荷外置与恢复

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **交付状态**：已自检并提交评审，见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 范围与限额

`PayloadCodec` 按完整 Protobuf `Payload` 大小计量，包含 `data` 与 `metadata`。单个载荷超过 128 KiB 时外置。一次 `decode` 还原字节累计最多 64 MiB，`encode` 在写文件前按相同预算检查。编码后单批的 Protobuf `Payloads` 大小最多 1 MiB，计入内联载荷、外置引用和封装开销。

载荷保存在现有共享文件区。文件登记复用 `runtime.file_objects` 的 `sdk_payload` 类别与 `FileReceived`。历史中的引用包含格式版本、文件标识、大小和 SHA-256。读取时核验登记与内容后还原原载荷。小载荷及早期内联历史沿 SDK 原格式读取。

Worker 和 API 容器的 `deermind-probe run` 通过 `bootstrap/temporal.py` 装配同一个转换器。技术故障由公共执行链处理，材料分批仍由调用方负责。[基础设施设计 §2.6](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#26-temporal载荷外置)

## 2. 复核与证据

| 场景 | 验收条件 |
| :--- | :--- |
| 预算边界 | 128 KiB、64 MiB、1 MiB 两侧及边界值均受检。多个小载荷累加超限时明确拒绝 |
| 往返与重启 | 在真实 Temporal 发送合成图文、工具返回和模型结果。Worker 重启后按原字节和哈希还原，保留元数据，复用已持久化的 Activity 结果 |
| 文件故障 | 写失败产生明确技术错误，历史中没有该文件的无效引用。缺失或损坏可定位到技术故障，业务结果未冒报成功 |
| 并发内存 | 记录接近上限时的客户端与 Worker 峰值内存、各自配置限额和进程退出状态 |

在 `src/m1` 执行 `bash scripts/check.sh` 和 `bash scripts/test.sh local`。真实 Temporal 验收从隔离测试目标执行 `bash scripts/test.sh payload`。所需镜像、数据库、Temporal 与文件卷参数见[质量检查入口](../../../quality/README.md#e01-16-temporal-载荷外置验证)。

本轮候选镜像为 `deermind/server:e01-16-review`，manifest 为 `sha256:16b67cfa5648db2f72645bfdf38bd3d2acf2ae68e870f24d7eeb09c600cc2fbd`。证据目录为 `src/m1/.artifacts/e01-16-20261122/`，测试使用临时 Pod、随机 PostgreSQL 库、隔离队列及共享卷上的测试目录。现行应用部署见[部署基线](E01-15-ai.md#3-验证)。

工程检查 `check.txt` 通过，本地 `local.txt` 共 65 项通过，其中 7 项为 Codec 单元测试。`package-source.txt` 逐字节核对镜像安装包中的 128 个 Python 源码及迁移文件。

首轮测试 Pod 的部分用例在测试 Worker 进入就绪前触发 20 秒夹具启动时限，输出保存在 `pod-readiness-first.txt`。复跑的夹具启动时限为 60 秒，5 次实际就绪耗时 10.61 至 22.94 秒。测试命令和临时 Pod 的总时限分别为 300 秒和 390 秒。

候选镜像下的原子事实保存、事件读取及文件附件回归分别通过 13、8、14 项，见 `target-facts.txt`、`target-reads.txt` 和 `target-files.txt`。

真实 Temporal 的 Pydantic AI 用例执行模型、工具、模型三个 Activity，验证旧内联历史与外置载荷往返。该流程外置 6 个载荷，Workflow 启动请求为 452 字节，历史记录的最大载荷批次为 1,948 字节，最大事件为 2,411 字节。并发用例同时处理 4 个 63 MiB 的 Activity 结果，另行验证 63 MiB 启动输入，实际启动请求为 458 字节。客户端与 Worker 的峰值 RSS 分别为 432.3 MiB 和 1,167.0 MiB，低于对应应用配置上限 512 MiB 与 1,536 MiB。这些读数来自同一隔离 Pod 内的两个测试进程。

近上限用例触发 5 次约 5.3 至 7.2 秒的 Workflow Task 时长警告，测试场景完成。模型与图文内容均由合成数据替代，整套备份恢复另见基础设施§6.2—6.3。

`target-payload.txt` 记录 4 项真实 Temporal 测试全部通过（180.504 秒）。重启用例在服务端持久化 Activity 后替换 Worker 进程，恢复后返回原始字节，Activity 执行记录只有一次。文件用例强制写失败时查不到已创建的 Workflow，已有 Workflow 缺文件或文件损坏时明确报错，恢复文件后可重新读取。人工自检核对了完整字节预算、引用发布顺序、文件登记及哈希校验、共享客户端装配和故障断言。文档版本与新增链接通过检查。

## 3. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记已确认的载荷限制、接线范围及自检结果 |
