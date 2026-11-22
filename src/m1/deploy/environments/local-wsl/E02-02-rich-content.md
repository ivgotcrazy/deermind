# E02-02 统一内容结构

> **版本**：v0.1<br>
> **更新日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#14-e02内容与建模)

## 1. 交付

从公开模型生成 [RichContent Schema](../../../contracts/generated/content/rich-content.schema.json) 和 OpenAPI。定义包含有序内容块、共用数据表及固定来源。程序继续核对块和列引用、用途、单位、空值、公式参数及几何关系。

管理员通过 D02 新建领域时可以随定义保存说明和覆盖范围。D04 读取相同版本的事件正文，在领域详情中展示。保存沿用首版事件、投影和回执事务，大正文使用已有事实附件。已有领域的空字段仍可读取。详见[领域 API](../../../../../doc/mvp/m1/engineering/contracts/Domain_API.md)。

Vue 共用组件以文本、MathML、HTML 表格和 SVG 展示。数值单位和原书写标记随正文保留，缺失数据明确标示。来源页码与输入中的关系依据一并保留。

## 2. 集群验证

使用同一 `deermind-m1` K3s 环境和 [管理端入口](http://127.0.0.1:5184/admin/)。生产接口复验领域正文、旧领域和原请求回执。四例保留原用途，在集群测试库和 PVC 中保存后重读，交给已部署的页面组件核对展示。

| 部署项 | 实际版本 |
| :--- | :--- |
| 后端镜像 | `deermind/server:e02-02-r1`，manifest `sha256:b32938428700f3aed7b016519f1abd913298e70c6fc17c5c084867fd49309875` |
| 前端镜像 | `deermind/client:e02-02-r1`，manifest `sha256:7b17717495d4be7bb33902ba48836acfdefcc43c6009229fa250aacef5ae4c9a` |
| Helm 与数据库 | `deermind-app` revision 23，API、Worker 和前端均已就绪。沿用 `0012_domain_roots` |

带正文的新领域需要支持 RichContent 的服务镜像读取。回退应用时须考虑新版本已写入的正文，原事件和附件继续保留。

| 样例 | 核对项 |
| :--- | :--- |
| C02 | 题面、两份解法及教学辅助分别保存，保留分数、括号、约分标记和答句空白 |
| C03 | 保留原错误算式和书上写出的结果 |
| C05 | 柱状、折线、扇形图按给定列读取数据，保留单位和小数位，区分缺值和零 |
| C06 | 展示六种几何形状及可见点，保留关系依据，原附页缺口有明确提示 |

正式领域 `E02-02 验收 20261122-a1` 可在管理端读取。数据库已核对说明、范围、首版事件及原请求回执对应同一记录。37,071 字节的事实附件位于 PVC，登记哈希与事件引用一致。非法公式返回可定位的 400 且无写入回执。旧 E02-01 领域详情可读，使用原编号重发纯名称新建请求仍返回原 v1 和收据。

四例共 9 份正文通过真实存取，错误属主、损坏和缺失的附件拒绝读取。Chromium 使用已部署的客户端验证 9 份回读正文，以及无数据时保留真实缺值的图表退化和 390px 窄屏显示。真实教材来源和授权原页读取随教材流程接入。

本地回归 76 项、编程规范及生成合同核对通过。运行证据在 `src/m1/.artifacts/e02-02-k3s-20261122/`。部署、存储、来源、事实及旧请求记录为 `deploy.txt`、`content-storage.txt`、`source-fixtures-check.txt`、`fact-check.txt` 和 `old-replay.txt`。浏览器断言和全页截图位于 `browser/`。

## 3. 复验

在 `src/m1` 执行。设置[数据库测试](E01-04-database.md#3-验证与自检)使用的显式目标、镜像、节点和 Secret 名称，另传本机文件卷名称。测试只使用本轮临时库及卷中的独立目录。

```bash
bash scripts/check.sh
bash scripts/test.sh local
M1_FILES_CLAIM=deermind-files \
  M1_TEST_CONTENT_OUTPUT=.artifacts/e02-02-k3s-20261122/restored-content.json \
  bash scripts/test.sh content
```

用已部署的管理端复验。浏览器用例读取集群回读结果，需要设置测试账号 `M1_TEST_DOMAIN_LOGIN/PASSWORD`。每轮用独立验收名称，同一名称重跑复用原请求。

```bash
M1_TEST_DOMAIN_ORIGIN=http://127.0.0.1:5184 \
  M1_TEST_RICH_DOMAIN_NAME='E02-02 验收 20261122-a1' \
  M1_TEST_CONTENT_OUTPUT=.artifacts/e02-02-k3s-20261122/restored-content.json \
  node tests/browser/domain/rich-content.cjs
```

## 4. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记统一内容结构、领域正式接入及四例验收 |
