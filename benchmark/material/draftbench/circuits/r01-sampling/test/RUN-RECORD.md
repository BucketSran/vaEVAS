# R01 电路资产运行记录

2026-10-11，在 reviewed main `826fefb12b5b068544be9de97e68f21e3c60e76f` 上新增本批资产。本记录针对本地分支 `codex/benchmark-r01-assets` 的文件，不代表已经提交、发布或合入 main。

本轮检查电路能否运行及是否呈现所描述的关键行为。没有开发正式评分 checker，也没有进行模型解题实验、全参数校准或跨后端等价验证。

## 2026-10-12 目录调整

本次按功能族 README、`module/`、`system/`、`test/` 重新组织资产。以下运行段落保留执行当时的路径与观测；[run-sources.json](run-sources.json) 的路径和哈希也保留原值，不作为迁移后网表的哈希清单。

下表路径以功能族根目录为起点。九份 VA 源码原样移动，九份 `tb.scs` 只调整 `ahdl_include` 路径。没有修改模型、激励、参数或分析设置，也没有因本次整理重跑 Spectre。

| 原目录 | 当前源码与说明 | 当前运行目录 |
| --- | --- | --- |
| `ideal/` | [module/ideal](../module/ideal/README.md) | [test/ideal](ideal/tb.scs) |
| `basic/` | [module/basic](../module/basic/README.md) | [test/basic](basic/tb.scs) |
| `core/` | [module/core](../module/core/README.md) | [test/core](core/tb.scs) |
| `simultaneous/` | [system/simultaneous](../system/simultaneous/README.md) | [test/simultaneous](simultaneous/tb.scs) |
| `mux/` | [system/mux](../system/mux/README.md) | [test/mux](mux/tb.scs) |
| `interleaved/` | [system/interleaved](../system/interleaved/README.md) | [test/interleaved](interleaved/tb.scs) |
| `pingpong/` | [system/pingpong](../system/pingpong/README.md) | [test/pingpong](pingpong/tb.scs) |
| `cds/` | [system/cds](../system/cds/README.md) | [test/cds](cds/tb.scs) |
| `characterization/` | [test/characterization](characterization/README.md) | [test/characterization](characterization/tb.scs) |

原功能族根目录的本记录与 `run-sources.json` 一并迁入 `test/`。当前命令应从对应的 `test/<对象>/` 目录执行。

## 执行身份

- 实际后端：Cadence Spectre `21.1.0.509.isr12`，64 bit。
- 每份 `tb.scs` 从各自目录运行，命令参数为 `spectre -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1`。
- 同时最多运行 4 个 Spectre 进程。源文件上传后冻结，完成后下载日志及 PSF。
- [run-sources.json](run-sources.json) 保存原五组以及 ideal、basic 的 VA/网表 SHA-256，包括系统共用的 core。CDS 与 pingpong 的原记录尚未登记输入 SHA-256，执行与观察见后文；不能把这份七组清单当作九组完整输入清单。该文件不是自动评分结果。
- 原始记录保留在仓库被忽略的 `runs/r01-circuit-assets/`：`attempt-02/` 的四组成功结果、`attempt-03/` 的交错组成功结果，以及失败尝试。`observations.json` 保存从实际 PSF 读取的观测点。

读取波形时仅复用 `benchmark/material/historyref/legacy-authoring/checkers/adc_linearity.py` 的 `read_psf` 解析函数，没有调用其 ADC 评分逻辑。下列数字取自保存点的线性插值或仪器的实际 `$strobe` 报告。

源码、网表与本记录随仓库保存。原始日志与波形为 local-only，不随本次提交发布；下列历史观测不构成公开原始数据包。

## 已观察到的行为

| 工程 | 实际运行及关键观测 |
| --- | --- |
| 连续采样核心 | 17 µs 完整瞬态，5,719 个保存点。两个相同 8 ns 采集窗后，在 150/190 ns 观察到约 0.828/1.173 V；长采集后约 1.601 V，前拍历史没有被清空。长保持从 502 ns 的约 1.598 V 降至 16.39 µs 的约 1.476 V；更漏的实例同期降至约 1.163 V。复位期间名义初值恢复至约 0.9 V，零初值实例恢复至约 0 V。 |
| 同步四通道 | 45 µs 完整瞬态，15,497 个保存点。1.3/3.1/7.1/13.1 µs 的 `dout` 分别等于对应的 `held0/1/2/3`，约 0.398/0.791/0.977/1.326 V。21.1 µs 重读通道 0 为约 0.360 V，显示等待期间仍有下垂；34 µs 复位后的输出无效，未把复位电压当作一帧新样本。 |
| 共享采样级 MUX | 7 µs 完整瞬态，8,559 个保存点。1.6 V 通道长采集后约 1.603 V，切到 0.2 V 仅采集 5 ns 后仍约 1.174 V；再切回高电平短采集约 1.307 V，体现共享前拍。低电平长采集后约 0.204 V。读出暂停时内部状态仍变化；复位释放时 track 已高的最后一次采集正确标记为通道 2。 |
| 响应驱动表征 | 4 µs 完整瞬态，5,930 个保存点。nominal、slow、leak 均完成两轮，timeout 完成两轮尝试并报告采集超时，有效轮数为 0。nominal 的采集报告为 67/74 ns，slow 为 232/256 ns；高目标轮的 1 µs 保持漂移分别约 −6.982 mV 与漏电条件的 −68.234 mV。异常轮没有伪造零漂移结果。 |
| 时间交错 | 4 µs 完整瞬态，17,800 个保存点。每组实际读出 38 个有效样本，中途复位前后各 19 个，序号重新从 0 开始；初次读出及复位后等待期间无效。支路 1 的偏移条件记录约 12 ns 更晚的保持时刻，并改变采样值。读出后的 `serial` 与对应支路在读出沿的实际保持值一致，插值差异最大约 1.8 nV。该数字只核对连接与保存路径，不是电路精度或模型误差。 |

五组最终运行均为 0 个 Spectre 错误；检查到的所有保存值有限，时间严格递增，末点覆盖各自停止时刻。参数对照仍是同一工程中的运行条件，没有按实例或波形增加题目数量。

## 失败尝试、警告与剩余边界

首轮 core 网表使用了没有续接的多行 PWL，Spectre 在读网表时失败；随后改为单行向量。`attempt-02` 的交错模块把保留字 `branch` 用作端口名，编译失败；改为 `branch_id`，并将序号端口明确为 `sample_index` 后，在 `attempt-03` 重新运行成功。原失败日志保留，未拿未执行瞬态的结果充当通过。

最终日志保留了安装环境的 `CDS_AHDLCMI_ENABLE` 已弃用警告。表征工程还报告没有显式地节点、由 Spectre 加入 gmin；它的全部激励来自 VA 端口贡献。该工程成功完成了瞬态，但尚未验证这种连接在其他仿真器中的处理。表征指标节点是编码后的数值通道，例如 1 V 表示 1 ns，不表示实际器件承受数百伏。

独立子 agent 对五组源码、接口、状态与 README 做了只读审查，并确认保留字问题；修正后未提出其他行为问题。主 agent 另读取了最终实际 PSF，核对上表现象。当前证据未覆盖全部边沿重合、参数极值、观察步长敏感性、PDK 或温度条件，也未证明 EVAS/ngspice 已能复现。

数据建模仍应使用有来源的独立数据。本批 core 的名义参数没有对真实采样级拟合；本轮运行成功不替代后续题目参考解与独立 checker 的作者校准。

## 追加资产：理想边沿 track/hold

2026-10-12 追加 [ideal/](../module/ideal/README.md)（`r01_track_hold_ideal`，事件瞬时采样语义）及其台架，并在同一后端完成一次成功运行。

- 实际后端：Cadence Spectre `21.1.0.509.isr12`，64 bit，主机 `thu-sui`，命令参数与五组资产一致；返回码 0，0 错误，5,136 个接受步，17 µs 完整瞬态，5,137 个保存点，全部数值有限、时间严格递增、末点 17 µs。
- 远程目录 `/tmp/jinzhihong/r01-ideal-20261012`；输入 SHA-256 上传前后逐一核对，共享 `core/track_hold.va` 哈希与 attempt-02 记录一致（`65252f9e…`）。日志与 PSF 保留在本地被忽略的 `runs/r01-circuit-assets/ideal-run/`。
- 实际观测（保存点线性插值，复用 `adc_linearity.py` 的 `read_psf`）：
  - 启动保持（5 ns）：`ideal`=0.900000 V（`vinit`，无虚构采样），`ref`=0.899978 V；
  - 复位优先期间（40 ns）：两者 0.900000/0.899983 V；复位释放后跟踪段（100 ns）：`ideal`=0.200000 V 精确跟随，`ref`=0.237385 V 仍在建立；
  - 第一个 8 ns 短窗结束（148.15 ns）：`ideal`=1.600000 V 精确等于穿越时刻输入，`ref`=0.826496 V——与 attempt-02 在 150 ns 记录的约 0.828 V 一致，确认同源 core；
  - 长保持 0.6 µs 至 16.39 µs：`ideal` 保持段 max−min = 0.000e+00 V（严格冻结），末点 1.600000 V；`ref` 下垂至 1.476102 V，与 attempt-02 记录的约 1.476 V 一致；
  - 末次保持（16.9 µs）：`ideal`=1.300000 V，`ref`=1.299248 V。
- 日志保留既有 `CDS_AHDLCMI_ENABLE` 弃用警告；拓扑检查提示 `ideal`、`ref` 两节点单连接（理想电压输出，无负载），与预期一致。
- 该运行只覆盖本台架的默认参数；边沿重合、参数极值、EVAS/ngspice 复现仍未验证。

## 追加资产：无注入无漏电 track/hold（basic）

2026-10-12 追加 [basic/](../module/basic/README.md)（`r01_track_hold_basic`，连续状态、保持 `rate=0`）及其台架，并在同一后端完成一次成功运行。

- 实际后端：Cadence Spectre `21.1.0.509.isr12`，64 bit，主机 `thu-sui`，命令参数与此前一致；返回码 0，0 错误，5,141 个接受步，17 µs 完整瞬态，5,142 个保存点，全部数值有限、时间严格递增、末点 17 µs。
- 远程目录 `/tmp/jinzhihong/r01-basic-20261012`；输入 SHA-256 上传前后逐一核对，共享 `core/track_hold.va` 哈希与 attempt-02 记录一致。日志与 PSF 保留在本地被忽略的 `runs/r01-circuit-assets/basic-run/`。
- 实际观测（保存点线性插值，复用 `read_psf`）：
  - 采集与复位段与 core 近似逐位一致：100 ns 处两者同为 0.237391 V，40 ns 处同为 0.899983 V；
  - 前拍记忆保留：第一个 8 ns 短窗末（148.15 ns）basic 为 0.824900 V，第二个相同短窗末（188.15 ns）升至 1.169117 V；与 core 的 0.826493/1.171255 V 相差 mV 级，来自 core 注入历史进入窗口初值；
  - 保持严格冻结：0.5025–16.3995 µs 保持段 max−min = 4.4e-14 V，比 `vabstol=1e-7` 低约 7 个数量级，是结构性归零后的积分器数值残余；同期 core 下垂至 1.476102 V，basic 保持 1.596081 V 不变；
  - 长窗末 1.596081 V（core 1.596601 V），末次保持 1.299577 V（core 1.299248 V）。
- 日志保留既有 `CDS_AHDLCMI_ENABLE` 弃用警告与单连接节点提示，与 ideal 运行一致。
- 同样只覆盖默认参数这一套激励；边沿重合、参数极值、EVAS/ngspice 复现仍未验证。

## 追加资产：相关双采样（cds）

2026-10-12 追加 [cds/](../system/cds/README.md)（`r01_cds_sampler`，ph1 参考拍 + ph2 信号拍差分输出）及其台架，并在同一后端完成一次成功运行。

- 实际后端与命令参数同前；返回码 0，0 错误，2,702 个接受步，1.5 µs 完整瞬态，2,703 个保存点，全部有限、时间严格递增。
- 远程目录 `/tmp/jinzhihong/r01-cds-20261012`；输入 SHA-256 上传前后逐一核对。日志与 PSF 保留在 `runs/r01-circuit-assets/cds-run/`。
- 实际观测：550 ns 处 CDS 输出 1.600962 V（误差 +0.96 mV），单 core 对照 1.601664 V（+1.66 mV）；1100 ns 处 0.201345 V（+1.35 mV）vs 对照 0.202048 V（+2.05 mV）。固定 pedestal 的共同分量受到差分抑制，残差与两拍漏电间隙的解析估计一致。`voff=10m` 失调实例输出与名义实例差 11 µV，共同失调受到抑制，非理想保持与有限建立仍可留下残差。配对完成前 `valid=0`、`vout=0`。

## 追加资产：乒乓采样（pingpong）

2026-10-12 追加 [pingpong/](../system/pingpong/README.md)（`r01_pingpong_sampler`，反相窗口、电平选择保持支路）及其台架，经一次失败修正后在同一后端完成一次成功运行。

- 失败尝试：初版把 `transition()` 写在条件分支内，Spectre AHDL 编译报三个 `VACOMP-2143` 错误（模拟算子不能条件执行）。改为门控求和的无条件贡献后通过。首次成功运行的台架中 `vin` 902 ns 阶跃与 `ph1` 下降沿重合，held1 多吸收约 1.5 mV（穿越前 0.1 ns 输入已在爬升）；把阶跃移至与沿分开 2 ns 后重跑，数值与解析一致。两次日志均保留。
- 最终运行：返回码 0，0 错误，4,514 接受步（修正后台架为 4,527），1.4 µs 完整瞬态，全部有限、时间严格递增。远程目录 `/tmp/jinzhihong/r01-pingpong-20261012`；日志与 PSF 保留在 `runs/r01-circuit-assets/pingpong-run/`。
- 实际观测：首次采集完成前 `valid=0`；250/350/450 ns 交替输出完全建立的 1.6 V 样本（1.6011–1.6017 V）；550 ns 支路 1 输出 0.611029 V——输入在窗中段跳变、50 ns 部分建立的 9.1 mV 残余 + pedestal，解析吻合；850/950 nm 两支路一致输出 0.601925 V；1150/1250 ns 交替输出 1.2017/1.2018 V。支路号按相位正确交替。
- 边沿重合的敏感性在此台架中有直接证据（上述 1.5 mV 偏差），已在 README 记为约定：输入与控制边沿应分开。
