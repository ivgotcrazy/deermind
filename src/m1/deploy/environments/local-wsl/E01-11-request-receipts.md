# E01-11 公共收据与接口合同

[环境目录](README.md) · [实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 交付范围

新增统一收据查询`GET /api/m1/requests/receipt`，先接入学生本人使用确认。响应丢失后按原动作、账号及request_id查询；底座委托Product读取原收据和事件结果，不重做确认。

- 当前动作：`product.record_usage_confirmation`，资源为`account`；未实现动作拒绝，不占位返回成功。
- `not_found`仅表示当前没有可读收据；数据库故障返回错误，不能伪装成没有提交。
- 确认已保存后返回原结果。随后接受或拒绝的新决定不会改变旧请求结果；查询不新增事件。
- 页面不自动重发写请求。结果不明时保留当前页面的原编号及正文，允许查询或明确重试；切换身份销毁旧页面状态。
- 统一HTTP错误外壳，保留安全错误码，不回显密码、校验输入、SQL或内部异常。OpenAPI由代码导出，客户端请求类型引用生成合同。

本项不新增表、不接模型、不改变账号规则，不实现E01-12的事件投递或E01-13的后台工作。管理员命令仍采用既有收据，不开放网页遍历入口。

## 2. 代码与职责

| 位置（相对src/m1） | 职责 |
| :--- | :--- |
| `server/src/deermind/foundation/system/public/receipts.py` | 只读查询和结果外壳；业务result采用泛型 |
| `server/src/deermind/foundation/system/requests.py` | 按已登记动作与资源委托所有者，不访问业务私表 |
| `server/src/deermind/product/accounts/usage.py` | 当前身份复核、精确查原收据、授权读取原事件；POST重试与GET共享结果读取 |
| `server/src/deermind/entrypoints/api/receipts.py` | Cookie/预期会话核对及公开响应合同 |
| `foundation/system/public/errors.py`、`entrypoints/api/errors.py` | 共同错误定义及HTTP适配（均位于server/src/deermind） |
| `clients/src/shared/api/http.ts` | 基于生成paths的类型化请求、共同错误、拒绝未声明成功状态；无自动重试 |
| `clients/src/shared/auth/UsageConfirmation.vue` | 原请求补读、显式重试和身份销毁 |
| `server/tests/test_api_contract.py`、`tests/migrations/test_receipts.py` | 错误/响应合同、真实PG原结果和权限验证 |

## 3. 部署与验证

运行`e01-11-20261116`，基线提交`3cab6ab`，本轮工作区修改待评审。证据保存在[运行目录](../../../.artifacts/e01-11-20261116/)。本机应用release第14版，镜像`deermind/server:e01-11-r1`和`deermind/client:e01-11-r1`；数据库仍为0006、16张表，未执行新迁移。Pod镜像摘要、就绪状态和正式库核对见`cluster.txt`。

| 检查 | 结果 | 证据 |
| :--- | :--- | :--- |
| 收据真实PG场景 | 1个综合用例通过：原结果、防重、同键冲突、越权、失效会话、不新增事实 | `receipts-package-tests.txt` |
| 账号确认、登录、事实授权读取回归 | 4＋10＋12项通过 | `usage/auth/reads-package-tests.txt` |
| API及纯逻辑、本地工具、目标参数 | 33＋7＋4项通过 | `local-tests.txt`、`unit-tests-final.txt` |
| 实际部署与共享卷 | 5项通过 | `application-tests.txt`、`deploy.txt` |
| 格式、类型、模块边界、生成物和Chart | 通过 | `check-final.txt` |
| 浏览器故障注入 | 未送达、保存后丢响应、查询暂时503、未声明202、原编号重试、409冲突、403/404隔离全部通过 | `browser-review.js`、`browser-review.txt` |

浏览器使用真实API、随机测试库和合成账号，只在网络层注入故障。截图：[结果不明时查询或原请求重试](../../../.artifacts/e01-11-20261116/unknown.png)、[查回结果](../../../.artifacts/e01-11-20261116/recovered.png)。正式库账号与事件仍为0，测试库已清理。

静态检查和本地工具测试在WSL原生目录执行，避免Windows挂载盘影响工具运行。163份代码、配置及生成合同逐字节一致，沿用原锁定依赖；对照见`quality-copy-match.txt`、`quality-source-hashes.json`。首次检查发现格式和类型问题，修正后完整重跑；未跳过规则。

## 4. 复核入口

沿[E01-09](E01-09-auth.md)设置显式集群、数据库Secret、测试节点等参数，镜像使用本轮版本：

```bash
export M1_DATABASE_TEST_IMAGE=deermind/server:e01-11-r1
bash scripts/test.sh receipts
bash scripts/test.sh usage
bash scripts/test.sh auth
bash scripts/test.sh reads
bash scripts/check.sh
bash scripts/test.sh local
```

合同变更后执行`server/.venv/bin/python scripts/export-openapi.py`和`npm --prefix clients run generate:api`；`check.sh`检查生成物无漂移。浏览器继续使用`tests/migrations/usage_browser.py`，不需要建立正式测试账号。

## 5. 人工review与限制

- 检查了API→底座登记→Product→事件读取的完整路径，底座没有越权查询Product表；原请求人的身份来自服务端，不接受客户端principal。
- 保存和补读共享原结果读取，没有再存一份可漂移的result；同步事务不伪造accepted或Execution。
- 公共错误替代认证层内重复定义；错误日志沿统一格式记录类别和栈位置，不输出参数。响应合同错误统一500，不能流出非法业务正文。
- 客户端保留原写身份，查询不触发写入；登录不保存密码收据，退出和身份刷新仍走原会话机制。
- 页面布局和提示已目视核对。当前只验证同步使用确认，其他业务、后台失败收据、WebSocket补读和100人容量随所属增量验证。

未新增依赖，未修改历史原型，未推进E01-12。待用户评审通过后才标记完成。

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-16 | E01-11公共收据、统一错误、类型化客户端及验证记录 |
