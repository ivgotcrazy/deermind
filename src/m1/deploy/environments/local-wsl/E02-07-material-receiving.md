# E02-07 教材原件登记

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

管理端「教材管理」支持选领域、登记 PDF／PNG／JPEG、搜索教材、补充原件、查看文件内页数和下载。补充只推进原件清单修订，旧文件及页身份保留。上传阶段生成文件收据，登记阶段原子保存教材投影、MaterialReceived 和业务收据。

普通 JSON 正文上限 2 MiB。教材文件使用二进制流，PDF 最多 512 MiB、600 页，PNG／JPEG 单份最多 32 MiB、4000 万像素。单批最多 600 份、2 GiB。PDFium 和 Pillow 做格式核验，受损原件按文件报错。模型处理由后续教材助手入口发起。

接口见 [P04、P05、P08](../../../../../doc/mvp/m1/engineering/contracts/Product_API.md#p04)及 [R01—R04、R07](../../../../../doc/mvp/m1/engineering/contracts/Runtime_Protocols.md#r01)。

## 2. 集群验证

原 `deermind-m1` K3s，应用 Helm revision 30，迁移 `0016_material_receiving`。部署镜像为 `deermind/server:e02-07-r1` 和 `deermind/client:e02-07-r1`。首轮发布中代理正则因缺引号导致前端进程启动失败，修正配置后同一环境恢复，API、Worker 和客户端均就绪。

| 检查 | 实测结果 |
| :--- | :--- |
| 类型和整批登记 | 双页 PDF 超过 2 MiB，登记成功；同批损坏 PDF 单独被拒；缺领域的登记被拒 |
| 原请求恢复 | 故意丢弃保存响应，页面补读原收据；重复提交返回相同教材、导入和来源 |
| 补充及回读 | PNG 作为第二份原件，共用教材与导入；旧来源保留，下载 PDF 字节一致；错配来源与文件时返回404 |
| 既有领域回归 | 集群 PostgreSQL 上 9 项通过，KC、题目、解法及版本不受迁移影响 |

证据位于 `src/m1/.artifacts/e02-07-k3s-20261122/`，其中 `browser/run.txt` 和 `browser/textbook-sources.png` 对应浏览器走查。测试使用合成原页。

## 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记教材原件上传、页序、原收据及集群验证 |
