# E01-04：数据库结构与迁移

本增量建立业务库的六个模块schema和`public.alembic_version`。112张规划表按所属增量逐步迁移；本轮不创建业务空表，不实现E01-05的事件和收据写入。

## 1. 交付边界

| 交付 | 实现 |
| :--- | :--- |
| 单一迁移链 | `server/migrations/versions/0001_infrastructure_schemas.py`；head为`0001_infrastructure_schemas` |
| 模块schema | product、domain、interaction、evaluation、runtime、ai；所有者为deermind_migrator |
| 迁移记录 | `public.alembic_version.version_num varchar(32) NOT NULL PRIMARY KEY`，与数据库设计§5一致 |
| 升级入口 | `deermind-database upgrade`，只使用显式环境配置；脚本随wheel打包 |
| 原子升级 | 单一事务内取得数据库部署锁、执行DDL、写版本；冲突退出，中断回滚，不自动重试 |
| 权限 | 应用只获schema USAGE及版本表SELECT；后续迁移逐表授予所需读写权限；不预授所有未来表权限 |
| 启动检查 | API／Worker检查当前账号、版本和六个schema；不兼容时停止，不自动执行DDL |
| 部署 | 独立迁移Job，完成后发布应用；迁移身份不注入API／Worker |

依赖使用SQLAlchemy **2.1.8**的asyncio扩展、psycopg **3.3.9**的binary扩展、Alembic **1.20.1**。传递依赖及hash锁在`server/uv.lock`；不另装驱动连接池。模型和业务处理不在本轮范围。

API与Worker各自只有一个Engine：pool_size=5、max_overflow=0、pool_timeout=3秒。连接5秒，单条SQL10秒，锁等待3秒，事务空闲10秒；退出时释放池。迁移使用单连接NullPool及独立Job期限，不套用短SQL时限。API就绪探针持续检查数据库；Worker在开始拉取任务前检查，不据此承诺数据库故障期间业务任务仍可执行。

## 2. 配置与发布

| 环境变量 | 来源 |
| :--- | :--- |
| M1_DB_HOST / PORT / NAME | 显式环境values；本机deermind-postgres / 5432 / deermind |
| M1_DB_USER | 应用固定deermind_app；迁移固定deermind_migrator |
| M1_DB_PASSWORD | 既有Secret的app-password或migration-password，仅注入所需字段 |

不在命令行、配置仓库或日志中输出密码。迁移使用与应用相同的后端镜像；wheel内携带脚本，容器不挂载源码。开发态从`server/migrations`读取，仍经过同一个命令和部署锁，不提供绕过保护的直接Alembic执行入口。

按[应用交付§2](application.md#2-构建)启动本机BuildKit，构建新后端：

```bash
bash scripts/build-app.sh deermind/server:e01-04-r2 deermind/client:e01-03-r2 \
  .artifacts/e01-04-20261115/images-r2
```

本轮后端镜像为`deermind/server:e01-04-r2`，OCI manifest SHA-256：`9d14ca7b2e9ed72aab5929bd2485b30a6b393e4bcae1342aee702114d5adb406`。客户端未改动，继续使用已部署的E01-03镜像。显式核对目标后，只导入本轮后端镜像：

```bash
set -e
bash scripts/check-target.sh --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1
k3s ctr images import .artifacts/e01-04-20261115/images-r2/server.tar

bash scripts/deploy.sh --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1 --release deermind-db-e0104-r2 \
  --chart deploy/helm/database-migration \
  --values deploy/environments/local-wsl/database-migration.values.yaml

bash scripts/deploy.sh --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1 --release deermind-app \
  --chart deploy/helm/application \
  --values deploy/environments/local-wsl/application.values.yaml
```

`deploy.sh`等待Job完成，失败返回非零，以上命令随即停止。迁移Job不自动重试；排查后再次执行用新的release名，保留旧失败记录。同一版本再次升级不建重复schema、不重置数据。已存在但不在迁移记录中的schema视为冲突，不静默接管。

不支持破坏性降级或自动清库。升级失败时保留旧应用和原数据；升级成功但新应用失败时停止发布，按已审兼容或恢复方案处理，不自动把新库强行降回旧库。

## 3. 验证与自检

在M1目录运行，先安装已锁定依赖和检查工具：

```bash
uv sync --project server --locked
bash scripts/check.sh
bash scripts/test.sh local

export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-04-r2
bash scripts/test.sh database

M1_APPLICATION_RELEASE=deermind-app bash scripts/test.sh application
```

数据库测试在临时Pod中使用已构建镜像，凭据通过Secret引用注入，结束后删除本次Pod。仅创建随机`dm_e0104_test_<uuid>`数据库，清理也只针对本次生成的名字。中断测试在首批DDL执行中终止该测试连接，核对schema和版本记录一起回滚，再重试升级。另测并发迁移锁、未知schema拒绝接管、应用禁止DDL/修改版本、Temporal账号禁止连接业务库，以及两个服务的启动拒绝。测试不删改既有业务库或Temporal库。

本轮于2026-11-15开始、跨日完成，证据保存在`.artifacts/e01-04-20261115/`。

| 验证 | 结果与证据 |
| :--- | :--- |
| 全部静态检查 | 通过：`check-initial.txt`；最后修改的检查另见`final-accepted.txt` |
| 本地检查器、部署入口及后端 | 19项通过：`local.txt`；其中7项检查器、4项部署入口、8项后端测试 |
| 真实数据库 | 8项通过：`database-accepted.txt`；使用已构建镜像，不从源码目录导入 |
| 已部署应用 | 5项通过：`application-accepted.txt`；浏览器入口/API代理、包安装、启动拒绝、SDK登记、共享卷任务 |
| 实际迁移 | `migration-deploy.txt`记录empty到首版本；`migration-repeat.txt`记录同版本重复升级 |
| 部署与清理 | `cluster-accepted.txt`记录6个schema、1张迁移表、应用就绪及测试库清零 |

人工review已核对：

- schema和版本字段与数据库设计一致；不多建业务表，不设置未来表的默认全权限。
- 迁移脚本打入wheel；API／Worker只有运行凭据，迁移Job独立注入迁移凭据。
- 同一连接取得事务锁并执行DDL、版本写入；断连后的回滚由真实PG验证，成功和失败日志不包含密码。
- 程序拒绝不兼容版本，Worker在检查通过前不连接Temporal；连接池在失败和退出时释放。
- 脚本、测试按逻辑分段，补齐中文说明；权限测试必须收到明确的权限拒绝，不能用网络错误冒充通过。
- OpenAPI重新从代码生成；交付计划、依赖参数、数据库状态和本记录相互引用。

初次接线发现并处理了三点：SQLAlchemy异步支持需安装asyncio扩展；强制断连会使本机port-forward退出，测试改为集群内临时Pod；临时测试Pod按1秒退出宽限清理，避免默认30秒宽限与删除等待上限碰撞。失败记录保留在`database-initial.txt`、`database-second.txt`、`database-container.txt`，未放宽数据库断言。

本轮没有验证112张业务表、事件原子写入、备份恢复或100人容量。E01-04交付待用户评审，E01-05未开始。
