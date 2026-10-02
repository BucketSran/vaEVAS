# Experiments

此目录保存仿真器验证、源码审查及 benchmark 实验的协议、分析程序和整理结果。
每项记录实际使用的模型、后端、任务范围、预算及版本；Harbor 和 Agent 信息只在对应实验中记录。

可跟踪内容包括配置、分析脚本和经过整理且可追溯的结果摘要。
原始轨迹、波形及临时输出使用仓库根目录下的 `runs/` 或外部运行目录，避免提交到 Git。

<a name="experiment-receipts"></a>

## 实验资产与收据

[CONTRIBUTING.md](../CONTRIBUTING.md#evidence-and-assets)规定协作与资产管理流程；
[能力总表](../evas/docs/CAPABILITIES.md)通过稳定 ID 链接结果。每轮实验沿用对应目录已有的协议与
收据格式，以下信息补入其现有 manifest/结果 JSON 即可，不要求再生成一套重复记录。

| 信息 | 必须能回答的问题 |
| --- | --- |
| 目标与身份 | 哪个能力/条件？run_id 是新执行、复用还是重判？后两者链接哪次原执行？ |
| 实现与构建 | DUT/EVAS commit、是否有未提交修改、可重建的源码快照/补丁哈希、内核哈希是什么？仅记录 dirty=true 不足以复现。 |
| 输入与判据 | 模型、刺激、初值、时间网格、独立答案、阈值和检查器版本/哈希是什么？ |
| 环境与命令 | 后端/工具链、命令、请求及实际生效设置、预算是什么？性能实验还记录机器、计时边界和重复方法。 |
| 输出与归因 | 执行状态、编译/运行/数值/环境失败、固定分母、P/F/I 或协议所定义结论、证据边界是什么？ |
| 可用性 | 输入/输出归档在哪里、清单和哈希是什么、外部人员能否取得？ |

适用字段不得凭空补值；不适用项注明原因，未知/缺失项保留为缺口。容器、Harbor、Agent 身份只在实际使用时记录。
不同开发分支可以共享包版本号，因此 commit 与二进制身份必须独立记录。参数或检查器变化后使用新 run/analysis 身份，
保留原执行与判定；旧数据重判不能计为新仿真。父分支变化只触发受影响结论的重新验证。

可用性明确标为：**仓库内可取得**、**公开归档可取得**、或 **仅本地保留**。
公开归档使用实际可下载地址及文件清单/哈希；未上传时写明缺口，不使用机器路径或哈希冒充下载入口。
发布公开材料仍需任务授权；应保留共同模型、独立检查器和足以复核的最小结果，大波形可放发布附件/数据仓库。
清理工作区前，先迁移需要保留的 ignored 原始材料；保存 Git 提交并不会保存这些文件。
迁移归档时保留原收据字节和执行时路径，在本地归档清单中记录旧路径、新路径与校验结果。
删除已合并分支不删除 main 中的提交或 PR 历史；分支名也不是原始材料的永久保存位置。

案例数、后端配置数、事件历史数和 unittest 方法数分别报告。测试用于诊断后属于开发证据，
有限观测不能替代连续时间误差界或独立确认集。已知差异与失败同成功结果一起保留。

<a id="checkpoint-evidence"></a>

## 已有实验入口

当前已合并检查点为 [PR33](https://github.com/BucketSran/vaEVAS/pull/33) 的 EVAS 0.12.2 / IR16。
[当前执行证据](parallel-gap-integration/README.md#当前证据)维护原矩阵、开发检查及源码/内核身份；
[能力总表](../evas/docs/CAPABILITIES.md)维护支持和剩余边界。本次文档校准未重新运行仿真。
原矩阵两档均为 **31/31 有限观测达标**，正式资格仍 **I**，完整 raw 为 **仅本地保留**；
本检查点没有新 Spectre 或性能测量。

[IR15 精度链](parallel-gap-integration/README.md#ir15-precision-chain)、
[首轮 IR16 与迁移](parallel-gap-integration/README.md#continuous-dynamics)、
[后续动态补齐](parallel-gap-integration/README.md#dynamic-closure)及
[共同闭包](parallel-gap-integration/README.md#lifecycle-closure-review)分别保存原执行。
这些结果不计为新 Spectre 仿真或原矩阵的新条件；历史状态仍保留在原收据中。

PR26 `edb004d` 的两档各 24/31 保留在[历史复位对照](pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)。
功能补齐 `39a4545` 与优化 `ddfd379` 的原执行、初期失败和测量从
[历史入口及无损收据](parallel-gap-integration/README.md#历史与资产)进入，不由新结果改写。

以下入口保留各自冻结身份，旧结果不替代当前源码的新执行，也不构成最新版本的配对性能比较。

| 入口 | 固定范围与证据边界 |
| --- | --- |
| [旧 EVAS 源码审查](legacy-evas-migration/README.md) | 2026-09-29 的旧 `v0.8.7` 报告、47 条本地诊断观测与反例；不是通过数。迁移建议属于当时规划，当前交付状态见能力表。 |
| [DVS-2 起步卡试点](dvs2-starter-pilot/RESULTS.md)及[协议](dvs2-starter-pilot/README.md) | 15 条件、四后端、两档的开发证据，尚非正式达标率或性能排名。 |
| [共同历史重判](dvs2-history-validation/README.md) | 使用精确有理数检查器重判旧事件波形；不计为新仿真，不覆盖 v1 原执行。 |
| [Spectre 扩展实测](dvs2-spectre-validation/README.md) | thu-sui 上的历史 31 条件 × 两档，共 62 配置满足固定有限观测判据；后续 cross/timer/transition 专项在原目录分别记录，正式资格仍 I。 |
| [四后端补测](dvs2-four-backend-validation/README.md)与[矩阵](dvs2-four-backend-validation/results/MATRIX.md) | 130 条新配置加 118 条复用记录；旧 EVAS 0.8.7 的 248 单元。基础档/细化档分别为 Spectre 31/31、EVAS 18/8、OpenVAF＋ngspice 16/16、Gnucap 17/16，各档分母 31；失败与超时保留。 |
| [后端故障归因](dvs2-four-backend-validation/DIAGNOSIS.md) | 15 个诊断探针追查机制；该轮只诊断，未改运行时，保留原矩阵。后续修复另有提交与收据。 |
| [新 EVAS 检查点结果](pr14-pr15-validation/RESULTS.md)及[原验证协议](pr14-pr15-validation/README.md) | 原 PR14/15 四后端 248 单元，EVAS 两档各 13/31；absdelay/slew 专项与步长诊断单列。该目录继续保存 PR23、PR26 的本地 EVAS 检查点，导航区分原矩阵与后续运行。 |

原始材料的可用性以各轮协议及收据为准；本索引不代表已经公开完整波形。
任务失败、仿真器问题和执行环境失败分别记录；影响判分的修复需评估哪些结果必须重跑。
