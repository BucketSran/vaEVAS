```json
{
  "scope": "F14 专项数值证明审查：commit 81a8615b 相对 e6b3e27e，在 continuous.rs::build_segments 中对仅含原始物理 PWL 输入的传播段改用原折点斜率（Trajectory::range），替代跨微小 strobe 区间的插值端点差商；包含 pwl.rs/interval.rs 证据、公开与 Rust 测试、以及 runs/strict-q3-diagnosis 下保留的冻结原始请求、重放与独立核对工件。F20 与其它聚合/再分析改动按请求排除在结论之外。",
  "standards": [
    "向外舍入区间算术（interval.rs TwoSum 加法、精确乘积比较、除法外扩）必须覆盖物理折点斜率 (u_b-u_a)/(t_b-t_a) 的全部舍入",
    "证明资格仅限原始物理源：生成/钳位源即使 error==0 也不得获得原源斜率证明资格（has_only_physical_inputs 依据 original_source_count 与 source_errors）",
    "ddt/源斜率观察约定：内部折点取右侧导数、stop 取左侧、t=0 为 DC 零导数",
    "零时长段（start==end，含终点段）斜率必须为零且不得进入差商路径",
    "多物理源各自折点时刻互异时逐源独立取斜率",
    "重放必须保留原始 107/172 行 strobetimes、max_step、模型与 Q3 预算；正确性不得由作者 PASS 日志单独证明，需有独立 Fraction/Decimal 参照"
  ],
  "spec": "冻结原始 F14-base--Q3 请求：dut.va 为 V(y)<+9.9999999999999995e-07*ddt(V(u))，输入 u=[[0,0],[1e-6,.5],[2e-6,-.5],[3e-6,-.5]]，stop=3e-6，max_step=4.8828125e-10，reltol=1e-10，vabstol=1e-14，107 个请求时刻（含 1e-6/2e-6 两侧约 2ps/4ps 的紧密 strobe）。修复前 Linux release 与本地 red-strobe/ddt-red 均以 bound 5.551137327586275e-11 > budget 5.001000000005759e-11 拒绝；修复后 release-original-green.log 记录 F14 PASS 107，independent-check.log 记录 F14 独立核对 PASS 且 worst_abs_error=0。",
  "findings": [
    {
      "severity": "low",
      "file": "evas/rust_core/src/pwl.rs",
      "line": 244,
      "trigger": "Trajectory::range 在没有任何 PWL 窗口与查询区间相交时，derivectors.push(slope.unwrap_or(I::ZERO)) 静默返回零斜率。",
      "impact": "当前由 Trajectory::new 的输入校验（源覆盖 [0,stop] 且起于 0）保证不可达，故现版本无错误结果；但该静默零斜率是不变量被破坏时的潜在无声错误点（零斜率会被当作已证明的导数，而非保守拒绝）。",
      "requirement": "不可证明的情形应显式拒绝而非静默取零。",
      "recommendation": "将 unwrap_or(I::ZERO) 改为在区间与源覆盖不符时报 event_resolution 错误，作为防御性收口。"
    },
    {
      "severity": "low",
      "file": "evas/rust_core/src/continuous.rs",
      "line": 1275,
      "trigger": "has_only_physical_inputs() 要求全部源为原始物理源；混合场景（一个物理源 + 一个 add_enclosed_source 追加的零误差生成源）下，物理源的斜率也退回端点差商路径。",
      "impact": "混合源模型在紧密 strobe 间仍会出现文档所述 (e_a+e_b)/h 量级的保守放大，可能导致原本可接受的恒定导数被拒绝（保守失败，非错误结果）。",
      "requirement": "文档 continuous.md 已声明此取舍；属已声明的保守边界，非正确性缺陷，但审查确认其存在。",
      "recommendation": "后续可按源粒度区分资格：仅对生成源保留端点差商路径。"
    },
    {
      "severity": "info",
      "file": "evas/rust_core/src/pwl.rs",
      "line": 225,
      "trigger": "range() 的窗口选择条件 pair[0][0] < time.hi && pair[1][0] > time.lo：当传播段端点恰与源折点重合时，段末折点包含其左侧斜率、不包含右侧；段首折点包含其右侧斜率。",
      "impact": "经核对与文档约定一致（内部折点右导数、stop 左导数），且 green JSON 在 t=1e-6 给 -1.0（右侧）、t<1e-6 给 0.5、t=3e-6 给 0（左侧）、t=0 给 DC 0，与 independent-check.py 的半开区间段选择 pair[0][0]<=t<pair[1][0] 逐点一致。无需修改，仅确认边界语义闭合。"
    }
  ],
  "missing_context": [
    "exact_source.rs、exact_time.rs、operators.rs（phase/ddt 算子接入）、transient.rs/settlement_bounds.rs 的 waveform_accuracy 验收实现未随附全文，无法逐行复核验收侧如何消费斜率区间（只能由 green JSON 的 voltage_bounds_V 与通过结果间接印证）。",
    "F20-base--Q3 的模型源码（sin_reduced/cos_reduced 与 idtmod 相位证书）未随附，F20 部分仅由独立核对日志印证，按请求范围排除。",
    "runs/strict-q3-diagnosis 中仅保留了 F14/F20 两个 case 的重放与冻结工件；未提供 batch-v2 其余条件的完整原始失败清单以核对'无丢弃困难行'的全集声明。",
    "red-strobe.log 标注为 Taylor-only 中间修复后的 F20 部分复现，其对应中间提交源码未提供。"
  ],
  "limitations": [
    "本审查为静态只读，未执行任何代码；结论基于所供源文本与保留工件的一致性推理，不构成运行时验证。",
    "作者测试与 PASS 日志未作为证明依据；F14 的正确性结论主要来自：(1) build_segments 物理分支的斜率来自原始折点 f64 值的向外区间差/商（interval.rs 的 TwoSum、equal_products 精确性与 next_down/next_up 外扩，含次正规与溢出路径已有属性测试）；(2) 资格门 has_only_physical_inputs 由 original_source_count（仅在 Trajectory::new 固定）与 source_errors（原始源恒为 0、add_enclosed_source 追加即破坏等式）共同保证，生成源无法获得原源资格；(3) 零时长段在进入差商前被 start==end 分支截获并取零斜率；(4) 多源逐源窗口匹配；(5) 独立核对 independent-check.py 以 Fraction 构造 scale*(u_b-u_a)/(t_b-t_a) 参照且 worst_abs_error=0，逐点语义与折点侧别约定吻合。",
    "重放脚本 replay-release.py 确实从冻结 request.json/requested_times.json 读取原始 strobetimes、max_step 与容差并整体传入（strobetimes=ts），未见删行或放宽；但请求路径指向另一 worktree 的原始 batch-v2 目录，本次无法验证其内容哈希与 INPUT_IDENTITY.json 中冻结 sha 的一致性。",
    "本结论不覆盖：混合物理/生成源模型在紧密 strobe 下的接受性（见发现 2）、非 ddt 消费者的波形精度影响、以及跨平台/编译器差异；亦不构成对 F20 或其它数值改动的任何结论。"
  ]
}
```
