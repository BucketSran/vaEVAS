# Cadence 安装库模型：控制环路

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [error_calc.va](error_calc.va)<br>[来源](../../SOURCES.md#cadence-control-error_calc) | 生成控制系统的误差信号。 | `` error_calc(sigset, sigact, sigerr) `` | IC618Hotfix4 / ICADVM201<br>`` real tdel = 0 ``；`` real trise = 1m from (0:inf) ``；`` real tfall = 1m from (0:inf) `` |
| [lag_compensator.va](lag_compensator.va)<br>[来源](../../SOURCES.md#cadence-control-lag_compensator) | 滞后补偿器，用于控制环路频率响应整形。 | `` lag_compensator(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 from (0:inf) ``；`` real tau = 1 from [0:inf) ``；`` real alpha = 2 from (1:inf) `` |
| [lead_compensator.va](lead_compensator.va)<br>[来源](../../SOURCES.md#cadence-control-lead_compensator) | 超前补偿器，用于控制环路频率响应整形。 | `` lead_compensator(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 from (0:inf) ``；`` real tau = 1 from [0:inf) ``；`` real alpha = 0.1 from (0:1) `` |
| [lead_lag_compensator.va](lead_lag_compensator.va)<br>[来源](../../SOURCES.md#cadence-control-lead_lag_compensator) | 组合超前与滞后的补偿器。 | `` lead_lag_compensator(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 from (0:inf) ``；`` real tau1 = 1 from [0:inf) ``；`` real alpha1 = 2 from (1:inf) `` |
| [p_controller.va](p_controller.va)<br>[来源](../../SOURCES.md#cadence-control-p_controller) | 比例控制器。 | `` p_controller(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real kp = 1 from [0:inf) `` |
| [pd_controller.va](pd_controller.va)<br>[来源](../../SOURCES.md#cadence-control-pd_controller) | 比例微分控制器。 | `` pd_controller(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real kp = 1 from [0:inf) ``；`` real kd = 0 from [0:inf) `` |
| [pi_controller.va](pi_controller.va)<br>[来源](../../SOURCES.md#cadence-control-pi_controller) | 比例积分控制器，输出比例项与积分项之和。 | `` pi_controller(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real kp = 1 from [0:inf) ``；`` real ki = 0 from [0:inf) ``<br>原注释误写包含微分项，实现是 PI。 |
| [pid_controller.va](pid_controller.va)<br>[来源](../../SOURCES.md#cadence-control-pid_controller) | 比例积分微分控制器。 | `` pid_controller(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real kp = 1 from [0:inf) ``；`` real ki = 0 from [0:inf) ``；`` real kd = 0 from [0:inf) `` |
