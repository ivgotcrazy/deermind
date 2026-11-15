# E01-05 事件、生产者投影与请求收据

本增量实现数据库内部保存闭环，待用户评审。E01-06附件、E01-07查询、E01-11收据API、E01-12发布订阅不在本批范围。

## 1. 交付范围

| 交付 | 位置与边界 |
| :--- | :--- |
| 事件登记、整批校验和范围序号 | `foundation/system/events/`；底座不导入业务模块，不接受客户端指定投影器 |
| 首个生产者及投影 | `product/accounts/`；接线既定`TrialAccountSaved`的`bootstrap_admin`子集，完整账号正文生成账号投影 |
| 普通命令收据 | `product/persistence/receipts.py`；唯一请求键、同键异文拒绝、结果一次落定 |
| 装配 | `bootstrap/events.py`；只登记已实施事件；其他类型/版本明确拒绝 |
| 迁移 | `0002_atomic_facts`；新增5张表，不修改首个迁移，不触碰Temporal内部库 |

五张表为`runtime.events`、`runtime.scope_event_heads`、`runtime.projection_receipts`、`product.accounts`、`product.command_receipt`。字段分别沿[Runtime分册](../../../../../doc/mvp/m1/engineering/database/Business_Runtime.md)和[Product分册](../../../../../doc/mvp/m1/engineering/database/Business_Product.md)，这里不复制字段字典。

账号样例用于接通真实生产者，不新增账号HTTP入口、不写密码、不建立登录能力；测试账号只存在于随机测试库。`AccountFact`保留既定v1字段，生产处理器暂只接受初始管理员事实。其他账号动作仍由E01-09补齐；不能把本次交付理解为74类事件均已实现。

## 2. 保存与失败处理

1. 受信调用方提供生产者、调用者身份、获准资源和来源事件集合；浏览器与模型不能直接构造授权上下文。
2. Product在一个短事务中用请求唯一键取得收据；相同输入返回原结果，输入不同拒绝。并发重复请求由唯一约束等待原事务，不再生成第二个业务效果。
3. 校验完整内联正文、记录矩阵、对象身份、来源授权和因果顺序；未知类型/字段、缺记录、错误正文版本均拒绝。
4. 按范围排序锁定序号头，核对`expected_seq`，追加事件。事务内序号分配失败随之回滚；不用PG sequence。
5. 已登记投影器只从正文写账号，随后写投影应用收据，最后完成请求收据；全部提交后返回。

任一步失败，事件、序号头、账号、两种收据一起回滚。未提交请求不留下单独的`accepted`行；原请求可再次提交。事务已提交但响应丢失时，原请求重试返回同一收据。数据库异常向调用方抛出，不伪装成功；入口层的统一错误响应属于E01-11。

规范化输入采用键排序、无多余空白的UTF-8 JSON，禁止NaN/Infinity，数组顺序保留；SHA-256与完整规范化输入共同核对。正文不从投影反查，不用当前配置补列。只接线`server_recorded`事实；其他时间依据、附件及授权查询随其增量接线。

本事件没有业务订阅，因此不写待发安排、不访问NATS。应用账号只获事件及投影收据的SELECT/INSERT；不能UPDATE、DELETE或TRUNCATE。在线投影代次固定1，不移动订阅扫描位置；维护重建与扫描去重仍属后续增量。

## 3. 复核与部署

在WSL的`src/m1`执行，沿用已安装工具。按[应用构建](application.md#2-安装检查与构建)启动BuildKit，构建完停止：

```bash
set -e
bash scripts/build-app.sh deermind/server:e01-05-r2 deermind/client:e01-03-r2 \
  .artifacts/e01-05-20261116/images-r2

export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-05-r2

bash scripts/check-target.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE"
k3s ctr images import .artifacts/e01-05-20261116/images-r2/server.tar
bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh facts
bash scripts/test.sh database

bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-db-e0105-r2 \
  --chart deploy/helm/database-migration \
  --values deploy/environments/local-wsl/database-migration.values.yaml
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-app \
  --chart deploy/helm/application --values deploy/environments/local-wsl/application.values.yaml
M1_APPLICATION_RELEASE=deermind-app bash scripts/test.sh application
```

真实数据库测试在临时Pod中使用已构建wheel，不从源码目录导入应用。每例创建随机测试库，结束后只删除本次创建的库和Pod；不修改已有业务数据。部署先迁移再发布应用，单条失败立即停止，不自动清库或降级。再次验证迁移使用新的Job release，保留旧执行记录。

本机已升级到`0002_atomic_facts`，应用release为第7版；API、Worker和客户端均就绪。部署库的事件、账号及请求收据均为0，随机测试库已清理。后端镜像`e01-05-r2`的manifest SHA-256为`21f7546633860a6c29b19c8a160c92a685e2c1f352c4ce4bb82d06ea9022a9fc`；客户端继续使用原镜像。

## 4. 验证与人工检查

证据目录：`.artifacts/e01-05-20261116/`。

| 验证 | 结果 | 证据 |
| :--- | :--- | :--- |
| 源码、类型、配置、前端及Chart静态检查 | 通过 | `check-final.txt` |
| 本地规范样例 | WSL原生临时副本7项通过；原挂载目录仍有工具启动超时 | `quality-native.txt`、`quality-native-source.txt` |
| 部署入口及后端单元测试 | 原工作区4＋12项通过 | `local-remaining.txt` |
| 原子保存真实PG测试 | 13项通过 | `facts-final.txt` |
| 真实PG迁移、权限和启动回归 | 8项通过 | `database-final.txt` |
| 部署后应用冒烟 | 5项通过 | `application-final.txt` |
| 字段与发布包一致性 | 五张表48个字段名称/类型一致；22个Python源文件及迁移文件与wheel逐字节一致 | `schema-review.txt`、`package-source.txt` |
| 迁移及集群状态 | 0001升级至0002；应用就绪，未遗留测试库 | `migration-deploy.txt`、`deploy-final.txt`、`cluster-final.txt` |

原Windows挂载目录的规范样例两次在ESLint加载规则时超过60秒，失败记录保留在`local-initial.txt`和`local-retry.txt`。诊断同一正式页面耗时157.11秒，其中实际lint约0.5秒，见`eslint-existing-file.txt`。未放宽规则或时限；将相同工具、配置和测试复制到WSL原生临时目录后，7项规范样例37.164秒全部通过；源文件逐字节核对，测试后清理临时副本。原目录`test.sh local`整组不能记为通过；本轮拆开完成其全部用例，挂载目录加载性能问题仍保留。

全量`check.sh`已在原工作区通过。初次类型检查暴露测试辅助模块的搜索路径缺失，已显式配置源码与测试路径；最终严格检查零错误。以上验证不构成容量或性能承诺。

人工检查逐项核对：

- 新迁移的字段、约束、索引和表归属与数据库分册一致；未增加未来业务占位表。
- 锁序为请求收据、范围序号头；投影只处理本次新对象，不反向取既有业务锁，不持锁调用外部服务。
- 整批先校验再写入，前因只允许获准的已提交事实或本批较早事实；数据库FK继续验证存在性。
- 重复请求从已提交收据返回；事件、投影收据应用账号不可改删；失败后没有孤立事实、投影或收据。
- 事实DTO与物理表分别维护，不从当前ORM自动生成历史Schema；投影时间和身份来自事实。
- 代码按模块职责分段，函数具备类型及中文约束说明；真实权限测试要求明确权限拒绝，不能用连接故障冒充通过。

未覆盖：全部业务事件、附件、订阅者投影、维护重建、登录授权入口、100人容量和灾难恢复。本批不推进E01-06。
