# 源驱动局部事件闭包的实际对照

本轮修复局部事件时间轴无法保留外部输入的限制。近邻 timer 后，原始 PWL
以精确时钟为原点重新表示，输入值、误差和可精确平移的折点一起进入线性或
显式多项式传播。随后 cross 改变流时继续保留所有积分历史；失败仍整批回退。
算法与范围见[事件手册](../../../evas/docs/math/events.md#有界局部因果闭包候选)。

[模型和冻结预算](../../../evas/validation/source-event-closure/README.md)在执行前固定。
两种刺激各运行 base/tight 两档精度，新执行四次 Spectre 仿真，全部产生波形。
工具为 Spectre `21.1.0.509.isr12`；没有把本地公式测试当作参考仿真。
EVAS 使用同一最终内核执行全部原生时间点和冻结请求点；68,384 行 Spectre 原生波形均保留。
[精简收据](evidence.json)记录内核、源码文件、模型、checker、工具和原始波形身份。

| 刺激 / 参考配置 | Spectre 原生行数 | EVAS 对独立答案最大电压误差 | EVAS–Spectre 最大电压差 | 完整直接判据 / 请求时间覆盖 |
| --- | ---: | ---: | ---: | --- |
| 正极性斜坡 / base | 3,139 | 1.11e-16 V | 2.014 µV | F / I |
| 正极性斜坡 / tight | 31,038 | 1.11e-16 V | 0.650 µV | F / I |
| 负极性折线 / base | 3,154 | 1.11e-16 V | 2.344 µV | F / I |
| 负极性折线 / tight | 31,053 | 1.11e-16 V | 0.682 µV | F / I |

模拟电压预算仍为 1 µV。两份 tight 的电压通过这一项，但完整直接比较仍为 F：
Spectre 首个保存的 flag=1 点比独立数学根早约 32 ns，超出预定的 2 ns 事件窗口。
base 的该偏差约 324 ns，模拟电压也超差。这是保存的观测，不是隐藏回调时刻的证明。
两档参考在已有共同请求点的最大电压差分别为 1.364 / 1.662 µV，
因此当前两档还未满足 1 µV 的参考稳定性判据，不能宣布参考精度已合格。
不因此改动 EVAS 数学根处更新的契约，也不将严格判据改成通过。

PSF 导出未精确命中部分请求 binary64 时间，包括 stop=0.31，覆盖保持 I；
没有插值或最近点填补；两份 tight 的原生末行略超 stop，域检查也保留为 F。
原通用设置读回缺少 `requested_settings.json`，四份结果保持 I。
[原生日志摘录](native-settings.json)打印了相应的 reltol、vabstol、iabstol、maxstep 和 traponly，
但这些摘录不补造完整设置资格。请求的 base/tight 参数见冻结 contract。
原 C1、#79、VCO、M1 的模型、预算和 F/I 也未改变。

同一内核还完成了两类复验：

- Spec B 的 12 份冻结请求与已合并重构版本逐字节相同；七份工程请求也逐字节相同，
  继续复用对应 14 份实际 Spectre 原始参考及原 F/I。没有新增论文评价集通过计数。
- 新 `.scs` 入口运行四个既有 strobe 模型，12 个内部强制点全部满足原 1 µV
  实际 Spectre 比较预算。此处复用旧波形，并明确从本地网表移除不支持的
  Spectre-only 选项；不声称两端设置相同。常规输出网格和强制点保持独立。

本轮模型属于开发集。更广源驱动历史 guard、不可精确平移的输入折点、隐式 DAE
与事件组合、局部闭包 strobe、strobeoutput 保存策略仍未完成。
完整 raw、失败尝试、双审和唯一决策 TSV 为 local-only，保留在可见任务工作区
`runs/event-source-closure-20261009/` 和 `runs/alignment-implementation-20261009/decisions.tsv`。
这些校验和不代表原始数据已公开下载。

具备本地原始参考时，用新目录重跑：

```sh
PYTHONPATH=evas/src python3 -B -m unittest discover -s experiments/backends/source-event-closure -v
PYTHONPATH=evas/src python3 -B experiments/backends/source-event-closure/pair.py \
  runs/event-source-closure-20261009/reference/collected/spectre/spectre-output \
  runs/source-closure-new-pairing --kernel evas/rust_core/target/debug/evas-kernel
```

检查器校准包括独立积分已知值、错误连续/离散输出、缺失点、重复点、空证据、NaN/Inf。
逐配置超时保留 I 并继续固定分母；原生日志和源码/内核身份在复验前后核对。
