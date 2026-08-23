# DeerMind 呦鹿智伴 · 高保真交互原型

基于 `doc/产品设计.md`（v1.3）的 1:1 可交互原型，**产品设计即原型**。

- 技术栈：Vue 3 + Vite + TypeScript + Vue Router + Pinia（纯前端 mock，无后端）
- UI 规范：`ui-ux-pro-max`（uipro-cli）生成的 `design-system/deermind/MASTER.md`
  - 孩子端：Claymorphism（软陶风，靛蓝 #4F46E5 + 进度绿 #22C55E，Baloo 2 / Comic Neue）
  - 家长端：Soft UI 覆盖（同色板，更清爽专业）
- 形态：独立双端（孩子端 / 家长端），**响应式布局**（手机/平板），浏览器全屏演示
- 顶部工具栏：角色切换、断点指示、PRD 对照、重置

## 运行

```bash
npm install
npm run dev      # 开发服务器 http://localhost:5173
npm run build    # 产物在 dist/
```

## 演示说明

- 顶部工具栏：
  - **角色切换**：孩子端 / 家长端（两个独立入口，无 PIN）
  - **断点指示**：显示当前视口（手机/平板），拖动窗口宽度即可体验响应式
  - **PRD 对照注释**：每页角标显示对应的 PRD 章节
  - **重置**：回到孩子端首页并清空流程状态
- 全程手动点击体验：孩子端旅程 首页 → 拍题（OCR mock）→ 归因对话 → 读题训练 → 讲解（TTS mock）→ 练习 → 变式验收 → 小结；家长端旅程 今日/周报（J5）→ 学习空间（J1）→ 新建空间

## 页面清单（对齐 PRD §4 信息架构，全部完成）

**孩子端（12）**：首页 / 摸底（J2） / 拍错题 / 归因对话 / 读题训练 / 讲解 / 练习 / 变式验收 / 小结 / 间隔复习（J4） / 进度画像 / 我的-设置

**家长端（8）**：今日日报（J5） / 周报（J5） / 学习空间（J1） / 新建空间 / 错题详情 / 家长录入（J6） / 记忆（§8.8） / 设置（J7）

## 目录

```
prototype/
  .github/prompts/ui-ux-pro-max/   # ui-ux-pro-max 技能（uipro init 安装）
  design-system/deermind/MASTER.md # 设计系统（ui-ux-pro-max 生成）
  src/
    data/mock.ts                   # 学习空间/知识点/错题/对话/练习/变式 mock
    stores/app.ts                  # 模式、学习空间、J3 流程状态
    styles/tokens.css              # 设计令牌（Claymorphism + Soft UI 家长覆盖）
    components/                    # 小鹿、图标、双端外壳、PRD 注释
    views/child/  views/parent/    # 孩子端 / 家长端页面
```
