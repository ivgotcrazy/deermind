# E01-07 事实授权查询

[环境目录](README.md) · [实施计划 E01](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

> 2026-11-17源码位置已按[独立抽象整改](E01-15-boundaries.md)迁移。下文保留本增量当时的路径、命令和验证事实；当前归属见整改清单。

## 1. 交付范围

提供三个内部读取能力：按条件查事件列表、按范围连续扫描、按EventPartRef读取获准正文。沿用现有事件表及文件登记，不新增表、迁移、依赖或浏览器入口。

| 内容 | 实现位置 |
| :--- | :--- |
| 受信上下文、用途、所有者字段许可、JSON Pointer | `foundation/system/events/reading.py` |
| 范围查询、签名游标、连续扫描及附件解引用 | `foundation/system/events/query.py` |
| 已实现账号及文件的维护许可 | `product/accounts/facts.py`、`infrastructure/files/records.py` |
| 正式登记汇总 | `bootstrap/events.py` |
| 指针规则与真实PG授权反例 | `server/tests/test_event_pointers.py`、`tests/migrations/test_event_reads.py` |

限额引用[基础设施§4.5](../../../../../doc/mvp/m1/engineering/Infrastructure_and_Deployment_Design.md#45-首轮入口与执行参数建议)H02/F01。本次确认默认50条、最多100条、响应最多4MiB、单次完整事实正文读取累计最多32MiB；超限明确失败，不截断。读取同一正文多次也累计，不能用大量小片段绕过预算。PDF大小不受事实读取预算限制。

## 2. 读取边界

1. 服务端提供已核验身份、处理器、授权依据、范围及必要来源集合；不把客户端传入的purpose作为授权。底座核对登记关系，所有者决定可读事件、记录和顶层字段。
2. 列表只返回固定摘要及授权元数据。游标绑定身份、授权、范围、筛选和首轮已提交上界，并校验签名；新事件留下一次查询。隐藏事件可能形成空页，调用方继续跟随next_cursor。内部连续扫描另返回已检查序号，不能拿最后匹配事件代替进度。
3. 精确读取先检查事件、记录及字段，之后才读取文件。`record_id=null`不能读取records；根路径裁剪私有字段，返回visibility。非法路径、无权、缺失附件、hash不符分别失败；获准字段缺失返回明确incomplete，不与权限裁剪混淆。
4. 文件必须匹配事件ID＋record_id的产物身份、类别、媒体类型和hash；读取时再核对长度、hash、规范编码与固定DTO Schema。后续引用不自动展开，每一跳重新授权。
5. 查询不追加事件、不改投影或加工进度。任一步失败不返回可推进的扫描结果；失败后缩小范围可重读原事实。

当前正式装配只开放初始账号和文件的授权维护读取；学生历史、Evaluation取证等用隔离夹具验证机制，尚未接入真实业务及登录。读取上下文是内部受信合同，不能直接从HTTP反序列化。签名密钥由装配层显式注入，至少32字节；测试密钥只在测试文件中，实际入口接入时统一使用服务配置，不自动生成每进程不同密钥。

## 3. 复核与部署

在WSL的`src/m1`执行。镜像使用本次构建包，未挂载源码；构建方式沿[E01-03](E01-03-application.md#2-安装检查与构建)。

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_POSTGRES_RELEASE=deermind-postgres M1_DATABASE_SECRET=deermind-postgres
export M1_TEST_NODE=deermind-m1 M1_DATABASE_TEST_IMAGE=deermind/server:e01-07-r1
export M1_FILES_CLAIM=deermind-files

bash scripts/check.sh
bash scripts/test.sh local
bash scripts/test.sh reads
bash scripts/test.sh facts
bash scripts/test.sh files
bash scripts/deploy.sh --kubeconfig "$M1_KUBECONFIG" \
  --context "$M1_CONTEXT" --namespace "$M1_NAMESPACE" --release deermind-app \
  --chart deploy/helm/application --values deploy/environments/local-wsl/application.values.yaml
M1_APPLICATION_RELEASE=deermind-app bash scripts/test.sh application
```

真实PG测试只写随机测试库，文件放临时目录；files回归仅用UUID文件验证既有PVC。测试结束清理本次资源，不写部署库业务数据。本轮没有数据库迁移。部署后API/Worker使用`deermind/server:e01-07-r1`，应用release第9版，数据库仍为`0003_file_objects`；部署库事件、文件和账号均为0，测试库/Pod已清理，BuildKit未运行。

## 4. 验证及人工检查

证据目录：`.artifacts/e01-07-20261116/`。用户评审通过才标记增量完成。

| 验证 | 结果 | 证据 |
| :--- | :--- | :--- |
| 静态、严格类型、导入边界和离线Chart | 通过 | `check-final.txt` |
| 本地完整测试组 | 7项规范样例＋4项目标入口＋20项后端单元测试通过 | `local-final.txt` |
| 授权查询及正文读取，真实PG | 12项通过，含正式账号/文件维护、跨空间与用途拒绝、私有字段、引用跳转、分页、扫描、附件损坏及大小限制 | `reads-final.txt` |
| 原子保存回归 | 13项通过 | `facts-final.txt` |
| 文件及附件回归 | 14项通过 | `files-final.txt` |
| 部署后应用 | 5项通过 | `application-final.txt`、`deploy-final.txt` |
| 构建包与源码 | 29份Python源码/迁移逐字节一致 | `package-source.txt` |
| 部署数据与资源清理 | 版本不变、无业务测试数据和测试库，构建器已停止 | `cluster-final.txt` |
| 文档文件链接及修订版本 | 692处链接无缺失，当前版本均有修订记录 | `documentation-check.txt` |

本轮共75项测试通过，静态检查另计；没有重新运行未受影响的数据库迁移组。

人工检查重点：私有字段拒绝发生在文件读取前；动作payload不能绕过records授权；列表不透传原始信封；游标不能换身份或筛选后复用；空匹配页不漏扫描区间；文件损坏不能伪装为空；大小按UTF-8字节而非字符数；无新DDL或依赖。

| 人工review范围 | 核对结论 |
| :--- | :--- |
| reading/query | 授权与解包顺序、指针转义、固定分页上界、连续扫描进度及失败路径已核对；内部受信上下文不能冒充登录授权 |
| 所有者登记与bootstrap | 只装配两类已实现事实的维护读取；无公开账号敏感正文或未登记payload回退 |
| 测试与脚本 | 正常、越权、损坏和超限断言齐全；测试夹具独立，数据库/文件清理限本次创建资源 |
| 文档与部署 | 限额、版本、实现边界和进度已对照；部署包与源码一致，旧迁移未改 |

## 5. 限制与下一步

本轮验证内部机制，不代表学生业务、管理员事件页面、完整权限系统或100人性能已验收。浏览器身份与入口按E01-09及后续业务接线；公开页面不应直接使用维护处理器。事实重建属于E01-08，本轮未推进。
