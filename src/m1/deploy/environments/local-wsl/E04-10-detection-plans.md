# E04-10 检测题单准备

2026-11-23 在 `deermind-m1` K3s 验证，迁移 `0033_detection_plans`，应用 Helm 修订 74。

- 独立入口和聊天入口各准备了两道题。聊天入口沿用原请求和执行身份。两个入口都显示题单摘要，等待学生确认，没有显示答题区。
- 题单从已采用目标引用的 Claim 解析到领域 Task，经同一 Domain 供题流程准备。首次部署遇到 Claim 字段读取和保存时受理状态核对错误，修正后重跑通过。
- 静态检查和 81 项后端单测通过，本次覆盖完整题单。

验证脚本为 `tests/browser/interaction/detection-plans.cjs`，题单、收据及截图位于 `src/m1/.artifacts/e04-10-k3s-20261123/`。

## 中断与部分缺题复验

应用 Helm 修订 83。合成题单要求两种方法。两组供题结果均已记录，保存题单前令 Worker 退出一次。重启后同一执行沿用原结果，提交步骤第 2 次运行。复验在提交步骤模拟其中一组结果不可用，浏览器显示一道可用题和一条缺题提示，学生仍需确认。数据库中只有一份准备好的题单，检测轮数为零。

故障前后日志、数据库对照、回执和截图见 `src/m1/.artifacts/e04-special-k3s-20261123/` 的 `plan-before.txt`、`plan-after.txt`、`plan-proof.json` 和 `browser/partial-detection-plan.*`。
