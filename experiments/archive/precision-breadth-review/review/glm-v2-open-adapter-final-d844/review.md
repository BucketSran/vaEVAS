```json
{
  "scope": "对固定 d844b795 相对 9bf3 的窄增量独立只读静态审查：(1) precision_breadth_open_evidence.py 中 proof.argv_sha256 的显式非空 list-of-lowercase-64hex schema 校验（line 94-98）及 load() 对 json.JSONDecodeError 映射为 EvidenceSchemaError（line 53-58）；(2) test_precision_breadth_open_evidence.py 新增 test_proof_argv_digest_schema_fail_closed 与 test_invalid_proof_json_fail_closed。逐行核对了校验逻辑、EvidenceSchemaError 在 qualify_open_backend except 链中触发全七轴 unknown 的路径，以及新测试的触发链与断言可达性（未假设作者测试正确，独立推演）。不重开 F1/F2（容差/16ulp/quantized cap 均为冻结合同且本增量未触及）；不审真实机制 proof、runner/native 机制证明（上下文明确排除）。按授权边界：无生产调用方、无已批准最终 proof，本审查不授予任何科学资格。",
  "standards": "1) fail-closed：结构错误一律 unknown，不崩溃、不升级为通过；2) 外部信任边界 = 调用方逐字批准的 proof exact SHA，包内字段校验仅是次级防线；3) argv_sha256/run_scopes 逐 run 绑定不得弱化：argv_sha256 必须是非空 list 且每项为 lowercase 64hex 字符串；4) malformed JSON syntax 必须映射为 EvidenceSchemaError，使全部七轴 unknown 且保留原因；5) 不以宽捕 TypeError/IndexError 代替显式 schema（9bf3 裁决已否决 broad catch，本增量应维持显式字段 schema 方向）；6) 不改动数值容差、16ulp stop 边界、quantized cap 语义。",
  "spec": "审查依据仅为消息内 FIXED SOURCE 文本（行号指该文本）、FULL DIFF、HANDOFF.md 及两个合成负控脚本/JSON（independent-negative、independent-argv-schema-negative，均为 synthetic_only）。对旧报告 F1/F2/F3-F5 及 disposition 的声明按'待批评声明'处理：本次独立核验的是 d844 新增代码本身，而非采信作者或先前模型的测试结论。",
  "findings": [
    {
      "id": "D1",
      "severity": "info（防御对称性备注，非违反本次增量要求）",
      "file": "experiments/backends/support/precision_breadth_open_evidence.py",
      "line": "55",
      "trigger": "load() 将 Path(path).read_text() 与 json.loads 置于同一 try 块，但仅捕获 json.JSONDecodeError。若 evidence 文件是无效 UTF-8 字节（如 RESULT.json 为二进制/损坏字节），read_text() 抛 UnicodeDecodeError，该异常虽是 ValueError 子类、会被外层通用 except 捕获而 fail-closed，但落点是非 schema 分支：七轴保持 'not evaluated' 而非按 EvidenceSchemaError 语义重置并报告 'not valid JSON' 类原因。",
      "impact": "行为仍是 fail-closed（无崩溃、无 false qualified），仅错误分类与 issues 文案与 JSON 语法错误路径不对称。且此类文件几乎必然同时通不过 manifest digest 校验（verify_files 在 load 之前，line 225/298），故实际可达性极低。",
      "requirement": "不违反本次增量规格（规格限定 malformed JSON *syntax*）；如需完全对称，可将 read_text 的 UnicodeDecodeError 一并归入 EvidenceSchemaError。仅为记录，不要求修改。"
    }
  ],
  "missing_context": [
    "无 open-backend-proof-v1 真实已批准实例，argv_sha256 实际形态只能按 HANDOFF 描述推断；本审查不构成对任何真实 proof 的资格认定。",
    "调用方（coordinator/consumer）对七轴输出与 approved_proof_sha256 的消费代码未提供，外部信任边界的实际执行无法复核。",
    "settings_readback.py 为既有依赖，其 ngspice/gnucap 行为按固定源文本采信，未独立复审其正则语义。",
    "新增测试中 refresh() 对畸形 proof 的'显式重新批准'仅是合成夹具；真实审批流程中该路径是否会出现取决于 owner，无法静态证实。"
  ],
  "limitations": [
    "纯静态只读审查，未执行任何代码、未复算哈希；两个 negative JSON 是外部提供的合成证据，本次仅核对其与 d844 源码逻辑的一致性，未复跑。",
    "argv_sha256 校验位于 proof digest 批准之后（line 87 先行）：未获批准的畸形包不会触发该 schema 路径，属设计意图（信任锚在外部 exact SHA），非缺陷。",
    "不重开 F1/F2：浮点容差严格比较、16ulp stop 边界、GN quantized cap 语义在 d844 中逐行确认未变（line 273、317-321、338-343、387-388 与 9bf3 一致）。",
    "runner/native 机制证明（NG startup/AddReal、GN integrator/load 等 HANDOFF 不可追证项）明确排除在本审查外，全部保持 pending，不因 schema 修补升级任何旧 run 资格。"
  ]
}
```

增量核验摘要（作为 findings 之外的事实陈述）：d844 相对 9bf3 的两处生产代码改动均正确实现规格——argv_sha256 校验（isinstance list、非空、每项 str 且 re.fullmatch `[0-9a-f]{64}`）以 EvidenceSchemaError 抛出，经 line 408-410 分支使全部七轴 unknown 并保留原因，与 9bf3 报告 N1 建议的修补形态一致；load() 的 JSONDecodeError 映射闭合了畸形 JSON syntax 路径。新测试 test_proof_argv_digest_schema_fail_closed 覆盖 8 种畸形形态（含子串攻击载体 string、dict、None、int、空 list、非 hex、None 元素、大写），且末尾恢复后断言 native qualified，验证校验不误伤合法值；test_invalid_proof_json_fail_closed 显式批准 '{invalid-json' 包以触发语法错误路径。未发现可导致 false qualified 或崩溃的路径；仅 D1 一条 info 级对称性备注。
