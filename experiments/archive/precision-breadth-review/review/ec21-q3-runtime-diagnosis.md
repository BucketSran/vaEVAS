# EC21 Q3 v2→v3 超时回退：只读初步归因

EC21-v1--Q3 的实际执行从 v2 waveform_available（89.84979362413287 s）变为 v3 runtime_timeout（90.01653360016644 s，SIGTERM/-15）。这是需要保留的功能完成回退；不能被其他槽净成功数掩盖。当前证据确认它已经非常接近原 90 s 限额，但不能确定是新代码、编译布局、运行时竞争还是一次波动把它推过上限。没有提高限额、改变观察点或选择结果；本诊断没有本地/远端内核执行，也未修改 tracked 源码。

## 原执行与冻结请求

两版路径分别为 `batch-v2/collected/composition-evas-part2/outputs/composition-evas-part2/runs/EC21-v1--Q3` 与 `batch-v3/collected/composition-evas-part2/outputs/composition-evas-part2/runs/EC21-v1--Q3`。执行来源逐文件核验由 Astra 独立完成，保留在 `review/astra-ec21-runtime-identities.json`；本报告的独立源码/请求核对在 `review/ec21-q3-runtime-source-evidence.json`。

| 原槽 | v2 stage耗时/s | v3 stage耗时/s | v2/v3完成情况 | accepted steps |
|---|---:|---:|---|---:|
| Q1 | 77.64654913172126 | 82.92018240131438 | 均有waveform | 两版20048 |
| Q2 | 77.82855626381934 | 81.7656090632081 | 均有waveform | 两版20272 |
| Q3 | 89.84979362413287 | 90.01653360016644 | 有waveform→timeout | 旧22064，新无partial receipt |

上述是每版本/每档一个实际 stage 观测，不是可报告一般性能倍数的交替重复实验。Q1/Q2 新旧 program.json、raw-response.json、waveform.csv 字节完全相同，discarded_trials 都为0；这证明这些完成请求的结果与工作计数没有变，不证明执行时间分布相同。两版日志均0 bytes；Q3 timeout 前没有 raw-response、内部profile或进度计数，无法知道杀进程时的具体步骤。stage 包含 Python worker 的前端编译、内核调用及结果序列化，不能把全段耗时等同某个 Rust 函数。

内核 v2 SHA256 `a91e466a34136abb5119c61a398c05c4499258ac5c98539e673035c6f85504d3`，source `5f73f5016bb44808549ddfbf9b685bc192f2b2d7`；v3 内核 `ae8e012c97abc166b33dbb2b0ccd7f9ed4a1d28543d2e1bd1c1f083c47fbf602`，source `519d5e2805c40f2534a781e7dce4b78fbfde01b9`（完整身份在 Astra JSON）。两版 cargo/rustc 版本、实际编译器 binary hash 与 RUSTC env 相同，build/controller driver身份不同；这不保证整个运行环境、频率或竞争相同。stage 都明确 CPU affinity 0、1线程、4 GiB address-space、32 MiB file、90 s 上限，未发现请求上限变化。

Q3 以下八个文件逐字节相同：dut.va、request.json、program.json、condition.json、requested_settings.json、requested_times.json、observation_plan.json、INPUT_IDENTITY.json。DUT SHA256 `6f9fea30bf233070f3b76613879de4f6ed9e80a3f0c0f2192abeeeb9cee8ef8e`；IR `b2f4ac5deab35d9562669d44c41477e446c745e3e8696c78bcf49da89d6c2d81`；request `a0c1e404b35156bf6a86eb03238b077e8169021040759681644134920914d16a`。原20049输出点没有减少。max_step=T/2048=4.656612873077393e-10 s，reltol=1e-10，vabstol=1e-14 V，stop=T=9.5367431640625e-7 s。

## 模型实际进入的路径

模型是一个非线性积分反馈：`V(y)<+idt(q*V(y)*V(y)/T,0.75)`。三个事件状态都是标量 next/q/n0，两个 timer 分别在 T/8 更新 held next 到3T/8、在 next 把q改为-1并计数。没有事件数组、sin、idtmod，也没有物理/生成输入PWL。独立模型数学：u=t/T，switch前 y=1/(4/3-u)，在u=3/8达到24/23；之后 y=1/(23/24+u-3/8)，u=1时为12/19。整个原区间分母为正，没有有限时发散可解释 timeout。

`git diff 5f73f501 519d5e28 -- evas/rust_core/src evas/src` 只有 continuous.rs、idtmod.rs、operators.rs、transient.rs 四个生产文件。events.rs/事件数组准入、非线性积分模块、调度语义、Python frontend/worker 和 Cargo依赖没有这个版本间源码变化。own-state array 更改不在这次差分，且模型本身无数组；不能把 EC21 timeout 归于该准入规则。

`Continuous::new_until`（continuous_runtime.rs:168）检测该积分输入含非affine乘积，直接选 NonlinearContinuous；不会进入 LinearContinuous::new。因此 F14 新 `continuous::build_segments` 非零物理PWL斜率分支不可达。nonlinear_dynamics.rs 的原 source endpoint差商/传播逻辑未改变；此模型sources为0，差商向量为空。无 sin，F20 Taylor余项分支不可达；无 IdtMod，exact Curve 认证求值也不可达。

新增 lazy wrapper 是唯一必经差分：transient.rs:288 的 prepare_root_window 先执行 ordinary impl，每个普通 history candidate经过它。impl开始/返回前调用 Operators::refine_ordinary_phase；该模型只有一个 Runtime::Continuous条目，这两次扫描不建立证书、不更改该条目。普通候选仍执行与旧版同样的advance/evaluation/settlement/observed_after/advanced_until/replay。静态上新增的函数边界、match与两次扫描可带来开销或影响release编译布局，但没有计时证据可把几秒差异归因于它。

特殊负路径仍需区分：若 original同刻最终voltage certificate出现特定waveform_accuracy，wrapper会在point、无events/fired roots条件下从accepted frame完整重复impl，即使模型无IdtMod。该模型此开关不能改变任何代表值/界，因而重跑不会把相同失败变为成功；但可增加终止前的重复工作。ordinary调用处（transient.rs:979）对错误直接传播，不是adaptive discard后继续，故 discarded_trials=0不能单独证明从没重试。Q1/Q2完整结果相等且均完成不支持“精确相位求值变慢”说法；Q3没有错误或partial trace，不能静态判定最后是否进入负路径。

模型原20049 dense observation已要求许多非线性history observation与闭合/复制。非线性传播的solver_points分段、suffix clone/refinement成本在旧版也存在（nonlinear_dynamics.rs:1235起），v2 Q1/Q2已约78s、Q3约90s，说明原工作量本来大。它是否是主要耗时、是否存在更深的复杂度问题，须profile而不是根据点数或代码外观下结论。

## 最小后续诊断建议

需要本地固定原request的配对诊断，当前只读材料不足以决定补丁。先由root确认诊断资源，使用原八个冻结文件、20049点与原90s终止边界；分别从固定5f73f501/519d5e28构建同release mode、同Rust工具链，用同hardware/core、不停无关进程。记录构建身份、uptime/竞争进程及两版原Q3功能完成/timeout；Q1可作为两版完成且byte-equal的控制。原waveform不替代原严格分析。

如需要性能归因，按 benchmark-checklist 做至少5次旧/新交替原程序执行；若成本只允许单次有界功能复验，只报告 completion/timeout复验，不能报告普遍性能差异。profile单独运行，不混入计时样本，可使用已有诊断stage计数观察history.clone/controller.prepare_candidate/history.nonlinear_propagate；trace应保持独立身份，原失败保留。若Q3仍90s超时无trace，不靠提高科学执行限额伪造通过；另行授权的诊断可收集外部进程栈/采样，或在私有instrumented snapshot数retry门实际命中，不能回写原raw。

仅在配对证据确认新wrapper开销/无phase负路径确实相关后，才能评估最小实现方案。当前不建议基于单次边界超时改scheduler、提高资源、跳观察点、放宽预算或撤销其他真实数值修复。v3这个EC21 Q3仍是原失败，结论保持未知。


本轮保留 [#119](https://github.com/BucketSran/vaEVAS/issues/119) 当前义务：“一般消费者预算分配、累计历史误差，以及截断、输入、舍入、包围保守性和资源限制的区分”。EC21 Q3 的实际 X 当前只证明原 90s 资源边界内没有完成，未证明截断/输入/舍入或包围误差失败，亦未证明根因仅为资源规模或仅为新wrapper。无phase retry负路径没有精度收益，但其本次实际命中及耗时未知；后续同环境交替与独立工作计数用于区分这些原因。本轮不关闭该义务、不解决回退、不声称性能不变；issue 更新由root统一处理。
