```json
{
  "scope": "仅限 F20 数值证明审查：commit 81a8615b 与 e6b3e27b 的差异中，(1) operators.rs 的 sin_reduced/cos_reduced 将 Lagrange 余项从整个认证域半径 limit 收紧为当前缩减区间半径 r.lo.abs().max(r.hi.abs())；(2) idtmod.rs certificate() 将普通非点相位也路由到 exact_source::Curve.wrapped 的原始 binary64 源精确有理证书（原仅同 turn 点相位早退）。配套审查 interval.rs 向外舍入、exact_source.rs 有理包裹/半开区间处理、pwl.rs 来源计数与 add_enclosed_source 的 provenance 排除、operators.rs 中 sin 消费 idtmod 的多段并集界，以及保留的 replay/independent-check 证据与 red 负控日志。F14（连续 ddt/物理 PWL 斜率）仅作上下文，不在结论范围内。",
  "standards": [
    "验收参考为编译后 binary64 IR 系数与原始 binary64 PWL 点在实数算术下的解析积分（docs/math/operators.md 明示），不把已舍入代表值或派生 clamp 端点当精确参考。",
    "所有区间运算必须向外舍入；证书缺失、预算超限、turn 不可表示时按 waveform_accuracy/event_resolution 拒绝，不得静默放宽。",
    "idtmod 相位半开区间 [offset, offset+modulus)；wrap 侧别由精确符号证明决定，不得用区间中点选侧。",
    "生成/包围源的非零误差必须使其精确曲线不可用（provenance 排除）；仅原始请求输入可确立事件时刻。",
    "不采信作者测试 PASS 作为证明；以 supplied 源码与保留的原始请求回放/独立 Fraction/Decimal 复核为证据。"
  ],
  "spec": "独立推导与核对结论：(1) Taylor 余项数学正确性——sin 截断至 17 阶（配对 (2,3)..(16,17) 覆盖 r¹..r¹⁷/17!）、cos 截断至 18 阶（(1,2)..(17,18) 覆盖 1..r¹⁸/18!），Lagrange 余项 |R|≤R^19/19!（sin）与 R^20/20!（cos），因 f^(19)/f^(20) 为 ±sin/±cos 且绝对值 ≤1，对任意 R 全局成立，不依赖项递减假设；R=max(|r.lo|,|r.hi|) 正确界住连续区间上幅值（幅值在端点取最大）。taylor_remainder 用区间幂/区间阶乘（≤20! 在 f64 精确可表示）加 .hi.next_up()，保守向外。(π/2)^19/19!≈4.37e-14 与文档声称的 4.38e-14 一致，解释了修复前 F20 在 y≈0（预算≈1e-14 绝对项）被余项挡住、修复后通过。(2) idtmod 非点普通相位证书——certificate() 仅在 raw 为点且同 turn 时保留区间路径；非点时进入 exact_source.wrapped，后者以精确有理梯形积分原表达式曲线、floor 取 turn、半开输出并在舍入 nominal 触到排除上端点时 next_down、低于 offset 时 next_up，最终以有理比较验证 converted∈[off,upper) 且包围 exact wrapped，逻辑自洽且比区间路径更贴近文档定义的实数参考。输入不确定性来源（source_errors>0 → exact_sources 条目为 None → Curve::expression 返回 None）被正确排除，负控测试 generated_source_error_cannot_supply_an_exact_ordinary_phase 与 pwl.rs 的 original_source_count 门（零误差生成源不获得 guard 原始身份，但按文档契约可为相位提供其自身 PWL 的精确来源）覆盖了该边界。(3) 消费链——bounds_reusing 中 sin(IdtMod) 走 value_bounds_segments 并对各相位段分别 sin_bounds 取并集，wrap 两侧不被丢弃；wrapped 证书生效时段数为 1 且为亚 ulp 级，符合 F20 输出。(4) 证据链——red-strobe.log（bound 1.395e-14 > 预算 1.094e-14，对应仅 Taylor 修复后的中间态）与 frozen-before Linux 原始失败（4.66e-14 > 1.0e-14）数值上与‘余项贡献≈4.4e-14、相位区间宽度≈1.4e-14、精确相位证书再收敛至亚 ulp’的归因一致；release 回放 172 行与 independent-check.py（F(.125)+F(750000)*F(t) 的 Fraction 相位、F(6.2831853071795862) 精确角度、80 位 decimal_sin，worst 5.45e-16 ≤ 1e-14+1e-10|y|）采用与内核相同的 compiled-binary64-IR 精确参考约定，参考公式核对无误；输出 JSON 中相位 0.9999999999999999（未钳到 1）及 wrap 邻域 y≈1e-15 量级通过，半开约定在结果中可见。综合判断：F20 两项数值修改在所供代码与证据范围内正确、保守且未放宽任何验收。",
  "findings": [],
  "missing_context": [
    "F14 实际改动的 continuous.rs / test_continuous_dynamics.py 源码未提供，无法核对其‘物理原始 PWL 结点斜率’实现（按题目声明排除于结论外）。",
    "原始 batch-v2 Linux 侧 precision_run.py worker 的 strobe 注入语义未提供，replay-release.py 以 strobetimes=ts 复现是否与原始 harness 完全同构只能采信头部声明。",
    "kernel 二进制 sha256、requested_times.json 的确切 172 行计数、以及 red/phase/ddt 负控日志的产生 commit（声称为父提交 e6b3e27 或中间态）无法在只读文本下独立验证。",
    "experiments/backends 与更早 PR 的 Spectre 对照原始数据未提供（本审查按声明将其排除）。"
  ],
  "limitations": [
    "静态只读审查，未执行任何代码、测试或重放；PASS/172、独立检查日志按保留工件采信但未复现。",
    "结论限定为 F20 冻结模型（idtmod 常量输入 + sin 线性消费）及所供代码路径；不构成对一般 sin 大幅角、非二进制系数组合、多物理源 idtmod 或连续时间全轨迹精度的证明。",
    " tightened 余项仅在缩减后 |r| 小且 |y| 小（预算由绝对项主导）时产生实质收益；phase 中段（|r|≈π/2）余项仍≈4.4e-14，由 reltol 项覆盖，属既有设计而非缺陷。",
    "非点相位现在每次查询都尝试有理 wrapped 计算（O(结点数) BigRational），在 200k 运算预算内正确但可能有性能影响，未获性能证据。"
  ]
}
```
