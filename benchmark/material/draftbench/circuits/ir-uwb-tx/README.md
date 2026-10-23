# IR-UWB TX 种子链（8DPPM+8FSK，4.032 Gb/s）

这里交付 IR-UWB 发射机种子链的 Verilog-A 系统，后续 vaBench 题目从这套已验证的模块里切出。
需求来自用户提供的工程 SPEC（《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》），只做其中 Verilog-A 的部分；
行为约定、来源和建模选择见 [SPEC.md](SPEC.md)，任务记录见 [#223](https://github.com/BucketSran/vaEVAS/issues/223)。

## 现状（2026-10-23）

M1–M4 的 9 个模块和系统顶层已写完。M5 在同一批模块上加入预热（释放提前量）、原 SPEC §8 中可以直接建模的非理想、支路隔离和事件导出，新参数默认关闭；
另有导出与功耗记账工具 [tools/uwb_export.py](tools/uwb_export.py)。全部检查在旧 EVAS 0.8.7 上通过。
当前 main 的 EVAS 跑不了其中大部分写法，缺口记录在 [#229](https://github.com/BucketSran/vaEVAS/issues/229)；Spectre 还没有跑。

| 模块 | 文件 | 检查 | 旧 EVAS 0.8.7 |
| --- | --- | --- | --- |
| 6 bit 串并转换 | [module/serial_to_symbol6.va](module/serial_to_symbol6.va) | [m1_data](test/m1_data/check_m1.py)：4097 个符号覆盖 64 个码字和 4096 个相邻码字对；复位、重复字 | 通过 |
| 8DPPM+8FSK 编码器 | [module/dppm_fsk_encoder8.va](module/dppm_fsk_encoder8.va) | 同上 | 通过 |
| 16 相主 RO | [module/master_ro16.va](module/master_ro16.va) | [m2_clock](test/m2_clock/check_m2.py)：抽头时刻、周期、调谐码跳变时相位连续 | 通过 |
| RO 频率校准 | [module/ro_frequency_cal.va](module/ro_frequency_cal.va) | 同上：正常收敛到 288、再次校准、参考缺失、RO 过快、RO 过慢 | 通过 |
| 脉冲发生器 | [module/pulse_generator.va](module/pulse_generator.va) | [m3_pulse/check_pg.py](test/m3_pulse/check_pg.py)：全部位置、7→0 / 0→7、同频首尾相接、n_pre=0 / 15、使能晚到 | 通过 |
| RF 支路 RO | [module/rf_ro_branch.va](module/rf_ro_branch.va) | [m3_pulse/check_rf.py](test/m3_pulse/check_rf.py)：与公式误差 1.5e-11 V，冷启动可重复，首周期 +1% 频差 | 通过 |
| 包络通道 | [module/envelope_lane.va](module/envelope_lane.va) | 同上：与 RK4 数值解误差 1.1e-11，150 ps 后尾部 < 1e-6 | 通过 |
| 8 支路调度器 | [module/ro_scheduler8.va](module/ro_scheduler8.va) | [m4_chain](test/m4_chain/check_chain.py)：保持条件、空闲 HOLD 窗口、抢占空闲 HOLD、两条通道上的丢弃、长空闲后冷启动、两路供电上限 | 通过 |
| 合路 / PA / 差分输出 | [module/tx_output.va](module/tx_output.va) | 同上：outp−outn 与独立重建的最大误差 5.2e-5 V（随机 200 符号场景） | 通过 |
| 系统顶层 | [system/tx_seed.va](system/tx_seed.va) | [system](test/system/check_system.py)：先校准（44.5 µs 时 done），再从 RF 波形解出符号：40/40 正确 | 通过 |

M5 的检查在 [test/m5/check_m5.py](test/m5/check_m5.py)，每个场景都打开导出，用导出的随机抽样值独立重建差分输出：

| M5 场景 | 内容 | 结果（旧 EVAS 0.8.7） |
| --- | --- | --- |
| lead | 释放比 RF 窗口提前 5 个抽头；调度器经过 RELEASE_SETTLE；窗口开始时幅度已建立（≥ 0.99998） | 通过 |
| static | 共同频偏 25 MHz，器件频率残差 10 MHz、增益残差 0.5 dB；每个器件的残差在各次激活中保持不变 | 通过，重建误差 5.3e-5 V |
| activation | 每次冷启动的频偏 5 MHz 和均匀随机初相：159 次激活，标准差 5.01 MHz（界 4.07–5.93），Rayleigh 检验 p = 0.62；保持的支路不重新抽 | 通过 |
| phase_noise | 相位扩散 5°/1 ns，50 ps 网格：1663 步的增量标准差 1.118°（界 1.054–1.182） | 通过 |
| timing | 符号抖动 5 ps、位置与宽度误差各 2 ps：164 个符号的抽样标准差都在界内；通道边沿 = 抽头 + 36 ps 公共延迟 + 抽样 | 通过 |
| tap_skew | 抽头偏斜 3 ps：去掉报告的偏斜后抽头构成均匀格点（误差 ≤ 2 ps） | 通过 |
| isolation | 隔离 40 dB：空闲保持的支路以 1 % 漏到输出，重建包含泄漏项 | 通过 |
| export | 导出 → CSV → 功耗记账：支路状态与监测边沿一致，状态时间与独立重放一致，参数为 null 时不给能量 | 通过 |
| combined | 原 SPEC §8 主档全部打开、n_lead = 2：重建一致；接收式解码 150/150 正确 | 通过 |

整链 4097 个符号（分 8 段）全部通过：每个 PG 窗口、每个支路的供电/预充电/释放边沿、门控和冲突都与独立重放一致。

**checker 能否检出错误。** 用 35 个典型错误版本逐个替换 gold 重跑，35 个全部被判失败，见 [test/mutants.py](test/mutants.py)。
M1–M4 的 25 个如不做反 Gray、用绝对位置、码跳变时重置相位、校准判决方向反了、没有参考缺失看门狗、不留准备帧、单通道、
不报 overrun、调度抢占忙碌槽、热请求重新预充电、不保持、保持窗口不扣 T_pre、不抢占空闲 HOLD、忽略极性或 DPC；
M5 的 10 个如只在 RF 窗口开始时释放、预热把 RF 窗口也提前、不加激活频偏、初相恒为 0、相位噪声不累积、
器件残差每次激活重抽、抖动只加在 RF 沿、宽度误差加在开始沿、泄漏包含已接通的支路、抽头偏斜没有加上。
尚未覆盖的场景列在 [SPEC.md 第 6 节](SPEC.md#6-验收)。

## 目录

```text
ir-uwb-tx/
├── SPEC.md      # 系统行为约定：常量、模块规则（来源/选择/待定）、验收
├── module/      # 9 个模块
├── system/      # 系统顶层 uwb_tx_seed
├── tools/       # 导出转换与参数化功耗记账（uwb_export.py、power_params.json）
└── test/        # 激励源、边沿记录仪、各里程碑 checker（m1–m5、system）、错误版本校准
```

## 怎么运行

每个 checker 自己生成测试台、调用仿真器、独立计算期望并写出 `checks.json`。结果默认写到 git 忽略的
`runs/uwb-tx-vabench-20261022/evas/`，可用环境变量 `UWB_OUT` 改。

```sh
cd benchmark/material/draftbench/circuits/ir-uwb-tx/test
python3 run_all.py                   # 全部检查加错误版本校准，约 25 分钟
python3 m1_data/check_m1.py          # 串并 + 编码器，约 2 分钟
python3 m2_clock/check_m2.py         # 主 RO + 校准，约 1.5 分钟
python3 m3_pulse/check_pg.py         # 脉冲发生器，几秒
python3 m3_pulse/check_rf.py         # RF 支路 + 包络，几秒
python3 m4_chain/check_chain.py      # 整链，5–8 分钟
python3 m5/check_m5.py               # M5 九个场景，约 4 分钟
python3 system/check_system.py       # 系统顶层，含 44.5 µs 校准，约 5 分钟
python3 mutants.py                   # 错误版本校准，约 5 分钟
```

导出与功耗记账：模块的 `export` 参数设为 1（系统顶层的 `export` 会传给所有模块），仿真后运行

```sh
python3 tools/uwb_export.py <Spectre 日志或 EVAS 的 strobe.txt> <输出目录> --params tools/power_params.json --models module
```

得到 symbols.csv、scheduled.csv、branch_states.csv、gates.csv、activations.csv、phase_noise.csv、calibration.csv、taps.csv、
power.json/md 和 manifest.json。power_params.json 的功率和能量都是 null（待提参），这时只报告状态时间、启动次数和供电支路统计。

单项可以只跑某个场景，例如 `python3 m4_chain/check_chain.py conflict`。耗时是 2026-10-22/23 在本机旧 EVAS 上的实测，两次运行之间差别可达 1.8 倍。

仿真器由 `UWB_BACKEND` 选择：`legacy`（默认，旧 EVAS 0.8.7）或 `evas`（当前 main，目前大多失败，见 #229）。
旧 EVAS 是 vaBench r53 认证时用的版本：从 `legacy/EVAS` 的提交 `6cb6fa7a` 用 `git archive` 导出，
编译其 Rust 内核并准备装有 numpy 的 Python，再用 `UWB_LEGACY_SRC`、`UWB_LEGACY_PY` 指过去
（默认指向本机 git 忽略的 `runs/legacy-evas-0.8.7/`，重建步骤见那里的 README；2026-10-23 机器重启清空了原来的 `/tmp/legacy-run`）。

## M5 参数一览（默认全部关闭）

| 位置 | 参数 | 含义（原 SPEC §8 主档） |
| --- | --- | --- |
| PG | `n_lead` | 释放比 RF 窗口提前的抽头数（0/1/2/5/11 ≈ 0/100/200/500/1000 ps） |
| PG | `sigma_jit`、`sigma_pos`、`sigma_wid`、`t_lat`、`seed` | 符号抖动（5 ps）、位置与宽度误差（各 2 ps）、公共延迟下限、种子 |
| 主 RO | `sigma_tap`、`tap_lat`、`seed` | 抽头静态偏斜、公共延迟下限、种子 |
| RF 支路 | `f_off`、`sigma_f_res`、`sigma_g_res_db` | 共同频偏（+25 MHz）、器件频率残差（10 MHz）、器件增益残差（0.5 dB） |
| RF 支路 | `sigma_f_act`、`phi_random`、`sigma_pn_1ns`、`t_pn_grid`、`seed`、`id` | 激活频偏（5 MHz）、随机初相、相位扩散（5°/1 ns）、网格（50 ps）、种子、导出编号 |
| 输出 | `iso_db` | 支路隔离（40 dB；200 表示关闭） |
| 各模块 | `export` | 1 时输出导出记录 |

系统顶层 `uwb_tx_seed` 有同名参数（支路种子为 `seed_br`，PG 为 `seed_pg`，主 RO 为 `seed_ro`）。

## 出题方向（下一步，尚未建设）

按五类工程动作，从这套模块切题；难度先是预期，以模型实测为准，同源关系另行登记。

| 工程动作 | 候选题 | gold 来源 | 预期难度 |
| --- | --- | --- | --- |
| 按规格建模 · 单模块 | 6 bit 串并；DPPM+FSK 编码器；频率校准状态机；PG；RF 支路；调度器 | 对应 `module/*.va` | 基础 → 难 |
| 按规格建模 · 系统 | 在给定架构下搭出种子链 | `system/tx_seed.va` | 难 |
| 扩展与集成 | 在健康链路上加 2PWM / 2PAM 维度；接入 CDC 方案 | 待写（M6、CDC 定案后） | 难 |
| 诊断与修复 | 故障取自 [mutants.py](test/mutants.py) 中已被 checker 检出的典型错误，如码跳变时重置相位、热请求重新预充电 | 对应模块 + 故障版本 | 中 → 难 |
| 电路测试与表征 | 从 RF 波形逐脉冲测起点、宽度、载频并解码（见 `check_system.py` 的解码思路）；违规检查：OFF 后载波、超过 2 路供电 | 新写 VA 仪表 | 中 |

现有 checker 用 Python 实现，要转成题包内的独立 checker，还需按题包约定重写并做作者校准。

## 已知限制

- **只在旧 EVAS 上验证过。** 它在 `maxstep=10p` 时把斜坡过阈时刻定位在约 0.5 ps 内，checker 的时间容差取 1 ps；
  它会把每个 `transition()` 输出在 t=0 从 0 V 拉起，checker 忽略 5 ps 前的边沿，校准测试用 `code_init=0`。
  这些是仿真器行为，Spectre 上需要重新确认。
- **checker 依赖旧 EVAS 的输出格式。** 换到 Spectre 时要改：`$strobe` 记录在 Spectre 日志里，边沿记录仪的
  `ttol=1e-15` 会让 Spectre 步长很小，`Edges` 的初值处理也要按 Spectre 的直流初值重新确认。
- **层次模型里的导出在旧 EVAS 上看不到。** 旧 EVAS 0.8.7 不输出 Verilog-A 层次子模块中的 `$strobe`，所以 M5 的导出检查用网表级连接的整链（m5/check_m5.py）；
  系统顶层打开 M5 参数后，在旧 EVAS 上验证了 RF 输出能正确解码（11/11 个后续符号），导出记录要等 Spectre 或新 EVAS 确认。
- **整链检查的时间容差是 2 ps。** 旧 EVAS 定位一个过阈时刻的误差约 0.5 ps，调度器边沿又是从另一个过阈时刻推出来的，所以 m4/m5 整链比较取 2 ps。
- **CDC 还没定。** 链路和系统测试里 bit 时钟与 RO 同频、相位固定，这只是测试条件（SPEC.md 第 5 节）。
- **占位参数。** n_pre=2、预置相位 φ₀=0、输出幅度 A_ro 和 G_pa 都是占位值，待提参替换。
- **为旧 EVAS 做的写法取舍。** 调度器用两个供电槽而不是数组，宏全部展开；这些仍是标准 Verilog-A。
- **还没做的。** PA 压缩与 AM-PM（建模方式待定）、供电纹波与互耦、其他 RO 架构、M6 其他调制、CDC。
