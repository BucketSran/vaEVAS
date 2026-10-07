# 瞬态精度与 VCO 发展对照

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
