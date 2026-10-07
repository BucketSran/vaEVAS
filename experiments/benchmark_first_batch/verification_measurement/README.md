# 验证工具与测量表征任务建设

本组新增 5 道验证工具题和 4 道测量表征题，已有 va08 仅在登记表引用。所有新题为仓库原创 `behavioral_synthetic` 电压域实验，以真实 SAR、开关电容时序、比较器、S/H 和 PLL 信号路径为工程对象。它们不是物理器件表征，未借用厂商曲线或外部分发受限源码。

`build.py` 生成本组拥有的 9 个 Harbor 目录及登记表。规范判据是 `benchmark/checkers/first_batch_verification.py` 与 `first_batch_measurement.py`，任务的 `verify.py` 调用协调者提供的 `circuit_task.main(evaluate)`。公共运行模块及规范判据的任务内副本由协调者打包；模块不存在时不宣称已接入验收。生成器不会写入现有 va08。

```sh
python3 -B experiments/benchmark_first_batch/verification_measurement/build.py
python3 -B -m unittest discover -s experiments/benchmark_first_batch/verification_measurement -p test_checkers.py -v
```

行级回归含 10 个测试方法，每项任务的公开参数/故障组合接受真实合同波形，错误的刺激或结果必须拒绝；另有 20 dB 解析频谱验证。该测试独立构造数学波形，没有运行候选 Verilog-A，因此不是 Spectre 校准证据。

每题保存至少 3 个可执行语义错版，分别针对不同合同条款。校准应首先运行全部参考配置，然后对每个错版找到至少一个实际运行且被拒绝的配置，同时保留任何额外通过/失败条件。验证 checker 题必须覆盖正确器件和全部三种故障，尤其晚期失锁、复位旧结果和建立之后回弹。不得把编译失败当成语义拒绝。

| 任务 | 原始独立判据 | 关键误版 |
| --- | --- | --- |
| verify-sar-flow | 实际刺激、done 数量/时间、码值、复位中止，再比较 verdict | 恒接受、恒拒绝、漏中止刺激 |
| verify-nonoverlap-stimulus | 两相全部上下沿、死区、无重叠、下游采样传递 | 重叠、错误死区、缺少第二相、无效电平幅值 |
| verify-comparator-overdrive | 正负 overdrive/common-mode、全部时钟边沿、输出延时与复位 | 单极性、共模写死、复位不足 |
| verify-pll-lock-checker | 最近 ref 边沿相位、全部周期、边沿数、末期活动 | 恒接受、错误检查获取期、漏丢周期 |
| verify-sh-settling-checker | 建立和保持全部窗口最大误差 | 恒接受、宽松门限、只看早期 |
| measure-adc-spectrum | 实际64采样码、DC、完整单边DFT，谐波属于SNDR分母 | 功率当幅度dB、删谐波、固定bin |
| measure-comparator-delay-hysteresis | 慢扫输出阈值、阶跃传播延时、斜率校正 | 忽略校正、低阈值符号错、单位错 |
| measure-sh-acquisition-droop | 首次建立且余窗无回弹、有符号保持端点斜率 | 门限错、去掉符号、间隔错 |
| measure-pll-relock-jitter | 连续4沿确认的第一沿、20沿19周期总体标准差 | 用第4沿、峰峰值代RMS、混入获取 |

固定隐藏配置共有32个。本目录不自行发远端 job；所有商业仿真由协调者的 circuit harness 调度，全局 Spectre 并发不超过4。实际校准、Harbor Trial 和 Agentic 运行状态分别记录，未完成项保持 pending。当前登记表是建设清单，不是正式已校准题数。

实际首轮校准发现两项工程问题，按原合同修复：ADC参考使用的 `M_PI 宏不符合共享提交策略，因此改为同精度π字面常量；两相时钟参考用连续 `$abstime` 条件跳变，未预约事件，实际边沿会等到下一个0.5ns数值步才更新，例如 phase2 第一沿55.55ns而合同55.05ns。参考刺激已改用四个周期timer预约相位上下沿，保留0.3ns边沿容差。三种负例仍各自注入重叠、错误死区和缺相。修订后用主树 `prepare_source` 静态核验本组54份VA源码全部通过；10个行级回归通过。新参考实际运行仍需协调者重新校准，不能用这些检查代替。

电平判据经过独立review收紧：非重叠题还检查所有稳定原始点符合0/1V电平±0.01V，增加0.49/0.51V低摆幅错版及三条件拒绝回归。全组现有28个语义负例、55份VA源码。静态提交合同可重复运行 `python3 -B experiments/benchmark_first_batch/verification_measurement/check_source_contract.py --runtime benchmark/checkers/circuit_task.py`，只读取源码，不执行候选。

ADC实际py312首轮三个条件均执行成功，但时钟cadence拒绝；DFT重算与参考输出的差值约1e-14dB。原始首沿10.05ns，后续出现111.15、211.45ns等边沿，最大偏移1.4ns。原因是合成器件时钟也用了未预约的连续时间条件。器件改为10ns/60ns起始、100ns周期的两个timer控制clk，保持原100ns采样timer。独立cadence的0.2ns容差、64样本定义及所有频谱判据不变。公开器件、隐藏support和generator同步修改，等待实际重跑。

测量checker新增两项已复现的无效观测防护：合法时钟配合64个全零ADC码，旧判据在已判原始输入不符后仍调用频谱，触发除零；PLL缺少ref边沿但存在clk获取边沿，旧判据调用空集合min。现在原始ADC覆盖/码值/输入校验失败即返回结构化拒绝；PLL在配对前拒绝空参考边沿。没有通用异常捕获，不屏蔽真正的checker代码错误，也未改任何正常计算或容差。新增两个行级回归先复现异常再验证拒绝，全组12 tests通过。该复现只涉及行级输入，没有证明真实VA能诱导异常，也未运行新仿真。对保存的12个实际条件做源码/波形/冻结case哈希绑定重判，9个原有效条件和3个原cadence失败条件的分数全部保持，正常指标最大浮点差约7.1e-15。
