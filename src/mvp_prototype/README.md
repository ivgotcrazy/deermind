# DeerMind MVP 交互原型

> **版本**：v0.13<br>
> **文档性质**：当前原型入口、运行说明与切换记录<br>
> **状态**：Phase 4 交互原型；统一目录，G4 尚未通过，不代表正式 MVP 实现<br>
> **维护责任**：Codex 维护；用户确认产品取舍及界面调整<br>
> **上游依据**：用户于 2026-10-25 授权以新版替换旧原型，原始来源及未迁入能力通过 Git 保留<br>
> **写作规范**：[设计文档规范](../../doc/top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-10-25<br>
> **修订说明**：原 `mvp_prototype_next` 成为唯一现行 `mvp_prototype`；解除旧测试依赖，统一启动和参考入口。旧版删除不等于相关能力全部迁入，历史交付记录见下文。

---

## 1. 当前入口与运行

在仓库根目录执行，也可双击根目录的 `prototype.cmd`：

```powershell
.\prototype.cmd start -Role admin
.\prototype.cmd status
.\prototype.cmd restart -Role admin -NoBrowser
.\prototype.cmd stop
```

本目录的 `prototype.cmd` 使用同一启动脚本。默认端口保持 **5181**，学生、家长、管理员由同一后台服务提供：

- [学生端](http://127.0.0.1:5181/student/)
- [管理员端](http://127.0.0.1:5181/admin/)
- [家长端](http://127.0.0.1:5181/parent/)

首次启动安装依赖、检查类型并构建三端；`restart` 重新构建并启动。页面使用静态构建，无 HMR，代码变更后需要刷新。旧 5178 页面入口已退役，不能再使用 `structure.html`、`phase4.html` 或旧版 `-Structure`、`-Foundation` 参数。

模型配置仍读取仓库根目录 `.env` 的 `DEERMIND_LLM_*`，服务端会话仍在 `.tmp/mvp-live/`。浏览器来源、存储键和会话归属保持不变，不需要清理浏览器数据。`.tmp/mvp-prototype-next/` 继续存放既有运行状态与检查证据；其中的名称是历史存储标识，不是对旧源码目录的依赖。

## 2. 目录与能力边界

| 位置 | 用途 |
| --- | --- |
| `student/` | 基于原 V2 的学生界面、连续对话、课堂进度和当前学习流程 |
| `admin/` | 当前模型、课程、账号及运行观测原型 |
| `parent/` | 保留此前迁入的家长界面，本轮仅移除退役的“旧流程工具”链接 |
| `shared/` | 当前 mock 课程流程和图文教材呈现 |
| `scripts/` | 三端服务、模型连接、会话保存及启动管理 |
| `tests/` | 服务检查与浏览器走查，测试依赖由本目录独立安装 |

真实 LLM 对话已有连接，但不代表接入完整 DeerMind 模型。后台及教材整理继续使用 mock。真实书页 49—50、91—93 已内置：教材管理 → 导入教材 → 载入真实教材书页 → 上传并开始整理。自选文件不进行真实 OCR。取消、删除未完成导入、保存和应用均为当前本地走查能力。

家长端仅保留，不在本轮继续打磨；学生多模态、正式模型运行、真实账号权限及未接通的评价仍须后续设计或工程实现。迁移不恢复旧审批流程，也不把旧预写结果变成当前真实判断。

## 3. 检查方式

在本目录执行：

```powershell
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd test
npm.cmd run test:learning
node tests/browser-controls.mjs
node tests/browser-parent.mjs
```

浏览器检查使用本机 Edge，测试服务使用独立临时目录和固定模型响应，不消耗真实模型调用、不删除用户浏览器资料。`browser-parent.mjs` 从下述 Git 提交读取来源，校验历史迁入清单；不再依赖旧工作目录。`--compare-legacy` 只供另行检出历史源码并运行 5178 服务时进行历史对照，不属于当前启动或检查前提。

## 4. 历史与未迁入内容

清理前已核对旧目录工作树无待保存源码，基线提交为 `e0895562acb4757e9f80af888643ab1e27d48506`。旧源码通过 Git 查看或另行检出，不设长期归档。

**清理尚未完成：** 新版目录及启动入口已切换，但自动审批审查拒绝了旧目录的递归删除，未返回具体原因。以下三处暂存旧文件仍待删除，当前服务和默认测试均不依赖它们：

- `.tmp/prototype-consolidation-20261025/old-mvp-prototype/`（仓库根目录下）
- `src/mvp_prototype_v2/`
- `src/mvp_admin_prototype/`

| 历史内容 | 固定引用 |
| --- | --- |
| 原 `mvp_prototype` | [旧实现](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype) |
| 原学生 V2 | [学生原始基线](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype_v2) |
| 原管理员 V2 | [管理员原始基线](https://github.com/ivgotcrazy/deermind/tree/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_admin_prototype) |
| 本次替换前的新原型及迁入清单 | [原型 v0.12 说明](https://github.com/ivgotcrazy/deermind/blob/e0895562acb4757e9f80af888643ab1e27d48506/src/mvp_prototype_next/README.md) |

M01–M16 的早期状态和作者评审按原时间阅读，不反写为当前完成状态。当前已接入的流程以现行源码和检查为准；旧多模态工具、未承接的历史记录操作、旧家长事项回传等只保留为参考，删除目录不表示批准迁入或取消对应需求。正式归并仍遵守 MVP 的文档职责。

`BASELINE_MANIFEST.json` 与 `parent/BASELINE_MANIFEST.json` 保留复制当时的源、目标路径和哈希；其中 `mvp_prototype_next` 是历史路径。旧说明、旧代码、归档设计与评测结果应连同其 Git 基线阅读，不能因为当前目录同名就引用当前实现解释旧结果。

本轮仅统一目录、依赖及入口，保留此前删除导入等已授权改动。具体变更和文档升版见 [共同管理记录 §5.3](../../doc/mvp/MVP_Governance.md#53-原型目录统一2026-10-25)。G4/G5 未因此通过。
