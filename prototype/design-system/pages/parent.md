# DeerMind · 家长端覆盖（Parent Mode）

> 覆盖：`MASTER.md`（本文件规则优先于 Master）。
> 应用方式：原型中 `.parent-mode` 作用域；Flutter 中 `app_parent` 入口的主题层。
> 说明：本节将家长端"专业/清爽"偏差正式化，属**有意覆盖**，非疏漏。

## 风格

Soft UI —— 清爽、专业、数据清晰、低干扰。

## 令牌覆盖

| 令牌 | 值 | 说明 |
|---|---|---|
| `--radius-card` | 14px | 卡片圆角 |
| `--radius-btn` | 8px | 按钮圆角（对齐 MASTER） |
| `--radius-input` | 8px | 输入框圆角 |
| `--card-bg` | `#FFFFFF` | 白卡 |
| `--btn-weight` | 600 | 对齐 MASTER |
| `--shadow-card` | 0 2px 8px | 轻投影，无粗描边 |
| 字体 | system-ui / 苹方 / 微软雅黑 | 去卡通感（覆盖 MASTER 的 Baloo/Comic） |

## 组件规格

- **卡片**：白底，radius 14px，padding 20px，轻投影
- **按钮**：radius 8px，字重 600，主按钮 `#22C55E`
- **输入框**：radius 8px，1px 描边
- **数据展示**：统计卡网格（手机 3 张横排 / 平板 3–4 张）、掌握率进度条、薄弱点清单（三色）
- **学习空间卡片**：左侧色条区分类型（学校 / 辅导班）

## 掌握度三色（与孩子端一致）

绿 = 已掌握 / 黄 = 攻克中 / 红 = 需关注

## 导航

手机：底部 Tab；平板/桌面（≥768px）：左侧 Navigation Rail。

## 无障碍

- 对比度 4.5:1；焦点可见；`prefers-reduced-motion`；触控目标 ≥44px
- CTA 按钮同 child 无障碍备注（加深绿或深字）

## 反模式

- 禁 emoji 图标 / 过度游戏化 / 信息轰炸（默认只展示三色 + 异常告警）
