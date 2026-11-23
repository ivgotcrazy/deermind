# E03-09 管理端学习空间

管理端「学习空间」允许按学生姓名查找。选择空间后可看教材采用、学习目标和空间事件。教材取固定版本内容，目标显示 Evaluation 保存的判断，事件按类型筛选。

复验在 `deermind-m1` K3s。应用采用 `e03-09-r4`，Helm 修订 54，业务库迁移 `0028_goal_results`。消息维护任务为 `deermind-nats-targets-e0309`。

首轮 r4 等待 API 就绪超时。API 随后通过启动检查，重新执行同一部署成功。API、Worker 和客户端均为 1/1 就绪。证据见 `deploy-r4-verify.txt`。

[浏览器用例](../../../tests/browser/evaluation/course-spaces.cjs)和[数据库回归](../../../tests/migrations/test_domain.py)用于复核 E03-04 至 E03-09。证据目录为 `.artifacts/e03-09-k3s-20261123/`。当前部署镜像见[应用配置](application.values.yaml)。

| 核对 | 结果 | 证据 |
| --- | --- | --- |
| 课程检查、应用、学生选用、目标重评与后台三个页签 | 浏览器通过，含方法名称和教材正文检查 | `browser/course-spaces.txt`、`browser/course-space-chain.json` 及截图 |
| 迁移、两章目标范围、无备用题、迟到与重复目标通知 | 12 项真实 PostgreSQL 回归通过 | `domain-regression-final.txt` |
| 后端单测、依赖边界与类型检查 | 71 项后端单测通过。Ruff、Pyright、Vue 类型及 OpenAPI 生成检查通过 | `backend-tests.txt` |

最后一次数据库复验仅将外层测试进程等待上限临时延长至 300 秒。应用的运行时限和部署配置沿用原值。
