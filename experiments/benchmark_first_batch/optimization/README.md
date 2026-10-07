# 仿真实现优化候选取证

这些目录保存原创电压域模型、等行为合同的优化提交与独立判据。
目前均为待 Spectre 取证候选，不是正式 Harbor 任务，不计已校准题数。
只有实际仿真功能通过、已定位瓶颈且重复性能结果超过波动后，才写正式任务包。

| 候选 | 固定工程工作 | 待证实的成本 | 状态 |
| --- | --- | --- | --- |
| vco_boundstep | 20 us 低频 PLL VCO，另验连续调谐与高频 | 按最高频率约束全部时间步 | v2 双侧 3/3 功能通过；低频步数差明显，待重复测量 |
| flash_thresholds | 100 us、10000 次 flash ADC 转换 | 连续重复扫描真实阈值阵列 | v1/v2 双侧均 3/3 功能通过；重复性能与 profile 待做 |
| power_monitor | 100 us 电源资格/迟滞监督 | 1 ns 轮询驱动的真实 timer 求值 | reference 3/3，baseline 2/3；浮点计时修复待重新执行 |
| sampled_dac | 100 us、10000 个 12-bit 采样电压码 | 连续重复真实位权解码 | 双侧 3/3，单轮无收益；待剖析或替换 |
| sar_calendar | 100 us、20次12bit SAR转换及每位DAC试探 | 空闲仍1ns轮询真实控制输入 | 三组解析fixture过；待actual双侧功能及profile |
| sc_coefficients | 100 us、10000 次四级滤波采样 | 连续重复求实际采样系数 | 双侧 3/3，单轮微差不足立题 |

每项 `REQUEST.md` 说明工程场景、功能合同与实际运行请求；`cases.json` 给出固定网表，
`baseline.va` 和 `reference.va` 分别是待比较提交。`negative/` 为针对合同的错版与
无效优化，是否编译和实际拒绝仍须校准。`evaluate.py` 只用公开数学/电路合同算预期，
不导入参考实现，也不使用其波形定义正确性。

`test_oracles.py` 的七组纯解析测试已经运行通过，检查相位积分/钳位、波形采样不足、
阈值单调与越量程、资格时间/迟滞边沿、DAC 采样保持和同时滤波级递推。它们不是 VA 仿真校准或性能证据。

所有原型均从本次电路要求独立编写，没有复制来源许可不明的历史 VA 文件。
Spectre 由协调者通过既有 harness 排队，最多四并发；本目录不新增远程编排。
性能结果遵循 benchmark-checklist：同机/版本/设置、编译热身分开、至少五对交替，
报告 actual accepted/rejected steps 与 CPU/elapsed、端到端时间、错误数、负载及 limiter。
保存波形点数不等同于实际接受步数。未超过运行波动的候选退回，不降低判据。

`first_calibration.json` 来自十二份实际回收归档，由 `summarize_archives.py` 读取，
保留源码/判据/归档身份与求解分项。首轮并发数据只用于选负载，性能结论为 inconclusive。
Spectre 默认日志未提供 rejected steps 时记 null；末尾 aggregate elapsed 与 CPU 相同，
与过程独立墙钟不符，因此不作为墙钟主指标。后续使用 intrinsic tran 分项和独立计时。

`second_calibration.json` 保存 v2 三十份实际归档的原生求解统计，仍是并发首轮，不能
声明性能收益。`second_waveform_replay.json` 在这些原始波形上回放新增的有限 transition
判据：29/30 通过，唯一失败是旧 power baseline 的资格时间偏差。回放不是新 VA 执行。

power 基线慢速 case 的首个高电压轮询为 20.001 us，25.001 us 时未使能；
保存时间按双精度相减为 4.9999999999999996 us，小于 5 us，导致又等到 25.002 us。
修复在时间比较加一百万分之一 poll_period（当前 1 fs）的数值裕量。该变化仅修
基线数值边界，checker 的 2 ns 边沿容差保持不变，不计作优化，修复后必须重新实际
校准。已有旧波形仍保留失败。禁止用失败基线的计时取得正式性能成绩。

新增 SAR 事件日历是独立候选，补充试探工程瓶颈，target_task_count 仍 5，task_count 仍 0；
候选数不等于正式题数。`test_sar_calendar.py` 三组纯fixture不作为 actual 证据。
