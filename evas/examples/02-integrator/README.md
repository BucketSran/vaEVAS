# 第 2 课：瞬态仿真与积分历史

**命令**（仓库根目录，注意入口换成 `transient`）：

```sh
PYTHONPATH=evas/src python3 -m evas transient evas/examples/02-integrator/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

## 电路

```
 input(斜坡: +0.2 → −0.2)              output(抛物线)
  ────────┐                              ▲
          │  V(out,0) = ∫ V(in,0)/1µs dt + 0.25V(初值)
          ▼
       [积分器 idt]
```

输入从 +0.2 V 线性降到 −0.2 V（4 µs）。积分器输出先上升、到达顶点后
随输入变负而下降——**输出是输入的累积，这就是"历史"**。

## 和第 1 课的新增概念

| 新字段/写法 | 含义 |
| --- | --- |
| `transient` 块 | 瞬态实验：有时间推进，区别于静态 `solve` |
| `"sources"` | PWL 激励源：节点 `input` 的分段线性波形 `[[t0,v0],[t1,v1],...]` |
| `"output_times"` | 在哪些时刻观察输出 |
| `"stop"` / `"max_step"` | 仿真结束时间 / 最大步长 |
| `.va` 中 `idt(expr, ic)` | 积分算子：对 expr 从起始积分，初值 ic（本例 0.25 V） |

## 期望输出

输入直线 `v(t) = 0.2 − 0.1t(µs)`，积分（归一化 1 µs）得抛物线，
加初值 0.25。五个观察点（µs → V）：

```
0 → 0.25    1 → 0.40    2 → 0.45    3 → 0.40    4 → 0.25
```

输出沿抛物线上升，到中间的峰 0.45 V 后回落。
