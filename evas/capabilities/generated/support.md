# 当前要求的四后端事实

view_status: current-default
adopted: true
provisional: false
adopted 只表示这是当前默认支持视图，不是新的项目决定，也不授予任何资格。

current_requirements: 10
source_index_items: 12880
source_index_is_requirement_coverage: false
规范源索引不是要求覆盖率。
historical_nodes: 78
historical_nodes_joined_to_current_requirements: 0
current_requirement_support_conferred: 0

## 当前要求

### requirement:$itor@1

sha256：`779220af0f65d2967caf011d1099f36b01f113d566f37a32c3a6647f947da671`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：2023 selected delta; voltage-domain analog context
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`reference:IEEE-1364-2005` version 1 sha256 8d88283385b189d25ca45e99ab0b19b6409a33a1c68b4048b71a0865b6426fcf kind source bound True path unknown origin IEEE-1364-2005 referenced by LRM 2.4
引用未决：LRM 2.4 incorporates Verilog HDL; conversion-function definitions and inherited language constructs require clause review.
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："Requirement card and independent boundary answers require review; selection alone is not support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["9.1 Table 9-8", "9.11"]
原文 required_boundaries：["positive and negative operands", "fractional and integral operands", "representation/range boundaries"]
原文 budget："pending applicable referenced definition; no inferred rounding rule"
原文 allowed_behavior："Permitted in analog context under selected 7920; actual conversion semantics depend on referenced IEEE 1364 definition."
原文 conditions：["definition and aliases", "domain and boundary", "analog context"]
原文 observables：unknown
就绪缺口：reference:IEEE-1364-2005@1: missing source identity
就绪缺口：reference:IEEE-1364-2005@1: pending
就绪缺口：requirement:$itor@1: pending
就绪缺口：requirement:$itor@1: review missing
关联案例：none

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:$rtoi@1

sha256：`803746845220bcb2683117ec390ac2df68ec0c56e1890c7a9712be799ff470ed`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：2023 selected delta; voltage-domain analog context
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`reference:IEEE-1364-2005` version 1 sha256 8d88283385b189d25ca45e99ab0b19b6409a33a1c68b4048b71a0865b6426fcf kind source bound True path unknown origin IEEE-1364-2005 referenced by LRM 2.4
引用未决：LRM 2.4 incorporates Verilog HDL; conversion-function definitions and inherited language constructs require clause review.
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："Requirement card and independent boundary answers require review; selection alone is not support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["9.1 Table 9-8", "9.11"]
原文 required_boundaries：["positive and negative operands", "fractional and integral operands", "representation/range boundaries"]
原文 budget："pending applicable referenced definition; no inferred rounding rule"
原文 allowed_behavior："Permitted in analog context under selected 7920; actual conversion semantics depend on referenced IEEE 1364 definition."
原文 conditions：["definition and aliases", "domain and boundary", "analog context"]
原文 observables：unknown
就绪缺口：reference:IEEE-1364-2005@1: missing source identity
就绪缺口：reference:IEEE-1364-2005@1: pending
就绪缺口：requirement:$rtoi@1: pending
就绪缺口：requirement:$rtoi@1: review missing
关联案例：none

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:bound-step-request-invariance@2

sha256：`5e5112073733e07cd3ec0103fa3f110f5ccbc6fe6e069eade07cfb13d606e2e0`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：LRM 2.4/2023 9.17.2 $bound_step in an ordinary analog block that also contains idt() and an input-driven procedural if whose predicate crosses its threshold inside a PWL ramp. Requirement: admission and waveform are invariant under adding or removing $bound_step(h), up to the certified voltage band.
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："procedure_plan.rs next_bound_time (1119-1141) executes the whole procedure on the accepted solution's certified_voltage_bounds; a straddling input predicate then fails in condition (445-477). Tests are linked through case:bound-step-request-invariance-python; calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["9.17.2"]
原文 required_boundaries：["predicate never crossing (t22: must stay accepted)", "algebraic program without idt (t18/t20: already accepted)", "threshold crossing exactly at a PWL corner"]
原文 budget：{"basis": "静态阅读", "pair_equality": "the two waveforms must agree within the sum of their certified bands; the exact integral is rational, so each is also compared with it directly", "voltage": "EVAS certified-path contract (docs/math/solving.md): |v - v_exact| <= vabstol + reltol*|v| at every returned point, using the bench settings (EVAS defaults vabstol=1e-12 V, reltol=1e-10 when the netlist sets none)."}
原文 independent_answers：[{"answer_file": "answers/b2_revised.json", "answer_sha256": "e7bfbf266fd3e470cb34fdd175222de11a9b3bd97de8476e8cc0fb353326c53a", "basis": "已执行验证", "bench": "repro nf12_t8/t14 tb.scs (heldout-0 PWL of v3-ota-continuous), stop 1.4 us, maxstep 250p", "enable_crossings_s": ["21/2000000000", "1701/2000000000", "1901/2000000000"], "method": "exact rational integration of the piecewise-affine integrand (trapezoid exact on affine pieces; split at enable crossings)", "model": "target=0.75+0.98*(V(vin)-0.75); if(V(enable)<0.75) target=0; V(q)<+idt(target/20n,0); [t14: + $bound_step(0.25n)]", "script": "scripts/b2_revised.py", "script_sha256": "a62e6982173b1e99dc7191fd582da495b9c19be9c5f12f0563f06580c6e7d485", "test": "t8_t14_exact_integral", "values": {"1/10000000": {"decimal": "3.474493125000000e+00", "exact": "5559189/1600000"}, "1/100000000": {"decimal": "0.000000000000000e+00", "exact": "0"}, "1/2500000": {"decimal": "1.453486312500000e+01", "exact": "23255781/1600000"}, "1/5000000": {"decimal": "7.356793125000000e+00", "exact": "11770869/1600000"}, "11/1000000000": {"decimal": "1.924612500000000e-02", "exact": "153969/8000000"}, "17/20000000": {"decimal": "3.722199812500000e+01", "exact": "59555197/1600000"}, "1701/2000000000": {"decimal": "3.726615462500000e+01", "exact": "298129237/8000000"}, "19/20000000": {"decimal": "3.726615462500000e+01", "exact": "298129237/8000000"}, "201/1000000000": {"decimal": "7.394146125000000e+00", "exact": "59153169/8000000"}, "21/2000000000": {"decimal": "0.000000000000000e+00", "exact": "0"}, "3/5000000": {"decimal": "2.728349812500000e+01", "exact": "43653597/1600000"}, "7/5000000": {"decimal": "5.197333812500000e+01", "exact": "83157341/1600000"}, "951/1000000000": {"decimal": "3.731031112500000e+01", "exact": "298482489/8000000"}}}, {"basis": "已执行验证", "derivation": "target 0 before the enable crossing at 10.5 ns; affine on [10.5, 11] ns; constant 0.77646 after; trapezoid exact on affine pieces", "script": "standard-line scripts/rev_batch2_after_r1_20261028.py (q_exact)", "test": "short_bench_exact_values", "values": {"10ns": "0", "11ns": "153969/8000000", "15ns": "279261/1600000", "20ns": "117969/320000"}}]
原文 allowed_behavior：{"implementation_choice": [{"basis": "推断", "text": "Evaluate the request on the statements it depends on (its value and activation slice), on the box of the current accepted time point (left/right limits at PWL corners), not by executing every procedural condition over the whole accepted-step box; or split the accepted step at the predicate roots before evaluating (window_roots in continuous_select.rs exists)."}, {"basis": "来源事实 (review r1 B2-ST-03)", "text": "Conservative application when the activation may be true stays allowed. Refusals stay allowed for an uncertifiable request value, numeric-domain errors, unsupported paths, precision limits and resource budgets (step budget, proof work). Only the NF-12b refusal is forbidden: refusing because an unrelated procedural predicate straddles its threshold over the accepted-step box."}], "lrm_mandated": [{"basis": "静态阅读", "text": "Use the request only to cap the next step; the solution of the program with and without the request is the same mathematical object."}], "must_not": [{"basis": "来源事实", "text": "Refuse a program because an unrelated procedural condition straddles its threshold over the accepted-step box used for the bound-step evaluation (procedure_plan.rs next_bound_time 1119-1141 -> condition 445-477, error at 467)."}]}
原文 conditions：["constant request (0.25n, 1u)", "PWL ramp crossing the predicate threshold off the output grid", "request inside a branch (conditional activation)", "request value depending on an input (dynamic)"]
原文 observables：["on the fixed resource-sufficient short bench (heldout-0 PWL, stop=20n, maxstep=250p): t8 and t14 both complete and V(vout) equals the exact values at 10, 11, 15, 20 ns", "on the step-check bench (t14 model, stop=20n, maxstep=5n): accepted_steps >= 80 = ceil(20n/0.25n) (mandatory); V(vout) equal to the same exact values", "negative control: the same step-check bench with the request removed completes with far fewer accepted steps (shows the step check is discriminating)", "no universal same-outcome claim across benches: resource and precision refusals remain legitimate", "state at d6b7543f: the short-bench t8 completes and t14 refuses with kernel.event_condition (review r1); the full 1.4 us t8 bench hits step_budget first"]
就绪缺口：requirement:bound-step-request-invariance@2: pending
就绪缺口：requirement:bound-step-request-invariance@2: review missing
关联案例：`case:bound-step-request-invariance-python`@1 sha256 be9ee7177a25f6cf282b381048221b28d43fc8eb98328443a068f6adef3ab721 状态 pending 审核 pending 测试 {"python-regression": 10}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:cross-event-body-right-limit@2

sha256：`4ba3ffa2012f92fb93a614b18f330d81c443c4be44fe10723c8bec421002a50a`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：Bodies of events triggered by cross leaves (single or OR'ed, with or without timer leaves) whose conditions, ternaries, if/else chains or loop conditions compare a quantity that is exactly zero at the crossing root tau (the crossing signal itself, a same-zero-set expression, a coincident unfired input, latched reads, floor arguments, histories).
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："Since 0097ef90 (inside #243) cross-triggered bodies read comparisons at tau (g(tau)=0) with no diagnostic; the documented tau+ rule and its certificates are not applied (bisect: last good 2a790344, first bad first-parent 5ab52780). Tests are linked through case:cross-event-body-right-limit-python and case:cross-event-body-right-limit-rust; calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["5.10.3.1", "5.10.3.3", "5.10.1", "4.2.12", "5.8.1", "5.9.1", "5.10.3.2"]
原文 required_boundaries：["root at stop: the event exists under the arrival convention; refuse unless arms identical", "plateau exactly at threshold (event fired at plateau entry under the arrival convention): >= true, > false", "PWL knot at the threshold (ordinary crossing or arrival): leaving segment decides", "touch and turn back (event fired at the touch under the arrival convention): u>=0.5 false", "window enclosure [0, e]: >= decided, > refused", "initial value exactly at the threshold: no event at t=0 (LRM 5.10.3.2); leaving the zero later does not fire (arrival convention)"]
原文 budget：{"basis": "静态阅读", "branch": "exact (no tolerance); every decided comparison follows a certificate or the run refuses", "time": "event times within the certified root window", "voltage": "EVAS certified-path contract for assigned real values"}
原文 independent_answers：[{"agreement": {"c_direction": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_or2_ternary": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_or3_ifelse": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_or3_ternary": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_single_ge": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_single_ge_dir": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "f_single_real": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "r_or2_gt": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "s_timer_or": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": true}, "s_while": {"right_limit == receipt expected": true, "value_at_tau == EVAS got": null}}, "answer_file": "answers/b2_right_limit.json", "answer_sha256": "b895b4bd287e6aa126e96d07b327d9a3667897d511b38e8d791796601b128c61", "basis": "已执行验证", "method": "exact event-level evaluation of the ten cases/ benches (binary64 corners as exact rationals); post-root sign from the leaving PWL segment", "note": "right_limit equals every case's expected value; value_at_tau reproduces every EVAS result on d6b7543f, i.e. the observed outputs are exactly the g(tau)=0 reading", "script": "scripts/b2_right_limit.py", "script_sha256": "3b20fb644b40f9e233693ea1903267af9913ac7c36d37f27b265f66e0b2d9b51", "test": "probe_cases_right_limit", "values": {"c_direction": {"receipt_expected": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 3.0, "1.5u": 2.0, "2.5u": 1.0}, "right_limit": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 3, "1.5u": 2, "2.5u": 1}}, "f_or2_ternary": {"receipt_expected": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 3.0, "1.5u": 3.0, "2.5u": 2.0}, "right_limit": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 3, "1.5u": 3, "2.5u": 2}}, "f_or3_ifelse": {"receipt_expected": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 3.0, "1.5u": 3.0, "2.5u": 2.0}, "right_limit": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 3, "1.5u": 3, "2.5u": 2}}, "f_or3_ternary": {"receipt_expected": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 3.0, "1.5u": 3.0, "2.5u": 2.0}, "right_limit": {"1.0u": 3, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 3, "1.5u": 3, "2.5u": 2}}, "f_single_ge": {"receipt_expected": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 2.0, "1.5u": 2.0, "2.5u": 2.0}, "right_limit": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 2, "1.5u": 2, "2.5u": 2}}, "f_single_ge_dir": {"receipt_expected": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 2.0, "1.5u": 2.0, "2.5u": 2.0}, "right_limit": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 2, "1.5u": 2, "2.5u": 2}}, "f_single_real": {"receipt_expected": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "receipt_got": {"1.0u": 2.0, "1.5u": 2.0, "2.5u": 2.0}, "right_limit": {"1.0u": 2, "1.5u": 2, "2.5u": 1}, "value_at_tau": {"1.0u": 2, "1.5u": 2, "2.5u": 2}}, "r_or2_gt": {"receipt_expected": {"1.0u": 1, "1.5u": 2, "2.5u": 3}, "receipt_got": {"1.0u": 1.0, "1.5u": 1.0, "2.5u": 2.0}, "right_limit": {"1.0u": 1, "1.5u": 2, "2.5u": 3}, "value_at_tau": {"1.0u": 1, "1.5u": 1, "2.5u": 2}}, "s_timer_or": {"receipt_expected": {"1.0u": 2, "1.6u": 2, "1.8u": 1, "2.4u": 1, "2.6u": 1}, "receipt_got": {"1.0u": 2.0, "1.6u": 2.0, "1.8u": 2.0, "2.4u": 2.0, "2.6u": 1.0}, "right_limit": {"1.0u": 2, "1.6u": 2, "1.8u": 1, "2.4u": 1, "2.6u": 1}, "value_at_tau": {"1.0u": 2, "1.6u": 2, "1.8u": 2, "2.4u": 2, "2.6u": 1}}, "s_while": {"receipt_expected": {"1.0u": 5, "2.5u": 0}, "receipt_got": null, "right_limit": {"1.0u": 5, "2.5u": 0}, "value_at_tau": {"1.0u": 5, "2.5u": 7}}}}, {"answer_file": "answers/b2_right_limit.json", "answer_sha256": "b895b4bd287e6aa126e96d07b327d9a3667897d511b38e8d791796601b128c61", "basis": "已执行验证", "script": "scripts/b2_right_limit.py", "script_sha256": "3b20fb644b40f9e233693ea1903267af9913ac7c36d37f27b265f66e0b2d9b51", "test": "exact_crossing_times", "values": {"falling 3->1 over [1us,2us]": {"0.5 V": "never (minimum 1 V)", "1.5 V": "33056565380087515/18889465931478580854784 s (1.75*fl(1e-6))", "2.5 V": "23611832414348225/18889465931478580854784 s (1.25*fl(1e-6))"}, "timer(0.5e-6, 1e-6)": "fl(0.5e-6) + k*fl(1e-6): never equal to a crossing"}}, {"answer_file": "answers/b2_right_limit.json", "answer_sha256": "b895b4bd287e6aa126e96d07b327d9a3667897d511b38e8d791796601b128c61", "basis": "已执行验证", "script": "scripts/b2_right_limit.py", "script_sha256": "3b20fb644b40f9e233693ea1903267af9913ac7c36d37f27b265f66e0b2d9b51", "test": "restored_test_expectations", "values": {"R1 test_fired_guard_predicate_sees_crossing_side, rising if(V(u)>0.5) q=2; else q=3": {"IR33 record format": "events: initial_step (q=0, p=0), then cross at 0.5 with after=[2, 0]; states at [0,.25,.75,1] = [[0,0],[0,0],[2,0],[2,0]]", "q": 2, "right_limit_u>0.5": true, "value_0097ef90_expects": 3}, "R2 test_floor_argument_on_an_integer_needs_its_bin_after_tau, w=DOWN": {"2*w(tau)": "1", "expected": "KernelError event_condition (floor argument exactly integral at tau with falling input: no certificate)", "q assigned (tau value)": 1, "q<1 at tau+ would be": true, "value_0097ef90_expects": "[0, 3]", "w slope after tau": -1}, "R3 same method, w=UP": {"IR33 record format": "[0, 3] (initial record + cross); semantic value unchanged", "bin over the right window": 1, "p": 3, "q<1": false, "w slope after tau": 1}, "tau": "1/2"}}, {"basis": "来源事实", "file_sha256_0097ef90_and_d6b7543f": "678597388cb60cb7baf1674a726cf15ec694d3cfc98f25f0cbd15fa5c0d7007f", "file_sha256_2a790344": "3d5fb66aeede7f0ee8e53da80a91489b9763d6354a87b761cfd5528c6b22e3bb", "method": "the 2a790344 version of test_cross_right_limit.py decides every branch by hand from the ramp directions (docstring); 15/15 passed on 2a790344 (CI 40114724924)", "test": "test_file_answers"}]
原文 allowed_behavior：{"implementation_choice": [{"basis": "来源事实", "id": "arrival-convention", "text": "EVAS convention, not an LRM rule (events.md:1269-1276 at d6b7543f; standard-line decision item SL-DEC-20261028-01, recommendation A, awaiting the coordinator): an exact zero belongs to the arriving segment. A guard pair (a, 0) with a nonzero fires once in direction -sign(a), filtered by dir, whether or not a next segment exists; this covers isolated zeros, zero-plateau entry and stop. Zero to zero and zero to nonzero do not fire; an initial zero plateau and an all-zero input do not fire. LRM 5.10.3.1 and 5.10.3.2 do not define these four degenerate cases."}, {"basis": "来源事实", "id": "timer-point-time", "text": "EVAS executes timer-triggered bodies, including an OR body fired by its timer leaf at the same instant as a cross, at the exact scheduled time and compares point values (events.md:1835-1838). This is the expected value for this batch; it is not a cross-backend tie answer, because a simulator placing the point just beyond the time may decide an exactly-at-threshold comparison the other way."}, {"basis": "来源事实", "text": "Documented EVAS contract (events.md@d6b7543f #cross-right-limit): read te=tau+; a comparison exactly zero at tau needs a post-root certificate: (1) fired leaf with an exact same zero set d=k*g, sign(k)*s with s the PWL side (segment end sign; at a knot the next segment; a zero end value is a proven plateau); (2) other stateless conditions: derivative enclosure of the accepted history on [lo, next_up(hi)] strictly signed, or exactly [0,0] (plateau); (3) right window W=[lo, next_up(hi)]: plateau (first-order dependence exactly zero on W, e.g. constant inputs, exact cancellation q=V(w); V(w)-q, floor/real-to-integer only when all of W lies in one bin) or a window enclosure that already decides the comparison."}, {"basis": "来源事实", "text": "Without a certificate return kernel event_condition; continue only when both arms behave identically. Loop conditions use the same rule (while loops are unrolled into guarded trips)."}, {"basis": "来源事实", "text": "Time-invariant equalities keep their value (the difference reads no input or operator column and no state assigned in this body from a voltage or history)."}, {"basis": "来源事实", "text": "Timer-triggered bodies, including an OR body fired by its timer leaf at the same instant as a cross, run at the exact time; an unrelated same-instant timer does not change a cross body's reads; a cross-triggered body in a batch that also contains a separate timer block uses only conditions without operator columns (this restriction does not apply to an OR body fired by its own timer leaf); paid history contexts install only the leaf side and charge right-window reads to the same ledger; budget/resource/IR errors are reported as such, not as missing certificates."}, {"basis": "来源事实", "text": "Known limit: assigned values use the tau root box (the right limit for continuous quantities); floor/rounding arguments exactly on a breakpoint at tau assign the tau value, so only exactly-zero comparisons are protected. Ordinary contribution Selects are continuous-time expressions and keep the g(tau)=0 decision."}], "lrm_mandated": [{"basis": "静态阅读", "text": "A cross-triggered body observes the post-crossing side: with exact PWL ramps, V(code)>=1.5 after a falling crossing of 1.5 is false and V(u)>0.5 after a rising crossing of 0.5 is true."}, {"basis": "静态阅读", "text": "A timer event occurs at a time point within time_tol of its scheduled time; without time_tol the point is at, or just beyond, that time (5.10.3.3). The LRM therefore does not fix a unique branch when a timer-body comparison is exactly at its threshold at the scheduled time."}, {"basis": "静态阅读", "text": "cross() generates no event at t=0 (5.10.3.2)."}], "must_not": [{"basis": "来源事实", "text": "Return the value at tau (g(tau)=0 treated as equality) without a diagnostic: observed on d6b7543f for single leaf, falling-only leaf, two and three OR leaves, ternary, if/else, integer and real targets, rising with strict >, and cross OR a non-coincident timer."}, {"basis": "来源事实", "text": "Choose a branch by a nominal or rounded sample when no certificate exists."}]}
原文 conditions：["rising and falling crossings; dir 0/+1/-1", "one, two and three OR leaves (including a leaf that never fires)", "ternary chains and if/else chains", "integer and real targets", "same-instant timer: separate block vs OR leaf", "knot exactly at the threshold, touch-and-return, plateau at the threshold", "latched reads (q=V(u) then compare q)", "floor argument on an integer at tau (falling vs rising)", "settled vs moving histories (transition outputs)", "loop conditions in a front-end-supported form", "paid history contexts", "root reached exactly at stop (no right side)"]
原文 observables：["value written by the body after each crossing (integer or real state, then the output contribution)", "refusal kind and message (kernel event_condition) when no one-sided certificate exists", "event records: crossing time, kind, before/after states (IR33 record format includes the initial_step record)"]
就绪缺口：requirement:cross-event-body-right-limit@2: pending
就绪缺口：requirement:cross-event-body-right-limit@2: review missing
关联案例：`case:cross-event-body-right-limit-python`@1 sha256 58ce678bac85cc39a1eec9f831288f0f989a50b2d2cda03bee42a1dc786711f4 状态 pending 审核 pending 测试 {"python-regression": 40}；测试关联只作导航，不授予要求级支持
关联案例：`case:cross-event-body-right-limit-rust`@1 sha256 0fa731b9c1e1ec8d126c1c4208eb5010aa6a1bc2359db0c20bbbcc2ece64ba02 状态 pending 审核 pending 测试 {"rust-tests": 4}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:event-observer-math-isolation@3

sha256：`dc5644b29a72fab7e6c66af63d2a5f9eb80871f7fb629bf55ba651d9fe763168`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：Meter modules whose event bodies compute ln-based dB values from accumulated state; the kernel requires an isolated observer event.
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："causal_event.rs:287-321: sampled-position inheritance stops at real_boundary wrappers (E-H root); isolated-observer rule at 317-321. Tests are linked through case:event-observer-math-isolation-python; calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["4.3.1 Table 4-14", "4.3.1"]
原文 required_boundaries：["fund/noise <= 1e-8 invalid path (no ln executed)"]
原文 budget：{"basis": "静态阅读 + 来源事实 (review r1 B2-SP-02)", "diagnostics": "a changed diagnostic text in any of the 9 methods that were green before #243 is a test-expectation change: it needs a standard-line signoff naming the old and new text; skip, expectedFailure or a wider tolerance are not allowed", "enclosure": "voltage_bounds_V of every report row must contain the high-precision answer; the box includes the source errors", "minimal_tests": "the acceptance tests of this card are the sampled-math tests already in test_group_math_sampled_domain.py: sqrt and ln positives (lines 94-121) with their own vabstol/reltol and box assertions, the strict positive-domain negatives and the future-amplification negatives (lines 148-172); each keeps its original numeric assertions and budget", "reports": "held report outputs of the meter, read at the strobe times after each completed record (completed_at_s plus one output row); for every reported quantity Q: |V - Q_exact| <= vabstol + reltol*|Q_exact| + e_dec, where vabstol and reltol are the effective controls echoed in observation_evidence (EVAS defaults 1e-12 V and 1e-10 when the bench sets none) and e_dec is the decimal truncation of the stored answer string (half a unit in its last printed digit; 5e-12 for 2.554206714999e+1); the high-precision value 25.542067149988333... (review r1, 80-digit DFT) lies inside this interval"}
原文 independent_answers：[{"answer_file": "answers/b4_history.json", "answer_sha256": "072bfe7df34d984f353b3cf88dbde161f788e2d4d7706080b4587a77cda049b3", "basis": "已执行验证", "script": "scripts/b4_history.py", "script_sha256": "5571e8fd453099cc17be1c35956cb586c816f40a324d02670c5e2656cb4fefb3", "test": "adc_db_values", "values": {"normal": {"completed_records": 1, "reports": [{"completed_at_s": "31601/100000000000", "dc": "2.048000000000e+3", "enob": "3.950509493354e+0", "fund": "1.799772697512e+5", "noise": "5.023552488055e+2", "sfdr_dB": "2.598843728573e+1", "sndr_dB": "2.554206714999e+1", "spur": "4.532876959543e+2", "valid": 1}], "samples_in_last_open_record": 64}, "private-0": {"completed_records": 1, "reports": [{"completed_at_s": "31601/100000000000", "dc": "2.048000000000e+3", "enob": "4.502673832623e+0", "fund": "2.591271883225e+5", "noise": "3.364366775466e+2", "sfdr_dB": "2.955069925023e+1", "sndr_dB": "2.886609647239e+1", "spur": "2.873710783789e+2", "valid": 1}], "samples_in_last_open_record": 64}, "private-1": {"completed_records": 1, "reports": [{"completed_at_s": "31601/100000000000", "dc": "2.048000000000e+3", "enob": "3.332989555284e+0", "fund": "1.351611674139e+5", "noise": "8.879575861497e+2", "sfdr_dB": "2.207150867245e+1", "sndr_dB": "2.182459712281e+1", "spur": "8.388823692787e+2", "valid": 1}], "samples_in_last_open_record": 64}, "private-2": {"completed_records": 1, "reports": [{"completed_at_s": "31601/100000000000", "dc": "0", "enob": "0", "reason": {"all_sample_ok": false, "first_low_sample_ok_index": 23, "in_range": true, "integral": true}, "sfdr_dB": "0", "sndr_dB": "0", "valid": 0}], "samples_in_last_open_record": 64}, "private-3": {"completed_records": 2, "reports": [{"completed_at_s": "31601/100000000000", "dc": "2.048000000000e+3", "enob": "3.921028966953e+0", "fund": "1.921852882123e+5", "noise": "5.588055376676e+2", "sfdr_dB": "2.576371716947e+1", "sndr_dB": "2.536459438106e+1", "spur": "5.097396570329e+2", "valid": 1}, {"completed_at_s": "63601/100000000000", "dc": "0", "enob": "0", "reason": {"all_sample_ok": false, "first_low_sample_ok_index": 23, "in_range": true, "integral": true}, "sfdr_dB": "0", "sndr_dB": "0", "valid": 0}], "samples_in_last_open_record": 64}, "private-4": {"completed_records": 0, "final": {"dc": "0", "enob": "0", "reason": "fewer than 64 clk edges before stop", "sfdr_dB": "0", "sndr_dB": "0", "valid": 0}, "reports": [], "samples_in_last_open_record": 32}}}]
原文 allowed_behavior：{"implementation_choice": [{"basis": "推断", "text": "Recognise meters whose outputs are held reports as isolated observers, or extend observer math to events that also read control nodes."}, {"basis": "推断", "text": "Make control() transparent to real_boundary(kind in {store, sample}) by passing 'sampled' to its value (E-H proposal, S). Keep the refusals pinned at test_group_math_sampled_domain.py:136-146 and test_event_statistics.py:134."}], "lrm_mandated": [{"basis": "静态阅读", "text": "Evaluate ln on the held values at the event."}], "must_not": [{"basis": "推断", "text": "Refuse with 'observer mathematics and control nodes require an isolated observer event' for a pure meter."}]}
原文 conditions：["slot 9 ADC meter (dB of fund/noise)", "slot 29 fixed comparator after the NF-10 bypass (prep finding a)"]
原文 observables：["held dB reports", "current diagnostic"]
就绪缺口：requirement:event-observer-math-isolation@3: pending
就绪缺口：requirement:event-observer-math-isolation@3: review missing
关联案例：`case:event-observer-math-isolation-python`@1 sha256 f3ebd93905a0b1b1a3d2d8a37ba226f176250e8405cb86966cbd52248a62de7b 状态 pending 审核 pending 测试 {"python-regression": 18}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:expm1@1

sha256：`40d49f23708f53f048e1f976444714306e554c2a745cc192b0b13a9b61d1f5ad`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：2023 selected delta; voltage-domain analog context
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："Requirement card and independent boundary answers require review; selection alone is not support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["4.3.1 Table 4-14"]
原文 required_boundaries：["x=0", "small positive and negative x", "large magnitudes within selected numerical domain"]
原文 budget："No invented universal tolerance; independent numerical acceptance pending review."
原文 allowed_behavior："exp(x)-1 for numeric real-domain operands; operands converted to real."
原文 conditions：["definition and aliases", "domain and boundary", "analog context"]
原文 observables：["expm1(x)", "$expm1(x)"]
就绪缺口：requirement:expm1@1: pending
就绪缺口：requirement:expm1@1: review missing
关联案例：none

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:idt-reset-argument-procedure-frame@6

sha256：`f441c8458b9f15ee52c0061b18d02a836eb75a79352a173240eeca76b2a7c29c`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：Front-end-accepted programs where a procedure-bound real (RealLocal: freq computed with clamps; upper_th = offset + 0.5*vhys) reaches a kernel consumer that only accepts closed expressions: the integrand of idt(expr, ic, assert) with an assert argument (slots 18, 20, 26 rewrites) or a cross expression (second-batch hysteresis comparator). The kernel returns kernel.invalid_ir 'unbound real value requires its procedure frame' instead of running or giving a typed refusal.
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："real_expression.rs:45-51 materialized() returns invalid_ir for procedure-bound reals (constant() has no RealLocal case); callers include operators.rs:1265 (reset_terms), affine_bounds.rs:95, events.rs:213, display.rs:139. Tests are linked through case:idt-reset-argument-procedure-frame-python and case:idt-reset-argument-procedure-frame-rust; calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["4.5.4 Table 4-18", "4.5.4"]
原文 required_boundaries：["assert released exactly at t0"]
原文 budget：{"basis": "静态阅读", "voltage": "EVAS certified-path contract: |v - v_exact| <= vabstol + reltol*|v| at every returned point; event times within the certified root window; integer and branch results exact."}
原文 independent_answers：[{"answer_file": "answers/b5_events.json", "answer_sha256": "6426889cada15f1526c27feeb40992a92a6415dedfdc6dd0ab5d279595096c76", "basis": "已执行验证", "model": "freq=1e6+1e5*V(c) (procedural, with if-clamps to [1e6,70e6]); y=idt(freq,0,a); V(y_out)<+y; c=1 V dc", "recheck": "review r1 recomputed 11/10, 11/5 (no reset) and 11/10, 11/5 after release at 3 us; 2a790344 completes and matches, d6b7543f returns invalid_ir", "script": "scripts/b5_events.py", "script_sha256": "cd63c61704c5de9192160adfae9e6bb7470bfd0fb68f701f82557c1c1fa2a9d9", "test": "r3n2_minimal", "values": {"a=0 (constant)": {"y(1us)": "11/10", "y(2us)": "11/5"}, "a=q (q=1 on [0,3us) via events, 0 after)": {"y(2us)": "0", "y(4us)": "11/10", "y(5us)": "11/5"}, "equivalence": "idt(x,ic,0) must equal idt(x,ic) at every time (assert never nonzero -> integrate from t0 with ic)"}}]
原文 allowed_behavior：{"equivalence_property": {"basis": "LRM 4.5.4 Table 4-18 (assert never nonzero -> integrate from t0 with ic); review r2 B2-R2-H1-01", "text": "For programs EVAS supports, adding or removing a constant-zero third idt argument does not change the outcome: either both complete with equal values and certificates, or both stop with the same refusal kind for the same cause. Legitimate refusals (resource budgets such as step_budget, precision, numeric domain, unsupported paths) stay allowed for both members; invalid_ir never is. This is a property, not a must_run requirement."}, "implementation_choice": [{"basis": "来源事实 (review r1 B2-SP-03)", "text": "Evaluate the procedural integrand in its procedure frame on the reset-capable idt path. A named typed refusal (for example unsupported_operator naming the integrand) is allowed only for programs outside the must_run set below; it is never a substitute for running the must_run programs."}], "lrm_mandated": [{"basis": "静态阅读", "text": "idt(x, ic, 0) equals idt(x, ic) at every time; with a state assert, hold ic while nonzero and integrate from the release instant."}], "must_not": [{"basis": "来源事实", "text": "Return kernel.invalid_ir for IR produced by compile_sources (Q9:B: internal errors are behaviour defects)."}, {"basis": "来源事实 (review r1 B2-SP-03)", "text": "Replace invalid_ir by another refusal for a must_run program."}], "must_run": [{"bench": {"max_step": "1e-06", "origin": "review r1 repro specs r1b_h1_zero.spec.json (d8b1ddf0...) and r1b_h1_state.spec.json (5aef25ef...)", "output_times": ["0", "1e-06", "2e-06", "3e-06", "4e-06", "5e-06"], "sources": {"c": [[0, 1], ["5e-06", 1]]}, "stop": "5e-06"}, "certificate": "voltage_bounds_V contain the exact values, half-width within vabstol+reltol*|v|", "expected": {"V(y)": ["0", "11/10", "11/5", "33/10", "22/5", "11/2"], "times": ["0", "1e-06", "2e-06", "3e-06", "4e-06", "5e-06"]}, "program": "r3n2 zero assert: module m(c,y); real freq,acc; integer a; analog begin freq=1e6+1e5*V(c); if(freq<1e6) freq=1e6; if(freq>70e6) freq=70e6; acc=idt(freq,0,0); V(y)<+acc; end"}, {"bench": {"max_step": "1e-06", "origin": "review r1 repro specs r1b_h1_zero.spec.json (d8b1ddf0...) and r1b_h1_state.spec.json (5aef25ef...)", "output_times": ["0", "1e-06", "2e-06", "3e-06", "4e-06", "5e-06"], "sources": {"c": [[0, 1], ["5e-06", 1]]}, "stop": "5e-06"}, "certificate": "as above", "expected": {"V(y)": ["0", "0", "0", "0", "11/10", "11/5"], "times": ["0", "1e-06", "2e-06", "3e-06", "4e-06", "5e-06"]}, "program": "r3n2 state assert: module m(c,y); real freq,acc; integer a; analog begin @(initial_step) a=1; @(timer(3u)) a=0; freq=1e6+1e5*V(c); if(freq<1e6) freq=1e6; if(freq>70e6) freq=70e6; acc=idt(freq,0,a); V(y)<+acc; end"}, {"bench": {"max_step": "1e-06", "origin": "review r1 repro specs r1b_h1_zero.spec.json (d8b1ddf0...) and r1b_h1_state.spec.json (5aef25ef...)", "output_times": ["0", "1e-06", "2e-06", "3e-06", "4e-06", "5e-06"], "sources": {"c": [[0, 1], ["5e-06", 1]]}, "stop": "5e-06"}, "expected": {"V(y) of each": ["0", "11/10", "11/5", "33/10", "22/5", "11/2"], "both complete": true, "values and certificates": "identical"}, "program": "r3n2 pair: the zero-assert program above and the same program with acc=idt(freq,0)"}]}
原文 conditions：["assert constant 0", "assert = held state written by events", "procedural integrand with if-clamps", "with and without $bound_step and events (prep and round3 diagnostics: all invalid_ir)"]
原文 observables：["integral output", "absence of kernel.invalid_ir for compiler-produced IR", "values and voltage_bounds_V of the must_run programs (the box contains the exact value, half-width within the budget)", "downstream DCO edges (slots 18, 20) and sweep reports (slot 26) on the original Benchmark files once their rewrites are returned (integration, not acceptance)"]
就绪缺口：requirement:idt-reset-argument-procedure-frame@6: pending
就绪缺口：requirement:idt-reset-argument-procedure-frame@6: review missing
关联案例：`case:idt-reset-argument-procedure-frame-python`@1 sha256 220fbcc6844ea0c1d623c5c8e7575cb4ff976e7831c4543f4f744dc503fec882 状态 pending 审核 pending 测试 {"python-regression": 12}；测试关联只作导航，不授予要求级支持
关联案例：`case:idt-reset-argument-procedure-frame-rust`@1 sha256 af0bdb9435df8f91765f92dfb684cd80999b69ba404ca132b6b96e171bc50c18 状态 pending 审核 pending 测试 {"rust-tests": 3}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:ln1p@1

sha256：`eacc51a292b3e1838711d2a37af6c30d9f808baa09699d4cd8a28d9d42e0a895`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：2023 selected delta; voltage-domain analog context
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
原文 gap："Requirement card and independent boundary answers require review; selection alone is not support."
原文 status："pending"
原文 review："pending"
原文 source_locations：["4.3.1 Table 4-14"]
原文 required_boundaries：["x approaches -1 from above", "x=0", "small positive and negative x"]
原文 budget："Not a language-mandated binary64 ULP budget; numerical acceptance pending review."
原文 allowed_behavior："Natural logarithm of 1+x for numeric x > -1; operands converted to real."
原文 conditions：["definition and aliases", "domain and boundary", "analog context"]
原文 observables：["ln1p(x)", "$ln1p(x)"]
就绪缺口：requirement:ln1p@1: pending
就绪缺口：requirement:ln1p@1: review missing
关联案例：none

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:output-point-limit@1

sha256：`b3e278bf5444893d9a14a2eba90589cc2d482bbe613b235e3b31ac870543edf0`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：EVAS transient request and SCS adapter contract (capability batch 2A); voltage-domain analog context; implementation resource limit, not a Verilog-A language rule
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
引用：`source:request-limits-contract` version 1 sha256 872a92e74ca2b12185f28bde54f1e0bf1963c884c97d893569ddea89736e94f9 kind source bound True path evas/docs/reference/proof-work-limit.md origin evas/docs/reference/proof-work-limit.md
原文 gap："Requirement card for capability batch 2A. Tests are linked through case:output-point-limit-python and case:output-point-limit-rust; review, calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：[]
原文 required_boundaries：["999999, 1000000 and 1000001 points", "floor(stop/maxstep) from limit - 2 to limit + 1", "100000 and 100001 rows", "pulse corners 4*periods + 2 around the limit"]
原文 budget："Exact for counts (integer equality) and messages (pattern match). Values on the 120001-row stateless-gain grid are within 1e-12 V (input) and 3e-12 V (output) of the closed form, compared with Fractions. The dynamic RC check holds every one of its 120001 rows to the request's own accuracy: |y - (1 - exp(-t))| <= absolute_V + relative*|y| with exp in 50-digit Decimal, where absolute_V = 1e-12 V and relative = 1e-10 are the SCS defaults (the deck has no options line) echoed in effective_controls; the certified voltage_bounds_V contain 1 - exp(-t) and their half-width is within the same tolerance. Discovery does not collect that check: CI runs it by name in the rust-regression job on every regression selection, with or without package, on a release kernel through scripts/run_explicit_checks.py, which fails unless it ran exactly once and passed, and the CI inventory records the step as a CI by-name check entry. A local run of that step is recorded in evas/capabilities/observations/capability-batch1-20261028/pr-evidence/rc-check-release.json in the capability batch 1 construction archive, sha256 e86536dbfb230d46195e61b18d1cdfba8f73620c43fd6cf395b6503c3f526c3f."
原文 normative_basis："No clause of LRM 2.4 or LRM 2023 limits the number of transient output or forced time points. MAX_OUTPUT_POINTS = 1000000 is an EVAS implementation budget recorded in evas/docs/reference/proof-work-limit.md and referenced by evas/docs/reference/strobe.md."
原文 related_source_locations：[{"clause": "8.3.2", "editions": ["2.4", "2023"], "relation": "Time points are the simulator's choice (\"The simulator controls the interval between the time points\"); the LRM fixes no count.", "title": "Transient analysis"}, {"clause": "9.17.2", "editions": ["2.4", "2023"], "relation": "A model may bound the step and so raise the number of time points; the limit does not change that semantics.", "title": "$bound_step task"}, {"clause": "5.10.3.3", "editions": ["2.4", "2023"], "relation": "Timer events add time points; forced strobe points are an EVAS request control, not an LRM construct.", "title": "timer function"}]
原文 target_scope_applicability：{"analysis": "transient requests and SCS transient decks", "included_groups": ["voltage-relations", "analog-state-events", "language-for-voltage-models"], "statement": "Applies to every voltage-domain transient request and SCS deck EVAS admits and changes only admission by point count. It admits no construct and no model outside the target: general-current-kcl, mixed-digital-ams, noise-ac-pss-rf, general-multistability and vpi stay excluded, and fine-grained clause membership stays pending.", "target_scope": "evas-voltage-domain-v1"}
原文 independent_answers：[{"derivation": "Output grid {k*maxstep < stop} U {stop}; the floor is computed with Fractions of the binary64 stop and maxstep.", "expected": "admitted while floor(stop/maxstep) + 2 <= 1000000; floor + 1 rows for an exact ratio", "observable": "SCS grid rows"}, {"derivation": "Points start + delay + k*period <= end, counted with exact rationals.", "expected": "floor((end - start - delay)/period) + 1", "observable": "periodic strobe count"}, {"derivation": "Explicit points on odd multiples of 2^-21 never meet periodic points on multiples of 2^-20, so the union size is the sum.", "expected": "size of the set union", "observable": "combined strobe count"}, {"derivation": "Four corners per period (rise start and end, fall start and end) plus the first and last points, from the pulse definition.", "expected": "4*periods + 2", "observable": "pulse corners"}, {"derivation": "The grid {0, .25, .5, .75, 1} contains no odd sixteenth or odd thirty-second, so the counts add.", "expected": "5 grid rows plus the distinct odd-sixteenth corners or odd-thirty-second points", "observable": "rows with source corners and saved rows"}, {"derivation": "Stateless gain driven by a PWL triangle: exact piecewise-linear arithmetic with Fractions on the 2^-20 grid.", "expected": "u is the triangle ramp and y = 3u", "observable": "large-grid values"}, {"derivation": "V(y) <+ idt(V(u) - V(y), 0) with V(u) = 1 V gives y' = 1 - y and y(0) = 0; exp is evaluated with 50-digit Decimal, without the kernel.", "expected": "y(t) = 1 - exp(-t); at stop = 120000*2^-20 s, y = 0.1081353699645114710...", "observable": "dynamic RC rows above 100000"}]
原文 allowed_behavior：["One limit of 1000000 points at the eight Python checkpoints (SCS grid, rows after including source corners, saved rows with forced points, pulse corners, explicit, periodic and combined strobe tables, response strobe_evidence.times) and at the kernel's strobetimes count; the Python and Rust constants are equal.", "A count within the limit is admitted; one more is rejected and the message names the limit in force, for example \"output point budget (1000000) exceeded\".", "The SCS grid is admitted while floor(stop/maxstep) + 2 <= limit; an exactly divisible stop/maxstep needs only floor + 1 rows, so admission is conservative by one row.", "Counts above the former 100000 boundary are admitted; unrelated budgets that share the number 100000 (netlist tokens, integer invariants, native audit) are unchanged.", "The limit changes admission only; admitted requests compute the same results as before."]
原文 conditions：["cap - 1, cap and cap + 1 at every checkpoint", "former 100000 boundary", "conservative grid bound", "message names the enforced limit", "Python and Rust constants agree", "end to end above 100000 rows"]
原文 observables：["admission or rejection and its message at each checkpoint", "number of output, saved and forced rows", "values on a 120001-row grid", "Rust: strobetimes count accepted or rejected by Trajectory"]
就绪缺口：requirement:output-point-limit@1: pending
就绪缺口：requirement:output-point-limit@1: review missing
关联案例：`case:output-point-limit-python`@1 sha256 c09f6a60e134f5aab7d8a74ea22838060efea744b4e9a0ea73a0fa5d88f71b59 状态 pending 审核 pending 测试 {"explicit-check": 1, "python-regression": 18}；测试关联只作导航，不授予要求级支持
关联案例：`case:output-point-limit-rust`@1 sha256 45ad6aeca6c399c1dca41d1cada81263851d2eb4a46545dc08b85129f985256c 状态 pending 审核 pending 测试 {"rust-tests": 3}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


### requirement:proof-work-limit@1

sha256：`183c2ab5059311e142a8c06212ae7d42f4a677675c40394d205e3bab6e920512`
语言配置字段：evas-va-2.4-plus-2023-v1
语言配置：`evas-va-2.4-plus-2023-v1` version 1，基础 2.4，选入 7780, 7920
范围：EVAS transient request contract (capability batch 1A); voltage-domain analog context; implementation resource limit, not a Verilog-A language rule
要求级支持：not_conferred
覆盖充分性：pending
coverage sufficiency is not defined for this requirement
readiness gaps are registry navigation, not a qualification verdict
引用：`lrm-2.4` version 1 sha256 afdb66b8baec11cb63e0572346862434fb6652faf3849a402c96bb02f03f13cf kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf
引用：`lrm-2023` version 1 sha256 86b19cb490fab45c0d8dbc077a3412a3dffdd4a553741ac196c825a0cbae3194 kind source bound True path unknown origin https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf
引用：`source:language-profile` version 1 sha256 96bad1a55d3da59d733ad376d4659e3ff6b821c9a0e5ab41ed6353e794453599 kind source bound True path evas/capabilities/data/language-profile.json origin evas/capabilities/data/language-profile.json
引用：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc kind source bound True path evas/capabilities/data/target-scope.json origin evas/capabilities/data/target-scope.json
引用：`source:request-limits-contract` version 1 sha256 872a92e74ca2b12185f28bde54f1e0bf1963c884c97d893569ddea89736e94f9 kind source bound True path evas/docs/reference/proof-work-limit.md origin evas/docs/reference/proof-work-limit.md
原文 gap："Requirement card for capability batch 1A. Tests are linked through case:proof-work-limit-python and case:proof-work-limit-rust; review, calibration and execution evidence are pending and the links confer no support."
原文 status："pending"
原文 review："pending"
原文 source_locations：[]
原文 required_boundaries：["N = 1", "N = 10000000000000", "N = 0 and N = 10000000000001", "2e12 written as a JSON float", "an integer beyond u64", "unset versus explicit 1000000000", "null in a CLI manifest versus a missing field", "default exhaustion versus completion at 1e10 for one 3000-row request"]
原文 budget："Exact for every control fact: echo, error kind, limit in the message, ledger slots and request bytes compare by equality, and the C8 comparison requires the echoed default as the integer 1000000000 before removing it. Raising the limit changes no numerical result: unset and explicit default give byte-identical responses; simulate_scs at 2e12 saves data equal to the default run; as one-time PR evidence and not a CI test, the default response through a kernel built from main d6b7543f equals the previous kernel's after removing only the echo key (receipt evas/capabilities/observations/capability-batch1-20261028/pr-evidence/main-kernel-checks-r3-final.json in the capability batch 1 construction archive, sha256 bf95d3f3cd876a6e072f4789678869aae25d71e15dbfea38cd2ef3a3636e50e5). Completed rows of the slew request are within the request's own tolerance absolute_V + relative*|y| read from effective_controls, which must equal the requested 1e-12 V and 0; rows are compared with Fractions. Exhaustion depends on the request bytes, because the ledger charges serialized program text: the two end-to-end tests name their source proof_limit.va, so the checkout path never enters their requests. Measured total work is 891444759 for 1000 rows (108555241 below 1e9, 841444759 above 5e7) and 2669543465 for 3000 rows (1669543465 above 1e9, 7330456535 below 1e10); each extra character of the source name adds 11061 and 33061 work, so the tightest margin, 1000 rows under 1e9, allows 9814 more characters. No universal tolerance is introduced."
原文 normative_basis："No clause of LRM 2.4 or LRM 2023 defines a proof-work budget. The limit is an EVAS request contract and implementation budget recorded in evas/docs/reference/proof-work-limit.md; it is neither a correctness criterion nor a performance promise."
原文 related_source_locations：[{"clause": "8.3.2", "editions": ["2.4", "2023"], "relation": "The LRM leaves the numerical method and its effort to the simulator (\"There are a number of different approaches to solving this problem numerically\"); it sets no work budget.", "title": "Transient analysis"}, {"clause": "4.5.8", "editions": ["2.4", "2023"], "relation": "EVAS charges the ledger while certifying transition() source plans; the operator semantics do not depend on the limit.", "title": "Transition filter"}, {"clause": "4.5.9", "editions": ["2.4", "2023"], "relation": "The end-to-end answers use slew(); the limit decides only whether certification finishes.", "title": "Slew filter"}, {"clause": "5.10.3", "editions": ["2.4", "2023"], "relation": "Event certification inside a transient request draws on the same ledger.", "title": "Monitored events"}]
原文 target_scope_applicability：{"analysis": "transient requests only; the static solve path keeps its fixed default ledger and has no request field", "included_groups": ["voltage-relations", "analog-state-events", "language-for-voltage-models"], "statement": "Applies to every transient request EVAS admits in the voltage-domain target. It admits no construct and no model outside the target: general-current-kcl, mixed-digital-ams, noise-ac-pss-rf, general-multistability and vpi stay excluded, and fine-grained clause membership stays pending.", "target_scope": "evas-voltage-domain-v1"}
原文 independent_answers：[{"derivation": "Literals of the designed contract written in the tests, not read from the constants under test.", "expected": "1000000000 and 10000000000000", "observable": "default and hard bound"}, {"derivation": "Literal slots of the unchanged default ledger; only slot 2 takes N.", "expected": "[128, 8192, N]", "observable": "ledger slots"}, {"derivation": "Request contract in evas/docs/reference/proof-work-limit.md; rejected shapes are written as raw JSON text so Python cannot normalize 2e12 or true.", "expected": "accepted exactly when the value is a JSON integer in [1, 1e13]", "observable": "accepted and rejected values"}, {"derivation": "u ramps from 0 to 1 on [0, 1]; the selected target becomes 1 once u > 0.5, i.e. after t = 1/2; slew(target, 1, -2) rises at 1 V/s. Evaluated with fractions.Fraction without the kernel.", "expected": "y(t) = min(1, max(0, t - 1/2)) on [0, 2]", "observable": "slew end-to-end rows"}, {"derivation": "Differential reference: the same request unset and with the explicit default (collected tests), and, as one-time PR evidence and not a CI test, through a kernel built from main d6b7543f before the field existed (receipt evas/capabilities/observations/capability-batch1-20261028/pr-evidence/main-kernel-checks-r3-final.json in the capability batch 1 construction archive, sha256 bf95d3f3cd876a6e072f4789678869aae25d71e15dbfea38cd2ef3a3636e50e5).", "expected": "identical response bytes apart from the echo", "observable": "the limit is not a numerical input"}, {"derivation": "The C8 kernel predates the field; for an unset request the contract echoes the designed default literal, so that key is the only mapped difference.", "expected": "the schema-33 response equals the C8 response plus effective_controls.proof_work_limit = 1000000000, an integer", "observable": "C8 comparison of a default request"}, {"derivation": "Request contract in evas/docs/reference/proof-work-limit.md: a present manifest field is a set value; only None in the Python API means unset.", "expected": "manifest_input naming transient.proof_work_limit before any kernel starts; a missing field is unset and an integer in range reaches the kernel", "observable": "null proof_work_limit in a CLI manifest"}, {"derivation": "The transient request section is closed to unknown fields (evas/docs/reference/proof-work-limit.md, compatibility), which is what makes a kernel without proof_work_limit reject it.", "expected": "invalid_request naming the field", "observable": "unknown transient field"}]
原文 allowed_behavior：["Unset: the request ledger is [128, 8192, 1000000000], the request bytes are those of the previous release (the field is not sent) and the response echoes effective_controls.proof_work_limit = 1000000000.", "Set to an integer N with 1 <= N <= 10000000000000: N is the work slot of every source-transition proof ledger the request builds, with one exception. Slots 0 and 1, the sharing between consumers and the no-refund rule for failed reservations are unchanged, and each ledger is sticky. A consumer shares a bound owner's ledger (source context, procedure, analytic sources) and otherwise builds its own from the same N, so one request can hold several: measured, the slew and RC requests hold the events ledger [128, 8192, N] and the operator-plan ledger [8192, 8192, N], and an analytic-source request holds the request ledger and the events ledger, both [128, 8192, N]. The exception is the transition-input form audit (operators.rs, transition_input): each call builds a fresh default ledger [128, 8192, 1000000000] that does not take N. The kernel admits at most 100000 IR values with container depth 96, which bounds one audit at about 6.9e6 work (measured at most 540847), so that ledger never binds.", "Every other value is rejected by the layer that receives it. In a kernel request, 0, above 1e13, negative, any float including 2e12 and 2000000000000.0, bool, string, JSON null and an integer beyond u64 are invalid_inputs. In a CLI manifest a present transient.proof_work_limit must be an integer in range: null and every other shape are rejected while the manifest is read (manifest_input, naming the field), before anything is sent, and omitting the field is the default. The CLI flag accepts decimal digits only, and only for transient and simulate. In the Python API None is the default and means unset (the request bytes are those of the unset request above); any other non-integer or out-of-range value raises ValueError before sending.", "Exhaustion reports step_budget with the limit in force (\"exceeds N\").", "The limit is request metadata, not part of the serialized config identity: a request that completes under two limits is charged the same work and returns the same values.", "A kernel without the field rejects it as invalid_request (fail closed); request_protocol_version stays null. This was checked once against a kernel built from main d6b7543f before the field existed, as one-time PR evidence and not a CI test (receipt evas/capabilities/observations/capability-batch1-20261028/pr-evidence/main-kernel-checks-r3-final.json in the capability batch 1 construction archive, sha256 bf95d3f3cd876a6e072f4789678869aae25d71e15dbfea38cd2ef3a3636e50e5). Under CI, test_kernel_rejects_an_unknown_transient_field_by_name keeps the same rule for any unknown transient field."]
原文 conditions：["default and explicit default", "range boundaries", "invalid value shapes", "natural exhaustion and completion under a larger limit", "sticky ledger without refunds", "echo and response validation", "Python, CLI and SCS surfaces"]
原文 observables：["observation_evidence.effective_controls.proof_work_limit", "error kind and message: invalid_inputs, step_budget (\"exceeds N\"), invalid_request", "transient rows and node voltages", "serialized request and response bytes", "Rust: ledger slots, serialized config identity bytes and the work they are charged"]
就绪缺口：requirement:proof-work-limit@1: pending
就绪缺口：requirement:proof-work-limit@1: review missing
关联案例：`case:proof-work-limit-python`@1 sha256 e58e3d4f856a45d7cac2e6c12eedbacdcaeca88c5cb7fa351287b470caa8dce5 状态 pending 审核 pending 测试 {"explicit-check": 2, "python-regression": 26}；测试关联只作导航，不授予要求级支持
关联案例：`case:proof-work-limit-rust`@1 sha256 43cd6be84a7f3a547e9662060f5c862198ce1d06dbb77dc2cc769cbe0abaf7ff 状态 pending 审核 pending 测试 {"rust-tests": 12}；测试关联只作导航，不授予要求级支持

| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Spectre | unknown | unknown | unknown | unknown | unknown | unknown |
| ngspice + OpenVAF-R | unknown | unknown | unknown | unknown | unknown | unknown |
| Gnucap + modelgen-verilog | unknown | unknown | unknown | unknown | unknown | unknown |
| EVAS | unknown | unknown | unknown | unknown | unknown | unknown |


## 未绑定当前要求的资格

资格记录：qualification:sef-registration-example@1 sha256 6ec74a49a91bac6807d9b675257ea922221441b4b96d7112999a58f9fc104287
current_qualified: false
historical_qualified: false
counts_as_current_support: false
confers_requirement_support: false
资格范围：SEF current calibration registration example only
资格后端原文："unknown"
执行：recorded:"passed"
完整性：recorded:true
数值：unknown
工具链：unknown
证据：missing_evidence
资格未决说明：This example deliberately retains incomplete review; it grants no current EVAS or external-backend support.
资格缺口：analysis:sef-calibration-pr1@1: analysis not accepted
资格缺口：analysis:sef-calibration-pr1@1: case is not a bound case dependency
资格缺口：analysis:sef-calibration-pr1@1: pending
资格缺口：calibration:sef@1: approval is not a bound source dependency
资格缺口：calibration:sef@1: calibration review identity or scope missing
资格缺口：calibration:sef@1: execution is not a bound calibration-execution dependency
资格缺口：calibration:sef@1: pending
资格缺口：calibration:sef@1: review missing
资格缺口：calibration:sef@1: subject is not a bound checker-definition dependency
资格缺口：checker:sef@1: checker does not match its calibrated subject and scope
资格缺口：checker:sef@1: pending
资格缺口：checker:sef@1: review missing
资格缺口：checker:sef@1: subject is not a bound checker-definition dependency
资格缺口：example:existing-positive@1: case scope or requirements missing
资格缺口：example:existing-positive@1: inputs is not a bound case-inputs dependency
资格缺口：example:existing-positive@1: pending
资格缺口：example:existing-positive@1: review missing
资格缺口：execution:sef-calibration-pr1@1: inputs is not a bound case-inputs dependency
资格缺口：execution:sef-calibration-pr1@1: raw_report is not a bound source dependency
资格缺口：qualification:sef-registration-example@1: analysis does not bind the selected case
资格缺口：qualification:sef-registration-example@1: analysis/review does not identify the selected case
资格缺口：qualification:sef-registration-example@1: pending
资格缺口：qualification:sef-registration-example@1: qualification differs from the executed backend identity
资格缺口：qualification:sef-registration-example@1: qualification differs from the reviewed case scope/requirements
资格缺口：qualification:sef-registration-example@1: qualification exceeds or differs from the reviewed claim
资格缺口：qualification:sef-registration-example@1: qualification requires scope, requirements and backend
资格缺口：qualification:sef-registration-example@1: review does not bind the selected case
资格缺口：qualification:sef-registration-example@1: review missing
资格缺口：review:sef-calibration-pr1@1: case is not a bound case dependency
资格缺口：review:sef-calibration-pr1@1: evidence is not a bound source dependency
资格缺口：review:sef-calibration-pr1@1: missing independent approval identity and claim
资格缺口：review:sef-calibration-pr1@1: pending
可定位版本：`analysis:sef-calibration-pr1` version 1 sha256 735a60e19d8f71c369f1bb50ec58b98b74baecffd3e348b86ff2a9bc3cb8ccfb selected true
可定位版本：`calibration:sef` version 1 sha256 dfa64101eb8614ece6a6e88d0e7cc06f12815c5b44eef52370b88fed991f7e61 selected true
可定位版本：`checker:sef` version 1 sha256 e36eac6e1d42cd35779c720365c5e9d571951f527dcad9eeaa5321d163f1316b selected true
可定位版本：`example:existing-positive` version 1 sha256 8dd8b0ac8689197c097ee08f1208c6d1d08ef211f645ce692e06efea139154b6 selected true
可定位版本：`execution:sef-calibration-pr1` version 1 sha256 5c3f0567a4b7d70d3644f54f1529c737ba24945741cd5c9e08ef071b3fbf5bb1 selected true
可定位版本：`qualification:sef-registration-example` version 1 sha256 6ec74a49a91bac6807d9b675257ea922221441b4b96d7112999a58f9fc104287 selected true
可定位版本：`review:sef-calibration-pr1` version 1 sha256 3bb9baa2f4fe869de6234d5f0a2417c616c42475a014eabdf741bf9e171660a0 selected true
可定位版本：`source:existing-positive` version 1 sha256 6ca4e89199f661b352ae5bf7c7c0ec9c6d3d8d902e1324f23bf41a7bb5de3970 selected true
可定位版本：`source:sef-calibration` version 1 sha256 d0587738903d93870ca2a1e6e56edb5f70375fe3bc2a7932e195a932faeb5244 selected true
可定位版本：`source:sef-calibration-execution` version 1 sha256 6bdbe88bf9701506011e54bf8f0b0d1d6e9864a27b45a1d6881d5bedb46a3c0f selected true
可定位版本：`source:sef-contract` version 1 sha256 6a0d4c879b0cfb29a50866a8e0a6855fb849c2208f0356aaa1bd93613f4ff4d3 selected true
可定位版本：`source:target-scope` version 1 sha256 bbc16ec9f813042a44b714014359fef63bbf28e2c43a113f4aa5868bcd0264cc selected true
执行记录：execution:sef-calibration-pr1@1 执行 recorded:"passed" 完整性 recorded:true 数值 unknown
分析结论：analysis:sef-calibration-pr1@1 recorded:"pending-scope-review"
分析数值：analysis:sef-calibration-pr1@1 unknown

## 历史引用

identity: historical-comparison-import-f210ebd5
source: evas/docs/COMPARISON.md
scope: Historical transcription; not qualification for current main
这些节点保持原身份。它们的格子不是当前要求的执行、完整性、数值、资格或证据。

### 历史 macro-include

title："宏与 include"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "层次语法编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 parameters

title："参数"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "层次语法编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 conditions

title："条件与逻辑表达式"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 case

title："case 分支"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sequential-assign

title："顺序赋值"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 user-function

title："用户函数"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 static-loop

title："静态循环"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 array-static-index

title："变量数组：静态下标"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 electrical-vector

title："电气向量"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 hierarchy

title："模块层次"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sin

title："sin"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 cos

title："cos"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 exp

title："exp"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 ln

title："ln"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sqrt

title："sqrt"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 pow-cube

title："pow：三次幂"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 pow-half

title："pow：半次幂"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 voltage-contribution

title："电压访问与贡献"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 static-voltage-feedback

title："静态电压反馈"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 initial-step

title："initial_step"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "编译或初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 cross

title："cross：斜坡穿越"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "漏事件", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 timer

title："固定 timer"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 event-or

title："事件 OR：采样与复位"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "漏事件", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 transition

title："transition：定时非对称沿"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 absdelay

title："固定 absdelay"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 slew

title："固定 slew"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 idt

title："idt：非零初值与正负面积"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "✓ Q3", "spectre": "✓ Q2"}
in_current_denominator: false
counts_as_current_support: false

### 历史 idtmod

title："idtmod：原始相位与环回"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "环回边界未验收", "spectre": "环回边界未验收"}
in_current_denominator: false
counts_as_current_support: false

### 历史 ddt-time

title："ddt：二次时间表达式"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q2", "ngspice": "误差超限", "spectre": "Q1 误差超限"}
in_current_denominator: false
counts_as_current_support: false

### 历史 ddt-input

title："ddt：电压斜坡平方"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q2", "ngspice": "误差超限", "spectre": "✓ Q2"}
in_current_denominator: false
counts_as_current_support: false

### 历史 laplace-nd

title："一阶 laplace_nd"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "非零初态错误", "ngspice": "✓ Q3", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 laplace-np

title："一阶 laplace_np"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 filter-second-order

title："二阶滤波（内部微分）"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "Q1 误差超限", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sample-hold-timer

title："采样保持：定时"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sample-hold-cross

title："采样保持：阈值"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "漏事件", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sample-reset-edge

title："采样、复位与输出边沿"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "漏事件", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 hysteresis-edge

title："迟滞比较器与边沿"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sample-integrate-timer

title："定时采样→积分：原模型"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "漏定时事件", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 sample-integrate-ordered

title："采样→积分：停止边界与非线性"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "停止边界未达标", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 integrator-cascade-reset

title："积分级联与复位"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "初始化失败", "spectre": "复位误差超限"}
in_current_denominator: false
counts_as_current_support: false

### 历史 nonlinear-filter-feedthrough

title："非线性输入与滤波直通项"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "Q1/Q2 误差超限", "spectre": "Q2 误差超限"}
in_current_denominator: false
counts_as_current_support: false

### 历史 filter-ddt-dc

title："滤波与微分：DC 直通项"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "✓ Q3", "spectre": "Q3 启动误差超限"}
in_current_denominator: false
counts_as_current_support: false

### 历史 two-absdelay

title："两个固定延迟的历史"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 two-slew

title："两级 slew 与反向追赶"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 interrupted-edge-integrate

title："中断边沿→积分"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "新版验收未跑", "ngspice": "新版验收未跑", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 array-event-update

title："数组的事件状态更新"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 chain-sample-hold-edge-filter

title："采样→保持→边沿→滤波"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "事件与输出错误", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 filter-then-sample

title："滤波→采样保持"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "采样历史错误", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 solve-delay-sample

title："电压求解→延迟→采样"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "编译失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 vco

title："VCO：扫频与原始相位"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "扫频误差超限", "spectre": "环回边界未验收"}
in_current_denominator: false
counts_as_current_support: false

### 历史 instance-integrator-reset

title："实例隔离：双积分器复位"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "编译失败", "spectre": "复位误差超限"}
in_current_denominator: false
counts_as_current_support: false

### 历史 instance-phase

title："实例隔离：双相位历史"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "编译失败", "ngspice": "编译失败", "spectre": "环回边界未验收"}
in_current_denominator: false
counts_as_current_support: false

### 历史 nonlinear-integral-filter-feedback

title："非线性积分与滤波联合反馈"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ Q3", "ngspice": "误差超限", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 event-dynamics-linear

title："事件改变动态：线性反馈"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "Q1 误差超限", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 event-dynamics-riccati

title："事件改变动态：Riccati 滤波"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "误差超限", "ngspice": "初始化失败", "spectre": "✓ Q3"}
in_current_denominator: false
counts_as_current_support: false

### 历史 near-timer-chain

title："近邻定时事件：原整链"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "✓ 1µV", "ngspice": "初始化失败", "spectre": "✓ 1 µV"}
in_current_denominator: false
counts_as_current_support: false

### 历史 near-timer-adjacent

title："近邻定时事件：相邻浮点采样积分"
status："compared"
review："recorded"
evidence："evas/docs/COMPARISON.md#支持矩阵"
results：{"evas": "✓ Q3", "gnucap": "回调同刻", "ngspice": "初始化失败", "spectre": "回调同刻"}
in_current_denominator: false
counts_as_current_support: false

### 历史 include-guard

title："include 保护"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："include 保护、条件编译的独立验收尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 parameter-range

title："参数范围端点"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："参数依赖与范围端点尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 loop-bounds

title："零次、一次与参数化循环"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："零次、一次与参数化次数的循环尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 array-declaration-order

title："数组声明方向"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："相反声明方向的数组尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 supply-reference-precision

title："供电与参考的统一精度"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："原 v2 四条件已测；统一精度流程中的供电依赖和对应观察尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 initial-threshold

title："初始阈值"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："初始阈值尚未逐项补齐。"
in_current_denominator: false
counts_as_current_support: false

### 历史 above

title："above"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："PROTOCOL 仍将 above 列为待补，独立答案尚未写入本登记。"
in_current_denominator: false
counts_as_current_support: false

### 历史 last-crossing

title："last_crossing"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："PROTOCOL 仍将 last_crossing 列为待补，独立答案尚未写入本登记。"
in_current_denominator: false
counts_as_current_support: false

### 历史 period-update

title："周期修改"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："周期修改尚未逐项补齐。"
in_current_denominator: false
counts_as_current_support: false

### 历史 schedule-cancel

title："旧日程取消"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："旧日程取消尚未逐项补齐。"
in_current_denominator: false
counts_as_current_support: false

### 历史 same-time-rules

title："同刻规则"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："同刻规则尚未逐项补齐。"
in_current_denominator: false
counts_as_current_support: false

### 历史 vco-gated

title："VCO 门控"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："门控 VCO 尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 vco-long-phase

title："VCO 长期相位"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："长期相位尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 phase-cross

title："读取相位的 cross"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："读取相位的 cross 尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 sine-response

title："正弦幅相"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："正弦幅相尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 conjugate-poles

title："共轭极点"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："共轭极点尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 smooth-derivative

title："光滑曲线导数"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："光滑曲线导数尚未跑。"
in_current_denominator: false
counts_as_current_support: false

### 历史 delay-then-slew

title："延迟后限速"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："延迟后限速尚未形成独立卡。"
in_current_denominator: false
counts_as_current_support: false

### 历史 short-pulse

title："短脉冲"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："短脉冲尚未形成独立卡。"
in_current_denominator: false
counts_as_current_support: false

### 历史 deeper-slew-cascade

title："更深 slew 级联"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："更深 slew 级联尚未形成独立卡。"
in_current_denominator: false
counts_as_current_support: false

### 历史 adc-codes

title："ADC 端码、阈值、饱和与读取时序"
status："waiting"
review："pending"
evidence："evas/validation/paper/COVERAGE.md#remaining-coverage"
gap："固定端码、阈值、饱和及读取时序的仿真器用例尚未跑，不能用 benchmark 成绩代替。"
in_current_denominator: false
counts_as_current_support: false

## 例外

exception: coverage_sufficiency_pending 10
exception: historical_unjoined 1
exception: toolchain_unknown 40
exception: unbound_qualification 1
exception-detail: {"count": 78, "kind": "historical_unjoined", "reason": "historical nodes do not name a current requirement and are not joined"}

## 分类

classifications: {"backend_execution_cells": {"unknown": 40}, "exception_counts": {"coverage_sufficiency_pending": 10, "historical_unjoined": 1, "toolchain_unknown": 40, "unbound_qualification": 1}, "historical_node_status": {"compared": 57, "waiting": 21}, "qualification_records_current_qualified": {"false": 1}, "record_execution_states": {"recorded": 1}, "requirement_status": {"pending": 10}}

## 本视图不做的事

- 默认视图与预览都由登记生成；adopted 只表示当前默认视图身份，不是新的项目决定，也不授予要求级支持或科学资格。
- pending、not_conferred 表示待审核或未取得资格，不等于 unsupported（不支持）或 known_nonconformance（已知不符合）。
- 覆盖充分性未定义时保持 pending；单个案例资格不解释成要求或能力通过。
- 工具链版本只来自已绑定记录上的显式 toolchain 列表；没有该列表时为 unknown。
- catalog.BACKENDS 的四个键不接收协议别名；无法精确对应的后端身份单独列出。
- 历史成绩保持原身份，不进入当前要求分母。
