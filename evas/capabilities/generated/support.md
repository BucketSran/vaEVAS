# 当前要求的四后端事实

view_status: current-default
adopted: true
provisional: false
adopted 只表示这是当前默认支持视图，不是新的项目决定，也不授予任何资格。

current_requirements: 6
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

exception: coverage_sufficiency_pending 6
exception: historical_unjoined 1
exception: toolchain_unknown 24
exception: unbound_qualification 1
exception-detail: {"count": 78, "kind": "historical_unjoined", "reason": "historical nodes do not name a current requirement and are not joined"}

## 分类

classifications: {"backend_execution_cells": {"unknown": 24}, "exception_counts": {"coverage_sufficiency_pending": 6, "historical_unjoined": 1, "toolchain_unknown": 24, "unbound_qualification": 1}, "historical_node_status": {"compared": 57, "waiting": 21}, "qualification_records_current_qualified": {"false": 1}, "record_execution_states": {"recorded": 1}, "requirement_status": {"pending": 6}}

## 本视图不做的事

- 默认视图与预览都由登记生成；adopted 只表示当前默认视图身份，不是新的项目决定，也不授予要求级支持或科学资格。
- pending、not_conferred 表示待审核或未取得资格，不等于 unsupported（不支持）或 known_nonconformance（已知不符合）。
- 覆盖充分性未定义时保持 pending；单个案例资格不解释成要求或能力通过。
- 工具链版本只来自已绑定记录上的显式 toolchain 列表；没有该列表时为 unknown。
- catalog.BACKENDS 的四个键不接收协议别名；无法精确对应的后端身份单独列出。
- 历史成绩保持原身份，不进入当前要求分母。
