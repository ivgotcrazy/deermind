# M1 交互原型

> **版本**：v0.2<br>
> **文档性质**：M1独立原型的范围、启动与复用说明<br>
> **状态**：领域管理与教材管理的本轮mock闭环可浏览；其他M1工作包尚未全部迁入<br>
> **上游依据与基线**：[M1 PRD](../PRD.md)、[交互规格](../design/Interaction_Design.md)及用户关于在M1目录新建精简原型的要求<br>
> **维护责任**：Codex维护；用户确认重要产品取舍<br>
> **评审记录**：本批构建及30项浏览器检查通过；用户认可交互大致逻辑，文档同期收束；不代表真实模型质量验收<br>
> **写作规范**：[设计文档规范 v1.1](../../../top/DeerMind_Design_Document_Standard_v1.1.md)<br>
> **更新日期**：2026-11-06<br>
> **修订说明**：v0.1 → v0.2：更新领域与教材走查、当前测试及截图采集方式，标明旧组件、旧测试和真实服务边界。本批依据与检查见决定登记第14节<br>

---

本目录是M1当前交互代码的维护位置，与上一级的PRD及design共同推进。旧原型保留为参考，M1不在旧原型上继续叠加。当前维护领域和教材两个入口，后续工作包各自设计、复用和核对，不把旧版完整菜单复制为新M1范围。

## 1. 启动与浏览

在仓库根目录双击`m1-prototype.cmd`，或运行：

```powershell
.\m1-prototype.cmd start
.\m1-prototype.cmd status
.\m1-prototype.cmd restart -NoBrowser
.\m1-prototype.cmd stop
```

也可以在本目录运行`prototype.cmd`。首次启动安装锁定依赖并构建，后台窗口隐藏；`-NoBrowser`只启动服务，`-Port 5183`可改端口。需要已安装Node.js及npm，版本要求见package.json。

默认地址是[http://127.0.0.1:5182/admin/#/textbooks](http://127.0.0.1:5182/admin/#/textbooks)。旧5181仍是旧原型，根目录原来的`prototype.cmd`也仍启动旧版，二者不会互相替换。

**走查路径：** 先在[领域管理](http://127.0.0.1:5182/admin/#/domain)新建领域或载入示例，查看Task、Solution、KC与实例；再在教材管理导入并选择领域，载入真实书页或四例样例，解析并核对。重新解析后采用结果，选择题目／解法／知识提交领域；处理完回教材添加章节任务及方法关联。

内置四例会创建独立mock领域，方便复核而不覆盖手动数据。普通文件选择没有OCR，不应把固定样例当成上传结果。题目与解法可分别处理，提取模板和关联实例是不同操作；章节关联另行保存。

页面使用构建结果，修改代码后运行restart。开发时可在本目录执行`npm run dev`，须先停止占用5182的预览服务。浏览器mock保存在本目录服务自己的来源下，使用M1专用存储键；更换端口或浏览器不会自动带入草稿。

## 2. 当前范围与限制

| 范围 | 当前表达 |
| --- | --- |
| Domain | 新建／编辑领域；Task、Solution、KC手动维护与搜索；复杂任务样例、递归方法、实例及参考解法 |
| 教材 | 必选领域、批量样例、章节三类内容、详情及原页、按说明重新解析、单独选择题目和解法、待入库、章节关联、继续与删除草稿 |
| 内容与模型分工 | 教材保留解析候选；领域复用或补建定义并关联实例；回教材选择章节Task／Solution，KC计算汇总 |
| 后续M1 | Task Claim、目标、教学模型、课程应用、学生端教学检测及真实评价／追溯尚未全部迁入，继续按工作包推进 |
| 真实服务 | 解析、重新解析、生成和语义匹配均为mock；本原型不调用LLM，不验收真实PDF／全册建模 |

当前使用本浏览器localStorage保存领域及教材草稿。它支持交互审阅，不是生产数据库、账号权限或不可变版本实现。测试用独立浏览器，不操作用户已有数据。历史组件代码仍在目录中，不表示都由当前路由使用；本次文档同步不删除旧组件。

## 3. 代码与检查

- `src/components/domain/`：领域对象、实例和待入库操作。
- `src/components/TextbookImport.vue`、`MaterialContents.vue`：导入、章节解析及关联。
- `src/model/`：Domain与教材mock、关系计算及样例；`public/materials/`保留真实原页。
- `scripts/`：启动、静态预览及文档截图；`tests/`为浏览器回归。
- [初始复用清单](reuse-manifest.json)记录独立原型建立时的来源，不代表后来每次新增功能的完整变更清单。

运行`npm run build`及`npm test`。Playwright缺浏览器时执行`npx playwright install chromium`。当前测试覆盖导入生命周期、语义内容工作流、行内入库、手动领域及复杂任务／方法模板。本批30项通过，原始日志在`test-results/documentation-review-tests.log`。

`npm run test:previous-import-ui`保留被替代工作区的旧测试，不能作为当前产品验收命令；它们尚未删除，也没有算入本批通过数。

构建及当前测试后，运行`node scripts/capture-domain-material-design.mjs`可重采本批文档画面，写入[当前资产](../design/assets/domain-material-v0.1/capture-manifest.json)。脚本包含独立采集及复制本次测试截图，原型源码不因截图改变。文档正文、截图和检查需一起维护；旧`d01-v0.1`／`d01-v0.2`保留历史。
