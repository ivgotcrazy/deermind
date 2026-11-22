# 编程检查工具

规则见[编程规范](../../../doc/mvp/m1/engineering/Coding_Standard.md)。这里仅包含开发检查依赖，没有应用、页面或服务入口。

## 工具与安装

| 工具 | 固定版本/位置 |
| :--- | :--- |
| Node / npm | 24.22.3 / 11.19.1，E01-03同时用于正式客户端构建 |
| Ruff / yamllint | 0.17.5 / 1.38.0；Python直接和传递依赖见`requirements.txt` |
| ShellCheck / shfmt | 0.9.0 / 3.8.0；本次Ubuntu包分别为`0.9.0-1`、`3.8.0-1` |
| Pyright、ESLint、Prettier、Vue/TS检查依赖 | 精确版本见`package.json`，传递依赖及完整性值见`package-lock.json` |
| Helm与官方Chart | 沿E01-02的组件清单和已核验缓存，不另安装一套 |

在WSL/Linux准备Python 3.12、Node官方Linux包及上述两个Shell工具；Node包须按官方同目录`SHASUMS256.txt`核对。本机安装在`/root/.local/share/deermind-quality/node-v24.22.3-linux-x64/`，没有替换Windows Node。新环境使用自己的用户目录，不修改旧WSL。

```bash
# 在src/m1中执行；PATH中必须是Linux版Node，不能误用Windows npm。
export PATH="$HOME/.local/share/deermind-quality/node-v24.22.3-linux-x64/bin:$PATH"
python3 -m venv "$HOME/.venvs/deermind-quality"
source "$HOME/.venvs/deermind-quality/bin/activate"
python3 -m pip install -r quality/requirements.txt
npm --prefix quality ci --ignore-scripts --no-audit --no-fund
```

Ubuntu 24.04可按上述精确包版本安装ShellCheck/shfmt；其他系统安装对应上游版本。工具升级须改版本文件、重新安装并跑正反测试，不在检查命令中自动下载。网络受阻时仅为安装进程配置用户提供的代理，不把代理或凭据写入项目配置。

## 检查与测试

```bash
bash scripts/check.sh
bash scripts/test.sh local
```

`check.sh`只检查，不修改代码。包含Python/TS/脚本/配置的静态检查与离线Helm渲染；普通格式检查忽略模板、生成物、依赖缓存及历史文档。模板渲染后检查YAML，真实Kubernetes验证仍由组件测试承担。官方Chart缓存默认沿E01-02路径，也可显式传`M1_CHART_CACHE`；缺缓存或工具时报错。

`local`测试使用临时正反样例验证检查器确实能拒绝错误，并运行E01-01本地测试。不会访问集群。E01-03已接入正式后端严格类型和单元测试、客户端Vue/TS检查、实际模块边界检查；集群应用测试须显式选application。

需要显式格式化时，执行对应工具而非绕过检查：

```bash
ruff check scripts tests quality --fix
ruff format scripts tests quality
shfmt -w -i 2 -ci scripts/*.sh
quality/node_modules/.bin/prettier --write '**/*.{json,yaml,yml,mjs,ts,vue}'
```

检查阶段不使用`--fix`。Ruff不自动执行unsafe fixes；使用类型忽略或规则豁免前说明原因。

真实环境验证分别执行，不能仅运行local后声称集群通过：

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
bash scripts/test.sh target

export M1_TEST_NODE=deermind-m1
export M1_CHART_CACHE=/mnt/d/code/deermind/deermind/.tmp/e01-02/charts
bash scripts/test.sh components
```

组件测试会重启三个E01-02测试release，并创建、清理临时材料。不要对试用或生产环境运行。跨环境不改变默认context。

## 本轮自检

本次按编程规范v0.3重新整改，运行编号`readability-20261115`，基线仍为`73e000a`及前轮未提交改动。保留上一轮记录，不用旧结果代替本次验证。证据位于[本机目录](../.artifacts/readability-20261115/)。

| 验证 | 结果 | 证据 |
| :--- | :--- | :--- |
| 静态检查 | 现有源码／配置通过；新增E501行宽检查，最后排版／命名调整另做增量复核，正式应用仍待接入 | `check-final.txt`、`final-delta-check.txt` |
| 检查器正反样例 | 7组通过 | `local-tests.txt` |
| 目标／部署入口 | 本地4项、含真实目标共5项通过；新增预检／lint失败阻止部署及目标参数透传验证 | `target-local.txt`、`target-tests.txt` |
| 真实组件 | 首轮5项中4项通过、NATS握手失败；未改相关逻辑、断言或时限，NATS单项复测通过 | `components.txt`、`nats-recheck.txt` |
| 行为与人工review | 对照本轮修改前源码，核对参数、命令顺序、资源、断言及安全边界；7个相关函数除文档外AST相同 | `before/`、`scoped-review.diff`、`behavior-check.txt` |

NATS首次在创建测试流前未收到预期握手；单项复测通过，但底层原因未确定。保留首次失败，不声称整组首次通过，不扩大时限或移除断言。容量及环境稳定性仍未验收。

逐文件人工review结论：已按下表核对并修正遗留缩写、SQL拼接排版和case展开；未发现本次可读性整改改变既定部署行为。

| 文件／范围 | 人工检查内容 |
| :--- | :--- |
| `check-target.sh` | main入口与只读查询职责分开；参数、本地校验、远端检查、汇总分段；长查询和失败原因可读 |
| `deploy.sh` | 单变量声明、参数与预检分段；解释禁止hooks及独立初始化原因；失败不能进入后续部署 |
| `check.sh`、`test.sh` | 检查阶段有独立职责和说明；本地与真实测试分支明确；不改变既有检查范围 |
| `test_target.py`及fixtures | 替身移到独立类型化文件；保留原断言，补部署预检／lint失败停止和目标参数透传测试；真实故障只修改配置副本 |
| `test_components.py` | 每组验证及辅助函数有契约说明；持久化、鉴权、共享卷分段；注明密码传输、socket短读及清理顺序；资源与断言不减弱 |

本轮不声称正式应用完成、日志封装已实现、100人容量或灾难恢复已验证。E01-01/02仍待用户评审。

## 首轮检查记录

运行编号`coding-standard-20261115`，基线提交`73e000a`上的工作区改动。原始输出保存在[本机证据目录](../.artifacts/coding-standard-20261115/)，不提交依赖缓存、凭据或大文件。

| 验证 | 结果 | 证据文件 |
| :--- | :--- | :--- |
| 现有源码、配置与离线Chart检查 | 通过；正式前后端检查明确为待接入 | `check-final.txt` |
| 检查器正反样例 | 7组通过：Python类型/格式、Vue模板/TS、导入边界、Shell、YAML/JSON、Chart类型、入口拒绝 | `local-tests-final.txt` |
| E01-01本地与真实集群 | 本地3项、含真实目标4项均通过；未跳过真实目标测试 | `local-tests-final.txt`、`target-tests.txt` |
| E01-02真实组件回归 | 整组复测5项通过，包含PG/NATS/Temporal重启持久化、权限、共享卷及错误配置 | `components-recheck.txt` |
| YAML整改前后比较 | 9份已修改配置解析值与HEAD相同；新增Schema单独验证 | `yaml-semantics.txt` |
| 工具与最终环境 | 固定工具版本、组件及PVC状态 | `tool-versions.txt`、`cluster-after.txt` |

首次组件回归中，Temporal启动探测工作流超时；同一时段日志显示PG重启后数据库连接超时。未放宽断言、时限或资源配置，连接恢复后单项复测及整组复测通过。首次失败保留在`component-tests.txt`，单项结果在`temporal-recheck.txt`。这说明本机短暂恢复窗口仍需关注，不能把复测通过当成恢复时延或100人容量已达标。

本轮整改包括函数类型标注、格式和导入、Shell参数校验写法，以及自有Chart的values Schema。没有创建API、Worker或客户端，未推进E01-03；规则样例不代替实际应用验证。E01-01/02保持待用户评审。


## E01-03应用接入

`check.sh`新增server严格类型检查、客户端检查和应用Chart渲染。通用脚本仍使用quality环境；依赖应用包的OpenAPI导出与SDK夹具由server配置检查。`.venv`、产物和锁文件不做通用格式扫描。

`test.sh local`另运行后端单元测试；`test.sh application`要求显式kubeconfig、context、namespace和`M1_APPLICATION_RELEASE`，只验证本轮应用，不重启E01-02基础组件。用例、实测及限制归[应用交付说明](../deploy/environments/local-wsl/E01-03-application.md)。

## E01-04数据库接入

`check.sh`包含迁移脚本的格式、类型和迁移Chart；`test.sh local`增加数据库配置与单一迁移链检查。真实数据库测试显式选择`test.sh database`，使用已构建后端镜像，在临时Pod及随机测试库中验证；所需目标、Secret名称和镜像参数见[数据库交付](../deploy/environments/local-wsl/E01-04-database.md)。不读取密码到工具输出，不清空业务库。该段记录E01-04验证边界。

## E01-05事实保存接入

`test.sh facts`复用数据库目标/镜像配置，在随机测试库验证原子保存、并发防重、来源授权与全批回滚；`database`继续验证迁移。server类型检查显式包含源码和数据库测试辅助模块，不依赖已安装包代替源码检查。场景、结果与限制归[交付记录](../deploy/environments/local-wsl/E01-05-facts.md)。

## E01-06文件与附件接入

`test.sh files`沿用数据库目标、Secret与镜像参数，另要求显式`M1_FILES_CLAIM`；随机测试库验证附件外置、完整性、投影一致及失败原子性，实际PVC只创建并清理本用例的UUID文件。部署和结果见[交付记录](../deploy/environments/local-wsl/E01-06-files.md)。本地文件边界用例纳入`test.sh local`。

## E01-07授权查询接入

`test.sh reads`沿用数据库组的目标、Secret和构建镜像参数，在随机 PostgreSQL 测试库及临时文件目录验证范围和请求关联条件、固定上界分页、逐号扫描、片段读取及附件校验。JSON Pointer 单元测试纳入 local 组。最新回归见[读取与重建验证](../deploy/environments/local-wsl/E01-08-rebuild.md#3-验证与限制)。

## E01-08受控重建接入

`test.sh rebuild`沿用数据库目标、Secret及镜像配置，在随机测试库验证分批隔离、逐号扫描、原子发布、中断回滚和失败后重做。独立进程验证维护 CLI，覆盖普通应用身份、正在写入及并发维护时的拒绝。结果见[重建验证](../deploy/environments/local-wsl/E01-08-rebuild.md#3-验证与限制)。

## E01-09认证与生成类型接入

`test.sh auth`沿用数据库组的显式目标、Secret及镜像参数，在随机测试库验证登录、并发限制、限流、会话、事实原子性及认证审计重建。`test.sh application`另要求`M1_AUTH_TEST_ORIGIN`，核对实际代理的认证路径及2MiB拒绝；本机使用`http://127.0.0.1:5184`。

修改HTTP合同后，先用`server/.venv/bin/python scripts/export-openapi.py`导出，再在clients执行`npm run generate:api`。`check.sh`核对导出与生成类型无漂移，不手改生成文件。生成工具仅参与开发/构建，不增加运行服务。浏览器夹具、结果及人工review见[登录交付](../deploy/environments/local-wsl/E01-09-auth.md)。

## E01-10账号使用验证

`test.sh usage`沿用数据库组显式目标和镜像，在隔离测试库验证开户、确认、防重、权限、资料更新及密码恢复；包含真实终端管理命令，密码不进入argv。浏览器夹具为`tests/migrations/usage_browser.py`，只使用合成账号。结果见[E01-10交付](../deploy/environments/local-wsl/E01-10-account-usage.md)。

## E01-11公共收据与接口验证

`test.sh receipts`使用相同显式集群、Secret和构建镜像参数，在随机数据库验证原请求查询、不重新写入、同键冲突及身份隔离。API错误与响应合同用例进入local组；浏览器通过真实API故障注入验证回执丢失和原请求重试。公共收据只注册已实现的本人使用确认；不测试尚未接入的后台受理或WebSocket。结果见[E01-11交付](../deploy/environments/local-wsl/E01-11-request-receipts.md)。

## E01-12事件交接验证

`test.sh delivery`沿用数据库组参数，另需`M1_TEST_NATS_ADDRESS`和`M1_MESSAGING_SECRET`。临时测试Pod通过Secret取得维护密码；每例只创建并删除随机测试库、消息流。验证提交回滚、重复承接、PubAck丢失、承接后未Ack、订阅缺失、重投耗尽、拒绝及受控重送。`test.sh local`包含通知Schema、登记边界、凭据及日志检查；应用凭据的管理禁止项另做实际集群验证。结果及边界见[E01-12交付](../deploy/environments/local-wsl/E01-12-event-delivery.md)。

## E01-13执行恢复验证

`test.sh execution`沿用数据库组的显式目标、Secret和构建镜像参数，另需`M1_TEST_TEMPORAL_ADDRESS`和`M1_TEST_TEMPORAL_NAMESPACE`。每例使用随机测试库和独立测试队列；Worker子进程可强制终止，不重启正式Worker。覆盖启动回执丢失、稳定Step、停止迟到、失败恢复、结束核对及服务不可用；测试结束清理本例资源。结果见[E01-13交付](../deploy/environments/local-wsl/E01-13-execution.md)。

## E01-14等待接续验证

`test.sh waits`沿用execution组的显式集群、Secret、构建镜像及Temporal参数，在随机库和独立队列验证结果原子保存、早到/重复/迟到通知、到期补查、恢复不续期、接续并发和Worker重启。等待的业务条件由隔离所有者适配器提供，不调用模型或正式教学。结果见[E01-14交付](../deploy/environments/local-wsl/E01-14-waits.md)。

## E01-15受控模型验证

`test.sh ai`沿用execution组的显式集群、镜像和Temporal参数，使用随机数据库和独立Worker队列；默认全部使用模型替身，真实调用用例明确跳过。真实测试须显式设置`M1_LIVE_AI=1`、模型环境变量和`M1_AI_EVIDENCE_DIR`，只运行`test_ai_live.py`；累计账本不得删除或重置，超出批准额度停止。结果见[E01-15交付](../deploy/environments/local-wsl/E01-15-ai.md)。

## E01-16 Temporal 载荷外置验证

`bash scripts/test.sh payload` 沿用数据库组的显式目标、Secret 名称及镜像参数，并要求 `M1_TEST_TEMPORAL_ADDRESS`、`M1_TEST_TEMPORAL_NAMESPACE` 和 `M1_FILES_CLAIM`。场景在临时测试 Pod、随机库、隔离任务队列及 PVC 独立测试目录执行，合成模型返回走官方 Pydantic AI Temporal 集成。重启用例替换测试 Worker 进程。内存用例分别记录客户端及 Worker 进程的峰值 RSS。验收与证据见[E01-16 交付记录](../deploy/environments/local-wsl/E01-16-payload-codec.md#2-复核与证据)。

## E02-03 领域与知识成分验证

`bash scripts/test.sh domain` 使用数据库组的显式集群、Secret 和已构建镜像，在随机测试库核对领域根回归、知识成分并发修订、分页续读、软删除与原收据。浏览器用例通过现有管理端入口验证真实保存和内容展示。
