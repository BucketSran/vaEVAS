# 支持范围专项探针

15 个模型补充 core-v1 未覆盖的语言和算子路径，用于[四后端支持表](../../docs/COMPARISON.md)。
这是开发与支持范围探针，不能当成未见过的独立论文评价集。

[cases-v2.json](cases-v2.json) 固定源码、刺激、参数、时间网格、数学答案和误差目标。
相比保留的 [v1](cases-v1.json)，13 例补齐显式端口方向，其中两个模块补齐 `analog begin/end`；
函数和数组模型不变。数学、刺激与预算未变，原 v1 准入失败继续保留。

[checker.py](checker.py) 只用独立方程/PWL 答案，不导入 EVAS。
要求有限观测完整、有序、有限值，输入误差不超过 0.1 µV、输出误差不超过 1 mV。
检查所有保留的原生点；最大观察间隔不超过预定网格的 1.01 倍。
首尾时间须在停止时刻的 32 ULP 内；不符时记为观察无效，不能仅凭这个状态判定原因。
实际停止时间量化、导出舍入或波形截断需要分别核对。Gnucap 的本轮阻塞是 dtmin 时间量化，
后续调整时间分辨率重新执行，保留原检查器与失败记录，见[补测报告](../../../experiments/backends/support/README.md#gnucap-时间分辨率补测)。

函数阈值、DDT 拐点和数组事件的排除窗在运行前固定，原始边界值单独保留，不计为通过。
数组例的窗为 ±15.625 ms，只检验窗外状态平台，不验证源码规定的 1 ns 事件定位。
其余限制：AD 为直接输入固定延迟；SL 为直接输入固定速率；LP 为一阶零初始输入；
DDT 为分段内部点。所有通过均不构成全时域误差认证。

```sh
python3 -B -m unittest discover -s evas/validation/support -p 'test_*.py'
python3 -B experiments/backends/support/probes.py freeze runs/new-support-inputs
```

校准沿用 v1 的答案；摘要生成器逐字段确认 v2 除源码外的判据、刺激和预算与 v1 相同。
校准包括手算锚点、正确输出、错误输入/输出、缺端点、稀疏网格、重复时刻、NaN，以及未评分边界的保留。
实际执行和已知适配限制见[实验入口](../../../experiments/backends/support/README.md)。
