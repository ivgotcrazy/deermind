# E01-09 登录与身份隔离

[环境目录](README.md) · [实施计划 E01](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 交付范围

学生和管理员共用真实登录API、Cookie会话和退出入口。页面刷新向服务端恢复身份；同浏览器账号切换时清空旧内容，丢弃旧响应。当前只开放登录框架，正式账号维护、首次使用确认和找回入口留E01-10。

| 内容 | 实现位置（相对src/m1） |
| :--- | :--- |
| 认证公开合同与环境校验 | `server/src/deermind/product/public/` |
| 密码验证、限流、会话及原子事实 | `server/src/deermind/product/accounts/auth.py`、`auth_facts.py` |
| HTTP、Cookie、同源及正文上限 | `server/src/deermind/entrypoints/api/auth.py`、`body_limit.py` |
| 依赖装配 | `server/src/deermind/bootstrap/authentication.py` |
| 共享登录及身份隔离 | `clients/src/shared/auth/` |
| OpenAPI及生成类型 | `contracts/generated/http/openapi.json`、`schema.d.ts` |
| 认证三表 | `server/migrations/versions/0005_auth_sessions.py` |
| 真实数据库与浏览器夹具 | `tests/migrations/test_authentication.py`、`auth_browser.py` |

参数与决策见[登记§116](../../../../../doc/mvp/DECISIONS.md#116-e01-09登录与身份隔离)；表字段见[Product数据字典](../../../../../doc/mvp/m1/engineering/database/Business_Product.md)。新增login_attempts为已确认的控制表，没有新增AI Operation。

## 2. 关键边界

- 密码验证在事务外；校验完成后锁定账号事件头、重查凭据修订，再共同保存会话与登录事实。换账号同时撤销本浏览器旧会话；其他浏览器不受影响。
- 限流检查和占位在数据库中原子完成，重启不清零。未完成校验暂占名额；服务故障不计作密码错误，密码错误和未知账号返回同一提示。
- 登录秘密只放HttpOnly Cookie，数据库只存token摘要。事件和普通日志不记录密码、token、密码散列或CSRF值。凭据、会话与限流是控制数据，不从事件重建。
- 本机精确允许localhost/127.0.0.1:5184，使用开发Cookie；其他环境采用HTTPS与Secure Cookie。来源IP只信任配置的代理，代理覆盖来源头。
- 2MiB上限在代理和API的JSON解析前检查。API同时检查实际分块长度，超限拒绝且不截断。账号/密码另检查各自长度。
- 标签页只广播身份变化信号；重新取身份前清空旧视图。写请求不自动重发；失败后查询服务端会话。后台工作不随退出登录取消。

## 3. 部署与复核

本轮基于`197de27`的工作区改动，运行编号`e01-09-20261116`；不代表已提交Git或已通过用户评审。应用Helm revision 11；API、Worker、客户端均指定`e01-09-r4`。数据库head为`0005_auth_sessions`，实际12张表；114张是规划总数。正式库账号、凭据、会话及事件均为0。

部署先停止API/Worker写入，运行独立迁移Job，再升级应用。迁移不创建默认账号或密码。三个应用Pod就绪；本轮未重装基础组件。

在WSL的`src/m1`目录复核认证和应用接线：

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-09-r4
export M1_APPLICATION_RELEASE=deermind-app
export M1_AUTH_TEST_ORIGIN=http://127.0.0.1:5184
bash scripts/test.sh auth
bash scripts/test.sh application
```

浏览正式登录页：

```bash
kubectl --kubeconfig=/root/.kube/deermind-m1.yaml --context=deermind-m1 \
  -n deermind-m1 port-forward --address=127.0.0.1 svc/deermind-app-client 5184:8080
```

打开`http://127.0.0.1:5184/admin/`或`/student/`。当前无正式账号，不能用测试密码登录业务库。完整登录走查使用`auth_browser.py`建立随机测试库、两个合成管理员和真实API，服务只监听127.0.0.1:5185；退出后删除该测试库。夹具需要与数据库测试相同的受控环境变量，禁止指向业务库或真实学生数据。

OpenAPI由实际FastAPI代码导出，再由openapi-typescript 7.13.0生成TS类型。修改合同后执行：

```bash
server/.venv/bin/python scripts/export-openapi.py
npm --prefix clients run generate:api
bash scripts/check.sh
```

## 4. 验证与证据

本机证据保存在[本轮目录](../../../.artifacts/e01-09-20261116/)，不提交依赖缓存、密码和大产物。

| 验证 | 结果与证据 |
| :--- | :--- |
| 静态检查、类型与生成物 | `check-final.txt`及最终`check-delivery.txt`均通过 |
| 本地单元及工具回归 | 最终工具7项、目标4项、后端27项全部通过；`local-delivery.txt`，保留此前输出 |
| 真实PG认证 | 10项通过：登录/切换/退出、限流与重启、会话过期、凭据变化、并发上限、失败回滚、来源与Cookie、重建不恢复登录、其他浏览器会话保留；`auth-final-tests.txt` |
| 已交付数据能力回归 | 迁移8、原子事实13、文件14、读取12、重建13项通过；`*-package-tests.txt`。这些回归使用r2包；最终r4补充认证及应用测试 |
| 实际应用部署 | 5项通过：启动拒绝、Chart配置、双入口/代理/正文上限、SDK注册、Worker与共享卷；`application-final-tests.txt` |
| 浏览器走查 | 错密码、刷新恢复、角色入口、两标签换账号、旧响应迟到、断网恢复和退出通过；`browser-review.txt`、`browser-race.txt`、`browser-final.txt` |
| 窄视口与截图 | 390px无横向溢出；`browser/e01-09-login-narrow.png`，实际部署登录页`browser/e01-09-deployed-login.png` |
| 部署及数据库核对 | `deploy.txt`、`cluster-final.txt`；镜像、12张表、head及正式库空记录一致 |

浏览器401与断网错误是对应场景的预期网络结果，不计为JavaScript运行失败。首次类型检查发现BroadcastChannel能力判断导致TS错误，已修复；保留原失败输出。未声称真实用户容量、远程HTTPS部署或完整账号维护已验收。

## 5. 人工review

| 范围 | 核对结论 |
| :--- | :--- |
| 认证/限流 | 并发占位和锁序明确；密码散列不占数据库事务；会话与安全事实同成同败；失败不保留半份登录 |
| HTTP/日志 | 密码及校验输入不反射；代理不信任客户端伪造IP；两层正文限制一致；日志保留定位信息且不输出异常参数 |
| 客户端 | 只使用生成类型；Cookie不交给JS；迟到的成功和错误响应均检查身份代次；恢复连接清除旧提示 |
| 迁移/重建 | 应用不可修改密码散列或表结构；认证审计可扫描但不产生账号副本，原凭据和会话不由重建恢复 |
| 部署/文档 | 使用显式集群和独立迁移；数据库字典、参数确认、生成合同及计划同步，正式账号留E01-10 |

当前提交用户评审，进度只在实施计划维护。

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-16 | E01-09登录、身份隔离、生成类型及部署验证记录 |
