# 输入限幅与 VCO 的有限观测对照

CO-VCO-01 检查输入仿射频率限幅后，`idtmod` 是否积分限幅后的分段面积，
以及 `sin(2πphase)` 是否使用同一历史。[精简证据](evidence.json)记录实际
Spectre 与冻结修复内核的同刻开发对齐，同时保留未完成的边界查询和观察资格。

原始卡与独立答案固定于已发布的
[core-v1](https://github.com/BucketSran/vaEVAS/blob/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper/core-v1.json) 和
[A oracle](https://github.com/BucketSran/vaEVAS/blob/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper/oracle.py)。
[原源 fixture](../../../evas/tests/fixtures/input_clamp_vco.va)与实际商业后端源逐字节一致；
刺激、参数、初相位、预算和分母没有为结果调整。这是已用于开发的条件，不能称为未见确认数据。

| 有限同刻比较 | 频率最大差 V | 圆周相位最大差 cycle | 正弦最大差 V |
| --- | ---: | ---: | ---: |
| Spectre 与 EVAS，40,836 行 | 6.661e-16 | 1.010007e-8 | 6.346029e-8 |
| Spectre 与独立答案 | 9.437e-16 | 1.010007e-8 | 6.346029e-8 |
| EVAS 与独立答案 | 4.441e-16 | 1.332268e-15 | 8.520962e-15 |

固定预算分别为1mV、0.001cycle、3mV。以上配对行没有预算超限；两边各观察4次包裹，
实际左右记录括定区间都在原±100ps窗口内。没有最近邻配对、跨包裹插值或相位重建。
查询发生在 Spectre 实际时间；EVAS 的闭式历史查询不能冒充内核 accepted-step 日志。

另一个包含4行包裹中心的 EVAS batch 在首次 `waveform_accuracy` 错误处退出，
phase 普通电压误差界跨0/1而约为1。四行均未配对，当时各点独立执行结果未知；
该 batch 不能证明每个中心分别失败。后续逐点结果见下节，原失败记录保留。精简证据保留中心 Spectre原值、
实际时间、scalar/circular误差与完整错误。此边界没有通过放宽内核容差或强改phase为0解决。

Spectre末 token `7.999999999998141e-06` 早于 deck stop token
`7.9999999999999996e-06`，精确 Decimal缺口为`1.8586e-18 s`。
正式导出舍入和输入误差资格仍不足；去除中心后的EVAS左右间隔约40ps，也不满足正式局部20ps网格。
因此 paper 状态保持 **I**。开发数值差值和有前提的误差上界不等于正式资格、全连续轨迹证明或整个clamp能力支持。

EVAS是 reviewed base `4368a890` 加未提交修复，默认内核版本`0.13.0 / IR17`，
构建修订字段为null；JSON保留二进制SHA、完整Python/Rust source closure和修复文件SHA。
Spectre是`21.1.0.509.isr12 64bit`。两边请求`maxstep=200ps`、`reltol=1e-5`、
`vabstol=1e-7 V`；Spectre实际conservative瞬态`reltol=1e-6`、`traponly`。
两次本地EVAS查询各限90秒，未启动新增远端作业。Spectre日志40,839 accepted steps加初行与
40,840原PSF行一致；全部原PSF字段和转换后的observation已核验，实际保存来源的安装合同及其界限另有固定身份。

本目录只保留摘要与身份，不复制大波形、审查日志或另建checker。完整归档、请求、输出、
失败和一次性分析脚本是 **local-only**，JSON逐件给出路径及SHA；原商业后端归档SHA为
`913a17abb151e881c0f7e068c1759f0d29c2d73174415480247dbe5498e15910`。
哈希不是公共下载地址。取得这些原材料、固定源码closure及工具后，才能复查原始分析；
仅靠本摘要不能宣称公开原始数据复现。实现、审查和集成状态由根任务/PR维护。


## CI 写法修正后的复验

`6d328f31` 的全量 Rust/Python CI 通过后，clippy 要求将单分支 `match` 改为
等价 `if let`。同时重新生成诊断源码清单，补入原限幅实现的19个源码记录；
这些记录不代表实际错误覆盖。没有改变方程、容差、分支顺序或输入。

重建内核的 SHA 已改变。使用原 ordinary/boundary 两份请求重新执行后，两份 stdout、
stderr 都与原始实际对照逐字节相同。普通点仍成功，中心 batch 仍以原错误退出。
[增量身份](lint-followup.json)分别保留旧内核、新内核和请求 SHA；原证据不覆盖。
此复验复用原 Spectre 参考，没有新增远端仿真。clippy、fmt、5项相关 Rust 和
8项公开入口测试通过；新提交的完整 CI 状态由 PR 记录。

## 回绕中心的逐点诊断与容差含义

[逐点补充](boundary-diagnostics.json)以 `d7034820` 的原生产代码重建内核，
复用同一批 Spectre 实际记录，在四个中心和各自的实际左右邻点分别查询。
本次共48次本地内核调用，没有新增 Spectre 运行。

| EVAS 设置：absolute / relative | 原模型中心拒绝 | 原模型左右邻点完成 | 常零 phase 输出诊断模型中心完成 |
| --- | ---: | ---: | ---: |
| 原配置：1e-7 / 1e-5 | 4/4 | 8/8 | 4/4 |
| 收紧：1e-8 / 1e-6 | 4/4 | 8/8 | 4/4 |
| 仅诊断的放宽：1e-6 / 1e-4 | 4/4 | 8/8 | 4/4 |

以上是调用结果计数，不是新增题目或正式达标数。所有原模型中心仍因普通 phase 的
前向误差界跨0/1而拒绝；不能靠这三档容差消除边界歧义。成功查询的各节点名义值在三档间相同。
诊断模型只把普通 `V(phase)` 贡献改为常零，保留原频率、`idtmod` 与正弦链，
用于区分相位节点认证和周期输出路径；它是不同源码，不能作为原模型通过证据。
原源码、刺激、时间、预算、失败和分母保留，paper 状态仍为 **I**。

独立精确分数计算还区分了“请求的中心”与数学边界：按原始 binary64 PWL 和编译后
binary64 IR 的精确实数解释，四个中心相对最近整圈的侧别为 **正、正、负、正**，
距离约为 `2.75e-16`、`1.90e-16`、`-4.91e-16`、`2.52e-16 cycle`。
第三点在该参考下应接近1，不能把所有中心强置为0。此计算不是十进制工程源的精确答案，
也不是源到 IR 等价证明或 Spectre 内部算法说明；前端倒数折叠等算术还须单独检查。

实际 Spectre 日志121–141行记录 `errpreset=conservative`、`reltol=1e-6`、
`vabstol=1e-7 V`、`lteratio=10`、`relref=alllocal`、`maxstep=200ps`、`method=traponly`；
deck 显式覆盖积分方法，不能仅从预设名推断方法。其相对误差参考可采用该节点历史最大幅值，
而 EVAS 当前瞬态包围检查使用本次返回值幅值。两者约束对象也不同，见
[容差解释](../../../evas/docs/math/solving.md#spectre-与-evas-的容差含义)。
本地三档诊断没有建立 Spectre 的容差收敛结论；新的 Spectre 扫描须另行冻结具体设置，
并保持外部物理验收预算不变。

修复方向是保留原输入来源，在普通包围跨整圈时按需证明积分落在哪一侧，同时认证名义返回值。
只精确积分已舍入的派生 PWL，不能消除它与原输入之间的误差带。
这需要新的数值证书，按 [Spec A Q7](https://github.com/BucketSran/vaEVAS/issues/96)
先讨论具体设计；本次补充没有实现新方法，也没有扩大支持范围。
