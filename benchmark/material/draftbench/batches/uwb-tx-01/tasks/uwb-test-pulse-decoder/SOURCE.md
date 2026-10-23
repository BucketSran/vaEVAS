# uwb-test-pulse-decoder 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链，系统行为约定见 [ir-uwb-tx/SPEC.md](../../../../circuits/ir-uwb-tx/SPEC.md) 第 2–6 节。题目的被测电路是种子链本身（公开台架 `testbench/chain/` 中的 8 个模块与 [module/](../../../../circuits/ir-uwb-tx/module/) 逐字节相同），求解者交付的是接在差分输出上的在线测量仪表。
- 本题没有现成 gold。参考解 `pulse_decoder` 是为本题新写的标准 Verilog-A，解码规则取自系统检查 [test/system/check_system.py](../../../../circuits/ir-uwb-tx/test/system/check_system.py)：|outp − outn| 超过 50 mV 的区间成组、组中心减半个窗口得到脉冲起点、DPPM 按位置差 mod 8、FSK 用中间一半窗口内的过零点、符号 = Gray(D)·8 + Gray(F)。种子链的格点 δ₀ = Ts/16、脉宽 9δ₀、8 个载频 f_k = 4.5 + k·3/7 GHz 见 SPEC.md 第 2 节；差分测量电压 outp − outn 见第 4.9 节。
- 差分位置递推与 Lei 等，[JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 式 (1) 一致（原文 16 阶，本链 8 阶）。
- 公开台架的连接照搬 [test/m4_chain/chain_tb.py](../../../../circuits/ir-uwb-tx/test/m4_chain/chain_tb.py)：理想 bit 时钟为 RO 的 6 倍、RO 码由理想源固定、发射端复位在第一个 bit 前释放；仪表的 clk 接主 RO 的 ph0。

## 建模选择

预期难度：难。考点是从连续波形做事件测量：|v| 双极性过阈与间隙合并、等到 t_gap 后才能确认脉冲结束、在不能动态索引数组的前提下保存过零点并在脉冲结束后按中心窗口计频、帧边沿的选取、差分解码与 Gray 码、三类错误判据、输出时序与复位。

与任务说明（briefs/t8-decoder.md）不同或补充的选择：

- **帧边沿取 t_s + δ/2 之前最近的 clk 上升沿**，不是任务说明写的“t_s 之前”。种子链的包络有约 11 ps 的一阶响应，加上载波相位量化，P = 0 的脉冲起点实测可早于帧边沿约 3 ps；按“t_s 之前”会把它算成上一帧的 P = 16 并判错。改后 P 取 0–15，P = 8–15 判错，与任务说明的终评设计一致。错误版本 `frame_before_ts` 专门检查这一点。
- **错误脉冲之后 P_prev = P mod 8**（每个脉冲都更新，含错误脉冲）。理由：位置偏离格点或载频不对时，四舍五入得到的 P 仍是最好的位置估计；而且这样下一个符号不受 err 判定影响，err 落在判据边界时不会连带改变后续符号。错误版本 `hold_pprev_on_err` 检查它。
- **终评的另一时钟频率用码 100（625 MHz，δ = 100 ps）**，不是任务说明举例的码 300。码 300 只比 672 MHz 高 0.4 %，7δ 内的位置差约 3 ps，“δ 按标称 672 MHz”的错误检不出来；码 100 差 7 %，合成用例另用 800 MHz 和 700 MHz 的理想时钟。
- **输出时序**：在 t_l + t_lat 同时更新 sym/err 并拉高 sym_valid，高 t_pw；后级在 sym_valid 下降沿取字，与种子链串并转换到编码器的接口一致。t_lat ≥ t_gap，因为脉冲结束要等 t_gap 才能确认。
- **参数默认值与范围**：v_det 50 mV、t_gap 100 ps、n_width 9、频率容差 3 %、位置容差 δ/4 按任务说明；t_lat 200 ps、t_pw 200 ps、tr 2 ps 为本题选择。t_gap 100 ps 的依据：公开用例里种子链脉冲内的最大间隙 25 ps，相邻脉冲间最小间隙 130 ps（P = 7 接 P = 0 时两个 9δ 窗口首尾相接）。
- **位置容差 δ/4 会把一部分健康脉冲判为错误。** 起点估计“首末过阈中点减半窗”受载波相位量化影响，种子链的位置误差 e 实测在 −3 到 +33 ps。公开用例（码 288）e ≤ 21 ps，全部不报错；终评码 100（δ = 100 ps）的 F = 6 冷启动脉冲 e ≈ 33 ps > 25 ps，11/90 个按规则报错。测量题如实报告即可，不要求 DUT 达标；是否改默认容差留给人工审核。
- **checker 的分辨率带（S9）**：|v| 的峰离 v_det 不到 1 mV 时，这个峰算不算过阈取决于采样，t_f/t_l 会跳半个载波周期；checker 在 v_det ± 1 mV 各测一次，把 t_f、t_l 当作区间，区间内都接受。|e| 距 tol_pos·δ 不到 2 ps、频率误差距 tol_f 不到 0.002 时 err 两值都接受。P 或 F 在分辨率内会取整到不同值、间隙离 t_gap 不到 10 ps、复位落在脉冲或待发输出期间等，都报“用例超出工作范围”（执行问题），不判模型。全部用例在参考运行中没有触发这些情况。
- **时间容差 3 ps**：sym_valid 过阈与 t_l + t_lat + tr/2 比较。参考解实测最大偏差 0.07 ps（脉冲结束时刻由仿真器的过阈定位给出，与 checker 的线性插值一致）；3 ps 远小于 t_lat、t_gap，可以区分“在判定时刻（t_l + t_gap）出字”的错误。maxstep 10 ps，种子链 RF 支路自带 1/(20f) 的步长上限，合成脉冲源 1/(40f)。
- **过零点保存**：EVAS 0.8.7 不支持动态数组下标，参考解用 32 个标量组成移位寄存器，正确替代实现用 32 个标量的环形缓冲（case 写入）。工作范围（载频 ≤ 8 GHz、脉冲 ≤ 1.2 ns、t_gap ≤ 300 ps）保证一个脉冲从首次过阈到判定时刻最多 24 个过零点，checker 会核对。
- **合成脉冲源** `tests/benches/test_burst.va`：升余弦包络乘载波，中心对齐，可设幅度（负值即反相）、初相、两段频率（窗口内一个频率、窗口外另一个）。checker 在 0.1 ps 网格上计算同一闭式，不读仿真波形。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S1 \|v\| 双极性过阈、t_gap 合并、t_l | chain288（种子链 120 个符号） | chain100_pol（随机极性）、synth_grid（反相、小幅度、不同初相）、chain288_two/a（v_det 100 mV、t_gap 80 ps） | strobe_every_crossing、positive_only |
| S2 δ 取实测时钟、帧边沿、P | chain288（码 288） | chain100_pol（625 MHz）、synth_grid（800 MHz，e = ±28 ps、P = 0 早到 12 ps）、synth_params（700 MHz） | nominal_delta、frame_before_ts |
| S3 中心窗口内过零计频、最近信道 | chain288（8 个载频） | synth_grid（信道间 5.10 GHz、±2–3.5 % 偏差、窗口外的边缘用 4.0/7.8 GHz）、synth_params（同上） | frequency_by_peaks、whole_pulse_window |
| S4 差分解码、Gray、错误脉冲后 P_prev | chain288（64 个符号全覆盖） | synth_grid、synth_params（错误脉冲后接正常脉冲） | absolute_position、no_gray、hold_pprev_on_err |
| S5 三类 err | chain288（全部 err = 0） | synth_grid（9 个错误脉冲：偏格、P = 8/9/12/15、频偏）、synth_params（tol_pos 0.15、tol_f 5 %）、chain288_two/a（tol_pos 0.2，16 个真实脉冲报错） | no_offgrid_err |
| S6 t_lat、t_pw、每脉冲一个 strobe | chain288 | chain288_two/a、synth_params/a（非默认 t_lat、t_pw、tr、vdd） | strobe_at_decision、fixed_strobe_width |
| S7 复位：P_prev 归零、输出拉低 | chain288（两脉冲之间复位一次） | 各用例另有一次复位，位置不同 | reset_keeps_pprev |
| 多实例与参数 | — | chain288_two、synth_params（n_width 7 使 P 整体加 1） | （以上各项在双实例中同时检查） |

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了种子链模型（多位同时翻转、数组、跨模块波形乘积等，见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`；当前 EVAS 若支持动态数组下标，参考解可改写得更短，但行为不变。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。合成脉冲源和仪表在 Spectre 上的过阈定位、`$bound_step` 与边沿记录格式需要重新确认（同 ir-uwb-tx README 的已知限制）。
