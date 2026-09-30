# 六路候选的复审记录

主分支比较基线：`508f5b924360a48c66b569a1719157a883d1db9f`。
本页记录 2026-09-30 的实际复审；候选仍在本地，未发布新 PR、合并 main 或发布 tag。
原联合检查点及其 30/31 结果保留在 [README](README.md)，不将新专项结果改写为新联合成绩。

## 首批候选：多事件写者

分支 `feat/evas-multiple-event-writers`，head `87491e8`，生产代码固定于
`144d8b0d90f4812fa4924597bcb0c1fa1337f20e`；末次提交只整理收据中的本地路径。
比较 `508f5b9..87491e8`。IR 仍为 9，无新增运行时依赖。

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

上述相对链接指联合检查点文件，阅读最新生产实现时须切到 `feat/evas-multiple-event-writers`
的固定 head；联合检查点尚未同步这一轮修复。最终差异涉及 9 个文件；生产逻辑仅
`events.rs` 与 `settlement.rs`，合计新增 27 行、删除 9 行，其余为测试、契约和紧凑收据。

### 验证与结论

子线程报告：86 项相关 Python、58 项 Rust、构建及格式检查通过。
主线程在固定生产 head 上另重跑 7 项 writer Python 与 1 项实际 Frame rollback Rust，均通过；
核对内核、checker、worker、两档 DUT/condition/settings/waveform 哈希，与新 V3 收据全部一致。

原 V3 的冻结输入、两档设置和独立 checker 未改；两档均 `observations_within_targets`，
分别 4,001 / 40,001 个观测点，最大观测电压误差约 `2.04e-14 / 2.12e-14 V`。
收据位于候选分支 `experiments/pr14-pr15-validation/results/event-writers-v3-branch.json`。
运行真实发生在旧 head 加未提交修复上，运行后修复提交为 `144d8b0`；收据保留当时的 dirty 身份，
不冒充 clean commit 执行。raw 与冻结输入仍 local-only，正式资格 I；本轮没有新 Spectre 执行或性能测量。

结论：该受限写者策略、调用位置与失败完整性没有新的阻塞发现，可先交用户 review。
最终交付仍需用户审阅和实际目标 main 的依赖同步；本结论不授权合并。

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
子线程继续设计有明确适用域的验证区间方法；名义 Newton 收敛、原关系区间残差和一阶灵敏度不能单独代替该证明。
这项暂不建议合并并宣称总电压精度已补齐。

## 其他候选与顺序

- analog 条件：固定 `134280e`，已有独立 Fraction 分支/顺序/结构依赖与原 V1 两档正向证据。
- 一阶 laplace：固定 `4389640`，已有带余项的指数界、原系数/时间区间与原 C2/V6 四次正向证据。
- phase：`11f49d2`，新增原相位 wrap 侧的精确符号证书；专项 D2 constant/chirp 两档均观测达标。
  near-wrap 测试已改为从原 binary64 常数作 Fraction 积分/modulo，half-ulp 错侧代表值仍保守拒绝。
  这不是联合 31/31 的新证据。

先 review 多事件写者；idt 以 `466d63c` 的修复与实际父依赖接续。analog 条件、一阶滤波和相位
分别保留独立范围，交付时统一共享 IR/前端接口并补受影响组合验证，不把临时联合分支直接当成一个大 PR。
