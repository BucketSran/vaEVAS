# 功能补齐候选与确认

本批次检验 EVAS 0.13.0 / IR17 候选的语言、事件和动态组合扩展。
合并基线是 `f1463361` 的 0.12.3 / IR16；这里记录合并前的执行。
合并状态见 [PR61](https://github.com/BucketSran/vaEVAS/pull/61)，未发布 tag。
数学含义和拒绝边界归 [能力表](../../../evas/docs/CAPABILITIES.md)及技术手册；
这里保存执行工具和紧凑收据。原始输出保留在本地忽略的 `runs/capability-completion/`，没有公开下载地址。

## 审查顺序

各改动按依赖顺序提交在 `feat/evas-capability-completion`。
不能只审查最后一条提交，再将整个分支视为已获审查。

| 批次 | 关键提交 | 先检查什么 |
| --- | --- | --- |
| 事件与历史投影 | `61e3efcc`、`23bc323b`、`917472b4`、`b8744637` | guard 状态变化后旧根是否作废；延迟/限速是否读取联立电压；OR 同刻只执行一次。见[事件数学](../../../evas/docs/math/events.md)、[重定位测试](../../../evas/tests/test_event_relocalization.py)、[投影测试](../../../evas/tests/test_history_projection.py)。 |
| 语言展开 | `fc945dc0`、`1fcd06bb`、`3a24fe67`、`16112055`、`0388e035` | 函数、循环、数组、层次和宏是否归入同一 IR；实例及展开后的算子历史是否独立。见[前端契约](../../../evas/validation/ANALOG_CONDITIONS_CONTRACT.md)及[确认集 language/histories](../../../evas/validation/confirmation/README.md)。 |
| 动态日程与整批提交 | `8d972837`、`63afd040`、`04cb050a` | 新日程先认证，再推进历史；失败不得改写帧、日程和事件记录；最终历史误差仍通过验收。见[定时契约](../../../evas/validation/TIMED_OPERATOR_CONTRACTS.md)、[动态 timer 测试](../../../evas/tests/test_dynamic_timer.py)、Rust Controller 私有回归。 |
| DAE 与直接 PWL 滤波（前一检查点） | `152a920d` | 滤波 DC 区间是否进入初始根；积分 IC 是否保留；高阶状态数是否与调用数分开；原约束和前向误差是否同时检查。见[共同数学](../../../evas/docs/math/continuous.md#index-one-多项式隐式电压-dae)、[独立开发测试](../../../evas/tests/test_implicit_filters.py)。 |
| 滤波一致初值与非线性 DC | `6952fb69`、`114d676e` | 原贡献、积分 IC 和滤波 DC 条件是否联合认证；内部节点/算子输入及 proper 直接通路是否完整；事件续算是否绕过冷启动。见[共同初始化数学](../../../evas/docs/math/continuous.md#index-one-多项式隐式电压-dae)、[DAE/滤波测试](../../../evas/tests/test_implicit_filters.py)、[混合动态测试](../../../evas/tests/test_mixed_dynamics.py)和[本轮收据](joint-dc-receipt.json)。 |
| 审查修复重复包含 | `d68d3db4` | 同一文件多次 include 时，各历史调用是否保留独立身份；包含路径是否与宏和循环路径组合。三个独立解析回归先失败后通过。见[预处理契约](../../../evas/validation/ANALOG_CONDITIONS_CONTRACT.md#preprocessing)、[开发回归](../../../evas/tests/test_preprocessor.py)和[提交前收据](review-receipt.json)。 |

这些批次都是限定支持。更广的事件驱动历史根重定位、DAE 事件/复位/ddt、
非线性直接通路、可变/嵌套历史参数及更广语言范围仍有缺口，具体以能力表为准。
这些本地收据没有新增 Spectre/ngspice 执行或性能结论；GitHub CI 对照另行记录。

## 执行与判定

- 原 31 条件使用冻结模型、刺激和两档设置。全部配置通过 transient API 执行；
  结果由原独立检查器重判，执行失败也计入固定分母。
- [七案例确认集](../../../evas/validation/confirmation/README.md)在 `5171558c` 固定模型、
  数学答案、目标、检查器及清单，随后才首次执行。稀疏和加密两档共 14 次。
  首轮没有失败后调参或修复。后续相同输入执行记为复跑，不增加未见条件数量。
- DAE/滤波及一致初值是在首轮确认之后新增的功能，其解析回归属于开发证据。
  首轮确认不能证明这项新增组合；当前的共同集复跑也不替代新的未见确认。
- 正式 DVS 资格仍为 **I**。有限观察通过不证明所有组合、完整 LRM 或一般连续时间误差资格。

[receipt.json](receipt.json)保存前一运行时 `152a920d` 的构建/源码、输入/检查器身份和观察结论；
[matrix-analysis.json.gz](matrix-analysis.json.gz)保存完整 62 配置的重判及波形身份。
压缩文件只含紧凑分析，不包含原始波形。可用 Python 标准库读取：

```sh
python3 -c 'import gzip,json; print(json.dumps(json.load(gzip.open("experiments/runs/capability-completion/matrix-analysis.json.gz")),indent=2))'
```

一致初值检查点运行时 `114d676e` 使用相同冻结输入和原检查器重新执行。
[joint-dc-receipt.json](joint-dc-receipt.json)绑定这次检查，
[joint-dc-matrix-analysis.json.gz](joint-dc-matrix-analysis.json.gz)保存 62 配置的紧凑重判。
原收据和分析保留；既有七案例确认属于复跑，不增加未见条件数量。

提交前直接审查发现并修复重复 include 的历史身份冲突；未使用独立子审查者。
修复后的运行时 `d68d3db4` 再次完成全部 Python/Rust 回归、原矩阵和既有确认集。
[review-receipt.json](review-receipt.json)绑定源码、复用的未改 Rust 构建及检查身份；
[review-matrix-analysis.json.gz](review-matrix-analysis.json.gz)保存该次矩阵重判。
此前检查点的收据保持原样。GitHub CI 与外部仿真器对照不在这份本地收据内。

矩阵仍使用既有 [matrix.py](../../archive/pr14-pr15-validation/matrix.py)执行。
本目录的 [analyze_matrix.py](analyze_matrix.py)复用原检查器，在计数前核对冻结来源、
完整输出清单、模型、条件及设置。它不改变阈值或重新生成波形。

```sh
python3 -B experiments/archive/pr14-pr15-validation/matrix.py evas \
  --source FROZEN_INPUTS --root runs/matrix-NEW \
  --kernel evas/rust_core/target/release/evas-kernel
python3 -B experiments/runs/capability-completion/analyze_matrix.py \
  --source FROZEN_INPUTS --run runs/matrix-NEW --out runs/analysis-NEW.json
```

`FROZEN_INPUTS` 是收据绑定的本地冻结输入库存。哈希只证明身份；取得该库存和原始输出之前，
不能声称已重现这份矩阵的观察。确认集输入、检查器及数学答案已在仓库内，可按其 README 独立执行。
