# EVAS 示例

每课一个目录、一个概念台阶：**静态求解 → 瞬态与历史 → 事件 → 事件与历史组合**。
所有示例自包含（`.va` 模型 + `sim.json` 装配清单），从仓库根目录
先构建内核，然后复制粘贴一行命令即可运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/01-static-gain/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

| 课 | 学什么 | 入口 |
| --- | --- | --- |
| 01 | 静态求解；`.va` 模型与 `sim.json` 清单的字段对应 | [01-static-gain/](01-static-gain/README.md) |
| 02 | 瞬态仿真；`idt` 对斜坡积分，得到抛物线输出 | [02-integrator/](02-integrator/README.md) |
| 03 | 事件系统；`cross` 过阈检测驱动计数器（阶梯波） | [03-event-counter/](03-event-counter/README.md) |
| 04 | 定向 `cross` 改变 `idt` 方向；同一模型在 EVAS 和 Spectre 中运行（当前分支候选） | [04-triangle-oscillator/](04-triangle-oscillator/README.md) |

前三课说明 EVAS 的两个输入文件如何分工：
`.va` 描述**元件行为**（模型），`sim.json` 描述**怎么用它做实验**
（实例化、连线、激励、观察）。更复杂的能力组合与边界见
[validation/smoke/](../validation/smoke/README.md)（最小冒烟集）与
[技术手册](../docs/README.md)。
