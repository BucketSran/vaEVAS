# 当前候选的四后端表

本表使用尚未合并的 PR #108 候选，实际 Linux 执行源码为
`830c8168ada17122bb64932553a02591181461d9`，EVAS 运行时代码与已测试的
`5ddf820d8b4aa5f0c847905da86f4fee470b94db` 相同。新跑 EVAS 原12条件，
历史 Spectre/开源参考36条保留各自身份；同一新 checker 重分析全部48槽。

EVAS 的 **12P** 表示这些条件在已取得资格的有限观察点上满足原行为和误差预算。
它不表示已经和 Spectre 全面对齐，也不证明连续时间内不会出现未观察到的短脉冲。
C1/#79 的原严格失败、VCO 原近邻点 F/I，以及论文两项相位条件的精确边界诊断 I
均继续保留。参考后端的 I 表示证据不足，不能据此宣称 EVAS 数值能力优于它们。

这次首先补齐实际逐点证书、来源和输入误差界，得到8P/4I；随后发现四个 I
来自 checker 在换算时间单位时把相邻浮点时间合并。修复只将严格排序检查放在
原始秒时间上，相同或倒序时间仍拒绝。原数据、阈值和48槽分母不变。
原 I12、8P/4I 和全部旧运行均保留，新 checker 及其校准、审核、重分析分别绑定身份。

下面两表直接摘自同一份维护工具输出，仅移除本地 assessment 链接。
[紧凑收据](evidence/integrated-observations-20261009.json)记录工具、内核、分析及旧结论身份。
完整资料在可见工作区的 `runs/alignment-implementation-20261009/paper-current-v1/`，
属于 local-only。这仍是开发条件的结果，论文正式验收还需补足参考观察资格、
设置适用范围、原边界义务和 main 整合。

上一候选的[I39/X9 表](https://github.com/BucketSran/vaEVAS/blob/e889068028517b17d552f37b79ee09cb01e90277/experiments/backends/paper/candidate-table.md)
继续保留其原身份，没有被重标为本次执行。

# core-v1 results

N=12 conditions; 4 backends; 48 slots. Cards SHA256 `e1ae5311da9e05991e9802da1a24e97a70d179972608a1b9d21eb00013f61a53`.
Immutable card design status: A0-cards-ready-for-A1-source-and-observation-qualification.
Actual outcomes below are separate from card design status and status_by_backend.
Counts are P/F/U/X/I/T: pass/fail/confirmed unsupported/execution failure/indeterminate/not run.
Missing slots are T only when --allow-pending is explicit. Properties and old31 add no conditions.

| Primary group | N | evas | spectre | openvaf_r_ngspice | gnucap_modelgen |
| --- | ---: | --- | --- | --- | --- |
| voltage | 1 | 1/0/0/0/0/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 |
| expression | 1 | 1/0/0/0/0/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 |
| event | 3 | 3/0/0/0/0/0 | 0/0/0/0/3/0 | 0/0/0/3/0/0 | 0/0/0/0/3/0 |
| history | 1 | 1/0/0/0/0/0 | 0/0/0/0/1/0 | 0/0/0/1/0/0 | 0/0/0/0/1/0 |
| continuous | 2 | 2/0/0/0/0/0 | 0/0/0/0/2/0 | 0/0/0/0/2/0 | 0/0/0/1/1/0 |
| structure | 1 | 1/0/0/0/0/0 | 0/0/0/0/1/0 | 0/0/0/1/0/0 | 0/0/0/0/1/0 |
| combination | 3 | 3/0/0/0/0/0 | 0/0/0/0/3/0 | 0/0/0/2/1/0 | 0/0/0/1/2/0 |
| Total | 12 | 12/0/0/0/0/0 | 0/0/0/0/12/0 | 0/0/0/7/5/0 | 0/0/0/2/10/0 |

| Condition | Primary group | Scenario | Features/operators | evas | spectre | openvaf_r_ngspice | gnucap_modelgen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR-01 | voltage | sample_hold | voltage_access, voltage_contribution | P | I | I | I |
| EX-01 | expression | vco | if_else, sequential_assignment, arithmetic | P | I | I | I |
| EV-SH-01 | event | sample_hold | initial_step, timer, event_assignment | P | I | X | I |
| EV-HC-01 | event | hysteresis | cross, event_assignment, initial_step | P | I | X | I |
| EV-HC-02 | event | hysteresis | initial_step, input_dependent_initialization, cross | P | I | X | I |
| TM-01 | history | sample_hold | timer, transition | P | I | X | I |
| CP-01 | continuous | vco | idt | P | I | I | I |
| CP-02 | continuous | vco | idtmod, sin | P | I | I | X |
| SI-01 | structure | sample_hold | module_instances, instance_state, timer | P | I | X | I |
| CO-SH-01 | combination | sample_hold | cross_or, if_else, initial_step, transition, event_assignment | P | I | X | I |
| CO-HC-01 | combination | hysteresis | cross, transition, event_assignment | P | I | X | I |
| CO-VCO-01 | combination | vco | if_else, sequential_assignment, idtmod, sin | P | I | I | X |
