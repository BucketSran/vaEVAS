# EVAS 到 ngspice/XSPICE 的编译入口

2026-10-19 的本地扩展固定使用 EVAS `c8dc2a7b`、IR28，推进六份 benchmarkv4-r53 样本及实际时钟采样链路。当前收据见 [r53-evidence.json](r53-evidence.json)，可复跑入口见[有限接入合同](../../../evas/validation/xspice/README.md#r53-bounded-pilot)。新电路已建立本地 ngspice 检查；115与068修复后，固定七例同源 Spectre 对照7/7通过；同源VA、物理网表和原判据保持，原RC超差、收敛失败及数值重试均保留。未提交、发布或合并。P0随后复用已有输入别名完成动态阈值、事件采样、下游RC和原近零边界六例验收6/6，另记于[P0收据](p0-evidence.json)；原VA和判据不变，校准与审阅修复记录保留。P1继而完成已确认1800ns标准整理版、零起点最终种子及独立批次的15例同源验收15/15；32/42路、参数变体、两实例及1000周期分别过验，原始失败、重试和检查器修复保留，见[P1收据](p1-evidence.json)。原始原件及动态共享状态不据此取得资格。以下为原入口阶段的历史记录。

本地候选从已审 `main@35876041` 接入独立 XSPICE 后端。公开入口为 `evas-rebuild xspice compile/build`；接口、工具链与模型边界见 [使用说明](../../../evas/docs/reference/xspice.md)。ngspice 解实际电路，EVAS Rust 求解入口保持原职责。

可移植验收源码在 [evas/validation/xspice](../../../evas/validation/xspice/README.md)，开发单测在 [test_xspice.py](../../../evas/tests/test_xspice.py)。五类有序组合和三种回退沿用前阶段冻结合同与实际 Spectre 输入；前阶段原始记录不修改。

本轮源码、CLI、构建、SDK 与精度的紧凑收据见 [evidence.json](evidence.json)。原始大体积数据保留在本任务本地 `runs/xspice-entry-20261018/`。本地绝对路径及哈希不代表已公开复现包；此候选尚未提交、发布或合入 main。

范围限固定日程、标量电压接口和事件保持的线性 transition。后端使用 host 的候选/已接受历史，不继承 EVAS Rust 的区间认证保证。默认模式不允许回退故障注入。Linux原生SDK及其他版本的ngspice尚未由本轮验收。
