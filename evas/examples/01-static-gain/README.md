# 第 1 课：静态求解

**命令**（仓库根目录）：

```sh
PYTHONPATH=evas/src python3 -m evas solve evas/examples/01-static-gain/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

## 电路

```
 u ──[×g1=1.5]────┐
                  │
 v ──[×g2=-0.5]───┼──(+ bias=0.125V)──► out
                  │
 ref ─────────────┴── 0 (地)
```

三条电压贡献相加：`V(out,ref) = 1.5·V(u,ref) − 0.5·V(v,ref) + 0.125`。
本例两个增益之和为 1，因此对地输出为 `V(out) = 1.5·V(u) − 0.5·V(v) + 0.125`。

## `.va` 与 `sim.json` 的对应

`.va` 定义元件行为（端口、参数、方程）；`sim.json` 声明怎么用它做实验。
两边的名字靠下表的粗体字段对上：

| sim.json 字段 | 含义 | 对应 .va 的什么 |
| --- | --- | --- |
| `"models": ["dut.va"]` | 加载哪个模型文件 | 整个 module 定义 |
| `"module": "dvs_sum"` | 实例化哪个模块 | `module dvs_sum(u, v, vout, vref)` |
| `"connections"` | 模块端口 → 全局节点 | 模块的端口列表 |
| `"parameters"` | 覆盖默认参数 | `parameter real g1 = 1.5` 等（本例用默认值） |
| `"driven": ["u","v","ref"]` | 哪些节点由外部给定电压 | ——（实验台的事，模型不管） |
| `"samples"` | 每组一个静态工作点：u、v、ref 的值 | —— |

`"connections": {"u": "u", "v": "v", "vout": "out", "vref": "ref"}`
把模型端口接到电路节点——相当于在原理图上放一个元件并连线。

## 期望输出

三个样本 `[u, v, ref]` = `[0, -0.2, 0]`、`[1.4, 0.8, 1.0]`、`[-0.2, 0.3, 0]`。
手算第一组：`1.5×0 − 0.5×(−0.2) + 0.125 = 0.225 V`。

`solutions[].voltages` 按 `nodes` 顺序排列，三组的 `out` 应约为
**0.225 V、1.825 V、−0.325 V**（可自己代入验证另外两组）。

## 可选 `.scs` 入口

同一个模型也可用 [tb.scs](tb.scs) 指定三角波输入并运行瞬态：

```sh
PYTHONPATH=evas/src python3 -m evas simulate evas/examples/01-static-gain/tb.scs --kernel evas/rust_core/target/debug/evas-kernel
```

预期关系为 `out = 2*u - 0.125 V`。结果中的 `saved` 是 save 选择的输出列。
输入范围和不同于 Spectre 的设置约定见[测试台说明](../../README.md#spectre-风格电压测试台)。
