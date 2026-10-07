# SAR 首轮实际校准与修复

协调者的 `verify-sar-reference-v3` 在 Spectre 上完成6个条件，执行均成功，归档均 verified。latency4、latency5和三种故障条件通过；latency6为错误拒绝，独立原始波形显示正确器件。

`fault0-lat6` 的 done 边沿为100.05、300.05、700.05、900.05、1100.05ns，码值与中止均正确。verdict却在905ns从0变1。这是参考监测器在第5次轮询检测done时，把由835ns+70ns算出的deadline与905ns直接比较。实际timer时间与重复浮点加法在边界可能有微小差别，因此产生超时误判。

修复仅给参考监测器的期限比较加1ps数值保护。公开35..75ns允许窗口、独立checker的边沿数量、1.1ns定位容差、0.1V码值容差以及故障定义全部保持原合同。1ps保护远小于既定0.1ns输出过渡，不改变5ns轮询的采样结果与真正的迟发故障。基于六份实际原始输入做本地数值重放，修订逻辑接受三个正确条件并拒绝三种故障，但重放不是修订VA的实际仿真，仍需重跑。

[紧凑身份与观测记录](sar_first_calibration.json)保存6份归档SHA256、实际候选身份、原判分与重放结果。原始大波形和日志保留于协调者的 ignored run `runs/benchmark-first-batch-20261008/calibration/verify-sar-reference-v3/`，不提交。
