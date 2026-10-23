# IR-UWB TX 种子链（8DPPM+8FSK，4.032 Gb/s）

这里交付 IR-UWB 发射机种子链的 Verilog-A 系统，后续 vaBench 题目从这套已验证的模块里切出。
需求来自用户提供的工程 SPEC（《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》），只做其中 Verilog-A 的部分；
行为约定、来源和建模选择见 [SPEC.md](SPEC.md)，任务记录见 [#223](https://github.com/BucketSran/vaEVAS/issues/223)。

## 现状（2026-10-22）

第一里程碑 M1–M4 的 9 个模块和系统顶层已写完，全部检查在旧 EVAS 0.8.7 上通过。
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

整链 4097 个符号（分 8 段）全部通过：每个 PG 窗口、每个支路的供电/预充电/释放边沿、门控和冲突都与独立重放一致。

**checker 能否检出错误。** 用 25 个典型错误版本（如不做反 Gray、用绝对位置、码跳变时重置相位、校准判决方向反了、
没有参考缺失看门狗、不留准备帧、单通道、不报 overrun、调度抢占忙碌槽、热请求重新预充电、不保持、保持窗口不扣 T_pre、
不抢占空闲 HOLD、忽略极性或 DPC）逐个替换 gold 重跑，25 个全部被判失败，见 [test/mutants.py](test/mutants.py)。
尚未覆盖的场景列在 [SPEC.md 第 6 节](SPEC.md#6-验收)。

## 目录

```text
ir-uwb-tx/
├── SPEC.md      # 系统行为约定：常量、模块规则（来源/选择/待定）、验收
├── module/      # 9 个模块
├── system/      # 系统顶层 uwb_tx_seed
└── test/        # 激励源、边沿记录仪、各里程碑 checker、错误版本校准
```

## 怎么运行

每个 checker 自己生成测试台、调用仿真器、独立计算期望并写出 `checks.json`。结果默认写到 git 忽略的
`runs/uwb-tx-vabench-20261022/evas/`，可用环境变量 `UWB_OUT` 改。

```sh
cd benchmark/material/draftbench/circuits/ir-uwb-tx/test
python3 run_all.py                   # 全部检查加错误版本校准，约 15 分钟
python3 m1_data/check_m1.py          # 串并 + 编码器，约 2 分钟
python3 m2_clock/check_m2.py         # 主 RO + 校准，约 1.5 分钟
python3 m3_pulse/check_pg.py         # 脉冲发生器，几秒
python3 m3_pulse/check_rf.py         # RF 支路 + 包络，几秒
python3 m4_chain/check_chain.py      # 整链，5–8 分钟
python3 system/check_system.py       # 系统顶层，含 44.5 µs 校准，约 5 分钟
python3 mutants.py                   # 错误版本校准，约 1.5 分钟
```

单项可以只跑某个场景，例如 `python3 m4_chain/check_chain.py conflict`。耗时是 2026-10-22/23 在本机旧 EVAS 上的实测，两次运行之间差别可达 1.8 倍。

仿真器由 `UWB_BACKEND` 选择：`legacy`（默认，旧 EVAS 0.8.7）或 `evas`（当前 main，目前大多失败，见 #229）。
旧 EVAS 是 vaBench r53 认证时用的版本：从 `legacy/EVAS` 的提交 `6cb6fa7a` 用 `git archive` 导出，
编译其 Rust 内核并准备装有 numpy 的 Python，再用 `UWB_LEGACY_SRC`、`UWB_LEGACY_PY` 指过去
（默认指向本机 git 忽略的 `runs/legacy-evas-0.8.7/`，重建步骤见那里的 README；2026-10-23 机器重启清空了原来的 `/tmp/legacy-run`）。

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
- **CDC 还没定。** 链路和系统测试里 bit 时钟与 RO 同频、相位固定，这只是测试条件（SPEC.md 第 5 节）。
- **占位参数。** n_pre=2、预置相位 φ₀=0、输出幅度 A_ro 和 G_pa 都是占位值，待提参替换。
- **为旧 EVAS 做的写法取舍。** 调度器用两个供电槽而不是数组，宏全部展开；这些仍是标准 Verilog-A。
- **还没做的。** M5 非理想矩阵和监测导出、M6 其他调制、vaBench 出题。
