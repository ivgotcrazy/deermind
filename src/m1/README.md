# DeerMind M1 工程

按[实施计划](../../doc/mvp/m1/engineering/Delivery_Plan.md)的小增量交付。旧交互原型仅作参考。

当前已推进到E01-04：六个模块schema、数据库迁移及启动检查，沿用E01-03的可安装后端包、API／共享Worker、Vue学生／管理员双入口，以及应用镜像和Helm。业务表、登录、聊天和AI留对应增量。

应用遵循[编程规范](../../doc/mvp/m1/engineering/Coding_Standard.md)。E01-03的安装、启动、复核和自检见[应用交付](deploy/environments/local-wsl/application.md)，检查工具见[quality说明](quality/README.md)。E01-04的迁移命令、范围和验证见[数据库交付](deploy/environments/local-wsl/database.md)。

| 目录 | 用途 |
| :--- | :--- |
| `scripts/check-target.sh` | 只读检查指定集群、命名空间和节点就绪情况 |
| `scripts/deploy.sh` | 显式目标下部署一个Helm release，不自动执行迁移或删库 |
| `scripts/check.sh` / `scripts/test.sh` | 静态检查、本地正反样例及显式目标回归 |
| `quality/` | 独立开发检查依赖、规则和版本锁；不包含应用 |
| `server/` | 唯一Python安装包、uv锁文件及严格类型测试 |
| `clients/` | Vue双入口、共享组件与样式、npm锁文件 |
| `contracts/generated/http/` | 从实际FastAPI路由生成的OpenAPI快照 |
| `deploy/images/` / `scripts/build-app.sh` | 锁定基础镜像和仅产物构建入口 |
| `deploy/helm/` | 基础组件、自有应用及显式初始化Job |
| `server/migrations/` | 单一业务库迁移链，随后端wheel发布 |
| `tests/migrations/` | 临时数据库中的升级、回滚、权限和服务启动测试 |
| `tests/deployment/` | 目标检查、组件重启持久化、权限及共享卷测试 |
| `deploy/components/manifest.yaml` | 本批实际安装版本、来源与文件校验值 |
| `deploy/environments/local-wsl/` | 本机初始化与复核说明 |
| `.artifacts/` | 本机测试输出，不提交凭据或大文件 |

基础组件：[部署与复核](deploy/environments/local-wsl/components.md)。

开始使用：[本机环境说明](deploy/environments/local-wsl/README.md)。脚本在 WSL/Linux 执行；Windows 不另实现一套部署逻辑。

安装检查工具后，在本目录执行：

```bash
bash scripts/check.sh
bash scripts/test.sh local
```
