# spec #134 真实采样级数据建模

当前作者校准为8/8个登记变体有效，见[作者校准最终报告](../author-calibration-final.md)。模型 Agentic 与适用 one-shot 试做及完整 spec 验收尚未完成。计划和生成清单中的 pending 保留生成时状态，当前作者结论以该报告为准。

本目录已建立来自JKU SKY130晶体管采样级的真实数据、完整实验划分、Harbor任务和独立评分程序。来源真实性、初始化和误差预算见[任务来源](../../../benchmark/tasks/v2-data-sampling-identification/SOURCE.md)。参考、合法替代和六类语义负例已完成实际Spectre作者校准，D3通过。D4模型试做仍在进行，spec #134与发布资格尚未完成。

[category-manifest.json](category-manifest.json)将本类唯一必做来源映射至任务。该采样级不是32个P1来源的新增计数。固定32条训练、2条公开自测与4条隐藏实验的身份在[dataset-manifest.json](dataset-manifest.json)，公开与隐藏不共享完整序列。

重生成源数据需Python 3.10+和ngspice 47。先取得固定PDK revision，生成器遇到不同revision会拒绝。使用自己的临时输出路径运行：

```sh
python3 experiments/benchmark_v2/data_modeling/generate_source.py --pdk /path/to/skywater-pdk-libs-sky130_fd_pr --ngspice /path/to/ngspice --work runs/v2-data-source
python3 experiments/benchmark_v2/data_modeling/check_source.py
python3 experiments/benchmark_v2/data_modeling/audit_export.py
```

生成器只使用真实MOS模型，不调用VA参考。32条公开训练覆盖输入/状态组合，包含20条从上下两种历史出发的固定目标6 ns轨迹。`fit_table.py`需要NumPy和SciPy（当前拟合为2.5.3/1.18.1）。它只从32条公开训练读出静态导数，拟合两种通道导通函数和有界正修正；分别形成29和15节点修正表。反相器上升/下降时间常数与修正平滑度按32条训练的最坏采集RMS选择，2条公开自测只用于验证，脚本不读取隐藏CSV。[switch-fit.json](switch-fit.json)保存拟合系数和训练字节身份，[public-fit-study.json](public-fit-study.json)保存8组公开选参结果。自由运行自测是离线模型研究，不是候选VA实际运行证据。当前`fit_table.py`重算已选中的scale=0.2 V、tau_up=0.09 ns、tau_down=0.08 ns及15/29节点表，不会重新扫描8组选参组合。`public-fit-study.json`保留8组公开研究结果，完整扫描脚本仍在本地研究归档。当前公开入口只重算已选中的模型。

```sh
python3 experiments/benchmark_v2/data_modeling/fit_table.py
python3 experiments/benchmark_v2/data_modeling/build_candidates.py
python3 experiments/benchmark_v2/data_modeling/build_task.py
python3 -B experiments/benchmark_v2/data_modeling/test_checker.py
```

`calibration-request.json`包含repo相对候选路径与预期语义。主协调者冻结候选、checker、激励与后端身份后执行Spectre。所有负例都应编译并运行，然后根据波形判错；编译或环境缺陷不能作为负例被有效拒绝。runtime与parser副本由主协调者统一同步。

## 实际作者校准已完成，模型试做仍在进行

[calibration-report.json](calibration-report.json)保存`isolated-r4`的8个候选、48个条件及版本身份。每个候选都执行2条公开自测与4条留出实验，没有剔除失败条件。参考与替代分别6/6通过，六类语义负例均编译、求解并被至少一个有效波形条件拒绝。采集RMS须不超过25 mV，采样和保持最大误差分别须不超过50 mV，三个指标都满足才算条件通过。

| 候选 | 通过条件 | 失败条件 | 校准结论 |
| --- | ---: | ---: | --- |
| reference | 6/6 | 0/6 | 正例通过 |
| alternative | 6/6 | 0/6 | 合法替代通过 |
| wrong_phase | 0/6 | 6/6 | 错误相位被拒 |
| missing_acquisition | 0/6 | 6/6 | 过快采集被拒 |
| fixed_rc | 0/6 | 6/6 | 固定RC被拒 |
| reset_history | 0/6 | 6/6 | 清零保持历史被拒 |
| ideal_sampling | 0/6 | 6/6 | 理想沿采样被拒 |
| public_replay | 1/6 | 5/6 | 公开记录回放被新序列拒绝 |

`public_replay`通过它回放的公开`selftest-0`，在其余5条序列失败，这个通过也保留在分母中。校准证明这些已测正负条件，不证明任意合法实现通过或任意错误实现被拒。它们是作者开发证据，不是模型主评成绩。

实际候选基于`98391cb74691e5982d37450371ba1d18d60878fb`的公开训练拟合。归档执行版本为Spectre `21.1.0.509.isr12`，每个条件的候选、criteria、package、checker、激励、波形及报告SHA见JSON。源真值由ngspice 47生成，二者身份分开。源数据重生成依赖固定PDK；候选评分读取保存的真值，不需要PDK。

报告还保留全部16个旧候选轮次、96个条件。`full-r1`的48次旧判分均报`sample missing from frozen truth`，不作为有效语义拒绝证据。`isolated-r2`的参考和替代各4/6通过，两条留出采集误差仍超限；该失败没有被r4结果覆盖。[旧参考诊断](isolated-r2-diagnosis.json)保留指标。报告引用的`calibration-audit`是较早固定快照，其中3个负例当时仍pending；当前结论来自全部r4的prepared、results与summary核对，不改写旧快照。

原始归档仅保存在本地ignored `runs/benchmark-spec-20261011/calibration/`，没有公开下载承诺。当前源任务的入口是Harbor固定路径，也不含旧`circuit_task.py`副本。[作者运行器的prepare()](../../benchmark_first_batch/runtime.py)会固定改写`test.sh`为Python 3.12的`-B`入口，并补入协调者的`circuit_task.py`和`adc_linearity.py`。这完整解释了源任务与r4有效包的两处身份差异。

按当前prepare规则只在内存重建后，8组有效模板的完整身份、criteria SHA和全部48个条件的文件SHA及字节数均与r4归档一致。候选和数据身份也一致，因此可在相同规范化作者校准路径下复用r4的D3证据。这个核对不代表源任务全文相同，也不验收Harbor固定路径调用或模型Agent隔离。D4模型试做和完整任务验收仍待完成。

开发中先试的低阶多项式在公开新中间电平轨迹出现较大误差，高阶拟合还出现速率外推不稳，未用于发布参考。为此补公开完整阶跃轨迹，改用正值速率表。[旧参考实际校准](isolated-r2-diagnosis.json)随后4/6通过，未过两条的采集RMS约35–36 mV。公开开通波形表明，单一导通沿不能表示直接PMOS与反相器驱动NMOS的差异。因此当前候选拆开两种导通函数和反相器状态，并从已冻结公开训练拟合正修正表；没有修改源数据或阈值，也不从隐藏输出拟合参数。r4校准采用该冻结候选，任何后续修改须重新冻结和校准。

后续扩充需要新增且可辨识的工程目标。长保持泄漏、沿附近pedestal/feedthrough和主动查询均未进入本题独立目标。当前短保持指标测量保留状态；已有数据不能证明这些后续效应可稳定评分。

公开诊断入口 `environment/public/public-default.scs` 已作为固定附件保存。它只使用原有公开材料；Spectre 实际执行返回 0，身份见 [public-diagnostic-calibration.json](public-diagnostic-calibration.json)。该结果验证默认诊断可运行，不提供隐藏指标或模型得分。新增成对模型试做应从含此附件的版本同时冻结。
