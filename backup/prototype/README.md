# DeerMind 呦鹿智伴 · 高保真交互原型

基于《产品设计.md》**v0.4.1**（证据驱动的学习决策引擎）与《概念产品.md》**v0.4.0** 的 1:1 可交互原型。

> 核心哲学：**减负优先 · UNKNOWN≠已掌握 · 掌握必须有证据 · AI 的安静也是一种成功。**
> 学习决策引擎（Evidence → Mastery → Policy → Next Best Action → Stop）是三端的共享内核，三端只是它的三个视角。

## 技术栈

- Vue 3 + Vite + TypeScript + Vue Router（hash 路由）+ Pinia（纯前端 mock，无后端）
- UI 规范：`design-system/`（ui-ux-pro-max 生成，MASTER + 学生/家长/管理员三端覆盖）

## 三端结构

```
原型 = 同一个学习引擎的三个观察/交互界面
├── 学生端（student）  体验层：Chat=控制面，结构化=执行面
├── 家长端（parent）   观察层：默认零操作，只收异常/周报
└── 管理员端（admin）  Evidence Debugger：当前状态→证据→政策→为什么
```

三端**共享同一份 mock 学习状态**（`src/stores/evidence.ts`）：学生端学完 → 家长端周报/今日变化 → 管理员端出现对应证据与决策，实时联动。

## 领域模型（对齐 PRD v0.4.1）

```
Concept（知识点本体，去年级化）＋ MasterySnapshot（掌握快照）分离
MasteryState = UNKNOWN / LEARNING / SHORT_TERM_MASTERED / STABLE_MASTERED
Evidence = polarity(正/负) + informationValue(信息价值) 分离
```

- `src/data/sharedMock.ts`：领域模型类型 + seed（概念/快照/证据账本/决策/空间/学生/规则/Attention）
- `src/stores/evidence.ts`：applyEvidence（证据入账 → 演示估计器合成 → 状态判定 → 决策记录）
- `src/stores/studentChat.ts`：学生端登录态、意图路由、四态流转对话流
- `studentMock.ts` 仅作为**内容型 seed**（题目/讲解/读题/Teach-back 引导），不作为状态源

## 页面清单

| 端 | 页面 |
|---|---|
| 学生端（8） | 登录 / 首页（今日安排 + 大对话区 + 快捷：拍题·复习）/ 拍照 / 确认 / 讲题（归因→讲解→练习→变式）/ 读题 / Teach-back / 设置 |
| 家长端（4） | 今日（平静摘要 + 可展开详情）/ 周报（四态分布 + 状态变化 + 停止记录）/ 学生账号 / 学习空间 |
| 管理员端（4） | Dashboard / 知识点（Concept Decision Inspector）/ 决策理由 / 规则配置 |

## 运行

```bash
npm install
npm run dev        # 开发服务器 http://localhost:5173
npm run build      # 产物在 dist/
npm run type-check # vue-tsc --noEmit（0 错误为准）
```

## 演示说明

- 顶部工具栏：**学生端 / 家长端 / 管理员端** 角色切换、断点指示、PRD 对照、重置
- **重置**：清空三端共享状态 + 对话，回到登录页，演示可重跑
- 学生端核心旅程：登录 → 复习/检验 → 变式（即时迁移）→ **短期已会** → 迁移题（高价值）→ **稳定掌握** → 停止（"可以去玩啦"）
- 所有 estimate/confidence/stability 与政策评分为**演示值**，页面脚注统一标注「演示数据 · 算法见《系统设计.md》」
