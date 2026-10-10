# 按规格建模的P1任务

本目录维护#133归口的19个来源，每个来源对应一个正式Harbor任务目录。
所有参考、替代实现和语义错误版本都已保存；实际Spectre校准与模型试做仍待执行。
因此当前不能关闭#133，也不能把这些任务计入已发布评分题数。

`manifest.json`逐来源保存建设归口和验收状态。`run-plan.json`列出每个实际候选目录、
预期判定以及改动的语义，交给统一运行器冻结身份后执行。`variants.py`只生成候选，
不会生成或认证仿真成绩。运行器由根协调者维护，Spectre并发最多4。

每题环境公开接口和固定自测，solution和tests不进入解题镜像。checker只使用实际输入输出和
公开数学、采样或状态合同，不读取参考源码、评分私有状态或要求源码相似。
分辨率不足、缺失波形和非有限数据抛出环境错误，不能按候选零分处理。
不同合法实现的预期通过须经真实仿真确认；16题替代现采用独立状态表示或建模方式，生成路径与候选一致；这不能据此声称已覆盖任意VA语言特性。

024从实际CLK交点计算采样值，检查初态、保持、上升沿取样、高相与停钟、单调过渡及起止时长。
375采用公开的全局tick死区，检查两相和取消历史，包括短于tick的disable脉冲及下一边沿重启。
001重建三次内部采样的完整Alexander结构；旧外部retimed输入关系未沿用。
047冻结为全局tick轮询双边界，314为异步迟滞进入退出历史，两者有独立目标。
186包含固定trial DAC和比较器协作场景；091、307、308保留各自多模块职责。
091、307、308 现采用 `system-interfaces-v2`，公开固定 helper 接口、职责及可替换性。
每题六个条件分别验收端到端行为、两个独立组件及两个顶层替身响应；
实例名、内部节点名和合法 VA 写法不受限制，评分不解析或比对候选源码。
组件条件只载入被测 helper，固定兼容的另一组件及顶层作为刺激适配；
其判据仍从公开合同独立推导。替身条件保留真实顶层，检查它使用实际 helper 输出。
091 的组件条件还保存固定测试台内的 core 边界，检查样本及通知时序。
活动但无关的 public helper 配上私有正确电路，以及只驱动复位值的空壳，
均作为待实际校准的架构负例；其中旁路包的两个 public helper 本身仍正确。

新合同、checker 和负例未做实际 Spectre 校准，不能据此关闭 #133。
旧版参考/alternative 外部行为校准及三个任务的六个 one-shot 配置结果保留旧身份，
不能升级为新版通过证据；三题的 one-shot/Agentic prompt 均需重新冻结运行。
其余16题公开要求及 checker 未变。`build_structure.py` 可重建六条件及架构负例，
`variants.py` 在生成常规变体后也调用它，不运行仿真。

#133 的运行计划由62个候选包、138条件增至68个候选包、210条件。
新增6个架构负例包；三题每题5个候选包×6条件，共90个新版实际校准条件。
全37题原171个候选变体的口径相应增至177，完整条件总数由根运行清单另行计算，
不能把变体数当作条件数。历史结果的分母及失败保持不变。

三题的 `verify.py` 顶层显式导入 `v2_runtime`、`v2_spec` 和新增的
`v2_structure`，任务 tests 保存三者副本。author prepare 与 `sync_runtime.py`
按这些顶层导入复制共享 checker，因此依赖不依赖仓库路径。新增复制规则只涉及
这三题的 `v2_structure.py`；共享 `v2_spec.py`、`v2_runtime.py` 及其余16题未改。
本地已用实际 author prepare 和兼容 harness `8bd212a300f01942091570cffed028216c350a06`
生成18个独立条件包，在隔离目录通过18次导入及三个消费替身评分入口检查。
这些检查使用主机 Python，未执行容器内 Python 3.12 或 Spectre。

独立checker合同回归使用手工推导的电平与反馈序列，检查正确波形、错误反馈、持续跟踪、
互补输出错误及环境证据不足。目前这些回归不替代真实VA校准，也不提供难度结论。

```sh
python3 -B -m unittest discover -s experiments/benchmark_v2/spec_modeling -p 'test_*.py' -v
```

校准完成后，将原始运行保存于ignored runs，提取带候选、checker、激励和实际工具链身份的
紧凑证据到本目录。模型Agentic与适用one-shot须用同一固定环境，至少两个实际模型配置。

## 审查后的判据修正

独立审查发现375在过渡豁免区间会漏掉短暂两相重叠，038会把正常clipping metric平滑判错。
新增独立2ps网格波形先复现这两项错误，再修正判据。375互斥不豁免过渡；
038按实际输入、采样增益和复位历史确定clip目标变化时刻，只对metric保留tr平滑窗口，
连续out仍逐点检查。初始clipping和退出clip的metric下降过渡也有独立正例。
没有放宽电压容差。186公开上电P/M、dout、clkc、MSB指针及首帧发布0111；
375合法范围明确为`0<tr<=tick/2`，包含既有默认值。

038、375的判据行为已变，需用新版本重新评分冻结的真实波形，旧结果保留。
186公开材料改变，需冻结新题面身份。其他16题判据行为未改，但共享checker及19份副本
的文件身份都已更新，运行身份也须记录新SHA。

实际首轮314的stretched-input在17.466ns以后仍保持toggled高。参考和替代使用timer事件
后又严格比较$abstime与pulse_end，可能因回调时间舍入而丢弃已经到达的定时事件。
候选现由timer(pulse_end)直接清除脉冲，不再重复时间判定。相同调度修正用于其语义mutant；
314的候选身份需重冻并实际重跑，此处没有宣称修复已通过Spectre。独立checker回归以
16.236ns进入、17.236ns结束的手算脉冲验证健康波形通过及持续高电平失败。
091、307的contract将dut.va列为首项，保持允许修改文件集合不变；它们此前未进入仿真，
新contract身份需冻结后重跑。激励未改。

## 替代实现的形态与限制

`alternative_forms.py` 为下面16题生成固定候选，`variants.py` 复用同一入口。024、375、183已有不同实现形态，保持原候选。所有公开题面、source材料、科学条件和checker阈值不变。下表区分旧候选已有的形态与本轮生成结果，避免把已有packed或归一化状态误称为纯表达式改写。

| 来源 | 旧候选 | 本轮权威状态或建模方式 |
| --- | --- | --- |
| 071 | same held voltage; convex expression | voltage deficit relative to vinit is the acquisition state |
| 038 | same gain voltage latch; affine expression | latched discrete gain mode; gain voltage computed continuously |
| 082 | normalized control voltage already differs from reference | integer hundredths gain controller instead of real gain accumulator |
| 091 | same baseband state; weighted expression | LP accumulator in unscaled input units; derived baseband voltage |
| 307 | same absolute integrator voltage; shifted expression | saturated integrator deviation relative to vcm is the stored state |
| 308 | same reset and signal states; affine expression | reset latch stores signed deviation, derives absolute boundary voltage |
| 370 | same convergence counter; weighted expression | three-bit history of qualifying errors instead of convergence counter |
| 353 | same shifting history; voltage sum expression | circular three-symbol buffer instead of shifting three registers |
| 055 | same accumulator; operation order expression | post-feedback residual is stored; next quantizer input is temporary |
| 002 | same two analog output latches; centered expression | latched digital code/calibration word instead of two latched analog levels |
| 003 | same branch outputs; middle-region expression | ternary sub-ADC decision state drives residue and bit decoding |
| 047 | same window boolean; complemented predicates | two sampled comparator states feed combinational window AND |
| 314 | outside-state encoding already differs from reference | inside rail voltage is the hysteresis memory instead of a boolean |
| 001 | same three latches; XOR decisions | packed three-sample history with decision lookup instead of separate latches |
| 396 | one-hot ring already differs from reference | rotating two-bit quadrature state instead of modulo phase counter |
| 186 | packed SAR words already differ from reference | packed SAR masks and bit updates instead of four-element arrays |

有限表达式回归覆盖Alexander完整真值表、SAR四决策组合与位序、三次连续资格、离散增益控制，以及采集、低通、饱和积分的公开算例。它们执行实际候选表达式，但不是Verilog-A仿真；新候选全部标为待Spectre校准，原实际结果仍绑定旧候选SHA，不能继承为新版通过。生成身份检查也不证明行为通过。
