{
  "scope": "本轮有界delta审查：固定final762a精简收据、新NG F03全部36槽（原RESULT/输入token审计/旧36槽/分析错误/设置来源）、最终44组×4后端×Q1Q2Q3共528状态格、四后端各轴counts、COMPARISON.md与COMPARISON-METHODOLOGY.md两份主文档、support README新44组节及历史身份、7文件diff中nav/candidates部分、决策日志最后两条。只判delta/data/doc一致性与措辞；不改科学结论、不颁science pass、不批准open proof。旧852/EVAS 213科学数学checker已审部分不重复。",
  "standards": ["文档自订规则：确认失败必须直接写原因，证据不足写明缺口，待完成项不得写成失败也不得写成通过（COMPARISON.md §2、COMPARISON-METHODOLOGY.md #table-verdicts）", "支持矩阵逐格结论须与固定数据/收据一致（README §44组：'逐项保留…数值达标与完整通过分别记录'）", "组级✓须全变体mandatory AND；数值/行为/证据轴分开（METHODOLOGY #precision-breadth）", "F03新36：全部waveform_available、ReadbackError、numeric unknown、不得推断比较器缺陷（决策2026-10-11T21:49行、诊断收据）", "总852计数154/510/132/50/6须与aggregate一致（决策2026-10-11T21:53行）"],
  "spec": "以用户提供的固定文本为唯一证据：三个FIXED FILE全文、无损pool展开（含all44_group_status_rows、各后端counts、36新槽逐字段、diagnostics、decision trail最后两行、settings_readback.py全文）。GLM不执行hash/数值复算，不假设作者证明正确。",
  "findings": [
    {
      "id": "F1",
      "severity": "中",
      "file": "evas/docs/COMPARISON.md（支持矩阵·工程组合表 EC04/EC05/EC20/EC24 行，gnucap列）vs 数据 all44_group_status_rows（pool $ref:33，EC04/EC05/EC20/EC24 共用同一状态格：gnucap_modelgen = numerical_error×3）",
      "trigger": "EC04 gnucap格写'三档 数值达标；观察来源待证'、EC20 写'三档 回调时刻待证'、EC05/EC24 写'三档 支持探针不计通过'，均为证据不足/探针类措辞；而固定528格中该四组gnucap三档均为 numerical_error（确认数值失败类）。",
      "impact": "表格把已记录为numerical_error的位置表述为数值达标或纯取证缺口（或仅以'不计通过'带过），读者会低估gnucap在这些组的已确认失败；也使同一状态值在不同行被渲染成失败与非失败两种语义。",
      "requirement": "违反COMPARISON.md §2与METHODOLOGY #table-verdicts：确认失败必须直接写原因；'数值达标；取证待补'不得用于确认超差位置。"
    },
    {
      "id": "F2",
      "severity": "中",
      "file": "evas/docs/COMPARISON.md（工程组合表 EC08、EC21 行 gnucap列；基础特性表 F13、F15 行 gnucap列）vs 状态格（$ref:36 for EC08/EC21：gnucap=evidence_insufficient×3；$ref:49 for F13、$ref:38 for F15/EC11：gnucap=evidence_insufficient×3）",
      "trigger": "表格断言 EC08/EC21 gnucap 'Q1 数值超差'、F13/F15/EC11 gnucap '（三档或Q1）数值超差'，但对应状态格在这些组×后端×档位上均为 evidence_insufficient，无 numerical_error。",
      "impact": "表格把证据不足写成确认数值失败，方向与F1相反；同一份528格内部既有力撑F1措辞又有力撑本条措辞的矛盾，说明组格与逐档文字至少有一方未与底层槽位判定对齐（槽级gnucap numerical_error=35 可由 EC02/EC06/EC12/F16/EC04系 另加这些组的Q1拼出，但组格与文字必须择一口径）。",
      "requirement": "违反'证据不足不能混为通过或后端缺陷'与逐格结论须链接实际结果的文档自订规则。"
    },
    {
      "id": "F3",
      "severity": "中",
      "file": "evas/docs/COMPARISON.md（基础特性表 F07 行、工程组合表 EC19 行，gnucap列）vs 状态格（$ref:44：gnucap=evidence_insufficient×3）",
      "trigger": "F07/EC19 gnucap 写'三档 编译失败'；状态格为 evidence_insufficient×3。gnucap compile_failed=21 恰为 EC17/EC18/F20/F06/F08/EC19/F07 七组×3，说明槽级确有编译失败，但组格记为EI，两处口径不一致。",
      "impact": "确认编译失败被状态格记为证据不足（或反之），固定数据内部与文档互相矛盾；F06/F08同口径位置却正确显示execution_failed，暴露状态格dedup/映射错误而非统一规则。",
      "requirement": "违反'确认失败直接写原因'与收据'原执行状态逐项保留'要求。"
    },
    {
      "id": "F4",
      "severity": "中",
      "file": "evas/docs/COMPARISON.md（工程组合表 EC03 行 gnucap列、EC23 行 evas列Q1）vs 状态格（$ref:32：EC03 gnucap=evidence_insufficient×3；$ref:45：EC23 evas=execution_failed×3）",
      "trigger": "EC03 gnucap 写'三档 未满足行为要求'（确认行为失败），状态格为EI；且gnucap behavior_error总数6，状态格中仅EC23可见3，余3应属EC03但格值未体现。EC23 evas Q1 写'事件判号未定'（未定/证据类措辞），状态格Q1为execution_failed。",
      "impact": "行为失败与执行失败在文字与状态格之间双向错位；behavior_error=6的计数与528格可见值无法对齐，固定数据内部不一致。",
      "requirement": "违反'确认失败（含行为失败）直接写原因、未定不得写成失败亦不得反之'及counts须与逐格一致的要求。"
    },
    {
      "id": "F5",
      "severity": "中",
      "file": "evas/docs/COMPARISON.md（基础特性表 F03/F04/F14 行、工程组合表 EC16 行，gnucap列）vs 状态格（$ref:41：gnucap=execution_failed×3）",
      "trigger": "四组gnucap格均写'三档 输入/初态阶段待证'（证据缺口措辞），状态格为execution_failed×3；而同为execution_failed的F06/F08/EC17/EC18/F20 gnucap在表中写'编译失败'。",
      "impact": "同一execution_failed状态被渲染为两种语义；若F03/F04/F14/EC16的gnucap失败另有具体原因（如输入异常），按文档规则应写明原因而非'待证'，当前措辞把确认执行失败表现为待完成验收。",
      "requirement": "违反COMPARISON.md §2'确认失败直接写原因…这些待完成项不等于失败'的分类规则。"
    },
    {
      "id": "F6",
      "severity": "低",
      "file": "evas/docs/COMPARISON.md（工程组合表 EC09 行，ngspice列）vs 状态格（$ref:37：openvaf_r_ngspice=evidence_insufficient×3）",
      "trigger": "EC09 ngspice 写'三档 数值超差'；状态格三档均为evidence_insufficient。",
      "impact": "同F2类错位，单点；ng numerical_error=14可由其他组+可能的槽级EC09拼出，但组格与文字口径不一致。",
      "requirement": "违反逐格结论须与固定结果一致的规则。"
    }
  ],
  "missing_context": [
    "首次完整基线20261012-breadth-baseline.json的逐组槽位未随包提供，README关于'F14/F20/EC17/EC18/EC19 Q3原来拒绝、本次返回波形'及EC21旧89.8498s/新90.0165s的原件无法独立核对（决策与诊断文字相互一致，但数值本身无原件）。",
    "F1–F6所涉底层逐槽判定（variant级numeric/behavior轴明细）未在包内展开，无法判定是528状态格错误还是表格文字错误，只能确认两者不一致。",
    "所有SHA256（收据762a6a…、内核ae8e012…、源码/波形/镜像哈希）按约定不复算，视为作者声明。",
    "7文件diff的完整changed hunks未逐字给出（仅nav/candidates片段），无法核对除三主文档外其余四文件的全部改动。",
    "旧7e8首次基线、七份机制草稿、完整session历史与全部raw均未提供，未审部分不作推断。",
    "support README历史bulk明示省略，历史节仅按供给文本审查。"
  ],
  "limitations": "只读静态审查，无文件系统/执行工具；行号不可用，定位以文档章节与表格行为准。已核对且一致的关键项：总852=154+510+132+50+6与四后端final轴逐项求和一致；EVAS 105/81/27与README/COMPARISON一致；新36槽全部waveform_available、ReadbackError（$ref:313与settings_readback.py ngspice()的wrdata正则不接受带引号节点一致）、numeric unknown、behavior pass、config/native/runtime unknown，与两文档'配置读取器待适配/adapter缺口非后端缺陷'措辞吻合；dc-1请求0x1.fffffffffffffp-2而三档导出全部0x1.0p-1（186/376/2165行全不匹配）、dc-0逐位匹配、OSDI逐槽byte-equal，与README/COMPARISON/METHODOLOGY的F03叙述一致且未武断归因；EC21回退保留为失败措辞一致；决策日志两行数字与counts一致；settings_readback.py无请求值回退、无双source写法，与'quoted wrdata被拒'解释自洽。本审查不构成science pass、不批准任何open proof、不修改科学结论。"
}
