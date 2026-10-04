# 来源与验证边界

本题由本仓库的积分历史重定位实验提出，不包含第三方模型源码。
候选身份为 [BC-0001](../../CANDIDATES.md#bc-0001)；这里是已校准的原型，尚未正式纳入 benchmark。
问题来源是双向 cross 的事件体改变自身积分斜率，返回穿越再次触发。
题目评估模型是否稳健表达指定振荡行为，不把某个仿真器的波形当作唯一数学答案。

参考解使用上限向上、下限向下的有向 cross；其他满足规格的写法同样可得分。
检查器从正速度输入的分段积分与三角波折返关系推导答案。
本题单独校准，不加入已完成的六题初筛分母，也不改变 EVAS 原 31 条件矩阵。

评分源码为 [triangle_oscillator.py](../../checkers/triangle_oscillator.py)，
`tests/verify.py` 是逐字节相同的执行副本。配置生成、校准与后端差异证据见
[振荡器兼容性实验](../../../experiments/backends/dvs2-spectre-validation/README.md#oscillator-compatibility)。
任务需要已配置许可证的 Spectre verifier；Docker 基础镜像不包含 Spectre。

在已配置 Spectre 的环境可运行 `tests/test.sh`；用 `CANDIDATE` 和 `VERIFY_OUTPUT`
指定源码与全新输出目录。基础设施错误不产生模型分数。
