# 下一轮实际取证请求

本轮优先 VCO 与 flash；power 修正基线先重校。DAC v2 CPU 未改善，SC 差异约 2.4%，
均保留候选并待诊断，不因凑数写正式题。当前 task_count 仍为 0。

## 功能与来源

本次 oracle 加了公开输出 delay 和有限 transition 的 25/50/75% 探针；power 相对
实际 50% 边沿检查 25/75% 电压，另有原独立绝对边沿容差。VCO 恒频两个条件逐相邻
时间点检查解析相位前进不得超过 1/64+1e-10 周期，保证 64 points/cycle 的分辨率。
变频条件保留解析波形误差合同。v2 原始实际波形回放 29/30 过，失败仍是旧 power
基线浮点资格计时；不把回放当新 VA 执行。重复结果使用新 probe oracle。

power 新 baseline 在时间比较加 1e-6*poll_period 数值裕量（默认 1 fs），以免精确
到期轮询由于浮点相减而多等 1 ns。轮询周期、实际工作、边沿容差没有变。它是修复
合法基线的数值边界，须新 actual 三条件全过后才能测优化收益。

## 独立诊断，不纳入最终计时

VCO 的 baseline 低频工作 20 us，fmax=400 MHz、64 points/cycle 的上限对应 512000
步；实际 accepted=512008。reference 完成同样 159.2 周期，64*159.2=10188.8，实际
accepted=10203。高频负控 baseline5134/reference4982 步，差异小。这些 native统计
加独立相位/分辨率判据定位了最高频率 bound_step 约束。可另做一次 per-process CPU/
系统负载采样；不要将采样运行计时纳入五对。

flash 原始两侧 accepted 均152093、10000转换，v1/v2 CPU有同方向差异，但尚无重复
判定。profile 运行全部使用 `probes/optimize-flash-thresholds` 的强化 oracle，源码：

- `flash_thresholds/profile/baseline.va` 和 `reference.va`：记录真实 callback、comparison、
  sample 保存状态计数；final_step 输出有独特 profile 前缀。诊断日志单独留存，这些带
  `$strobe` 源码不得通过正式性能 source guard，也不参与计时。
- `flash_thresholds/profile/sampled_linear_scan.va`：仅移动扫描到采样事件。
- `flash_thresholds/profile/continuous_binary_search.va`：仅改变解码搜索方法。

两消融均无计数，不改变规定实际工作；功能全过之后的单次 native CPU 只用于解释
重复求值/算法成本份额。诊断强度不足时保留未知，不能从源码直接宣布热点占比。

## 至少五对交替执行

VCO用 `low-band-end-to-end`，flash用 `bank-throughput`。其它功能条件先单独全过。
原始 baseline/reference 各一次热身，另做 A B A B A B A B A B，固定同机/Spectre版本/
网表/容差/线程设置，禁止 A/B 同时运行。可保持其它全局作业在既定资源限制内，但
必须记录并发/负载，若漂移影响计时，再在安静窗口复测。完整案例与源码路径均在
相应 REQUEST 和 optimization.json；probe 位于 `probes/optimize-{vco-step,flash-thresholds}`。

每个 job 必须功能通过、完整覆盖终点、独立确认周期/转换次数，统计使用原生
spectre.log intrinsic tran CPU/elapsed 和 accepted/rejected；拒绝步骤未报告记 unknown。
独立记录 process elapsed；compile/cache/license/queue/network 不混入求解 intrinsic
CPU。记录 source/netlist/checker/runtime/Spectre身份与归档哈希。fresh sandbox 编译若
无法缓存，明确生产 wrapper 的冷编译状态，保留编译分项，不假称热缓存。

正式性能 source guard 禁止 active 日志输出/流程控制 system tasks，以防伪造原生
统计；独立检查 process returncode 与真实捕获流的致命求解诊断；目前公共runtime将stdout/
stderr合并，必须标记merged并检查整份流，不能假称存在独立stderr。只从 native
spectre.log 读取数字。默认 aggregate audit elapsed 曾重复CPU，不能充当墙钟。

给出各侧 CPU/elapsed、steps 中位数与范围，逐对比率与时间走势。CPU差距小于变动
视为无可测改善。当前不设达标阈值，必须等实际五对和诊断证据。VCO可将减少实际
accepted步数作为成本指标，同时报告端到端耗时；不能用PSF点数代替步数。
