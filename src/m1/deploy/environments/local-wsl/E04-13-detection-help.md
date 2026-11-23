# E04-13 检测求助

2026-11-23 在 `deermind-m1` K3s 验证，迁移 `0035_detection_help`，应用 Helm 修订 78。

- 正式检测轮内请求提示，服务端先关闭本轮并取消剩余未开始项。然后真实模型生成答疑内容，子活动归属原检测活动。
- 旧轮拒绝补交。结束答疑后返回原检测活动，旧轮保持关闭，不能继续旧题单。
- 81 项后端单测通过。本次覆盖未提交求助及返回。求助先受理时的作答拦截、交卷后求助保留原记录于 [E04-16](E04-16-quarter-learning-path.md) 补验。

脚本 `tests/browser/interaction/detection-help.cjs`、事件关联及截图见 `src/m1/.artifacts/e04-13-k3s-20261123/`。
