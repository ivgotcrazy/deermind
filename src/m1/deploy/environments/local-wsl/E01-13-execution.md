# E01-13 后台工作执行与恢复

[环境目录](README.md) · [实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

> 2026-11-17源码位置已按[独立抽象整改](E01-15-boundaries.md)迁移。下文保留本增量当时的路径、命令和验证事实；当前归属见整改清单。

## 1. 交付范围

基线`cd7598f`，验证批次`e01-13-20261116`。已实现Temporal派发、稳定Step、停止、有限重试及授权恢复；进度和用户评审状态只在实施计划维护。

- 同一受理请求返回原工作；启动回执丢失查同一Workflow，不另建工作。
- 已完成Step跨恢复尝试复用；同键异输入拒绝，旧尝试及停止后的结果不能提交。
- 业务结果、Step和状态事件共同提交；所有者收尾失败整次回滚。先业务锁，再执行行锁。
- 停止先保存取消状态，再通知Temporal；停止事件指向本次停止请求。获准恢复追加有限新尝试，原输入、实现、适用配置及消耗归属不变。
- 服务暂不可用保留原状态并记故障；确认执行已结束才收尾。核对按批轮巡，长任务不会一直挡住后续任务。

迁移`0008_execution`新增四张既定表：executions、execution_attempts、execution_authorizations、step_results。实际业务库24张表（含迁移表），114张规划表总数不变；授权和Step只允许追加。

## 2. 实现位置

| 位置（相对server/src/deermind） | 职责 |
| :--- | :--- |
| `foundation/system/executions/contracts.py` | 固定身份、模块登记、业务锁和资格/收尾适配 |
| `foundation/system/executions/store.py`、`commands.py` | 受理、状态、停止和授权恢复 |
| `foundation/system/executions/steps.py` | 稳定键、输入核对、业务结果原子保存 |
| `foundation/system/executions/facts.py` | 完整执行控制快照及维护读取，不重建或重新派发 |
| `foundation/system/executions/dispatch.py` | 持久交接次数、预算、租约及旧租约拦截 |
| `infrastructure/temporal/executions.py`、`relay.py` | 固定ID启动、取消、生命周期Activity和结束核对 |
| `bootstrap/executions.py`、既有Worker入口 | 统一限额及共享进程装配；业务流程仍归各模块 |

用户确认的限额：启动/取消单次5秒、最多5次、总限90秒、租约30秒；每30秒核对执行结束，每次收尾最多30秒。参数唯一维护于[基础设施§4.2](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#42-消息交接参数)。

## 3. 验证与证据

证据保存在M1根目录`.artifacts/e01-13-20261116/`，共108项测试通过，不重复累计多轮运行。

| 验证 | 数量 | 证据 |
| :--- | :--- | :--- |
| 编程检查、本地规范/目标/服务端测试 | 49 | `quality-final.txt`，含Ruff、两组Pyright、Shell、客户端类型及Chart检查 |
| 构建包的PG＋Temporal执行验证 | 11 | `execution-r4-package-tests.txt` |
| 迁移、事实保存、授权读取、请求收据回归 | 34 | `database/facts/reads/receipts-package-tests.txt`，分别8/13/12/1项 |
| PG＋NATS交接回归 | 9 | `delivery-package-tests.txt` |
| 实际部署、认证入口、SDK登记及共享卷 | 5 | `application-tests.txt` |

11项执行验证覆盖：事务失败回滚、重复受理、原步骤复用、旧尝试拒绝、停止留痕与迟到提交、所有者收尾失败、恢复不重置额度/期限、跨范围读取、启动回执丢失、真实Worker强杀后接续、Temporal终止收尾及查询失联。部分边界合并在同一用例；模型额度以所有者检查夹具验证，未调用真实模型。

回归组使用r1包；最终r4在其上补批次核对及停止请求留痕，重新通过全部11项执行验证和5项部署验证。静态及49项本地测试针对最终源码；`source-hashes.json`记录191份源码/配置与WSL检查副本一致。构建、部署和最终环境分别见`build-r4.txt`、`deploy-r4.txt`、`deployed-state.json`。

## 4. 部署与复核

本机目标：`/root/.kube/deermind-m1.yaml`，context/namespace=`deermind-m1`。应用Helm revision 17；API和Worker为`deermind/server:e01-13-r4`，客户端沿用`deermind/client:e01-11-r1`。服务端镜像manifest为`sha256:e1037ed24392cfe4539b801a7f406e14212972a749be8083ac55ad18aa00a3e6`。

```bash
# 沿用数据库组的显式集群、Secret、节点及构建镜像参数。
export M1_TEST_TEMPORAL_ADDRESS=deermind-temporal-frontend:7233
export M1_TEST_TEMPORAL_NAMESPACE=dm-local-wsl
bash scripts/test.sh execution
```

参数说明见[quality README](../../../quality/README.md#e01-13执行恢复验证)。测试使用随机隔离库、测试队列和独立子进程，不重启正式Worker；结束清理本例工作、测试库及临时Pod。部署后确认API/Worker/客户端均1份就绪，正式库accounts、events、executions均为0，临时测试库和Pod均为0。

## 5. 人工review与边界

- 核对模块依赖和事务：底座不组织业务步骤，不在事务中调用Temporal或模型；所有者业务锁先于执行锁，派发回执不把终态改回运行。
- 核对失败路径：租约过期的返回不能覆盖新持有者；停止及恢复均保留原工作和已完成结果；取消安排按停止请求及尝试定位。
- 核对可读性和日志：按职责分文件，注释说明锁、原子提交、迟到和恢复边界；错误日志不输出正文或凭据。
- 核对本轮文档：900处本地文件引用及当前版本的修订记录通过检查，见`document-review.json`；未检查外部网址可用性。
- 测试最初的12秒ScheduleToClose不足以覆盖强杀后的接手；Temporal历史证实为测试时限耗尽，现改为60秒测试预算，正式配置未放宽。

生产业务登记仍为空，正式Operation随所属业务增量接入；测试Workflow不进入正式登记。AI配置接入、真实用量累计及模型调用留E01-15，跨Space等待留E01-14；本轮未新增页面或公开业务接口，也未验证100人容量和整套灾难恢复。

Temporal接线参考[官方客户端文档](https://docs.temporal.io/develop/python/client/temporal-client)及[错误处理文档](https://docs.temporal.io/develop/python/best-practices/error-handling)，沿用已锁定SDK，未增加依赖。
