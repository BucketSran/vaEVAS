```json
{
  "scope": "仅对两个最终工具 delta 做静态审查：(1) precision_breadth_aggregate.py 由 f125/c016 到 aa7c13 的变更（external_evidence_identity、readback_provenance、external_axes、verified_cards_digest、integrator 轴、official_cards_sha256 绑定）及其测试；(2) curate_public_receipt.py 由 e483 到 d9f200 的变更（verify_external_analysis、verify_cards、integrator_status、LAYERS 扩展、--expected-cards-sha256、输出树检查扩展）及其测试。上下文中提供的 precision_breadth_reanalysis.py、precision_breadth_open_evidence.py、settings_readback.py 仅作为接口证据使用。未执行任何代码、哈希或仓库操作。",
  "standards": [
    "密封输入信任：cards 必须绑定到已验证 MANIFEST／外部批准的精确摘要，元数据源绑定必须拒绝替换",
    "852/528/probe/unknown/8 科学轴保持，无 best-of 选择",
    "外部 proof hash/source/argv/environment/claims/reviews/integrator/legacy readback 仅作来源保留，不构成新的科学等级",
    "旧 receipt 7e8 缺新字段是 schema 版本差异，不得视为数据污染，也不得要求旧 receipt 满足新元数据",
    "fail-closed：证据缺失保持 unknown/missingproof-safeunknown，错误以可控异常表达",
    "不可变快照：路径逃逸/符号链接/哈希漂移必须被拒绝"
  ],
  "spec": "审查要求：覆盖全部改动函数/调用者/API/测试/差异；发现需给出触发条件、文件行号、影响与违反的要求；不假设作者测试或证明正确；无发现时 findings 为空数组。",
  "findings": [
    {
      "id": "F1",
      "severity": "low",
      "file": "fixed-d9:curate_public_receipt.py",
      "line": "174-176",
      "trigger": "main() 先以 verify()/verify_cards() 校验 digest，随后再次 read_text() 读取同一 OFFICIAL-DRAFT.json、FAILURES.json 与 cards.json 传入 curate()。校验与使用之间存在时间窗，若文件在窗口内被并发替换，receipt 将基于未校验内容生成（该模式在 e483 已存在，delta 通过 verify_cards 又新增了 cards 这一处）。",
      "impact": "并发篡改可绕过摘要校验进入 curated 输出；单机冻结场景下实际风险很低。",
      "requirement": "密封输入必须先验后用、无 TOCTOU 间隙（fail-closed）。建议读一次字节并同时用于校验与解析。"
    },
    {
      "id": "F2",
      "severity": "low",
      "file": "fixed-d9:curate_public_receipt.py",
      "line": "64-83 (verify_cards), 25-63 (verify_external_analysis)",
      "trigger": "OFFICIAL-DRAFT.json 的 analyses[].analysis 为本机绝对路径（aggregate 以 str(path) 写入）。当任一 sealed analysis 目录缺失、ANALYSIS_MANIFEST.json 不存在或不是合法 JSON 时，json.loads(manifest.read_text()) 抛 FileNotFoundError/JSONDecodeError 而非受控 ValueError；同时使 PUBLIC-RECEIPT 的生成强依赖原始主机上全部 analysis 目录的在场与完整性。",
      "impact": "跨主机/迁移后 curation 以难以诊断的 traceback 失败；错误类型不一致破坏 fail-closed 的可辨识错误契约。注意按 availability 申明（local-only）依赖本机证据是设计意图，本条仅针对失败方式而非依赖本身。",
      "requirement": "不可变快照校验应以受控异常报告缺失/漂移。"
    },
    {
      "id": "F3",
      "severity": "low",
      "file": "aa7cb13:experiments/backends/support/precision_breadth_aggregate.py",
      "line": "106-109 (external_axes)",
      "trigger": "当 record 携带 external_open_evidence 但缺少 'configuration' 键（伪造/异常 REANALYSIS.json）时，record['configuration']['status'] 抛 KeyError 而非 ValueError，与该模块其余防御（全部 raise ValueError）不一致。同理 line 107 在 external 缺 'integrator' 键时 external.get('integrator') 为 None，与 integrator(dict) 比较必不等会正确 raise；但 KeyError 路径未被覆盖测试。",
      "impact": "仅错误类型不一致，无资格提升风险；密封 manifest 已锚定 REANALYSIS.json 完整性，属纵深防御缺口。",
      "requirement": "fail-closed 校验应以统一受控异常表达。"
    },
    {
      "id": "F4",
      "severity": "info",
      "file": "fixed-d9:test_curate_public_receipt.py",
      "line": "84-93 (test_full_group_identity_and_mandatory_slots_rejected)",
      "trigger": "该测试依赖本机存在 official-draft-open-foundation-part1-guarded-v1 等 baseline 目录；两级 fallback 均缺失时抛 FileNotFoundError（而非 skip），且子目录名 OFFICIAL_CARDS.json 与 verify_cards 中识别的 'OFFICIAL_CARDS.json' 一致但 fixture 路径来自另一目录树。",
      "impact": "测试在缺少固定 baseline 的环境中以崩溃而非明确 skip 表达前置缺失；不影响生产代码正确性。",
      "requirement": "不可变快照测试应显式声明外部 fixture 依赖。"
    },
    {
      "id": "F5",
      "severity": "info",
      "file": "aa7cb13:experiments/backends/support/precision_breadth_aggregate.py",
      "line": "58, 274",
      "trigger": "main() 中对每个 catalog 条目先 verify_analysis(path)（line 261），随后 external_evidence_identity(path) 内部再次调用 verify_analysis(path)（line 58），同一密封树被完整重扫一遍。",
      "impact": "仅为重复计算开销，无正确性影响。",
      "requirement": "无（性能备注）。"
    }
  ],
  "missing_context": [
    "precision_breadth_reanalysis.py 中 qualification()/effective_settings() 的返回结构（actual/requested 键是否始终存在），影响 readback_provenance 在无 legacy 路径下 actual_settings 是否为空串的判断",
    "precision_breadth.load_contract / assess 与 PROFILE_BINDINGS.json 的真实结构（测试用合成 fixture 替代）",
    "真实 catalog、SELECTION、OFFICIAL-DRAFT、FAILURES 及旧 receipt 7e8 的实际数据，无法核对字段与摘要一致性",
    "precision_breadth_open_evidence.py 返回的 external axes 中 issues 字符串是否含本机路径（仅由 curator 的 '/Users/' 泄漏检查兜底）",
    "测试引用的 baseline fixture 目录内容（F4）"
  ],
  "limitations": [
    "纯静态文本审查，未执行任何代码、哈希或测试；所引快照 SHA 按供给文本采信但未验证",
    "无法验证作者测试是否在真实数据上通过，亦无法验证冻结输入摘要与外部批准摘要的实际匹配",
    "按审查指令确认：external_evidence_identity/verify_cards 的摘要绑定逻辑对 cards 替换（manifest 成员缺失、哈希漂移、probe 翻转）均 fail-closed；integrator 轴在 aggregate 与 curator 两端公式一致（开放后端仅 qualified/unknown，非开放仅 not_applicable，组级聚合两侧等价）；proof_metadata 为精确键子集投影且两端独立重算比对，未授予任何资格；旧 receipt 缺新字段符合 schema 版本差异处理，未发现要求旧数据满足新元数据的代码路径",
    "无以上限制外的发现；F1-F3 为低严重度健壮性问题，不构成资格提升或 best-of 通道"
  ]
}
```
