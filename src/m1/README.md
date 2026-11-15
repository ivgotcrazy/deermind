# DeerMind M1 工程

按[实施计划](../../doc/mvp/m1/engineering/Delivery_Plan.md)的小增量交付。旧交互原型仅作参考。

当前已交付 E01-01 环境和 E01-02 基础组件自检：PostgreSQL、Temporal、NATS及共享文件卷。应用、业务表和前端留到后续增量。

| 目录 | 用途 |
| :--- | :--- |
| `scripts/check-target.sh` | 只读检查指定集群、命名空间和节点就绪情况 |
| `scripts/deploy.sh` | 显式目标下部署一个Helm release，不自动执行迁移或删库 |
| `deploy/helm/` | PG服务、数据库初始化及显式Temporal Schema Job |
| `tests/deployment/` | 目标检查、组件重启持久化、权限及共享卷测试 |
| `deploy/components/manifest.yaml` | 本批实际安装版本、来源与文件校验值 |
| `deploy/environments/local-wsl/` | 本机初始化与复核说明 |
| `.artifacts/` | 本机测试输出，不提交凭据或大文件 |

基础组件：[部署与复核](deploy/environments/local-wsl/components.md)。

开始使用：[本机环境说明](deploy/environments/local-wsl/README.md)。脚本在 WSL/Linux 执行；Windows 不另实现一套部署逻辑。
