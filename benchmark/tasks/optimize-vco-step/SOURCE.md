# 来源与冻结范围

连续相位PLL正弦VCO模型由本次公开电路合同独立编写，没有复制来源许可不明的历史VA。
SOURCE不把旧power基线计时错误称作优化；已修合法基线重新实际校准后才准入。
本题属于Spectre扩展集，未声称开源后端可重评分。完整校准范围与失败记录保存在
experiments/benchmark_first_batch/optimization，五对准入证据SHA256为
`3a62c085546b0ec2a2c9421cdbf060c90f145be50d1ded4b0ca69323fc92c393`。该哈希绑定归档、源码、判据和实际计时；
题数/Agentic/负例正式校准状态由首批inventory维护，不由目录存在推导完成。

性能专用执行profile须保留完整原始PSF，建议至少1GiB收集上限及900s，
不能使用原功能profile256MiB上限，也不删波形片段绕开资源限制。

<!-- generated first-batch metadata -->
- `engineering_action`: `simulation-implementation-optimization`
- `source_group`: `original-vco-boundstep-optimization`
- `context_level`: `bounded-work-unit`
- `provenance`: `original-engineering-requirement`
- `data_provenance`: `behavioral_synthetic`
<!-- end generated first-batch metadata -->
