# SwDD 重建前的 M1 工程文档归档

> **版本**：v0.1<br>
> **状态**：历史参考，停止在旧工程稿中续写<br>
> **维护与评审**：Codex 归档及核对，用户审阅新规范<br>
> **更新日期**：2026-11-11<br>
> **修订说明**：按用户要求先归档旧稿，再从零建立工程规范和目录稿；见[决定登记](../../DECISIONS.md#32-swdd规范与工程文档重建)。

本次保存旧工程目录的七个文件，包括尚未提交的 v0.3 草案和 v0.10 README。归档前 HEAD 为 `72b4fd97c65ac0b45a7323601f88c07704382022`；HEAD 不包含全部工作区草案，因此另存精确原文。

## 1. 原文与可读副本

- [原文 ZIP](original-engineering.zip)：移动前七个文件的精确字节，保留原文件名、内容和版本。
- [原文清单](original-manifest.json)：原路径、字节数和 SHA-256。校验对象是 ZIP 中原文，不是经过导航调整的可读副本。
- `engineering/`：可阅读的归档副本；仅修正移动后的链接及归档文档头，设计正文保持原样。旧六稿从 v0.3 升至归档副本 v0.4，旧 README 从 v0.10 升至 v0.11，不表示设计进展。

| 旧文档 | 可读归档 |
| --- | --- |
| 工程入口 | [README](engineering/README.md) |
| 总体工程架构 | [Engineering Design](engineering/Engineering_Design.md) |
| Agent 运行框架 | [Agent Runtime](engineering/Agent_Runtime_Design.md) |
| 上下文与记忆 | [Context and Memory](engineering/Context_and_Memory_Design.md) |
| 业务运行机制 | [Business Flow](engineering/Business_Flow_Design.md) |
| 数据与接口 | [Data and Interface](engineering/Data_and_Interface_Design.md) |
| 实施计划 | [Delivery Plan](engineering/Delivery_Plan.md) |

归档中的“本轮”“当前”“下一步”均指归档前的工作。内部工程链接指向同批归档；产品和上位依据的链接指向现行文件，仅供导航，精确历史版本依原文所记提交查阅。归档未复制产品规格或实验资产。

## 2. 与新文档的关系

新工作从[现行工程入口](../../m1/engineering/README.md)和[系统设计文档规范](../../../top/DeerMind_System_Design_Writing_Standard.md)开始。旧稿只供参考，不作为新稿的正文模板，不直接迁移其候选技术、接口或章节。已经由用户确认的产品和分层决定继续以现行 PRD 与决定登记为准。
