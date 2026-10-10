# v4 单模块建模与修复来源

本来源卡服务 case-0011 至 case-0015。原始资料固定于 `Arcadia-1/behavioral-veriloga-eval` 的 `7b5616dc52195ec275ec6d21c71d7763613702cd`；本轮按 vaEVAS `c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9` 保存的 r53 字节阅读。此卡是共用检索入口，五个 family 仍分别登记 source group。

| 旧题 | 内容与来源身份 | 详细读取记录 |
| --- | --- | --- |
| 024 | 理想边沿采样保持；旧 slug026；未确认真实晶体管电路来源 | [DUT 筛选](../migration/v4-spec-screening.md) |
| 001 | CDR 场景的 BBPD 行为协议；旧 slug001 | [DUT 筛选](../migration/v4-spec-screening.md) |
| 186 | 四位 SAR 前端握手；旧导入222，原工程尚未定位 | [DUT 筛选](../migration/v4-spec-screening.md) |
| 1005 / family005 | 去抖资格等待；人工注错，实际 starter 与声明故障一致 | [修复筛选及 SHA-256](../migration/v4-repair-screening.md) |
| 1272 / family272 | 同步阶段控制；人工注错，实际忽略rst而非manifest所称的比例错误 | [修复筛选及 SHA-256](../migration/v4-repair-screening.md) |

两份报告链接到原题面、源码、合同和 provenance。本轮确认的是可读材料及改编方向，没有确认任务难度、当前后端适用或可直接运行的私有 checker。旧 reference 不作为正确性的唯一依据，公开示例也不等于完整验收。

遵循[原始资料使用约定](../../reference/README.md#使用约定)，只建立设计引用，不复制原代码到新任务。资料目前限内部研究，外发资格尚未确认。完整迁移取舍见[迁移入口](../migration/README.md)。
