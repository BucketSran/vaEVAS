# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。

## checker 的失败类别

只有一类：`out` 或 `metric` 的保存点落在允许范围之外超过 2 mV。允许范围由轨迹律给出，其中每个事件可以提前或推后至多 50 ps。失败记录的 `node`、`event` 与 `event_kind` 给出输出名和该点之前最近的复位或采样事件。50 ps 事件容差内外的时间变体由作者证据里的 Python 合成轨迹覆盖。

## 语义依据

被拒预期按 Verilog-A LRM 2.4 的 4.5.8（`transition()`）与 4.5.9（`slew()`）写成，是预期，不是结果，每个条目都待 Spectre 校准。历史 Spectre 21.1 运行中，原 `slew()` 模型的每个斜坡都从事件前一个时间点开始，最多提前一个时间步，在 50 ps 事件容差之内。旧版 EVAS 0.8.7 提前一个 50 ps 行开始斜坡；事件不在网格上时（`vth-override`），旧版在穿越处插一行，斜坡从前一个网格行开始，提前 27.8 ps。旧版 EVAS 不能降低带后处理的 `slew()`，所以 `metric_from_out` 没有旧版判定；作者证据里另列了一个旧版能降低的写法。

## 候选与应拒用例

“所有用例”指 `base`、`rate-override`、`reset-and-start`、`vth-override` 共 4 个。

| 候选 | 行为 | 应拒用例 | 预期失败 |
| --- | --- | --- | --- |
| `no_slew` | 输出直接跳到目标（10 ps 过渡） | 所有用例 | `out`、`metric` |
| `rates_swapped` | 以 `fall_rate` 上升，以 `rise_rate` 下降 | 所有用例 | `out`、`metric` |
| `symmetric_rate` | 下降也用 `rise_rate` | 所有用例 | `out`、`metric` |
| `fixed_duration_transition` | 用满量程斜坡时间的 `transition()`：只有满量程阶跃的斜率是对的 | 所有用例 | `out`、`metric` |
| `step_per_sample` | 输出只在采样事件移动，每次至多斜率乘以距上次采样的时间 | 所有用例 | `out`、`metric` |
| `metric_from_out` | `metric` 是限速后的 `out` 除以 0.8，所以快 1.25 倍 | 所有用例 | `metric` |
| `metric_same_target` | `metric` 跟随 `env`，不是 `env/0.8` | 所有用例 | `metric` |
| `fixed_rates` | 忽略 `rise_rate` 与 `fall_rate`（固定 8e8 和 3e8 V/s） | `rate-override`、`vth-override` | `out`、`metric` |
| `no_upper_clamp` | 没有 0.8 V 钳位 | 所有用例 | `out`、`metric` |
| `no_lower_clamp` | 没有 0 V 钳位 | `base`、`rate-override`、`vth-override` | `out`、`metric` |
| `mode_inverted` | `mode` 高时保持峰值，低时释放 | 所有用例 | `out`、`metric` |
| `always_release` | 每次采样都释放到 `vin` | 所有用例 | `out`、`metric` |
| `always_hold` | 每次采样都保持峰值 | 所有用例 | `out`、`metric` |
| `peak_on_output` | 峰值保持比较 `vin` 与实际的 `out`，不比较保持的包络 | `rate-override`（采样落在上升斜坡中途） | `out`、`metric` |
| `sync_reset_only` | 只在 `rst` 为高的采样事件清包络 | 所有用例 | `out`、`metric` |
| `reset_ignored_while_high` | `rst` 为高时的采样照常更新包络 | `base`、`reset-and-start`、`vth-override` | `out`、`metric` |
| `reset_jumps_outputs` | 手写斜坡，清零时两路输出都从 0 V 重新开始 | 所有用例 | `out`、`metric` |
| `falling_clk_sample` | 在 `clk` 下降穿越采样 | 所有用例 | `out`、`metric` |
| `init_env_from_vin` | 包络从 t = 0 的 `V(vin)`（钳位后）起步 | 所有用例 | `out`、`metric`（从 t = 0 起） |
| `fixed_vth` | 门限固定 0.45 V（`clk`、`mode`、`rst` 都用它） | `vth-override` | `out`、`metric`（事件提前） |
| `alt_explicit_ramp`（正确） | 不用 `slew()`：每路输出是从上一事件时的值出发、按 `$abstime` 计算的斜坡 | 无 | 无 |
| `alt_clamp_then_compare`（正确） | 先钳位 `vin`，再释放或取较大值 | 无 | 无 |
| `alt_above_reset`（正确） | 用 `above(V(rst) - vth)` 清零，不用上升 `cross()` | 无 | 无 |

## 非默认门限（p0-fix-a）

私有用例 `vth-override` 按审核 F05 加入：`vth` 0.8 V，`rise_rate` 4e9 V/s（合法上限），`fall_rate` 1e9 V/s，所有控制边沿都是 200 ps（合法上限）。0.45 V 门限会把每个上升穿越提前 77.8 ps，超出 50 ps 事件容差 27.8 ps：在 4e9 V/s 的上升上偏 111 mV，在 1e9 V/s 的下降上偏 27.8 mV。10 个事件中有 7 个改变包络，这 7 个都看得出提前量；另外 3 个采样不改变包络（对较低输入的保持、`rst` 为高时的采样），看不出，列为例外。

- `fixed_vth` 只能靠 `clk` 与 `rst` 的穿越时刻暴露。`mode` 与 `rst` 的穿越离任何采样至少 1 ns，边沿最长 200 ps，所以它们在每个采样时刻都处在 0 V 或 0.9 V，用错门限读取它们不会改变采样结果。作者证据里的合成控制 `fixed-vth-mode-only` 因此通过；`fixed-vth-rst-only` 被拒，因为两次清零都提前了（27.8 mV）。
- `peak_on_output` 在 `vth-override` 上应通过：4e9 V/s 时每段上升在下一次采样之前早已结束，峰值保持采样读到的输出就等于包络。
- 该用例的最后一次清零在仿真终点前 22.2 ps，用来检查审核 F01 修正后的终点处理：推后 50 ps 生效的轨迹不再越过终点。

## 旧版 EVAS 不能运行的候选

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。旧版只给点值，不做可信证明，结果可能不准也不报错。

- `metric_from_out`：旧版不能降低带后处理的 `slew()`，报 `ERROR [rust_lowering]: model:0:slew_envelope_tracker_Model:continuous_body_not_lowered`。作者证据里不用 `slew()` 的显式斜坡探针在全部 4 个用例上都被拒。
- 其余 22 个候选在 4 个用例上的旧版判定都与矩阵一致，包括 p0-fix-a 新增的 `fixed_vth`（只在 `vth-override` 上被拒）。

命令、退出码和逐例结果见 `runs/t3-p0-build-20261027/r06-spec-slew-envelope/checks.json` 与 `runs/t3-p0-build-20261027/p0-fix-a/disposition.json`。
