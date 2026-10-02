# 实验目录

这里保存仿真器验证、跨后端对照和旧实现审查的协议、运行与分析脚本、执行收据及整理结果。
按实验用途浏览下列分类；每次执行的版本、设置和结果以所属目录的收据为准。

## 从这里开始

| 想了解什么 | 入口 |
| --- | --- |
| main 支持哪些功能，还有哪些缺口？ | [能力总表](../evas/docs/CAPABILITIES.md) |
| 当前 EVAS 的原条件矩阵和新增组合验证结果？ | [当前执行证据](parallel-gap-integration/README.md#当前证据) |
| 数学原理与独立正确性判据？ | [技术手册](../evas/docs/README.md)与[独立验证集](../evas/validation/README.md) |
| EVAS 与 Spectre 的事件、复位和采样为什么不同？ | [共同生命周期专项对照](parallel-gap-integration/README.md#shared-lifecycle-review)及[Spectre 专项记录](dvs2-spectre-validation/README.md) |
| 原四后端基线的结果与失败原因？ | [历史矩阵](dvs2-four-backend-validation/results/MATRIX.md)与[故障归因](dvs2-four-backend-validation/DIAGNOSIS.md) |
| 如何复现当前验证、取回原始材料？ | [复现入口](parallel-gap-integration/README.md#复现入口)与[历史和资产说明](parallel-gap-integration/README.md#历史与资产) |

## 按实验用途浏览

<a id="checkpoint-evidence"></a>

### 1. 当前 EVAS 验证与演进

| 目录 | 保存的内容 | 阅读入口 |
| --- | --- | --- |
| `parallel-gap-integration/` | 当前 main 的执行证据，以及精度链、连续动态、混合算子和共同事件生命周期的历次检查点；保留开发失败和修复对照 | [当前证据](parallel-gap-integration/README.md#当前证据)、[复现](parallel-gap-integration/README.md#复现入口) |

先读当前证据，再按问题回看[IR15 精度链](parallel-gap-integration/README.md#ir15-precision-chain)、
[IR16 连续动态与迁移](parallel-gap-integration/README.md#continuous-dynamics)、
[动态补齐](parallel-gap-integration/README.md#dynamic-closure)、
[混合动态](parallel-gap-integration/README.md#certified-mixed-dynamics)和
[共同闭包](parallel-gap-integration/README.md#lifecycle-closure-review)。
各阶段收据保留执行当时的分支状态；是否已合并、当前支持范围由能力表维护。
当前矩阵的有限观测结论、正式 DVS 资格及是否新增 Spectre/性能测量，在当前证据中分别说明。

### 2. 参考仿真器与历史检查点

| 目录 | 保存的内容 | 阅读入口 |
| --- | --- | --- |
| `dvs2-starter-pilot/` | 初始 15 条件、四后端、两档试点；共同输入生成与分析工具也被后续实验复用 | [原协议](dvs2-starter-pilot/README.md)、[结果](dvs2-starter-pilot/RESULTS.md) |
| `dvs2-history-validation/` | 对旧事件波形的共同历史重判、精确有理数检查器及其校准；重判不计为新仿真 | [结果、判据与复现](dvs2-history-validation/README.md) |
| `dvs2-spectre-validation/` | thu-sui 上原 31 条件的 Spectre 对照，以及 cross、timer、transition 等专项；保留参考运行、检查器和远端执行工具 | [专项导航与记录](dvs2-spectre-validation/README.md)、[原矩阵协议](dvs2-spectre-validation/PROTOCOL.md) |
| `dvs2-four-backend-validation/` | 原 31 条件的历史四后端矩阵、设置审计及失败诊断；其中 EVAS 为旧版 0.8.7 | [协议与身份](dvs2-four-backend-validation/README.md)、[矩阵](dvs2-four-backend-validation/results/MATRIX.md)、[诊断](dvs2-four-backend-validation/DIAGNOSIS.md) |
| `pr14-pr15-validation/` | absdelay/slew 专项和该阶段矩阵；后来补充事件条件、OR、多写者、积分复位及普通 analog 条件的检查点，矩阵适配脚本仍被复用 | [导航与原协议](pr14-pr15-validation/README.md)、[各阶段结果](pr14-pr15-validation/RESULTS.md) |

这一类的**结果绑定原执行身份**，不能代表最新 EVAS 的性能或通过数；
其中的**脚本仍可能是当前实验的依赖**，不能因为结果较旧就整目录删除。
新版 EVAS 的各轮执行见第一类，旧数据复用和重判保留原来源。

### 3. 旧 EVAS 源码审查

| 目录 | 保存的内容 | 阅读入口 |
| --- | --- | --- |
| `legacy-evas-migration/` | 固定旧源码与构建身份的审查、反例探针、迁移候选和原始证据清单；诊断观测不用于估计整个项目的缺陷率 | [审查报告](legacy-evas-migration/README.md)、[复核方法](legacy-evas-migration/REPRODUCE.md) |

报告中的迁移建议是当时的判断，后续交付状态见能力表。

## 文件怎么读，怎么复现

| 文件或位置 | 职责 |
| --- | --- |
| 各目录的 `README.md` / `PROTOCOL.md` | 研究问题、范围、预先定义的判据、执行与复现入口 |
| `.py` / `.rs` 脚本 | 生成输入、执行后端、分析结果或校准检查器；按该实验协议调用 |
| `RESULTS.md` / `results/*.md` | 面向读者的结果、差异及失败解释 |
| JSON / JSONL / 压缩 JSON 收据 | 源码、输入、检查器和二进制身份，逐配置结果与归档清单；阅读摘要后用它们复核 |
| 根目录 ignored 的 `runs/` 或外部归档 | 完整波形、日志、临时文件及冻结构建；可用性由对应收据标明 |

复现时先核对目标检查点的输入、检查器、源码与内核身份，再使用该轮协议中的命令。
只重判已有波形和重新运行后端是两种操作，需要分别记录。
仓库中的整理材料可直接取得；完整 raw 若标为“仅本地保留”，外部读者不能据此下载。
本地工作区清理后的旧路径由归档清单映射，原收据保持执行时的路径和字节。

## 后续实验怎么归档

- 按研究问题或能力命名目录，例如 `event-lifecycle/`，避免继续用 PR 编号命名。延续同一问题时复用现有目录，用不同 run/analysis 身份区分执行。
- 目录 README 顶部放阅读入口和适用检查点，再链接协议、结果与收据；旧阶段按时间或执行身份排列，保留失败与差异。
- 数学与支持边界归 `evas/docs/`，独立模型、判据与检查器归 `evas/validation/`；这里记录实际实验，不重复维护能力总表。
- 新实验加入本索引的相应分类，原始大文件进入有清单和哈希的归档。现有目录名称暂保留：跨目录导入、源码快照和冻结收据依赖这些路径，搬迁需单独验证。

<a name="experiment-receipts"></a>

## 实验资产与收据

[CONTRIBUTING.md](../CONTRIBUTING.md#evidence-and-assets)维护协作流程；
[能力总表](../evas/docs/CAPABILITIES.md)通过稳定 ID 链接结果。每轮沿用对应目录已有的协议与
收据格式，把以下信息补入现有 manifest/结果 JSON，不要求再生成一套重复记录。

| 信息 | 必须能回答的问题 |
| --- | --- |
| 目标与身份 | 哪个能力/条件？run_id 是新执行、复用还是重判？后两者链接哪次原执行？ |
| 实现与构建 | DUT/EVAS commit、是否有未提交修改、可重建的源码快照/补丁哈希、内核哈希是什么？仅记录 dirty=true 不足以复现。 |
| 输入与判据 | 模型、刺激、初值、时间网格、独立答案、阈值和检查器版本/哈希是什么？ |
| 环境与命令 | 后端/工具链、命令、请求及实际生效设置、预算是什么？性能实验还记录机器、计时边界和重复方法。 |
| 输出与归因 | 执行状态、编译/运行/数值/环境失败、固定分母、P/F/I 或协议所定义结论、证据边界是什么？ |
| 可用性 | 输入/输出归档在哪里、清单和哈希是什么、外部人员能否取得？ |

适用字段不得凭空补值；不适用项注明原因，未知/缺失项保留为缺口。
容器、Harbor、Agent 身份只在实际使用时记录；不同开发分支可以共享包版本号，commit 与二进制身份须独立记录。
参数或检查器变化后使用新 run/analysis 身份，保留原执行与判定；旧数据重判不能计为新仿真。
父分支变化只触发受影响结论的重新验证。

可用性明确标为：**仓库内可取得**、**公开归档可取得**、或 **仅本地保留**。
公开归档使用实际可下载地址及文件清单/哈希，机器路径或哈希不能代替下载入口。
发布公开材料仍需任务授权；保留共同模型、独立检查器及足以复核的最小结果，大波形可放发布附件或数据仓库。
清理工作区前先迁移需要保留的 ignored 原始材料，核对清单并保存旧路径到新路径的映射；Git 提交不保存这些文件。
删除已合并分支不删除 main 中的提交或 PR 历史，分支名也不是原始材料的永久保存位置。

案例数、后端配置数、事件历史数和 unittest 方法数分别报告；
已用于诊断和修复的测试属于开发证据，有限观测不能替代连续时间误差界或独立确认集。
保留失败和未决项，区分模型、仿真器、检查器及环境责任；影响判分的修复需评估哪些结果必须重跑。
