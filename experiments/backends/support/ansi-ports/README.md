# ANSI 端口声明的有限对照

EVAS 接受每个端口显式方向的 ANSI 头部，复用已有端口顺序、范围求值与实例绑定。方向后可带已声明的 electrical 和一维范围；只写方向的端口仍须由正文补 discipline。原 non-ANSI 路径保留。合同及实现入口见[编译准入](../../../../evas/docs/reference/frontend-admission.md#ansi-端口声明)。

[固定输入](inputs.json)包含同一标量、向量物理模型的 ANSI/non-ANSI 等价形式、方向声明控制，以及重复 discipline 和共享名字列表两个拒绝控制。Spectre 21.1.0.509.isr12 实际执行七次，五个正例完成，两项负例拒绝。共享名字列表有 LRM 语法依据，但不属于本次有限支持，不能称为非法 Verilog-A。

[同源有限配对](reference.json)在新 EVAS 头部实现上复验。固定电压门槛为 10 nV，按完全相同的原生二进制时间配对，不插值；五个正例共 25 点，包括零时刻，最大电压差为 0。全部 Spectre 原生电压另按标量 `y=3a+5b`、方向控制 `y=2a` 或向量 `y0=a0+1,y1=2a1` 检查。Spectre 的实际 reltol 为 1e-8，EVAS 为请求的 1e-7；源、参数和其他配置身份均保留。两项拒绝控制也在新 EVAS 上拒绝。

[开发回归](../../../../evas/tests/test_ansi_ports.py)另覆盖按序和按名子实例、相反向量方向、两个实例不同的参数范围、混合显式/正文 discipline、timer 与积分器，以及带源位置的拒绝。范围和数值运行继续交给原绑定层及 Rust 内核；本次没有新 IR 或数值方法。有限对照不证明全部 ANSI、所有参数组合或完整 Verilog-AMS 兼容。

[原 26 请求](originals.json)保留原输入、精度和预算。001、047、089 完成运行并通过冻结旧 checker，另 23 项保留后续语法、初始化、表达式、事件相位、范围或动态组合拒绝。首阻塞移除不等于整题通过，也不把旧 checker 回放计为正式 benchmark 或新增 Q 成绩。没有重跑 400 家族矩阵。

原始 PSF、完整 EVAS 响应、独立答案核对脚本、进程清理收据和详细审查保留在本地 `runs/evas-ansi-ports-20261017/`，两项预期编译失败不重试。仓库只保存固定输入、选定原生点及紧凑身份，不提供公开原始数据集。

原 26 请求的 worker 均返回 0 且未超时，但本地执行器的进程组 TERM/KILL 均遇到
PermissionError，收据标为 `cleanup_incomplete`。该限制补记在原请求摘要中，不更改原结果或
旧 checker 判定；后续进程快照未见这些 worker 或内核，也不能据此把原清理收据改为成功。
