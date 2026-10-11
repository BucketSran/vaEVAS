```json
{
  "scope": "对 ignored 本地 curation 工具 curate_public_receipt.py（硬化后版本，SHA c0571c88…）及其 main/curate/verify 全函数、配套测试 test_curate_public_receipt.py、上游已审聚合器 precision_breadth_aggregate.py 的相关接口、以及所提供的 597 基线收据压缩投影（string_pool 编码）与硬化审计材料做只读静态复核。范围固定为：852 槽=71 变体×4 后端×3Q、528 组格=44×4×3、失败/未知不删除、无 best-of、各轴分离、hash/claim 保留、raw 仅 local-only。不覆盖最终 selection 与新 852 实际数据 delta（后续审查），不复跑任何测试或仿真。",
  "standards": "1) 收据必须逐槽保留全部 852 键与八条独立轴（final/numeric/behavior/evidence/config/native/runtime/original_execution），失败与 unknown 原样保留；2) 无重新资格判定、无 best-of 选择；3) 输入（aggregate/failure manifest、cards）需 sealed 校验（成员、hash、symlink、路径逃逸）；4) 探针不得计 pass；5) availability 声明必须区分 raw=local-only、源码=repository-contained、重跑=需后端环境，hash 不等于公共可获取；6) 分母与身份校验（852 唯一键、528 组格）应为工具可校验的硬约束；7) 公开产物不得泄漏私有绝对路径；8) 上游已审聚合器视为可信输入，但工具自身发布的字段仍应与输入一致（不得静默丢信息）。",
  "spec": "工具签名 curate(r, failures, cards, *, expected_slots=852)；main 以 --aggregate/--failure-inventory/--cards/--output 运行，verify(base, required) 校验 MANIFEST；收据含 schema_version、availability、tables（intern 去重）、slots、counts、groups 及各 manifest/源码 hash；本地 private 路径仅以 retention_id（basename）形式出现。",
  "findings": [
    {
      "id": "F1",
      "severity": "P3",
      "file": "curate_public_receipt.py:53-57",
      "trigger": "curate() 对 failures['nonpass_slots'][*]['unknown_by_origin'][origin] 为 dict 时，白名单仅保留 ['status','reason','issues','origin_gap']（外加 facts.origin_gap），其余键被静默丢弃。所供失败清单实例中 native_observation 含 'limit'（\"deck and aggregate export facts do not certify initial state, counters, phase, or interpolation error\"）、settings 含 'scope'（EC12-v2 的 ngspice/Gnucap stop/maxstep 说明），均不在白名单内；对照压缩收据 r67 仅剩 {status, reason}，证实 limit/scope 在发布收据中消失。",
      "impact": "公开收据对 unknown 原因的解释性信息少于已封存失败清单，削弱'不删除失败/未知信息'与独立归因可读性；读者无法从收据得知 unknown 的范围限定（scope/limit）。",
      "violation": "要求 1/8：失败与 unknown 信息须原样保留、发布字段不得静默少于输入。"
    },
    {
      "id": "F2",
      "severity": "P3",
      "file": "curate_public_receipt.py:72",
      "trigger": "curate() 把 r['groups'] 逐字段投影后直接写入收据，既不校验 len(groups)==528（44×4×3），也不校验每组 variants/final 与 slots 重算结果一致（组 pass ⟹ 全体 mandatory variant pass、mandatory_variants 与卡片一致）。此类校验只存在于 review/audit_public_curation.py:26-28，不在收据生成路径内。",
      "impact": "若上游聚合器组表与槽表不一致，curation 工具会把不一致的 groups 连同由 slots 重算的 counts 一并发布，收据内部自相矛盾且无告警；528 分母不是工具级硬约束。属'可信上游义务'与工具自校验缺口的叠加，实际 597 数据经审计脚本核对一致，未见现实污染。",
      "violation": "要求 6：分母（852/528）与组-槽一致性应为工具可校验硬约束。"
    },
    {
      "id": "F3",
      "severity": "P4",
      "file": "curate_public_receipt.py:50",
      "trigger": "reason 分类用 `'behavior' if issue in s.get('behavior_errors',[]) else 'evidence'`：当同一字符串同时出现于 behavior_errors 与 evidence_issues 时，两份记录均被标为 behavior 层；行为/证据两轴在 reason_refs 中可能失真（槽级两轴字段本身不受影响）。",
      "impact": "仅影响 reason 表的层标注与去重语义，不改变槽状态；当前数据未见同文双列实例。",
      "violation": "要求 1：各轴分离在 reason 投影中被弱化。"
    },
    {
      "id": "F4",
      "severity": "P4",
      "file": "curate_public_receipt.py:16",
      "trigger": "verify() 中 manifest 条目为 dict 但缺 'sha256' 键时抛未受控 KeyError（而非 ValueError 'receipt drift/unsafe' 系列）；同时条目可含 'bytes'（aggregate MANIFEST 均含）但 bytes 从不校验，只核 sha256。",
      "impact": "畸形 manifest 产生非预期异常类型，且 size 漂移（hash 相同理论上不可能但字段承诺未兑现）不被检查；对密封性结论无实质影响。",
      "violation": "要求 3：sealed 校验应对畸形输入给出受控失败并兑现 manifest 全字段。"
    },
    {
      "id": "F5",
      "severity": "P4",
      "file": "curate_public_receipt.py:79-80",
      "trigger": "私有路径泄漏检查仅匹配 '/Users/' 与 '/home/'，不覆盖 /tmp/、/Volumes/、/private/、Windows 盘符等前缀；且 main 未禁止 --output 位于 aggregate/failure/cards 目录之内（上游聚合器 main 有 disjoint 检查，本工具没有）。",
      "impact": "其他绝对路径前缀若经 reason/issue 文本进入收据不会被拦截；输出目录嵌套输入目录可能污染被封存输入区。当前 597 数据无泄漏迹象，属硬化不完备。",
      "violation": "要求 7 及输出与冻结输入解耦惯例。"
    },
    {
      "id": "F6",
      "severity": "P2（编码/证据缺口，非工具 bug）",
      "file": "提交的 LOSSLESS RECEIPT 编码（slots_columns 声明）",
      "trigger": "压缩收据 slots_columns 止于 reason_refs，整体省略工具 out 中逐槽生成的 original_result_sha256、kernel_or_binary_sha256、tool_identity_sha256、source_sha256、source_compatibility、input_identity_sha256 及 key_failure_witness（仅 analysis_ref 用 {$missing:true} 标注缺失）；编码说明自认'并非完整原收据'并保留全文件 hash c00c1d…/0c4377…。",
      "impact": "本轮无法从所供编码逐槽验证 raw/source/tool hash 与条件性 witness 的保留，只能依赖 audit_public_curation.py 的声明（其本身是被审证据而非权威）；这些恰是任务要求保留的 per-slot provenance 字段。后续最终 852 审查必须以未压缩 PUBLIC-RECEIPT.json 或补全列为核验对象。",
      "violation": "要求 1/5 的可核验性：压缩投影不足以证明逐槽 hash/claim 保留。"
    }
  ],
  "missing_context": [
    "未提供完整 852 槽的原始 OFFICIAL-DRAFT.json / FAILURES.json（仅 representative slots/groups 与 examples），无法逐槽独立复核 layer/hash 一致性，只能抽查所供样本。",
    "未提供 OFFICIAL_CARDS.json 原文（仅 cards_metadata 投影），declared_source_sha256 与 source 的对应依赖投影。",
    "未提供硬化版收据 public-receipt-baseline-597-hardening-v1/PUBLIC-RECEIPT.json 原文（仅 sha 与压缩投影），'除 availability/curation_source_sha256 外与旧收据逐项相等'的说法无法独立验证。",
    "测试日志/14 项通过、CLI 负控与各 SHA（如 c0571c88…、0c4377a3…）均为提交声明，静态审查无法执行验证。",
    "最终冻结 selection、新 852 实际执行数据、v3 delta 不在本次范围。"
  ],
  "limitations": "本审查为只读静态文本审查：不执行代码、不重算 hash、不访问文件系统；所有上游测试/审计通过记录视为待批证据而非权威。已确认的正面结论（基于代码逻辑）：852 唯一键/分母、失败清单键集与 non-pass 精确匹配、full_pass/selected_slots 反校验、probe 不可 pass、not_collected 不计 execution、counts 由收据槽独立重算、availability 三态不含 URL、retention_id 仅取 basename、'/Users/'与'/home/'泄漏检查、required-payload manifest 硬化（含 symlink/逃逸/漂移拒收）均与规范一致；所列 F1-F5 为残余硬化缺口，F6 为证据形态限制。最终 852 数据与新 selection 的 delta 审查另行进行。"
}
```
