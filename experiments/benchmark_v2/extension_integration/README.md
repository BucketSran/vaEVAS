# 扩展与集成 #135

必须完成来源349和case0007，两题已建立Harbor材料、参考、其他合法实现及语义mutants。当前没有实际Spectre或模型试做结果，不能报告任务完成或发布资格。

349复用#133健康单通道024四实例，检验同时采样、顺序读出与保持；case0007由出题方提供健康粗调、实际DCO反馈和有效fine执行器，候选完成TDC、控制与模式集成。行为输出统一由 `benchmark/checkers/v2_integration.py` 独立评分，不以内部lock替代真实输出边沿。

`manifest.json` 保存来源mapping及实际校准请求。`candidates/` 保存不同合法实现与可编译语义mutants；这些是待运行候选，存在并不证明checker能拒绝它们。

本地checker seam测试：`python3 -B -m unittest discover -s experiments/benchmark_v2/extension_integration -p test_checker.py -v`。其合成波形只验证checker合同，不能代替VA或Spectre运行。远端资源由root调度，总Spectre并发不超过4。
