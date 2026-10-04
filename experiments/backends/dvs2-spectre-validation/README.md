# Spectre 对照与事件专项

本目录保存 thu-sui 上的 Spectre 执行，以及与各次 EVAS 检查点的对照。
它包括原 31 条件两档验证、`cross` 触零/平台边界、`timer` 同刻更新和
`transition` 历史精度实验。

实验用独立数学关系判断结果。Spectre 是重要参考后端，但它的输出不会直接成为
EVAS 的黄金答案；版本、步长、容差与事件历史差异分别记录。

## 原 31 条件

Spectre 21.1.0.509.isr12 在两档各达到 **31/31**，共 62 条配置、1,333,719 个导出点。
[历史完整报告](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#original-31-condition-comparison)说明范围和观测结果，
[执行协议](PROTOCOL.md)固定输入、预算与判据。
[收据](results/RECEIPT.json)、[分析](results/analysis.json)和
[生效设置](results/effective-settings.json)保留实际身份。

这些结果属于固定历史批次。有限观察满足不代表完整连续时间资格，正式 DVS 资格仍为 I；
执行时间包含启动、编译等成本，不作为当前 EVAS 与 Spectre 的速度比较。

## 专项报告索引

完整实验记录从[固定历史提交](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md)查阅，保留原来的版本、失败、数学解释与命令。
下面按研究问题阅读，不需要按 PR 编号猜能力范围。

| 问题 | 报告 |
| --- | --- |
| 事件检查器能否检出漏事件、重复和共同历史矛盾？ | [独立校准](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#事件检查器的独立校准补充) |
| 孤立触零为何可能产生额外跳变？ | [触零实验](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pwl-触零边界实验)、[修复回放](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#孤立触零契约回放045) |
| 零平台、端点和停止点如何处理？ | [边界实验](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#零平台和停止点边界046) |
| 固定 timer 的事件前后解怎样联立？ | <a id="pr12-fixed-timer-comparison"></a>[timer 初版对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-fixed-timer-comparison) |
| timer 试算与整数顺序赋值有哪些反例？ | <a id="pr12-timer-repair-051"></a>[0.5.1 修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-repair-051)、<a id="pr12-timer-hardening-052"></a>[0.5.2 加固](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-hardening-052)、<a id="pr12-integer-sequence-053"></a>[0.5.3 整数顺序](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053) |
| 大绝对时间的 transition 历史误差为何不能只检查残差？ | <a id="pr13-transition-061"></a>[0.6.1 精度修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr13-transition-061)、[0.6.0 对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr13-transition-060) |
| 双向自换向的差异来自 cross，还是积分重启？ | [拆分诊断](#cross-restart-diagnostic)：已知轨迹、固定时刻换向、原始反馈模型 |
| 定向振荡器示例能否满足共同判据？ | [示例对照](#triangle-example)：同一 VA、新执行、解析答案 |

上述 EVAS 版本是各次实验的被测身份，当前能力见[能力表](../../../evas/docs/CAPABILITIES.md)。

## 工具的分工

| 入口 | 作用 |
| --- | --- |
| [run_suite.py](run_suite.py) | 生成共同 DUT、刺激、网表与冻结清单 |
| [remote.py](remote.py) | 在已有 Spectre 环境执行并保存日志/波形 |
| [check_results.py](check_results.py) | 用独立答案检查结果与事件历史 |
| [report.py](report.py) | 汇总结果、身份与实际设置 |
| `cross_*.py`、`timer_*.py`、`transition_reference.py` | 专项输入、执行或分析；具体命令在对应报告中 |

## 如何复核与重新执行

从仓库根目录运行公开检查器校准，无需 Spectre：

```sh
python3 -B -m unittest discover -s experiments/backends/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B scripts/verify_validation_version.py
```

只生成一份新输入，可运行 `python3 -B experiments/backends/dvs2-spectre-validation/run_suite.py runs/NEW-INPUTS`。
实际执行还需要 Spectre 安装、许可证与私有配置；远端命令见 [PROTOCOL](PROTOCOL.md)
和各专项报告。既有结果重判需要相应原始归档，并写到新路径。

公开材料包括协议、脚本、精简结果与收据。完整波形、日志和机器配置仅本地/thu-sui 保留；
公开哈希不等于可下载原始数据。新执行和历史重判必须使用各自的身份，不能覆盖原报告。

<a id="history-relocalization"></a>

## 事件修改积分轨迹后的 cross

[执行与分析工具](history_relocalization.py)固定 7 类模型、两档步长，共 14 个配置。
模型覆盖积分斜率增大、减小、停止、反向、反复反向、非精确触发时刻和保持阈值变化。
EVAS 和 Spectre 使用相同 VA 输入；两者分别与分段解析积分和手算事件时刻比较。
观察允许误差预先固定为电压 `1e-6 V`、事件时刻 `2e-7 s`，同时检查完整时间域、
事件计数和输入波形。该允许误差是实验判据，不等同于仿真器自身的误差保证。

当前运行入口：

```sh
python3 -B history_relocalization.py prepare /path/to/new-run
python3 -B history_relocalization.py evas /path/to/new-run
# 将冻结目录和脚本复制到有许可证的 Spectre 主机，然后运行：
python3 -B history_relocalization.py spectre /path/to/new-run --binary /path/to/spectre --setup /path/to/setup.csh
# 取回结果，在本仓库中分析：
python3 -B history_relocalization.py analyze /path/to/new-run --output /path/to/analysis.json
python3 -B -m unittest discover -s . -p test_history_relocalization_reference.py -v
```

每个 Spectre 配置限时 90 秒，许可证等待 30 秒。输入、工具和内核身份随运行冻结；
不能覆盖已有启动记录。原始输出留在 ignored `runs/`，不作为公开可下载的波形。
校准测试包含正确解析答案、漏事件、额外事件、偏移事件、错误轨迹和残缺输出。
这组测试是开发证据，不是新确认集或一般连续时间资格。

2026-10-04 前一版候选的[执行收据](results/history-relocalization.json)保留全部分母：

| 批次 | EVAS | Spectre | 观察 |
| --- | --- | --- | --- |
| 原 7 类 × 两档 | 14/14 | 10/14 | 非精确事件的两档积分波形超差；双向换向的两档反复触发并超时 |
| 换向仅改为 `cross(...,+1)`，两档 | 2/2 | 0/2 | Spectre 正常结束且各触发 3 次，但波形/时刻仍超差 |
| 非精确事件、单向换向，各两档更紧容差 | 复用相同模型的 EVAS 证据 | 4/4 | 保持原观察判据；改变的只有 Spectre 求解容差 |

最后四项固定 `maxstep=0.002 s`、`method=traponly`，使用
`(reltol,vabstol,iabstol)=(1e-10,1e-12,1e-16)` 和 `(1e-12,1e-14,1e-18)`。
非精确事件的最大积分误差从约 `6e-6 V` 降到 `6.13e-8 V`、`1.51e-9 V`；
单向换向则从约 `3.21e-5 V` 降到 `3.11e-7 V`、`6.62e-9 V`。
这些结果支持数值积分误差的解释，不能证明 Spectre 的内部实现细节。

双向换向在约 `0.508 s` 前已产生数百万次触发，90 秒限时后留下不完整 PSF。
单向对照只把乘积 guard 的 direction 从 `0` 改为 `+1`，独立预期仍为 `.5、1.5、2.5 s`。
它消除了反复触发，支持“换向后重新穿越同一零点”的反馈解释；不能把这两项超时改写为对照通过。

**解释修正：**上表 14/14 是旧候选对预设三角波的数值符合，不能证明原双向模型的可移植性。
旧候选的离根证明没有保留进入方向，可能把返回穿越当作已消费根的不确定性。
后续修复将无法区分的情况明确拒绝，见下节。原源码、原判据、14/14 结论和原失败原样保留，
新证据使用单独执行身份。

初次执行还保留两类设置失败：不完整的 Cadence 环境导致许可证错误；无前导零的实数字面量
导致 Spectre 编译拒绝。最终环境依据 AlphaApollo-Chips 已验证的 `ic6_sui` 配置，按顺序加载
两个管理员脚本，不启动 GUI。使用 `--setup /path/to/first.csh --setup /path/to/second.csh`
传递两个脚本；具体机器路径仅保存在私有运行配置中。

<a id="oscillator-compatibility"></a>

## 振荡器模型、返回穿越与容差

本专项分开检查两个问题：模型是否稳健表达设计要求，以及同一模型在两种后端的
数值结果是否满足共同判据。[工具](oscillator_compatibility.py)与
[收据](results/oscillator-compatibility.json)保留模型、配置、原始失败、分析修正和文件身份。
运行于本地 EVAS 候选及 thu-sui 的 Spectre 21.1.0.509.isr12。

### 模型为什么会反复触发

令 `z'=s`、`s=±1`，在 `cross((z-0.5)*(z+0.5),0)` 中执行 `s=-s`。
若第一次事件在真根之后 δ 秒执行，z 已略高于 0.5。换向后 z 返回穿过 0.5；
双向规则也选择这次返回，再次换向。准确的间隔还受积分历史、步长和定位影响。
所以“理想三角波每秒换向一次”是设计意图，不能直接当作这段代码的唯一合法结果。

在同一模型、相同输入下，只模拟到 `0.50000006 s`，比较以下单因素配置：

| Spectre 配置 | `reltol` | `cross(ttol,expr_tol)` | `maxstep` | 方法 | 观察到的事件数 |
| --- | --- | --- | --- | --- | ---: |
| 基础 | 1e-8 | (1e-9,1e-8) | 0.002 | traponly | 12 |
| 收紧求解容差 | 1e-12 | (1e-9,1e-8) | 0.002 | traponly | 2 |
| 收紧 cross 容差 | 1e-8 | (1e-11,1e-10) | 0.002 | traponly | 1002 |
| 缩小最大步长 | 1e-8 | (1e-9,1e-8) | 0.0002 | traponly | 1 |
| 改积分方法 | 1e-8 | (1e-9,1e-8) | 0.002 | gear2only | 1 |

各档 `vabstol=reltol/100`、`iabstol=reltol/1e6`。乘积 guard 的 expr_tol 对应 V²，
不是节点电压容差。基础档的前两次事件约为 `0.500000000500 s` 和
`0.500000031000 s`，z 分别在阈值两侧。这支持返回穿越解释，尚不能证明 Spectre 内部算法
或认定它有 bug。短窗口里只有一次事件也不能证明长期振荡正确。

旧 EVAS 离根检查缺少进入方向。当前候选保留该方向；如果不能区分返回穿越与原根的不确定性，
返回 `unsupported_cross`，上述五例均明确拒绝。已经可分辨的返回根仍会被搜索，
不能因为间隔小于 ttol 而删除。只计数、不改变轨迹的双向模型
`z=t−t²/2` 在 `.5、1.5 s` 穿越 `z=.375`，两边五档均通过。

### 同一外部精度目标，不要求内部参数相同

外部检查固定为波形误差 `1e-6 V`、事件时刻误差 `2e-7 s`，事件次数与顺序正确。
它们不等于任何后端的内部误差保证。对改为向外触发的振荡器，同样运行五档：

- Spectre 基础档误差约 `3.21e-5 V`；只收紧 cross 或只缩小 maxstep 仍超差。
- 收紧求解容差后，误差为 `6.62e-9 V`；gear2only 本例为 `3.22e-7 V`，都满足本次判据。
- EVAS 通常使用 `vabstol=1e-8、reltol=0`，四个对应配置通过；它没有切换到 Spectre 的积分方法。
- 单独把 EVAS 电压预算改成 `1e-10 V`、仍保留原 cross 容差时，历史误差上界
  `1.64e-10 V` 超预算，明确拒绝。它不是放宽外部判据后计入的通过项。

因此，比较应先固定源码、输入、初值和外部精度目标，再分别校准后端的设置。
内部求解、积分历史、事件定位和输出采样各有作用，不能把 reltol 的数字相同称为等精度。
事件次数不同属于离散行为差异，不能用电压误差较小来抵消。
本次只比较行为与准确度；机器、构建及计时边界不同，不报告速度比。

本次完成的是**共同外部判据与特定配置的校准**，尚未提供通用的容差自动换算。
最终八个候选题配置采用以下对应关系：

| 控制项 | EVAS | Spectre |
| --- | --- | --- |
| VA、参数、输入、初值 | 同一份 | 同一份 |
| VA 中的 cross 参数 | `ttol=1e-10 s、vtol=1e-10 V` | 相同；参考解用电压 guard |
| 内部求解设置 | `vabstol=1e-8 V、reltol=0` | 两档 `(reltol,vabstol,iabstol)` 为 `(1e-11,1e-13,1e-17)`、`(1e-12,1e-14,1e-18)` |
| 最大步长 | 同一案例规定值 | 同一案例规定值 |
| 验收 | 对独立解析答案检查电压 1 µV、事件时刻 200 ns 及正确事件序列 | 相同 |

两边在各自保存点上对解析答案通过检查，不表示输出时间网格相同、波形逐位相同，
也不是一般连续时间的误差保证。原始双向自换向模型仍是 EVAS 明确拒绝、Spectre 对设置敏感；
该差异没有被“容差统一”消除。方向明确的参考模型是修改后的模型，必须单独报告。

### 仓库自有的候选修复题

[va07-triangle-repair](../../../benchmark/tasks/va07-triangle-repair/instruction.md) 要求修复边界换向，
并改变上下限、初态、运动方向及正速度输入。数学答案来自速度积分和三角波折返：
若区间宽 W=upper−lower，累计路程 `A(t)=∫v_ctl(t)dt`，
则相位按 `2W` 取模后折返；每跨过一个宽度 W 就发生一次换向。
这份答案不来自 EVAS 或 Spectre 波形。

参考解用上限向上、下限向下的 `cross`；乘积 guard 的向外触发等价写法也可通过。
四类输入各两档，共 8 个配置。首次用 `reltol=1e-10/1e-12` 时，Spectre 为 6/8；
下降初态和斜坡输入的较松档事件时刻超差。保留该记录后，最终题目采用
`1e-11/1e-12`，仍保持原外部判据，EVAS 与 Spectre 各 **8/8**。
最大保存点误差分别约 `6.09e-13 V`、`9.26e-8 V`；最大事件误差分别约
`9.38e-12 s`、`3.43e-8 s`。这不构成全时域误差资格。

两份等价写法校准均通过；双向规则、错误速度、错误初态、忽略速度输入四个错误版本均被拒绝。
任务自带 verifier 在 thu-sui 对参考解完整执行八例，reward=1；未运行完整 Harbor 容器或 agent 评测。
该候选题不改变原六题初筛及原 31 条件的分母。

### 复跑与材料范围

从仓库根目录运行：

```sh
python3 -B experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py cases benchmark/tasks/va07-triangle-repair/tests/cases.json
python3 -B experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py prepare runs/NEW-ID
python3 -B experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py evas runs/NEW-ID
# 在同样目录结构、已配置 Spectre 的主机中运行：
python3 -B experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py spectre runs/NEW-ID --binary /path/to/spectre
# 取回结果后，新建分析文件，不覆盖旧记录：
python3 -B experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py analyze runs/NEW-ID --output runs/NEW-ANALYSIS.json
```

`prepare --group benchmark` 仅生成 8 个参考配置与 6 个校准配置。默认另含 15 个诊断配置。
Spectre 每例限 15 秒、单文件 16 MiB；EVAS 使用适配器的 300 秒限时。
输入与执行工具被冻结。重判允许新分析身份，并保留原执行身份。
首次分析曾误读 EVAS 的时间轴，已改为 `transient.times` 并增加回归；原分析被标为已替代，
不算仿真器失败。Spectre 日志把短 stop 显示为 0.5，实际停止时刻另从 PSF 核验。
原始数据和旧版本输入包保留在 ignored `runs/oscillator-compatibility-20261004-r1*`、`r2*`
及 thu-sui；公开收据中的哈希不表示这些原始数据可以公开下载。

<a id="cross-restart-diagnostic"></a>

## 将事件检测与积分重启分开检查

本轮固定三个问题，避免先把 Spectre 的输出或理想三角波当作原模型的唯一答案。
[工具](cross_restart_diagnostic.py)生成共同 VA；[收据](results/cross-restart-diagnostic.json)
保存 20 个拆分配置和 6 个不连续通知对照。Spectre 26 例均完成，设置和停止时刻均核验。
这是本地候选与 Spectre 21.1.0.509.isr12 的开发证据；没有改动本轮 EVAS 求解实现。

| 对照 | 固定什么 | 独立答案 |
| --- | --- | --- |
| 外部 PWL | 直接提供先升后降的 z，cross 只计数 | `z=t`（t≤τ），之后 `z=2τ−t` |
| timer 换向 | `z=idt(s,0)`，τ 时把 s 从 +1 改为 −1；cross 只计数 | 同上；两次穿越 `.5` 和 `2τ−.5` |
| 原始反馈 | 保留原 VA，cross 内执行 `s=-s` | 记录事件数和轨迹，不预定唯一事件序列 |

对照分别取 `τ=.5000000005 s` 和 `.500001 s`，两根间隔为 1 ns 和 2 µs。
每类使用基础、收紧求解容差、收紧 cross 容差、gear2 四档，参数与上一节对应档相同。
小间隔停止在 `.50000006 s`，大间隔在 `.500004 s`；每例限时 15 秒、单文件 16 MiB。
诊断预先固定了 `1e-10 V` 保存点目标、`2e-9 s` 事件目标和恰好两次穿越。
它们用于分辨很小的积分偏差，不替换上一节的 benchmark 判据，也不是语言合规判据。

### 已定位的两个影响

**第一，事件分辨能力会影响计数。** 对 1 ns 间隔的外部 PWL，Spectre 基础档、
收紧求解档和 gear2 档都只计一次；EVAS 因根时间包围重叠而明确拒绝。
将 cross 参数收紧为 `(1e-11,1e-10)` 后，两边都得到两次。
对 2 µs 间隔，两边四档均得到两次。该对照没有积分历史，不能把差异归因于 idt。

**第二，换向附近的积分误差会改变下一次穿越。** 固定 timer 的结果如下。
表中误差是在各后端保存点上，相对分段解析积分的最大偏差。

| 固定换向对照 | Spectre 基础档 | Spectre 收紧求解档 | EVAS 对应两档 |
| --- | --- | --- | --- |
| 1 ns 两根间隔 | 0 次；9.83e-8 V | 1 次；2.83e-11 V | 均 2 次；约 2.11e-15 V |
| 2 µs 两根间隔 | 2 次；2.67e-7 V | 2 次；3.12e-11 V | 均 2 次；约 2.11e-15 V |

用实际观察到的 timer 时刻重新计算参考积分，误差仍然存在，因此不能只解释为 timer 延迟。
小间隔即使积分误差缩小，事件计数仍可能受 cross 容差影响。这两个控制量不能互相替代。
这些结果只描述本组分段常量积分，不证明 EVAS 对一般电路更准确。

### 原模型的 30 ns 额外延迟如何产生

原模型基础档的前三个关键保存点为：

| 时刻 | 相对 `.5 s` 的时间 | `z−.5 V` | 观察 |
| --- | ---: | ---: | --- |
| 首次换向 | 0.500002 ns | +0.500002 nV | n=1 |
| 下一保存点 | 30.250001 ns | +0.500002 nV | z 没有变化 |
| 第二次换向 | 31.000003 ns | −0.250000 nV | n=2 |

在长约 29.75 ns 的第一步内，积分增量为零。它与梯形公式
`Δz=h(s_old+s_new)/2=h(+1−1)/2=0` 一致。随后 z 按 −1 V/s 下降。
从平台末端外推，返回根在 `.500000030750 s`；实际第二次事件又晚约 0.25 ns。
因此这次延迟可以拆为：**约 29.75 ns 平台 + 0.5 ns 回到阈值 + 0.25 ns 定位延迟**。
直接假设首次换向后立刻按 −1 积分，才会错误地把整个 30 ns 都归给 cross。

收紧求解容差后，首个平台缩短到约 0.499 ns；只收紧 cross 时仍约 29.997 ns。
这是对观测值的数学解释；没有访问 Spectre 的内部历史对象，不能据此断言其完整实现或判定产品 bug。
同一个短窗口内，原模型仍分别有 12、2、1002、1 次事件；EVAS 四档继续明确拒绝。

### 不连续通知不能直接当作修复

语言提供 [`$discontinuity`](https://www.verilogams.org/refman/modules/analog-procedural/task.html#discontinuity)
通知连续内核：参数 0 表示关系不连续，1 表示一阶导数不连续。
因此另取基础档，在原反馈模型和两个 timer 模型的换向体中分别添加这两种通知。
它们是修改后的模型，各自有独立执行身份。

原反馈模型的事件数从 12 变为 1（参数 0）或 3（参数 1）。两个通知都消除了所观察到的首个平台，
但返回事件未得到稳定定位；短窗口里的一次事件也不证明长期三角波正确。
两个 timer 对照的误差则基本不变。这个结果不支持“补一行通知就能统一结果”的结论。
EVAS 当前不接受该系统任务，六例均编译拒绝，未静默忽略通知。

本轮保留原模型作为兼容性探针。EVAS 继续保留可证明的返回根，并明确拒绝无法区分的根窗口；
不添加任意消抖时间，也不为匹配某组 Spectre 设置而制造积分平台。
面向三角波的可移植建模仍使用上一节的向外定向事件。若要接受原始双向写法，需先建立
根窗口中不同执行时刻是否会改变事件序列的判据，再确定可接受范围；本轮没有完成该能力扩展。
原始输入、证据和验收边界已记入 [Issue #70](https://github.com/BucketSran/vaEVAS/issues/70)。

### 复跑与分析边界

```sh
python3 -B experiments/backends/dvs2-spectre-validation/cross_restart_diagnostic.py prepare runs/NEW-ID
# 六项不连续通知对照改用：prepare runs/OTHER-ID --suite discontinuity
python3 -B experiments/backends/dvs2-spectre-validation/cross_restart_diagnostic.py evas runs/NEW-ID
# 在已初始化的参考主机上，用相同目录结构和冻结输入：
python3 -B experiments/backends/dvs2-spectre-validation/cross_restart_diagnostic.py spectre runs/NEW-ID --binary /path/to/spectre
python3 -B experiments/backends/dvs2-spectre-validation/cross_restart_diagnostic.py analyze runs/NEW-ID --output runs/NEW-ANALYSIS.json
```

EVAS 的事件时刻取自原生事件日志，并与输出计数核对；不能从稀疏输出点之间的计数跳变推定漏事件。
校准覆盖准确积分、错误历史、漏返回根、timer 延迟与积分误差的区分，以及稀疏观察。
原始文件在 ignored `runs/cross-restart-20261004-r1*`、`cross-discontinuity-20261004-r1*` 和 thu-sui 保留。
首次远端路径预检失败、分析适配修正及旧工具身份也保留；没有改写既有执行或正式矩阵分母。

<a id="triangle-example"></a>

## 定向振荡器示例的新执行

2026-10-04 将已校准的定向参考解整理成[第 4 课](../../../evas/examples/04-triangle-oscillator/README.md)，
使用同一份 VA 新跑 EVAS CLI 和 thu-sui Spectre 21.1.0.509.isr12。
初态 z=0、速度 1 V/s、阈值 ±0.5 V、stop=3 s，两边 maxstep 均为 .005 s。
EVAS 使用 vabstol=1e-8、reltol=0；Spectre 使用 reltol=1e-12、vabstol=1e-14、
iabstol=1e-18、traponly。内部设置并不等价，共同外部判据为 1 µV、200 ns、恰好三次换向。

| 后端 | 保存点最大电压误差 | 最大事件时刻误差 | 换向数 | 结果 |
| --- | ---: | ---: | ---: | --- |
| EVAS 本地候选 | 4.55e-13 V | 4.55e-12 s | 3 | 通过 |
| Spectre | 3.65e-9 V | 1.96e-9 s | 3 | 通过 |

独立答案是分段线性三角波，换向在 .5、1.5、2.5 s。EVAS 检查 10 个请求点，
Spectre 检查 706 个保存点；这些误差不是整个连续时间区间的最大值保证。
既有回归改为直接读取示例，检查手算值、等价 guard 和观察网格变化，相关模块 9 项通过。

[执行收据](results/triangle-example.json)保存输入、工具身份、生效设置、阈值和输出哈希。
原始材料在 ignored `runs/triangle-example-20261004-r1*` 与 thu-sui 保留，未公开下载。
Spectre 版本取自运行日志，原版本命令的空输出仍保留；分析对 OR 事件日志的适配修正也保留。
内核与前述拆分诊断相同，仍为未提交候选。本次完成可运行模型修复，
不关闭原双向模型的 [Issue #70](https://github.com/BucketSran/vaEVAS/issues/70)，也不改变原 31 条件矩阵。
## timer 缺省参数对照

<a id="timer-defaults"></a>

2026-10-04 在本地 EVAS 候选与 thu-sui 的 Spectre 21.1.0.509.isr12 上执行六个开发案例。
每个案例向两端提交同一份 VA。下表是固定事件日程与计数器的独立检查，不是原 31 条件矩阵的新执行。

| 案例 | 定时方式 | 预期次数 | EVAS / Spectre |
| --- | --- | --- | --- |
| 单次 | `timer(0.125e-6)` | 1 | 通过 / 通过 |
| 周期 | `timer(0.1e-6,0.2e-6)` | 5 | 通过 / 通过 |
| 显式容差对照 | `timer(0.1e-6,0.2e-6,1e-12)` | 5 | 通过 / 通过 |
| 空容差 | `timer(0.1e-6,0.2e-6,)` | 5 | 通过 / 通过 |
| 禁用 | `timer(0.125e-6,,,0)` | 0 | 通过 / 通过 |
| 自调度 | `timer(next)`，next 从 0.125 µs 起每次加 0.25 µs | 4 | 通过 / 通过 |

stop=0.95 µs，maxstep=10 ns；两端请求 `reltol=1e-6、vabstol=1e-9 V`。
Spectre 使用 traponly、`iabstol=1e-12 A`，已从日志核对实际设置。
EVAS 在编译期把缺省 timer 容差设为 1 ps。Spectre 的缺省 timer 容差没有从内部读取，
不能因 reltol/vabstol 相同就声称所有容差一致。
外部判据在执行前固定：事件次数精确一致、事件误差 ≤100 ps、事件窗口外计数电压误差 ≤1 µV。
两个后端的计数均正确；最大事件误差分别约为 2.12e-22 s 和 1.06e-22 s，
只代表这些简单时钟在保存点和事件记录上的结果，不是连续时间或性能资格。

[紧凑收据](results/timer-defaults.json)含共同 VA、网表、输入身份、有效设置、源码补丁和各项结果。
原始运行与一次性驱动脚本保留在本地 `runs/timer-defaults-20261004-final-evidence.tgz`，
r2/r3 Spectre 产物同时保留在 thu-sui；不是公开完整回放包。
提交前修复极大时间的上界溢出检查后，r4 用最终 EVAS 构建重跑六例，仍全部通过；
共同 VA、网表和契约均核对不变，Spectre 复用 r3 的执行，未冒充新执行。
读取实际 PSF 文件名所做的后处理修正没有改变模型、验收阈值或求解器设置；
检查器用手写正例及错时刻、缺事件、零计数、NaN 反例做过校准。

早期失败也保留：首轮 EVAS 的自调度案例在 `reltol=0` 时，real 状态更新的非零舍入界
无法通过零预算，5/6 通过；随后共同配置显式采用 `reltol=1e-6`。
r2 的六个 Spectre 案例因模型使用 `.125e-6` 等无前导零写法，在 AHDL 读入时报 VACOMP-1795，
不能用于判断 timer 语义。r3 同时修正两端源码为 `0.125e-6` 等写法后重跑；外部判据未放宽。

修复缺省参数后，原 [ZOOM 参考模型](../../../benchmark/tasks/va03-zoom-timing/solution/dut.va)
在该检查点编译推进到第 79 行的循环内事件。当时尚不支持静态 genvar 循环内的 `@(timer(...))`，
所以这份 timer 缺省参数收据未证明原模型可运行。后续补齐与新执行见下节。


<a id="zoom-static-events"></a>

## ZOOM 静态循环事件对照

2026-10-04 补齐循环内事件展开后，用未改写的
[ZOOM 参考 VA](../../../benchmark/tasks/va03-zoom-timing/solution/dut.va)分别运行本地 EVAS 候选和
thu-sui Spectre 21.1.0.509.isr12。两端采用原 [cases.json](../../../benchmark/tasks/va03-zoom-timing/tests/cases.json)
的两组参数，各跑两个周期。原 checker 的独立脉冲日程、15 mV 采样误差和 90 ps 边沿误差均未修改。

| 原案例 | 展开事件声明 | 两周期边沿总数 | 电压样本 | EVAS / Spectre |
| --- | ---: | ---: | ---: | --- |
| calendar-0 | 586 | 1172 | 1758 | 通过 / 通过 |
| calendar-1 | 114 | 228 | 342 | 通过 / 通过 |

两端的九路边沿数与预期完全一致，所有电压样本和边沿时间检查均通过。
EVAS 的观察网格在执行前固定：0.25 ns 网格、契约采样点、契约阈值时刻及其前后 20 ps。
Spectre 使用原网表和原生保存点。检查的是这些有限观察，不是整个连续时间区间的最大误差。

两端请求 `vabstol=1e-8 V、reltol=1e-5、maxstep=0.25 ns`。
原 Spectre 网表另有 `errpreset=conservative`，日志实际记录 `reltol=1e-6、method=gear2only`；
EVAS 保持请求值。两端按共同外部判据验收，不声称内部容差等价，也不作速度比较。
首次汇总因把全局请求值和瞬态实际值混读而停止；按日志作用域重新分析后得到本结果，
没有重跑后端或改变模型、设置与阈值。

[紧凑收据](results/zoom-static-events.json)保存源码、模型、checker、网表、观察网格与输出哈希及实际设置。
原始结果和一次性驱动/分析脚本保留在本地 ignored `runs/zoom-static-events-20261004/`；
Spectre 产物同时保留在 thu-sui。同名本地 evidence 压缩包含完整输入、补丁和原始输出，尚未公开下载。
这是开发回放，未新增 benchmark 任务，也未重跑或改写原 31 条件矩阵。
