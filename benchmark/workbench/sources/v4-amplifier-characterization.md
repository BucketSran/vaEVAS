# v4 增益与有限建立表征来源

服务[case-0018](../cases/testing-characterization/amplifiers/case-0018-amplifier-gain-settling/README.md)，分别保留`v4-family-038`、`v4-family-093`、`v4-family-370`同源组。共用一张来源页不把三个家族自动判为独立，也不把它们并成一个来源家族。

上游来源为`Arcadia-1/behavioral-veriloga-eval`的`7b5616dc52195ec275ec6d21c71d7763613702cd`；2026-10-11实读本仓库`c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9`保存的三个参考VA和各自score_tb。未重新审核全部旧DUT/Testbench/Bugfix包。

| 实读材料 | SHA-256 |
| --- | --- |
| [038增益模型](../../reference/v4/release/benchmarkv4-r53/tasks/038-programmable-gain-amplifier/evaluator/solution/programmable_gain_amplifier.va) | `19f89f91658be46809f3cee8fa247a0ab17bf3585816420481ad91542a810055` |
| [038原激励](../../reference/v4/release/benchmarkv4-r53/tasks/038-programmable-gain-amplifier/evaluator/score_tb.scs) | `e33ca664e43cb945f0af1e5f21d66fd5f10127417f2d3a945739e8ae7a9c8622` |
| [093测量参考](../../reference/v4/release/benchmarkv4-r53/tasks/093-gain-estimator/evaluator/solution/gain_estimator.va) | `72ced9edcd068aee48290f0b44d567ca2358beeb46bc82d2ecd36525ec76aab3` |
| [093独立信号源实验](../../reference/v4/release/benchmarkv4-r53/tasks/093-gain-estimator/evaluator/score_tb.scs) | `14939050be63a3a73219c1df6671b63792ebe054a53657147c86dfeb1c7f460b` |
| [370动态模型](../../reference/v4/release/benchmarkv4-r53/tasks/370-opamp-feedback-settling-monitor/evaluator/solution/opamp_feedback_settling.va) | `7b4b354ff35d8c791ea26597ef556be745f5923ce65012816bcef0c8bca20bf6` |
| [370原激励](../../reference/v4/release/benchmarkv4-r53/tasks/370-opamp-feedback-settling-monitor/evaluator/score_tb.scs) | `edd7fc6572b8b7d1747dd13eb66c46d59e893b80604d04fa000e53b27388bf8f` |

038提供被测增益级素材，093提供测量方法，370提供动态被测模型素材。093网表把输出另接正弦源，不能证明已经测过放大器；370内部error_metric与settled也不提供独立的外部测量依据。具体行为和组合缺口见[电路资产](../circuits/v4-amplifier-characterization-fixtures.md)。

新题按实际测量工作归电路测试与表征，不继承旧DUT/Testbench名字或历史认证。源码读取和哈希只证明材料身份，没有确认参考健康、测量有效或模型难度。资料遵循[原始使用约定](../../reference/README.md#使用约定)，限内部研究、外发资格未确认，本轮未复制新任务或运行仿真。
