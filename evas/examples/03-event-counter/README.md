# 第 3 课：事件系统

**命令**（仓库根目录）：

```sh
PYTHONPATH=evas/src python3 -m evas transient evas/examples/03-event-counter/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

## 电路

```
 input(方波 0.4/0.6 V)          output(阶梯波)
  ────┐    ┌────┐    ┌────        ▲
      └────┘    └────┘ ...        │  上升沿 +0.1V，下降沿 +0.01V
   [cross_counter]                │  out = 0.1×rising + 0.01×falling
      vin 从下方穿过 0.5V(+1) → rising+1
      vin 从上方穿过 0.5V(−1) → falling+1
```

## 和第 2 课的新增概念

| 新写法 | 含义 |
| --- | --- |
| `@(cross(expr, dir, tol, ttol))` | 事件：expr 穿过零且方向匹配 dir 时触发，精确落在穿越时刻（不是下一个网格点） |
| 事件体 `rising=rising+1` | 触发瞬间执行的赋值——这是**状态**，不是连续方程 |
| `@(initial_step)` | 仿真开始时初始化状态 |
| 整数状态 + 贡献混用 | 事件改状态，`V(count,vref) <+ ...` 把状态映射为输出电压 |

## 期望输出

输入方波在 0.5 V 上下摆动，每摆一次触发一个事件。五个观察点
（µs → V）：

```
0 → 0.00    0.75 → 0.10    1.75 → 0.11    2.75 → 0.21    3 → 0.21
```

0.75 µs 时输入已上穿 0.5 V 一次（rising=1 → 0.1 V）；1.75 µs 时又
下穿一次（falling=1 → 0.1+0.01=0.11 V）；如此阶梯上升。
EVAS 把事件定位到精确穿越时刻（0.5 µs、1.5 µs…）并重解该时刻的
工作点，而不是等到下一个网格点——观察点读到的就是结算后的状态。
