# 输入限幅与 VCO 的有限观测对照

CO-VCO-01 检查输入仿射频率限幅后，`idtmod` 是否积分限幅后的分段面积，
以及 `sin(2πphase)` 是否使用同一历史。[精简证据](evidence.json)记录实际
Spectre 与最终分支内核的同刻开发对齐，同时保留未完成的边界查询和观察资格。

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
phase 普通电压误差界跨0/1而约为1。四行均未配对，后续各点独立执行结果未知；
不能据此说每个中心分别失败，更不能把它们计为通过。精简证据保留中心 Spectre原值、
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
