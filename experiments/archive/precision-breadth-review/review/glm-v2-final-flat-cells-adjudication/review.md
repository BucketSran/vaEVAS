{
  "scope": "独立小增量裁决：(1) 以本包直接提供的固定真实762a group/Q轴JSON与原6e1/新388c表格句，逐条裁决前报告F1–F6是当前表格/数据错配还是前报告读数错误；(2) 裁决EC23/EC03新增“拒绝：”前缀是否仅正确表达既有X而不改科学状态；(3) 首次审查4文件（CANDIDATES.md、capability-evidence.md、validation/README.md、paper/README.md）固定历史diff dd33eb9e..6e1f4897。不重审旧v3身份/213/852数学工具、不执行hash/数值重算、不颁science pass、不将空工作区diff称为完整审过。",
  "standards": [
    "文档自订规则：确认失败必须直接写原因，证据不足写明缺口，待完成项不得写成失败亦不得写成通过（COMPARISON.md §2、METHODOLOGY #table-verdicts）",
    "逐格表格措辞须与固定group/Q轴的字段一致；裁决只以本包逐字提供的JSON与表格句为证据，不采信前报告的pool $ref读数，也不采信作者纠错",
    "不得凭缺省旧资料（未提供的counts、taxonomy、receipt）推定bug；无矛盾即不作finding",
    "开发候选/导航文档新增不得改写冻结卡、历史成绩或支持总表结论；不得把开发用例计为独立留出集"
  ],
  "spec": "用户消息内逐字提供的：F1–F6各条所涉固定group/backend/Q轴JSON对象（共约60行）、原固定6e1表格17行句、新固定doc SHA388c表格17行句、4文件完整git历史diff dd33eb9e..6e1f4897。GLM无hash执行/数值重算/公开raw批准能力。",
  "findings": [],
  "missing_context": [
    "各格“numeric/behavior/evidence/config…”以外的高级分类taxonomy（execution_failed是否细分为编译/运行阶段）及四后端各轴counts原件未随包提供，无法核验“编译失败”“瞬态收敛失败”等更具体原因措辞是否与execution_failed细分一致，只能确认其非EI、非通过。",
    "EC23/EC03 EVAS格的“事件判号未定”“误差包围过宽”具体失败原因不在所供cell字段内，需receipt原件（未提供）才能核验该原因描述本身；本次仅裁决“拒绝：”前缀未改变失败/未通过性质。",
    "paper/README.md新增声明“44组共71个必测变体”无法由本包部分组数据（F03=12、F04=5、F14/F16系=1等）独立求和核验，视为作者声明。",
    "其余三份主文档（COMPARISON.md正文其余章节、METHODOLOGY、support README）及diff范围外改动未在本包逐字提供，维持前报告相应结论不重开。"
  ],
  "limitations": "逐条最终裁决（证据仅限本包逐字文本）：【F1推翻，前报告读数错误】真实轴EC04/EC05/EC20/EC24 gnucap三档均为evidence_insufficient（numeric pass或unknown、evidence EI），并非numerical_error×3；表格“数值达标；观察来源待证/支持探针不计通过”与EI+numeric pass/unknown一致，无确认超差被淡化。前报告$ref:33读数错误。【F2推翻，前报告读数错误】EC08/EC21 gnucap真实Q1=numerical_error、Q2/Q3=EI+pass，表格“Q1 数值超差；Q2/Q3 数值达标；观察来源待证”逐档精确匹配；F15/EC11 gnucap三档numerical_error与“三档 数值超差”匹配；F13 gnucap三档EI+numeric pass，表格写“数值达标；观察来源待证”而非前报告所称“数值超差”，且其variant级EI支持“待证”措辞（evidence字段complete与variant EI并存，属轴分离规则内）。【F3部分推翻】F07/EC19 gnucap真实为execution_failed×3而非前报告所称EI，前报告$ref:44读数错误，“编译失败”未把确认失败写成EI，方向性问题不存在；残余限制：execution_failed格写更具体的“编译失败”原因，本包无taxonomy/receipt无法核验该细分原因，按“不凭缺省资料推定bug”不作finding（见missing_context）。【F4推翻，前报告读数错误】EC03 gnucap三档behavior_error，表格“三档 未满足行为要求”直接写明行为失败原因，匹配；EC23 gnucap三档behavior_error与“未满足行为要求”匹配；gnucap behavior_error恰为EC03+EC23共6格，前报告“计数无法对齐”不成立。EC23 evas Q1 execution_failed，表格“事件判号未定”系执行失败导致判号未定的如实描述，且新前缀“拒绝：”已明确其为拒绝而非开放问题，不违反“未定不得写成通过”规则。【F5推翻，前报告读数错误】F03/F04/F14/EC16 gnucap真实三档均为evidence_insufficient（numeric unknown、behavior pass），并非execution_failed×3；表格“三档 输入/初态阶段待证”与EI一致，未把确认失败写成待证。前报告$ref:41读数错误。【F6推翻，前报告读数错误】EC09 ngspice三档numerical_error，表格“三档 数值超差”匹配，非EI。【EC23/EC03“拒绝：”裁决：正确】新旧两表diff仅两处：EC03 evas Q3与EC23 evas Q1/Q2/Q3加“拒绝：”前缀，对应evas execution_failed×3（拒绝类），前缀把既有失败从未通过措辞显式标为拒绝，既未将待证改判失败、也未将失败改判通过，不改科学状态，不涉及后端列，表达正确。历史diff dd33eb9e..6e1f4897审查：4处改动均为文档/导航性质——CANDIDATES.md明确“目前只是开发候选…不能把状态值正确直接等同于事件时刻已证”，措辞克制不越权；capability-evidence.md与validation/README.md、paper/README.md新增44组导航/描述与“数值、行为、证据分别判定”“不修改冻结卡与历史成绩”“不与旧31条件混算”自洽，无科学声明变更、无与所供group轴矛盾的断言，未发现问题。剩余限制如missing_context所列；本裁决不构成science pass、不批准open proof、不修改科学结论，未提供原件的数值/哈希/71变体总数均视为作者声明。"
}
