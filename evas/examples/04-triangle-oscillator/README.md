# 第 4 课：事件改变积分方向

本例将积分与事件组合成三角波振荡器。它依赖当前分支的历史根重定位候选，
尚不能据此声称已合入 main。

从仓库根目录运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas transient evas/examples/04-triangle-oscillator/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

`ctl=1` 表示速度为 1 V/s，`sign` 决定方向。初态 z=0，先上升；上限为 +0.5 V，
下限为 −0.5 V。到上限且仍在上升时换向，到下限且仍在下降时换向。
`count` 用电压数值输出换向次数。

## 为什么要指定穿越方向

```verilog
@(cross(V(z,r)-upper,+1,ttol,vtol)
  or cross(V(z,r)-lower,-1,ttol,vtol)) begin
  sign=-sign;
  n=n+1;
end
```

事件可能略晚于阈值的数学穿越时刻。此时 z 已越过阈值，换向后会再次穿过同一阈值。
这次返回不应再次换向。两个定向 cross 把这个规则写清楚。
若改为双向 cross，返回也会被选择，可能产生额外事件；它是另一个模型。

换向时保留积分值，用新方向继续积分，不把积分重置为零。理想换向时刻是
0.5、1.5、2.5 s。预设观察点避开这些事件窗口，独立答案为：

| t / s | z / V | count |
| ---: | ---: | ---: |
| 0 | 0 | 0 |
| 0.25 | 0.25 | 0 |
| 0.75 | 0.25 | 1 |
| 1 | 0 | 1 |
| 1.25 | −0.25 | 1 |
| 1.75 | −0.25 | 2 |
| 2 | 0 | 2 |
| 2.25 | 0.25 | 2 |
| 2.75 | 0.25 | 3 |
| 3 | 0 | 3 |

EVAS 输出 `transient.events` 给出事件时刻；输出点之间没有采样，不代表漏事件。
[回归](../../tests/test_history_relocalization.py)直接加载本例，检查手算值、换向时刻、
观察网格变化，以及等价的乘积 guard。

## 在 Spectre 中检查同一模型

`tb.scs` 使用同一份 `dut.va`，固定相同初态、输入与最大步长。从本目录执行：

```sh
triangle_run=$(mktemp -d)
spectre -64 tb.scs +log "$triangle_run/spectre.log" -format psfascii -raw "$triangle_run/psf"
```

需要已有 Spectre 安装及许可证。每次使用新的输出目录。
该网表含 Spectre 专有求解设置；EVAS 使用上面的 `sim.json`，不要将其视为通用网表输入。
两边内部设置不同，共同外部验收为波形误差 1 µV、事件时刻误差 200 ns，换向恰好三次。
定向模型仍有积分与事件定位误差，方向正确不代替精度检查。

模型与已校准的[候选参考解](../../../benchmark/tasks/va07-triangle-repair/solution/dut.va)
一致；本例固定单位速度，变化速度的证据见[兼容性实验](../../../experiments/backends/dvs2-spectre-validation/README.md#oscillator-compatibility)。
原始双向模型继续保留为[诊断探针](../../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic)，
兼容性问题由 [Issue #70](https://github.com/BucketSran/vaEVAS/issues/70) 跟踪，没有算作已修复。
本例的新执行结果见[示例对照](../../../experiments/backends/dvs2-spectre-validation/README.md#triangle-example)。
