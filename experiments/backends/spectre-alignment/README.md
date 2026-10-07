# 分层 Spectre 对齐

首批实际完成10个Spectre数值配置和1次版本预检，累计Spectre为66数值/24版本。新的dyadic constant条件已经出现稳定普通相位差近1cycle，但该PSF时间文字的可表示舍入区间包含真实wrap root，内部modulo机制与导出精度仍不能分开。严格失败保留；本批没有签发paper P或完成source/export/stop资格。

完整紧凑字段与所有原始指针见[evidence.json](evidence.json)。raw、源码输入、请求/响应、stdout/stderr、校准、transfer/dispatch/collection及失败收据保存在本机ignored `current/runs/spectre-alignment-20261007/`，均为local-only。原accuracy-control冻结与旧分母未修改。

后续另完成4个去掉root及近root强制采样的控制配置，累计达到70次数值/24次版本查询，见[独立事件控制](event-unforced.md)。它们有独立输入与结果身份，不替换下述首批判决。

## 三层结果

独立source数学层以Fraction积分新dyadic模型，PWL段系数和90位Decimal roots在[cases.json](cases.json)。T=2^-20s，IC=.125，rate=f*2^20，constant f=.5；PWL f=.5+.25ctl，clip限制[.25,.75]。修复后EVAS在六个新VCO冻结strobes的独立检查均符合；修复前四个拒绝原样保留。三个新模型的observer-on均用`accum`端口输出独立`idt`积分；其误差位于各case的`spectre_reference_maxima.accum`。`spectre_independent_idt_maximum`是原VCO专用分析字段，新模型该字段为null不表示其accum未测。原decimal源oracle与compiled-binary64对象继续单列。

export层要求每个指定anchor在原生时间token中精确存在。10个配置都执行完成，但完整观测资格全部因缺exactanchors未通过。不能将执行完成记作对齐通过。constant另有严格普通相位错误。freq和独立idt旁路符合预算，只把已观察分歧限制到modulo/output边界，不能证明旁路就是idtmod内部状态。

snapshot重放层使用现有EVAS修复后响应，仅按原样binary64时间的精确交集配对，不做nearest-neighbor替代或插值。原生未配对行继续占原分母；四center原例响应不称为40k全行配对。

| 条件 | Spectre执行 | 完整观测资格 | 原生行数 | Spectre普通/circular最大误差 cycle | EVAS精确交集及普通/circular差 |
| --- | --- | --- | ---: | --- | --- |
| constant off/on，各1 | completed | 缺358anchors；普通phase失败 | 各32815 | 约1 / 8.88e-16 | 各683点；约1 / 4.44e-16 |
| PWL off/on，各1 | completed | 缺358anchors | 各32813 | 6.73e-10 / 6.73e-10 | 各685点；6.73e-10 / 6.73e-10 |
| clip off/on，各1 | completed | 缺362anchors | 各32813 | 6.73e-10 / 6.73e-10 | 各680点；6.73e-10 / 6.73e-10 |
| 原VCO observer on | completed | 缺40160anchors；原预算波形符合 | 40840 | 1.01e-8 / 1.01e-8 | 仅4center；约1 / 1.01e-8 |
| event wide/tight/on及tight/off，共3 | completed | 各缺mathroot anchor1个 | 各57 | 不适用 | 两合法EVAS投影各6点；x/sample/count差均0 |

phase固定预算.001cycle、sine3mV、freq1mV、ctl10uV、4wrap与±100ps括定。普通phase义务包含wrap窗口，circular/sine符合不能抵消它。新模型全native sine最大约7.52e-9V，原VCO约6.35e-8V。

## 时间文字与观察效应

constant见证的raw时间文字是`7.390975952148437e-06`。它解析为root前1ulp，Fraction phase应为`2251799813685247/2251799813685248`，而Spectre输出phase=0。该constant observer-on的独立idt旁路（`V(accum)<+idt(f*1048576,0.125)`）最大误差1.78e-15cycle，取自evidence中本case的`spectre_reference_maxima.accum.error`；off/on公共输出、原生网格全部完全相同。

按16有效数字nearest输出建立的保守闭区间为[7.3909759521484365e-6,7.3909759521484375e-6]，真实dyadic root恰位于上端。输出tie模式和隐藏内部时间未知，因此标记time-resolution ambiguity。这个诊断不覆盖原严格verdict，不声称Spectre内部积分或modulo规则不同，也不要求EVAS改变半开数学规则。

constant358缺anchors中350可找到按16位格式化的精确同字raw token。余8是四root的center/right-nextafter；请求无重复binary64时刻，但16位文字发生两点一组的碰撞，附近raw相差1至3ulp。不能由raw判断这些近ulp strobes是否执行或合并。PWL353/358、clip354/362缺行也吻合格式化文字；原例仅380/40160吻合，其他原因仍未知。诊断仅定位缺失，不补造原生行。

五组off/on控制的全部原生公共输出及时间网格一致，最大差0；实际逐时刻比较数依次为constant32815、PWL32813、clip32813、原例40840、event57，evidence保存compared_time_count、信号数及比较时刻SHA；这比只看指定strobes更强，但不消除缺anchors的完整资格失败。原VCO副本只加独立idt的端口/贡献/net/save；剥除这些项后source/deck与原off逐字相同，controls/strobes/刺激完全匹配，才复用旧真实off raw。

## 事件观察

源ramp x=t/T，数学root=.375T。expr_tol固定.0625V，ttol宽/紧为2^-24/2^-40s；外部时间预算100ps、sample1mV、count一次。允许的定位窗口另列，不与外部预算混同。

两次Spectre observer-on均存储callback `$abstime`=3.576278686523438e-7；三次samplevalue均为.375、count均跳变一次。observer-off没有firedtime字段，不能从on推断off的隐藏callback时间；宽/紧公共观察值未见差异。root strobe会影响步进，该结果不能推广为ttol无影响。读取时刻、实际触发时刻与数学root分别保存。mathroot token缺失符合16位时间输出舍入。

EVAS不支持原源的`$abstime`，compile拒绝保留。去掉firedtime观察的两个合法投影各执行一次，EventRecord的nominal/代表事件点time=3.5762786865234375e-7、guard=0、sample=.375、count一次；EVAS采用数学root读取语义，这个代表点不能泛称Spectre实际callback时间；本次exact-root记录没有emitted observation_time_bounds，缺字段原样说明。投影不代表原源完整支持，不扩大PR79 exception。两请求7个时刻中各6个可与Spectre精确配对，51/57原生行未配对，mathroot指定时刻未导出。

## 身份、控制与复核

远端FREEZE SHA为`fcff0cb032a26839f58c49b7d3f39d111e1a64b7622557af90d4ee56bb926832`。原process/runner/native-reader依赖闭包和operator_wrapper复用。每次数值90s、license30s、4GiB、单CPU/线程、32MiB单文件、256MiB每条件轮询；最大raw7,144,432字节。所有10stage和version预检completed；operator清理确认，collection科学manifest核验通过，无自动数值retry。

EVAS修复后kernel SHA为`feaa1a27c803da7d36d26e8972a0451e1bd6eb7aed34f8f3dab9bd0b86648d28`。协调者原七例与修复后七例身份均保留，修复后请求逐字不变；这里重用这七份响应，新增分析不启动数值调用。另新增两个事件投影本地调用、0版本，执行约.72s/.01s。第一次冻结copy丢失可执行mode导致Popen拒绝，实际0数值/0版本；原失败目录保留，以新目录copy2修复，不是数值重试。本地只宣称串行90s约束，不混称远端内存/CPU限制已在macOS强制。

```sh
python3 -B -m unittest discover -s experiments/backends/spectre-alignment -p 'test_*.py' -v
```

修正后的20项独立checker校准通过，补齐wrap count/bracket、phase范围、缺列/NaN/Inf、callback窗口、native代表事件数量/时间与count读取时序等负控。samplevalue与ramp x的验收不依赖firedtime；observer先检查时间顺序、重复和全部被比信号有限性。旧8项校准未击穿这三项审查复现，旧false-pass结果保存在`backend/checker-correction-r2/astra-negative-probe-old.json`，修正版对应三项均拒绝。

原checker、原分析及`FROZEN_RESULTS_MANIFEST.json`不改，原候选文档/代码另存`backend/checker-correction-r2/previous-candidate/`。新checker冻结在`backend/checker-correction-r2/checker/`，重分析10份Spectre raw、7份既有EVAS响应及2份既有事件投影，0新模拟器调用；新分析为`backend/analysis-r2-checked/`与`backend/local-fixed-analysis-r2-checked/`。物理阈值、缺行义务与旧判决未放宽。

生产修复、七例同request前后和代码检查/审查身份由协调者维护在[alignment-implementation.json](../input-clamp/alignment-implementation.json)；本目录不改该文件。

最终 r3 进一步要求事件任务卡显式声明有效 `ports`；声明或必需观察列缺失时拒绝。observer-off 保留触发时间未知，不能由输出反推是否承担时间义务。新增3项校准覆盖这些边界。全部25份既有输出（首批10+7+2、后续4+2）重分析后，判决、分母及配对结果未变，0次新增仿真或版本查询。r2 代码与证据保存在 `backend/checker-correction-r3/previous-candidate/`；r3 的94项冻结清单 SHA 为 `b23cafc2e77179088292a6f669bc6826e90571ee0c5b76aff7890c26737c9674`。当前紧凑证据指向 `analysis-r3-checked` 分析，旧判决保留。

事件卡的 `ports` 指定本次要验收的观察义务，不是输出表的排他列模式。额外但未声明的列不受验收，也不能取得额外的时间资格；报告的 `required_signals` 与 `projection` 明确所验范围。显式投影只验收公共列，即使输入表含 `firedtime` 也不将其作为完整原源时间证据。
