# Spectre verification on thu-sui

This experiment implements the 16 conditions in the seven
[new case cards](../../evas/validation/NEXT_CASE_CARDS.md), reruns 14 unchanged
v1 conditions, and runs a separate standard-array revision of the v1 lowpass
condition. There are **31 conditions and 62 configurations** across two settings.
**Completed on 2026-09-28: all 62 runs produced waveforms and all 62 met the
frozen finite-observation targets.** Spectre version: `21.1.0.509.isr12`.
No execution failures, timeouts, numerical violations or unresolved finite
checks occurred. Formal observation qualification remains I.

[PROTOCOL.md](PROTOCOL.md) is frozen before execution and describes inputs,
resource limits, targets, observation requirements, conditional history checks,
and the distinction between finite checks and formal qualification.

- [run_suite.py](run_suite.py) builds stimuli, netlists and the immutable manifest.
- [remote.py](remote.py) verifies inputs and runs Spectre serially without retries.
- [check_results.py](check_results.py) checks archived waveforms against independent
  mathematical answers, retaining every accepted point.
- [test_checks.py](test_checks.py) supplies eight calibration methods containing
  controls for all 16 new conditions, hand anchors, seven semantic fault classes,
  wrapped-range/whole-cycle faults, malformed observations and uncertainty bands.

The sampler source is intentionally shared by E2 and C1; C2 packages that same
sampler and the standard-array lowpass as two distinct modules. These are new
condition identities, with full instance declarations and all input/intermediate/
output nodes saved. The former v1 `v6-main` source remains frozen; `v6-standard`
is its explicitly identified source revision, not an additional 32nd condition.

Reproducible local checks:

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B evas/validation/check_design_math.py
python3 -B scripts/verify_validation_version.py
```

Build inputs only into a fresh directory:

```sh
python3 -B experiments/dvs2-spectre-validation/run_suite.py runs/NEW-RUN-input
```

The remote tool profile stays private. Execution, transfer, and reanalysis must
use the new run identity and preserve its input/output manifests. Results do not
qualify timestamp semantics or between-export behavior; formal DVS status is I.
This batch does not execute any other backend, historical variant suite or model
API, and does not modify EVAS or the v1 snapshot.

## 本轮结果

| 范围 | 条件数 | 基础设置 | 细化设置 |
| --- | ---: | ---: | ---: |
| v1 的 14 个原条件，加标准语法低通修订 | 15 | 15/15 | 15/15 |
| E1：方向事件计数 | 3 | 3/3 | 3/3 |
| E2：初始高电平与复位恢复 | 3 | 3/3 | 3/3 |
| C1：有状态实例隔离 | 3 | 3/3 | 3/3 |
| C2：低通后采样 | 1 | 1/1 | 1/1 |
| D1：积分、保持复位与释放 | 2 | 2/2 | 2/2 |
| D2：常频/变频相位与包裹 | 2 | 2/2 | 2/2 |
| S1：多输入与贡献累加 | 2 | 2/2 | 2/2 |
| **合计** | **31** | **31/31** | **31/31** |

表内“通过”表示成功执行且全部合格导出点满足预先固定的有限观测判据，
不表示正式 DVS P。两档共检查 **1,333,719 个时间点**；最大导出间隔约
1 ns。62 份实际生效的步长、最大步长、停止时间、误差容限和积分方法均与请求一致。
执行用时之和约 608 秒，包含编译与启动，不作为仿真器性能比较。

共同历史检查共涉及 40 条输出历史（包含同一条件的多输出，不另算测试条件），
在 B=0 与候选 B=0.25 mV 两个场景均取得共同历史见证。积分器的两条件、两档
也均取得相应有限数值见证。几个有独立解析目标的最大观测误差为：

| 量 | 最大误差 | 固定目标 |
| --- | ---: | ---: |
| C2 低通中间节点 | 0.1743 μV | 600 μV |
| D1 带复位积分输出，基础设置 | 48.73 μV | 1,000 μV |
| D2 累计/包裹相位 | 3.444e-7 周期 | 1e-4 周期 |
| D2 正弦电压 | 1.731 μV | 1,000 μV |
| S1 加权输出 | 9.437e-16 V | 1e-3 V |

上述误差是导出值相对解析答案或所列合法共同见证的误差，未加入未经证明的
物理观察误差界。D2 两条件分别观测到 2、4 次包裹；E1 的网格平移对照不证明
后端内部实际走过“精确零点”分支。其余后端的新增条件和旧 126 个变体未在本批运行。

所有 62 份日志均有相同的非致命 `VACOMP-2435` 提示：旧环境变量
`CDS_AHDLCMI_ENABLE` 不再受支持，Spectre 使用默认编译 C 流程。
未修改共享环境或放宽阈值；该提示与原始日志一并保留。

## 证据与复核

- [逐配置分析](results/analysis.json)：输入/输出检查、解析误差、共同历史见证和正式资格状态。
- [归档收据](results/RECEIPT.json)：版本、工具/输入/原始归档/分析哈希、运行预算和汇总。
- [实际设置核对](results/effective-settings.json)：62 份日志提取结果和请求匹配情况。
- 原始输出位于仓库忽略目录 `runs/dvs2-spectre-20260928-01/`，压缩包为
  `runs/dvs2-spectre-20260928-01.tar.gz`；thu-sui 的任务私有运行区另保留压缩归档。
  已核对压缩包 SHA-256 和清单中的 **1,216 个文件**，不将原始机器日志提交到仓库。
- 输入清单在启动前冻结，原始模型、网表、分析代码和协议快照均进入归档。
  [report.py](report.py) 是运行后整理设置与收据的程序，单独记录哈希，未改变判定器。
- 新判定器 8 项校准方法、共享历史判定器 17 项校准/适配方法均通过；设计算术检查
  和 v1 的 36 个 Git 工件、4 个快照工件、13 个原始输入身份检查通过。

原始证据保持只读，复核写入一个新的外部输出路径：

```sh
python3 -B experiments/dvs2-spectre-validation/check_results.py \
  runs/dvs2-spectre-20260928-01 runs/NEW-ANALYSIS.json
```

本次确认当前 31 条件在该版本 Spectre、这两档设置下均可执行且观测达标。
完整输入误差、时标语义、未采样区间和其他行为覆盖的资格工作仍未完成；不据此
外推所有 Spectre 版本、所有 Verilog-A 模型或 EVAS 的通过情况。
