# 仿真实现优化任务与取证

这些目录保存原创电压域模型、等行为合同的优化提交与独立判据。
本目录保存五个已准入的正式任务资产及两项未准入候选。VCO/power/SAR/UART按
accepted steps评分，Flash按原生intrinsic tran CPU评分。正式参考15个条件和Flash二分替代实现3个条件全部通过。30个负例各有至少一个
条件被拒绝，其90条件分为语义失败63、性能失败5、局部通过22。完整清单共108个
主条件，封存审计没有pending，36个变体全部符合校准预期。结果见
[formal_calibration_receipt.json](formal_calibration_receipt.json)与
[FORMAL_CALIBRATION.md](FORMAL_CALIBRATION.md)。DAC/SC保持候选身份。
只有实际仿真功能通过、已定位瓶颈且重复性能结果超过波动后，才写正式任务包。

| 模型 | 固定工程工作 | 工程成本 | 状态 |
| --- | --- | --- | --- |
| vco_boundstep | 20 us 低频 PLL VCO，另验连续调谐与高频 | 按最高频率约束全部时间步 | quiet五对步数/CPU/进程均5/5减少；正式参考与6负例已正式校准 |
| flash_thresholds | 100 us、10000 次 flash ADC 转换 | 连续重复扫描真实阈值阵列 | 事件内线性扫描五对CPU与进程均5/5减少；正式参考、6负例和二分替代已校准 |
| power_monitor | 100 us 电源资格/迟滞监督 | 1 ns 轮询驱动的真实 timer 求值 | 合法基线修正后功能过；quiet五对稳定减少；正式参考与6负例已正式校准 |
| sampled_dac | 100 us、10000 个 12-bit 采样电压码 | 连续重复真实位权解码 | 双侧 3/3，单轮无收益；待剖析或替换 |
| uart_calendar | 100 ms、10帧8N1状态消息 | 空闲仍16x波特率采样真实串行线 | quiet五对稳定减少；正式参考与6负例已正式校准 |
| sar_calendar | 100 us、20次12bit SAR转换及每位DAC试探 | 空闲仍1ns轮询真实控制输入 | quiet五对稳定减少；正式参考与6负例已正式校准 |
| sc_coefficients | 100 us、10000 次四级滤波采样 | 连续重复求实际采样系数 | 双侧 3/3，单轮微差不足立题 |

每项 `REQUEST.md` 说明工程场景、功能合同与实际运行请求；`cases.json` 给出固定网表，
`baseline.va` 和 `reference.va` 分别是待比较提交。`negative/` 为针对合同的错版与
无效优化。五个正式任务各6个负例的实际结果见封存收据；候选负例仍未正式校准。`evaluate.py` 只用公开数学/电路合同算预期，
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

SAR加入时为独立候选，补充试探工程瓶颈；当时target_task_count=5、task_count=0，
候选数不等于正式题数。`test_sar_calendar.py` 三组纯fixture不作为 actual 证据。

UART加入时让候选总数为7，当时正式题为0；`test_uart_calendar.py`不执行VA。

`third_calibration.json` 保存第三轮15份actual归档的native统计、merged流及源码/网表/
波形身份，功能15/15过。power数值修复没有减少100102accepted步，不是优化成绩。
SAR完成20转换/240决策，native102889→4467步；UART接收10帧/80位，native186759→2822
步。这些数字定位实际timer调度成本，只是单次并发功能轮，不替代五对重复测量。
UART每侧warmup+五对净PSF约266.2MB，也超256MiB硬上限。现实现paired完整PSF
判读后lossless gzip，逐字节解压SHA相同才删除重复原件；主功能PSF不压缩。
见scoring_prototype/README.md与lossless_psf_calibration.json；1GiB profile不可用。

五个正式资产在`benchmark/tasks/optimize-*`，准入配置为`admission_step_tasks.json`与
`admission_flash.json`。各题完整成功要求全部3个条件通过；性能条件在同job
保存两侧warmup及5对AB，逐次功能通过后才计算原生指标。private单条件一分不代表
整题成功。实际参考、负例及替代实现状态由最终封存收据记录，不由目录存在推导。

quiet四题历史配对收据见[QUIET_PAIR_RECEIPT.md](QUIET_PAIR_RECEIPT.md)，Flash事件内
扫描见[EVENT_ONLY_ADMISSION.md](flash_thresholds/profile/EVENT_ONLY_ADMISSION.md)。
这些独立分包准入测量保留原身份，不改称正式同job评分。新参考保留255次线性比较，
只在真实采样事件计算；旧二分实现原样保存，旧测量CPU下降但进程反慢的结果也保留。
它在公开CPU合同下是合法替代实现，已实际3条件通过，不算负例。CPU满分只证明CPU
规则通过，不能据此声称所有实现端到端更快。完整进程计时始终另列，网络/调度耗时
也不能混入intrinsic tran CPU。

最终封存审计核对完整条件清单、冻结candidate/package/criteria与封存manifest、
results/report字段一致性、主功能完整raw PSF及每条paired gzip。解压核原始字节数和
SHA后，当前独立oracle重判全部保存点；每条native/merged流重解析错误和统计，
重算AB顺序及性能摘要。192次paired子求解完成完整波形无损核验，压缩在solver
计时之外，未截断点或日志。最大archive为82,702,392B，最大封存成员总字节数为
134,491,453B，均低于256MiB；这些是本次实际校准观测，不保证任意候选不会超额。
该审计是对已执行档案的重新核验，不是新仿真，也不运行档案内checker代码。
原始完整封存档案只在本地ignored runs保留，公开精简收据的hash不是下载地址。
它不证明两保存点之间的任意连续毛刺，也不声明开源后端重评分或Agentic通过。
历史unknown/失败运行继续保留，不替换为成功结果。

正式Flash参考性能条件的CPU中位ratio为0.932565，进程诊断ratio为0.875564；二分
替代实现分别为0.843996和1.071898。两者都通过公开CPU规则，但二分实现整体较慢。
这些是正式同job校准数值，与历史quiet准入测量分列，不替换其原始结果。
