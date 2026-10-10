# spec #134 真实采样级数据建模

本目录已建立来自JKU SKY130晶体管采样级的真实数据、完整实验划分、Harbor任务和独立评分程序。来源真实性、初始化和误差预算见[任务来源](../../../benchmark/tasks/v2-data-sampling-identification/SOURCE.md)。当前任务候选尚待实际Spectre校准，模型试做也待协调执行，不能据离线拟合宣布spec关闭。

[category-manifest.json](category-manifest.json)将本类唯一必做来源映射至任务。该采样级不是32个P1来源的新增计数。固定32条训练、2条公开自测与4条隐藏实验的身份在[dataset-manifest.json](dataset-manifest.json)，公开与隐藏不共享完整序列。

重生成源数据需Python 3.10+和ngspice 47。先取得固定PDK revision，生成器遇到不同revision会拒绝。使用自己的临时输出路径运行：

```sh
python3 experiments/benchmark_v2/data_modeling/generate_source.py --pdk /path/to/skywater-pdk-libs-sky130_fd_pr --ngspice /path/to/ngspice --work runs/v2-data-source
python3 experiments/benchmark_v2/data_modeling/check_source.py
python3 experiments/benchmark_v2/data_modeling/audit_export.py
```

生成器只使用真实MOS模型，不调用VA参考。32条公开训练覆盖输入/状态组合，包含20条从上下两种历史出发的固定目标6 ns轨迹。`fit_table.py`需要NumPy和SciPy（当前拟合为2.5.3/1.18.1）。它只从32条公开训练读出静态导数，拟合两种通道导通函数和有界正修正；分别形成29和15节点修正表。反相器上升/下降时间常数与修正平滑度按32条训练的最坏采集RMS选择，2条公开自测只用于验证，脚本不读取隐藏CSV。[switch-fit.json](switch-fit.json)保存拟合系数和训练字节身份，[public-fit-study.json](public-fit-study.json)保存8组公开选参结果。自由运行自测是离线模型研究，不是候选VA实际运行证据。

```sh
python3 experiments/benchmark_v2/data_modeling/fit_table.py
python3 experiments/benchmark_v2/data_modeling/build_candidates.py
python3 experiments/benchmark_v2/data_modeling/build_task.py
python3 -B experiments/benchmark_v2/data_modeling/test_checker.py
```

`calibration-request.json`包含repo相对候选路径与预期语义。主协调者冻结候选、checker、激励与后端身份后执行Spectre。所有负例都应编译并运行，然后根据波形判错；编译或环境缺陷不能作为负例被有效拒绝。runtime与parser副本由主协调者统一同步。

开发中先试的低阶多项式在公开新中间电平轨迹出现较大误差，高阶拟合还出现速率外推不稳，未用于发布参考。为此补公开完整阶跃轨迹，改用正值速率表。[旧参考实际校准](isolated-r2-diagnosis.json)随后4/6通过，未过两条的采集RMS约35–36 mV。公开开通波形表明，单一导通沿不能表示直接PMOS与反相器驱动NMOS的差异。因此当前候选拆开两种导通函数和反相器状态，并从已冻结公开训练拟合正修正表；没有修改源数据或阈值，也不从隐藏输出拟合参数。候选稳定后再固定包，任何后续修改须重新冻结和校准。

后续扩充需要新增且可辨识的工程目标。长保持泄漏、沿附近pedestal/feedthrough和主动查询均未进入本题独立目标。当前短保持指标测量保留状态；已有数据不能证明这些后续效应可稳定评分。
