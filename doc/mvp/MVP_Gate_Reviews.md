# MVP 阶段 Gate 评审记录

| 元信息 | 当前记录 |
| --- | --- |
| 状态与版本 | 记录框架草案；G3/G4/G5 均未形成本轮评审记录 |
| 更新日期 | 2026-10-10 |
| 维护责任 | 阶段评审记录维护角色，具体承担者待指定 |
| 评审人及记录 | 各次实际评审时登记；当前未指定 |
| 依据的上游基线 | [Development Roadmap §7.1](../top/DeerMind_Development_Roadmap_v0.3.md#71-项目级-gate-总览)；评审前登记准确提交及所审交付版本 |

本文独立汇总阶段判断，各主体文档只提供自身完成情况与证据。文档导航见 [README](README.md)，版本、变更和登记规则见[共同管理规则](MVP_Governance.md)。历史 G3 记录仍保存在[归档产品定义](archive/DeerMind_MVP_Definition_v0.1.md#11-g3-评审与阶段完成条件)，不转写为本轮新范围已经通过。

## 1. 统一记录结构与判断规则

每次评审登记 Gate、记录标识与日期、提出者和实际判断者、审查范围、基线标识、准确提交与资产版本、逐项证据、未满足项、遗留责任、结论及重开条件。独立文件不代表已经独立审查；可以由同一人承担多个角色，须如实记录实际分工。

| 核对项 | 所依据的要求与版本 | 证据位置及版本 | 满足／未满足／不适用及理由 | 待决或风险编号与责任 | 实际判断人及日期 |
| --- | --- | --- | --- | --- | --- |

以上表结构在各次实际评审时使用，当前无已填记录。结论说明是否允许进入下一阶段、需补充后再评审，或需返回哪一责任层修订。不能以已建立大纲、勾选文档清单或指定后续责任代替当前必须具备的证据；不阻塞的遗留项须有明确理由、责任和处理节点。

## 2. G3 — MVP Definition

**本轮状态：未评审，待正文交付。** 条件依据为 [Development Roadmap §4.1](../top/DeerMind_Development_Roadmap_v0.3.md#41-phase-3--mvp-definition)，通过后允许进入 Product & Domain Foundation，不表示产品已经实现或可开展真实用户试用。

评审输入为[产品定义](phase-3-definition/MVP_Definition.md)、[需求与验收规格](phase-3-definition/MVP_Requirements_and_Acceptance.md)、[验证方案](phase-3-definition/MVP_Validation_Plan.md)，以及相关来源证据、已确认决定和待决事项。

核对目标用户、核心问题与场景、价值假设、完整范围、最低成功指标和关键验证问题是否清晰；需求取舍有依据，必要角色及 AI 行为边界可理解。数据权限、内容可得性及使用条件、运营成本量级与责任、适用安全约束等范围级前提不能全部推迟到下游。

允许后续细化的测量参数按验证方案登记校准依据、责任、期限及不阻塞 G3 的理由；不能把所有最低可接受目标留待实现后决定。历史决定的相关承接和未决冲突须有记录。本节实际评审时按 §1 填写证据表与结论，当前未执行。

## 3. G4 — Product & Domain Foundation

**本轮状态：未评审，待设计与实际资产交付。** 条件依据为 [Development Roadmap §4.2](../top/DeerMind_Development_Roadmap_v0.3.md#42-phase-4--product--domain-foundation)，通过后允许进入 MVP Engineering。

评审输入为[产品与交互设计](phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md)、[领域与内容基础](phase-4-product-and-domain-foundation/MVP_Domain_and_Content_Foundation.md)、[数据与权限设计](phase-4-product-and-domain-foundation/MVP_Data_and_Authority_Design.md)、[评测资产规格](phase-4-product-and-domain-foundation/MVP_Evaluation_Assets_Specification.md)，以及相符的实际原型、首批领域内容、参考案例和审查记录。

核对核心用户与运营旅程、活动衔接、异常及反馈是否可实现；领域范围、内容来源与映射、初始资产及质量审查是否足以支撑已确认场景；数据、授权与用户控制是否一致；评测材料是否可取得且有可信参考。工程不能再临时发明核心交互或领域语义。

四项交付共同评审，原型可点击或单篇设计完成均不能代表 G4 通过。检查 G3 基线引用、后续变更影响与到期的测量校准责任。本节实际评审时按 §1 填写证据表与结论，当前未执行。

## 4. G5 — MVP Feature Complete

**本轮状态：未评审，待真实实现与工程证据。** 条件依据为 [Development Roadmap §5.1](../top/DeerMind_Development_Roadmap_v0.3.md#51-phase-5--mvp-engineering)，通过后允许进入 Internal Alpha，不替代 G6 Pilot Readiness 或 G7 的真实使用验证。

评审输入为[工程设计](phase-5-engineering/MVP_Engineering_Design.md)、[分步实施与验证计划](phase-5-engineering/MVP_Incremental_Delivery_Plan.md)、[交付与运行交接](phase-5-engineering/MVP_Delivery_and_Handover.md)，以及准确版本的软件、领域与评测资产、可复现操作和实际检查结果。

核对完整 MVP 核心价值链是否端到端可用，核心 AI、数据与架构路径是否为真实实现，必要能力与关键异常是否有证据，尚缺能力和质量限制是否明确。不能以局部增量演示或测试旁路替代实际可用性；影响本阶段核心交付的实现缺陷不能只登记后转交。

正式质量评估仍由 Phase 6 负责，但进入该阶段所需的测量口径、参考与运行条件必须就绪，不能把尚未固定的标准交给结果决定。本节实际评审时按 §1 填写证据表与结论，当前未执行。

## 5. 复评与历史关系

后续变更按[共同管理规则 §5](MVP_Governance.md#5-变更与影响分析)判断是否需要复评及其范围。保留每次原始对象、证据和结论，新记录指明替代、补充或仍然有效的部分，不覆盖原失败或通过记录。非阻塞事项到期后仍未解决时重新判断对下一步的影响，不无限期以“后续处理”维持准入。
