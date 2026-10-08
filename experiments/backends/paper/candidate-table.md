# 当前候选的四后端表

本表对应尚未合并的 PR #108 源码 `41c3f34e248fe6bf5403552d89c1a1793b172899`。
Linux release 候选新执行原 12 条 EVAS 条件，复用原 36 条 Spectre/开源参考。
原条件、预算、checker 和 48 槽分母均不变。EVAS 12 条均产生波形，但原始
观测的来源、不确定性及有效设置等资格仍不完整，所以是 I12，不能记为 12P。

下面两个表摘自维护工具 `table.py` 的同一份实际结果，只去掉指向本地原件的链接。
完整表 SHA256 为 `33b33464632d99a17dfcf0875a1ca781a85f9710bf0f1979eab0dcc7249909b2`。
[紧凑收据](evidence/integrated-core-v2-20261009.json)记录实际内核、构建、执行与逐条资格。
完整记录与原 EVAS prior attempts 位于可见工作区的
`runs/alignment-implementation-20261009/al5/strict-current41c3/`，属于 local-only。
历史 I35/X13 和此前工程配对保留各自身份，本表不覆盖它们。

## 原 12 条件结果

N=12 conditions; 4 backends; 48 slots. Cards SHA256 `e1ae5311da9e05991e9802da1a24e97a70d179972608a1b9d21eb00013f61a53`.
Immutable card design status: A0-cards-ready-for-A1-source-and-observation-qualification.
Actual outcomes below are separate from card design status and status_by_backend.
Counts are P/F/U/X/I/T: pass/fail/confirmed unsupported/execution failure/indeterminate/not run.
Missing slots are T only when --allow-pending is explicit. Properties and old31 add no conditions.

| Primary group | N | evas | spectre | openvaf_r_ngspice | gnucap_modelgen |
| --- | ---: | --- | --- | --- | --- |
| voltage | 1 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 |
| expression | 1 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/0/1/0 |
| event | 3 | 0/0/0/0/3/0 | 0/0/0/0/3/0 | 0/0/0/3/0/0 | 0/0/0/0/3/0 |
| history | 1 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/1/0/0 | 0/0/0/0/1/0 |
| continuous | 2 | 0/0/0/0/2/0 | 0/0/0/0/2/0 | 0/0/0/0/2/0 | 0/0/0/1/1/0 |
| structure | 1 | 0/0/0/0/1/0 | 0/0/0/0/1/0 | 0/0/0/1/0/0 | 0/0/0/0/1/0 |
| combination | 3 | 0/0/0/0/3/0 | 0/0/0/0/3/0 | 0/0/0/2/1/0 | 0/0/0/1/2/0 |
| Total | 12 | 0/0/0/0/12/0 | 0/0/0/0/12/0 | 0/0/0/7/5/0 | 0/0/0/2/10/0 |

| Condition | Primary group | Scenario | Features/operators | evas | spectre | openvaf_r_ngspice | gnucap_modelgen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR-01 | voltage | sample_hold | voltage_access, voltage_contribution | I | I | I | I |
| EX-01 | expression | vco | if_else, sequential_assignment, arithmetic | I | I | I | I |
| EV-SH-01 | event | sample_hold | initial_step, timer, event_assignment | I | I | X | I |
| EV-HC-01 | event | hysteresis | cross, event_assignment, initial_step | I | I | X | I |
| EV-HC-02 | event | hysteresis | initial_step, input_dependent_initialization, cross | I | I | X | I |
| TM-01 | history | sample_hold | timer, transition | I | I | X | I |
| CP-01 | continuous | vco | idt | I | I | I | I |
| CP-02 | continuous | vco | idtmod, sin | I | I | I | X |
| SI-01 | structure | sample_hold | module_instances, instance_state, timer | I | I | X | I |
| CO-SH-01 | combination | sample_hold | cross_or, if_else, initial_step, transition, event_assignment | I | I | X | I |
| CO-HC-01 | combination | hysteresis | cross, transition, event_assignment | I | I | X | I |
| CO-VCO-01 | combination | vco | if_else, sequential_assignment, idtmod, sin | I | I | I | X |
