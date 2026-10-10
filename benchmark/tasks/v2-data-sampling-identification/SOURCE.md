# 真实采样级的来源与验收边界

本题真值来自实际 SKY130 晶体管瞬态仿真。固定来源是 [efabless/SKY130_SAR-ADC1 的 8922722](https://github.com/efabless/SKY130_SAR-ADC1/tree/892272208df28b6c7620101e129a9d8dd95ebab7)，作者为 Manuel Moser / JKU，许可为 Apache-2.0。原始原理图和许可保存在[来源快照](../../../experiments/benchmark_v2/data_modeling/source/)。本题属于 case-0006 / spec #134，首个试点独立于32个P1来源。

[源表征生成器](../../../experiments/benchmark_v2/data_modeling/generate_source.py)逐器件转录采样开关、dummy补偿、时钟反相器和2.44 pF保持电容。主开关 W=7.6 µm、L=0.22 µm、nf=4；dummy W=3.8 µm、nf=2，L不变。反相器的PMOS为W=.84 µm/nf=2，NMOS为W=.42 µm/nf=1，均L=.15 µm。供电1.8 V，温度25°C，tt。激励台架按任务的完整序列重建；器件结构、尺寸和接线没有用拟合VA替代。

端子转录经过原理图符号引脚与旋转交叉核对，见[转录核验](../../../experiments/benchmark_v2/data_modeling/source-transcription.json)。两只主开关的D端接vin、S端接保持输出；dummy和反相器端子按原图连接。初稿将主开关D/S互换，已经修正并重新生成全部数据和公开拟合；初稿运行结果不代表该来源验收。

源PDK为 [google/skywater-pdk-libs-sky130_fd_pr](https://github.com/google/skywater-pdk-libs-sky130_fd_pr/tree/f62031a1be9aefe902d6d54cddd6f59b57627436) 的固定版本，许可Apache-2.0。生成器递归展开lod和两种MOS的tt/mismatch文件，参数不改。ngspice 47使用`wnflag=1`，使多指器件按W/nf选择模型区间。默认按总宽度选区间的初跑报负u0/Pclm，不能作为源证据。有效求解配置为gear、reltol=1e-4、vntol=1e-6、abstol=1e-15、chgtol=1e-18、trtol=1、maxstep=10 ps，启动使用DC工作点。

完整输入和来源身份见[数据清单](../../../experiments/benchmark_v2/data_modeling/dataset-manifest.json)。32条训练和2条公开自测按完整独立实验发布，4条隐藏实验保留独立的新输入轨迹、时长、前拍及相位。初态由t=0的vin和有效跟踪状态定义，随后30 ns可见前史；没有在评分阶段用真值反馈补初态。所有源初始输出与已声明输入之差不超过10 nV。

平静段公开观察每2 ns保存一点，采集及输入/时钟变化附近仍保存50 ps观察，全部PWL节点和样点另行保存。该压缩得到9415行公开观察。模型速率表严格从当前公开CSV拟合；作者参考没有另取求解者不可得的细粒度轨迹。隐藏真值保持原50 ps网格和固定样点。

源精度、导出和模型误差是不同预算。[数值对照](../../../experiments/benchmark_v2/data_modeling/source-convergence.json)对一条训练和一条隐藏实验比较2.5 ps/reltol=1e-5，以及5 ps/trap。已测评分区间的最大源差为0.131 mV；更严容差的原尝试在恒定初态出现timestep失败，因此不作为有效比较。额外UIC试验在一条记录跑完后评分差0.0661 mV，另一条在启动失败。固定合同采用已核查DC工作点，不声称任意初始化方法都可靠。

[导出审计](../../../experiments/benchmark_v2/data_modeling/export-errors.json)把发布观察重构后与原晶体管瞬态点比较。评分区间最大插值差为4.081 mV，公开数据最大为1.969 mV；全时轴最大为5.037 mV。主要来自快速输入变化附近，首轮不把这种细节当作独立的feedthrough辨识目标。25 mV采集RMS与50 mV采样/保持阈值公开且固定，覆盖已量化的数据不确定性与允许模型误差。源已跑条件和两条数值对照可复核，不推广为全部PDK、corner或长期保持的验证。

有限采集和历史确实可见。`train-0-0`在0.2 V历史后跟踪1.6 V达0.8 ns，观测样值约0.66872 V。相同1.6 V目标、6 ns跟踪，`train-sweep-9-0`与`train-sweep-9-1`因历史分别为0.2 V和1.6 V，样值约1.47897 V与1.60000 V，差121 mV。该差远高于已测数值误差与导出误差，且公开数据包含这些完整历史。

评分从原电路留出CSV读取真值，分段计算采集RMS、样点绝对误差和保持最大误差。参考是29节点的状态相关正速率表与积分状态；另一个合法模型用15节点表、电容和非线性导纳。它们仅用于可做性和checker校准，不能成为隐藏真值。理想采样、过快采集、错误时钟相位、固定RC、清零历史和回放公开记录作为语义负例。

候选固定由Spectre执行。这属于ngspice晶体管真值与Spectre VA执行的跨后端数据拟合，重新验收候选无需PDK；重生成真值需要固定PDK和ngspice。因此当前归属Spectre扩展集。没有声明源晶体管在Spectre的物理对齐，也没有声明EVAS或开源VA评分可复现。实际VA校准和两配置Agentic/适用one-shot试做由协调实验补齐，目前这两项仍待实跑。
