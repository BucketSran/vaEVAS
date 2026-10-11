```json
{
  "scope": "只读静态审查:(1) experiments/backends/paper/inputs.py 与 test_inputs.py 的最小 diff(ngspice wrdata 对 lt/le/gt/ge/ne/eq/or/and/not 九个保留名加引号,仅出口引用);(2) 判定 NEW36 F03 导出实验可否执行(仅导出修复,不构成科学通过、不升级任何 qualification、旧证据不可变);(3) 核对原生成行为/源/设置/其他后端不受影响、reader header 映射、保留词语义;(4) 证据基线:实际 probe 仅覆盖 ng-f03-quoted-export-01(F03-dc-0 Q1,四个名字 lt/le/gt/ge),其余五个名字为 ngspice 公开源码 commit ebdaf58 的词法预测,非安装版实测。审查人未执行任何仿真。",
  "standards": [
    "导出接口修复与科学语义验证分离:wrdata 引号只改出口语法,不得改 DUT 节点名、OSDI、激励、选项、observer、预算(报告第58、66行要求)",
    "旧失败与新产物并存:保留旧 deck hash 与新 deck hash,原 RESULT/波形不可改写(DECK_CHANGE.json 双 hash 机制;报告第58行)",
    "证据分级:安装二进制的公开 commit 未建立前,源码预测不得冒称安装版实测(报告第13、68行)",
    "reader 映射独立核验:旧 native reader 只去 v(...) 包装不去引号,必须读取真实 raw header 确认(报告第70行)",
    "三独立检查:引用机制是否有效、实际全部向量是否存在、reader 映射是否正确,不得互相冒充(报告第70行)",
    "进程 returncode 0 不等于仿真成功;ngspice 命令错误仍可能正常 quit(报告第28、46行)",
    "历史报告 pending probe 控辞仅被本次提供的实际 probe 事实取代,取代范围限于已提供事实"
  ],
  "spec": "判定结论:NEW36 F03 导出实验可以执行,附下述条件。理由:(a) 实际 probe(DECK_CHANGE.json + tb.cir + simulate.log + FILE_MANIFEST.json)证明同一固定安装(compiler sha ca1037be…/image 069ae46a…、233b15bc…,ngspice-46)上,仅将 wrdata 中四个引用改为 v(\"lt\") v(\"le\") v(\"gt\") v(\"ge\"),DUT hash e618a9e1… 不变、PWL 激励与 observer 行逐字不变、选项快照显示请求 reltol=1e-5/vntol=1e-9/abstol=1e-13/trap 生效,DataRows=186 与原 F03-dc-0 Q1 一致,无 PPerror,生成 51612 字节 waveform.txt;(b) 实际 raw header 显示列名 v(lt) 等不带引号,旧 reader 去 v(...) 包装后映射到 observables 成立(该项对四个实测名字为实测事实);(c) F03 批 DUT 端口为 u,a,b,c,lt,le,gt,ge,logic_out,tern,不涉及 ne/eq/or/and/not,故 NEW36 重导出只落在已实测的四个名字上;(d) inputs.py diff 仅改 ng deck 的 wrdata 一行,signals 未变,gnucap .print、spectre save、evas request 均保持裸名,test 同步锁定;失败回退模式与原来相同(同一语法错误),不会更糟。执行条件:(1) 仅按 F03 原目录逐槽复制此单变量 diff,禁止改 DUT/OSDI/选项/observer;(2) 旧失败槽与旧 RESULT 原样保留,新 deck hash 入档;(3) 导出完成仅计为'出口可写',比较/逻辑/三元完整瞬态语义、F03-dc-1 的 0.49999999999999994 边界差异归因(报告第28行)仍属未决,不得据此升级 qualification;(4) inputs.py 中五个未实测名字的引号路径在其实际 probe 通过前不得视为已验证机制。",
  "findings": [
    {
      "severity": "medium",
      "file": "experiments/backends/paper/inputs.py",
      "line": 125,
      "trigger": "ng_operators 集合含 9 个名字,但实际固定安装 probe 仅覆盖 lt/le/gt/ge 四个;ne/eq/or/and/not 的引号形式只有 ngspice 公开源码 commit ebdaf58 的 PPlex(parse.c 785-820)与引号分支(parse.c 866-874)预测,而安装二进制(ngspice-46,hash ca1037be…)的公开 commit 仍未建立(报告第13、68行)",
      "impact": "若 paper A1 的 12 张卡(core-v1.json 未随附,无法排除)或其他后续批次的 observables 含这五个名字,生成的 wrdata 将使用未在固定安装上实测的引号语法;一旦安装版行为与 ebdaf58 不同,失败模式虽回退为同一语法错误(无更劣后果),但会把'源码预测'误当'已验证导出机制'记录",
      "requirement": "证据分级标准:安装二进制公开 commit 未建立前,源码预测不得冒称安装版实测(报告第68行);实际 probe 事实仅取代四个名字的 pending 措辞",
      "recommendation": "在 inputs.py 注释或 qualification_requirements.json 中显式标注:ne/eq/or/and/not 为 lexer 预测、未经固定安装 probe;或在 NEW36 执行范围断言 F03 端口集不含这五个名字(F03 端口为 u,a,b,c,lt,le,gt,ge,logic_out,tern,满足此断言)"
    },
    {
      "severity": "low",
      "file": "experiments/backends/paper/test_inputs.py",
      "line": 27,
      "trigger": "测试断言 gnucap deck 的 .print tran 保留裸 v(lt)/v(not) 等引用不变,但未检查 gnucap 自身表达式语法是否接受这些保留词作为节点名;gnucap 词法冲突在本轮所有证据中均无 probe 或源码分析",
      "impact": "该测试只锁定'其他后端生成行为不变'这一要求(已满足),不能证明 gnucap 出口可写;若未来 gnucap 批遇同名端口,可能出现与 F03-ngspice 同类的导出失败,且易被误读为已由本 diff 覆盖",
      "requirement": "三独立检查原则:引用机制有效、向量存在、reader 映射正确不得互相冒充(报告第70行);export-only 范围声明",
      "recommendation": "在测试注释或文档中注明 gnucap 保留词出口为未检验项,不随 ngspice 四名实测事实外推"
    },
    {
      "severity": "low",
      "file": "experiments/backends/paper/observations.py",
      "line": 34,
      "trigger": "read_native 复用旧解析器,只去 v(...) 包装不去节点引号(报告第70行 runner 提醒);本次实际 probe 的 raw header 显示 ngspice 导出已自动去引号(头部为 v(lt) 等),故四个实测名字映射成立;但该 header 行为对五个预测名字及未来版本无实测保证",
      "impact": "若某安装版本导出 header 保留引号,旧 reader 将产生带引号的列名,与 observables('lt' 等)不匹配,checker 静默失配或列缺失;当前对 NEW36 F03 无影响(F03 仅四名且 header 已实测无引号)",
      "requirement": "reader header 映射须以真实 raw header 实测为准,不得以导出完成代替(报告第70行)",
      "recommendation": "NEW36 各槽导出后先核验 raw header 无引号且列名与 observables 一一对应,再进入既有分析流程"
    }
  ],
  "missing_context": [
    "evas/validation/paper/core-v1.json 未随附:无法确认 paper A1 的 12 张卡 observables 是否含 ne/eq/or/and/not,finding#1 的实际触发面无法闭合",
    "旧 reader 实现(dvs2-starter-pilot/analyze.py、suite.py 源码)未随附:read_native 的 header 解析行为只能依据报告第70行描述与本次实测 header 间接确认",
    "EXPORT_EVIDENCE.json、RESULT.json、AUDIT_RECEIPT.json 的内容未随附(仅 FILE_MANIFEST hash):probe 的向量完整性/全部 10 列逐列断言只能依据 raw excerpt 与 51612 字节体量间接支持",
    "安装 ngspice-46 二进制与公开 commit ebdaf58 的对应关系仍未建立(报告自认),五个预测名字及任何非 F03 端口的引号行为均属外推",
    "F03 其余 35 槽及 Q2/Q3 的原 deck 全文未随附:判定'逐槽仅四名需引号'依据报告第23、28行的 36 槽模式核对陈述,未逐槽复核"
  ],
  "limitations": [
    "本审查为只读静态审查,未执行任何仿真、编译、probe 或文件系统访问;所有'实际'事实均取自用户提供的 probe 产物文本及其自洽性(DECK_CHANGE 双 hash、dut hash 不变、选项快照、DataRows=186、raw header 无引号),未独立复算 SHA256",
    "允许范围仅为判定 NEW36 F03 导出实验可否执行;不构成对比较/逻辑/三元算子科学通过、F03-dc-1 输入 0.49999999999999994 边界差异归因、F07/F17/F19 事件与历史接口问题的任何结论",
    "引号机制证明是 export-only:native/runtime 缺口(来源合法性、native phase/counters、tool identity)仍为未知,qualification_requirements.json 中 'pending' 状态不因本 diff 改变",
    "历史报告中的 pending-probe 措辞仅在四个实测名字范围内被本次事实取代;五个预测名字维持源码预测地位"
  ]
}
```
