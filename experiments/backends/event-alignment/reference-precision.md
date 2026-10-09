# 固定参考精度流程 v1

`precision_profile.py` 只准备输入和分析观察，不启动后端。使用同目录的
`prepare_spectre.deck`、`normalize_psf.normalize`、`compare.compare` 和
`paper/settings_readback.spectre`，继续沿用原模型、观察和外部预算。

参考精度的有限判据是冻结网格上的相邻档位稳定性。每个档位均保留，不能执行后
删去失败档位或改预算。它不证明参考真值，也不替代原独立数学 checker 或
EVAS/Spectre 直接比较。`reltol` 是求解器控制，不是输出误差上界。
连续时间资格始终为 I；这里没有新加通用证明门槛。

## 执行前冻结

输入是已有 `case.json` 和 `dut.va`，以及三个显式文件：

- ladder：版本、标识、`method=traponly` 和至少三个有序档位，每档声明
  reltol/vabstol/iabstol/maxstep。给定的 `precision-ladder-v1.json` 是原事件模型
  125 ns 步长的单因素容差计划，不自动适用于其他模型。选择不同步长、方法或
  档位须执行前另存计划，不覆盖旧计划。
- contract：沿用原观察和预算，字段为 `stop`、`required_times`、`budgets_v`，
  可带 `phase_nodes`、`event_windows_s`。全部原电压节点都须有预算，时间逐项
  等于原 case 的 times，不新增近邻匹配容差。
- initialization：显式声明原初态与其证据，例如
  `{"declaration":"原模型 initial_step 与默认 DC 初态；没有外加 ic", "evidence":"dut.va"}`。
  该声明冻结初态要求，不证明隐藏内部状态已读回。需要实际初态检查时继续使用
  原 checker。

```sh
python3 -B experiments/backends/event-alignment/precision_profile.py freeze \
  evas/validation/event_alignment/M1 \
  experiments/backends/event-alignment/precision-ladder-v1.json \
  /absolute/path/original-contract.json /absolute/path/initialization.json \
  runs/reference-precision-M1-v1
```

输出新目录内的 `FROZEN.json` 和各档 model/deck/PROFILE。绑定模型字节、完整
case、输入、初态声明、观察、外部预算、全部档位及准备/读回/规范化/checker
工具 SHA。原 deck 构造器只支持 traponly，其他方法明确拒绝。
远端执行沿用原串行 supervisor、90 秒主仿真和既有资源限制；本工具没有另设
执行器、SSH、自动重试或全局耗时截止。

## 实际观察与设置读回

执行方逐档保留返回的 `dut.va`、`tb.scs`、PSF、完整日志及原 supervisor 收据。
必须返回未改动 deck/model；本地准备文件本身不能证明远端执行身份。

```sh
python3 -B experiments/backends/event-alignment/precision_profile.py attest \
  runs/reference-precision-M1-v1/FROZEN.json baseline \
  /absolute/path/returned/baseline /absolute/path/returned/baseline/tran.tran \
  /absolute/path/returned/baseline/spectre.log runs/baseline-attestation.json \
  --spectre-version 21.1.0.509.isr12 --execution-status success
```

version 参数必须出现于日志，具体版本身份仍需原执行收据绑定。读回器分别保留
请求设置、transient 有效设置、global user 设置、PSF header 与原始行号。
缺失/冲突/调整设置不回填请求值；不能稳定验收。规范化保留全部原生行、重复
时刻和十进制 token，既不插值也不替换最近点。失败/超时档位也应调用 attest，
保存缺失证据，不从计划分母移除。

## 固定网格分析

```sh
python3 -B experiments/backends/event-alignment/precision_profile.py analyze \
  runs/reference-precision-M1-v1/FROZEN.json runs/reference-analysis.json \
  runs/baseline-attestation.json runs/target-attestation.json \
  runs/confirmation-attestation.json
```

记录顺序必须与冻结档位完全相同。分析比较冻结 required_times 的精确 parsed
binary64 时刻；逐档原生行留在报告中，但网格外 native 行不冒充 required
观察。重复时刻不选相位。原计数通道取自 case 的
`criteria.expected_final_counts`；比较同一要求时刻的计数值。原生行数不当作
事件数，没有计数通道时 event_count_status 为 unknown。

- `event_count_unstable`：已有同刻计数观察变化；即使其他点缺失也保留变化。
- `not_converged`：已有相邻档位差异超过原电压预算。
- `incomplete`：没有已知越界，但档位、设置、版本或要求观察不足。
- `finite_stable`：全部相邻档位在原有限观察预算内，并具备实际设置/版本覆盖。

上述状态只表示当前固定计划结果。不能在看见结果后选择通过的一对子计划，
也不能将 reference 稳定直接称为数学准确或与 EVAS 对齐。
旧 v2/v3 bespoke deck 的实际 F/P 和 exact-query 结果保留。该工具不将
事后挑出的旧档位冒称执行前冻结的计划；身份保持不变的档位可另外用原分析器
作诊断，只有完整的新冻结计划才给本流程的稳定判定。

本地校准命令：

```sh
python3 -B -m unittest discover -s experiments/backends/event-alignment \
  -p 'test_*.py' -v
```

覆盖错误源/预算/请求设置身份、实际有效设置冲突、缺失观察/档位、事件计数
变化与观察缺失的区别，以及没有连续时间证明时仍可记录有限稳定性。
