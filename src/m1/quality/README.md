# 编程检查工具

规则见[编程规范](../../../doc/mvp/m1/engineering/Coding_Standard.md)。这里仅包含开发检查依赖，没有应用、页面或服务入口。

## 工具与安装

| 工具 | 固定版本/位置 |
| :--- | :--- |
| Node / npm | 24.22.3 / 11.19.1，仅作为检查工具运行环境 |
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

`local`测试使用临时正反样例验证检查器确实能拒绝错误，并运行E01-01本地测试。不会访问集群。前端只验证规则和样例，未创建正式客户端；真实前后端源码建立后再接入相应构建、类型和依赖测试。

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
