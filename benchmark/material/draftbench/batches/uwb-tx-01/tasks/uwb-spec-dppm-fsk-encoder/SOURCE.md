# uwb-spec-dppm-fsk-encoder 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的编码器，行为约定见 [ir-uwb-tx/SPEC.md 第 4.3 节](../../../../circuits/ir-uwb-tx/SPEC.md#43-8dppm8fsk-编码器uwb_dppm_fsk_encoder8)。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）§6.3：symbol<5:3> 为 DPPM Gray 信息、symbol<2:0> 为 FSK Gray 信息；P[n] = (P[n−1] + D[n]) mod 8，P[−1] = 0；在 symbol_valid 下降沿收字；encoded_valid 上升沿供后级锁存，重复字仍产生新上升沿；ro_request 只是独热选频请求。
- 位置递推与主参考论文同组前作一致：Lei 等，[JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 式 (1)，`PPC_i ≡ D16PPM_i + PPC_{i−1} (mod 16)`（原文是 16 阶，本题是 8 阶种子）。
- 参考解与系统资产中的 [dppm_fsk_encoder8.va](../../../../circuits/ir-uwb-tx/module/dppm_fsk_encoder8.va) 相同，只把模块名改为 `dppm_fsk_encoder8`。系统资产的独立检查见 [ir-uwb-tx README](../../../../circuits/ir-uwb-tx/README.md)。

## 建模选择

- 时间参数 t_enc、t_ev、t_pw、tr 的默认值（10 ps、30 ps、400 ps、2 ps）来自系统资产的选择，原 SPEC 没有给数值。允许范围按“种子链 1.488 ns 符号周期内能工作”取。
- 复位是异步的，并取消已排程但尚未开始的输出变化（S5）。原 SPEC 只要求“复位”，异步与取消是本题为让行为可判定而定的规则。
- 输出边沿规定为时长 tr 的线性边沿，验收用 vdd/2 过阈时刻，容差 2 ps。容差先按“远小于 t_enc，且能容纳仿真器定位误差”取：EVAS 0.8.7 在 maxstep 10 ps、tr 5 ps 时实测误差 1.25 ps。
- 预期难度：基础（D1–D2）。考点是 Gray 反码、差分位置递推、下降沿收字、重复字也要出新的 valid 脉冲、异步复位取消待发输出。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S1 下降沿收字、复位期间忽略 | debruijn、reset_repeat | reset_phases（复位期间的收字） | capture_on_rising_edge |
| S2 Gray 反码、P 递推、独热 | debruijn（64 码字、4096 相邻对） | params_two_instances、dense | no_gray_decode、absolute_position、one_hot_before_first_word |
| S3 数据延迟 t_enc 与边沿 | 全部 | 非默认参数 | data_without_delay |
| S4 每字一个 valid 脉冲，宽 t_pw | reset_repeat（重复字）、debruijn | 非默认 t_pw | fixed_pulse_width、no_strobe_for_repeat |
| S5 异步复位、P 归零、取消待发 | reset_repeat | reset_phases（t_enc 前、t_enc 与 t_ev 之间、valid 高时） | reset_keeps_position、reset_does_not_cancel |

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了参考解（同一事件触发的多个 transition 输出无法排序等，见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`）。
  2026-10-23 的结果见 `results/`：参考解 6 个用例、114 项检查全部通过；替代实现 1 分；9 个错误版本都是 0 分。
  原先的错误版本“enc_valid 跟随 sym_valid”实际与正确模型等价（捕获后 t_ev 时 sym_valid 总是低），已换成“重复字不出新脉冲”。
  EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。
