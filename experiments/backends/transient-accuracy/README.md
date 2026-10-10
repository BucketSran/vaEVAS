# 瞬态精度与 VCO 发展对照

近邻固定时钟与线性历史的后续修复、新Spectre容差对照及保留失败，见
[近时钟历史证据](near-clock-history.md)。以下各节保留其原检查点身份。

## 2026-10-10 四组失败的实际补测

**两类模型都能在原预算内完成 EVAS/Spectre 工程对照。三个原配置是 Spectre 参考超差，
另一配置是连续观测点的时间偏差；本批没有发现需要修改 EVAS 内核的证据。**
[新收据](reference-followup.json)绑定 8 次新 Spectre 仿真、8 次同点 EVAS 和 8 次精确锚点 EVAS 请求。
两份 [非线性积分](fixtures/nonlinear.va)／[事件续算](fixtures/event-continuation.va)源码与旧实验逐字相同。
内核仍为 main `ab0df35b` 的实现，0.14.0 / IR18，源码候选 `b4f8c8a3`；本轮未改数值算法。

模型为 `z'=-a*z², z(0)=1`。第一例 `a=1`；第二例在名义 `t=0.5 s` 把 `a` 从 1 改成 2。
名义答案分别为 `z=1/(1+t)`、事件后 `z=1/(0.5+2t)`；放大输出为 `10000*(z-0.5)`。
固定预算为 z/low 各 0.1 µV、amp 为 1 mV，事件一次且位于原 100 ps 观察窗。

Spectre 21.1.0.509.isr12，`traponly`、`conservative`、stop=1 s 和原 `strobetimes`／`strobeoutput=all` 保持。
实际 log 与 PSF 读回的设置及最大 amp 名义误差如下。误差统计覆盖每档全部原生记录，不只看指定锚点。

| 配置 | 实际 reltol / vabstol | maxstep | 非线性积分 | 事件续算 |
| --- | --- | --- | ---: | ---: |
| 原基础档 | 1e-6 / 1e-8 V | 1 s | 9.488 mV，超差 | 11.689 mV，超差 |
| 只收紧容差 | 1e-9 / 1e-11 V | 1 s | 0.306 mV，通过 | 0.504 mV，通过 |
| 只缩小步长 | 1e-6 / 1e-8 V | 1 ms | 0.606 mV，通过连续观测验收 | 1.165 mV，超差 |
| 收紧容差并缩小步长 | 1e-9 / 1e-11 V | 1 ms | 0.236 mV，通过 | 0.289 mV，通过 |

基础与收紧档请求 reltol 分别是 1e-5、1e-8，实际值均小一档；实际 iabstol 分别为 1e-12、1e-15 A。
仅缩步不能保证本例达标。它与收紧容差分别改变一组控制，combined 是另列的新配置。
两例收紧容差后的结果足以满足本批目标，无需猜测或复刻 Spectre 内部接受网格。

两个 step-only 的原始 PSF 仍在 0.125、0.25、0.75 s 附近记录约 1.11e-16～2.22e-16 s 偏差。
这不是 EVAS 漏读，EVAS 原请求使用的就是这些实际时刻。新增 [qualify.py](qualify.py) 只为这两条有理数轨迹
补充连续观测验收：邻近点最多偏离 1 ps，不能越过事件侧；用精确有理数计算
`|记录值−名义答案(实际时刻)| + |名义答案(实际时刻)−名义答案(目标时刻)|`，仍须满足原电压预算。
最大 amp 时间项只有 1.43e-12 V。时间和值均未改写，没有插值；0、0.5、1 s 仍要求精确时刻。
这个规则不适用于 VCO、跳变侧或其他模型。

原 [check.py](check.py) 未修改，旧 **2/6** 结论不改。
新八档按严格精确时间判据为 **4/8**，按补充连续观测规则且双方独立、同点均达标为 **5/8**；
其余三档仍是参考超差。不能把“原四个失败已经查明”写成“四个原配置全部通过”。

EVAS 在 12,243 个共同点和另外 68 个精确锚点观测均达标。
共同点最大 amp 名义误差为 6.68e-11 V，八档最大自身请求预算占用为 0.00639；不是全轨迹误差证明。
事件模型的 EVAS native 记录均为 0.5 s 一次、`[a,n]=[1,0]→[2,1]`。
Spectre 的 count 跳变括在 `[0.4999999999, 0.5] s`，不能据此断言其内部回调恰好为 0.5 s；
因此上表报告相对名义轨迹的工程误差，不声称知道 Spectre 的内部误差估计。
实际 strobe 列表没有独立有效值读回，观测时刻由原 PSF 证明；尚不能区分内部步进与输出表示的贡献。

八次远端执行均完成并确认清理自有进程。远端解析包装漏带历史 reader 依赖，原 `observation_error` 保留；
收回未改写的 PSF 后用维护中的 reader 本地解析，没有重跑仿真。原始波形和完整执行材料仍为 local-only，
收据、模型与 checker 可随仓库审查，哈希不等于公开原始材料。

复算某份已解析原生观测，输出同时保留旧 verdict：

```sh
python3 -B experiments/backends/transient-accuracy/analyze.py observation.json \
  --model nonlinear --qualify-reference --output qualification.json
python3 -B -m unittest discover -s experiments/backends/transient-accuracy -p 'test_*.py' -v
```

## 2026-10-10 精度复核

[精度控制收据](precision-audit.json)绑定 main `ab0df35b` 的当前内核。原 VA、刺激、初值、
Spectre 数据与共同预算保持；用当前前端重新编译到 IR18，未修改旧请求的版本号来冒充迁移。
六次 EVAS 请求全部完成，共配对 7,045 个原生时刻。每点另用 `Fraction` 计算独立有理数答案，
六档均满足原电压请求预算。两档 tolerance-only 仍通过完整有限对照；baseline 参考超差和
step-only 缺 exact anchors 等原失败仍在。没有新增 Spectre 执行，没有新增支持范围。
控制含义、自动细化与拒绝边界统一在[数值手册](../../../evas/docs/math/solving.md#当前精度控制怎么用)维护。

本批的 2/6 是两个模型各三档设置的完整验收数，不是六种功能的支持率。四个未通过配置的原因如下；
`amp` 的独立误差预算为 1 mV，当前 EVAS 已查询点均满足原请求预算。

| 配置 | Spectre 的最大 amp 误差 | 完整验收未通过的原因 |
| --- | ---: | --- |
| nonlinear baseline | 9.488 mV | Spectre 超差；EVAS 独立检查通过 |
| event-continuation baseline | 11.689 mV | Spectre 超差；EVAS 独立检查通过 |
| nonlinear step-only | 0.606 mV | 双方同点波形达标，缺精确检查时刻 |
| event-continuation step-only | 1.165 mV | Spectre 超差，同时缺精确检查时刻 |

两个 step-only 的 Spectre 原始 PSF 将 0.125、0.25、0.75 s 附近记录为
0.1250000000000001、0.2500000000000002、0.7500000000000002 s。EVAS 请求沿用这些原生时刻，
没有漏掉已请求点。当前 checker 要求时间值完全相等，所以双方仍报 `missing_anchor`。
这定位到观测时间与验收的差异，尚未确定来自内部步进还是输出表示；不构成 EVAS 数值缺陷证据。
原 exact-anchor 判据和失败保持，未进行近邻替代、插值或重新判分。

## 近零采样状态与独立固定时钟

四端首轮中，EV-SH-01、CO-SH-01 因近零 real 状态的相对误差预算趋零而拒绝，
SI-01 因独立固定时钟的时间区间重叠而拒绝。现在保留 real 状态完整误差区间，
由后续电压、历史和事件等物理消费者认证；纯固定时钟簇按原 binary64 名义时刻
精确排序，并在原 time_tol、stop 和外部事件边界内选择可表示执行时刻。
整数精确性、事务回退和混合事件的保守拒绝继续保留。

本轮新跑三例 Spectre，并在相同导出时刻查询同一组合内核。没有插值或扩大 stop。

| 用例 | 同刻配对 | 原事件窗口外输出最大差 | 整段原始最大差 | 计数结果 |
| --- | ---: | ---: | ---: | --- |
| EV-SH-01 | 45,836 | out 0.300 mV | out 0.5997 V | 双方均4次 |
| CO-SH-01 | 46,083 | out 0.04992 mV；state 0.004 mV | out约0.05 mV；state 1.05 V | 双方均5次 |
| SI-01 | 35,785 | oa/ob各0.100 mV | oa 0.4499 V；ob 0.299902 V | 双方两实例均3次/2次 |

不同回调阶段分别涉及220、3、210行，全部位于预先冻结的事件窗口内。窗口外计数差为零。
Spectre 的部分 timer 约提前1 ns，EVAS选择不早于精确名义时间的代表值；采样结果会
随触发时间改变。CO-SH的cross也有数十ps差异。不能把这些差异删去，也不能把有限窗口外
符合原电压预算视为全波形一致。两条 Spectre 超原stop末记录单列保留。

[本次紧凑证据](core-followup.json)分别记录整段/窗口内/窗口外结果、原窗口、请求与
实际设置、计数和完整事件记录的查询不变性。全十二例 EVAS 从8份波形变为12份，
但这是 PR100/101/102 组合候选的执行结果。仅本节三例修复属于本 PR，限幅条件由PR100交付。
原论文判决没有改写。真实参考、raw与完整审查材料为 local-only；所有原失败保留。

下文瞬态精度实验是独立历史检查点，不能把它的通过数与本次合并计分。

本组实际运行 8 个 Spectre 配置。完整有限检查通过的是两个动态 tolerance-only 配置；VCO 100ps 仅原域内 80748 行符合波形判据，超 stop 末行和 EVAS 原 80749 时刻整批拒绝单列。前一 EVAS accuracy 检查点重放六个原请求后，四个完成，两个严格容差档拒绝认证；本轮候选实现逐字重放后六个完成，两个 tolerance-only 档满足完整有限对齐检查。前一检查点的独立数值审查已完成；本轮继续修复了特定等价严格编码的区间投影缺口，见下文追加证据。普通 phase 边界仍未解决。这些结果不签发 paper P，也不改变原 fixed12 卡或其 checker。

紧凑完整字段在 [evidence.json](evidence.json)。所有 raw、请求、响应、stdout/stderr、来源身份和失败收据保留在本机 ignored `current/runs/accuracy-control-20261007/backend/`；路径与 SHA 只是本地证据指针，不代表公开可下载。

## 条件与独立答案

nonlinear 模型满足 z'=−z²、z(0)=1，因此 z=1/(1+t)。event 模型在 timer(.5) 将 a 从 1 改成 2，之后 z=1/(1.5+2(t−.5))。输出 low=z−.5、amp=10000(z−.5)；count 应在事件后从 0 变 1。固定物理预算为 z/low 1e-7 V、amp 1e-3 V、count 精确、一次事件及 100ps 时间预算。严格容差不改变这些外部预算。

精确 anchors 为 0、.125、.25、.5、.75、1，event 另保留 .5+1e-8。两个 step-only 档缺少原生 exact .125/.25/.75 行；附近时刻没有替代这些义务。解析答案不依赖 EVAS 或 Spectre。

原 CO-VCO-01 的 source、PWL 刺激、IC=.125 cycle、stop=8us 和原 strobe times 保持不变。旧真实 Spectre baseline 40840 行复用；新增两个控制档。`retained-vco/` 是原 paper oracle 与条件的字节快照。预算为 ctl 10uV、freq 1mV、普通及 circular phase .001 cycle、sine 3mV、四次 wrap 和原 ±100ps 窗口。普通 phase、circular phase、从 drops 恢复的累积 phase、sine、事件计数和括定时间分别报告；不跨 wrap 插值。

## Requested 与 actual effective

所有 Spectre 档请求 conservative、traponly。下表 tolerance 顺序是 reltol / vabstol V / iabstol A；EVAS 使用对应 requested reltol/vabstol/maxstep，但这些数字不能当成两个模拟器同一数学保证。

| 模型/档 | Requested tolerance | Actual Spectre tolerance | Requested / actual maxstep |
| --- | --- | --- | --- |
| dynamic baseline | 1e-5 / 1e-8 / 1e-12 | 1e-6 / 1e-8 / 1e-12 | 1s / 1s |
| dynamic tolerance-only | 1e-8 / 1e-11 / 1e-15 | 1e-9 / 1e-11 / 1e-15 | 1s / 1s |
| dynamic step-only | 1e-5 / 1e-8 / 1e-12 | 1e-6 / 1e-8 / 1e-12 | .001s / .001s |
| VCO tolerance-only | 1e-8 / 1e-10 / 1e-15 | 1e-9 / 1e-10 / 1e-15 | 200ps / 200ps |
| VCO step-only | 1e-5 / 1e-7 / 1e-12 | 1e-6 / 1e-7 / 1e-12 | 100ps / 100ps |

安装手册预测 conservative maxstep 上限 stop/100=.01s，但 dynamic baseline/tolerance 实际 log+PSF 回读都是 1s。以 actual 为准。原 reader 对五份 pV/ms 单位记录报错；原错误保留，独立窄 SI 适配器逐 token 转换后再交原 reader。原 log、PSF 和 numerical checker 未修改。

## 前一检查点实际结果（历史记录）

下表属于 `1bea62cd` / kernel `b347f86e…`，保留当时的失败；本轮结果另列，不能把旧表读作新候选实现的表现。

| 配置 | Spectre 原生行 | Spectre 独立检查 | 最终 EVAS 同点尝试 | 配对结果 |
| --- | ---: | --- | --- | --- |
| nonlinear baseline | 298 | z 9.488e-7V / amp .009488V，超预算 | 完成；z 6.994e-15V / amp 6.997e-11V | 超预算 |
| nonlinear tolerance-only | 2116 | z 3.061e-8V / amp .0003061V，通过 | accumulated-history 8 次 refinement 后拒绝 | 2116 行未配对 |
| nonlinear step-only | 1029 | 波形符合，缺 exact anchors | 完成；z 1.11e-15V，缺原 anchors | 波形符合；缺行义务保留 |
| event baseline | 359 | z 1.169e-6V / amp .011689V，超预算 | 完成；z 2.22e-15V / amp 2.22e-11V | 超预算 |
| event tolerance-only | 2213 | z 5.044e-8V / amp .0005044V，通过 | amp forward bound 3.494e-10 > request budget 1.000e-11，拒绝 | 2213 行未配对 |
| event step-only | 1030 | z 1.165e-7V / amp .0011649V，超预算且缺 anchors | 完成；z 1.11e-15V，缺原 anchors | 超预算 |
| VCO tolerance-only | 40878 | 第一 center 普通 phase 约 1 cycle 错误 | 完成；第三 center 普通 phase 错误 | 第一及第三 center 差近 1 cycle |
| VCO 100ps step-only | 80749 | 域内 80748 行波形符合；末行超 stop | 整批 invalid_inputs | 全批未配对；另列域内诊断 |

最终完成的两个 event 档原生 timer 均在 .5s 一次，从 [a,n]=[1,0] 变为 [2,1]。Spectre count 跳变括定为 [.4999999999,.5]。严格容差 near-zero amp 的 EVAS 请求绝对精度 1e-11V 比共同物理预算 1e-3V 紧得多；拒绝没有波形可评分，不能删除。

VCO tolerance-only 的 Spectre circular 最大 4.60e-11 cycle、sine 2.89e-10V，但第一 center 普通 phase 仍超预算。100ps 原生末行 8.000000000003679e-6 大于 stop=8e-6。另一次独立身份本地诊断只查询原域内 80748 个原生时刻，原分母 80749 和未配对末行保留。第三 center 两端普通 phase 差 .9999999974 cycle；circular 2.60e-9 cycle、sine 1.63e-8V 符合各自预算。诊断不替代整批失败。

compiled-binary64 IR 证书、decimal-source oracle 和实际 Spectre 是不同数学对象；普通 phase 边界、source/export/stop qualification 继续独立。有限采样符合不能证明全连续时间精度。

## 本轮六请求重放

候选 kernel SHA 为 `c4fa73110ee6ca650ba902e3b89216a95617c28114f19a4338e749b5156bac7a`，基于 `7cb5f65f` 加冻结的非线性精度源码差异；完整生产 source closure 与各请求/输出/分析 SHA 见 [alignment-followup.json](alignment-followup.json)。六个 request 的 bytes SHA 均与原请求相同。复用同一实际 Spectre raw 与冻结 checker `a9da685e…`，不改变物理预算、anchors、缺行义务或原生时刻，不作插值。

| 配置 | 同点行数 | 新 EVAS 解析最大 z / amp 误差 | 与实际 Spectre 最大 amp 差 | 完整有限对齐 |
| --- | ---: | --- | --- | --- |
| nonlinear baseline | 298 | 6.661e-15 V / 6.662e-11 V | .009488 V | 超物理预算 |
| nonlinear tolerance-only | 2116 | 1.110e-16 V / 1.819e-12 V | .0003061 V | 通过 |
| nonlinear step-only | 1029 | 1.110e-16 V / 1.819e-12 V | .0006059 V | 缺 exact .125/.25/.75 anchors |
| event baseline | 359 | 1.110e-16 V / 1.819e-12 V | .011689 V | 超物理预算 |
| event tolerance-only | 2213 | 1.110e-16 V / 1.819e-12 V | .0005044 V | 通过 |
| event step-only | 1030 | 1.110e-16 V / 1.819e-12 V | .0011649 V | 超物理预算且缺同样 anchors |

六档均完成，所有原生行精确配对且未配对行数为零。两个 step-only 档的 EVAS 波形误差符合，但完整 checker 仍因缺 exact anchors 不通过。三个 event 档均在 .5s 记录一次 timer，状态从 `[a,n]=[1,0]` 到 `[2,1]`；count 从 0 到 1 的原生括定仍为 `[.4999999999,.5]`。本轮额外保留 Fraction 对 binary64 原生时间的独立有理答案误差，冻结 checker 的原判据单独报告。

本批是 4 次新本地数值调用、2 份同 kernel 已成功严格请求收据复用，0 次版本查询、0 次远程调用、0 次自动重试。四次新调用串行且各强制 90s，最长约 14.37s。复用两份收据原 timeout 为 120s，没有记录 elapsed，不能改记为强制 90s。本地 raw 与新分析保存在 ignored `worktrees/transient-accuracy-control/runs/spectre-alignment-20261007/accuracy/alignment-followup-{raw,analysis}/`；旧失败、旧 summary 与原 Spectre 输出均未覆盖。

该检查点消除了这两个严格原请求的认证拒绝；当时等价 direct u/y 与耦合状态的严格编码仍显式 `waveform_accuracy` 拒绝，不能扩写为全部等价编码已对齐。Astra 与实际 Claude CLI/GLM-5.3 已完成独立审查。GLM 的 TwoSum 下溢证明疑虑经原始论文、精确有理数边界测试及 Astra 复核关闭；生产数值函数未因此改动。最终发布与 CI 状态另在 PR 记录。

## 前一批身份、失败与计数（不包含本轮追加）

最终 accuracy 来源 `1bea62cde6ff1b1b4eb0cf9aa6fd4822fd8a596c`，kernel SHA `b347f86ef2915f5ce19f39bdaa59882c0dd1c1b59b15b375e88d34f52972817b`。六请求与原请求逐字同 SHA。旧 accuracy 来源 `3f0c9292`、kernel `1676e21d…` 的结果全部保留；旧 event baseline 的拒绝没有覆盖。VCO 来源 `b781af77`、kernel `9909791c…` 保持不变，完整身份见 evidence 指针。

Spectre 实际新增 8 次数值调用、1 次版本预检；EVAS 原批 8 次、VCO 域内诊断 1 次、最终 accuracy 重放 6 次，共 15 次数值调用，版本查询共 9 次。旧 baseline raw 复用不增加调用，没有自动数值重试。

r2 packaging/import failure 为 0 数值/0 版本；本地 AS preexec control failure 也是 0/0。缺输出目录导致的首次 collection failure 属传输失败，单列保留。r3 外层 operator 确认清理完成；远端原目录保留。远端限制为串行、每次 90s、4GiB、单 CPU、32MiB/文件及 256MiB/条件轮询上限；最大 raw 11,700,927 字节。最终本地可证约束是串行与每次 90s，不宣称远端内存/CPU限制已在 macOS 强制。

## 复核入口

```sh
python3 -B -m unittest discover -s experiments/backends/transient-accuracy -p 'test_*.py' -v
python3 -B experiments/backends/transient-accuracy/analyze.py OBSERVATION.json --model nonlinear --output NEW_ANALYSIS.json
# model 也可选择 event-continuation 或 vco
```

11 项 numerical calibration 和 4 项 SI adapter calibration 均通过，覆盖初值、符号/频率、增益、缺行、重复行、非有限值、事件缺失/多余/错时、continuation 和 wrap 普通误差。checker 不执行后端，不调整预算。

raw 根目录内 `analysis-r3/SUMMARY.json` 是 Spectre 独立判据与 actual effective；`paired-analysis-r3/WITH-DIAGNOSTIC-SUMMARY.json` 是旧完整尝试与 VCO 域内诊断；`paired-analysis-final-accuracy/SUMMARY.json` 是最终六请求。`ACTUAL_R3_RESULTS_MANIFEST.json` 保留旧草稿身份，错误的“3 完整通过”只在新文档中纠正。原 `CHECKER_MANIFEST.json` 也绑定旧 README；本 README 是新文档身份，numerical checker 字节不变。

数值生产修订为 `a911ec9a`。实测kernel仍绑定原冻结源码；随后三行模块注释和一个私有测试的增量单独记录，没有将其冒称为旧执行的同步身份。两条生产修复在临时源码快照合并后，60项联合公共回归通过；三份文档/生成索引冲突保留，尚未正式整合。

## 孤立单位方程的投影修复

后续诊断发现同一数学模型仅将输出端口 y 改为 a，就能改变严格请求的认证结果。原因是区间消元优先选择大系数主元，给本来精确的 z=w、y=10000z−5000 关系引入倒数舍入包围。现在仅在当前未知量系数为精确±1、其余待消未知量系数全部为0时优先使用该孤立方程；其他情况保持原来的最大幅值主元策略。区间右端和最终电压预算继续保留；不宣称一般稠密或病态系统与所有写法均可认证。

原字节诊断请求11个全部完成，其中包含此前4个严格失败；逐点独立 Fraction 检查满足原请求预算。公开回归另检查事件、耦合、正负增益、端口改名及稀疏/稠密查询网格。原1e-20初始拒绝测试的 IC=1 经本修复可精确表示，故改用 binary64 IC=.3 的独立不可表示初值，预算仍为1e-20；原1e-13累计历史拒绝保留。旧失败和新的正确拒绝阶段都有独立记录。

新内核又执行6个原始物理端口请求，与既有真实 Spectre raw 的7045个原时刻逐一配对。所有输出数值与前一候选完全一致，仍仅两个 tolerance-only 档通过完整有限合同；对应放大输出最大差0.306mV/0.504mV，原1mV预算不变。未新增这6个条件的Spectre运行，原baseline物理失败及step-only缺行/超预算仍保留。

精度公开回归9项、共享消费者回归178项及Rust测试163项通过（另1项忽略）；format和clippy通过。共享回归中的奇异DAE负例只断言KernelError，未保留异常类别，不能据此声称数值认证拒绝；其标量求解路径与修改前相同的证明另有保留。

紧凑身份、原请求重放、RED/GREEN与本地证据指针见 [projection-followup.json](projection-followup.json)。一次本地重放脚本初版路径错误在启动内核前失败，0数值调用；修正脚本另建输出目录，旧stderr保留。原alignment-followup.json是前一冻结身份，未被重写。独立审查及最终检查由PR记录，尚未合并。
