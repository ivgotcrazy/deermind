# DeerMind · 孩子端覆盖（Child Mode）

> 覆盖：`MASTER.md`（本文件规则优先于 Master）。
> 应用方式：原型中 `.child-mode` 作用域；Flutter 中 `app_child` 入口的主题层。
> 说明：本节将 MASTER 通用组件规格中的"儿童端偏差"正式化，属**有意覆盖**，非疏漏。

## 风格

Claymorphism（软陶 / 粘土风）——软 3D、圆润、活泼、儿童友好、鼓励式。

## 令牌覆盖

| 令牌 | 值 | 说明 |
|---|---|---|
| `--radius-card` | 24px | 卡片圆角（MASTER 基础 12px） |
| `--radius-btn` | 18px | 按钮圆角（MASTER 基础 8px） |
| `--radius-input` | 14px | 输入框圆角（MASTER 基础 8px） |
| `--border-thick` | 3px | 卡片粗描边（MASTER 无） |
| `--card-bg` | `#FFFFFF` | 白卡（置于 `#EEF2FF` 背景） |
| `--btn-weight` | 700 | 按钮字重（MASTER 基础 600） |
| `--shadow-card` | 4px 4px 0 + inset 双阴影 | Claymorphism 双阴影 |
| 字体 | Baloo 2 / Comic Neue | 儿童友好（MASTER 同） |

## 组件规格

### 卡片 Card
白底，radius 24px，padding 24px，3px 粗描边 `rgba(79,70,229,.08)`，双阴影；hover 轻抬。

### 按钮 Button
radius 18px，字重 700，padding 12×24；
主按钮 `#22C55E` + 白字 + 3D 底阴影（0 4px 0）+ 按下下压 2px；
次按钮（ghost）主色描边。

### 输入框 Input
radius 14px，2px 描边 `#E2E8F0`，字号 16px，focus 主色 + 3px 光环。

### 对话气泡 Chat Bubble
小鹿（AI）左对齐白底，圆角 16px（左上角 4px）；孩子右对齐主色底白字（右上角 4px）。

### 掌握度三色
已掌握 `#22C55E` / 攻克中 `#F59E0B` / 需关注 `#EF4444`（+ 淡色底 pill）。

### 导航
手机：底部 Tab；平板/桌面（≥768px）：左侧 Navigation Rail。

### 步骤/进度
读题训练步骤编号、练习进度点、掌握率进度条——圆角，当前步主色、已完成绿色。

## 动效

- hover 200ms ease-out；按压 scale / 位移 150–200ms
- 通过 / 成就反馈使用软弹曲线 `cubic-bezier(0.34,1.56,0.64,1)`
- 尊重 `prefers-reduced-motion`

## 无障碍

- 焦点可见 3px 光环；触控目标 ≥48px
- ⚠️ CTA 绿 + 白字对比 2.3:1 不达 AA → 主按钮使用加深绿 `#16A34A`（折中）或 `#15803D`（AA 达标），或改用深色字

## 反模式

- 禁 dark mode / 复杂术语 / emoji 当图标 / 无 cursor:pointer / 低对比文字
