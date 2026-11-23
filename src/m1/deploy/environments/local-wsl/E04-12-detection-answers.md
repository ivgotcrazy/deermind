# E04-12 正式作答与当题反馈

2026-11-23 在 `deermind-m1` K3s 验证，应用 Helm 修订 76，沿用 `0034_detection_rounds`。

- 两道题分别提交错答。首题关闭后只确认已保存，学生点击继续才打开不同的第二轮；末题返回真实模型生成的当题反馈。
- 同一请求重放返回原回执。关闭后用新请求再答返回 `round_closed`。无须等待掌握状态。
- 静态检查和 81 项后端单测通过。本轮浏览器记录覆盖错答。完整正确作答、反馈失败及重试恢复于 [E04-16](E04-16-quarter-learning-path.md) 补验。

脚本 `tests/browser/interaction/detection-answers.cjs`、回执和截图见 `src/m1/.artifacts/e04-12-k3s-20261123/`。
