# E02-11 教材提交领域入库

## 交付范围

- 教材只提交已采用的内容，知识、题目、题内参考分别选择。提交题内参考时核对对应题目。
- Product保存提交及可靠投递安排，Domain按固定事件读取候选并原子生成待办。受理结果交给Product回写。
- 同一请求返回原收据；新请求中再次选择同一已采用内容，领域复用原待办。

## 集群验证

2026-11-22，local-wsl，`e02-11-r1`，Helm revision 34，迁移 `0020_material_intake`。部署实际登记两个JetStream订阅。9项领域回归通过。

真实C03候选已采用后，只勾选题目提交。浏览器显示领域已接收，领域出现一条题目待办且无题内参考。相同请求返回原收据，新请求提交同一候选复用原待办，同批重复选择返回409。

证据在 `src/m1/.artifacts/e02-11-k3s-20261122/browser/`，含教材、领域页面截图和受理结果。入口为 [intake.cjs](../../../tests/browser/materials/intake.cjs)。

2026-11-23 复验 C02。先只提交并保存题目。单独提交参考时漏选父题返回 400。补给已入库的父题后，两条参考各自形成待办。验收入口为 [representative-intake.cjs](../../../tests/browser/materials/representative-intake.cjs)。
