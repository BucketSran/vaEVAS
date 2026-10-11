# 开放 adapter 最终 schema 增量复审

结论：固定 `d844b79584b8a42d361e340ce918658f3609d9a9` 相对已通过 Astra 的 `1e825b47956ad2a80fddb2b2e910bbff041b0f42`，本次未发现新的 P1/P2。新增的 JSON schema 错误处理、七轴稳定返回、双审附件区分和 argv digest 列表校验符合当前失证保持 unknown 的合同。可以继续等待实际 GLM 结论并审生产 caller 接入；没有真实 proof 被本报告批准，没有科学成绩升级。

## 代码复核

`load` 明确要求 JSON object，并将 JSON 语法错误分类为 `EvidenceSchemaError`。实际嵌套对象（compiled_artifacts、container_cleanup、tool.images、backend image、proof attachments/reviews/individual review/claims）均在使用 `.get` 前显式检查。execution argv 必须为字符串列表；proof argv_sha256 必须是非空列表，成员均为小写 64 hex digest，防止字符串子串成员测试或 dict key 误当批准列表。

schema 错误独立捕获后，七个轴全部返回 unknown，保留理由。没有加入 `except Exception` 或 AttributeError 的广泛吞错；其它实现错误不伪装成正常资格。既有证据缺失等 ValueError 仍保留已独立核得的事实，但不会把缺证明的 runtime/native 变为 qualified。

Astra/GLM review 附件必须有不同 path 和不同内容 hash，并都在已验证附件表中。这是防止同一报告重复计数的结构约束；真正独立审查的含义仍由包外 exact SHA 批准承担，不能以不同文件名或内容 hash 自动证明两位审查者的判断。

逐行 diff 未改变容差、tick cap 计算、16 ulp stop 边界或 native/runtime 合取。额外比较 AST，`waveform_complete`、`gc_number`、`gc_options`、`source_lines`、`control_block`、`positive` 与 1e825 完全相同。前次 run_scopes 的六输入、compiled、完整 argv 精确绑定保留。

## 实际本地检查

- 固定 head 为 d844b795；adapter 56 项校准 PASS，相关 support breadth 78 项 PASS；diff check 通过。
- 原五项 Astra 负控重跑，runtime/native 均 unknown，修后输出另存 `astra-open-adapter-negative-d844b795.json`，没有覆盖原 49a 失败证据。
- 前次逐输入、只换 compiled、缺 proof、缺批准、重复 scope 的独立脚本重跑，全拒；输出为 `astra-open-scope-d844b795.json`。
- 另建 `astra-open-schema-d844b795.py`：RESULT/simulate-final/INPUT_IDENTITY/proof 的 list/null/bool/number/string/无效 JSON，argv digest 非列表/空列表/大写/空成员等，以及重复 review path，共 32 项独立变异均安全返回 unknown 和具体理由；结果存同名 JSON。没有将这些合成证据当作实际运行。

本增量未修改 whole-deck grammar，因此沿用前次 78 份实际完整 NG/GN deck 兼容性结果；未重复模拟器或整矩阵。无远端调用、tracked 修改、原 RESULT/hash/分母变更。

## 未完成的外部条件

没有生产调用方在此 diff 内，也没有最终实际 approved proof 包。接入时仍需检查批准 SHA 的受控来源、原 frozen/raw manifest 的真实验证、全部资格轴与科学门的合取，以及 probe/失败/unknown 的保留。真实启动与导出机制缺件仍按 `astra-open-origin-delta.md`；不能用这次代码校准替代实际 NG/GN 来源证明。旧 49a、1e825 报告和失败记录全部保留。
