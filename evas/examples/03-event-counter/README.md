# 第 3 课：事件系统

**命令**（仓库根目录）：

```sh
PYTHONPATH=evas/src python3 -m evas transient evas/examples/03-event-counter/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

## 电路

```
 input(三角波 0.4 ↔ 0.6 V)      output(阶梯波)
       /\      /\                 ▲
      /  \    /  \ ...            │  上穿 +0.1V，下穿 +0.01V
   [cross_counter]                │  out = 0.1×rising + 0.01×falling
      vin 从下方穿过 0.5V(+1) → rising+1
      vin 从上方穿过 0.5V(−1) → falling+1
```

## 和第 2 课的新增概念

| 新写法 | 含义 |
| --- | --- |
| `@(cross(expr, dir, ttol, tol))` | expr 穿过零且方向匹配 dir 时触发；ttol 是时间容差（秒），tol 是表达式容差（本例为伏特） |
| 事件体 `rising=rising+1` | 触发瞬间执行的赋值——这是**状态**，不是连续方程 |
| `@(initial_step)` | 仿真开始时初始化状态 |
| 整数状态 + 贡献混用 | 事件改状态，`V(count,vref) <+ ...` 把状态映射为输出电压 |

## 期望输出

输入三角波在 0.5 V 上下摆动，每次穿越阈值触发一个事件。五个观察点
（µs → V）：

```
0 → 0.00    0.75 → 0.10    1.75 → 0.11    2.75 → 0.21    3 → 0.21
```

0.75 µs 时输入已上穿 0.5 V 一次（rising=1 → 0.1 V）；1.75 µs 时又
下穿一次（falling=1 → 0.1+0.01=0.11 V）；如此阶梯上升。
本例的解析穿越时刻为 0.5 µs、1.5 µs、2.5 µs。EVAS 按事件容差
认证根的位置，并重解代表时刻的工作点；观察点读到结算后的状态。
输出采样网格不决定触发时刻，这也不表示一般根都能用浮点数精确表示。
