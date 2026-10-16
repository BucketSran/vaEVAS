# Pulse delay 缺省值的有限对照

线性 pulse 可省略 `delay`，取 0 s。其余 `val0/val1/rise/fall/width/period` 仍须显式提供。
安装版 Spectre 21.1.0.509.isr12 的 `spectre -h vsource` 报告 `delay=0 s`；其他参数默认值涉及不同规则，本次不扩展。
默认值只在 [scs_sources.py](../../../../evas/src/evas/scs_sources.py) 进入原有 PWL 构造前补入，调用者参数不被修改。
正边沿、周期、宽度、点数上限、时刻分辨率和电压误差约束沿用[源合同](../../../../evas/README.md)。

[固定输入](inputs.json)把省略 delay 和显式 delay=0 的两个源置于同一次仿真，输出均为输入的两倍。
源为 `val0=-.25,val1=.75,rise=.125,fall=.125,width=.25,period=1`，只在第二例改变 stop/maxstep。
独立答案以 `p=t mod 1` 定义：`p<.125` 时为 `-.25+8p`，`.125<=p<.375` 时为 `.75`，
`.375<=p<.5` 时为 `.75-8(p-.375)`，其余为 `-.25`。输出为这个值的两倍。
这同时检查初始值、上升、平台、下降和下一周期，不依赖 EVAS 生成的源点作为答案。

[实际有限配对](reference.json)保留两次 Spectre 执行与新 EVAS 源构造身份。固定电压门槛为 10 nV，
只比较完全相同的原生二进制时间，不插值。两例共 22 个配对点，最大电压差为 0，包含零时刻及各边沿。
Spectre 的全部 100 行原生电压及 EVAS 全部保存值另按独立答案检查。
与双精度公式的差均为 0；相对精确有理公式，参考记录最大舍入差约为 `2.78e-17 V`，
EVAS 保存记录的差为 0。这些指标均满足预定门槛。
两后端请求 reltol=1e-7、vabstol=1e-9，Spectre 读回相同；EVAS 明确忽略 iabstol，
仅从 EVAS 输入移除输出精度格式字段，物理源、参数、模型和初值不变。

[开发回归](../../../../evas/tests/test_scs_pulse_delay.py)经公共 SCS 入口和默认 Rust 内核运行，
另检查默认值与显式零的请求等价、不同观察控制、其余缺参和非法显式 delay、边沿/点数/分辨率拒绝。
第二次 pulse 位于 1e9 s 的控制还检查舍入证明和下游三倍增益的误差预算拒绝。
既有显式正 delay、DC、PWL 和 source uncertainty 回归保留。没有修改内核、IR 或连续/事件历史机制。

[原 22 请求](originals.json)保持原模型、刺激、精度及预算，全部移除缺 delay 的首阻塞，
18 项仍由源不确定性组合检查拒绝，另 4 项编译或语法拒绝，旧 checker 均未运行。
22 个 worker 均返回 0 且未超时，但进程组 TERM/KILL 收据均因 PermissionError 标为
`cleanup_incomplete`，不能声称清理已获证明。后续进程快照未见本任务 worker 或内核，
该快照不替代原失败收据。本轮也对同一执行器的 ANSI 回放补记此限制。
这不等于整题完成，不是正式 benchmark 或新增 Q 成绩，也没有重跑 400 家族或完整后端矩阵。
数值家族 030 属于这份原始集合，与 F30 的 R01 MUX 恢复任务不同；本次不接管后者。

原始 PSF、完整 EVAS 响应、帮助输出、参考解析器校准来源和进程清理收据保留在本地
`runs/evas-pulse-delay-20261017/`。仓库保存固定输入、选定原生点和紧凑身份，完整原始数据未公开。
