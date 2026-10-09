# 四后端支持范围实测（2026-10-09）

本轮使用服务器实际执行。结论更新在唯一的[支持总表](../../../evas/docs/COMPARISON.md)，
本页保存逐条件结果、判据和证据边界；首轮收据为 [20261009.json](20261009.json)，
Gnucap 时间分辨率补测为 [20261009-timegrid.json](20261009-timegrid.json)。
当前表采用补测后的 Gnucap 结果，首轮失败和原始判定继续保留。

## 版本、范围与执行身份

EVAS 为 main `6ee1ebaaea827dc52b506984d732aa74a74bc6e8`、0.14.0 / IR18。
运行时源码未改，现有工作区差异是文档与验证资产。服务器新建隔离目录、复制源码、
锁定依赖并重新构建 release 内核，SHA256 为
`5f569a5aad2f3e0627d7a89841853eee01a4b51c010839d3d8b4a9f47662c59f`。
内核自报 build_revision 为空；源码到二进制的关系由完整源码清单和实际构建收据补充。
后续补测复用同一二进制，并逐文件核对运行时源码一致。

| 后端 | 实际身份 |
| --- | --- |
| Spectre | `21.1.0.509.isr12`；二进制 SHA256 `72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f` |
| OpenVAF-R + ngspice | 编译器自报 `OpenVAF-reloaded unknown`；工件位于 v24.0.2mob 包，编译器 SHA256 `ca1037be094cbfecb1249a1f220c9c390bc265015dd177ec27800ed365d6ef3a`；ngspice 自报 46 |
| Gnucap + modelgen-verilog | 瞬态日志中的主程序/core-lib/default plugins 为 `snapshot 2026.07.29`；modelgen 版本查询未返回版本号，仍为 unknown；实际镜像 ID `sha256:6a094609a9dbe4e6e535625807569a212d681ecf6a66fa5d532344f10121a698` |

本轮主比较为 **27 条件 × 4 后端 = 108 个组合**：12 条 core-v1 和 15 条专项探针。
所有编译与模拟串行，单阶段 90 s、Spectre 等待许可 30 s、单进程 4 GiB、单文件 32 MiB；
外层还监控每条件目录并确认进程组/容器清理。没有自动重试，也没有做性能测量。

首次专项 v1 有 13 个模型省略方向声明；Spectre 可接受，EVAS/OpenVAF-R 拒绝。
统一补齐方向后，准备阶段又发现 EVAS 要求显式 `analog begin/end`，两个模块一并补齐。
v2 保持原数学、刺激、参数和预算，仅重跑 13×4；两个源文件未变的模型复用 v1 的 8 份实测。
未执行的中间准备目录不计实验。**60 份 v1、52 份 v2、48 份 core、3 份设置复核均保留，共 163 个后端配置尝试**；
编译失败的配置没有启动其后续瞬态模拟。最终结果不把首次失败冒充成未运行。
后续另执行 13 个 Gnucap 时间分辨率补测及 3 个细步长诊断，共 **179 个配置尝试**。
主比较仍为 108 个位置；其中 13 个 Gnucap 专项位置使用新设置，其他位置复用原收据。

## 核心 12 条件

core-v1 源码、刺激、网格、检查器和原资格门槛保持不变。
请求 `reltol=1e-5`、`vabstol=1e-7 V`、`iabstol=1e-12 A`、`maxstep=200 ps`。
Spectre 实际瞬态 reltol 为 `1e-6`，EVAS 响应回显 `1e-5`，不声称同名容差等价。

下表是执行结果；W 表示可解析波形、C 表示编译失败、R 表示瞬态失败无波形。
W **不是行为通过**：观察资料未达到 core-v1 检查要求，W 的正式判定均为 I；C/R 为 X。

| 条件 | Spectre | OpenVAF-R + ngspice | Gnucap | EVAS |
| --- | --- | --- | --- | --- |
| VR-01 | W | W | W | W |
| EX-01 | W | W | W | W |
| EV-SH-01 | W | R | W | W |
| EV-HC-01 | W | R | W | W |
| EV-HC-02 | W | R | W | W |
| TM-01 | W | R | W | W |
| CP-01 | W | W | W | W |
| CP-02 | W | W | C | W |
| SI-01 | W | C | W | W |
| CO-SH-01 | W | C | W | W |
| CO-HC-01 | W | R | W | W |
| CO-VCO-01 | W | W | C | W |

OpenVAF-R/ngspice 的 5 个 R 是瞬态工作点失败，日志提示 timestep too small；SI-01 的层次语法
和 CO-SH-01 的事件 OR 在编译阶段失败。Gnucap 的 CP-02、CO-VCO-01 在 modelgen 编译阶段失败。
这些是所测输入和固定工具组合的结果，不是对所有等价写法的“不支持证明”。

### 为什么两者都未判通过

Spectre 和 EVAS 的 24 份核心判定均为 `execution_state=completed`、`status=I`，
唯一性质记录都是 `observation: Missing source/units/uncertainty qualification`。
[检查器](../../../evas/validation/paper/criteria.py)的 `assess` 在此前置检查直接返回，
**还没有对电压、事件次数或边界行为正式判 P/F**。

适配器尚未提供经过资格核验的时间、电压和输入误差界，以及来源、输入和原生初值资料；
例如两端 VR-01 的 `time_error_s`、`voltage_error_V`、`input_error_V` 都是 null，
`qualified`、`source_validated`、`input_bounds_qualified`、`native_initial` 均为 false。
这表示适配器没有建立这些资格，不能反推实际输入或初值错误。已有源码清单和输出哈希，
也不能替代数值误差界。VR-01 在 69 个共同采样点的后端最大差约 `4.996e-16 V`，但仍得到 I。

这项资格针对有依据的有限观测误差，检查器明确不覆盖未观察到的点间短脉冲；
不能把 I 一概解释成“缺完整连续时间证明”。专项检查器使用另一套预先固定的有限采样判据，
因此其 ✓ 与 core-v1 的 I 可以同时成立，两份结果都保留。

语言语义、选定设置下的精度目标和本项目的证据资料要求分别判断。
例如 [Verilog-AMS LRM 2.4 §5.10.3.3](https://accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
允许 `timer` 在显式 `time_tol` 范围内放置事件点，并未要求两款工具选择同一个浮点时刻。
因此两端时刻不同本身不证明违反语言语义；但也不能据此豁免本轮所有事件差异。
要认定某个实现有语言缺陷，仍需给出合法模型、对应条款、实际设置与超出允许范围的可靠观察。
当前核心 I 记录不能证明 Spectre 和 EVAS 都无法实现相应语言能力。

### EVAS 与 Spectre 的实测差异

EVAS 与 Spectre 还做了严格相同数值时间的波形交集比较，不做插值或最近点代替。
每例仅有 29–1088 个共同点，不能冒充整个导出网格的误差上界：

- EV-SH-01：事件窗外最大输出差 0.300 mV；含边界的最大差 0.5997 V，边界计数差 1。
- EV-HC-02：边界输出差 0.8 V；窗外本轮共同点无差异。
- TM-01：输出最大差 0.800 mV，边界状态与计数差 1。
- CP-02 与 CO-VCO-01：普通相位节点在环回边界的差接近 1；圆周相位接近不能抵消该普通电压差异。
- CO-SH-01、CO-HC-01 的共同点输出差分别约 0.050 mV、0.032 mV；这仍不补足正式资格。

## 专项 15 条件

[冻结模型与判据](../../../evas/validation/support/README.md)要求输出误差 ≤1 mV、输入误差 ≤0.1 µV，
完整端点、有序有限值和规定最大网格间隔。只作有限观测判断，不给出全时域误差证明。
请求 reltol `1e-7`、vabstol `1e-9 V`、iabstol `1e-13 A`；基础最大步长为每例时间单位的 1/128。
Spectre 实际 reltol 为 `1e-8`。各后端 requested/effective 分开存档。
stop/maxstep 的日志十进制显示舍入也可能被读回器列为 mismatch，不能据此断言实际设置漂移；
reltol 的上述数量级差异则直接见于瞬态参数打印。

下表是**首轮固定设置的历史结果**：✓ 为有限观测达标，F 为超出预算，C 为编译失败，I 为观察资格不足。
Gnucap 的当前结果见后面的时间分辨率补测。

| 条件 | 检查范围 | Spectre | OpenVAF-R + ngspice | Gnucap | EVAS |
| --- | --- | --- | --- | --- | --- |
| AD-ramp | 固定延迟斜坡 | ✓ | C | I | ✓ |
| AD-after-stop | 延迟超过终止时间 | ✓ | C | I | ✓ |
| SL-catch | 限速追赶 | ✓ | C | I | ✓ |
| SL-reverse | 反向追赶 | F | C | I | ✓ |
| SL-tracking | 未触限速跟踪 | ✓ | C | I | ✓ |
| LP-nd | 单极点 nd | ✓ | ✓ | I | ✓ |
| LP-np | 单极点 np | ✓ | C | I | ✓ |
| DDT-pwl | 微分段内 | ✓ | ✓ | I | ✓ |
| NL-cubic | 三次反馈 | ✓ | ✓ | I | ✓ |
| VR-add | 参考节点与贡献累加 | ✓ | ✓ | I | ✓ |
| LANG-preprocess | 宏与参数 | ✓ | ✓ | I | ✓ |
| LANG-hierarchy | 静态层次 | ✓ | C | I | ✓ |
| LANG-functions | 函数/分支，阈值窗外 | ✓ | ✓ | I | ✓ |
| LANG-array-events | 循环数组，事件窗外 | ✓ | C | C | ✓ |
| LANG-vector | 静态电压向量 | ✓ | ✓ | C | ✓ |

EVAS 为 15 ✓；Spectre 为 14 ✓、1 F；OpenVAF-R/ngspice 为 7 ✓、8 C；Gnucap 为 13 I、2 C。
函数阈值、DDT 拐点和数组事件的原始窗口值保留且不计分；数组窗为 ±15.625 ms，
不证明源码中的 1 ns 事件定位达标。仅检验直接输入 AD/SL、一阶零初输入 LP，不能外推到一般算子组合。

OpenVAF-R 的 AD 两例编译器崩溃，slew 三例与 laplace_np 明确报不支持，层次和数组事件语法编译失败。
Gnucap 的数组事件与向量编译失败；其余 13 例最先在端点检查返回 I。
**此前将其归因为“时间打印精度不足”不准确。** 例如 SL-reverse 的停止时刻请求为
`7.450580596923828e-9 s`，原生记录为 `7.4505810000000005e-9 s`，已输出约 17 位有效数字。
后续核对源码与实跑确认，原设置 `dtmin=1e-15 s` 会量化实际时间，原终点并不在该时间网格上。
首轮检查尚未进入输出判分，所以这 13 项 I 不能解释成“不支持”，也不能证明输出已经正确。

## Gnucap 时间分辨率补测

安装镜像内 `apps/s_tr_swp.cc` 的 `TIME_t` 使用 `round(T/dtmin)` 保存时间刻度，
再乘 `dtmin` 转回物理时间。`include/u_sim_data.h::new_event` 也会按 dtmin 取整事件。
这与官方[瞬态命令文档](https://gnucap.org/dokuwiki/doku.php/gnucap%3Amanual%3Acommands%3Atransient)
所述的最小可分辨时间相符；`numdgt=17` 已实际生效，不是解决此次问题的控制项。
镜像源码摘录和哈希保存在补测收据指向的本地证据中，未修改第三方仿真器。

13 个原先端点不符的模型保持源码、刺激、网格、原 1 mV 输出目标及检查器不变，
只把 `dtmin` 改为时间单位的 `2^-24`，即 `5.551115123125783e-17 s`。
该二进制时间刻度能表示本批的起止时刻和网格。原生记录重新采集，**没有把旧时间列改写成请求时间，
也没有放宽 32 ULP 端点条件**。另两项编译失败复用原记录，不从分母中删除。

| 当前 15 项结果 | 条件 |
| --- | --- |
| 9 项通过 | AD-ramp、AD-after-stop、SL-catch、SL-reverse、SL-tracking、NL-cubic、VR-add、LANG-hierarchy、LANG-functions |
| 3 项输出超差 | LP-nd、LP-np、DDT-pwl |
| 1 项输入异常 | LANG-preprocess：参考节点应为 0.5 V，最大输入误差 8388608.5 V |
| 2 项编译失败 | LANG-array-events、LANG-vector，复用原记录 |

LANG-preprocess 的输出虽然接近答案，输入已经违反固定合同，不能计为行为通过。
该现象的工具或适配原因尚未定位，不据此宣称宏或参数本身不受支持。

对三个超差模型再将最大步长缩小 16 倍，仍使用相同模型、刺激和误差目标：

| 条件 | 原最大步长下的输出误差 | 最大步长缩小 16 倍 | 结论 |
| --- | ---: | ---: | --- |
| LP-nd | 0.405234 V | 0.405232 V | 两档均超出 1 mV |
| LP-np | 0.405234 V | 0.405232 V | 两档均超出 1 mV |
| DDT-pwl | 约 6 V | 约 6 V | 两档均超出 1 mV |

这些结果只证明所测模型与设置下的偏差，尚不构成对工具所有写法或内部算法的定论。
本次新增 16 次配置已全部完成并确认清理；两次收集分别校验 393、103 个输出文件。
`timegrid_report.py` 核验模型、镜像、输入清单，重新判读全部 16 份波形，保留原首轮收据。

## Spectre 的 slew 设置复核

只对 SL-reverse 增加三次新执行，原源码、刺激、观察网格和 1 mV 目标保持不变。
基础档与仅收紧容差档都产生 4.6875 mV 的最大有限观测误差；减小步长后改善：

| 配置 | 请求 reltol / vabstol | 请求最大步长 | 最大输出误差 | 有限观测 |
| --- | --- | --- | ---: | --- |
| 基础档 | 1e-7 / 1e-9 V | 7.276 ps | 4.6875 mV | F |
| 只收紧容差 | 1e-9 / 1e-11 V | 7.276 ps | 4.6875 mV | F |
| 只缩小步长 | 1e-7 / 1e-9 V | 0.4547 ps | 0.2930 mV | ✓ |
| 两者同时 | 1e-9 / 1e-11 V | 0.4547 ps | 0.2930 mV | ✓ |

后两档日志明确打印 `maxstep = 454.747 fs`，但现有设置读回器不识别 fs 单位，
其自动有效设置记录仍为 unknown。原生打印行和日志哈希另外保留，没有伪装成读回器已通过。
这组结果支持“本例受最大步长影响”的结论，不推断 Spectre 的内部实现；基础档 F 不被细档替换。

## 复核、再运行和材料位置

新检查器先通过正负校准；维护的 paper 执行器/观察工具 115 项检查通过。
独立审查先核对公式和范围，实际首轮另发现端口准入问题，已保留并统一修正夹具。
没有修改 EVAS 编译器、Rust 内核或原 core-v1 判据。

```sh
python3 -B -m unittest discover -s evas/validation/support -p 'test_*.py'
python3 -B experiments/backends/support/probes.py freeze runs/new-support-inputs
python3 -B experiments/backends/support/summarize.py runs/support-comparison-20261009 /tmp/support-summary.json
python3 -B -m unittest discover -s experiments/backends/support -p 'test_*.py'
python3 -B experiments/backends/support/timegrid_report.py runs/support-comparison-20261009 /tmp/support-timegrid.json
```

执行入口为 `probes.py run INPUTS --output NEW_DIR --backend BACKEND --profile PROFILE`。
它复用维护的四后端网表、工具身份、原生读数及进程清理工具；真正远端执行还需本轮外层
串行锁与目录输出监控，不能把 profile 文件当资源授权。机密/机器相关 profile 和完整输出不提交仓库。
补测输入使用 `probes.py freeze NEW_INPUTS --cards SELECTED_CARDS --gnucap-time-bits 24` 冻结。
只改 Gnucap 的时间分辨率；对照测试确认其他后端、模型、网格和判据保持不变。

主比较与设置复核的清理收据全部确认完成。精简收据、模型和检查器是 repository-contained；
原始波形、完整日志、冻结输入、实际请求与二进制为 **local-only**，保存在项目可见入口
`runs/support-comparison-20261009/`，服务器原目录也保留。哈希不是公开下载地址。
本轮可支持开发文档的实测说明，尚不能宣称独立论文评价、全面 Spectre 对齐或完整公开复现已完成。
