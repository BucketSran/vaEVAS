# Cadence 安装库：VA 测量与激励示例

来源为本仓库已有 IC618Hotfix4、ICADVM201 安装库参考资料，读取时仓库提交
`ad6f3577da261aedf51d33f13768c2b887f3bfa9`。文件与原始来源映射见 [SOURCES.md](../../reference/veriloga/SOURCES.md)，没有把安装资料登记为开源项目。

2026-10-10 静态阅读的文件：

| 文件 | 已有行为 |
| --- | --- |
| [delta_probe.va](../../reference/veriloga/cadence/measurement_stimulus/delta_probe.va) | 按阈值事件测时间间隔 |
| [find_probe.va](../../reference/veriloga/cadence/measurement_stimulus/find_probe.va) | 按时间或事件取样 |
| [crossing_detector](../../reference/veriloga/cadence/measurement_stimulus/crossing_detector__icadvm201.va) | 阈值穿越转换为脉冲 |
| [slew_rate_meas](../../reference/veriloga/cadence/measurement_stimulus/slew_rate_meas__icadvm201.va) | 设置供电与反馈，等待后施加正向阶跃，测两次输出上升穿越的时间差 |

`slew_rate_meas` 用 `(vend-vstart)/(tend-tstart)` 报告压摆率。它说明 VA 模块可以同时组织激励和测量，但当前实现只有正向阶跃和上升穿越。双向阶跃是我们拟增加的要求，需独立设计，不是此文件已有能力。

这些资料按仓库约定仅供内部研究；没有确认可公开再分发原代码。新题的实现自行编写，先选公开可使用的 DUT。此页只登记方法来源，不能据此填上“已选定运放”或“已验证后端”。本轮未编译或运行这些模块。
