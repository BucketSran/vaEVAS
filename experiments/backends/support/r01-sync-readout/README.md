# 同步读出：完整运行与剩余差异

**原物理同步请求现在能在原时限内完成；原整题 checker 仍失败。** 修复消除了动态电压乘边沿的拒绝、时间关系在历史重建时的丢失，以及积分短步的重复计算。严格阈值导致的状态差异单独保留，不算修复通过。

| 原请求 | EVAS 本轮结果 | 实际 Spectre |
| --- | --- | --- |
| 物理 core，`r01-integrate-sync/c0` | 完成9001行；原 checker 失败 | 完成10902行；原 checker 通过 |
| 连接夹具，`core-boundary` | 完整运行；原 checker 失败 | 完成10052行；原 checker 通过 |

物理请求首候选耗时91.34秒，收窄低阶优化范围后的最终复验为76.13秒；两次完整响应逐位相同，原内核120秒、父进程135秒上限不变。这只证明本次请求完成，不表示一般性能排名或稳定的加速倍数。两份原 VA、刺激、容差、checker及历史成绩均保留。

## 哪部分已经正确，哪部分还不同

四路保持电压均满足原数值要求。与实际 Spectre 的原有限配对中，最大差为 **29.56 µV**，低于原2 mV门槛。这个配对保留原5 ns控制边沿窗口及插值，不证明窗内或全时域逐点一致。

整题失败来自 `valid` 和 `dout`。模型在 `cross(V(track)-vth,+1)` 内又判断 `V(track)>vth`：EVAS在根上读到等号，严格大于为假；Spectre实际首次回调约晚0.0501 fs，读到正的guard，条件为真。后续的保持标志和读出因此不同。这是本模型的实际观测，不是对Spectre所有回调的内部算法结论。

原291个配对点中，236个点的 `valid` 一致，此时 `dout` 最大差6.05 µV；另55个点的 `valid` 不同。这个分组解释失败，**没有删除失败点或改判通过**。只读回调版本与原Spectre的完整原生科学波形相同；修改源码的观测身份仍单列。

## 独立用例与支持边界

五个用例在实现前固定：斜坡乘边沿、增益1000、独立积分历史，以及普通/中断边沿后的两个滤波组合。本批前三个均能完成，分别有385个EVAS原生观察点；数学参考与实际Spectre均已核对。EVAS相对参考的最大有限误差为0、0.455 pV、0；Spectre只读回调版本分别为1.13 fV、1.20 pV、30.2 fV。浮点导出的零差不等于实数计算无误差。

这些结果**没有取得新Q资格**：实际关键边界两侧观察及外部导出/回调资格仍不完整。两张滤波卡在本批仍未实现，保留原正例及原拒绝，不记入通过数。另有相邻浮点切点的非线性事件窗口保守拒绝，归入#119，#131不动。

原工程Spectre实际生效 `reltol=1e-7`、`vabstol=1e-9 V`、`iabstol=1e-15 A`、`maxstep=100 ps`、`conservative`、`gear2only`；EVAS使用原网表请求的 `reltol=1e-6`、`vabstol=1e-9 V`、`maxstep=100 ps`，不应用Spectre的preset。

独立三卡的Spectre为 `reltol=1e-10`、`vabstol=1e-11 V`、`iabstol=1e-15 A`、`maxstep=T/128`，其中 `T=2^-20 s`；EVAS为请求的 `reltol=1e-9`、`vabstol=1e-11 V`、同一maxstep及显式观察时刻。EVAS使用自身积分方法，也没有电流未知量。

完整回归首轮有4项失败：一项强制点下的代表值变化、三项旧拒绝范围断言。现在纯源场保留原高阶路径，原逐位断言通过；三条乘积原式保留并新增非零输入正例。原失败日志保存，最终Rust为342通过、1忽略，相关Python为25通过；完整CI状态以PR最终提交为准。

## 复核入口

- [紧凑结果与身份](summary.json)：源码清单、内核、原输入和旧checker散列、实际运行、诊断分组和剩余缺口。
- [独立模型和数学答案](design/DESIGN.md)、[checker](checker/v2-centered/check.py)、[校准](checker/v2-centered/calibrate.py)：原61项合成正反控制通过；这些控制不是仿真器成绩。
- [EVAS配方差异](evas-recipes/MAPPING.json)：仅移除Spectre专用PSF格式、积分method和 `strobeoutput=all`；VA、刺激、数值请求和显式观察时刻保持。
- [公共路径回归](../../../../evas/tests/test_live_transition_coefficient.py)与[状态关系事务测试](../../../../evas/rust_core/src/transient_time_proof_tests.rs)：检查实时读值、根身份、历史保留、失败回退与重试。

checker和校准源码按原身份保留。校准命令会在脚本旁生成结果，复跑时将本目录复制到仓库的ignored `runs/` 下，再运行 `python3 -B checker/v2-centered/calibrate.py`。原始波形、审查和历次失败保存在 `current/runs/evas-night-20261014/delivery/issue-repair-20261015/next-sync/`，为local-only；仓库散列不是公开下载地址。旧候选超时、配方拒绝和读回失败均保留。
