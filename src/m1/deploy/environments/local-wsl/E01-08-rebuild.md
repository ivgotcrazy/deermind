# E01-08 账号投影重建

> **版本**：v0.3<br>
> **更新日期**：2026-11-22<br>
> **评审状态**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

## 1. 交付范围与职责

`product.account_views.v2` 重建账号 `product.accounts`、监护人 `product.guardian_records`、监护关系 `product.student_guardian_relations`、使用确认 `product.usage_confirmations` 和当前使用条件 `product.usage_conditions`。重建从事件及其固定附件恢复原 ID、修订、时间和来源。当前使用条件取历史中最后一个已保存的快照。旧单表维护结果只证明当时覆盖的范围。

| 实现 | 职责 |
| :--- | :--- |
| [账号投影器](../../../server/src/deermind/product/accounts/projections.py) | 维护 `TrialAccountSaved` 和 `UsageConfirmationRecorded` 两类输入。生产者与维护重建复用同一个转换器 |
| [账号重建](../../../server/src/deermind/product/accounts/rebuild.py) | 生成本批临时副本、独立复核行集合及引用关系，再替换正式投影 |
| [Foundation 事件读取](../../../server/src/deermind/foundation/system/events/query.py) | `scan_scope` 按范围和固定上界逐号检查，只展开目标事件。生成和复核都沿用同一个维护事务查询事件与附件登记 |

任何序号缺失都使本批失败。目标事件须通过类型、版本、正文和附件校验。重建期间遵守原账号范围及外键关系，凭据、文件登记和执行控制由各自的恢复流程处理。当前读接口与业务授权边界见[公共运行设计 §2](../../../../../doc/mvp/m1/engineering/System_Foundation_Design.md#2-全局事件的追加与查询)，账号的重建规则见[产品业务设计 §2.8](../../../../../doc/mvp/m1/engineering/Product_Application_Design.md#28-账号业务投影与维护重建)。

## 2. 维护操作

在维护窗口暂停相关写入。维护包应与目标库的迁移版本匹配。通过受控环境变量配置 `M1_DB_HOST`、`M1_DB_PORT`、`M1_DB_NAME`、`M1_DB_USER`、`M1_DB_PASSWORD`、`M1_FILES_ROOT` 和 `M1_FILES_BACKEND`。数据库账号使用 `deermind_migrator`，文件根目录指向原事实附件存储。命令会获取与迁移共用的维护锁及事件和投影表锁。

每批使用新的重建 UUID 和该投影器尚未使用的大于 1 的代次。每个 `--scope` 指定一个账号 UUID，可重复传入。每批应覆盖所选账号的完整历史及必要关联。共享监护人的来源账号超出范围时，本批失败，需先获准将来源账号纳入重做范围。

```bash
deermind-rebuild run \
  --rebuild-id "$REBUILD_ID" --generation "$GENERATION" \
  --scope "$ACCOUNT_ID" \
  --operator "$OPERATOR" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed

deermind-rebuild status \
  --rebuild-id "$REBUILD_ID" \
  --operator "$OPERATOR" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed
```

每批独立核对。正式投影、在线应用收据、扫描位置及成功记录同事务提交，临时副本随批次完成而清理。失败时回滚本批副本和变更。相同参数重发已结束的批次会返回原结果。

进程中断或提交结果不明时，先用原 UUID、操作人和批准依据查询。`completed` 表示已提交。确认数据库可访问且原事务已结束后，若结果为 `failed` 或确认没有批次记录，修复原因后使用新 UUID 和代次从头重做。`status` 也可查询旧维护记录。

## 3. 验证与限制

| 检查 | 最近一轮结果 |
| :--- | :--- |
| PostgreSQL 回归 | 70 项通过，含 20 项重建、8 项事件读取、4 项使用确认、10 项认证、1 项请求收据、13 项原子保存及 14 项事实附件测试 |
| 本地与工程检查 | 58 项本地测试和 `bash scripts/check.sh` 通过。已核对测试副本与工作区的 21 个变更文件 |

重建用例覆盖五表恢复、批次隔离、同一维护连接、非目标事件缺号、超上界排除、坏附件及失败回滚。读取回归另核对回执的账号和原请求关联，防止同账号的其他请求结果被误读。

本轮在 local-wsl 使用隔离的 PostgreSQL 测试库和合成账号，附件组复验使用 K3s 测试环境的 `deermind-files` PVC。结果适用于本轮核对的源码。该轮未替换运行中的应用镜像，也未重建部署环境的已有账号数据。证据位于 `src/m1/.artifacts/e01-08-business-read-20261122/`。

复验可在 `src/m1` 执行 `bash scripts/check.sh` 和 `bash scripts/test.sh local`。真实数据库测试使用当前源码构建的后端镜像，显式选择目标环境，再运行 `bash scripts/test.sh rebuild`、`bash scripts/test.sh reads` 及所需的回归组。配置见[质量检查说明](../../../quality/README.md)。

## 4. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记单批重建命令、失败重做及验证 |
| v0.2 | 2026-11-22 | 补充现行读取合同与回归结果 |
| v0.3 | 2026-11-22 | 合并交付记录，补齐五表职责、现行读取和最新验证口径 |

业务投影职责见[决策 §120](../../../../../doc/mvp/DECISIONS.md#120-事件与业务投影职责)，分批执行与失败处理见[决策 §124](../../../../../doc/mvp/DECISIONS.md#124-按范围重建及失败重做)，业务授权和逐号扫描见[决策 §125](../../../../../doc/mvp/DECISIONS.md#125-事件读取授权与维护扫描)。各阶段文档及部署记录可查 Git 提交 `fe13cf7` 的合并前版本。
