# E01-14 结果登记与等待接续

> **版本**：v0.2<br>
> **日期**：2026-11-17<br>
> **进度**：[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)是唯一状态来源

[环境目录](README.md) · [运行合同](../../../../../doc/mvp/m1/engineering/System_Foundation_Design.md#49-e01-14结果与等待接线)

> 2026-11-17源码位置已按[独立抽象整改](E01-15-boundaries.md)迁移。下文保留本增量当时的路径、命令和验证事实；当前归属见整改清单。

## 1. 交付

基线`92dd268`，验证批次`e01-14-20261116`。消费方决定等什么、等多久及之后做什么；底座保存结果身份、等待决定和接续收据，生产方不依赖等待者。

- 结果按固定ResultKey登记。正式事实、业务结果及发布索引同事务保存；重复同内容返回原结果，异内容拒绝。
- 登记后先补查，再用Temporal Signal／Timer挂起。等待不占Activity槽位、模型调用或数据库连接；通知只提示补查。
- 到期先查结果。查询跨过截止点且得到空结果时，再查一次；读取故障不按空结果处理。
- 命中、超时和取消只落定一次；接续在所有者事务内执行，重复通知不能重复提交业务。超时后迟到结果不能复活等待。
- 恢复保留原Wait及截止点。新的执行尝试仍须留出接续时间；停止消费工作不取消生产工作。

已确认参数：等待最多300秒，业务可更短；Signal单次5秒、最多5次、总预算90秒、租约30秒；每30秒补查。唯一参数口径见[基础设施§4.2](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#42-消息交接参数)。

## 2. 实现位置

| 位置（相对server/src/deermind） | 职责 |
| :--- | :--- |
| `foundation/system/waits/results.py` | 固定结果身份、生产尝试、发布与授权读取 |
| `foundation/system/waits/contracts.py`、`service.py` | 所有者策略登记、等待决定、业务接续及取消 |
| `foundation/system/waits/facts.py` | WaitStateChanged控制事实及维护读取；不承担业务投影 |
| `foundation/system/waits/notifications.py` | 消费方订阅适配；先保存Signal安排，再确认接住 |
| `foundation/system/executions/` | 共用租约、派发；失败/恢复同步生产尝试，停止撤销未提交等待 |
| `infrastructure/temporal/waits.py` | 短Activity、原生Signal／Timer及轮巡补查 |
| `bootstrap/waits.py`及共享Worker | 装配已实现能力；业务条件随所属增量登记 |

`0010_waits_results`新增五张既定运行表：expected_results、result_attempts、published_results、waits、wait_handling。实际29张表（含迁移表）；114张规划表总数不变。字段及约束见[运行分册§13—17](../../../../../doc/mvp/m1/engineering/database/Business_Runtime.md#13-runtimewaits)。

## 3. 验证

证据保存在M1根目录`.artifacts/e01-14-20261116/`。167项测试通过：等待专项12、既有运行及存储101、本地49、部署5；不累计重复运行次数。编程检查通过。

| 验证 | 验收点 | 证据 |
| :--- | :--- | :--- |
| 等待与结果专项 | 早到结果、重复/漏通知、超时迟到、到期二次查询、接续回滚及并发、停止、恢复不续期和预留不足、权限及不可变结果 | `waits-r4-package-tests.txt` |
| Temporal实际接续 | 单Activity槽位下进入原生Timer；退出Worker后重新接手，发送Signal继续，仅一次业务提交 | 同上 |
| 既有运行及存储回归 | 执行恢复、迁移、事实、文件、读取、账号、投影、请求收据及NATS交接 | `*-package-tests.txt` |
| 规范与本地测试 | Ruff、Pyright、Shell、Vue类型、生成合同及Chart；本地用例 | `check.txt`、`local-tests.txt` |
| 部署验证 | API、Worker、认证代理、SDK及共享PVC；不改变客户端界面 | `application-tests.txt`、`deploy.txt` |

最终r4包通过12项等待测试及5项实际部署测试。r2包通过执行11项和迁移8项；其余82项回归使用r1包。r4在此基础上只补恢复预留校验和wait_id日志，最终源码重新通过规范与49项本地测试。构建分别保留`build*.txt`；`source-hashes.json`核对166份源码、测试及配置与检查副本一致。

本机部署context/namespace=`deermind-m1`，应用Helm revision 20。API与Worker镜像为`deermind/server:e01-14-r4`，manifest `sha256:f9bf382693fecc5ec9276a676de2c14f1619b20d9cbbdd6f9fb89e4f91d786e5`；客户端沿用`deermind/client:e01-11-r1`。迁移为`0010_waits_results`，五表字段与DTO核对一致，详见`deployed-state.json`。

升级镜像时，原迁移Job不能修改容器模板；使用新release `deermind-migrate-waits-0010-r4`重复核对迁移，未删除旧Job或业务数据。首次拒绝与后续成功分别留存于`deploy-existing-job.txt`、`deploy.txt`。

在WSL执行，沿用execution测试组的显式目标配置：

```bash
export M1_TEST_TEMPORAL_ADDRESS=deermind-temporal-frontend:7233
export M1_TEST_TEMPORAL_NAMESPACE=dm-local-wsl
bash scripts/test.sh waits
```

测试只创建随机测试库及独立Temporal队列。测试Workflow在夹具中，不注册为正式业务；测试结束清理自己的资源。

## 4. 自检与限制

- 所有者提供只读probe和同事务接续；底座不查询教学私有表、不生成业务投影。
- 锁顺序为业务→Execution→Wait→控制事实；probe只锁Wait，避免反向取业务写锁。取消已提交接续只返回原收据。
- 原始结果与恢复尝试分开；未发布的结果必须先发布才能完成生产工作，不能靠Workflow关闭冒充有结果。
- Signal发往已登记尝试，不使用SignalWithStart；通知漏失可补查，已经结束的尝试不重启。
- 等待故障日志保留wait_id；日志不复制结果正文，事实及处理收据仍是追溯依据。

文档已核对本轮新增链接、版本及修订记录。历史DECISIONS仍有1处指向旧章节标题的锚点，本轮未改历史决定；清单在`document-check.json`。

这是公共运行能力验证，不代表正式供题、教学、评价已接线，也不代表100人容量通过。未调用真实模型，未修改页面；首条完整业务链仍归E01-18。本轮不推进E01-15。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-16 | 登记结果与等待接续、确认限额、部署及验证边界 |
| v0.2 | 2026-11-17 | 增加跨层迁移指引，保留原验证记录 |
