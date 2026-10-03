# 冒烟集（smoke）

每个 manifest 是一条仿真能力路径的最小可运行用例，只验证
“编译 → IR → 内核求解 → 输出”链路是否连通，不携带独立期望值，
不构成语义正确性证据。语义验证见上级目录的[条件与协议](../README.md)。

| 输入 | 覆盖路径 |
| --- | --- |
| [static_nonlinear.json](static_nonlinear.json) | 静态非线性求解 |
| [idt.json](idt.json) | 连续积分（连续动力学） |
| [absdelay.json](absdelay.json) | 延迟历史查询 |
| [timer_counter.json](timer_counter.json) | 定时事件 |
| [transition_pulse.json](transition_pulse.json) | 有限边沿转换 |
| [cross_counter.json](cross_counter.json) | 过阈事件 |

准入标准：保持短小、每条能力路径至多一个用例；
需要期望值或阈值时移入 `cases/`，不在本目录扩充。

演示 manifest 数据结构的单一示例保留在
[examples/](../../examples/README.md)（三课入门教学示例）。
