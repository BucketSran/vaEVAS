# 四后端支持范围实测

最新的[采样保持与一阶滤波精度测试](#precision-pilot)于 2026-10-10 完成。
下方先保留旧批次身份和结果，两个批次不合并计数。

本轮使用服务器实际执行。结论更新在唯一的[支持总表](../../../evas/docs/COMPARISON.md)，
本页保存逐条件结果、判据和证据边界；首轮收据为 [20261009.json](20261009.json)，
Gnucap 时间分辨率补测为 [20261009-timegrid.json](20261009-timegrid.json)。
当前表采用补测后的 Gnucap 结果和[新的 EVAS 核心验收](20261009-core-evidence.json)，首轮失败和原始判定继续保留。

## 版本、范围与执行身份

EVAS 为 main `6ee1ebaaea827dc52b506984d732aa74a74bc6e8`、0.14.0 / IR18。
运行时源码未改，现有工作区差异是文档与验证资产。服务器新建隔离目录、复制源码、
锁定依赖并重新构建 release 内核，SHA256 为
`5f569a5aad2f3e0627d7a89841853eee01a4b51c010839d3d8b4a9f47662c59f`。
内核自报 build_revision 为空。原 BUILD 缺实际编译器哈希与 Cargo.lock 字段，不能补造这些字段。
本轮从 main `5d357251` 新建隔离目录，记录实际 cargo/rustc 路径、哈希、版本和 Cargo.lock，
以 `--offline --locked --release -j 1` 重新构建，再运行原 12 条核心条件。新内核 SHA256 为
`ae6fcaf25770ebefe0fac8e226aeec952068f84a69e7d4c5aa1977b6e8b5caf5`。
两轮保留源码的 138 个文件逐一核验哈希相同，其中生产依赖为 106 个文件。
12 份归一化观察的时间与节点电压 rows 逐项相同。新身份链用于新执行，原收据不回填。
专项和 Gnucap 补测仍使用各自原身份。

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
本轮再执行 12 个 EVAS 核心条件和 2 个 Spectre 输出格式预检，合计 **193 个配置尝试**。
主比较仍为 108 个位置；12 个 EVAS 核心位置和 13 个 Gnucap 专项位置使用新记录，其他位置复用原收据。
Spectre 两次预检另列，不增加条件数，也不替换原先的 I。

## 核心 12 条件

core-v1 源码、刺激、网格、检查器和原资格门槛保持不变。
请求 `reltol=1e-5`、`vabstol=1e-7 V`、`iabstol=1e-12 A`、`maxstep=200 ps`。
Spectre 实际瞬态 reltol 为 `1e-6`，EVAS 响应回显 `1e-5`，不声称同名容差等价。

下表是当前结果；✓ 是原 core-v1 有限观测验收通过，W 表示可解析波形但未完成验收，
C 表示编译失败，R 表示瞬态失败无波形。W 的正式判定为 I，C/R 为 X。
EVAS 采用新执行与完整身份链，**12 项 P**；其余后端保留首轮的 **27 项 I、9 项 X**。

| 条件 | Spectre | OpenVAF-R + ngspice | Gnucap | EVAS |
| --- | --- | --- | --- | --- |
| VR-01 | W | W | W | ✓ |
| EX-01 | W | W | W | ✓ |
| EV-SH-01 | W | R | W | ✓ |
| EV-HC-01 | W | R | W | ✓ |
| EV-HC-02 | W | R | W | ✓ |
| TM-01 | W | R | W | ✓ |
| CP-01 | W | W | W | ✓ |
| CP-02 | W | W | C | ✓ |
| SI-01 | W | C | W | ✓ |
| CO-SH-01 | W | C | W | ✓ |
| CO-HC-01 | W | R | W | ✓ |
| CO-VCO-01 | W | W | C | ✓ |

OpenVAF-R/ngspice 的 5 个 R 是瞬态工作点失败，日志提示 timestep too small；SI-01 的层次语法
和 CO-SH-01 的事件 OR 在编译阶段失败。Gnucap 的 CP-02、CO-VCO-01 在 modelgen 编译阶段失败。
这些是所测输入和固定工具组合的结果，不是对所有等价写法的“不支持证明”。
这 5 个运行失败已通过[后续事件诊断](#ngspice-events)定位到实际编译产物中的事件条件丢失。
原 R 和 27 条件分母保留，诊断探针不替代原条件。

### 本轮补齐的取证与剩余缺口

首轮 Spectre 和 EVAS 都停在 `Missing source/units/uncertainty qualification`，尚未正式判行为对错。
本轮 EVAS 的新构建、新执行、完整源码依赖、实际编译器和内核哈希已连通；
[独立源码审查](core-source-review.json)来自 `support_publication_review` 审查 agent，
逐项阅读固定源码并从方程核对声明的解析锚点，覆盖全部 12 份模型；不是由输出吻合自动生成的证书。
现有 `actual_observation.py` 从实际响应推导时间序列化、输入 PWL 表示差、输出区间半径及原生记录来源，
再交给未修改的 core-v1 检查器。12 项的规定计分性质均通过，基础观察资格项齐全，原模型、网格、误差目标和分母未变。
**CP-02、CO-VCO-01 的精确模端点语义仍单列 I**，未纳入这个 P。新报告完整保留
`endpoint_semantics_status`、逐边界记录及 `separate_diagnostics`，没有把边界待核折叠掉。
具体是 22 条事件精确边界记录和 8 条环回精确边界记录均为 I；这些原本属于单列诊断，
不在规定计分性质内。有限时间不确定度下，边界的左右侧尚不能由这些记录唯一确定。

这个 P 是规定观察点的电压、计数、环回与一致历史检查通过。
事件规则要求存在一条与原生计数括区和全部相关输出相容的合法历史，
**不证明每个潜在实际回调时刻都满足窗口，也不证明点间连续波形或与 Spectre 完全一致**。
输出区间取自 EVAS 的实际证书，适配器检查其传输、包含关系和身份，没有独立重证整个求解器。

Spectre 安装版 User Guide pp.253–254、Reference pp.443、456 说明 strobe 在保存点求解，
Reference p.201 定义 PSFASCII precision。手册版本与文件哈希见[安装手册依据](../event-alignment/spectre-numerics-and-portability.md#sources-and-identity)。原 12 份 PSF 的行数均等于日志接受步数加初始点，
已核对原生保存记录、端口、时间顺序和身份；这些事实不能替代输入及导出误差资格。
原 12 份中有 9 份末行早于固定 stop，部分条件缺少精确中心。

两项新预检显式设置 `precision="%.17g"`、`compression=no`、`skipcount=1` 和步进日志；
源码、刺激、容差、最大步长、完整 strobe 请求及 stop 均保持不变。日志确认 17 位格式生效：

| 预检 | 实际结果 | 仍缺什么 |
| --- | --- | --- |
| EV-SH-01 | 45,837 行；覆盖 stop；规定网格间隔达标 | 2 µs 精确中心仍无记录 |
| CP-02 | 30,855 行；局部间隔超限消失；缺失精确中心由 3 个减至 1 个 | 末行仍早于 6 µs 约 1.70×10⁻¹⁸ s；一个环回中心缺失 |

两例仍为 I。17 位导出只能修复部分十进制表示损失，不能消除实际时间调度偏差。
Spectre 实际 PWL 输入在未保存回调时刻的全域误差界也尚未建立，不能把容差或采样点吻合当作该界。
后续先解决这些具体观察缺口，再扩展同一取证方法；不把 I 当成语言能力失败。

### EVAS 与 Spectre 的实测差异

EVAS 与 Spectre 还做了严格相同数值时间的波形交集比较，不做插值或最近点代替。
每例仅有 29–1088 个共同点，不能冒充整个导出网格的误差上界：

- EV-SH-01：事件窗外最大输出差 0.300 mV；含边界的最大差 0.5997 V，边界计数差 1。
- EV-HC-02：边界输出差 0.8 V；窗外本轮共同点无差异。
- TM-01：输出最大差 0.800 mV，边界状态与计数差 1。
- CP-02 与 CO-VCO-01：普通相位节点在环回边界的差接近 1；圆周相位接近不能抵消该普通电压差异。
- CO-SH-01、CO-HC-01 的共同点输出差分别约 0.050 mV、0.032 mV；这仍不补足正式资格。

<a id="ngspice-events"></a>

## OpenVAF-R 事件体被无条件执行

**本批 5 个 ngspice 运行失败的共同主因是编译后的事件语义错误。调整容差、步长和求解方法没有修复最小反例。**
2026-10-10 使用上表同一编译器哈希和两个镜像重跑，ngspice 仍自报 46。
未修改第三方工具、EVAS 内核或原验收门槛，也没有新增 Spectre 或 EVAS 仿真。
[诊断收据](20261010-ngspice-events.json)保存输入、设置回显、日志身份、原模型 MIR 摘录和观察事实。
MIR 是编译器生成机器码之前的中间表示。

原 EV-SH-01、EV-HC-01、EV-HC-02、TM-01、CO-HC-01 五份 VA 和网表全部复现初始工作点失败。
删去不连接被测模型的观测辅助源，失败仍然存在。继续缩减后，只保留下列三句就能复现：

```verilog
@(initial_step) n = 0;
@(timer(2e-6, 2e-6, 1e-9)) n = n + 1;
V(count) <+ n;
```

仿真在 1 µs 结束，早于第一次 2 µs 事件，本应始终输出 0。
实际在初始工作点就失败。删除 timer 句后，同一测试台输出全零；单独把初值改成 5 也能正确保持 5。
因此，不能把这次组合失败写成 `initial_step` 单独不受支持。

### 能跑完的反例进一步确认了原因

| 探针 | 应有行为 | 实际观察 |
| --- | --- | --- |
| timer 到时执行 `n=1` | 首个事件之前为 0 | t=0 就为 1 |
| 将 timer 从 2 µs 移到 20 µs | 改变事件日程 | 生成的模型库字节完全相同 |
| 将上述模型初值从 0 改成 5 | 首个事件之前为 5 | 模型库仍完全相同，t=0 仍为 1 |
| cross 越过 0.5 V 后执行 `n=1` | 初始输入为 0 V，应输出 0 | t=0 就为 1 |
| 每 0.2 µs 采样并保持斜坡输入 | 首次采样前为 0，采样之间保持 | 输出连续跟随输入；0.1028 µs 时已为 0.1028 V |

实际二进制导出的未优化 MIR 已经没有这些 timer/cross 条件。
常量赋值变成无条件存入 1，自增变成无条件读取状态、加 1、写回。
原五个模型的 MIR 复核得到同样结论；开启 MIR 导出前后，它们的模型库哈希完全一致。
两个迟滞模型甚至把上下阈值的两段更新接连执行，计数每次评估加 2。
TM-01 则无条件翻转状态。这些更新破坏了工作点迭代所需的稳定关系，解释了后续不收敛。
`timestep too small` 是运行阶段的表现，不能据此认定只是精度设置不当。

### 设置、接口和编译器分别排查

最小计数模型使用以下设置对照，均未生成波形。每项相对基线改变所列因素：

| 设置 | 具体变化 | 生效依据 |
| --- | --- | --- |
| 基线 | reltol=1e-5，vntol=1e-7 V，abstol=1e-12 A，trap | 分析后 option 回显 |
| 积分方法 | trap 改为 Gear，最高阶数仍为 2 | 分析后回显 |
| 迭代次数 | itl1 从 100 改为 1000，itl4 从 10 改为 100 | 分析后回显 |
| 紧容差 | reltol=1e-7，vntol=1e-9 V | 分析后回显 |
| 松容差 | reltol=1e-3，vntol=1e-6 V | 分析后回显 |
| 小步长 | 最大步长由 10 ns 改为 1 ns | 实际 tran 命令；初始化即失败，没有接受步可供核验 |
| UIC 诊断 | 跳过工作点 | 实际命令和跳过工作点日志；仅作诊断，不作为等价验收设置 |
| 关闭编译优化 | `-O 0` | 实际编译命令和仍无事件条件的未优化 MIR |

因此，**编译器缺口有直接证据；求解设置不是恢复这些丢失事件条件的方法。**
OSDI 接口仍需单独看待：ngspice 46 能加载 0.4 模型库，但使用的是 0.3 的功能。
这不等于它不支持动态状态，也不能解释已经在 MIR 阶段丢失的条件。
本次没有建立“另有一个接口缺陷导致这五例失败”的独立证据。
公开 ngspice 46 源码把 prev_state 和 next_state 指向同一当前状态数组，
与重复模型评估时自增或翻转状态的失败机制相符。

公开 OpenVAF-R `v24.0.2mob` 的
[事件 lowering](https://github.com/OpenVAF/OpenVAF-Reloaded/blob/fdf2522b70f42793f64b1c72f0195c96dea0cc19/openvaf/hir_lower/src/stmt.rs#L21)
和 [retained 状态](https://github.com/OpenVAF/OpenVAF-Reloaded/blob/fdf2522b70f42793f64b1c72f0195c96dea0cc19/openvaf/hir_lower/src/body.rs#L17)
也支持此解释；宿主处理见
[ngspice 46 load](https://github.com/imr/ngspice/blob/ebdaf58ec76a06ffaac7e0f138360dd1cf5ee4b6/src/osdi/osdiload.c#L137)。
接口版本说明见 [Reloaded README](https://github.com/OpenVAF/OpenVAF-Reloaded/blob/fdf2522b70f42793f64b1c72f0195c96dea0cc19/README.md)。
编译器自报版本仍是 unknown，不能由安装目录反推它一定来自该公开提交。
本结论依赖本批实际二进制及其产物，不外推到所有 OpenVAF 版本。

这轮只给原表的失败补充原因，不增加通过数。特别是 transition 所在组合已经在事件状态阶段失败，
不能用这些失败证明 transition 单独不可用；层次、事件 OR 和专项编译失败也没有因此解决。
EVAS 的优势与后续范围见 [EVAS 定位](../../../evas/README.md)：应以电压域模型的正确状态和历史行为证明价值，
不能由其他工具的一个缺口推出全面精度或性能优势。Gnucap 已有行为能力，仍需按相同要求完成比较。

### 诊断材料与复核

共 39 个诊断配置，各执行一次编译和一次 ngspice 仿真调用，另有工具身份查询。
其中原模型重跑 5 个、缩减与控制 6 个、代码生成探针 7 个、首轮设置 8 个、
带分析后参数回显的设置复核 8 个、原模型 MIR 复核 5 个。首轮设置缺少分析后的回显，
因此另行复核；两轮结果都保留，不把重复执行计入能力表分母。全部配置的容器与进程清理均已确认。
沿用串行锁、单阶段 90 s、4 GiB 内存、32 MiB 单文件和 256 MiB 条件目录监控。

原始材料是 **local-only**，归档在 `runs/ngspice-openvaf-diagnosis/raw.tar.gz`，
SHA256 为 `e389ae362bea84a0f7690c2aed92c4d7a7c03d6d98e41e17f8ed4d19406050e5`。
内含模型、网表、实际编译产物、MIR、波形、运行驱动、执行命令和逐文件清单。
服务器原目录保留。收据不是公开下载地址，也不代表已交付公共复现包。
已解压材料可用下列命令复核；脚本验证各轮清单、输入与产物身份，再读取事实，不重新运行仿真：

```sh
python3 -B experiments/backends/support/ngspice_event_report.py \
  runs/ngspice-openvaf-diagnosis/raw/ngspice-openvaf-diagnosis-20261010 \
  runs/ngspice-openvaf-diagnosis/reanalysis.json
```

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
python3 -B experiments/backends/support/core_report.py \
  runs/core-evidence-20261009 runs/core-spectre-evidence-20261009 \
  runs/support-comparison-20261009 experiments/backends/support/core-source-review.json \
  runs/new-core-reanalysis
```

执行入口为 `probes.py run INPUTS --output NEW_DIR --backend BACKEND --profile PROFILE`。
它复用维护的四后端网表、工具身份、原生读数及进程清理工具；真正远端执行还需本轮外层
串行锁与目录输出监控，不能把 profile 文件当资源授权。机密/机器相关 profile 和完整输出不提交仓库。
补测输入使用 `probes.py freeze NEW_INPUTS --cards SELECTED_CARDS --gnucap-time-bits 24` 冻结。
只改 Gnucap 的时间分辨率；对照测试确认其他后端、模型、网格和判据保持不变。

主比较与设置复核的清理收据全部确认完成。精简收据、模型和检查器是 repository-contained；
原始波形、完整日志、冻结输入、实际请求与二进制为 **local-only**，保存在项目可见入口
`runs/support-comparison-20261009/`。核心补测分别在 `runs/core-evidence-20261009/` 和
`runs/core-spectre-evidence-20261009/`，服务器原目录也保留。`core_report.py` 复核原始清单，
用现有适配器和原检查器重算，并另存新报告。哈希不是公开下载地址。
本轮可支持开发文档的实测说明，尚不能宣称独立论文评价、全面 Spectre 对齐或完整公开复现已完成。

<a id="current-main"></a>

## 2026-10-11 当前 main 复验

使用已合入的 **`fc7e57fd`** 重新构建 EVAS，重新编译原 VA，并保留原模型、刺激、
观察时刻、配置和检查器。**21 个固定条件、74 个配置，EVAS 全部通过原验收。**
这是已有能力在最新代码上的复验，不增加语言支持范围，也不是新独立论文集。

| 复验范围 | 条件数 | EVAS 配置通过数 |
| --- | ---: | ---: |
| 原采样保持与一阶滤波精度集 | 8 | 32/32 |
| strobe 采样→边沿→滤波及采样→积分 | 4 | 16/16 |
| 近邻 timer 及连续消费者 | 3 | 12/12 |
| 两级固定 slew | 3 | 8/8 |
| 外部平方输入的滤波直接通路 | 3 | 6/6 |

[本轮收据](20261011-current-main.json)记录当前提交、构建、内核、检查器及逐配置结果。
包版本仍为 0.14.0，IR18 未变；它们不是这次复验的唯一代码身份。
实际运行采用本机 macOS debug 构建，不作速度或 Linux 新构建通过声明。

本轮**没有新增远端仿真**。Spectre、ngspice 和 Gnucap 复用原批次实际证据，
不改其版本、失败配置和通过数。原精度集与 strobe 组合的检查器哈希保持一致；
slew 与滤波直接通路另核验原始文件清单，并在全部原生时刻重新查询 EVAS、运行独立检查。
旧基础语言与算子表没有全部重跑，仍按原执行版本展示。

可用现有入口重做组合检查：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -B experiments/backends/strobe/near_timer_run.py evas runs/near-timer-strobe-20261011/inputs-v3 runs/new-near-timer-main --kernel evas/rust_core/target/debug/evas-kernel
python3 -B evas/validation/slew_cascade/compare.py analyze --inputs runs/evas-backlog-20261011/slew-inputs --raw runs/evas-backlog-20261011/slew-collected/outputs --output runs/new-slew-main --kernel evas/rust_core/target/debug/evas-kernel
python3 -B evas/validation/slew_cascade/compare.py analyze --inputs runs/evas-backlog-20261011/slew-local-inputs --raw runs/evas-backlog-20261011/slew-local-collected/outputs --output runs/new-slew-local-main --kernel evas/rust_core/target/debug/evas-kernel
python3 -B evas/validation/filter_direct/compare.py analyze --inputs runs/evas-backlog-20261011/c4-inputs --raw runs/evas-backlog-20261011/c4-collected/outputs --output runs/new-filter-main --kernel evas/rust_core/target/debug/evas-kernel
```

这组命令依赖已有的本地原始材料，不能视作公开下载后的完整复现教程。
本轮 32+16 个精度及 strobe 请求通过原 `precision_run.py worker` 执行，继续调用原独立检查器、
生效设置读回、观察来源和时间覆盖检查。仅执行包装改为本机子进程，单次 90 秒超时。
首次尝试的 Linux 限额包装在 macOS 上不可用；其后两次初步执行的进程清理不满足要求。
这些记录保留在 `runs/comparison-current-20261011/`，不计入合格运行，也不判为 EVAS 行为失败。
随后重新执行全部 48 个请求，未放宽数值或观察判据。

完整响应、实际命令、日志、输入及输出清单保存在同一目录，为 **local-only**。
原严格边界失败、SEF-TIMER-18 的限定接受范围和 #131 draft 均未改变。

<a id="precision-pilot"></a>

## 2026-10-10 采样保持与一阶滤波精度测试

本批固定 8 个条件、4 个后端、4 档设置，完成 128 组配置。
EVAS 的 3 个定时采样条件另跑四档普通查询，追加 12 组，总计 140 组。
所有原始尝试均保留，没有用补测覆盖 strobe 拒绝。结果只在[支持总表](../../../evas/docs/COMPARISON.md#新精度测试)汇总，
[精简收据](20261010-precision.json)记录每次状态、实际设置、误差范围、选中配置与原始文件哈希。

### 测试范围与身份

采样保持的 SH-T-RAMP、SH-X-RAMP、SH-T-SMALL、SH-T-LONG 分别检查定时采样、
阈值采样、1 mV 刻度和 32 次连续采样。滤波的 LP-RAMP、LP-NONZERO、LP-SMALL、LP-IDT
分别检查变斜率、非零 DC 初态、小信号和等价 `idt` 反馈。
源码、输入、预算和配置写在 [precision-v1.json](../../../evas/validation/paper/precision-v1.json)。
它们来自开发需求，尚不是独立留出的论文测试集。

EVAS 生产源码取自 `6d23108d636514e7c8b296ad106b7652127f19ed`，没有行为修改。
服务器使用锁定依赖离线构建，release 内核 SHA256 为
`541836836a70ffeb12caf19904fab00c5d1a9b3223b5de9b2ad040f92c965024`。
收据保留源码清单、Cargo.lock、实际 rustc/cargo 版本和二进制哈希。
内核自报 build_revision 仍为空，构建记录另作来源证明，不补造自报字段。
Spectre 使用 21.1.0.509.isr12；OpenVAF-R、ngspice 46 和 Gnucap 沿用本页所列镜像，
本批重新核验工具身份。无法取得的版本号仍写 unknown。

### 精度设置实际改变了什么

采样保持把允许的事件时移与额外数值误差分开。一阶滤波逐段使用 80 位 Decimal 计算解析解。
预算推导、四档数值与实际生效差异见[评测标准](../../../evas/docs/COMPARISON-METHODOLOGY.md)。
Spectre conservative 预设使瞬态 reltol 为请求值的十分之一，日志和 PSF 元数据相符。
Gnucap 的实际 method=trap 与地参考经过核验；ngspice 保留分析后的积分控制读回。
此前执行收据的初步 verdict 保留，最终报告按这些资格重新判读，没有更改波形或数值门槛。

以 LP-RAMP 为例，下表是各档全部实际观察点的最大误差上界，单位 µV，目标为 1.01 µV。
不同后端的原生步数不同，均覆盖同一组必需边界和最大观察间隔；没有插值成共同网格。

| 后端 | 基础 | 只收紧容差 | 只减小步长 | 同时收紧 |
| --- | ---: | ---: | ---: | ---: |
| Spectre | 1.467706 | 0.367300 | 0.494824 | 0.354625 |
| ngspice + OpenVAF-R | 19.733028 | 2.837244 | 0.563426 | 0.653434 |
| Gnucap + modelgen-verilog | 32.790222 | 2.817119 | 0.497813 | 0.494399 |
| EVAS | < 0.000001 | < 0.000001 | < 0.000001 | < 0.000001 |

EVAS 四档输出在本例相同，误差上界约 5.63×10⁻¹⁴ V，已经包含保守的读写与时刻不确定度。
这是有限观察结果，不能写成精确解或所有动态路径的误差保证。
本例说明 Spectre 收紧容差后达标，ngspice 与 Gnucap 还需要减小步长。
同时收紧不保证误差逐次单调下降，最终仍按独立答案判断。

### 必须保留的限制与失败

- EVAS 的三个 timer 条件在四档强制 strobe 下均报 `unsupported_strobe`，原因是请求落在原子因果事件簇内。
  追加普通查询后，12 次均通过采样次数、时刻、读值和保持检查。原始响应注明
  `accepted_controller_frame` 或 `certified_causal_frame`，时间和值与 CSV 逐项核对。
  [物理事件次序](../../../evas/rust_core/src/schedule.rs)和
  [查询阶段选择](../../../evas/rust_core/src/transient_event_acceptance.rs)用于核验来源，
  没有对旧波形重采样，也不把查询宣称为强制求解接受点。该运行时的 strobe 组合仍有缺口。
  [后续固定 timer 修复](../strobe/README.md#timer-fix)用新内核重新运行并关闭这 12 组拒绝，原记录不变。
- ngspice + OpenVAF-R 的 16 个采样配置编译完成后均未取得波形，日志报初始瞬态工作点失败、步长过小。
  [先前最小反例](#ngspice-events)已确认这个编译器工件会丢失事件条件；本批复现组合失败，
  没有重新对这四个模型逐一审计编译中间代码。不能仅凭本批报错指定内部原因。
- Gnucap 阈值采样的基础档通过，预期 8 次事件；后三档仅有 4、7、3 次。
  固定选档规则保留基础档通过，但这些退化也是行为缺陷的实测证据，原因尚未定位。
- Gnucap LP-NONZERO 在四档均从 0 V 开始，输入和独立 DC 答案为 0.25 V。
  最大误差约 0.25 V。其他三个滤波条件能达标，因此不能把它写成一般 `laplace_nd` 不支持。
  旧短时常数滤波失败也仍保留，不被本批通过覆盖。

### 复验与材料位置

本轮沿用服务器串行锁，阶段超时 90 s、许可等待 30 s、进程内存 4 GiB、单文件 32 MiB。
外层轮询每条件 256 MiB 输出上限，所有进程与容器均确认清理。
原始数据留在项目入口 `runs/precision-pilot-20261010/collected/` 及现有服务器，属于 local-only。
精简收据校验全部归档与逐文件哈希，并保存分析依赖身份；哈希不等于公开下载地址。

```sh
python3 -B -m unittest discover -s evas/validation/paper -p 'test_precision.py' -v
python3 -B -m unittest discover -s experiments/backends/support -p 'test_precision_reporting.py' -v
python3 -B experiments/backends/support/precision_run.py freeze runs/new-precision-inputs
python3 -B experiments/backends/support/precision_report.py \
  runs/precision-pilot-20261010 /tmp/new-precision-report.json
```

冻结操作生成模型和网表，不启动仿真。实际执行入口为
`precision_run.py run INPUTS OUTPUT --backend BACKEND --profile PROFILE --family FAMILY`。
它仍需要本页所述串行锁、外层输出监控和本机工具配置。
`precision_query.py` 是三个 timer 用例的独立追加入口，保留原输入和普通查询执行身份。
本批执行时的冻结源码和追加查询脚本随原始归档保存；之后统一了执行与分析的设置资格检查，
重算报告不会改写旧执行收据。每次分析写新文件，不覆盖历史报告。

<a id="precision-v2"></a>

## 2026-10-11 三档精度扫描

本轮新跑 **8 条件 × 4 后端 × 5 配置，共 160 个组合**。采用独立 v2 checker，
同一数学答案分别检查 Q1、Q2、Q3。原八条件的源码、刺激、初态、事件容差完全不变；
观察计划加密，新增合法窗口端点及其两侧。原 v1 checker、条件卡、收据和成绩保留。
[主表](../../../evas/docs/COMPARISON.md#precision-v2-results)列出完整验收结论，
[新收据](20261011-precision-v2.json)保留全部配置、误差、资格问题、选中配置及后续退化。

### 实际执行与数学参考

EVAS 使用 main `826fefb12b5b068544be9de97e68f21e3c60e76f` 的模拟器源码，未作行为改动。
服务器离线 release 构建使用 Rust/Cargo 1.96.0，内核 SHA256 为
`262c157050ad7ab9dc8e3c86b6c2303c1355c8766cf66d10e8949d5e3b8b89b7`。
本轮未提交的内容是新 checker、执行工具和文档，其执行快照另有文件清单。
其他后端在同服务器新跑，工具、镜像与编译器身份逐批登记，没有用旧波形替代新扫描。

160 个组合全部尝试一次，**137 个取得波形，20 个 ngspice 采样保持配置工作点失败，
3 个 EVAS deep 滤波配置被精度认证拒绝**。八批均有完成及清理回执，逐文件和归档哈希已核验。
Spectre 滤波执行结束后 SSH 客户端断开；服务器的完成回执已确认 20 例成功结束，
随后仅收集原结果并继续未启动的三批，没有重复仿真或覆盖失败。

PWL 参考对实际表示的输入数值作精确有理数运算。一阶滤波使用逐段解析解、
80 位 Decimal 定向舍入及向外转换，记录参考自身的不确定度。
参考不调用 EVAS，也不由 Spectre 输出拟合。计算误差界后，对三档目标分别判分。
新校准包括合法与越界回调、跨窗缺证、旧值、漏事件、每个保持阶段的漂移、
非零滤波初态、跨输入折点、输入错误和参考／导出不够准。

### 一阶滤波的误差如何变化

以下是 LP-RAMP 在全部实际观察点的最大误差上界，单位 µV。
Q1/Q2/Q3 门槛分别为 10.1、1.01、0.101 µV。
本表只展示波形误差，完整通过还要求设置与关键观察合格。

| 后端 | base | tol | step | both | deep |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spectre | 1.467706 | 0.367300 | 0.494824 | 0.354625 | 0.008520 |
| ngspice + OpenVAF-R | 19.733028 | 2.837244 | 0.563426 | 0.653434 | 0.010371 |
| Gnucap + modelgen-verilog | 32.790222 | 2.817119 | 0.497813 | 0.494399 | 0.007741 |
| EVAS | < 0.000001 | < 0.000001 | < 0.000001 | < 0.000001 | 内部认证拒绝 |

EVAS 前四档在本例输出相同，误差上界约 5.63×10⁻¹⁴ V。它走本例的解析传播路径，
不能由此推广到全部非线性积分路径，也不能称为没有误差。
其 LP-RAMP、LP-NONZERO、LP-IDT 在 deep 下分别因内部误差界超过极紧预算而拒绝；
LP-SMALL 的 deep 成功。外部 Q3 通过不代表内部容差可以任意收紧。

Spectre 的四个滤波条件在 deep 下都满足 Q3 波形要求；日志与 PSF 仅以六位数字回显
最大步长，尚不能确认完整请求值。ngspice 四条件各有 Q2 数值达标配置，
但 TMAX/stop 仍缺独立生效证明；LP-RAMP、LP-IDT 的 deep 还缺输入折点一侧的观察。
这些是配置或观察资格问题，没有冒充数值超差。

Gnucap 的实际镜像内源码、构建源清单、安装目标、库符号和启动加载记录已配对，
可以追踪 `.tran` 的第四参数到求解器最大步长。前四档符合请求；deep 经 `dtmin` 取整后
为 4.882813×10⁻¹⁰ s，与冻结请求 4.8828125×10⁻¹⁰ s 不同，该档保留资格问题。
这不是逐位重建 Gnucap 的证明，来源审计材料及独立审查的哈希在新收据中登记。
Gnucap LP-NONZERO 五档仍从 0 V 开始，正确 DC 初态为 0.25 V，属于真实输出错误。

### 采样保持为何还有缺证

EVAS、Gnucap 的三个 timer 条件均在基础档满足 Q3。
Spectre 四个采样条件、EVAS 的 cross 条件，其输出误差都已小于 Q3 门槛，
但计数变化括定的回调区间跨越合法窗口的端点。v2 不再把区间与窗口相交就算合格。
因此新结论为“回调边界待证”，不称为这些波形已证明时间越界。

以 Spectre SH-T-RAMP 基础档第一次回调为例，观察区间从约 999.899999608 ns
到 999.900039600 ns，合法起点为 999.900000000 ns。数值差很小，
仍不足以证明回调没有早于窗口。旧 v1 成绩保留，新规则不裁掉区间外侧。
完整接受点清单只说明没有漏保存点，不能独立证明 handler 的实际时刻等于首个新计数点。

Gnucap 的 cross 条件在本轮五档均只记录 3 次事件，预期为 8 次，属于真实行为错误。
新观察计划比旧版更密，不能把旧基础档的 8 次事件拿来替换本轮结果。
ngspice 四个采样条件的五档设置全部在工作点失败；此前事件 lowering 诊断仍见
[编译器定位](#ngspice-events)，本轮没有重新审计这四个模型的全部编译中间代码。

下一步需要分别处理：同次运行的实际回调取证、精度控制的可靠读回或安装版本传递证明，
以及上述确切的行为错误和 EVAS 极严配置拒绝。缺证首先补观察与身份，不据此修改 EVAS 的数学边界。
#131 和其他组合的原验收范围未变。这批仍是开发条件，尚不能宣称独立论文评价集已完成。

### 校准、复核与资料位置

本轮新 checker 有 16 项校准，配置与报告有 7 项校准。
连同原检查器与报告回归，共 70 项检查通过。独立 Spec/Standards 审查覆盖数学参考、
配置资格、冻结输入身份和决策记录。审查中修复了空镜像身份被误当相同、执行条件卡未绑定冻结方案两项问题。
最终分析使用新身份，执行时的初步判定原样保留。

```sh
python3 -B -m unittest discover -s evas/validation/paper -p 'test_*.py'
python3 -B -m unittest discover -s experiments/backends/support -p 'test_*.py'
python3 -B experiments/backends/support/precision_v2_run.py freeze runs/new-precision-v2-inputs
python3 -B experiments/backends/support/precision_v2_report.py \
  runs/precision-tiers-20261011 runs/new-precision-v2-report.json \
  --step-evidence runs/precision-tiers-20261011/step-evidence.json
```

冻结不启动仿真。实际执行入口为 `precision_v2_run.py run INPUTS OUTPUT --backend BACKEND --profile PROFILE --family FAMILY`，
仍须使用既有串行锁、外层输出监控和本机配置。沿用每阶段 90 秒、4 GiB 内存、
32 MiB 单文件及 256 MiB 条件目录限制，无自动重试。
原始模型、网表、波形、日志、设置、源码快照、构建与清理证据保存在
`runs/precision-tiers-20261011/` 和服务器原目录，均为 **local-only**。
仓库内的新定义、脚本和精简收据可审查；哈希不是公开下载地址，上述重分析命令依赖本地原始材料。

<a id="precision-bindings"></a>

## 2026-10-11 配置绑定与补充取证

本轮补齐“运行前选 Q 档”的配置入口。首轮 v2 的定义、检查器、160 次执行资料和原成绩保持不变；
[新增收据](20261011-precision-binding.json)保存全部 176 个尝试的新分析，另保留每项原 v2 判定。
[可复用配置](../../../evas/validation/paper/precision-bindings-v1.json)包含 96 个条件／后端／Q 档选择，
其中 75 个有合格配置，21 个明确列出尚不可用的原因。75 个选择复用 45 个不同的运行配置。
它们仅适用于本批八个固定条件和工具身份，不能推广为任意模型的先验精度保证。

### 新跑了什么，复用了什么

新增 16 次实际运行均取得波形：四个 Spectre 采样保持条件增加同次回调日志；
Spectre、ngspice、Gnucap 各补跑四个滤波条件。后者采用 `deep_bound`，
请求 reltol=10⁻¹⁰、Vabs=10 fV、Iabs=10 aA、最大步长 **0.4 ns**。
Spectre 的实际 reltol 为 10⁻¹¹，其余两个为 10⁻¹⁰；原模型、刺激、事件容差、Q 门槛和观察计划不变。

EVAS 未改代码、未重跑，复用首轮同一源码和内核的完整原生记录。
四个补测批次均保留串行执行、资源上限、清理回执和全文件清单，归档哈希已核验。
新增批次的 15 个尝试完整通过 Q3，Gnucap 非零初态继续确认失败。
联合分析仍保留首轮 20 个 ngspice 工作点失败和 3 个 EVAS deep 认证拒绝。

以下为新增 deep_bound 的电压误差上界，包含原 checker 规定的不确定度。
这些数值只描述固定观察，不是全时域上界。

| 滤波条件 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | Q3 门槛 |
| --- | ---: | ---: | ---: | ---: |
| 斜坡 LP-RAMP | 5.539 nV | 7.581 nV | 5.163 nV | 101 nV |
| 非零 DC 初态 LP-NONZERO | 5.053 nV | 7.697 nV | 0.250 V，失败 | 101 nV |
| 小信号 LP-SMALL | 0.005145 nV | 0.007581 nV | 0.005164 nV | 1.1 nV |
| 等价 idt LP-IDT | 5.539 nV | 7.581 nV | 5.296 nV | 101 nV |

表中数值向上取整。选择可复用配置时仍按预先确定的顺序取首个完整通过者，
因此 ngspice Q3 的大信号滤波选中的是原 deep，小信号也不需要 deep_bound。
最终选择和实际参数见[主表](../../../evas/docs/COMPARISON.md#measured-settings)。

### 哪些证据补齐了

- **Spectre 回调时刻**：单实例采样模型在更新计数后输出 17 位 `$abstime`。
  共 56 条回调均与同次原生波形的计数变化、采样值对应，无漏行或重复。
  依据语言的 binary64 real 定义和安装版接口手册，规范格式可往返恢复机器时间。
  这允许判断恰好落在合法端点的记录；数学阈值根的不确定度继续保留。
- **Spectre 与 Gnucap 步长**：新增 0.4 ns 配置分别取得完整回显和 dtmin 整数刻度表示。
  原 deep 的回显不足和量化差异不改写。
- **ngspice 参数传递**：针对实际安装二进制核对 `.control tran` 到解析、任务参数、TRANinit 和 DCtran 的路径。
  显式正 TMAX/stop 可据此核验；其他容差与方法仍使用运行时回显。
  二进制 SHA256 为 `e9b0e776ac656de5e470f6b339c4a7254c961d77714b4b94f4b71be2422e7b46`，
  镜像 ID 为 `233b15bcc2bdfd40c915dbf6ed41d731306f64083885d1255ae1bdd37cdcb555`。
  这不是运行时 TMAX 回显，也不证明每个浮点时间间隔严格受限。
- **ngspice 折点两侧**：原 deep 和新增 deep_bound 的 LP-RAMP、LP-IDT 各有一处旧搜索漏检。
  新证据层在原 2.1 ps 距离内搜索全部原生记录，保存左右见证点。
  未更改观察义务，没有删掉任何数值评分点，原 v2 缺证结论仍在收据中。

Spectre、EVAS、ngspice、Gnucap 在每个 Q 档分别取得 8/8、7/8、4/8、6/8 的完整配置资格。
数值达标、行为结果和证据完整性分别保存在 `axes` 中。
EVAS 阈值采样数值达标，但回调区间仍跨合法窗端点，不能仅凭数学根自报改成通过。
Gnucap 阈值采样漏事件时没有完整数值评分，记录为不可评，而不是零误差通过。

### 校准和复验入口

新增绑定校准 14 项，连同原检查器和报告回归共 84 项通过。
正反例覆盖端点与早一 ULP、低精度或重复回调记录、错误计数、真实缺失与密集网格漏检、
数值通过但证据不足、工具／依赖变化以及禁止降档。
Spec 与 Standards 独立审查均检查了最终分析和配置选择；冻结前后执行与输入身份均核验。
本地生成检查还逐项确认 75 个合格绑定可重建原输入，21 个不可用绑定拒绝生成。
这项检查不算新的仿真运行，也不代替当前工具预检。

```sh
python3 -B evas/validation/paper/precision_binding.py --tier Q3
python3 -B -m unittest discover -s evas/validation/paper -p 'test_*.py'
python3 -B -m unittest discover -s experiments/backends/support -p 'test_*.py'
python3 -B experiments/backends/support/precision_binding_report.py \
  runs/precision-tiers-20261011 runs/precision-binding-20261011/batch \
  runs/new-binding-analysis --step-evidence runs/precision-binding-20261011/step-evidence.json
```

新分析通过校准和审查后，冻结到新的收据与注册表路径：

```sh
python3 -B evas/validation/paper/precision_binding.py \
  --freeze-analysis runs/new-binding-analysis \
  --receipt experiments/backends/support/NEW-binding.json \
  --registry evas/validation/paper/NEW-bindings.json
```

首次生成补测输入的入口是 `precision_binding_run.py freeze NEW_INPUTS`，不会启动仿真。
实际执行沿用 `precision_v2_run.py` 的后端适配器，须继续使用既有串行锁、外层输出监控和资源上限。
本地完整材料在 `runs/precision-binding-20261011/`，最终分析为 `analysis-02`；`analysis-01` 仅为中间诊断。
服务器补测目录为 `/tmp/chips-jinzhihong/precision-binding-20261011/batch`。
原始日志、波形、二进制审查资料和完整审查报告均为 **local-only**，仓库收据中的哈希不是公开下载地址。
公开重跑仍需要相应工具和运行环境；旧 v1/v2 的原始资料继续留在各自原目录。
