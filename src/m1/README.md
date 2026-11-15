# DeerMind M1 工程

按[实施计划](../../doc/mvp/m1/engineering/Delivery_Plan.md)的小增量交付。旧交互原型仅作参考。

当前只实现 E01-01：独立 WSL/K3s 测试环境、显式部署目标检查及测试。应用、数据库、Temporal、NATS 和前端随后续增量建立。

| 目录 | 用途 |
| :--- | :--- |
| `scripts/check-target.sh` | 只读检查指定集群、命名空间和节点就绪情况 |
| `tests/deployment/` | 目标校验的异常测试及真实集群测试 |
| `deploy/components/manifest.yaml` | 本批实际安装版本、来源与文件校验值 |
| `deploy/environments/local-wsl/` | 本机初始化与复核说明 |
| `.artifacts/` | 本机测试输出，不提交凭据或大文件 |

开始使用：[本机环境说明](deploy/environments/local-wsl/README.md)。脚本在 WSL/Linux 执行；Windows 不另实现一套部署逻辑。
