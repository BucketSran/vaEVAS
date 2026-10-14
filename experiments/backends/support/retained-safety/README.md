# 两项错误接受的修复

这轮只修复两类原 main 会错误接受的请求，没有新增 Q 档资格。
夜间集成版此前重跑原 70 条请求仍为 12/70 完成；本轮 main 适配不宣称新增整题完成。
测试判据、历史成绩和 #131 均保留。

| 问题 | 修复前 | 本轮结果 | 实际 Spectre 对照 |
| --- | --- | --- | --- |
| 空循环中引用未声明节点 | 循环展开后引用消失，编译成功 | 先检查原始语法树，返回 `undeclared_node` | 同源非法例返回 VACOMP-2212；合法对照正常运行 |
| 修改参数后生成当前时刻的 timer | 误当作过去或已经消费的事件，漏回调仍返回成功 | 按 timer 叶子和精确时钟确认是否消费；新出现的当前事件明确拒绝 | 两个反例均发生一次回调；正常改周期的计数与 EVAS 相同 |

例如固定事件在 t=0.5 将 `b` 从 0.75 改为 0.5，另一个 `timer(b,0,0.001)` 此时需要触发。
旧 main 的计数始终是零。修复后返回 `event_resolution`，提示需要同刻闭包。
这修正了错误成功，**还没有实现该模型的完整仿真**。
已经消费的同一个 timer 在回调中修改周期，仍按原绝对相位继续；不会重复触发。
不同 timer 即使共用一个 OR 事件体，也分别记录是否消费。

## 验证了什么

基线为 main `ff5d0fd9bc4dbeafe7fc91e233ad97880155a233`，适配生产提交为 `b053ac6545c23045d5bee29d1621ff9b866602d1`，沿用 EVAS 0.15.0 / IR19。
本目录保存五个同源 VA/SCS 输入及[结果摘要](comparison.json)。三次 timer 对照检查
0、0.0625、0.125、0.375、0.625、0.875、1 秒的原生输出，没有插值或缺点。
两个新当前事件的 Spectre 输出分别为 `[1,1,1,1,1,1,1]` 和 `[0,0,0,0,1,1,1]`；
EVAS 明确拒绝。正常改周期的输出两端均为 `[1,1,1,2,3,4,5]`。
固定预算为 1e-8 V，实际导出计数相同；这不是连续波形精度或内部回调时刻的认证。

实际 Spectre 版本为 21.1.0.509.isr12。timer 输入请求 reltol=1e-9、vabstol=1e-11 V、
iabstol=1e-15 A、maxstep=0.03125 s 和 conservative；原生记录显示 reltol=1e-10、
gear2only，其余上述控制不变。timer 的语言时间容差为 0.001 s；本轮不要求复制跳变处的取侧。
编译准入对照使用单独保存的 deck，不能把它的 traponly 设置套到 timer 上。
EVAS 请求 reltol=0、vabstol=1e-8 V，原输入与查询时刻不变。

开发回归另检查开启当前事件、OR 兄弟叶子、过去/未来时间、周期改写、积分历史，
以及同一 Controller 失败后的原状态保留和合法重试。
测试入口为 [动态 timer](../../../../evas/tests/test_dynamic_timer.py)、
[边界证书](../../../../evas/rust_core/src/schedule_timer_boundary_tests.rs)、
[失败后重试](../../../../evas/rust_core/src/transient_timer_boundary_tests.rs)和
[空循环声明](../../../../evas/tests/test_event_body_loops.py)。

## 证据和保留范围

本目录的输入、摘要与生产回归属于 repository-contained。
Spectre 原始日志、PSF、输入/输出 manifest 和执行收据属于 **local-only**，位于
`current/runs/evas-night-20261014/retention-spectre-v1/`；摘要保留文件哈希及原生输出。
五次执行均检查过输入、输出和工具身份，未把本地路径冒充公共下载地址。
原始资料没有因本轮提取而删除，公开论文复现还需要发布可取回归档。

夜间原分支 `codex/evas-night-source-transition` 保留。它依赖尚未合入的 R01 父级，
不能把局部通过直接算成 main 支持。初始化后的历史种子错误已独立复现，值得单独适配 main；
条件流场的根窗口修复需随 R01 一起审查。
源驱动 transition、数组/循环、更多语言准入和边界精度扩展仍有实现或验收缺口，
不随本轮两项安全修复合入。相关需求继续由
[#65](https://github.com/BucketSran/vaEVAS/issues/65) 和
[#96](https://github.com/BucketSran/vaEVAS/issues/96) 跟踪，不以此关闭整个 issue。
