# 1800ns参数化时钟的标准整理版

`clock1800_standard.va`来自恢复的tangxy `CLOCK_VA_SAMPLE_1800n`，原始路径及哈希见[sources.json](sources.json)。按已确认Q14，仅将输出discipline改为electrical，并将initial_step中的电压贡献替换为六个状态的显式零初始化，包含CONV。所有timer和transition表达式、时序参数及genvar循环保留。差异见[standard-normalization.patch](standard-normalization.patch)。这不表示原始voltage discipline或事件体内贡献已获支持。

ngspice、Spectre和Rust适用路径均执行同一整理文件。默认32个timer调用点，1800ns周期、1.1V电平、20ps边沿；0至3700ns独立日历共75次发生。42路变体将五组NUM设为4、周期设为2400ns，运行至4900ns。另验空循环、单次循环展开、不同参数的两实例。

其余文件是独立微例或控制，不替代完整整理版验收。`zero_start.va`用私有整数计数观察零timer是否重复消费；二进制周期夹具与反序版检查独立同刻全部执行；near夹具用显式5fs容差区分0.5ps邻居。

验收、原预算与工具边界见[P1合同](../../../validation/xspice/README.md#p1-parameterized-clock)，本地收据见[P1证据](../../../../experiments/backends/xspice-entry/p1-evidence.json)。
