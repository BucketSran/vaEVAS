# Filter / RF 来源与改编

五个任务对应 #149 的四个核心单元。C3 的实际变频与包络时间演化有独立接口、输入和验收，因此拆成两题；不把它们宣称为完整接收机。所有任务权重为1。

| 单元与任务 | 来源去向 | 新增合同和资产 |
| --- | --- | --- |
| C1 `v3-filter-ctle` | verilogaLib CTLE 的一零点两极点主题 | 原创归一化状态模型、非零初态、真实多正弦工程、复数频响判据 |
| C2 `v3-filter-programmable-lp` | v4 334 的可调带宽与历史主题 | 原创连续低通基线、公开码频映射、换码连续性、复位；不复用旧离散递推 |
| C3a `v3-filter-iq-conversion` | v4 364 的上变频及400的下变频合并 | 明确 cos/sin LO、Q负号、真实乘法搬频、下变频带宽、使能与连续状态 |
| C3b `v3-filter-envelope` | v4 336 的包络动态主题 | 独立能量低通与平方根输出，禁用衰减、复位和初态；不是旧逐采样attack/release模型 |
| C4 `v3-filter-sweep-measurement` | 新建连续滤波测量工程 | 原创只读低通DUT、真实VA扫频与同步积分、低幅度及观察窗无效合同 |

来源334、364、400、336全部有资产去向。旧模型的钳位、电源共模、调试资格位、时钟和离散tick不继承为新合同；本轮明确测试的是连续时间滤波和理想变频。旧版同源关系仍保留，不能把两次改编算作独立来源。

固定来源为本仓库 reviewed main `81eb66258b59b0a0cd48cd3decaa767be02cdd58` 下的 `benchmark/reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/{334,364,400,336}-*/evaluator/solution/`，逐文件SHA见 `source-identities.json`。该历史包原文件保持不变，仅作为内部主题与行为资料；本轮公共候选、健康工程和checker均为原创重建，未复制原文件。

外部CTLE固定为 [Brian Li / verilogaLib ctle.va](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/ctle.va)，该版本MIT，2025 Brian Li，原源码引用情况及未声明gain的缺口见[已有资料核查](../../../benchmark/research/spec-modeling.md)。本轮未复制该源码，不依赖其归一化；公开题面给出独立数学合同。外部论文、Analog Design Bench biquad和SC研究仅为指标背景，本轮没有重发其资产，也未声称它们验证了新连续模型。

Spectre是固定评分后端；Python 3.12、标准disciplines/constants、运行命令和实际版本身份随校准报告冻结。开源复验缺口：尚未证明这些VA候选能通过ngspice编译执行，不能以DUT电路可开源运行代替候选资格。真实数据全部是本轮固定候选的作者仿真，未使用模型生成答案或模型试跑。
