# Cadence 安装库模型：其他物理域

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [damper.va](damper.va)<br>[来源](../../SOURCES.md#cadence-multidomain-damper) | 机械阻尼元件，连接平动机械端口。 | `` damper(posp, posn) `` | IC618Hotfix4 / ICADVM201<br>`` real d = 1000 `` |
| [dc_motor.va](dc_motor.va)<br>[来源](../../SOURCES.md#cadence-multidomain-dc_motor) | 连接电气端口和转动机械端口的直流电机。 | `` dc_motor(vp, vn, wshaft, pos_shaft) `` | IC618Hotfix4 / ICADVM201<br>`` real km = 4.5 ``；`` real kf = 6.2 ``；`` real j = 0.004 `` |
| [em_relay__ic618hotfix4.va](em_relay__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-multidomain-em_relay__ic618hotfix4) | 由控制电压驱动的电磁继电器。 | `` em_relay(vopen, vcomm, vclosed, vctrl_p, vctrl_n) `` | IC618Hotfix4<br>`` real vtrig=0.5 from (0:inf) ``；`` real vrelease=0.5 from (0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [em_relay__icadvm201.va](em_relay__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-multidomain-em_relay__icadvm201) | 由控制电压驱动的电磁继电器。 | `` em_relay(vopen, vcomm, vclosed, vctrl_p, vctrl_n) `` | ICADVM201<br>`` real vtrig=0.5 from (0:inf) ``；`` real vrelease=0.5 from (0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [gearbox.va](gearbox.va)<br>[来源](../../SOURCES.md#cadence-multidomain-gearbox) | 按传动比连接转动机械端口的齿轮箱。 | `` gearbox(wshaft1, wshaft2) `` | IC618Hotfix4 / ICADVM201<br>`` real radius1=1 from (0:inf) ``；`` real inertia1=0 from [0:inf) ``；`` real radius2=1 from (0:inf) `` |
| [mag_core.va](mag_core.va)<br>[来源](../../SOURCES.md#cadence-multidomain-mag_core) | Jiles–Atherton 磁芯模型。 | `` mag_core(mp,mn) `` | IC618Hotfix4 / ICADVM201<br>`` real len=0.1 from (0:1000) ``；`` real area=1 from (0:inf) ``；`` real ms=1.6M from (0:inf) `` |
| [mag_gap.va](mag_gap.va)<br>[来源](../../SOURCES.md#cadence-multidomain-mag_gap) | 磁路中的气隙模型。 | `` mag_gap(mp,mn) `` | IC618Hotfix4 / ICADVM201<br>`` real len=0.1 from [0:inf) ``；`` real area=1 from (0:inf) `` |
| [mag_winding.va](mag_winding.va)<br>[来源](../../SOURCES.md#cadence-multidomain-mag_winding) | 连接电气与磁路端口的绕组模型。 | `` mag_winding(vp,vn,mp,mn) `` | IC618Hotfix4 / ICADVM201<br>`` real num_turns=1 ``；`` real rturn=0 `` |
| [mass.va](mass.va)<br>[来源](../../SOURCES.md#cadence-multidomain-mass) | 平动机械质量元件。 | `` mass(posin) `` | IC618Hotfix4 / ICADVM201<br>`` real m = 1000 ``；`` integer gravity = `yes `` |
| [restrainer__ic618hotfix4.va](restrainer__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-multidomain-restrainer__ic618hotfix4) | 限制机械运动范围的约束元件。 | `` restrainer(posp, posn) `` | IC618Hotfix4<br>`` real minl = 0.02 ``；`` real maxl = 0.10 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [restrainer__icadvm201.va](restrainer__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-multidomain-restrainer__icadvm201) | 限制机械运动范围的约束元件。 | `` restrainer(posp, posn) `` | ICADVM201<br>`` real minl = 0.02 ``；`` real maxl = 0.10 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [road.va](road.va)<br>[来源](../../SOURCES.md#cadence-multidomain-road) | 含路面起伏的机械激励模型。 | `` road(posin) `` | IC618Hotfix4 / ICADVM201<br>`` real height = 0.05 from (0:inf) ``；`` real length = 0.10 from (0:inf) ``；`` real speed = 10 from (0:inf) `` |
| [spring.va](spring.va)<br>[来源](../../SOURCES.md#cadence-multidomain-spring) | 机械弹簧元件。 | `` spring(posp, posn) `` | IC618Hotfix4 / ICADVM201<br>`` real k = 5000 ``；`` real l = 0.5 `` |
| [three_phase_motor.va](three_phase_motor.va)<br>[来源](../../SOURCES.md#cadence-multidomain-three_phase_motor) | 连接三相电气端口和转动机械端口的电机。 | `` three_phase_motor(vp1, vn1, vp2, vn2, vp3, vn3,shaft_pos,shaft_w,com) `` | IC618Hotfix4 / ICADVM201<br>`` real km = 0.06 ``；`` real kf = 0.6 ``；`` real j = 0.0004 `` |
| [trafo_hdl.va](trafo_hdl.va)<br>[来源](../../SOURCES.md#cadence-multidomain-trafo_hdl) | 连接两个绕组的变压器模型。 | `` trafo_hdl(vp_1, vn_1, vp_2, vn_2) `` | IC618Hotfix4 / ICADVM201<br>`` real turns1 = 1 from (0:inf) ``；`` real turns2 = 1 from (0:inf) ``；`` real rwinding1 = 0 from [0:inf) `` |
| [wheel__ic618hotfix4.va](wheel__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-multidomain-wheel__ic618hotfix4) | 轮子与固定路面的机械关系模型。 | `` wheel(posp, posn) `` | IC618Hotfix4<br>`` real height = 0.5 from (0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [wheel__icadvm201.va](wheel__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-multidomain-wheel__icadvm201) | 轮子与固定路面的机械关系模型。 | `` wheel(posp, posn) `` | ICADVM201<br>`` real height = 0.5 from (0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
