# E03-09 管理端学习空间

管理端「学习空间」允许按学生姓名查找。选择空间后可看教材采用、学习目标和空间事件。教材取固定版本内容，目标显示 Evaluation 保存的判断，事件按类型筛选。

复验在 `deermind-m1` K3s。应用采用 `e03-09-r3`，业务库迁移 `0028_goal_results`。消息维护任务为 `deermind-nats-targets-e0309`。

[浏览器用例](../../../tests/browser/evaluation/course-spaces.cjs)和[数据库回归](../../../tests/migrations/test_domain.py)用于复核 E03-04 至 E03-09。证据目录为 `.artifacts/e03-09-k3s-20261123/`。当前部署镜像见[应用配置](application.values.yaml)。
