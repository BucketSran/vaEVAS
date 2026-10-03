# ngspice 电压关系对照

本工具对照一个明确的共同子集：静态仿射/整数多项式电压关系，以及由连续 PWL
驱动的仿射网络。它另用独立行为源检查固定周期计数器在事件之间的值。
运行前安装 `ngspice`，并按 [EVAS 构建说明](../../README.md#构建与运行)生成内核。

从仓库根目录运行：

```sh
python3 -B -m unittest discover -s evas/validation/differential -v
PYTHONPATH=evas/src python3 -B evas/validation/differential/ngspice_compare.py \
  --kernel evas/rust_core/target/debug/evas-kernel \
  --out runs/ngspice-differential-01
```

输出目录必须是新目录。工具保存 VA、IR、网表、波形、日志、版本、文件摘要和报告。
执行失败返回非零；缺少波形不能当作通过。数值差异超过预算也返回非零。
CI 使用相同命令，归档每次执行结果。

## 固定范围与独立答案

- 生成 1、4、16、64 个未知节点的严格对角占优网络，每个网络执行三个静态输入和七个瞬态观察。
  系数为二进制精确分数。预设解是 `y_i = root_i + u`，随后反向构造方程；
  EVAS 和 ngspice 都必须符合此解。固定随机种子写在脚本内。
- 遍历全部 smoke manifest。只翻译无状态、无事件、无算子，且每个未知节点由一个支路定义的模型。
  不支持的模型在报告中逐个列出，不从 smoke 总数中删除。
- 独立计数参考为 `floor(t/0.25)`。五个观察点避开跳变，因此只验证事件之间的计数值，
  **不验证事件定位精度、同刻读写或通用 timer 语义**。
- 同一支路的贡献先相加。独立理想源并联、浮动支路图和通用状态程序不在翻译范围。
  整数幂展开为乘法，避免 ngspice 幂函数对负底数的不同处理。

比较预算是 `1e-12 + 1e-10*max(|EVAS|, |reference|)` V，与 EVAS 默认电压容差一致。
ngspice 请求 `vntol=1e-12, reltol=1e-10, abstol=1e-14`，瞬态最大步长为 .005 s。
ngspice 的电流容差只控制其自身求解，不视作 EVAS 的对应设置。
PWL 段内输出是仿射函数，所以对 ngspice 输出作线性插值；计数器只在常值区间插值。
这个理由不能推广到非线性瞬态或事件边沿。

IR 翻译共享 EVAS 前端，不能单独证明前端正确。预设解析解和另写的计数参考提供额外独立检查。
这是开发对照，不是完整语言一致性认证，也不修改原 31 条件矩阵或其历史成绩。
首轮执行见[实验记录](../../../experiments/backends/ngspice-differential/README.md)。
