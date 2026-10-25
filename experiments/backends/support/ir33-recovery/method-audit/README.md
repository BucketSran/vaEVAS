# 3257 个测试方法的契约、参考答案与断言审计

本目录保存 2026-10-25 完成独立复审的固定审计基线，供后续修复选择可信验收对象。
发布整理保留原裁决、撤回理由和统计；原始审查范围见 [review.json](review.json)。

已覆盖全部 3257 个方法、332 个模块，包括通过、失败、错误和预期失败项。
其中 **377 项包含已识别的测试问题，95 项有未解决的契约或参考证据缺口，2785 项在本次静态审查范围内未发现具体缺陷**。
377 项中有 32 项在原 CI 中通过。因此，通过数不能直接当作可靠验收目标数。

这些计数按方法去重。一个方法可能同时有正确数值检查、过期诊断断言和无效负控，
不能把“包含问题”解释为整方法毫无价值，也不能把一个方法当成一个独立缺陷。
本次归纳 86 组发现，组之间可共享方法。

## 范围与可信度

固定 `main@15eb7216f7071edb7eda7a9b0c56b7e8933c4c79`。
审查工作树 `566c36a9` 与其 Git tree 相同，生产代码及测试与
[完整 CI 40192400498](https://github.com/BucketSran/vaEVAS/actions/runs/40192400498)
的候选 `66aaa847` 完全一致。复用其执行结果，未重新运行完整套件。

此次对每个方法读取源码、相关 fixture/helper 和合同，核对参考来源、实际断言及可检测的故障。
六组独立 Spec 审查按模块分工，主协调者交叉核对旧审计与新结论，另由独立 Spec 和 Standards
审查汇总结论、强反例、身份与分母。针对疑点运行了独立算术、合成轨迹校准和有限匹配内核探针。

“未发现具体缺陷”是静态审查结论，**不等于全部 oracle 已完成独立数值认证或故障注入**。
方法里的参数组合、连续输入域和全部消费者并未因此穷尽。3257 是 Python unittest 方法数，
包含 12 个由同一工厂生成的不同 case 方法，来自 3246 个定义位置。
Rust 私有回退测试、外部 benchmark、完整 Verilog-A 语言覆盖不属于这个分母。
Spectre 按用户指示继续待跑，不增加 backend 对齐资格。

| 原 CI 结果 | 方法数 | 含测试问题 | 证据不足 | 静态未发现缺陷 |
| --- | ---: | ---: | ---: | ---: |
| 通过 | 2617 | 32 | 8 | 2577 |
| 断言失败 | 423 | 293 | 62 | 68 |
| 执行错误 | 214 | 51 | 25 | 138 |
| 预期失败 | 3 | 1 | 0 | 2 |

表中两种维度不能互相替代。当前 637 项失败/错误仍是执行事实，不能从本表直接推算 EVAS bug 数。
一个失败方法里的旧诊断断言可以有错，同时其未执行的数值义务仍暴露实现问题。

## 已经用具体证据确认的问题

1. **参考答案依赖被测结果，漏检真实输入误差。**
   `SourceMath.test_small_true_source_box_encloses_both_independent_endpoint_roots`
   从 EVAS 返回的输入盒取端点，再算“独立”输出参考。若把请求的输入误差带丢成一个点，
   并同步缩窄输出盒，错误响应仍通过真实公共协议检查及原测试。
   正确源带通过、错误输出被拒绝的对照也已运行。
   见 `L6-F12` 与 [lane6-probe-sourceband.json](evidence/lane6-probe-sourceband.json)。

2. **数值断言没有执行，方法仍然通过。**
   三个 RootRecovery 方法通过原始 `_invoke`/observe 路径读取结果，缺少公共接口的完整性校验。
   空或只含前两个样本的轨迹会跳过后续循环。合成校准实际调用原方法，保留其他断言，
   正确数值通过、错误数值被拒，而空/截断轨迹仍通过。其正控使用旧方法要求的 runtime-only
   事件元数据，只证明断言检出力漏洞，不称其为完整合法的 IR33 响应。见 `L6-F11`。
   另有两项同类原测试校准见 [lane3-probe-results.json](evidence/lane3-probe-results.json)。

3. **负控击中了错误层。**
   部分 raw IR 变异仍向旧 RHS 位置写入 `args` 或 `function`，当前该位置是 `RealBoundary`。
   内核以 `invalid_request: unknown field` 拒绝，原断言因此通过，整数原语参数检查尚未执行。
   另一个“采样误差传播到未来电压”的通过方法，在启动时 `u=0±0.01` 的条件判断就被拒绝，
   没有走到目标 timer 与后续输出。见 [lane5-probe.json](evidence/lane5-probe.json)、[rejection-path-probe.json](evidence/rejection-path-probe.json)。

4. **预期失败遮住了已经正确的目标结果。**
   `IndependentDriverCondition.test_state_driver_condition_reads_independent_voltage`
   在匹配内核上得到 `u=[1,1,1,1,1]`、`y=[0,0,1,1,1]`，符合独立手算。
   当前失败来自事件列表 `[0,0,0.5]` 与旧 `[0.5]` 断言冲突，两个 0 是初始化记录。
   这只能证明该原案例的目标电压已满足，不能据此关闭整个能力或 issue。
   见 [coordinator-probes.json](evidence/coordinator-probes.json)、[independent-driver-actual.json](evidence/independent-driver-actual.json)。

5. **旧数值参考越过了程序舍入边界。**
   RootRecovery 的一个 filter 子请求复用未舍入采样公式。
   按原程序逐次 RN 后，`y(1.5)` 的参考约为 `0.6065306597`，旧 helper 约为 `0.89776`，
   差约 `0.2912`，远超原 `1.01e-6` 预算。此处不能通过放松容差或修改 EVAS 去追旧答案。
   同类问题还包括程序条件、Floor、已存储状态和部分初始化参考。见 `L6-F09`。

其余发现包括旧初始化计数/快照、过期 IR 结构、失效资源增长假设、同过程事件顺序、
诊断代码与测试辅助器迁移。精确方法、子例、证据和限制见逐项表与各 finding，不能按文件名批量改答案。

## 本次主动排除的误判

- 公共 `solve`/`transient` 会验证样本数量、时刻和有限值。缺少局部 `len` 断言的 `zip`
  并不自动有空遍历漏洞；本次独立正控、空/额外样本及 NaN 校准确认了这一点。
- 程序 `real` 的 RN、直接连续方程和算子输入必须按具体上下文区分。
  直接连续 Select 没有程序采样边界时，不能用“相邻 binary64 中没有程序值”否认其物理窄区间。
- 一个近似参考与逐次 RN 不完全相等，并不自动使测试错误。
  必须检查实际可观察查询与误差预算；passive-history 与 held-timer 的若干初步疑点因此撤回，理由保留在审查记录。
- 存储已完成 RN 后，后续连续贡献仍可能有不可表示的真实电压误差。
  不能把所有“放大后必须拒绝”都改成成功。
- 不同事件记录具有相同浮点时间，不足以证明它们属于同一次逻辑发生。
  跨过程或不同周期时钟的争议继续保留，不批量套用源码顺序。

语言依据使用 [Verilog-AMS LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的 real 存储、求值顺序及过程语句条款；EVAS 的有限能力、证明与诊断仍须遵守对应项目合同。
项目 ADR 是开发合同，不能单独证明所有具体实现都满足语言标准。

## 后续开发应按什么顺序推进

| 优先级 | 工作 | 完成判据 |
| --- | --- | --- |
| P0 | 修复会让错误对象通过的检查器、raw 负控、空轨迹及过期 xfail | 原错误响应必须被拒；合法响应通过；负控实际到达目标校验层；保留原案例与分母 |
| P1 | 按实际程序/物理边界修正已证实的参考、初始化记录及结构断言 | 独立推导、原输入/预算、正确与错误对照齐全；有冲突的子例拆开说明 |
| P1 | 逐项关闭本表的契约/参考缺口 | 先明确语言要求、EVAS支持范围、允许误差与拒绝条件，再决定改测试还是改实现 |
| P2 | 用可信且有区分力的案例选择 EVAS 实现修复 | 有原案例、明确可观察要求、独立参考和当前失败路径；按同一验收对象验证修复与回退 |
| P2 | 补能力组合、历史/回退及真实源误差的检测缺口 | capability关联只是导航；新增证据须说明检测哪种故障，不能只增加方法数 |

后续每项实现修复应绑定“原模型与刺激 → 合同 → 独立答案 → 实际断言/反例 → 固定版本执行”。
有测试问题的条目先修受影响断言；证据不足的条目暂不单独作为实现修改依据。
保留方法中的有效义务，不删除失败用例、不批量改成当前输出、不扩大预算来换绿灯。
同一原案例通过后再检查受影响消费者和回退，Spectre 仍作为明确待补的独立证据。

## 逐项材料与可复核性

- [methods.tsv](methods.tsv) 保存全部方法的执行结果、裁决、角色、合同、oracle、断言、引用和下一动作。`mixed` 的 359 项与 `test_defect` 的 18 项合计 377 项；`mixed` 表示方法仍有应保留的有效义务。
- [findings.json](findings.json) 保存 86 组发现、撤回理由和最终协调修正。没有把已撤回的 RN 怀疑继续计为缺陷。
- [summary.json](summary.json) 保存固定源码提交、332 个模块哈希、方法分母及结果交叉统计。逐方法源位置和哈希在表内。
- [review.json](review.json) 保存原独立 Spec、Standards 审查的结论、关闭事项及限制；它不代替发布整理后的差异审查。
- [provenance.json](provenance.json) 区分仓库内材料、公开 CI 和仅在本地保留的原始工作档案。哈希只标识原件，不表示该原件可公开下载。
- `evidence/` 保存支持当前结论的精简探针结果；[主要参考](evidence/primary-references.json)登记语言规范来源。部分内核探针保留观察结果，未发布完整重放工具，不能把本目录称为所有证据的完整离线重放包。

原 3255 项的 capability 关联仍在[历史对齐表](../capability-audit/methods.tsv)。该关联是导航，
不是逐方法支持认证；新加入的两个查询方法在本表单独审查。原失败分类只描述当时首先失败的义务，
本表评价整个方法，不能直接把两个维度相减。

在含固定源提交的仓库根目录运行以下命令。第一条核对记录、引用、分母和 Git 中的源哈希，
不重新证明人工裁决。后四条运行原方法的有限校准或独立算术，不启动仿真内核。
校准要求当前 `evas/src`、测试及相关输入仍与固定版本一致；以后源码变化时应使用该版本的独立 checkout。
输出必须是本目录以外的新文件，不能覆盖已保存的证据。

```sh
python3 -B experiments/backends/support/ir33-recovery/method-audit/verify.py --repository .
python3 -B experiments/backends/support/ir33-recovery/method-audit/probes/lane3-probe-checks.py --repository . --output runs/method-audit-replay/lane3.json
python3 -B experiments/backends/support/ir33-recovery/method-audit/probes/lane6-probe-rn.py --repository . --output runs/method-audit-replay/rn.json
python3 -B experiments/backends/support/ir33-recovery/method-audit/probes/lane6-probe-sourceband.py --repository . --output runs/method-audit-replay/sourceband.json
python3 -B experiments/backends/support/ir33-recovery/method-audit/probes/lane6-probe-vacuity.py --repository . --output runs/method-audit-replay/vacuity.json
```

校准应重现原审计缺陷：lane3 两个不完整响应仍通过；SourceMath 的正确响应和丢失输入误差带响应
均通过，错误输出被拒；RootRecovery 三个方法接受空/截断轨迹，但拒绝错误数值。
这不是修复后的通过证据。RN 算术应得到 filter 差约 0.2912，并保留连续放大必须拒绝的反例。

本批未修改 EVAS 源码、原测试、容差、预算或 capability 成绩。3257 项原 CI 结果完整保留，
审计提供后续验收目标的筛选依据，不宣称实现已修复。既有下降根前 1 ULP 的状态保持反例仍在
[procedure-consumers.json](../procedure-consumers.json) 中，未因审计而关闭。
