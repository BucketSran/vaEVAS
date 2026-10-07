# 五个正式任务的30负例校准

当前五题各6个负例，共30提交、90条件，全部完成实际执行及封存审计，每个变体
至少一个条件被拒绝。负例包括24个semantic_neg、5个performance_neg和1个mixed_neg；
90条件中语义失败63、性能失败5、局部通过22，没有编译/基础设施失败替代拒绝证据。
最终结果见[formal_calibration_receipt.json](formal_calibration_receipt.json)，完整审计
范围见[FORMAL_CALIBRATION.md](FORMAL_CALIBRATION.md)。Flash另有合法二分替代
3条件通过，角色为equivalent_cpu_only，不在负例30个分母中。

以下保留四题24负例的历史准备记录。

`prepare_formal_negatives.py` 仅调用主树现有runtime.prepare，未调用execute/SSH/Spectre。
实际准备目录为主树ignored `runs/optimization-formal-negatives-v2`，包含prepare.py、
plan.json（24提交）、manifest.json（72条件）以及每个负例全部3个冻结条件包。
不覆盖已有目录或证据。准备时主树revision c726ef3f，评分helper与reviewed
8e4a7a186f4d171d4042b1e2105c8d0a569050b1字节相同，SHA256
`dfd6aa6baae8e604896068a65575ab4890da29888a3d707a4f52bf8e90ffa71c`。

24个原负例全部通过实际performance source guard及core文件/宏/include guard，
没有日志打印、native统计读取或控制系统任务阻挡功能求解。这里的通过只是源边界
预检查；在准备时编译状态全部unknown，后来实际执行结果由封存收据记录。若某负例编译失败，需记录
该失败并诊断，不能拿它代替语义错误被独立oracle拒绝的证据。

| 类型 | 负例 | 合同与整题拒绝判据 |
| --- | --- | --- |
| 纯无效优化 | 五题各一个unchanged（bound/poll/poll/oversampling/scan） | 全功能应通过，performance条件因步数ratio不达0.1或Flash CPU ratio不达0.97失败；非性能单条件可得1。 |
| 分辨率/精度错误 | VCO reduced_resolution、undersample | 32/2点每周期违背公开至少64点约束，不能用步数下降得分。 |
| 时序语义错误 | power coarse_poll；SAR coarse_poll、early_bit_calendar | 超过2ns公开事件误差或改位周期。 |
| 波形/控制错误 | VCO frozen_low_band、wrong_phase、wrong_amplitude；power no_hysteresis、no_qualification、stale_qualification；SAR no_input_hold、restart_while_busy；UART msb_first、no_start_validation、no_stop_check | 至少一个合适条件必须由实际oracle拒绝；不要求每个单条件都零分。 |
| Flash采样/阈值错误 | falling_edge、wrong_skew_sign、no_hold、uniform_thresholds | 保持原sample/hold、非均匀阈值与边沿合同；至少一个条件由独立oracle拒绝。 |
| 有限边沿错误 | power/SAR/UART/Flash各no_transition | 当前原始PSF逐点固定rise检查必须拒绝理想跳变。 |
| 混合负例 | UART eight_times_baud | 即使功能通过，8x仍不足0.1步数比；0.125bit量化也可能违反0.08bit合同，实际结果决定拒绝路径。 |

unchanged均以实际lexer有效token确认等价合法基线；power只少两行数值guard解释
注释，源码SHA不同但有效token完全相同。各自原始source hash与合法baseline hash均
在plan保留，不改写负例来强制哈希一致。

条件隔离的private packet一分只表示该条件成功。frozen_low_band在low-band、
wrong_phase在恒频、no_stop_check在无framing错误条件、no_start_validation在无假start
条件可能通过，所以实际校准应保留72条件原分母，并按全题至少一个预定负例失败
判断覆盖。五题完整负例分母为90条件；实际审计按全3条件判断30个变体，每个
预定负例须至少一个功能或性能条件被拒绝。不能把单条件功能一分误报整个负例绕过checker。

历史准备产物本身无job ID或simulator结果，不能作为执行证据。此后远端执行、
共享slot与unknown job恢复由主任务协调，Flash6个负例在另一实际校准批次完成。
源guard拒绝、编译失败、求解失败与语义/性能拒绝必须分开，不从失败档案制造性能
分母。最终审计核完整raw封存、原生统计、每次paired功能及结构化判定的一致性；
`semantic_neg`、`performance_neg`与`mixed_neg`保留不同预期，不把30个都称语义错版。

24个语义负例的72条件为语义失败61、局部通过11；5个纯性能负例的15条件为性能
失败5、非性能条件通过10。UART mixed负例的3条件为语义失败2、局部通过1。上述
局部成功不会让完整负例得分，也没有从校准分母移除。正式参考5个变体15条件和
Flash合法替代1个变体3条件全部通过，连同30负例共36个变体全部符合预期。
