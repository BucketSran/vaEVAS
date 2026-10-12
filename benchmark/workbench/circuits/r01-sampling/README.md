# R01 采样与多通道读出

本功能族用于 [#159](https://github.com/BucketSran/vaEVAS/issues/159) 的电路功能与场景审核。现有九组资产包括三个采样单元、五个组合系统和一个表征仪器。先结合 VA 源码判断电路用途与覆盖，再决定具体出什么题。

本轮整理目录，并把扩展方向保留为暂缓候选。九组资产不是九道新增计分题，现有 56 题的合同与数量不变。题面、独立 checker、Harbor 封装和模型实验仍留在后续阶段。

## 目录与阅读顺序

```text
r01-sampling/
├── README.md                       # 功能族总览、同源关系和候选方向
├── module/                         # 单个采样模块及各自说明
│   ├── ideal/
│   ├── basic/
│   └── core/
├── system/                         # 组合电路及各自说明
│   ├── simultaneous/
│   ├── mux/
│   ├── interleaved/
│   ├── pingpong/
│   └── cds/
└── test/                           # 激励、连接、测量仪器和运行记录
    ├── ideal/                      # 以下同名目录各保留一份 tb.scs
    ├── basic/
    ├── core/
    ├── simultaneous/
    ├── mux/
    ├── interleaved/
    ├── pingpong/
    ├── cds/
    ├── characterization/           # bench.va、tb.scs 和仪器说明
    ├── RUN-RECORD.md
    └── run-sources.json
```

先看 `module/` 的三种采样行为，再看 `system/` 怎样组织采集与读出。需要观察实际响应时，进入 `test/` 的对应目录。相近模块或系统以后可以继续按结构或功能细分子目录，共用源码通过引用复用。

`test/` 存放电路激励与测量资产；这里的目录名不表示已经建立了正式评分 checker。

## 现有模块

| 模块与入口 | 代码大体思路 | 电路功能 |
| --- | --- | --- |
| [ideal 理想跟踪保持](module/ideal/README.md) · [VA](module/ideal/circuit.va) · [台架](test/ideal/tb.scs) | 跟踪阶段直接跟随输入，下降沿保存电压，保持阶段冻结 | 基本跟踪保持、复位与初态处理；它不同于旧 024 的上升沿瞬时取样 |
| [basic 有限采集、理想保持](module/basic/README.md) · [VA](module/basic/circuit.va) · [台架](test/basic/tb.scs) | 内部电压逐渐逼近输入，采集速度与输入电平有关，保持阶段冻结 | 观察采集窗口不足与前拍残余，单独考察建立误差 |
| [core 连续非理想采样保持](module/core/README.md) · [VA](module/core/track_hold.va) · [台架](test/core/tb.scs) | 在有限采集之外，加入有限注入、保持漏电和复位恢复 | 观察采集误差、切换偏移和长时间保持误差 |

## 现有系统

| 系统与入口 | 代码大体思路 | 电路功能 |
| --- | --- | --- |
| [同步四通道](system/simultaneous/README.md) · [VA](system/simultaneous/circuit.va) · [台架](test/simultaneous/tb.scs) | 四路输入各有采样状态，共同时钟采集，外部选择码和读使能控制输出 | 多传感器同步快照、顺序读出；等待期间各路继续下垂 |
| [MUX 共享采样级](system/mux/README.md) · [VA](system/mux/circuit.va) · [台架](test/mux/tb.scs) | 锁存本次通道，让四路输入轮流使用同一采样状态 | 扫描采集；换通道后从上一通道留下的电压重新建立 |
| [时间交错采样](system/interleaved/README.md) · [VA](system/interleaved/circuit.va) · [台架](test/interleaved/tb.scs) | 两支路错时采同一输入，按读时钟取出样本，并保留支路、序号和时刻 | 组合采样序列，以及增益、失调、时序和带宽差异对序列的影响 |
| [乒乓采样](system/pingpong/README.md) · [VA](system/pingpong/circuit.va) · [台架](test/pingpong/tb.scs) | 两支路轮流采集，连续选择已完成采集的保持支路输出 | 一支路采集时，另一支路供后级使用；当前没有独立读时钟 |
| [相关双采样 CDS](system/cds/README.md) · [VA](system/cds/circuit.va) · [台架](test/cds/tb.scs) | 先采参考，再采信号，两份保持电压相减 | 抑制共同偏移，观察有限建立和不等保持时间留下的残差 |

同步四通道采不同输入，保留同一时刻的快照；MUX 让不同输入共用一个存储状态。交错与乒乓都用两个支路采同一输入，当前实现的区别在于向后级提供结果的方式：交错按读时钟组织样本序列，乒乓直接提供保持支路。

## 表征仪器

[响应驱动的表征仪器](test/characterization/README.md)包含 [bench.va](test/characterization/bench.va) 和[连接网表](test/characterization/tb.scs)。它实际驱动复位、输入与采集控制，根据输出是否稳定决定下一步，报告采集时间、切换变化、保持漂移和超时。

阶段控制来自 `timer`、`cross` 和端口观测，`$strobe` 负责输出报告。这组资产用于讨论电路测试与表征；模块与系统还可以用于规格建模、扩展集成或有具体故障依据的修复任务。数据建模需要有来源的独立数据，不为五类题型凑齐任务。

## 同源关系与已有材料

`ideal`、`basic` 和 `core` 是同一采样功能的三个层次。五个系统和表征仪器均复用 `module/core/track_hold.va`，应保留这种关联。更改时间常数、输入电压或窗口长度属于运行条件；是否拆成独立题目，要看是否增加了独立工程要求。

| 已有材料 | 与本功能族的关系 |
| --- | --- |
| [024 边沿采样保持](../../../tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | 旧题按上升沿取样；当前 ideal 在跟踪阶段透明，不能视为同一合同 |
| [071 有限采集](../../../tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) | 已有离散更新下的有限采集和历史残余；core 补充连续状态、输入相关采集与保持动态 |
| [真实 SKY130 采样级数据](../../../tasks/v2-data-sampling-identification/SOURCE.md) | 独立的真实电路数据来源；当前 core 未拟合这份数据，也不继承其校准结论 |
| [349 多通道读出](../../../tasks/v2-integrate-349-multichannel-readout/instruction.md) | 与同步采集、顺序读出关联；当前系统保留等待中的连续下垂，另建 MUX 与交错结构 |
| [308 相关双采样](../../../tasks/v2-spec-308-correlated-double-sampler-offset-cancel/instruction.md) | 与 CDS 抑制共同偏移的功能关联；当前系统补充连续采集和保持动态，不修改旧题合同 |

## 暂缓候选与后续优先级

以下方向本轮全部暂缓，只保留思路和待解决的问题。P1、P2、P3 表示以后需要扩充 R01 时的讨论顺序，不表示已经批准建设或具备完整材料。同一优先级按表内顺序讨论。

| 优先级 | 候选方向 | 希望增加的电路功能 | 重新推进前需要明确什么 |
| --- | --- | --- | --- |
| P1 | MUX 扫描顺序与采集窗口控制 | 根据通道切换幅度和精度需要安排选择顺序、采集时长 | 控制器知道哪些输入信息，哪些通道必须按固定周期采集，以及实际吞吐需求 |
| P1 | 同步采样后的读出安排 | 对保持能力不同的通道安排读序与等待时间 | 各通道的实际差异、后级读取速度，以及调整读序是否有明确用途 |
| P1 | 信号相关注入与 CDS 残差 | 两次采样的注入量不同，研究共同偏移抑制后的剩余误差 | 注入与输入电平的关系、适用电路依据，以及与现有 CDS 的区分 |
| P1 | 保持期间的输入耦合 | 输入变化通过寄生路径扰动保持输出 | 耦合路径、频率范围与等效电路，区分输入耦合、时钟馈通和漏电 |
| P2 | 交错支路的增益与失调校准 | 从参考输入测出支路差异，再修正读出结果 | 可用参考信号、可调整参数和校准方式；仅增加失配参数仍作为已有变体 |
| P2 | 介质吸收造成的慢记忆 | 保存额外的慢状态，表现历史充电后的电压恢复 | 有实际需要的精密采样场景及慢状态模型，区分它与采集不足的前拍残余 |
| P2 | 输入驱动器与输出负载 | 表现驱动器、采样电容和后级负载之间的共同建立过程 | 具体连接与等效参数；当前 core 的理想输入、输出端口不能直接表示这种相互作用 |
| P3 | 采样噪声 | 表现采样噪声及两次采样之间的相关性 | 噪声来源、带宽、统计模型和 CDS 场景是否需要保留相关性 |
| P3 | 随机孔径抖动 | 表现采样时刻不确定性对采样电压的影响 | 抖动来源与时间相关性，区分它与现有确定性支路时偏 |
| P3 | 工艺、供电与温度变化 | 表现环境变化对采集、保持或偏移的影响 | 参数随条件变化的物理依据或数据；普通参数扫描仍归入已有场景 |
| P3 | 主动表征与辨识 | 自选激励，从原电路获取数据再建立模型 | 可调用的原电路、开放控制量和数据来源；这是任务方式扩展，不另算采样架构 |

候选机制可继续参考 [ADI MT-090](https://www.analog.com/media/en/training-seminars/tutorials/MT-090.pdf)、[TI TIPD169](https://www.ti.com/tool/TIPD169) 和 [ADI 交错 ADC 说明](https://www.analog.com/en/resources/technical-articles/the-abcs-of-interleaved-adcs.html)。资料支持机制讨论，不代表当前已有可直接移植的完整题目。

## 来源、运行与边界

源码为本轮新建的电压域行为资产，参数为名义设计值。没有复制上述资料的电路源码，也未宣称参数来自测量、PDK 拟合或厂商官方 VA 模型。当前 core 不表示输入阻抗、外部负载电流、噪声、随机孔径抖动、孔径延迟、介质吸收、保持态输入耦合或 PVT。

从本功能族目录进入对应台架目录运行，例如：

```sh
cd test/core
spectre tb.scs
```

九组资产此前的 Spectre 执行与观察见[运行记录](test/RUN-RECORD.md)。本次只迁移文件并修正引用路径，未重跑仿真；旧输入路径与哈希保留为历史记录。EVAS 与 ngspice 的运行适配尚未验证，已有运行也不等于正式题目的作者校准或 R01 审核通过。
