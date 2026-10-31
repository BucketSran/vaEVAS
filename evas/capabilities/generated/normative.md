# 规范登记状态

由 `evas/capabilities/data/` 生成。规范索引、目标范围、资格和历史成绩分别记录。
当前逐要求四后端事实见 [support.md](support.md) 与 [support-facts.json](support-facts.json)。

语言配置：`evas-va-2.4-plus-2023-v1`。基础为 LRM 2.4，选入变化为 7780, 7920。

未选入的变化继续采用基础版本；规范选入不表示后端已支持。Spectre 待跑。

EVAS 目标配置：`evas-voltage-domain-v1`，目标域 3 项，明确目标外 5 项，待细分 1 项。
这些是产品范围组，不是规范覆盖率或实现支持数。

| 来源处置 | 条目数 |
| --- | ---: |
| excluded | 2592 |
| included | 270 |
| pending | 10018 |

处置数是源索引的分母，不是要求数、测试方法数或规范覆盖率。
待判定条目及抽取边界保留在登记中；完整语义审核不能由目录自检代替。

| 当前对象 | 类型 | 资格缺口数 |
| --- | --- | ---: |
| `analysis:sef-calibration-pr1@1` | analysis | 19 |
| `calibration:sef@1` | calibration | 6 |
| `case:bound-step-request-invariance-python@1` | case | 9 |
| `case:cross-event-body-right-limit-python@1` | case | 9 |
| `case:cross-event-body-right-limit-rust@1` | case | 9 |
| `case:event-observer-math-isolation-python@1` | case | 10 |
| `case:idt-reset-argument-procedure-frame-python@1` | case | 9 |
| `case:idt-reset-argument-procedure-frame-rust@1` | case | 9 |
| `case:output-point-limit-python@1` | case | 9 |
| `case:output-point-limit-rust@1` | case | 9 |
| `case:proof-work-limit-python@1` | case | 9 |
| `case:proof-work-limit-rust@1` | case | 9 |
| `checker:bound-step-request-invariance@1` | checker | 4 |
| `checker:cross-event-body-right-limit@1` | checker | 4 |
| `checker:event-observer-math-isolation@1` | checker | 5 |
| `checker:idt-reset-argument-procedure-frame@1` | checker | 4 |
| `checker:output-point-limit@1` | checker | 4 |
| `checker:proof-work-limit@1` | checker | 4 |
| `checker:sef@1` | checker | 10 |
| `example:existing-positive@1` | case | 14 |
| `example:internal-budget@1` | internal-contract | 3 |
| `example:negative-control@1` | case | 14 |
| `execution:sef-calibration-pr1@1` | execution | 16 |
| `qualification:sef-registration-example@1` | qualification | 32 |
| `requirement:$itor@1` | requirement | 4 |
| `requirement:$rtoi@1` | requirement | 4 |
| `requirement:bound-step-request-invariance@2` | requirement | 2 |
| `requirement:cross-event-body-right-limit@2` | requirement | 2 |
| `requirement:event-observer-math-isolation@3` | requirement | 2 |
| `requirement:expm1@1` | requirement | 2 |
| `requirement:idt-reset-argument-procedure-frame@6` | requirement | 2 |
| `requirement:ln1p@1` | requirement | 2 |
| `requirement:output-point-limit@1` | requirement | 2 |
| `requirement:proof-work-limit@1` | requirement | 2 |
| `review:sef-calibration-pr1@1` | review | 23 |

资格缺口来自固定版本的依赖、审核和来源检查，不把历史运行通过转授为当前支持。
