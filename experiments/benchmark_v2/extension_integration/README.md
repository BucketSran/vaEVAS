# 扩展与集成 #135

当前作者校准为20/20个登记变体有效，见[作者校准最终报告](../author-calibration-final.md)。模型 Agentic 与适用 one-shot 试做及完整 spec 验收尚未完成。计划和生成清单中的 pending 保留生成时状态，当前作者结论以该报告为准。

必须完成来源349和case0007，两题已建立Harbor材料、参考、其他合法实现及语义mutants。旧包已有实际Spectre运行，严格审查发现reset、分频关系和lock资格覆盖缺口；修订包的作者校准现已完成，模型试做和完整发布资格尚未完成。

349复用#133健康单通道024四实例，检验同时采样、顺序读出与保持；case0007由出题方提供健康粗调、实际DCO反馈和有效fine执行器，候选完成TDC、控制与模式集成。行为输出统一由 `benchmark/checkers/v2_integration.py` 独立评分，不以内部lock替代真实输出边沿。

`manifest.json` 保存来源mapping及实际校准请求。`candidates/` 保存不同合法实现与可编译语义mutants；这些候选已纳入当前作者校准；单凭文件存在仍不证明checker能拒绝它们。

本地checker seam测试：`python3 -B -m unittest discover -s experiments/benchmark_v2/extension_integration -p test_checker.py -v`。其合成波形只验证checker合同，不能代替VA或Spectre运行。远端资源由root调度，总Spectre并发不超过4。

修订checker另验证实际fb频率与每N个DCO边沿关系，并以独立配对重算20次lock资格、缺边沿与无新配对撤销。15项本地seam tests通过；这不替代修订包reference、alternative和全部语义mutants的实际运行。

缺钟case在52us至54us验证lock撤销，稳定窗口移至恢复后的57us至59us，原200kHz频率和3ns相位阈值保持不变；该恢复窗还必须出现独立重算的正lock资格。公开lock更新期限为2ns，观测增加50ps数值裕量。本地合成轨迹覆盖2ns合法更新、3ns超期更新与缺钟后的重新取得资格。

公开诊断入口 `environment/public/public-default.scs` 已作为固定附件保存。它只使用原有公开材料；Spectre 实际执行返回 0，身份见 [public-diagnostic-calibration.json](public-diagnostic-calibration.json)。该结果验证默认诊断可运行，不提供隐藏指标或模型得分。新增成对模型试做应从含此附件的版本同时冻结。

ADPLL 也已保存固定 `public-default.scs`。诊断运行保留60us、1ns最大步长，以1ns strobe记录9个实际接口信号；完整10.7MB报告通过新版harness，Agent取得摘要及分页入口。身份见 [adpll-public-diagnostic-calibration.json](adpll-public-diagnostic-calibration.json)，这不是隐藏checker或模型成绩。

349 的 `sample-hold-causal-v2` 在原两个健康条件之外增加两档公开增益诊断，验四通道读出是否实际使用保持部件；新增在线整体重写和活跃旁路负例。独立在线轨迹能检出两档旁路，VA reference、alternative及新增负例的实际 Spectre 作者校准已完成。旧版模型试做保留原题面与材料身份，新版须成对重新冻结。
