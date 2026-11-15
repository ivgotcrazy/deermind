# E01-06 文件与事实附件

[环境目录](README.md) · [实施计划 E01](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 交付范围

用户确认：单条事实DTO超过32KiB整体外置，等于32KiB仍内联；完整事件最多1MiB。统一按UTF-8字节计算，信封、payload和外置引用都计入事件大小。沿用8GiB业务PG和8GiB文件测试卷；不代表100人试用容量。

| 内容 | 实现位置 |
| :--- | :--- |
| 字节存储端口 | `foundation/system/files/ports.py` |
| local/PVC、不可覆盖发布、长度/hash检查 | `infrastructure/files/local.py` |
| 文件登记及FileReceived完整DTO | `infrastructure/files/records.py` |
| 事务外附件准备、固定产物复用 | `foundation/system/events/attachments.py` |
| 事件大小、附件身份和完整正文核验 | `foundation/system/events/store.py` |
| 文件登记表与最小权限 | `migrations/versions/0003_file_objects.py` |

未新增依赖。`M1_FILES_BACKEND`默认为pvc，Chart明确设置pvc；本地测试可指定local。PVC必须是真实挂载，目录被替换后旧适配器拒绝写入，不自动创建同名目录。

## 2. 保存闭环

1. 业务提供完整事实DTO及受信生产者范围，程序先校验事件登记、记录矩阵和所有者约束。
2. 大DTO按固定JSON编码写入同卷临时文件，计算SHA-256、刷新文件，再以硬链接发布不可覆盖的正式文件，刷新目录。文件名由程序生成；拒绝路径穿越和符号链接。
3. 回读长度、hash及正文一致后，短事务登记文件及FileReceived；产物键由事件ID和record_id组成。同键同文复用，同键异文拒绝，不跨身份按hash共享。
4. 业务短事务重新检查附件登记、完整DTO及1MiB事件上限，共同保存业务事件、完整正文投影和请求收据。文件I/O不占业务事务，异步入口把阻塞文件操作放到线程中执行。
5. 文件写入或校验失败，不提交业务事实；业务事务失败只保留已完成的文件准备事实，业务事件、投影和收据一起回滚。重试可复用原附件。

事件存`{storage:file,file_id,sha256,media_type}`，投影存展开后的原DTO。准备结果不是免校验凭证：提交前仍核对事件身份、原文和附件登记，调用方篡改不能造成事件与投影异文。文件身份不授予读取权限，本轮没有向浏览器开放裸文件访问。

正式文件只读，不提供覆盖或删除操作；SQL应用账号对file_objects只有SELECT/INSERT。故障可能留下未登记文件或已登记但未被业务引用的文件，本轮不自动清理。提交后若磁盘丢失或文件损坏，后续读取明确失败，不以空正文或其他文件替代。

## 3. 复核与部署

在WSL的`src/m1`执行。按[E01-03](E01-03-application.md#2-安装检查与构建)启动BuildKit，构建后停止：

```bash
set -e
bash scripts/build-app.sh deermind/server:e01-06-r2 deermind/client:e01-03-r2 \
  .artifacts/e01-06-20261116/images-r2

export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-06-r2
export M1_FILES_CLAIM=deermind-files

bash scripts/check-target.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE"
k3s ctr images import .artifacts/e01-06-20261116/images-r2/server.tar
bash scripts/check.sh
bash scripts/test.sh files
bash scripts/test.sh facts
bash scripts/test.sh database

bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-db-e0106-r2 \
  --chart deploy/helm/database-migration \
  --values deploy/environments/local-wsl/database-migration.values.yaml
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-app \
  --chart deploy/helm/application --values deploy/environments/local-wsl/application.values.yaml
M1_APPLICATION_RELEASE=deermind-app bash scripts/test.sh application
```

本机已升级到`0003_file_objects`，共7张表（含迁移表），应用release第8版。API、Worker和客户端均就绪；部署库的文件、事件、账号均为0，测试库已清理，BuildKit已停止。

真实PG用例只写随机测试库；文件故障用临时目录，另用随机文件名验证实际PVC往返。结束时清理本次测试资源，不写业务账号，不删除现有文件。镜像里的wheel包含源码和迁移，不以挂载源码代替包验证。

## 4. 验证与人工检查

证据目录：`.artifacts/e01-06-20261116/`。实施计划仍须用户评审后才标完成。

| 验证 | 结果 | 证据 |
| :--- | :--- | :--- |
| 静态检查、严格类型、模块边界与离线Chart | 通过 | `check-final.txt` |
| 本地完整测试组 | 7项规范样例＋4项部署入口＋17项后端单元测试通过 | `local-final.txt` |
| 后端单元测试 | 17项通过，含5项文件边界用例 | `check-final.txt` |
| 文件与事实附件，真实PG/PVC | 14项通过：32KiB两侧、1MiB限制、并发复用、损坏/缺失、准备后篡改、回滚及权限 | `files-final.txt` |
| E01-05事实原子保存回归 | 13项通过 | `facts-final.txt` |
| 迁移与数据库权限回归 | 8项通过 | `database-final.txt` |
| 部署后应用与共享卷 | 5项通过 | `application-final.txt`、`deploy-final.txt` |
| 文件表与部署清理 | 11列、索引和应用权限与分册一致；部署库无测试数据 | `cluster-final.txt` |
| 构建包与源码 | 27份Python源码/迁移与wheel逐字节一致 | `package-source.txt` |
| 文档文件链接 | 843处检查无缺失，修订版本及引用人工核对 | `documentation-check.txt` |


自查修正了准备后正文可能被改动的问题，补入内联正文及文件所属事件的提交前校验，并用反例回归；新文件必须回读成功后才记录FileReceived。

人工review重点：字节限额而非字符数；文件先完成再引用；同键异文拒绝；内联与外置DTO一致；文件失败、业务失败分别留痕；目录逃逸/错误挂载拒绝；旧迁移未重写；新表字段及权限与数据库分册一致。

## 5. 边界

- 本轮接线是内部存储能力，没有增加上传页面、HTTP文件入口或登录授权。
- file_uploads、上传租约、PDF/图像格式解析随教材上传实现；事件授权查询归E01-07，Temporal PayloadCodec归E01-16。
- local-path的8GiB申请量不是磁盘硬配额；当前功能测试不证明容量、备份恢复或100人性能。底层空间不足必须失败，不靠删除历史腾空间。
- 不实现对象存储后端和物理清理；已确认的存储隔离端口保留。
