```json
{
  "scope": "固定提交 0e1f91d1 相对基线 6f2f9dfc 的 D1-D3 加固增量静态只读复查：(1) raw label 解析封闭与 runs 目录/符号链接祖先约束（raw_work 及 worker/aggregate 两处接入）；(2) 官方 PROFILE_BINDINGS.json 强制 manifest 成员与哈希校验（verified_bindings 及 freeze_inputs/aggregate main 接入）；(3) worker 在缺失官方绑定文件时未知绑定不得旁路 profile 门（slot_status 无条件传入 binding、configuration 降级）。含新增/修改的 4 个测试与 precision_breadth.py/precision_report.py 上下文。数值 lazy delta、F14/F20、既有 852 槽/六分层/CLI 独占等基线性质按约定不重审；前次 F-D4 已确认是评审提示错误（实际优先级 execution_failed > behavior_error > numerical_error > evidence_insufficient，all-pass 先行，独立分层保留全部失败），本次不再要求 evidence 优先。",
  "standards": [
    "D1：聚合与 worker 消费的 raw 工作目录路径必须由 label 解析并封闭在已验证 lane 的 runs/ 之内，拒绝逃逸、runs 自身/候选/祖先符号链接",
    "D2：PROFILE_BINDINGS.json 必须列入冻结 MANIFEST.json 且哈希一致才可被 freeze_inputs 与 aggregate 消费；符号链接拒绝",
    "D3：worker 在官方绑定不可用时，绑定状态必须为 unknown 并使 slot_status 强制 evidence_insufficient，configuration 降级为 unknown，绝不产生 pass",
    "既有不变量不得回归：852/528 分母、probe_only/support_probe_only 不可 pass、六独立分层保留失败、选定 attempt 唯一、CLI 输出独占、冻结哈希链",
    "组状态优先级为实际接受值 execution_failed > behavior_error > numerical_error > evidence_insufficient（all-pass 先行），不施加 evidence 优先要求"
  ],
  "spec": "逐行核对 delta 与全量文件：reanalysis L43-51（raw_work：runs.resolve、runs/candidate is_symlink、parents 链上符号链接检查、resolved==runs 与 is_relative_to 拒绝）、L54-59（verified_bindings：manifest 成员 + 符号链接 + 哈希三重校验）、L65（freeze_inputs 前置调用）、L217-219（worker 绑定文件存在时哈希复检）、L228（worker 用 raw_work）、L241（bindings 为 None 或 card 缺失时 binding=unknown）、L270（qualified_tiers 无条件传入 binding，删除 binding if bindings is not None else None 旁路）、L271-273（非 matched 时 configuration 覆写为 unknown 并保留原读回状态与 binding_issues）；aggregate L29（导入）、L181（verified_bindings，替代原裸 load）、L206（raw_work 替代裸拼路径）；测试 test_raw_label_cannot_escape_runs_or_follow_a_symlink（合法路径/../../逃逸/目录别名符号链接三例）、test_unmanifested_official_profile_bindings_are_rejected（缺 manifest 拒绝、含正确哈希接受）、reanalysis 测试补 profile/requested_settings/INPUT_IDENTITY 固定装置及 missing-bindings 二次 worker 运行断言（numeric 分层保留 pass/numerical_error、execution_status 保留、configuration 全 unknown、qualified_tiers 全 evidence_insufficient）。slot_status L169-176 对 binding.get('status')!='matched' 与跨 tier 双重拒绝确认无 None 旁路。",
  "findings": [
    {
      "id": "F-D1a",
      "severity": "信息",
      "file": "experiments/backends/support/precision_breadth_reanalysis.py",
      "line": 45,
      "trigger": "raw_work 先做 is_symlink 检查再 candidate.resolve()，检查与解析/后续读取之间存在 TOCTOU 窗口；且 runs.resolve() 每次调用重新解析，若 lane 本身位于符号链接路径下，两次调用之间理论可被替换。",
      "impact": "在与攻击者并发写文件系统的对抗场景下，符号链接检查可被竞态绕过。实际威胁模型不成立：lane 在分析前后经 verify_lane 全量哈希/符号链接清单校验（L327/L335-336），且分析目录为独占新建目录；静态评审无法演示该竞态可达。不构成可行动缺陷，仅作记录。",
      "requirement": "路径封闭（D1）。无需修改；如后续强化可在 verify_lane 中记录 runs 目录设备/ inode 一致性。"
    }
  ],
  "missing_context": [
    "固定提交 0e1f91d1 与 6f2f9dfc 的完整差异仅以用户提供的 diff 与四个全量文件呈现；precision_breadth_run.py、precision_run.py、observations.py、precision_binding_run.py 及实际产物目录（OFFICIAL-DRAFT/SLOTS/MANIFEST）未在本次范围内提供，无法验证新 raw_work/verified_bindings 在真实产物链上的端到端重放。",
    "无法执行测试或重算任何哈希；test_raw_label_cannot_escape_runs_or_follow_a_symlink 在符号链接权限受限的文件系统上的可运行性未验证。"
  ],
  "limitations": "只读静态文本审查，无文件系统/工具/执行；测试断言内容被核对其确实覆盖目标行为，但测试通过本身不作为证明。结论：(1) D1 已落实——worker L228 与 aggregate L206 均改经 raw_work，label 逃逸（../、绝对路径经拼接）、runs/candidate/任一祖先符号链接均被拒绝，resolve 后 is_relative_to(runs) 且拒绝 resolved==runs，双重消费者一致；aggregate 不再直接信任密封分析 REANALYSIS.json 中的 label 拼路径（前次 F-D1 修复确认）。(2) D2 已落实——verified_bindings 要求 PROFILE_BINDINGS.json 必须在 MANIFEST.json 中、非符号链接且哈希一致，freeze_inputs 与 aggregate main 均前置调用，前次 F-D3（绑定文件可绕过 manifest 哈希链）修复确认；aggregate 中该调用位于任何绑定消费之前（L181 早于 L206-209）。(3) D3 已落实——worker 删除了 binding if bindings is not None else None 旁路，slot_status 对非 matched 绑定无条件返回 evidence_insufficient（L170），缺失绑定文件时 binding.status='unknown'，且 L271-273 将 configuration 一并降级为 unknown 并保留 binding_issues 与 original_readback_status 可审计；card 缺失分支同样落入 unknown 绑定，无旁路路径；新增 missing-bindings 测试同时证明 numeric/execution 独立分层信息不丢失。(4) 无回归：slot_status 数值/执行失败优先逻辑（L172-176）、probe_only 双键拒绝（precision_breadth.py L343-345 与 aggregate L107/L141-142）、852/528 强制（aggregate L182-185/L216）、重复 attempt 拒绝（worker L227、aggregate L98）、CLI 输出独占与 disjoint 检查均未改动或仍在位。(5) 前次 F-D4 按更正确认为评审提示错误：group_status L62-67 的实际优先级与既定接受契约一致，独立分层保留全部失败，不构成缺陷，不再列入。唯一记录项为理论性 TOCTOU 竞态（信息级，现有 verify_lane 前后双校验已实质覆盖）。"
}
```
