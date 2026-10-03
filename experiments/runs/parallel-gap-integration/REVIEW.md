# IR15 历史审查导航

本页保留已有锚点。当前支持与证据分别从[能力表](../../../evas/docs/CAPABILITIES.md)和
[实验入口](README.md#当前证据)进入；下列内容均属于原 IR15 检查点。
逐轮推导、失败和兼容分析保存在[固定完整审查](https://github.com/BucketSran/vaEVAS/blob/b4921ca9cfa0b25bc515ffa47c2b397151937d50/experiments/runs/parallel-gap-integration/REVIEW.md)，
更早收据由[无损历史资产](README.md#历史与资产)索引，不删除或改判。

<a id="precision-chain"></a>

## 历史精度链：d451605

点输入根盒及无条件 PWL/采样误差传播的算法见[数值手册](../../../evas/docs/math/solving.md#精度链的已修复反例与边界)。
[执行摘要](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#ir15-precision-chain)、[检查收据](results/precision-chain-checks.json)及
[逐配置矩阵](results/precision-chain-matrix.json)绑定当轮源码、内核、失败与检查。
[原 review](https://github.com/BucketSran/vaEVAS/blob/b4921ca9cfa0b25bc515ffa47c2b397151937d50/experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)保留完整推导和当时未支持的组合。

<a id="gap-completion"></a>

## 历史限定功能补齐：39a4545

[31 行摘要](results/gap-completion-matrix.md)记录原矩阵，
[完整 review](https://github.com/BucketSran/vaEVAS/blob/b4921ca9cfa0b25bc515ffa47c2b397151937d50/experiments/runs/parallel-gap-integration/REVIEW.md#gap-completion)记录普通条件、一阶滤波、相位和无状态非线性整合。
当前基础算子与联合动态分别由[OPERATORS](../../../evas/docs/math/operators.md)和[CONTINUOUS](../../../evas/docs/math/continuous.md)维护。

<a id="accuracy-optimization"></a>

## 历史查询复用与标量认证：ddfd379

[计时收据](results/accuracy-optimization-profile.json)与
[固定方法/范围](https://github.com/BucketSran/vaEVAS/blob/b4921ca9cfa0b25bc515ffa47c2b397151937d50/experiments/runs/parallel-gap-integration/REVIEW.md#accuracy-optimization)记录原测量，
不代表最新版本的端到端或跨后端性能；算法入口见[数值手册](../../../evas/docs/math/solving.md)。
