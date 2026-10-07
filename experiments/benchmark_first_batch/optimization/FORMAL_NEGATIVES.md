# 四个正式任务的24负例准备

`prepare_formal_negatives.py` 仅调用主树现有runtime.prepare，未调用execute/SSH/Spectre。
实际准备目录为主树ignored `runs/optimization-formal-negatives-v2`，包含prepare.py、
plan.json（24提交）、manifest.json（72条件）以及每个负例全部3个冻结条件包。
不覆盖已有目录或证据。准备时主树revision c726ef3f，评分helper与reviewed
8e4a7a186f4d171d4042b1e2105c8d0a569050b1字节相同，SHA256
`dfd6aa6baae8e604896068a65575ab4890da29888a3d707a4f52bf8e90ffa71c`。

24个原负例全部通过实际performance source guard及core文件/宏/include guard，
没有日志打印、native统计读取或控制系统任务阻挡功能求解。这里的通过只是源边界
预检查；编译状态全部unknown，必须由后续真实运行确认。若某负例编译失败，需记录
该失败并诊断，不能拿它代替语义错误被独立oracle拒绝的证据。

| 类型 | 负例 | 预期整题判据 |
| --- | --- | --- |
| 纯无效优化 | 四题各一个unchanged（bound/poll/poll/oversampling） | 全功能应通过，唯一performance条件必须因步数比率不达0.1失败；非性能单条件可得1。 |
| 分辨率/精度错误 | VCO reduced_resolution、undersample | 32/2点每周期违背公开至少64点约束，不能用步数下降得分。 |
| 时序语义错误 | power coarse_poll；SAR coarse_poll、early_bit_calendar | 超过2ns公开事件误差或改位周期。 |
| 波形/控制错误 | VCO frozen_low_band、wrong_phase、wrong_amplitude；power no_hysteresis、no_qualification、stale_qualification；SAR no_input_hold、restart_while_busy；UART msb_first、no_start_validation、no_stop_check | 至少一个合适条件必须由实际oracle拒绝；不要求每个单条件都零分。 |
| 有限边沿错误 | power/SAR/UART各no_transition | 当前原始PSF逐点固定rise检查必须拒绝理想跳变。 |
| 混合负例 | UART eight_times_baud | 即使功能通过，8x仍不足0.1步数比；0.125bit量化也可能违反0.08bit合同，实际结果决定拒绝路径。 |

unchanged均以实际lexer有效token确认等价合法基线；power只少两行数值guard解释
注释，源码SHA不同但有效token完全相同。各自原始source hash与合法baseline hash均
在plan保留，不改写负例来强制哈希一致。

条件隔离的private packet一分只表示该条件成功。frozen_low_band在low-band、
wrong_phase在恒频、no_stop_check在无framing错误条件、no_start_validation在无假start
条件可能通过，所以实际校准应保留72条件原分母，并按全题至少一个预定负例失败
判断覆盖。不能把单条件功能一分误报整个负例绕过checker。

准备产物无job ID、无simulator结果，不能计入已校准数量。远端执行、共享slot和
unknown job恢复仍由主任务协调。Flash第五题不在此准备清单，尚待准入review。
