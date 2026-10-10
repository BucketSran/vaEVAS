# 五类任务的材料与学习入口

本目录把论文、作者技术资料、公开工程和已有 benchmark 资产连接到具体工程任务。
当前采用五类：按规格构建模型、从数据建立模型、扩展与集成、诊断与修复、电路测试与表征。
定义和决策保存在 [Issue #107](https://github.com/BucketSran/vaEVAS/issues/107)，这里维护学习材料及其适用范围。

具体候选的资产来源、改编形式和设计 review 进入 [逐题工作区](../workbench/README.md)。
本目录继续维护跨题材料研究；逐题状态以工作区为准，不在两处重复登记。
旧 v4 优先迁移的源码筛选与五类对应见[迁移记录](../workbench/migration/README.md)。

初轮核查日期为 2026-10-08。核查包括论文正文、实际源文件、数据说明、版本和许可；
没有运行电路仿真、模型训练或新增题目校准。材料中的 checker 和任务方案均为研究建议，
不是已建成题目。第三方公开代码不能自动作为正确答案，论文可读也不代表代码或数据可再分发。

2026-10-10 的逐题来源复核记录在 [工作区来源卡](../workbench/sources/README.md)，
新增候选及缺口见 [review 队列](../workbench/REVIEW.md)。早期专题中的后端建议保留阅读时的背景；
正式政策以 [当前 benchmark 合同](../README.md#评测方式与题目建设)为准，已允许满足条件的 ngspice 题独立评分，
不将 Spectre 对照设为所有新题的统一前提。

## 按五类查材料

| 类别与专题 | 重点材料 | 本轮要学习的问题 |
| --- | --- | --- |
| [按规格构建模型](spec-modeling.md) | SC 滤波器、CT ΔΣ、DCO、VCO、CTLE 与电源状态模型 | 如何把架构、动态和非理想行为写成可以独立验收的规格？ |
| [从数据建立模型](data-modeling.md) | JKU 采样级、OTA、Silverbox、Wiener–Hammerstein、动态辨识方法和作者代码 | 输入包是否足以辨识目标行为？初态、连续输入重构和隐藏实验如何定义？ |
| [扩展与集成](extension-integration.md) | Tiny Tapeout ADPLL、PFD/TDC/DLF/DSM 架构、VA PLL 部件、SAR 与 CDR | 如何保留原模式，并证明新增模块真正参与反馈与状态交互？ |
| [诊断与修复](diagnosis-repair.md) | v4 三个单模块、三角波振荡器、UVLO、公开 DFF/PFD | 故障是否真实或明确人工注入？允许重写后还剩什么诊断价值？ |
| [电路测试与表征](testing-characterization.md) | TI 模拟断言、ADCToolbox、Analog Design Bench、锁定与抖动测量 | 如何独立检查测量准确性、正常行为误报、违规行为漏报和报告时机？ |

材料可以服务于多个类别。相同电路的“按完整规格新建”“按数据辨识”“增加功能”和“修复错误”
需要不同起始材料与验收要求；不能改一个题目名称就重复计题。

## 建议按这个顺序共同学习

每次只处理一行，先读具体材料，再讨论一个问题。顺序是学习建议，不是出题配额。

| 顺序 | 先读什么 | 聚焦的问题 | 阅读后应形成的产物 |
| --- | --- | --- | --- |
| 1 | [TI 电路自检查论文](https://dvcon-proceedings.org/wp-content/uploads/assertion-based-self-checking-of-analog-circuits-for-circuit-verification-and-model-validation-in-spice-and-co-simulation-environments.pdf) §3.1、§4.1.1 | 一次取样、持续监测和超时检查分别承诺什么？ | 一页 VA 检查模块合同草案 |
| 2 | [ADCToolbox](https://github.com/Arcadia-1/ADCToolbox) 的具体指标函数，见测试表征专题的固定版本 | 同一份波形为何会因窗口、谐波归属和拟合约定得到不同指标？ | 指标定义、输入格式和独立参考方法 |
| 3 | [JKU 采样级台架](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_tb_transient.sch) 与[辨识路线图](https://arxiv.org/html/1902.00683v1)的实验设计部分 | 固定数据能否区分理想采样和带状态的动态模型？ | 公开表征实验与完整留出实验的草案 |
| 4 | [Tiny Tapeout ADPLL](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/tree/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2) 的 DCO、反馈计数、PI 与测试 | 频率接近、相位锁定和 lock 标志是同一个要求吗？ | 模块职责、可达范围与系统验收图 |
| 5 | [SC 滤波器论文](https://bmas.designers-guide.org/2000/papers/bmas00-lauwers.pdf) §3，以及[CT ΔΣ 论文](https://bmas.designers-guide.org/2003/papers/bmas03-sobot.pdf) §II | 哪些非理想效应可由电压域合同表达？哪些必须保留负载和电流接口？ | 一份边界明确的建模规格 |
| 6 | [v4 修复候选与 UVLO 分析](diagnosis-repair.md) | 一个模块允许重写后，什么时候仍值得做修复题？ | 单模块筛选条件与一个多模块故障场景 |

## 统筹后的候选方向

下表说明材料可以怎样进入下一轮讨论。它不表示已选定全部代表题，也不保证难度。

| 候选方向 | 主要类别 | 已有依据 | 首先要补的证据 |
| --- | --- | --- | --- |
| 真实采样级固定数据建模 | 从数据建立模型 | 已确认的试点；MOS 开关、保持电容及原瞬态台架 | 源仿真数值精度、动态可辨识性、固定验收后端；不能预设必有可测下垂 |
| 固定架构 ADPLL 补 DCO 或控制模块 | 按规格构建模型 | 开源数字闭环及码频、计数、PI 逻辑 | 独立 VA 基线、相位/复位协议、模块参与反馈的证据 |
| 既有 PLL 接入 fine TDC 或 fractional 部件 | 扩展与集成 | DVCon 架构及公开 coarse loop | 健康旧系统、新增模式的公开合同和旧模式保持要求 |
| UVLO、复位释放与使能门的小系统修复 | 诊断与修复 | 原创 UVLO 取消计时故障及独立事件队列 | 多模块起点、可观测故障、允许修改范围与系统级判据 |
| 采样时序、转换超时或锁定资格检查 | 电路测试与表征 | TI 小模块检查方法及电路事件模型 | 观察窗口、缺失事件、容差、误报与漏报校准 |
| ADC 指标提取或滤波器/振荡器表征 | 电路测试与表征 | 指标源码、测量台架与判定代码 | 明确 VA 承担的计算和输入方式，建立独立数值真值 |
| 有限带宽、压摆与恢复的滤波/放大模块 | 按规格构建模型 | SC 分层建模论文和真实 OTA 台架 | 固定负载适用条件，避免隐式要求端口电流与任意负载耦合 |

## 跨专题发现

**系统必须检查真实反馈。** 一个公开 ADPLL 的顶层把 divider 输入接到了参考时钟，
另一些工程的 lock 仅由内部计数或步长产生。源码位置见[集成专题](extension-integration.md)。
因此建议同时检查外部边沿、内部交互和受控扰动，不能只验 lock 或最终数字结果。

**指标名称不足以定义任务。** “建立时间”“INL”“锁定”需要说明参考目标、取样时机、
观察窗口及例外条件。TI 2011 的 `within_limits` 例子在 enable 上升沿取样，并不持续监视后续越界。
这一点直接影响题目承诺和 checker 的负例设计，见[测试表征专题](testing-characterization.md)。

**数据量不能替代实验设计。** 同一输入值在不同历史下的输出、跟踪时长和启动状态，是采样级的重要信息。
部分公开研究代码的 validation/test 切分有重叠，不能直接作为严格评测协议；
具体版本和适用范围见[数据建模专题](data-modeling.md)，不由局部代码观察推断作者所有结果无效。

**历史认证不能替代当前来源核对。** v4 的 PFD 与事件计数器 starter 字节分别对应 ignore-reset
与 ignore-enable 负例，但派生 manifest 声称的是其他种子。相应文件与身份核对见[修复专题](diagnosis-repair.md)。
旧 checker profile 也不能证明本轮已取得、审计并重跑独立 checker。

**学习价值与直接复用条件要分开记录。** Designer’s Guide 有很好的 VA 部件，但分发条款受限；
有些公开课程工程缺少 LICENSE，有些论文只有图和片段。Tiny Tapeout 和 JKU 的仓库许可较明确，
仍需核对第三方工艺依赖。电流域 flyback、限流稳压器及光学例子仅作边界或方法参考，
不会因本次收集而扩大当前电压域任务范围。

## 如何使用这批材料

先从每类挑选一个有工程意义且可独立验收的代表场景，再补输入、交付物、修改权限与 checker。
候选源若含已知错误，应明确用于修复任务，或先建立正确基线后才研究集成。
难度由实际模型试跑决定；源码长、参数多或用了神经网络都不是难度证据。

每份专题区分已读事实、改题建议和未知条件，保留源文件与固定版本链接。原始下载、检索日志和模型调用收据
仅保存在本机 `runs/benchmark-material-survey-20261008/`，不随笔记再分发第三方论文、数据或源码。
阶段进度、后续选择和实验状态继续写入现有 issue，避免另建平行任务清单。

## 收集方法与 GLM 交叉核对

五个专题分别由子 agent 读取主源并整理，主会话统一分类边界、来源身份和学习顺序。
另外通过 tmux 实际调用 GLM 检索测试与表征材料，CLI 返回 success、18 turns，记录中有 17 次 WebSearch/WebFetch 工具调用。
完整输出和收据保存在本机 `runs/benchmark-material-survey-20261008/glm/scout/`；主调用与结果标签为 `glm-5.3`，
收据还记录了 `glm-5.3-flash[1m]` 的用量。这些是工具返回的标签，不是对服务端权重身份的独立认证。

GLM 找到的材料没有直接全部纳入正文。它将 TI 自检查论文记为 2014，且未解码正文；
专题作者已读取原文，按 2011 记录，并核对了 `within_limits` 的实际事件语义。
GLM 读取 ADPLL README 后提出的锁定解释，需以集成专题读到的顶层连接和独立输出判据为准。
检索中的 `YiDingg/AnalogIC` 返回 404，已用实际可读的 `YiDingg/YiDingg` 固定版本替换，见集成专题。
只有摘要、没有精确正文来源的 NXP 双基准监测线索没有升级为任务依据；
VA-Models 的器件模型及收敛修改也没有纳入当前电路任务方向。

决策记录保存在本机 `runs/benchmark-material-survey-20261008/decisions.tsv`。
以上交叉核对用于筛选材料，不构成电路运行或 checker 校准证据。
