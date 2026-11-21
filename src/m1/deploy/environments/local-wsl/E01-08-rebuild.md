# E01-08 受控投影重建

> 本文记录当时的交付。当前维护命令和失败处理见[按范围重建](E01-08-single-run.md)。

[环境目录](README.md) · [实施计划 E01](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

本文保留首批交付时的范围、路径及验证记录。职责补修改为业务拥有生成器并覆盖账号五表，见[E01-08职责补修](E01-08-ownership.md)；旧单表结果不代表五表已重建。

## 1. 交付范围

从原始事件和完整附件恢复初始账号查询数据；维护过程有固定记录，可以中断后继续。本轮只接入已实现的`product.accounts.v1`，不提前实现教材、活动或评价投影。

| 内容 | 实现位置 |
| :--- | :--- |
| 完整事实授权读取 | `foundation/system/events/query.py` |
| 固定范围、隔离副本、检查点与原子替换 | `foundation/system/projections/rebuild.py` |
| 维护记录及结果合同 | `foundation/system/projections/contracts.py` |
| 共用账号转换、程序白名单与实现摘要 | `product/accounts/facts.py`、`bootstrap/projections.py` |
| 维护命令 | `entrypoints/maintenance/rebuild.py`，安装命令`deermind-rebuild` |
| 扫描位置及维护记录表 | `migrations/versions/0004_projection_rebuilds.py` |
| 真实PG故障、恢复与独立进程测试 | `tests/migrations/test_projection_rebuild.py` |

用户确认增加维护记录；字段字典见[运行分册§19—20](../../../../../doc/mvp/m1/engineering/database/Business_Runtime.md#19-runtimeprojection_offsets)。没有新增服务、依赖、页面或AI Operation。

## 2. 处理与失败边界

1. 操作人停止相关写入，使用维护数据库账号并明确确认维护。程序与迁移共用互斥锁；数据库表锁发现仍有写入就拒绝，不静默等到业务超时。
2. prepare固定范围、每范围上界、代次、实现摘要和临时副本。相同请求返回原记录；范围或实现不能在续做时更换。普通应用账号不能读取或修改维护表及副本。
3. resume按范围序号读取完整事实，沿用授权、Schema、附件完整性和大小检查。副本行、维护代次收据与进度一起保存；不跳过失败事实。
4. 中断保留已提交检查点；新进程沿原记录继续。来源上界变了则拒绝，不能将维护期间的新事实混入原工作。
5. 全部核对通过后，同一事务写回正式查询行、合并在线收据、推进在线进度、登记唯一维护结果并删除本次副本。保留原ID、版本、正文、时间和来源；不改请求收据、文件登记或运行控制。
6. 明确失败保留旧查询数据和副本，记录failed及安全的错误类别；修复后另建代次。数据库故障导致结果无法保存时，不声称失败记录已落库。完成/失败后重复resume只返回原结果，不再追加事件。

重建不重新投递历史事件，不调用模型、发送通知或创建业务任务。当前测试覆盖账号转换；多表因果依赖及其他业务投影在对应增量实现时扩充。

## 3. 维护命令

在安装本次后端包、可连接目标业务库的维护环境执行。事先通过受控环境变量提供M1_DB_HOST/PORT/NAME/USER/PASSWORD与M1_FILES_ROOT/BACKEND；用户必须是deermind_migrator，文件路径必须对应原文件区。凭据不写命令行或记录文件。下面变量由操作人按本次维护填写，不能复用别次维护身份。

```bash
: "${REBUILD_ID:?本次维护UUID}"
: "${REBUILD_GENERATION:?未使用的大于1的代次}"
: "${ACCOUNT_ID:?已有源事实的账号UUID}"
: "${OPERATOR_ID:?维护操作人}"
: "${AUTHORIZATION_REF:?本次批准依据}"

deermind-rebuild prepare --rebuild-id "$REBUILD_ID" \
  --generation "$REBUILD_GENERATION" --scope "$ACCOUNT_ID" \
  --operator "$OPERATOR_ID" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed

# 可选：先处理一件事实并保存检查点；不替换正式查询数据。
deermind-rebuild resume --rebuild-id "$REBUILD_ID" --max-events 1 \
  --operator "$OPERATOR_ID" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed

deermind-rebuild resume --rebuild-id "$REBUILD_ID" \
  --operator "$OPERATOR_ID" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed

deermind-rebuild status --rebuild-id "$REBUILD_ID" \
  --operator "$OPERATOR_ID" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed
```

多个账号重复传入--scope。prepare不自动选择“全部”，status不扩大授权。命令输出维护记录，不输出账号正文或凭据；failed及前置拒绝返回非零。没有自动清理失败副本的命令。

## 4. 测试与部署复核

在WSL的`src/m1`执行，构建方式沿[E01-03](E01-03-application.md#2-安装检查与构建)。真实测试只使用随机测试库及临时文件，不清空部署库数据。

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-08-r1
export M1_FILES_CLAIM=deermind-files

bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh rebuild
bash scripts/test.sh reads
bash scripts/test.sh facts
bash scripts/test.sh files
bash scripts/test.sh database

# 目标已核对且应用已暂停后运行迁移；失败保持暂停，不恢复旧包绕过版本检查。
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-db-e0108-r1 \
  --chart deploy/helm/database-migration \
  --values deploy/environments/local-wsl/database-migration.values.yaml
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-app \
  --chart deploy/helm/application --values deploy/environments/local-wsl/application.values.yaml
M1_APPLICATION_RELEASE=deermind-app bash scripts/test.sh application
```

部署后API/Worker使用`deermind/server:e01-08-r1`；客户端仍为`deermind/client:e01-03-r2`。业务库共9张表（含迁移表），账号、事件、文件、维护记录及扫描进度均为0；随机测试库与测试Pod已清理，BuildKit已停止。实测见`cluster-final.txt`。

## 5. 验证与人工review

证据目录：`.artifacts/e01-08-20261116/`。本轮共96项测试通过，静态检查另计；用户评审通过才标记增量完成。

| 验证 | 结果 | 证据 |
| :--- | :--- | :--- |
| 静态、类型、边界、格式及Chart | 通过；最后新增测试及部署配置另行复核通过 | `check-local.txt`、`changed-final.txt` |
| 本地测试 | 7项规范样例＋4项目标入口＋20项后端单元测试通过 | `check-local.txt` |
| 受控重建，真实PG | 13项通过；含独立进程续做、最终提交失败回滚及越权拒绝 | `rebuild-final.txt` |
| 授权读取、原子保存、文件及迁移回归 | 12＋13＋14＋8项通过 | `reads-final.txt`、`facts-final.txt`、`files-final.txt`、`database-final.txt` |
| 部署后应用 | 5项通过；应用release第10版，迁移head为0004_projection_rebuilds | `deploy-final.txt` |
| 构建包与源码 | 34份Python源码/迁移逐字节一致 | `package-source.txt` |
| 部署状态、权限与资源清理 | 服务就绪、普通应用不能读写维护表，测试数据和资源已清理 | `cluster-final.txt` |
| 文档链接、版本与字段 | 已核对，结果见证据文件 | `documentation-check.txt` |

人工review核对：维护入口只用专用账号；代码及范围摘要不接受替换；源事实未改写；检查点与副本/收据同事务；最终替换失败全部回滚；重复终态不追加结果；错误记录不泄露原文或SQL参数。维护生成的副本名由UUID确定，成功只删除本次副本，失败不清理。

| 人工review范围 | 核对结论 |
| :--- | :--- |
| 读取与所有者转换 | 复用已有授权与固定Schema；在线/维护共用转换；原事实不修改，不从当前账号行取原文 |
| 重建与迁移 | 专用身份、维护互斥、固定上界及实现摘要齐全；副本/收据/进度共同保存；最终提交失败恢复旧数据 |
| CLI与故障 | 显式维护确认；新进程能续做；终态重复查询不重放；失败仅保留错误类别，不输出敏感异常输入 |
| 测试及文档 | 真实构建包运行故障用例；新增13字段与DDL一致，规划表数量及跨文档入口同步；无后续业务占位 |

## 6. 当前限制与下一步

首批仅有账号查询投影，不能将本轮通过当成所有模型、教学和评价数据可重建。运行中的Execution、凭据、Wait及Temporal历史仍按运行恢复和整批备份合同处理。正式业务库没有测试账号，因此本轮在隔离测试库演练恢复，不为演示注入正式数据。

本增量交付用户评审；下一步按实施计划进入E01-09，本轮不提前实现。
