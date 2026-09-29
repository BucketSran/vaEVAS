# Spectre verification on thu-sui

## 事件检查器的独立校准补充

`test_event_review.py` 对原 E1 三项、E2 三项、C1 三项共 9 个既有条件，使用手算输出
断点和 `Fraction` 插值构造正控。输入来自冻结条件规范；期望输出不调用 checker 的
reference、history 或 PWL 辅助函数，也不从 EVAS/Spectre 输出生成。
手算依据是 E1 上/下沿计数分别乘 .1，以及采样器在复位为真时取初值、否则取
`.8-.1*t` / `.2+.1*t`，再按原 .01/.025/.04 微秒边沿形成显式输出折线。

负控包含漏/重复/错方向计数、漏采样、初态高电平伪采样、复位期间错采样、
释放时额外采样、实例串扰及额外有效更新。另检查 ±0.9/1.1 mV 容差两侧，
以及缺列、非有限值、重复时间、错误时间单位和缺尾。
重复事件若不改变任何输出，单凭波形不可检出；这类情况要由独立计数探针或内核事件记录验收。
这些是 checker 校准控制，不增加 31 条件的分母，也不是新后端执行。
原 builder、checker、DUT 和阈值保持原身份，正式资格仍为 I。

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_event_review.py' -v
```

## PR13 transition 0.6.1

实现提交 [`9850450`](https://github.com/BucketSran/vaEVAS/commit/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4)
修复历史误差未进入电压验收的问题。源事件在 `1e12 s`、延迟 `0.10005 s`、边沿 1 s 的
独立 Fraction 反例，旧版在 `vabstol=1e-9` 时接受约 `1.70e-4 V` 的误差且残差为零；
新版给出 `waveform_accuracy`，认证误差上界 `2.44140625e-4 V`。放宽到 `1e-3 V` 可接受，
实际误差满足该预算。这是显式检出精度不足，没有把原算法变成高精度算法。

历史起点、延迟时刻、斜率、目标和采样状态的区间一起传播，并经网络映射验收节点电压。
若输出点落入延迟生效区间，包围已生效/未生效两种可能；不因无法精确排序就遗漏误差，
也不无条件拒绝原有短脉冲。初始化、网络放大、跨事件采样和失败回退均有独立回归。
参考对象和数学边界见[历史误差说明](../../evas/docs/OPERATORS.md#历史误差与电压精度)。

本轮执行身份为 `pr13-transition-20260929-03`，固定 8 场景 × 两档 = **16 配置/后端**。
在原 0.6.0 的设置/阈值基础上新增 `strobeperiod=U/8, strobeoutput=all`，
强制 Spectre 包含 EVAS 的 257 个观察时刻，同时保留额外接受点。两后端仍各自对独立折线答案检查。
保持 Spectre 21.1.0.509.isr12、单线程、traponly、原容差、90 s/次及 30 s license 等待上限。
检查器先完成接受/拒绝校准，再冻结输入；不改原始波形或旧判据。

| 后端 | 满足有限观测判据 | 检查的输出点 | 共同网格点/配置 | 最大采样误差 |
| --- | --- | --- | --- | --- |
| EVAS 0.6.1 | 16/16 | 4,112 | 257 | 1.11e-16 V |
| Spectre | 16/16 | 4,368 | 257 | 2.67e-15 V |

粗档短脉冲现在有斜坡内部观察，满足原先的覆盖要求。旧不强制 strobe 的记录仍是
Spectre 15 符合、1 观察不足；使用新检查器重判，原 32 个后端配置的判定全部保留。
这两次实验观察设置不同，不能把新结果覆盖到旧实验上。运行文件回收哈希、日志设置、
网格完整性、源码/内核/检查器身份及逐配置结果见[收据](results/transition-0.6.1.json)。

本地检查：**155 Python、23 Rust、48 checker 方法**通过；离线锁定构建、all-targets
warnings-as-errors、rustfmt、CLI 示例、13 组设计数学与冻结材料身份检查通过。
新增 6 个 Fraction 方法覆盖历史误差；Rust 包含未提交候选的误差状态回退。
这些不是新增正式条件，原 31 条件分母不变，也没有重跑完整后端矩阵。

小型容差探针固定一条 769 点斜坡，`reltol=0`，每档 5 次，Apple M5/debug build。
`vabstol=1e-6/1e-9/1e-12 V` 都接受 768 步，Python transient 调用耗时中位数分别约
45.3/44.9/51.9 ms；`1e-16 V` 报精度不足。计时包含 JSON、子进程启动、求解及解析，
不含 VA 编译，不能用于估计相对 0.6.0 的认证开销或宣称性能排名。
当前收紧容差不自动增加时间步/运算精度；保守区间也可能拒绝实际误差较小的模型。

复现入口沿用下一节命令，在新的输出目录执行 `build --strobe`。
仓库包含输入生成器、检查器、回归和整理收据；原始波形/日志与本机计时探针仅本地和服务器保留，
尚未公开归档。全部结论限于声明参考和有限开发观察，不是连续时间全轨迹精度或正式资格证明。

## PR13 transition 0.6.0

PR13 同步已合入的 PR12（main `e6f04c4`），修复旧电压读取导致 transition 目标滞后的问题。
EVAS 0.6.0 / IR v6 的数学与代码路径见[算子手册](../../evas/docs/OPERATORS.md#transition)。
[收据](results/transition-0.6.0.json)固定本轮源码、内核、输入、检查器、逐配置结果及原始材料哈希。

执行前冻结 8 个场景 × 两档 = **16 配置/后端**；EVAS 与 Spectre 分别对独立的显式折线答案检查。
时间单位 U=2^-30 s；粗/细 max_step 为 3U、U/8，timer 容差为 U/1024。
Spectre 21.1.0.509.isr12 在 thu-sui 新执行 16 次，单线程、traponly、reltol=1e-8、
vabstol=1e-10、iabstol=1e-14，不强制 strobe。每次上限 90 s，license 等待上限 30 s。
日志的 step/maxstep/stop 只有有限小数位，按显示末位舍入区间核对请求，而非误称日志给出了完整精度；
波形终点另行核对。16 次均执行成功，所有回收文件的哈希与远端清单一致。

| 场景 | EVAS 粗/细 | Spectre 粗/细 |
| --- | --- | --- |
| 非零初值、延迟、非对称上/下沿 | 符合 / 符合 | 符合 / 符合 |
| 上升中反向 | 符合 / 符合 | 符合 / 符合 |
| 上升中同向延长 | 符合 / 符合 | 符合 / 符合 |
| 下降中反向 | 符合 / 符合 | 符合 / 符合 |
| 下降中同向延长 | 符合 / 符合 | 符合 / 符合 |
| 延迟队列中的短脉冲 | 符合 / 符合 | 观察不足 / 符合 |
| 重复相同目标 | 符合 / 符合 | 符合 / 符合 |
| 同刻新电压生成 transition 目标 | 符合 / 符合 | 符合 / 符合 |

EVAS **16/16** 满足有限观测判据，最大采样误差 1.11e-16 V；Spectre **15/16** 满足，
1 项因边沿内部无观察点而未满足覆盖要求。全部 Spectre 已输出点的最大误差为 2.67e-15 V。
粗档短脉冲只在约 12U、13U、14U 输出 0、0.5、0，两个斜坡内部没有点；
这些点符合答案，但不能据此宣布斜坡已验证。细档通过。原判定保留，不降低覆盖要求，也不诊断成数值错误。
本轮没有发现已观测点上的 EVAS/Spectre 数学差异，不能推广成任意模型或连续时间完全一致。

判据逐点检查波形，并在事件容差窗口外检查目标保持和事件采样时间；每条非平坦段必须有内部观察。
条件性波形裕量为 `1e-8 V + 4*(U/1024)*最大参考斜率`，后项覆盖这组固定例子的事件定位偏移，
不是拿 Spectre 结果估出的容差，也不是完整物理观测误差证明。原 31 条件的分母及正式资格不变。

本地检查：149 Python、21 Rust、47 个 Spectre checker 测试方法（其中新增 3 个），
locked/offline build、all-targets warnings-as-errors、rustfmt、CLI 示例均通过。
13 组 Fraction 设计数学核对及冻结验证材料身份检查通过；它们不是额外仿真配置。
原 PR13 和旧四能力联合检查点保留为历史，不能替代此轮 main 同步后的结果；本轮未重跑静态大矩阵。

可复现入口（Python 3.10+，服务器使用 python3.11）：

```sh
python3 -B experiments/dvs2-spectre-validation/transition_reference.py build --root runs/transition-new
python3 -B experiments/dvs2-spectre-validation/transition_reference.py evas --root runs/transition-new --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/transition_reference.py spectre --root runs/transition-new --spectre-profile /path/to/private-profile.json
python3 -B experiments/dvs2-spectre-validation/transition_reference.py check --root runs/transition-new --output runs/transition-new-analysis.json
```

`build` 冻结共同 VA、网表、数学折线、阈值和 checker 清单；`check` 拒绝身份漂移。
比较脚本、输入生成器、判据与整理收据在仓库内可取得；原始波形/日志仅本地和 thu-sui 保留，未公开归档。
准备目录 `pr13-transition-20260929-01` 未执行；正式 `-02` 首次服务器 Python 3.9 导入失败，
尚未启动 Spectre，改用已安装的 Python 3.11 后完成冻结的 16 次预算；无波形覆盖或隐式重跑。

## PR12 integer sequence 0.5.3

实现为 [`ba3c063`](https://github.com/BucketSran/vaEVAS/commit/ba3c06390cfaca6c34653fcc2f978d7c793a0958)，
同步 main 文档基线 `55f2fe3`，IR 仍为 v5。
[本轮收据](results/timer-0.5.3.json)记录源码/内核/检查器身份、实际命令及逐配置结果。

0.5.3 移除绑定阶段“一块内同一 integer 不得写两次”的限制。原有局部顺序代入、
原赋值重放与区间认证均未改；每次整数写入仍检查 signed 32-bit 范围，中间越界不会
被下一句覆盖隐藏。两次 `n=n+1` 应净增 2，三次应净增 3，具体推导及兼容性原则见
[事件手册](../../evas/docs/EVENTS.md#同块顺序赋值与同刻联立求解)。

本轮 **132 项 Python 方法、17 项 Rust 测试**通过；locked offline build、
all-targets warnings-as-errors、rustfmt 和 diff 检查通过。四项顺序赋值 Python 方法
替换旧的一项拒绝测试，覆盖 integer/real、timer/cross、初值、两次/三次更新、中间值、
覆盖赋值、周期电压反馈、网格/步长变化和中间溢出。新增 Rust 回归检查重复写后的
丢弃重试、缓存复用、残差失败及越界失败，确认已接受帧不变。
相同最终测试对旧内核产生 16 个拒绝错误和 3 个错误类型断言失败（均为子测试），
旧结果保留。首次新增测试有五个内部节点命名错误；改为显式导出该端口后通过，
未据此修改运行时或放宽预期值，原失败日志同样保留。

只重新执行受本次支持边界影响的专项范围及其控制：既有 `--extended`、
`--sequence-controls`、`--counter-rewrite` 三组共 **12 个 EVAS 配置**，全部完成，
**14 条历史均满足未修改的独立候选**，包含此前被拒绝的 4 个配置。
对应 Spectre 波形复用 0.5.2 收据中的相同模型、网表和条件；逐字节核对身份，
本轮 **没有新增 Spectre 执行**。

| 范围（各两档） | EVAS 0.5.3 | 复用的 Spectre 21.1.0.509.isr12 |
| --- | --- | --- |
| 连续两次 integer 自增、独立事件计数 | 输出 2，符合顺序语义 | 输出 1，`candidate_differs` |
| 连续两次 integer 自增及 real 电压反馈 | 输出 4，归一化计数 1 | 输出 2，归一化计数 0.5；`finite_inconsistent` |
| 非收缩反馈、real 常量/反馈顺序、单次加 2 控制，共 8 配置 | 全部符合原候选 | 全部符合原候选 |

检查器没有改答案或阈值，Spectre 的 4 个差异配置仍明确保留。另一次已完成的
18 配置最小诊断发现相同异常也涉及 real，且减小步长无效、加入观测可能改变结果；
独立复现输入及版本限制由 [Issue #16](https://github.com/BucketSran/vaEVAS/issues/16) 跟踪。
不将该版本的异常输出作为 EVAS 应复现的语义。

原 42 配置中另外 30 个配置没有在本轮重新执行，旧收据继续描述旧版本；因此本轮不报告
“新版 42/42 与 Spectre 一致”。未重跑静态全量、四后端矩阵或性能实验。动态 timer、
非线性事件、状态反馈 guard 等边界保持；原 31 条件的分母和完整 DVS 资格未改变。

输入及检查器可从仓库重新生成，完整原始结果和日志仅在本地 `runs/integer-sequence-053/`
保留，尚未公开归档。使用全新目录复现三组（以下以 extended 为例，另外两组换对应标志）：

```sh
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py build runs/NEW-EXTENDED --extended
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py evas runs/NEW-EXTENDED \
  --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py check runs/NEW-EXTENDED \
  --backends evas --output runs/NEW-EXTENDED-analysis.json
```

该命令重新运行 EVAS；重现 Spectre 结果还需可用的对应版本和独立运行环境，不能从本地
哈希推断公开数据已经可下载。

## PR12 timer hardening 0.5.2

2026-09-29：本轮实现固定于 `1a7757ddda5b784226bcd30c88e2af0e14b69f07`，
运行脚本修复固定于 `046f62f87ffa963205f2fd8c6c431168db5ca3b1`。
[0.5.2 收据](results/timer-0.5.2.json) 保存逐配置结果、原始失败、源码/内核/检查器身份、
Spectre 回传清单和本地原始证据包哈希；0.5.0、0.5.1 收据与原 31 条件矩阵不变。

修复了三个由独立反例确认的问题：

- **残差小不代表解准确**：原 IR 的顺序赋值形成精确反馈系数
  `0.5 + 0.49999999999999983`，精确解为 `2^54/3`；旧版返回 `2^52`，
  前向误差 25%，却通过残差与重放。新版从原 IR 独立进行区间代入和消元，
  包围事件后解，无法满足误差预算时报告 `event_accuracy`，不提交状态。
- **real 状态不能借用电压绝对容差**：电压保留 `vabstol + reltol*abs(v)`；
  real 状态仅用其自身数值的相对预算，integer 必须精确。`(1+2^-55)-1`
  的顺序赋值旧版静默得到零，新版拒绝；单位按 `2^-80 / 1 / 2^80` 缩放也覆盖。
  这是针对给定旧状态、采样驱动和编译后 IR 的逐事件认证，不是跨事件累计误差界。
- **三个根候选不完整**：`22*(15/22)` 的舍入候选及区间两端都不等于精确根 15。
  新版用四项乘积和的精确符号，在已有有效根区间内对 binary64 时间作有界二分，
  找到可表示精确根才缩为单点；一 ULP 邻近事件仍分开。端点区间非单点、
  不能先建立有限严格段内包围或根不可表示时，原有保守限制继续适用。

新增 Spectre 对照 **12 次**，全部正常执行；加上逐字节核对后复用的 30 个历史配置，
最终比较分母为 **42 个配置**。EVAS 0.5.2 完成其中 **38 个**，另外 **4 个明确拒绝**
重复整数赋值；不能写成 42/42 通过。原有 30 个配置全部完成并保持已有有限历史结论。

| 新增范围（各两档） | 配置数 | EVAS 0.5.2 | Spectre 21.1.0.509.isr12 |
| --- | ---: | --- | --- |
| 非收缩正反馈和负反馈控制 | 2 | -1、2/3 | -1、2/3 |
| real 常量顺序赋值 | 2 | 3 | 3 |
| real 顺序赋值带电压反馈 | 2 | 2 | 2 |
| 单次 `n=n+2`，再执行 real 反馈 | 2 | 4 | 4 |
| 连续两次 `n=n+1`，带 real 反馈 | 2 | 明确不支持 | 归一化计数 0.5、输出 2；原顺序候选不相容 |
| 连续两次 `n=n+1`，独立计数观察 | 2 | 明确不支持 | 整数输出 1，顺序候选为 2 |

最初未限制重复整数写入时，EVAS 在后两类分别得到 4 和 2，与 Spectre 不同。
独立观察计数将此差异与漏事件区分开；实数赋值控制相符，单次整数更新也相符。
因此这版对同一事件块内同一 integer 状态的多次写入返回 `unsupported_transient`，
保留实数顺序赋值。此限制比已观察反例更保守；不把 Spectre 输出硬编码成语言语义，
也不凭这些观测裁定 LRM 或推断其内部算法。两批原始分歧记录完整保留。

最终选取的 64 条普通 timer 历史、16 个明确前后交互、8 个同刻新值读取，以及原有
20 条仿射诊断历史均维持与 Spectre 的对应关系；新增支持范围内的 8 个配置含 10 条
共同历史，双方均与独立候选相容。同刻旧检查器的候选仍是旧值 0，双方读 1 仍记录
`candidate_differs`，没有为提高通过数而修改旧判据。

验证包括 **129 项 Python、16 项 Rust、44 项检查器测试**，Rust 测试以警告视作错误；
另有 16,408 次区间四则包围、2,054 次四乘积精确符号和 24 个独立有理数耦合解检查，
均包含在上述方法中，不另加到方法数。原来三个回归在 0.5.1 上分别暴露根认证拒绝、
错误解被接受和状态误差被接受；0.5.2 的失败回滚及缓存重试检查通过。

`evas/tests/benchmark_events.py` 冻结 1/8/32 节点 × 10/100 次事件，两个 release 内核
交替各重复三次，共 36 次执行。最终内核全部计数/状态正确，六组均满足预先固定的
5 秒、256 MiB 上限；候选最慢一次含启动约 0.747 秒，最大 RSS 6,045,696 字节。
只缓存最近一批事件的符号认证系数，缓存不随事件数累积。两次测量的速度差方向存在
波动，原始结果均保留，不声明加速或大型网络扩展性，也不用于仿真器排名。

一次六配置回放因归档的 macOS `._*.va` 元数据文件被旧脚本误读为源码而失败。
`046f62f` 改为只读取冻结设计中的文件名；用新 ID 重跑这六项，保留原始失败，
无新增 Spectre 执行、无模型或阈值变更。这六次基础设施失败不混入最终 42 配置分母，
也不在收据中隐藏。

认证仍可能保守拒绝合法问题，尤其接近零的 real 状态；不覆盖前端常量折叠、输入采样
或跨事件误差传播。动态 timer、非线性事件、状态反馈 guard、`transition`、`absdelay`
和 `slew` 继续明确不支持。本轮为开发与兼容性证据，完整 DVS 观察资格仍为 I。

复现新增组时分别给 `timer_settlement.py build` 加 `--extended`（4 配置）、
`--sequence-controls`（6 配置）或 `--counter-rewrite`（2 配置）；每组必须使用新目录。
之后的 `evas`、`spectre`、`check` 命令沿用下节入口。规模检查单独运行：

```sh
PYTHONPATH=evas/src python3 evas/tests/benchmark_events.py \
  --baseline /path/to/0.5.1-release-kernel \
  --candidate evas/rust_core/target/release/evas-kernel \
  --output runs/NEW-EVENT-SCALING
```

## PR12 timer repair 0.5.1

EVAS 0.5.1 的实现身份为 `e78d1abbda90d81f948f6a4f52540acf484b0748`。
本轮针对 0.5.0 对照暴露的两个问题分别修复，不改历史收据或原验证阈值：

1. **可表示零点的认证**（提交 `874ad5b`）：PWL 插值的中间除法虽有舍入，最终根可能
   恰好是 binary64 可表示数。若 guard 两端值 `a,b` 及到候选时刻的两侧时间差均有
   精确证书，就以完整二进制乘积比较证明 `a*(t1-t) = -b*(t-t0)`，将根区间收窄为点。
   因而 `19U*(8/19)=8U` 可以与 timer 认证为同刻；相差一个 ULP 的事件仍分别调度。
   端点不确定、根不可表示或证书不足时保留原区间，不以 epsilon 合并事件。
2. **同刻状态与电压的联立解**（提交 `e78d1ab`）：令旧状态为 `s−`、事件块赋值映射为
   `Phi`、电压贡献残差为 `F`，求解 `F(v+, Phi(s−,v+), t)=0`，再取得 `s+=Phi(s−,v+)`。
   当前映射和瞬态网络均为仿射，可代入后使用已有线性求解器，不需要靠声明顺序传播。
   每次试算固定从旧状态开始，同一块保留语句顺序，计数器不会随试算重复累加。
   最后重算未代入的原始电压约束并检查状态重放一致性，全部成功才一次提交。

`timer_settlement.py` 新增六个先冻结后执行的诊断电路：两档步长和两种声明顺序下的
跨实例/单实例三级链，以及两档下的正负反馈 `s=0.5*s+1`、`s=-0.5*s+1`。
候选值由方程独立得到，分别为 1、2 和 2/3；检查器同时检查计数、保持、采样时钟、
全部导出输入点、时间覆盖和有效设置。20 条历史包含链的生产者控制，不是 20 个新条件。

2026-09-29 完成最终 **30 个 EVAS 配置**：原 24 个配置全部可执行（0.5.0 为 16/24），
新增六个诊断也全部完成。对应的 Spectre 30 个配置均有成功结果：本轮在 thu-sui
**新执行 18 次**（12 个原组合配置、六个诊断），另 12 个隔离配置复用历史波形。
诊断先用旧内核执行 `-02`，修复后 `-03` 复用这同一组六份 Spectre 波形，不重复计数。
复用前逐字节核对条件、VA 与网表，核对原始文件清单及所有回传文件哈希。

下表仍选原组合配置中的终点/长序列、隔离配置中的普通/交互历史，避免重复计数：

| 范围 | 数量 | EVAS 0.5.1 | Spectre |
| --- | ---: | --- | --- |
| 普通 timer、初始化、实例隔离、终点及长序列 | 64 条历史 | 全部满足原有限判据 | 全部满足原有限判据 |
| timer/timer、timer/cross 明确前后关系 | 16 个探针 | 全部满足原判据 | 全部满足原判据 |
| 同刻 timer/timer 电压状态读取 | 4 个探针 | 均读新状态 1 | 均读新状态 1 |
| 同刻 timer/cross | 4 个探针 | 均完成并读新状态 1 | 均完成并读新状态 1 |
| 新增级联和正负仿射反馈 | 20 条历史 | 全部符合联立候选值 | 全部符合联立候选值 |

新增诊断的旧 EVAS 内核在 20 条历史中有 16 条与候选值不同：链中消费者读 0、
正负反馈都读 1；修复后分别为 1、2、2/3，符合解析方程，也符合 Spectre 观测。
这不以某一后端的结果直接定义答案。

最终两端分别检查 19,732 个 EVAS 输出点和 7,309 个 Spectre 导出点。
新执行的 18 次 Spectre 全部成功、无超时，核验 682 份新远端文件；另核验历史隔离批次
412 份文件。仅出现既有非致命 `VACOMP-2435`。当前 122 项 Python、14 项 Rust、
43 项检查器方法全部通过；锁定依赖的离线 all-targets warnings-as-errors、格式及 diff
检查通过。clippy 因本机未安装而未运行。未重跑静态全量回放或原四后端矩阵。

新组合批次与历史首批的条件、有效模型和数值设置一致；八个终点/长序列网表少了
一个未实例化的 `timer_once.va` include 和对应闲置源码，这是既有隔离版生成器的行为。
收据逐文件记录该差异；不声称这八份网表与历史字节相同。本轮已重新执行其 Spectre。
复用的隔离及诊断模型、条件和网表则全部逐字节一致。

[0.5.1 逐配置收据](results/timer-0.5.1.json) 记录修复前后输出、执行/输入/源码身份和归档哈希。
原 0.5.0 同刻检查器仍以旧电压 0 为候选；0.5.1 和 Spectre 均读到 1，故原报告中的
`candidate_differs` 在两端都保留。它表示与历史候选不同，不是本次跨后端差异。
新诊断单独检查联立方程候选，不通过改写旧答案把旧实验变成“通过”。

当前结论限定于已测的固定 timer、PWL 根和仿射网络。Spectre 的观测与联立方程候选
相容，不证明其内部采用同一算法。数值求解须通过现有数值秩和残差检查；非唯一或无解的反馈
明确失败。实数状态重放使用现有绝对/相对数值容差，不是任意状态物理单位的误差证明。
动态 timer、状态反馈 guard 的同刻再触发、非线性事件网络及其收敛仍未实现。
原 31 条件及其支持数量不变，完整 DVS 资格仍为 I；本轮不作性能结论。

新增检查器有 4 项独立合成校准。首个本机预检将“已触发的计数”与“更晚的采样时刻”
错误配对，校准测试按预期的历史一致性约束报错；修正合成数据为窗口内较早采样后，
另建 `pr12-timer-settlement-20260929-02` 才执行 Spectre。原预检源码与六份本机输出保留，
没有放宽生产检查器阈值，没有将该预检加入对照分母。

复现新批次时，先构建当前内核和运行检查器校准，再固定新的输出目录：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B experiments/dvs2-spectre-validation/timer_reference.py build runs/NEW-TIMER --implementation e78d1abbda90d81f948f6a4f52540acf484b0748
# 隔离配置另建目录，增加 --isolate；各目录最多 12 次 Spectre 尝试。
python3 -B experiments/dvs2-spectre-validation/timer_reference.py evas runs/NEW-TIMER --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/timer_reference.py spectre runs/NEW-TIMER --spectre-profile /PRIVATE/profile.json
python3 -B experiments/dvs2-spectre-validation/timer_reference.py check runs/NEW-TIMER --output runs/NEW-TIMER-analysis.json
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py build runs/NEW-SETTLEMENT
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py evas runs/NEW-SETTLEMENT --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py spectre runs/NEW-SETTLEMENT --spectre-profile /PRIVATE/profile.json
python3 -B experiments/dvs2-spectre-validation/timer_settlement.py check runs/NEW-SETTLEMENT --output runs/NEW-SETTLEMENT-analysis.json
```

Spectre 命令在已有工具环境运行；需复制相同源码、冻结输入和检查器依赖，并核验回传
文件清单。每次独立电路串行占一个 CPU，90 秒上限、30 秒许可证等待；不在原目录重试。
新的同刻诊断每批最多六次 Spectre。`--implementation` 是显式声明，实际内核和全部
Python/Rust 源码哈希另存于 `EVAS_STARTED.json`；不能仅凭声明判断执行身份。

## PR12 fixed timer comparison

以下是 **0.5.0 历史检查点**，原结果保留；修复后对照见上节。

**2026-09-29：已完成两批新执行的 EVAS–Spectre 对照，存在两项兼容性缺口。**
Spectre `21.1.0.509.isr12` 在 thu-sui 完成 24/24 次电路执行，无超时或执行失败；
固定 `9a25a401` 的 EVAS 完成 16/24 个冻结请求，另 8 个因事件次序无法认证而拒绝。
其中 4 个是首批组合电路，另 4 个是隔离后的同刻 timer/cross 电路，不能把前者
算成内部所有探针逐一失败。原 31 条件及其达标率不变。

以下选择首批的终点/长序列、第二批的普通及交互探针，避免重复计数：

| 范围 | 观察数 | EVAS 0.5.0 | Spectre |
| --- | ---: | --- | --- |
| 普通 timer、初始化、实例隔离、终点及长序列 | 64 条历史 | 64 条与独立有限判据相容 | 64 条相容 |
| timer/timer、timer/cross 的明确前后关系 | 16 个交互探针 | 16 个相容 | 16 个相容 |
| 同刻 timer/timer 电压状态读取 | 4 个探针 | 均读旧状态 0 | 均读新状态 1 |
| 同刻 timer/cross | 4 个探针 | 均拒绝，`event_resolution` | 均完成并读新状态 1 |

粗细步长、正反声明顺序下上述差异均存在。初始化探针从状态 7 开始，首个可见
计数均为 8；终点前/处/后配对的最终计数均为 0/1/1。长序列两档、两端都观测到
2,000 次事件，并满足原先固定的 1 ps 时间窗口。此处使用输出计数、采样时钟和
保持值做共同历史检查，不把 EVAS 内部事件日志当作独立答案。

同刻读取差异不直接裁定任一后端违反 LRM，但否定了“当前 EVAS 同刻快照与 Spectre
已一致”的说法。timer/cross 的最小隔离案例由线性时钟跨过 8 V、timer 在 `8*unit`
触发组成；EVAS 对区间内根的舍入包围无法证明其与 timer 同刻，因而拒绝。这项
保守限制仍存在，不能从旧测试中可精确定位的少数同刻例子外推到一般情况。
本次只补充验证，不修改仿真器实现；这两个问题留给后续语义与数学 review。

[逐配置结果与执行收据](results/timer-0.5.0.json) 记录了所有拒绝、共同模型、检查器、
实现和构建身份，以及原始归档哈希。两批共核验 920 份远端文件、24 份有效设置，
检查全部 7,063 个 Spectre 导出时间点和 18,672 个 EVAS 输出时间点。
检查器目录共 **39 项方法通过，其中 14 项为 timer 校准**。
原始运行、首次判定、修正后的重判和构建保存在忽略目录 `runs/`；收据包含完整
本地证据包的哈希。所有 Spectre 配置保留已有的非致命 `VACOMP-2435` 环境提示。
数值结论以固定的观察假设为条件，完整 DVS 资格仍为 I，未进行性能排名。

`timer_reference.py` freezes a separate development comparison for EVAS 0.5.0
implementation `9a25a401`. It does not change the original 31-condition matrix.
The execution contract is written into each new run's `contract.json`; generated
VA, Spectre netlists, inputs, observation grids and checker sources are hashed
before either backend runs. `test_timer_reference.py` supplies independent
synthetic accept/reject controls, including locally legal values with no common
event history, missing/duplicate events, future stamps and endpoint windows.

The frozen batch has **12 configurations per backend**: four ordinary circuits
(two maxsteps, forward/reversed event and instance declarations), six endpoint
circuits (stop before/at/after the same event, two maxsteps), and two circuits
with 2,000 periodic events. There are **64 timer probe histories and 24 event
interaction probes per backend**, not 88 new benchmark conditions. Each
interaction probe contains two observable event histories. Ordinary probes cover
positive periods, omitted/zero/negative periods, zero/nonzero constant enables,
nonzero initialization with `timer(0)`, instance isolation, simultaneous timers
and events beyond stop. Interactions cover timer/timer and timer/cross before,
at and after the same nominal time, with voltage-state sampling.

The ordinary time unit is exactly `2^-30 s`; explicit timer tolerance is
`unit/1024`. Long probes use start `0.13 us`, period `7 ns` and tolerance `1 ps`;
their nominal answers are exact rationals of the submitted binary64 values.
Coarse/fine maxsteps are 5/0.5 ns (50/5 ns for long probes). Both backends use
reltol `1e-8`, vabstol `1e-10 V`; Spectre also uses iabstol `1e-14 A` and
`traponly`. Spectre exports every accepted point without strobe; EVAS additionally
uses different output grids in the forward/reversed configurations.

Every exported input and output point is retained. Counts, sampled clocks and
held data must admit one ordered event history within the independent nominal
windows. The conditional voltage allowance is `1e-8 V`; this is an assumed
finite-observation screen, not a measured physical observation-error bound.
Timer windows are symmetric, cross windows one-sided. Endpoint windows are
not clipped to stop: an event may remain unobserved if its allowed window extends
beyond stop. Same-time voltage-state reads are classified against EVAS's
pre-event-snapshot candidate; a different valid state is reported explicitly,
not silently accepted as compatibility or labelled an LRM violation.

Budget: at most 12 Spectre circuit attempts in one fresh run, serial, one pinned
CPU, 90 seconds per attempt including a 30-second license wait, no in-place retry.
Any changed-input follow-up receives a new identity and preserves the old attempt.
This comparison cannot establish full timer support, continuous-time accuracy,
dynamic-parameter semantics, atomic rollback inside Spectre, or a performance
advantage. The other three timed operators are outside this batch.

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_timer_reference.py' -v
python3 -B experiments/dvs2-spectre-validation/timer_reference.py build runs/NEW-TIMER
python3 -B experiments/dvs2-spectre-validation/timer_reference.py evas runs/NEW-TIMER --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/timer_reference.py spectre runs/NEW-TIMER --spectre-profile /path/to/private-profile.json
python3 -B experiments/dvs2-spectre-validation/timer_reference.py check runs/NEW-TIMER --output runs/NEW-TIMER-analysis.json
```

The Spectre action runs on the configured Linux host. Transfer the frozen inputs
and the exact checker dependencies to a fresh checkout layout there; preserve
and verify its returned file manifest before analysis. Private profiles, raw
waveforms and full logs remain outside Git.

The first combined run revealed an EVAS event-ordering rejection. A separate
`build ... --isolate` follow-up preserves all four ordinary configurations and
their probe parameters, but splits each into three circuits: timers (including
timer/timer interactions), neighboring timer/cross events, and simultaneous
timer/cross events. It adds at most 12 Spectre attempts under the same per-run
budget. The original rejection remains in the report. This follow-up is
development diagnosis after observing the first result, not an unseen test set;
no acceptance thresholds or EVAS implementation are changed. The first checker
is reproducible at commit `6aa43ad`; each run retains its exact source hashes.

Run `-01` initially classified two Spectre endpoint observations as invalid:
PSF printed the final time one binary64 ULP above the requested stop, and the
input evaluator rejected this outside its closed knot domain. The corrected
adapter applies the PWL source's constant endpoint extension while preserving
the raw timestamp, original coverage gate, voltage allowance and event windows.
A calibration accepts this rounding case but rejects wrong input values and
out-of-range final times. Reanalysis is explicit: `check` with
`--frozen-source-root /path/to/extracted-original-input-archive` verifies the
original source snapshot and records both original and current checker hashes.
The original analysis remains archived; this is a checker correction, not a
new Spectre execution or a changed event acceptance target.

## Original 31-condition comparison

This experiment implements the 16 conditions in the seven
[new case cards](../../evas/validation/NEXT_CASE_CARDS.md), reruns 14 unchanged
v1 conditions, and runs a separate standard-array revision of the v1 lowpass
condition. There are **31 conditions and 62 configurations** across two settings.
**Completed on 2026-09-28: all 62 runs produced waveforms and all 62 met the
frozen finite-observation targets.** Spectre version: `21.1.0.509.isr12`.
No execution failures, timeouts, numerical violations or unresolved finite
checks occurred. Formal observation qualification remains I.

The separate [PR7 cross comparison](#pr7-cross-小规模对照) below uses eight
development conditions. Its results do not change this 31-condition denominator.

[PROTOCOL.md](PROTOCOL.md) is frozen before execution and describes inputs,
resource limits, targets, observation requirements, conditional history checks,
and the distinction between finite checks and formal qualification.

- [run_suite.py](run_suite.py) builds stimuli, netlists and the immutable manifest.
- [remote.py](remote.py) verifies inputs and runs Spectre serially without retries.
- [check_results.py](check_results.py) checks archived waveforms against independent
  mathematical answers, retaining every accepted point.
- [test_checks.py](test_checks.py) supplies eight calibration methods containing
  controls for all 16 new conditions, hand anchors, seven semantic fault classes,
  wrapped-range/whole-cycle faults, malformed observations and uncertainty bands.

The sampler source is intentionally shared by E2 and C1; C2 packages that same
sampler and the standard-array lowpass as two distinct modules. These are new
condition identities, with full instance declarations and all input/intermediate/
output nodes saved. The former v1 `v6-main` source remains frozen; `v6-standard`
is its explicitly identified source revision, not an additional 32nd condition.

Reproducible local checks:

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B evas/validation/check_design_math.py
python3 -B scripts/verify_validation_version.py
```

Build inputs only into a fresh directory:

```sh
python3 -B experiments/dvs2-spectre-validation/run_suite.py runs/NEW-RUN-input
```

The remote tool profile stays private. Execution, transfer, and reanalysis must
use the new run identity and preserve its input/output manifests. Results do not
qualify timestamp semantics or between-export behavior; formal DVS status is I.
This batch does not execute any other backend, historical variant suite or model
API, and does not modify EVAS or the v1 snapshot.

## 本轮结果

| 范围 | 条件数 | 基础设置 | 细化设置 |
| --- | ---: | ---: | ---: |
| v1 的 14 个原条件，加标准语法低通修订 | 15 | 15/15 | 15/15 |
| E1：方向事件计数 | 3 | 3/3 | 3/3 |
| E2：初始高电平与复位恢复 | 3 | 3/3 | 3/3 |
| C1：有状态实例隔离 | 3 | 3/3 | 3/3 |
| C2：低通后采样 | 1 | 1/1 | 1/1 |
| D1：积分、保持复位与释放 | 2 | 2/2 | 2/2 |
| D2：常频/变频相位与包裹 | 2 | 2/2 | 2/2 |
| S1：多输入与贡献累加 | 2 | 2/2 | 2/2 |
| **合计** | **31** | **31/31** | **31/31** |

表内“通过”表示成功执行且全部合格导出点满足预先固定的有限观测判据，
不表示正式 DVS P。两档共检查 **1,333,719 个时间点**；最大导出间隔约
1 ns。62 份实际生效的步长、最大步长、停止时间、误差容限和积分方法均与请求一致。
执行用时之和约 608 秒，包含编译与启动，不作为仿真器性能比较。

共同历史检查共涉及 40 条输出历史（包含同一条件的多输出，不另算测试条件），
在 B=0 与候选 B=0.25 mV 两个场景均取得共同历史见证。积分器的两条件、两档
也均取得相应有限数值见证。几个有独立解析目标的最大观测误差为：

| 量 | 最大误差 | 固定目标 |
| --- | ---: | ---: |
| C2 低通中间节点 | 0.1743 μV | 600 μV |
| D1 带复位积分输出，基础设置 | 48.73 μV | 1,000 μV |
| D2 累计/包裹相位 | 3.444e-7 周期 | 1e-4 周期 |
| D2 正弦电压 | 1.731 μV | 1,000 μV |
| S1 加权输出 | 9.437e-16 V | 1e-3 V |

上述误差是导出值相对解析答案或所列合法共同见证的误差，未加入未经证明的
物理观察误差界。D2 两条件分别观测到 2、4 次包裹；E1 的网格平移对照不证明
后端内部实际走过“精确零点”分支。其余后端的新增条件和旧 126 个变体未在本批运行。

所有 62 份日志均有相同的非致命 `VACOMP-2435` 提示：旧环境变量
`CDS_AHDLCMI_ENABLE` 不再受支持，Spectre 使用默认编译 C 流程。
未修改共享环境或放宽阈值；该提示与原始日志一并保留。

## 证据与复核

- [逐配置分析](results/analysis.json)：输入/输出检查、解析误差、共同历史见证和正式资格状态。
- [归档收据](results/RECEIPT.json)：版本、工具/输入/原始归档/分析哈希、运行预算和汇总。
- [实际设置核对](results/effective-settings.json)：62 份日志提取结果和请求匹配情况。
- 原始输出位于仓库忽略目录 `runs/dvs2-spectre-20260928-01/`，压缩包为
  `runs/dvs2-spectre-20260928-01.tar.gz`；thu-sui 的任务私有运行区另保留压缩归档。
  已核对压缩包 SHA-256 和清单中的 **1,216 个文件**，不将原始机器日志提交到仓库。
- 输入清单在启动前冻结，原始模型、网表、分析代码和协议快照均进入归档。
  [report.py](report.py) 是运行后整理设置与收据的程序，单独记录哈希，未改变判定器。
- 新判定器 8 项校准方法、共享历史判定器 17 项校准/适配方法均通过；设计算术检查
  和 v1 的 36 个 Git 工件、4 个快照工件、13 个原始输入身份检查通过。

原始证据保持只读，复核写入一个新的外部输出路径：

```sh
python3 -B experiments/dvs2-spectre-validation/check_results.py \
  runs/dvs2-spectre-20260928-01 runs/NEW-ANALYSIS.json
```

本次确认当前 31 条件在该版本 Spectre、这两档设置下均可执行且观测达标。
完整输入误差、时标语义、未采样区间和其他行为覆盖的资格工作仍未完成；不据此
外推所有 Spectre 版本、所有 Verilog-A 模型或 EVAS 的通过情况。

## PR7 cross 小规模对照

2026-09-29，EVAS 0.4.4 在本机运行，Spectre `21.1.0.509.isr12` 在 thu-sui
运行相同 DUT 和连续 PWL 激励。[cross_reference.py](cross_reference.py) 提供
8 个开发条件：双向、仅上升、37 ps 平移、断点穿越与相切、初始高电平、内部反馈、
收紧时间容差、收紧表达式容差。每条分别使用 100 ns / 7 ns 最大步长，共每后端 16 组。
该 DUT 不含 `transition`，不替换原 E1，也不是新的未见确认集。

事件块累加计数并采样线性时钟电压；检查器根据独立声明的 PWL 段，用精确有理数
计算根及允许窗口 `min(ttol, tol/abs(slope))`，再检查计数和保持电压。
两个后端均接受同一判据；不以两者相等作为正确性的定义。
预先固定的电压观测余量为 `1e-8 V`（时钟上约 10 fs），这是条件假设，
不是已证明的物理观测误差界。有限采样和保持值也不证明完整连续事件历史。

| 固定判据结果 | EVAS | Spectre |
| --- | ---: | ---: |
| 普通穿越等 7 条件 × 两档 | 14/14 | 14/14 |
| 断点穿越与相切 × 两档 | 2/2 | 0/2，事件次数不同 |
| 合计 | 16/16 | 14/16 |

最后两组预期在 0.5、2.5 µs 穿越时各触发一次，忽略 1.5 µs 的同侧相切。
Spectre 两档都额外在 1.5 µs 触发，最终计数为 3，EVAS 为 2。
这表示 **当前 EVAS 相切契约与 Spectre 实测行为不一致**，不能解释成 Spectre 错误
或 EVAS 更准确，也没有通过修改判据消除差异。

另外两次成功的方向诊断使用 `u: 0.6 → 0.5 → 0.6 V`，谷底在 1.5 µs，
guard 为 `scale*(V(u)-0.5)+offset`，同一网表含七个独立实例：

| guard | 双向次数 | 上升次数 | 下降次数 |
| --- | ---: | ---: | ---: |
| `V(u)-0.5` | 1 | 0 | 1 |
| `-(V(u)-0.5)` | 1 | 1 | 0 |
| `V(u)-0.5+1e-6` | 0 | 未运行 | 未运行 |

两档一致，观测触发时刻均为 1.5 µs，符合“按接近零的方向触发”的现象。
最低点仍为正、但小于表达式容差的实例没有触发；因此不能简单用容差带模拟这个行为。
这里没有内部 guard 记录，不能确定内部零值分类或舍入机制，也未把这两次诊断
加入基线通过分母。首次诊断两次均因 VA 的 `.5` 字面量语法被拒绝；修正为 `0.5`
并将方向参数声明为整数后，在新目录重跑。失败记录保留，未作为波形结果使用。

普通穿越中，保持电压反推出的 Spectre 最大延迟约为：默认 25 ps、内部节点斜率
加倍时 12.5 ps、收紧 `ttol` 时 0.5 ps、收紧 `tol` 时 0.25 ps。
这些值满足固定窗口，支持分别核验两项容差的设计；它们不证明通用的“半窗口”算法。
EVAS 无须复制相同延迟，但仍须证明自身的根定位误差满足声明容差。

[完整收据](results/cross-reference-0.4.4.json) 保存每组结果、源码/内核/检查器哈希、
实际设置和诊断 DUT。基线 16 次 Spectre 执行均成功，无超时；16 份生效设置匹配，
只出现既有非致命 `VACOMP-2435`。连同诊断共 20 次电路执行：18 次产出波形，
2 次语法失败。原始归档位于忽略目录 `runs/pr7-spectre-contract-20260929/`，
thu-sui 任务私有区另有副本；主归档 296 个文件、诊断归档两批共 54 个文件的哈希均已核对。
执行耗时含启动与编译，不作为性能比较。

复现时先运行检查器校准，再冻结新目录；将源码、检查器依赖和冻结目录复制到
已有 Spectre 环境后执行 `spectre` 子命令，私有工具 profile 不进入仓库。
回传完整结果后在原源码版本重新分析：

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p test_cross_reference.py -v
python3 -B experiments/dvs2-spectre-validation/cross_reference.py build runs/NEW-CROSS
python3 -B experiments/dvs2-spectre-validation/cross_reference.py evas runs/NEW-CROSS --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/cross_reference.py spectre runs/NEW-CROSS --spectre-profile /PRIVATE/profile.json
python3 -B experiments/dvs2-spectre-validation/cross_reference.py check runs/NEW-CROSS --output runs/NEW-CROSS-analysis.json
```

四项校准方法包含手算锚点、合法延迟、共同错误、缺失/错序/非有限观测等控制。
当前结论只涉及这些限定条件；相切语义仍须 review，不宣称完整 Spectre 兼容。

## PWL 触零边界实验

[cross_touch.py](cross_touch.py) 单独检查步长、时刻平移、容差与触零次数的关系，
EVAS 保持 0.4.4。每组有三路 PWL 电压，从 0.6 V 降到 0.501 / 0.500 / 0.499 V，
再回到 0.6 V。每路分别监测正、负 guard 和双向/上升/下降三个方向，
共 18 个独立监测实例。事件块保存次数、线性时钟电压和当次 guard 采样值。

| 因素 | 设置 |
| --- | --- |
| 谷底时刻 | 1.5 µs；整个波形平移 37 ps，前段补恒定值 |
| 最大步长 | 100 ns、7 ns |
| 默认事件容差 | `ttol=100 ps`、`tol=10 µV` |
| 只收紧时间容差 | `ttol=1 ps`、`tol=10 µV` |
| 只收紧表达式容差 | `ttol=100 ps`、`tol=0.1 µV` |

两时刻 × 两步长 × 三容差，共 **12 个配置，每后端 216 条监测历史**。
谷底高于阈值的实例预期没有事件；低于阈值的实例预期双向两次、每个单方向一次。
两次真实穿越间隔约 29.7 ns，大于最大时间容差 100 倍；解析根以冻结 binary64
PWL 输入的精确有理数独立计算。恰好触零的六个实例只分类观测为“不触发、到达方向、
离开方向、两个方向或其他”，不先规定哪一类正确。

输入、检查器和 12 次 Spectre 执行预算在运行前冻结；每次使用一个固定 CPU，
90 秒墙钟上限、30 秒许可证等待，不自动重试。固定电压观测余量仍为 `1e-8 V`，
检查所有导出点的有限性、输入、计数历史、保持时间见证和事件 guard 采样值范围。
触零分类不是正式语义资格，公开的 guard 采样也不等于 Spectre 内部迭代记录。

2026-09-29 的新批次 `pr7-touch-boundary-20260929-01` 已完成：本机 EVAS 和 thu-sui
Spectre 各执行 12 个配置。两者的 144 条非零谷底控制历史全部满足冻结判据；
各自另有 72 条恰好触零的诊断历史。全部配置的分类一致：

| 谷底 | EVAS：双向 / 上升 / 下降 | Spectre：双向 / 上升 / 下降 |
| --- | --- | --- |
| 高于阈值，正 guard | 0 / 0 / 0 | 0 / 0 / 0 |
| 恰好触零，正 guard | 0 / 0 / 0 | 1 / 0 / 1 |
| 恰好触零，负 guard | 0 / 0 / 0 | 1 / 1 / 0 |
| 低于阈值，两种极性 | 2 / 1 / 1 | 2 / 1 / 1 |

高于阈值的负 guard 同样无事件。Spectre 所有触零事件的公开 guard 采样值均为 0，
没有“到达一次、离开再一次”的双重计数。其基础档导出 70–76 点、细化档 461–466 点，
导出网格明显不同，但触零次数和方向保持一致。普通穿越的最大观测延迟约为默认
50 ps、收紧时间容差后 0.5 ps、收紧表达式容差后 0.743 ps，均满足各自窗口。

因此，在本次 PWL 范围内，单纯减小步长没有消除差异，结果支持到达零值时的事件规则
与 EVAS 不同。但全部触零点仍是显式 PWL 断点，尚未排除断点命中的作用，也未测试
没有显式断点的光滑极小值；不把观察模式当作 Spectre 内部算法的证明。本次没有修改
EVAS 运行时语义，也没有增加原 31 条件的分母。

[逐配置收据](results/cross-touch-0.4.4.json) 保存计数、方向、事件采样、设置和完整身份。
12 次 Spectre 执行均成功，无超时；只出现 12 次既有 `VACOMP-2435`。
已核对原始归档中 812 个文件，另将本机 13 份 EVAS 工件按相同输入身份汇集分析。
私有原始材料位于忽略目录 `runs/pr7-touch-review-20260929/`；远端另保留原始压缩包。

报告处理有两项明确修复，未修改事件判据、未增加电路执行：共享测试发现与旧 pilot
同名的 `report.py` 导入冲突，发布脚本改为按文件路径加载所属模块；平移后的日志把
停止时间 `3.000037 µs` 显示为 `3.00004 µs`，冻结分析先报告 6 次设置不匹配。
重分析按日志显示精度区间核对 stop，再要求波形末点与请求值在原定 `1e-18 s`
界限内一致，其余设置仍按原阈值核对。六份波形末点均为请求值；原始误报和修复后报告
分别保留。所有波形、根和事件检查仍使用归档中的冻结函数。
新检查器原有 4 项校准、后补 2 项元数据校准均通过，目录内共 18 项测试通过。

复现新批次：

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p test_cross_touch.py -v
python3 -B experiments/dvs2-spectre-validation/cross_touch.py build runs/NEW-TOUCH
python3 -B experiments/dvs2-spectre-validation/cross_touch.py evas runs/NEW-TOUCH --kernel evas/rust_core/target/debug/evas-kernel
# 将冻结目录及检查器依赖复制到已有 Spectre 环境后执行：
python3 -B experiments/dvs2-spectre-validation/cross_touch.py spectre runs/NEW-TOUCH --spectre-profile /PRIVATE/profile.json
# 汇集同一输入身份的两后端结果后：
python3 -B experiments/dvs2-spectre-validation/cross_touch.py check runs/NEW-TOUCH --output runs/NEW-TOUCH-analysis.json
```

## 孤立触零契约回放（0.4.5）

用户审阅上述实验后，EVAS 0.4.5 将内部 PWL 孤立零点定义为到达方向触发一次，
离开不再触发。`cross_touch.py check --require-arrival` 启用显式版本契约
`isolated-pwl-zero-arrival-v1`：正 guard 的双向／上升／下降次数为 `1/0/1`，
负 guard 为 `1/1/0`。逐点检查计数窗口、方向、保持时间见证和 guard 采样；
原始 `inspect` 诊断模式、非零谷底判据和 `1e-8 V` 观测余量均保持不变。
新增 3 项校准方法，接受到达规则，拒绝漏事件、离开方向、双触发、过早或过晚计数、
错误保持时间及 guard 值。目录内共 21 项校准方法通过。

`pr7-touch-arrival-20260929-02` 在运行前固定该契约、检查器和输入身份，
新执行本机 EVAS 的 12 个配置，**没有新执行 Spectre**。复用前述 thu-sui 批次，
核对原始归档哈希及 812 份文件；新旧 85 份模型、网表和条件文件逐字节一致。
在新目录中重判 12 份归档 Spectre 波形及新 EVAS 输出：

| 有限观察历史 | EVAS 0.4.5 新执行 | Spectre 归档重判 |
| --- | ---: | ---: |
| 高于阈值及低于阈值控制 | 144 / 144 | 144 / 144 |
| 孤立触零、两种极性和三种方向 | 72 / 72 | 72 / 72 |

全部 12 配置的计数与方向一致。作为反例，同一新检查器重判旧 EVAS 0.4.4：
144 条普通控制仍通过，72 条触零历史中 48 条应触发而未触发；另外 24 条本就要求零次事件。
这不是重写旧版的诊断结论，而是按获审阅的新契约单列检查结果。

[0.4.5 收据](results/cross-touch-0.4.5.json) 保存新旧输入、构建、检查器及波形哈希，
并逐配置记录计数和方向；原始运行、冻结契约及完整重判输出保存在忽略目录
`runs/pr7-touch-arrival-20260929-02/`。只增加本次开发回归证据，不增加原 31 条件分母。
所有触零点仍为显式 PWL 节点；不证明光滑极值、零平台、停止时刻触零、完整 DVS 资格或性能优势。

对同一输入身份汇集的两后端输出启用新契约：

```sh
python3 -B experiments/dvs2-spectre-validation/cross_touch.py check runs/NEW-TOUCH --require-arrival --output runs/NEW-TOUCH-arrival.json
```

## 零平台和停止点边界（0.4.6）

`cross_boundaries.py` 独立冻结 21 种输入、3 个方向及 6 个配置：maxstep 为 100/7 ns，
每档搭配 nominal（ttol=100 ps、tol=10 µV）、time_tight（1 ps、10 µV）和
expression_tight（100 ps、0.1 µV）。同一 VA 探针保存计数、事件时钟和 guard；
21 种输入包含终点到零及终点后延伸、同侧/异侧平台、初始/终端平台、20 ps 短平台、
恒零输入，并以近零非零平台、普通穿越和已审阅的孤立零点作对照。

运行前固定候选规则：非零到零按到达方向触发一次，停留及离开不触发；终点输出可见提交后的状态。
边界结果标为 candidate-consistent/inconsistent，不预设哪个仿真器正确。
检查器逐点检查次数窗口、方向、保持时间与输入重建的一致性、guard 容差及初始状态，
观测余量为原定 `1e-8 V`；4 项合成校准覆盖缺失/重复/错误方向事件和错误历史、采样。
这属于条件性的有限观察判据，不是对内部步进或完整 LRM 的证明。

`cross-boundaries-20260929-01` 的 6 次 Spectre 均在编译期因 `.5` 字面量被拒绝
（VACOMP-1795），未产生瞬态结果。保留其输入、原始日志和身份；探针仅改为 `0.5` 后，
以 `cross-boundaries-20260929-02` 重新冻结相同输入和判据。该新批次 6 次全部完成，
单 CPU、串行、每次 90 秒上限、license 等待 30 秒，批次内不重试；两批总计 12 次 Spectre 尝试。
核对新批次原始归档的 110 份文件、有效设置及高精度停止时刻后：

| 有限观察历史 | EVAS 0.4.6 新执行 | thu-sui Spectre 新执行 |
| --- | ---: | ---: |
| 零平台/停止点边界（15 输入 × 3 方向 × 6 配置） | 270 / 270 | 270 / 270 |
| 近零、普通穿越、孤立触零对照（6 × 3 × 6） | 108 / 108 | 108 / 108 |

两后端计数和方向一致；该结果支持本轮 EVAS 到达规则扩展，不能推广到光滑极值、动态/
非线性轨迹或有状态反馈的 guard。EVAS 0.4.5 对首批相同数值输入的 6 个组合请求均
显式返回 `unsupported_cross`，这是组合请求被拒绝，不能算成 378 条逐探针失败。
原 31 条件及其支持数量不变。

[整理后的收据](results/cross-boundaries-0.4.6.json) 保存冻结输入、检查器、内核、原始归档及
逐配置结果身份，原始记录在忽略目录 `runs/cross-boundaries-20260929-01/` 和 `-02/`。
复现实验应使用新的输出目录；运行前检查收据里的预算与使用权限：

```sh
python3 experiments/dvs2-spectre-validation/cross_boundaries.py build runs/NEW-BOUNDARIES
python3 experiments/dvs2-spectre-validation/cross_boundaries.py evas runs/NEW-BOUNDARIES --kernel evas/rust_core/target/debug/evas-kernel
python3 experiments/dvs2-spectre-validation/cross_boundaries.py spectre runs/NEW-BOUNDARIES --spectre-profile /path/to/private-profile.json
python3 experiments/dvs2-spectre-validation/cross_boundaries.py check runs/NEW-BOUNDARIES --output runs/NEW-BOUNDARIES-analysis.json
```
