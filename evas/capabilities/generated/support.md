# 当前要求的四后端事实

view_status: current-default
adopted: true
provisional: false
adopted 只表示这是当前默认支持视图，不是新的项目决定，也不授予任何资格。

current_requirements: 4
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

exception: coverage_sufficiency_pending 4
exception: historical_unjoined 1
exception: toolchain_unknown 16
exception: unbound_qualification 1
exception-detail: {"count": 78, "kind": "historical_unjoined", "reason": "historical nodes do not name a current requirement and are not joined"}

## 分类

classifications: {"backend_execution_cells": {"unknown": 16}, "exception_counts": {"coverage_sufficiency_pending": 4, "historical_unjoined": 1, "toolchain_unknown": 16, "unbound_qualification": 1}, "historical_node_status": {"compared": 57, "waiting": 21}, "qualification_records_current_qualified": {"false": 1}, "record_execution_states": {"recorded": 1}, "requirement_status": {"pending": 4}}

## 本视图不做的事

- 默认视图与预览都由登记生成；adopted 只表示当前默认视图身份，不是新的项目决定，也不授予要求级支持或科学资格。
- pending、not_conferred 表示待审核或未取得资格，不等于 unsupported（不支持）或 known_nonconformance（已知不符合）。
- 覆盖充分性未定义时保持 pending；单个案例资格不解释成要求或能力通过。
- 工具链版本只来自已绑定记录上的显式 toolchain 列表；没有该列表时为 unknown。
- catalog.BACKENDS 的四个键不接收协议别名；无法精确对应的后端身份单独列出。
- 历史成绩保持原身份，不进入当前要求分母。
