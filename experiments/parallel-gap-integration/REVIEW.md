# 六路候选的复审记录

主分支比较基线：`508f5b924360a48c66b569a1719157a883d1db9f`。
本页记录 2026-09-30 的实际复审；候选仍在本地，未发布新 PR、合并 main 或发布 tag。
原联合检查点及其 30/31 结果保留在 [README](README.md)，不将新专项结果改写为新联合成绩。

## 首批候选：多事件写者

分支 `feat/evas-multiple-event-writers`，head `bfaf8d3b2696a362f6209259ba520356485552fb`，生产代码固定于
`144d8b0d90f4812fa4924597bcb0c1fa1337f20e`；后两次提交只整理收据路径与主分支/候选能力登记。
比较 `508f5b9..bfaf8d3`。IR 仍为 9，无新增运行时依赖。

原先两个事件块只要可能写同一状态就被静态拒绝，导致正常的上下阈值迟滞也不能运行。
现在先认证候选批次的条件路径，再检查实际写集合。对状态 q 与批次 B：

```text
W(q,B) = { event block | its selected path actually assigns q }
accept the writer check iff |W(q,B)| <= 1 for every q
```

不同批次分别写 q 合法；同一块的顺序赋值仍属于一个写者。同批两个块写 q 则整批
`event_conflict`，即使写入值相同。没有按源码顺序决定跨块优先级。OR 的同块去重沿用已有实现。
此检查发生在候选求解和正式历史提交之前；已接受 Frame 作为试算起点，失败不会消费事件或修改历史。

跨块读取仍明确拒绝。复审发现 `q-q`、`0*q`、下溢系数可绕过非零系数检查，
`144d8b0` 已改用保留的结构依赖；前端与 raw IR 均有回归，同块顺序更新仍保留。

### Review 入口与范围

- [events.rs](../../evas/rust_core/src/events.rs)：潜在写者集合、结构读取拒绝、实际 Selection 写者检查。
- [settlement.rs](../../evas/rust_core/src/settlement.rs)：认证路径后、求解前的检查位置。
- [test_event_writers.py](../../evas/tests/test_event_writers.py)：迟滞、保持、实例排列、选中路径、相同值冲突与结构读取反例。
- [transient_condition_tests.rs](../../evas/rust_core/src/transient_condition_tests.rs)：实际 Frame 失败回退及 raw IR 拒绝。

阅读单项差异时切到 `feat/evas-multiple-event-writers` 的固定 head；下方临时联合版本
已同步这一轮修复，但包含其他未批准能力，不能作为这项 PR 的完整差异。单项最终差异涉及 9 个文件；生产逻辑仅
`events.rs` 与 `settlement.rs`，合计新增 27 行、删除 9 行，其余为测试、契约和紧凑收据。

### 验证与结论

子线程报告：86 项相关 Python、58 项 Rust、构建及格式检查通过。
主线程在固定生产 head 上另重跑 7 项 writer Python 与 1 项实际 Frame rollback Rust，均通过；
核对内核、checker、worker、两档 DUT/condition/settings/waveform 哈希，与新 V3 收据全部一致。

原 V3 的冻结输入、两档设置和独立 checker 未改；两档均 `observations_within_targets`，
分别 4,001 / 40,001 个观测点，最大观测电压误差约 `2.04e-14 / 2.12e-14 V`。
收据位于候选分支 `experiments/pr14-pr15-validation/results/event-writers-v3-branch.json`。
运行真实发生在旧 head 加未提交修复上，运行后修复提交为 `144d8b0`；收据保留当时的 dirty 身份，
不冒充 clean commit 执行。这份分支专项当时未新执行 Spectre；后续新对照见下节。
raw 与冻结输入仍 local-only，正式资格 I；未作性能测量。

结论：该受限写者策略、调用位置与失败完整性没有新的阻塞发现，可先交用户 review。
最终交付仍需用户审阅和实际目标 main 的依赖同步；本结论不授权合并。

### 后续补充：V3 与 Spectre 的新执行对照

`event-writers-spectre-20260930-01` 固定同一候选 `bfaf8d3`，干净工作树，内核 SHA256
`b3cf1d076325dea136ac806823f9f78d434f174b9199fd9d6a1ed8710cedcd83`。
原 V3 DUT、condition、两档 settings、Spectre 网表逐字节复制自原冻结输入；原 checker 未改。
本轮 EVAS 与 thu-sui 的 Spectre **21.1.0.509.isr12** 各新执行两次，共四次，未复用旧波形。
沿用原 Spectre runner，只将案例数、输出数断言与预算元数据缩减为 1 条件 / 2 次；
单线程、单 CPU，90 s/次、30 s license 等待上限。实际 stop、step、maxstep、method 与
reltol/vabstol/iabstol 均已从 Spectre 日志核对，全部匹配原请求。

| 档位 | EVAS / Spectre 点数 | 独立验收 | 平台误差 | 两波形最大插值差值 |
| --- | ---: | --- | ---: | ---: |
| 基础 | 4,001 / 4,006 | 两者均 observations_within_targets | 两者 0 V | 4.0000 mV |
| 细化 | 40,001 / 40,006 | 两者均 observations_within_targets | 两者 0 V | 0.65250 mV |

原独立答案中，两次迟滞更新的名义时刻为 1.375 / 3.375 μs；输出从 0.1 V 到 0.9 V，
边沿时长 50 ns。基础档从 Spectre 的输出 50% crossing 推算起点约晚 0.25 ns；
细化档约晚 0.03140 / 0.04078 ns。这些是输出边沿估计，不是直接读取内部事件时刻。
边沿斜率为 `0.8 V / 50 ns`，故 0.25 ns 位移对应约 4 mV 名义波形差值。
原合同允许事件起点晚至 0.5 ns，原 checker 用所有导出点检验是否存在共同允许事件历史；
不能把原电压目标理解为每个点都必须贴合名义零时间偏差波形。两者的共同历史检查均为 P，
正式观察资格仍为 I，未证明未观测时刻的误差。

结论限定为正常 V3 迟滞：平台与事件历史相容，边沿存在可解释且细化后减小的数值差异；
不能声称逐点一致、Spectre 出错、EVAS 普遍更准确或同刻多写语义已对齐。
本轮未新增同刻跨块实际写冲突的 Spectre 诊断、完整 31 矩阵或速度测量。

新收据见 [V3 对照](../pr14-pr15-validation/results/event-writers-spectre-v3.json)，
重分析入口为 [event_writer_compare.py](../pr14-pr15-validation/event_writer_compare.py)。
8 项原 checker 校准检查另通过。原始波形、远端清单、运行器快照及候选源码归档仅本地/thu-sui 保留，
不称为可公开下载的复现包。

## 继续处理的精度问题

### idt reset

复审在 `778a667` 确认：`1e16*q+q-1e16*q` 本应等于 q，却被合并系数舍入成零。
q 初值 1、t=2 归零、输入恒 1、IC=.25，原实现接受 `[.25,1.25,2.25,3.25]`，
正确应为 `[.25,.25,.25,1.25]`。`26164ce` 已保留原 reset 树并认证未合并 product-sum，
`7ecf652` 同步真正依赖的 event writer `144d8b0`。

但 `7ecf652` 仍有嵌套乘积反例：

```text
reset = (0.1*q)*0.1 - 0.010000000000000002*q
```

对 q=1，原 binary64 常数的精确实数解释为非零：
`Fraction(.1)^2-Fraction(.010000000000000002) = -1080863910568919/1298074214633706907132624082305024`。
主线程重现了同样的错误输出，原因是系数乘法先舍入、随后把舍入系数当作精确值认证。
`466d63c3269aaa0dfbf8580e776cdc0541062ceb` 已补每次系数乘积的 exact 资格检查，
常数合并也要求可证明精确；否则从原树作区间回退，跨零明确拒绝。
主线程重跑 source/raw IR 的两类相消与嵌套乘积共 4 项回归，均通过。
子线程另报告 274 项 Python、61 项 Rust，以及 D1 free/reset 两档四次专项均观测达标。
原 `1e16*q+q-1e16*q` 可正确运行，嵌套非精确系数的反例会保守拒绝。
该有界实现可以作为多事件写者后的第二项 review 候选；不同于支持任意 reset 代数化简。

### 无状态瞬态的反馈放大

`0063f82` 补了 exact-PWL 输入区间下的支路残差检查，能拒绝原 `y=1e16*(u-1)` 反例，
但残差不等于输出误差。主线程在该 head 又重现：

```text
y = a*y + (u-1), a=0.99999999999999
u: (0,1), (3,nextafter(1,+infinity)); observe t=1
vabstol=1e-12, reltol=0
```

精确有理数答案为
`(Fraction(nextafter(1,+inf))-1)/3/(1-Fraction(a)) = 1/135 V`，
内核却接受 y=0。输入残差很小，但 `(1-a)^-1` 将其放大约 `1e14` 倍。
`4a903d4` 的固定 Jacobian 灵敏度检查已拒绝这个反馈反例，但固定点导数不能独自给出
非线性根移动的严格上界，普通浮点逆与误差累加也不自动成为可靠包络。
名义 Newton 收敛、原关系区间残差和一阶灵敏度不能单独代替根误差的证明。

最终候选固定于 `227c77cbc29f35584ea7a7fe7fa686ebb65543d3`：非点输入使用 square Krawczyk
预算盒，浮点逆只作预条件器，要求区间映射严格内含盒且收缩。复审提出的 `X-x` 减法、
范数累加已采用外扩区间运算；残差与 Jacobian 从保存的 `Equation.original_rhs` 求值。
没有放宽重复 affine terms 的原 invalid-IR 规则；相消反例使用合法原始 Add 树，另保留非法重复项拒绝回归。

主线程在最终候选的实际内核上重跑上面的 `1/135 V` 反馈反例，结果为 `waveform_accuracy` 拒绝。
子线程报告 41 项相关 Python 通过；外扩与原树修复后另有 57 项 Rust，以及 V7 两条件两档共四次正向回放。
最终恢复 IR 校验的提交另重跑合法 Add 树与重复项拒绝测试。

此项可以进入单独 review，不能宣称总电压精度已补齐：非点输入证书仅限无事件/历史/状态、
方阵、单 origin 的既有多项式路径；点输入仍只有原关系区间残差验收，不提供根包络或前向误差证明。
它尚未合入下方临时组合版本，专项证据不能替代组合后的检查。

## 更新后的临时组合检查

联合运行时固定于 `fc106879e40e993fa5fe41fd07151f8f96a8d358` / IR14，
内核 SHA256 `77e740300eb43992d5978f5e7c6dbab5217efa3d9282c18de9c77a981f941581`。
合入 event writer `87491e8`、reset `466d63c`、phase `11f49d2`，未合入上述非线性精度修复。
解决共享接口时保留相位 helper，给 reset 判定的 `Select` 明确拒绝；raw phase 边界证书
遇到带 reset 的 idt 必须退出，不能无视其释放历史。

58 项相关 Python（含 8 项跨能力组合）、75 项 Rust、构建及 all-targets warnings-as-errors
检查通过。详细范围及 Clippy 工具链组件缺失记录于 [checks](results/review-checks.json)；
本轮没有把它写成 Clippy 通过，也没有重复完整 Python suite。

原 V3、D1 free/reset、D2 constant/chirp 五条件、两档共 10 次新本地请求、220,010 个导出观测点均
`observations_within_targets`，仍复用原 INPUT_MANIFEST 与独立 checker。
新 [专项收据](results/review-affected.json) 独立保存实际执行 commit、干净状态、内核和源码哈希、
输入/设置/波形身份；raw local-only。这不是全矩阵 31/31 或连续时间精度的证明。

## 其他候选与顺序

- analog 条件：固定 `134280e`，已有独立 Fraction 分支/顺序/结构依赖与原 V1 两档正向证据。
- 一阶 laplace：固定 `4389640`，已有带余项的指数界、原系数/时间区间与原 C2/V6 四次正向证据。
- phase：`11f49d2`，新增原相位 wrap 侧的精确符号证书；专项 D2 constant/chirp 两档均观测达标。
  near-wrap 测试已改为从原 binary64 常数作 Fraction 积分/modulo，half-ulp 错侧代表值仍保守拒绝。
  这不是联合 31/31 的新证据。

先 review 多事件写者；idt 以 `466d63c` 的修复与实际父依赖接续。analog 条件、一阶滤波和相位
分别保留独立范围，交付时统一共享 IR/前端接口并补受影响组合验证，不把临时联合分支直接当成一个大 PR。
