# 来源与冻结范围

采样非均匀阈值flash ADC模型由本次公开电路合同独立编写，没有复制来源许可不明的历史VA。
SOURCE不把旧power基线计时错误称作优化；已修合法基线重新实际校准后才准入。
本题属于Spectre扩展集，未声称开源后端可重评分。完整校准范围与失败记录保存在
experiments/benchmark_first_batch/optimization，五对准入证据SHA256为
`504d89e1aa58ad4cc2878bc45079b0ec69428a35dd97d22ae8f1c3f1aba67283`。该哈希绑定归档、源码、判据和实际计时；
题数/Agentic/负例正式校准状态由首批inventory维护，不由目录存在推导完成。
公开评分指标为intrinsic tran CPU。参考准入的实际进程收益是另列的工程证据，不是每个满分
候选的硬门槛；不能将指定指标满分解释为所有实现的端到端收益。Flash旧二分版本
保留CPU收益与进程回退记录，若满足公开CPU及功能规则就是合法替代，不是负例。

执行profile采用现有256MiB收集硬上限及900s。paired完整PSF在求解计时及
功能判读后gzip无损压缩，核验解压SHA/字节长度相等才移除重复原文件；保留双身份
及版本/路径/压缩时间。主功能PSF仍原格式。所有点/日志保留，不截断波形。

<!-- generated first-batch metadata -->
- `engineering_action`: `simulation-implementation-optimization`
- `source_group`: `original-flash-thresholds-optimization`
- `context_level`: `bounded-work-unit`
- `provenance`: `original-engineering-requirement`
- `data_provenance`: `behavioral_synthetic`
<!-- end generated first-batch metadata -->
