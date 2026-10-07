# 独立诊断配置

这里的三项诊断不替换此前五项配置的失败或 I。hidden 的 1ps 配置只将两个 timer 的第三参数从 1fs 改为 1ps，保留 cross。nocross 配置保留 1fs timer，只删除 cross 回调，因此 h/y 的独立答案为 0，n/q/m 和积分 z 的答案不变。mixed 源程序完全不变，只增加 ±0.25ns 保存点。

checker.py 使用新冻结身份，以加入明确的 nocross 答案。原 mixed/hidden 的二进制字面量 Fraction 公式、1e-7/1e-6V 电压标准和 1ns 外部事件标准均未改变。FROZEN_CALIBRATION.json 保留实际执行前固定的 16 项正例、故障和缺观测校准；calibrate.py 独立重现这些断言。

在本目录运行：

```sh
python3 -B calibrate.py
```

Spectre 从各 fixture 目录执行 tb.scs，compile.va 包含同一份 dut.va。EVAS 使用同一 dut.va 和对应的 coarse/fine JSON manifest，保持原数值域及原求解器预算。任何新执行都应记录 frontend/kernel/source 身份及实际 request/response。

配套 experiments/backends/ordered-event-sources/diagnostics-v5 保存实际紧凑结果与 receipt。原始日志、波形及历史二进制只在本地保存，未包含在公共材料中。精确端点及同记录内回调顺序仍未获证明。
