# EVAS 联合交付与验证

本页按执行身份保存各阶段的联合验证。当前 EVAS 0.12.2 / IR16 已由
[PR33](https://github.com/BucketSran/vaEVAS/pull/33) 合并到 `main` `b4921ca`；版本 tag 尚未发布。
数学、试算生命周期和拒绝范围分别由[能力表](../../evas/docs/CAPABILITIES.md)、
[手册](../../evas/docs/README.md)维护。旧收据中的未提交/未合并状态描述执行当时的快照。

## 当前证据

运行时 `8618339` 和审查头 `18063c9` 已由 PR33 合并。以下是已执行并绑定该源码的证据，
本次文档整理没有新执行；数学与支持边界见[事件截止点](../../evas/docs/CONTINUOUS.md#known-event-horizons)。

| 收据 | 实际执行与限制 |
| --- | --- |
| [截止点开发检查及合并前审查](results/event-horizon-checks.json) | 506 Python、124 Rust 通过，1 个旧性能探针 ignored；locked build、Clippy、格式通过。9 个新增 Python 方法、2 个 Rust 私有测试及 3 组解析审查探针不增加原矩阵分母 |
| 同收据的原 31×2 矩阵 | 两档各 31/31；62 份 CSV 与 PR32 基线逐字节一致，输入、检查器和数值设置不变，仅引擎版本元数据更新 |
| [前一共同闭包的观察/依赖修复](results/lifecycle-observation-review-fixes.json) | PR32 被测运行时 `1b99c33`；与当时源码快照一致，执行时的状态字段保留 |

最终内核 SHA256：`d66cb9b0622b744cc49f38e0fcc23d3f98ffc55c60fbc863a3f2f492beb0205e`。
收据保存执行时快照与后续审查/集成记录；`status` 不是当前 PR 状态。
固定 raw 清单、原始失败和补充探针均为 **仅本地保留**，工作区清理后通过本地归档路径映射取回。
正式 DVS 资格仍 **I**；没有新 Spectre 执行、性能测量或一般连续时间资格声明。

<a id="ir15-precision-chain"></a>

## 历史 IR15 精度链

下表是 EVAS 0.9.0 / IR15 运行时 `d451605` 的历史精度链证据，不描述新运行时。

| 收据 | 实际执行与限制 |
| --- | --- |
| [精度链检查](results/precision-chain-checks.json) | 372 Python、83 Rust、locked build、Clippy、格式与冻结身份检查通过；一项旧性能探针 ignored；保留旧内核 RED 和修复过程失败 |
| [原 31×2 矩阵](results/precision-chain-matrix.json) | 62 次新本地执行，两档各 31/31；CSV、判定与生效设置和 ddfd379 一致；输入、阈值、检查器与分母未改 |
| [数学/兼容 review](REVIEW.md#precision-chain) | 点输入根误差证明，无条件 PWL/采样状态误差传播，实际接受帧的失败回退；无法证明预算时拒绝 |

矩阵 JSON 保留全部原字段和逐配置值，格式改为每条记录一行；检查收据同时记录原格式与当前格式
SHA256。这是排版整理，不是新执行或重判。该轮修复没有新 Spectre 执行或性能测量。

执行内核 SHA256：`0d92e770471638182f05fec53c308c0b34d89935c25bbaf70d47f5c9c33f522f`。
原始波形、日志、两版内核、输入与源码快照在 ignored 的
`runs/precision-chain-20260930T202707Z-e1c89a/`，为 **仅本地保留**。
RAW_MANIFEST SHA256：`a55ea465456f812f05f06be6673e4b9dbc323f38b89ed0f349319521b0a727af`，
绑定 876 文件、172,681,211 字节；此归档没有因交付整理而改写。
正式 DVS 资格仍 **I**；原条件已参与开发，有限观测满分不是全时域精度或未见确认集。

<a id="continuous-dynamics"></a>

## IR16 连续动态开发检查点

本地运行时 `ba5ab46e90ec4769e47478a492b80ab2dc7a09b6`，EVAS 0.10.0 / IR16，
该实现已随 PR30 合并；执行收据仍保留当时的分支身份，未发布 tag。
[数学、状态生命周期与组合边界](../../evas/docs/CONTINUOUS.md)记录仿射积分反馈、固定系数
1–8 阶完整滤波、直接 PWL `ddt` 和状态独立动态 cross。

| 收据 | 实际执行与限制 |
| --- | --- |
| [开发检查与迁移](results/continuous-dynamics-checks.json) | 416 Python、110 Rust、locked build、Clippy、格式、数学及冻结身份检查通过；一项旧性能探针 ignored；仓库内 7 份可运行 manifest 均从原始 VA 重编译为 IR16，生成 IR 由冻结内核直接执行成功 |
| [原 31×2 新矩阵](results/continuous-dynamics-matrix.json) | 两档各 31/31；62 份 CSV、独立判定和数值设置与 IR15 `d451605` 一致；仅引擎版本元数据变化，原输入、检查器、阈值与分母未改 |

内核 SHA256：`6a33d40145edace830285cf6b17615d6010a3391db0368cd6566fe393b382335`。
原始波形、日志、生成 IR、请求/响应、源码与内核在 ignored 的
`runs/continuous-dynamics-20261001T063752Z-128260/`，为 **仅本地保留**。
RAW_MANIFEST SHA256：`956d566e2afbc280aafe4980c1ac916294fe3fe6d8ac10cb9012569ad6aaa97c`，
绑定 621 文件、166,825,131 字节。IR15 旧归档及旧收据保持原身份。
收据保留开发过程失败的可用性；一轮中间失败只有会话记录，没有保留日志，不声称可以重取。

新解析开发回归不增加原 31 条件数；本轮没有新 Spectre 执行或性能测量，正式资格仍 I。
输出和根盒认证限所列受限范围，不宣称任意非线性 DAE、事件修改积分反馈、理想跳变
或整个电压域 Verilog-A 已完成。后续公开完整 raw 或发布版本属于独立动作。

### PR30 初始化 review 修复

初始化修复运行时 `071a813db83f92714f9a4f946ab2d0a2159f31b2`，EVAS 0.10.0 / IR16，
已随 PR30 合并到 main `bedf20f`。原收据的未合并状态描述保留为执行时快照。
此前单位斜坡的 `ddt` 在 DC 返回 0，但恒等滤波后的输出返回 1，且残差为零。
修复在整个网络中分别使用 DC 的零输入导数和瞬态 PWL 斜率；查询不修改物理初始状态。
连续 guard 准入还需排除经滤波直接通路留下的 ddt 跳变。

[初始化组合义务](../../evas/docs/CONTINUOUS.md#初始化组合的独立行为义务)由恒等式、联合线性关系、
闭式响应及区间包含关系确定答案。[修复收据](results/continuous-initialization-review.json)保留：

- 旧内核 RED：7 个 Python 测试方法出现 15 个失败的测试/子测试；2 个新增 Rust 私有测试失败。
- 修复后 423 Python、112 Rust 通过，1 项旧性能探针 ignored；locked build、Clippy、格式、数学及身份检查通过。
- 相同 IR 请求的五个新旧内核对照；嵌套/内部 relay 恒等滤波及直接通路初值修复，正时间符合独立答案。
- 原矩阵 62 次新请求，两档各 31/31；输入、62 份 CSV、独立判定及生效设置与首轮 IR16 完全一致。

新增 7 个 Python 方法、2 个 Rust 私有测试及 6 项行为义务分别计数，原 31 条件分母未变。
没有新 Spectre 或性能测量；它们已经用于修复，属于开发证据，正式资格仍 I。
完整源码快照、内核、日志和波形仅本地保留；其目录及封存清单哈希见修复收据。
首轮 IR16 和历史 IR15 的收据/归档保持原身份。

<a id="dynamic-closure"></a>

## 历史动态补齐检查点

0.11.0 / IR16 动态补齐基于 PR30，已随 PR31 合并；下述收据保留执行时身份。
内部/算子输入 ddt 采用质量关系；事件后的积分/复位保留全部调用点状态；
受限多项式积分采用 Picard 管和区间 Taylor。数学、状态和组合边界见
[连续动态章节](../../evas/docs/CONTINUOUS.md)，精确执行身份见[分支检查收据](results/dynamic-closure-checks.json)。
运行时 `71c6ceb` 的 450 Python、116 Rust 通过，另有一项旧性能探针 ignored；
locked build、Clippy、格式、数学和冻结身份检查通过。原矩阵 62 次新执行两档各 31/31，
CSV、判定和数值设置与 PR30 一致。27 个新动态开发方法不增加原条件分母。
此首轮检查点的非精确时刻非线性重启仍拒绝；后续扩展见下面的新执行身份。
本批没有新 Spectre 或性能测量，完整 raw 仅本地保留，正式资格仍 I。

运行时 `4642cd2` 的[事件窗口检查](results/nonlinear-event-window-checks.json)补充时间独立参数切换
的非线性根盒重启；先应用实际复位，再认证到代表时刻的短段流，完整误差进入未来历史。
456 Python、117 Rust（另有一项旧性能探针 ignored）、Clippy 与格式检查通过；
33 个动态开发方法单独计数，其中本轮新增 6 个方法、扩展 1 个原方法。
原矩阵再次执行两档各 31/31，62 份波形、独立判定与数值设置和 `71c6ceb` 一致。
保留先前开发尝试接受超预算结果的连续采样反例，该检查点明确拒绝非线性网络非精确时刻的连续采样和输入条件写者。
边界检查在事件批次入口访问实际触发体，相同代表状态值不绕过检查；
未来的精确采样写者不会阻止当前常量切换，精确时刻采样仍使用已有验收。
隐式非线性 DAE、混合算子、根盒采样/条件联合认证、未来事件稳定化及事件后 guard 重定位仍缺。
没有新增 Spectre 执行、性能结论或全时域资格，完整 raw 仅本地保留。

运行时 `d06e7f3` 的[合并前审查检查](results/dynamic-closure-review-checks.json)保留两项线性采样/选支反例的同 IR 前后对照，
并统一线性/非线性事件准入与上端点代表时刻前提。458 Python、118 Rust 通过；
一项旧性能探针 ignored，Clippy/格式/数学/冻结身份检查通过。35 个动态开发方法单独计数。
原矩阵两档新执行各 31/31；62 份 CSV、判定与生效设置和 `4642cd2` 一致。
原收据的本地分支状态保留为执行时快照；完整 raw 仍仅本地保留，没有新 Spectre 或性能测量。

<a id="certified-mixed-dynamics"></a>

## 连续动态三项开发检查点

0.12.0 / IR16 基于 PR31 / main `09b4222`；该次被测运行时为 `fd60d11`，
记录的是当时尚未集成的开发检查点。三组实现共用历史/误差接口，数学与边界见 [CONTINUOUS](../../evas/docs/CONTINUOUS.md)：
积分与 proper 滤波共同传播；根盒采样/条件与代表时刻输出分别认证；无事件 index-one 多项式隐式 DAE。
每项都保留显式初值、调用点身份和不可变候选历史，超出范围或不能证明预算时拒绝。

[检查收据](results/certified-mixed-dynamics-checks.json)记录 482 Python、121 Rust 通过，
另有一项旧性能探针 ignored；locked build、Clippy、格式、数学及冻结身份检查通过。
24 个新增开发方法来自三个专题和积分乘积面积检查；查询不变性、精确有理数、奇异 Jacobian、
拒绝/丢弃后重试由独立答案和 Rust 私有检查保护。
[原矩阵新执行](results/certified-mixed-dynamics-matrix.json)两档各 31/31；
62 份 CSV、独立判定、输入和除引擎版本外的生效设置与 PR31 完全一致。模型、判据、容差和分母未改。

第一次 `cc68572` 的矩阵两档只有 26/31：完整根盒失去了条件与已触发 guard 的零集关系，
导致等号分支不确定。该失败检查点完整封存；修复利用精确的同零集证书，并测试未触发 OR 叶子不能提供证明。
严格比较以数学根 tau 为观察点，代表时刻 b 单独验收；与旧的代表时刻选支约定的区别明确留作 review 重点。
保留同 IR 在 PR31、修复前和最终内核间的对照，未将根盒改写为零宽或扩大容差。

最终完整 raw 在 `runs/certified-mixed-review-20261001T121949Z-311235/`，
第一次失败 raw 在 `runs/certified-mixed-dynamics-20261001T115742Z-dafb6b/`，均为仅本地保留。
精确源码、内核、清单哈希和可用性由检查收据维护；仓库内只有整理结果及开发测试，不宣称完整 raw 公开可取。
本轮没有新 Spectre 执行、性能结论、未见确认集或一般连续时间资格；正式 DVS 仍为 I。
隐式 DAE 的事件/复位/其他算子组合、非线性滤波 DC/直接通路及更广事件调度仍未补齐。

独立审查修复运行时 `d3daff0` 的[单独收据](results/certified-mixed-review-fixes.json)
保留修复前失败、修复后的 484 Python / 121 Rust 及原矩阵新执行：两档各 31/31，
62 份 CSV 与 `fd60d11` 和 PR31 一致。原模型、检查器、容差与分母保持冻结。
修复仅针对显式零 reset 的 tau 采样和已知混合历史重启的 DC 误拒绝；
独立复核另发现的“同刻实际复位并采样同一积分”误拒绝在该 0.12.0 检查点前后都存在；
后续修复见[第二批共同闭包](#lifecycle-closure-review)，历史失败不改写。
爆炸方程探针在 25 秒上限内未得到最终判定，不能计为通过；本轮没有新 Spectre 或性能实验。
新 raw 在 `runs/mixed-review-fixes-20261001T211952/`，旧失败、旧验证归档与收据保持不变，均为仅本地保留。

<a id="shared-lifecycle-review"></a>

## 共同生命周期：第一批审查

本批只交付[共同契约](../../evas/validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract)、
独立答案和对照证据，未修改求解器。使用本地 `0d255b0` 分支，运行时与 `d3daff0`
完全相同，EVAS 0.12.0 / IR16；没有合并或发布。
首次初始化、已知历史续算、事件复位/采样、只读观察和整批提交分别定义。
数学根 tau、实际触发 te 与内部代表时刻 b 分开记录；同刻采样阶段是待审查的实现选择。

10 类开发探针各两档：cross 严格条件、零复位 timer/非线性 cross 采样、
实际复位采样正序/逆序/非线性 cross、单独复位、释放时采样、已知历史非线性续算、
首次积分加滤波。新执行的[综合收据](results/shared-lifecycle-review.json)保留全部 40 条配置记录。

| 最终执行与观测 | EVAS | Spectre 21.1.0.509.isr12 / thu-sui |
| --- | --- | --- |
| 新执行配置 | 20 | 20，全部正常退出 |
| 有限轨迹与独立答案一致 | 12 | 9 |
| cross 条件/采样分类观察 | 2；根附近采样，严格条件为假 | 2；稍晚采样，严格条件为真 |
| 其余结果 | 6 个实际复位并采样配置明确拒绝 | 8 条轨迹超本实验 allowance；1 条释放样值超 IC allowance，观测检查未通过 |

Spectre 六个实际复位/采样配置都接近复位后初值 1，而不是复位前约 1.5；
交换两句赋值仍得到相同分类。EVAS 对同一合法组合报
`operator history changed during same-time settlement replay`。
这支持下一批共同闭包的方向；不能通过放宽历史比较或固定追加一次重放掩盖问题。

cross 对照的 base/fine 触发见证分别约为 `0.50390625 T` / `0.5000004768371582 T`，
EVAS 为 `0.5 T`；时钟采样和输入采样在本实验 allowance 下承认共同 te。
严格条件可以随合法触发时刻改变，不能从 `g(tau)=0` 推出 `g(te)=0`。
根触发和晚触发的取舍要随采样及未来历史一起审查，不单独追求条件位一致。

Spectre 的部分复位后滤波偏差约 1e-5 V，在 fine 档仍超当前有限观测判据。
最大偏差来自滤波 y；检查按该次实际事件见证重新计算解析分段轨迹，已计入早/晚触发。
本批未调节 Spectre 的 LTE、积分方法或复位附近步长，不能归因为某个未验证的内部算法，
也不能据此判断 EVAS 普遍更准确。释放 base 的保持样值为 `1.000001300271197`，
超 `1e-6 V` 的 IC allowance；此条没有完整轨迹误差判定。

观察 allowance 为 `1e-6 V`，平滑组合轨迹采用 `4*allowance`，首次初始化轨迹采用
`allowance`；均在首次执行前固定，重判没有扩大。边界附近原始导出保留、平滑误差统计排除，
事件阶段、保持状态和时间见证另查。没有物理观察误差上界、完整边界认证、真实性能测量
或真实控制流程的失败回退试验；正式资格 I。原 31 条输入、检查器、阈值和分母未动，本批未重跑它们。

首次冻结预检缺少 checker identity 时没有仿真执行。随后 r2 的 20 次 Spectre 尝试中，
8 条因源码 `.5` 字面量不兼容而失败，12 条正常退出；原失败保留。
仅将源码改为 `0.5` 后用新身份 r3 重跑全部配置。r2 和 r3 各另有 20 次 EVAS 新请求。
分析阶段修正了日志显示舍入的误判，以及释放采样的阶段绑定；旧判定保留，新分析绑定独立源码哈希。
日志设置仅能确认精确提交值落入显示舍入区间，不能宣称日志暴露了内部完整浮点设置。

完整 raw、冻结输入、源码和分析归档为仅本地/thu-sui 保留，路径及清单哈希见收据。
仓库包含生成器、数学校准和整理结果；这不等于完整 raw 已公开可取。
以下在仓库根目录执行，使用新目录；远端只运行冻结源码，不修改私有配置：

```sh
python3 -B evas/validation/check_lifecycle_math.py
python3 -B -m unittest discover -s experiments/parallel-gap-integration -p test_lifecycle_contract.py -v
python3 -B experiments/parallel-gap-integration/lifecycle_contract.py build runs/NEW-LIFECYCLE
python3 -B runs/NEW-LIFECYCLE/snapshot/experiments/parallel-gap-integration/lifecycle_contract.py evas \
  runs/NEW-LIFECYCLE --kernel evas/rust_core/target/debug/evas-kernel
# 将冻结输入复制到远端新目录；PROFILE 是已授权使用的私有 Spectre 配置。
python3 -B runs/NEW-LIFECYCLE/snapshot/experiments/parallel-gap-integration/lifecycle_contract.py spectre \
  runs/NEW-LIFECYCLE --spectre-profile PROFILE
# 取回远端目录为本地 runs/NEW-LIFECYCLE/spectre-remote 后：
python3 -B experiments/parallel-gap-integration/lifecycle_contract.py analyze \
  runs/NEW-LIFECYCLE --output runs/NEW-LIFECYCLE/analysis.json
```

第一批独立校准为 7 项纯数学、9 项检查器正反例。其后实施结果另列下节，不改写第一批失败。

<a id="lifecycle-closure-review"></a>

## 共同生命周期：第二批实现

0.12.1 / IR16 在原分支实现[复位观察闭包](../../evas/docs/CONTINUOUS.md#shared-lifecycle-closure)，
该次执行发生在提交、集成之前。运行时身份采用完整本地源码快照和内核哈希，基于 `0d255b0`；
不能把该基准 commit 当作新内核源码。数学、代码入口、RED 与全部失败见[实施收据](results/lifecycle-closure-checks.json)。

实际复位后的 IC 与事件体采样共同求解，闭包稳定后安装未来历史；每轮赋值从同一接受状态重放。
未复位的积分和严格 proper 滤波保持物理历史；局部 `q=q+1` 只按源程序顺序执行一次。
真实生产 Controller 的拒绝、丢弃和重试测试覆盖接受时间、状态/误差、历史查询、算子截止点、记录及游标。
共同观测时间区间进入事件 trace，保留 te=tau 的 cross 策略；没有增加晚触发模式或泛化复位固定点求解。
审查还发现非严格 proper 滤波的直接项事件反馈可能有多个同刻解：新增结构准入明确拒绝，
并验证局部顺序更新和经过严格 proper 状态的控制组。先前接受结果与修复前 RED 保留。

| 本批检查 | 实际结果 |
| --- | --- |
| 同 IR 生命周期回放 | 20 个新 EVAS 请求：18 个有限一致，2 个 cross 分类；原六个误拒绝全部消除 |
| Spectre 对照 | 复用第一批 20 条 raw，冻结的最终检查器重判：9 个有限一致、2 个分类、8 个有限不一致、1 个观察检查失败；无新远端执行 |
| 原 31 条件矩阵 | 62 个新 EVAS 请求，两档各 31/31；62 份 CSV、独立判定、输入及除引擎版本外的设置与前检查点一致 |
| 开发检查 | 490 Python、122 Rust；另有 1 个旧性能探针 ignored；locked build、Clippy、格式通过 |
| 独立检查器 | 7 项纯数学及 9 项正反校准，阈值不变 |

复位反例的最大有限输出偏差约 `8.66e-15 V`；这只是该批采样结果，不是一般精度或速度排名。
原矩阵分母与正式资格 I 不变；完整 raw 和二进制仅本地保留，仓库内收据不等于全部原始资产已公开。
回放工具曾因原执行快照缺少后期分析接口而预检失败，随后因复制二进制未保留执行权限产生
20 条启动失败（没有内核进程执行）；这些记录均保留，最终回放另用新目录。
新增 trace 回归的首稿把 real 状态相对预算设为零而被拒绝，修正为非零相对预算后验证时间绑定，
没有修改原 20 配置、原矩阵或检查器阈值；通用状态绝对预算仍是缺口。

以下回放需要第一批本地冻结 raw；工具不会重新编译请求或运行 Spectre：

```sh
python3 -B experiments/parallel-gap-integration/lifecycle_closure.py \
  --prior runs/lifecycle-contract-20261001150222-r3 \
  --root runs/NEW-CLOSURE --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src:evas/tests python3 -B -m unittest -v test_lifecycle_closure
```

矩阵分析允许显式 `source_snapshot` 加完整源码哈希描述未提交的运行时；继续逐项核对当前源码、
冻结源码、执行记录和内核，不把工作树伪标为 clean，也不继承旧 commit 的结果。

## 复现入口

普通使用与开发回归见[构建/API](../../evas/README.md#构建与运行)。
重跑原矩阵需要记录中指明的冻结输入归档（仅本地保留）；分析程序验证输入、执行源码、内核、
波形和清单，再调用未修改的[原独立检查器](../dvs2-spectre-validation/check_results.py)。
以下命令在仓库根目录运行，输出使用新目录；占位路径须替换为实际输入和身份：

```sh
python3 -B experiments/pr14-pr15-validation/matrix.py evas \
  --source runs/FROZEN-INPUTS --root runs/NEW-MATRIX \
  --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/parallel-gap-integration/analyze.py \
  --source runs/FROZEN-INPUTS --run runs/NEW-MATRIX \
  --identity runs/NEW-SOURCE-IDENTITY.json --output runs/NEW-ANALYSIS.json
```

`NEW-SOURCE-IDENTITY.json` 必须绑定实际源码与构建身份；格式见当前矩阵的 `execution_identity`，
不能复制旧身份描述新内核。上述是复现入口，不声明外部读者已能取得完整 frozen/raw。
兼容比较可对 gzip 归档解压出的原 JSON 使用 `--baseline`；历史 Spectre 重判用
`--spectre-receipt`，不计为新 Spectre 仿真。

<a id="lifecycle-observation-review-fixes"></a>

## 共同闭包审查的追加修复

[追加收据](results/lifecycle-observation-review-fixes.json)记录共同闭包之后的本地源码快照，
[数学与边界](../../evas/docs/CONTINUOUS.md#lifecycle-observation-review-fixes)随实现更新。
两个 RED 反例分别针对不可变历史遗漏根时刻误差、ddt 消除积分后遗漏瞬时依赖。
测试还覆盖恒等包装、断开恒零组件、内部电压中转、保留一层状态的合法组合和直接积分释放。
同刻观察接口与未来安装接口分开，未来 transition 目标不会被拿回去查询旧根盒。

旧收据和失败日志保留；本次原 31 条件、20 条共同生命周期回放使用原输入/检查器，
Spectre 部分仅复用历史原始结果。实验阶段没有新远端仿真或性能测量；后续集成记录见 PR32。
未提供非点历史观察的算子明确拒绝，精确 timer 的正常支持作为通过控制。
原始日志与源码/内核快照仍为仅本地可用；公开收据不代表完整原始资产已经公开。

## 历史与资产

重复的长篇历史叙述保留在[固定交付前快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/REVIEW.md)。
六份大历史 JSON 以 `.json.gz` 在仓库内无损保存；
[归档清单](results/historical-receipts.json)记录原路径/字节数/SHA256、压缩文件身份与固定历史链接。
只有整理收据被压缩，完整 raw 波形/日志仍为仅本地保留。

| 固定检查点 | 历史入口 |
| --- | --- |
| 初期 IR14 与已发现反例 | [协议快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/README.md)、[矩阵摘要](results/MATRIX.md)、[原收据 gzip](results/original31.json.gz) |
| 联合功能 `39a4545` | [数学/范围](REVIEW.md#gap-completion)、[31 行摘要](results/gap-completion-matrix.md)、[矩阵 gzip](results/gap-completion-current.json.gz)、[检查 gzip](results/gap-completion-checks.json.gz) |
| 查询/根认证优化 `ddfd379` | [原理/测量](REVIEW.md#accuracy-optimization)、[矩阵 gzip](results/accuracy-optimization-matrix.json.gz)、[计时收据](results/accuracy-optimization-profile.json) |
| analog 单项与 Spectre 原执行 | [历史结果](../pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)、[Spectre 收据 gzip](../pr14-pr15-validation/results/analog-gap-spectre-comparison.json.gz)、[analog 收据 gzip](../pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz) |

例如无损解压至 ignored 输出目录后，原有 JSON 分析器可读取；清单中的 `original_sha256`
针对解压后的字节，不是压缩文件：

```sh
mkdir -p runs/RECEIPT-RESTORE
gzip -dc experiments/parallel-gap-integration/results/accuracy-optimization-matrix.json.gz > runs/RECEIPT-RESTORE/accuracy-optimization-matrix.json
```

合并保留这些历史提交及失败身份。历史记录中的“本地候选/未合并”描述的是当时的执行状态，
不代表当前交付状态；旧成绩也不改写为新源码的实验。
