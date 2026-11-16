# E01-10 最小账号使用

[环境目录](README.md) · [实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 交付范围

受控命令完成初始管理员引导、合成学生开户、姓名/登录标识更新、监护确认和密码恢复。学生登录后在网页查看测试告知、确认本人意愿。缺少监护核实、监护同意或本人意愿时不放行。

本轮只验证合成账号。正式告知及真实数据保留未确认，不启用真实学生；不新增账号管理页面，不推进E01-11。

| 内容 | 实现位置（相对src/m1） |
| :--- | :--- |
| 管理命令 | `server/src/deermind/entrypoints/maintenance/accounts.py` |
| 开户、资料更新、密码恢复 | `server/src/deermind/product/accounts/manage.py` |
| 首次确认及使用条件 | `product/accounts/usage.py`、`conditions.py`（位于server/src/deermind） |
| 测试告知与公开载荷 | `server/src/deermind/product/public/notice.py`、`usage.py` |
| 完整事实及投影 | `product/accounts/facts.py`、`usage_events.py`、`recovery_facts.py` |
| 四张既定表 | `server/migrations/versions/0006_account_usage.py` |
| 学生确认页 | `clients/src/shared/auth/UsageConfirmation.vue` |
| PG与浏览器夹具 | `tests/migrations/test_account_usage.py`、`usage_browser.py` |

## 2. 保存与权限

- 管理命令隐藏输入密码。凭据不出现在命令参数、普通日志、事实或请求收据中；散列在事务外计算。
- 首次管理员仅部署维护账号可创建，固定安装收据保证只引导一次。其他管理操作须再次验证管理员登录；恢复管理员密码仅限部署维护者。
- 所有变更先固定请求收据，再按账号ID顺序锁定账号事件头并复核权限。事实、投影、凭据及收据同成同败。
- 首次确认保存实际决定和当时告知全文。重复请求读取原事件快照，不因后来另一项确认完成而改变原请求结果。
- 学生只能确认本人意愿。网页写入检查同源、CSRF及预期会话，拒绝跨学生和代监护人确认；发生时间由服务端记录。
- 密码重置只更新凭据代次，不改账号ID、历史事实、监护或使用决定。旧会话立即无效；同一请求重试不再次更换密码。
- 资料更新当前只开放姓名和登录标识；复杂监护关系变更与撤回同意未增加入口。既有账号重建支持新资料快照，跳过确认/恢复审计，不恢复秘密或会话；四张新表的维护替换命令不在本次验收范围。

## 3. 管理命令

以下在WSL的`src/m1`执行。先通过显式集群的PG转发连接本机，禁止把生产凭据写在命令参数或文档中：

```bash
kubectl --kubeconfig=/root/.kube/deermind-m1.yaml --context=deermind-m1 \
  -n deermind-m1 port-forward --address=127.0.0.1 svc/deermind-postgres 15432:5432
```

另一个终端设置本次目标。首次引导/恢复管理员使用`deermind_migrator`，其他命令使用`deermind_app`；从受控Secret取得对应密码，隐藏输入：

```bash
export M1_DB_HOST=127.0.0.1 M1_DB_PORT=15432 M1_DB_NAME=deermind
export M1_DB_USER=deermind_migrator
read -rsp '数据库密码：' M1_DB_PASSWORD
export M1_DB_PASSWORD
server/.venv/bin/python -m deermind.entrypoints.maintenance.accounts \
  bootstrap-admin --operator YOUR_OPERATOR --login YOUR_ADMIN --name 管理员
unset M1_DB_PASSWORD
```

这会在显式指定的库创建管理员；交付过程不代填正式账号或密码。再次使用相同输入不会重设管理员密码。后续按上面的方式重新设置应用数据库账号和密码：

```bash
server/.venv/bin/python -m deermind.entrypoints.maintenance.accounts \
  create-student --admin YOUR_ADMIN --request-id REQUEST_UUID \
  --login synthetic-student --name 合成学生 --guardian-name 合成监护人 \
  --verification SYNTHETIC_RECORD_ID --synthetic

server/.venv/bin/python -m deermind.entrypoints.maintenance.accounts \
  record-guardian-consent --admin YOUR_ADMIN --request-id REQUEST_UUID \
  --account-id STUDENT_UUID --expected-revision 1 --decision accepted \
  --verification SYNTHETIC_CONSENT_ID --files-root /ABSOLUTE/EXISTING/FILES

server/.venv/bin/python -m deermind.entrypoints.maintenance.accounts \
  reset-student-password --admin YOUR_ADMIN --request-id REQUEST_UUID \
  --account-id STUDENT_UUID --expected-revision 1 --verification SYNTHETIC_RESET_ID
```

每个新操作使用新的UUID，技术重试沿用原UUID及输入。confirmation的expected-revision取当前使用条件；资料更新/恢复的expected-revision取账号修订。`--files-root`为现有绝对文件目录，用于授权事实读取；当前确认正文内联。命令`--help`列出资料更新和维护恢复参数；密码只能从终端隐藏输入，不支持参数传入。

## 4. 验证与部署

运行编号`e01-10-20261116`，基线提交`7f37f78`，本轮工作区变更待评审。检查、测试和截图保存在[本轮证据](../../../.artifacts/e01-10-20261116/)。

应用镜像为`deermind/server:e01-10-r2`、`deermind/client:e01-10-r2`。数据库迁移到`0006_account_usage`，实际16张表，规划总数仍114张；API、Worker和客户端均已部署。部署及运行镜像摘要见`deploy-r2.txt`、`cluster-r2.txt`。正式库未初始化账号；浏览器使用随机测试库、真实API和合成学生。

| 验证 | 结果 | 证据文件 |
| :--- | :--- | :--- |
| 受控命令、确认、越权、重复及回滚、恢复与资料重建 | 4项通过；确认和恢复事件按合同登记v2 | `usage-r2-tests.txt` |
| 登录认证及数据库/事实/附件/读取/重建回归 | 70项通过：10/8/13/14/12/13 | 对应`*-package-tests.txt` |
| 实际部署启动、代理、安装包、共享卷 | 5项通过 | `application-r2-tests.txt` |
| 本地工具、目标参数、服务端测试 | 7＋4＋30项通过 | `local-native-r2.txt` |
| 格式、类型、模块边界、脚本、Chart、OpenAPI生成物 | 通过 | `check-native-r2.txt` |
| 浏览器 | 拒绝/同意刷新后保留；缺CSRF、伪造监护同意、跨学生均403；390px无横向溢出 | `browser-review.txt` |

截图：[测试告知](../../../.artifacts/e01-10-20261116/notice.png)、[暂不使用](../../../.artifacts/e01-10-20261116/declined-narrow.png)、[确认完成](../../../.artifacts/e01-10-20261116/confirmed.png)。浏览器截图对应相同客户端构建；最后仅修正服务端新增事件版本，并以真实PG用例复验。

WSL读取Windows盘时，工具测试遇到60秒超时；初次并行检查还读到了工具测试的临时反例。保留失败记录，改在WSL原生目录按顺序执行检查和本地测试。155份源码、配置及生成合同逐字节一致，同一锁定依赖、同一规则；对照见`quality-copy-match.txt`和`quality-source-hashes.json`。没有放宽超时或跳过检查。初次回归的文件卷未挂载、旧凭据权限断言问题已分别用真实PVC测试和新授权合同修正。

复核沿E01-09的显式集群参数，将`M1_DATABASE_TEST_IMAGE`设为本轮镜像，执行`bash scripts/test.sh usage`；本地执行`bash scripts/check.sh`、`bash scripts/test.sh local`。浏览器夹具为`tests/migrations/usage_browser.py`，结束后清理随机测试库；不把合成账户写入正式业务库。

## 5. 自检结论与限制

已逐文件检查本轮服务、命令、迁移、API、页面及测试：

- 管理与确认流程分开；函数按校验、锁定、保存和返回组织。密码输入、权限复核、幂等及原子保存均有异常测试。
- 身份来自当前服务端会话；页面不自行推断同意，不在响应丢失时自动重发决定。确认保存告知全文和版本。
- 新增确认/恢复事件使用设计合同v2；既有账号/登录事件版本不改写。正文与事件的版本分别校验。
- 账号重建保留资料变化和既有使用条件，不恢复凭据、旧会话或再次执行开户。四张新表仅完成在线投影，未增加其维护替换命令。
- OpenAPI从FastAPI导出，客户端使用生成类型；未增加普通业务Operation、管理页面或新依赖。

真实学生、实际监护材料、教学业务和100人容量均未验证。正式告知和数据保留规则须另行确认；“退出不取消已受理工作”随后续执行增量验证。本项待用户评审，不推进E01-11。

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-16 | E01-10最小账号、首次确认、恢复及验证记录 |
