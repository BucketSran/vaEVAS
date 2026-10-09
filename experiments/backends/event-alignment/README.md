# Spectre 驱动的事件组合对照

[固定参考精度流程 v1](reference-precision.md)提供本地冻结、实际设置/原生输出读回
和预先声明的档位稳定性分析；不会派发后端或覆盖旧参考判决。

当前候选的后续[精确根证明与组合消费者](consumer-precision.md)修复了无关滤波状态
破坏积分根证明的问题，并补充实际 Spectre 对照与同一 Controller 回退检查。
原 C1、VCO 和 #79 严格边界义务仍未关闭。

后续[单因素容差收敛与直接配对](convergence.md)补充 14 份实际 Spectre 波形，
并用真实 C1 反例校准独立 P 与直接一致性的区别。D1/D2 的 3,628 个原生点在
分别选定的控制下有限一致；C1 阶段差、M1 差异与过严 EVAS 请求拒绝仍保留。
本页以下为原检查点结果，不用新结果覆盖旧判决。

本检查点将 PR100、PR101 与 PR106 的代码合成 EVAS 0.14 / IR18 候选，
冻结工程模型后实际运行 Spectre，修复了直接输入 `cross` 的物理时刻证明丢失。
运行代码对应 `cc8d8b0c08960bc71cbc60e098239ab949fe3165`；后续补充的测试、IR 格式整理与文档不改变该生产路径。
这是开发证据，不是独立论文评价集，也不代表这些父 PR 已合并或全部满足合并条件。

## 修复的行为

C1 用上升电压触发采样，再将采样值送入 `transition`。
集成基线 `e2832326` 在名义 1.4 µs 查询点返回
`event_resolution: output query cannot certify its physical event phase`。
该根由原始 binary64 输入确定，精确值为 `Fraction(.7)*Fraction(6e-6)/3`，
略晚于查询时刻。原路径对端点 guard 做浮点减法后，丢失了足够的来源信息。

候选从原始 PWL 源构造有预算的有理数根证书。
证书必须与原区间端点、根包围和分段一致，才能用于根排序、时钟比较和查询阶段。
生成轨迹、内部节点或耗尽证明预算的请求仍走原保守路径。
原 `ttol`、表达式预算和输出预算都不变。详见[事件数学](../../../evas/docs/math/events.md#原始输入的事件时刻证书)。

本次直接修改的是来源与事件时刻在多个消费者间的传递。
`timer`、`transition` 和积分被纳入组合验证；这不表示三个算子均换了实现。

## 冻结范围与实际结果

[资产及完整判据](../../../evas/validation/event_alignment/README.md)在首次后端执行前冻结。
电压预算为 1 µV，采样值与 stamp 为 0.1 µV，普通事件时间为 1 ps。
N1 的 cross 时间预算为 0.1 ps。每次运行的全部观察必须允许同一组事件时刻，
禁止逐点重选事件时间来取得通过。

| 模型 | 检查的组合 | 集成基线 EVAS | 修复后 EVAS | Spectre base / tight |
| --- | --- | --- | --- | --- |
| T1 | timer、延迟、完整上升与下降沿 | P | P | P / P |
| T2 | 延迟队列中的短脉冲与中断边沿 | P | P | P / P |
| C1 | cross、输入采样、transition、阶段查询 | 拒绝 | P | P / P |
| C2 | timer 起升、cross 中断采样与反向边沿 | P | P | P / P |
| M1 | 同一事件目标的 transition 与积分面积 | P | P | F / P |
| H1 | held timer 改期、禁用与旧日程撤销 | P | P | P / P |
| N1，独立诊断 | 相隔 5 ps 的三来源事件 | P | P | P / P |

六个工程模型的 EVAS 通过数从 5/6 变为 6/6，N1 为 1/1。
Spectre 工程配置为 11/12，N1 为 2/2。
另做 C1 的负向 guard 和等价 OR 两种写法，EVAS 为 2/2，Spectre 两配置合计 4/4。
它们不加入原七例分母。所有 18 份 Spectre deck 均可由公开的准备工具逐字节重建。

P 表示满足冻结的有限工程判据，不能代替逐点相同或连续时间误差证明。
以下差异在[行为收据](evidence/behavior.json)中完整保留：

- C1 在名义 1.4 µs 点，EVAS 为事件前态，Spectre 为事件后态。
  两档各有一个窗口内计数差；stamp 输出从 −1 V 跳到约 1.4 V，产生 2.4 V 的全量最大差。
  窗口外计数一致。等价写法仍保留相应阶段差。
- M1-base 的 Spectre 独立误差为 1.1742481131094962 µV，超过 1 µV 预算，判 F。
  M1-tight 为 0.33185963151899243 µV，判 P。
  两后端直接电压最大差分别约 2 µV 和 0.996981711 µV，这与独立数学误差是不同指标。
- 两档 14 组共有 2,252 个要求观察点。按原冻结 1 fs 表示允许差，每点恰有一个原生输出候选；
  没有插值或最近点挑选。最大表示偏差约 0.5 fs。
  严格 binary64 时间键的未匹配计数仍保留，不能把表示匹配当作精确物理同刻。

Spectre 为 21.1.0.509.isr12，方法均为 `traponly`。
base 的 reltol/vabstol/iabstol/maxstep 为 `1e-9 / 1e-11 / 1e-15 / 125 ns`；
tight 为 `1e-10 / 1e-12 / 1e-16 / 31.25 ns`。
EVAS 使用 `reltol=1e-8, vabstol=1e-6, max_step=125 ns`。
双方参数不是数值相等的控制旋钮，结果按同一外部工程预算判断。
两档同时改变容差和步长，因此只证明配置间稳定性，不能独立归因某个参数。

原设置读取器因为缺少 `requested_settings.json` 报 I，原文件保持不变。
[HEADER 读回](evidence/settings-readback.json)另用 Decimal 核对实际 PSF 中的设置和方法，
18 组均在打印精度内相符。这不证明内部设置逐位相等，也不补足严格终点资格。

## 同机完整请求成本

Intel Xeon Gold 6326，同一服务器，release 构建，每例每侧五次交替运行。
Spectre 使用 tight，EVAS 使用原设置；先满足同一工程判据，再纳入计时。

| 模型 | EVAS 中位数，最小–最大 / s | Spectre 中位数，最小–最大 / s |
| --- | --- | --- |
| T1 | 0.299265，0.293664–0.299812 | 2.414678，2.372831–2.586646 |
| M1 | 0.360116，0.353693–0.366563 | 2.578823，2.410393–2.801056 |
| H1 | 0.281973，0.280174–0.284960 | 2.786421，2.470666–2.853829 |
| C1 | 0.285094，0.282201–0.305943 | 2.322219，2.286702–2.654052 |

正式 40/40 请求满足原判据；8 次暖机与 8 次独立剖析不计入中位数。
C1 的边界阶段差仍在，计时通过不表示逐点相同。
Spectre 正式请求复用了已核对的 AHDL 缓存。
初次性能批因 Python 文本编码错误在仿真前退出，零样本；失败记录保留，没有自动重试或删除失败样本。

计时包含新进程启动至完整输出闭合。EVAS 包含 Python 导入、VA 编译、release kernel 请求及 JSON 消费；
Spectre 包含环境初始化、启动与许可至 PSF 输出。独立 checker、PSF 规范化和搬存位于计时外。
两个批次源文件身份相同，各自 release binary hash 均记录；二进制字节不同，不能称同一二进制。

EVAS 在这四个小模型中每轮完整请求都更快。
但 Spectre 的 tran elapsed 不到完整 wall 的 1%，启动生命周期和许可影响很大。
EVAS 的 Python 导入和 kernel 等待也占相当部分。
现有剖析不足以定位 Rust CPU 热点或 Spectre 日志外的具体等待来源，
因此核心求解速度、长时域、大模型及一般吞吐结论仍为未确定。
不得拿 EVAS kernel transport wall 与 Spectre tran CPU 混算速度比。
逐次样本、身份、限制及剖析摘要见[性能收据](evidence/performance.json)。
第一性能批的初次分析脚本未单独保存，随后有字段和说明调整，旧执行脚本身份不能恢复。
当前脚本已先冻结，再在新目录实际重分析原 30 个正式样本；数值结论全部复现，旧结果保持不变。
收据分别记录旧摘要来源和新重分析身份。C1 批原本已使用调整后的脚本执行。

## 审查与剩余缺口

完整 Rust 回归在最后收紧诊断断言前完成 208 项，另有 1 项原有 ignored。
source-v3 的映射 Python 回归为 178 项；最后的断言版本另重跑 18 项 Python 与 1 项 Rust，均通过。
这些测试范围重叠，不能相加。Clippy `-D warnings` 与全 workspace 格式检查通过。
集成基线此前完成 928 项 Python 回归，不能把该旧计数当作最终全套复跑。
检查器的 19 项正负校准与 PSF 规范化的 2 项检查通过。
后续独立审查增加了混合源根/固定 timer/held 改期的测试、原预算拒绝检查及回退检查。
最终补测和审查身份见[审查收据](evidence/review.json)。

Astra 独立复算了全部 2,252 个配对点，核对原 PSF token、来源与最终输出，并重跑 checker 校准。
实际 Claude CLI 的 GLM5.3 完成了源码审查；原报告提出的覆盖缺口促成上述补测。
模型审查不代替模拟器结果，也不使所有父 PR 自动可合并。

另一个极近簇开发诊断曾明确拒绝：PWL 从 0.1 升至 0.9，两个 cross 阈值为
0.5 与 0.5000000000000001，中间插入 `timer(0.5)`。
虽然精确物理顺序可证明，第一簇的浮点执行代表推进后会碰到下一簇的下界。
当前候选在原精确证书能排序下一事件时扩展相连簇，再验收每个原预算。
原请求已通过独立计数、相邻查询点及整批回退重试检查；未知内部根仍拒绝。
这一新增诊断的[原配置实际 Spectre 对照](mixed-cluster/README.md)取得 50/68 个原生行，
计数和电压均在原预算内；参考缺失三个亚 ULP 查询行，精确阶段覆盖仍为 I。
把 timer 改成相邻的 `0.5000000000000001` 得到的是另一个可接受结构，不能充当原诊断的修复。
原七例没有包含该亚 ULP 情况，其分母不变。

后续 [高精度事件日志与单因素控制](event-reference-controls.md)显示，C1 回调会随
观察网格变化，M1 收紧 timer 容差后仍有积分残差。原严格 F 均保留。

下一步应分别解决工程事件时间合同、极近簇日程可接受范围和严格边界约定。
PR100 的普通 VCO 相位分歧、PR79 的终点差异及更广连续/事件反馈仍需原专题证据，
本组 timer/transition/cross 模型不能消除这些问题。
PR102/103/104/106 在本候选中的有限组合回归可用，但若分别合并或变更父分支，
必须按其实际目标版本检查依赖和受影响证据。本检查点保留原 PR heads，不合并 main。

## 材料与复现

仓库内包含模型、card、独立 checker、校准、EVAS runner、PSF normalizer、
Spectre deck 准备器及精简收据。原始波形、完整进程日志、远端设置、review 响应与剖析是 local-only，
位于日常入口的 `runs/spectre-event-alignment-20261008/`。
收据记录 archive 和文件 hash；hash 不是下载地址，不构成公共完整复现。
[源清单](evidence/source-manifest.json)的 103 项已逐一对上运行代码提交 `cc8d8b0c`。
[资产冻结清单](assets-v2-manifest.json)的 17 项保持原字节；编码控制另在 `encodings/`。

从仓库根目录运行，下列命令使用新的输出目录：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
python3 -B experiments/backends/event-alignment/run_evas.py . \
  evas/validation/event_alignment runs/event-alignment-replay
python3 -B -m unittest discover -s evas/validation/event_alignment -p 'test_checker.py' -v
python3 -B -m unittest discover -s experiments/backends/event-alignment -p 'test_*.py' -v
python3 -B experiments/backends/event-alignment/prepare_spectre.py \
  evas/validation/event_alignment/C1 runs/event-alignment-spectre-C1
```

最后一条只写 deck，不启动 Spectre。执行方须提供合法可用的 Spectre 环境，
保存 `psfascii` 全部原生点与日志，再由 `normalize_psf.py` 和冻结 checker 判定。
本次远端采用串行、单线程、每次 90 秒、许可等待 30 秒、4 GiB 内存、32 MiB 单文件及
256 MiB 条件输出限制；条件总量由 supervisor 轮询限制，不能称硬容器配额。
性能比较还需沿用计时边界、暖机、交替顺序及完整输出验收，不能用普通 debug runner 耗时替代。

原 Spec B E3/E5 查询阶段拒绝的有界精确历史证书增量见
[常数积分历史重放](exact-history.md)。原严格 Spectre 差异与 stop 覆盖 I 继续保留；
此增量没有解决 C1、VCO 环回或 va07 stop=3 计数，PR #108 继续 draft。
