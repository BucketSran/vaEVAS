# 开源后端实际失败归因（本地只读）

本轮最主要的基础语言“缺波形”不是已证明的语言能力缺失：v2 NG part1 的 36 个 F03 槽全部编译成功并生成 186–2165 个瞬态数据行，但 `wrdata` 在 `v(lt)` 处发生表达式语法错误。这批应归为导出接口失败，比较、逻辑、三元表达式的完整瞬态结果仍未检验。另一些模型确有编译器明确拒绝或初始工作点失败，不能混为一种“不支持”。

只读范围：旧 batch NG foundation part2 与完整封存的 v2 NG foundation part1；未启动仿真、编译器或远端进程，未修改 DUT、deck、checker、原 RESULT、预算或生产代码。统计仅描述执行/现有分析，不是新评分。已使用 evas-validate 的归档证据检查要求。

## 身份与可复核入口

工作目录为 `/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current`。下面路径均相对此目录；配套 [evidence JSON](open-backend-failure-attribution-evidence.json) 收录每槽源码、网表、日志、RESULT、已有波形的绝对路径、SHA256 与大小，共 132 个执行槽。

- 旧 part2：`runs/evas-overnight-20261012/batch/collected/foundation-openvaf_r_ngspice-part2/`，COLLECTION 验证 1149 文件，archive SHA256 `05da90d59edd71efd746dfb27fce028e5711b8f9e75d265097806c566ebf3e05`；39 槽中 27 waveform_available、6 compile_failed、6 missing_waveform。
- 新 part1：`runs/evas-overnight-20261012/batch-v2/collected/foundation-openvaf_r_ngspice-part1/`，runner 收齐后 COLLECTION 验证 2673 文件，archive SHA256 `65eece9179a198af79e408a5b3b4167b6bc63f3c4e49f7a6287245e1cd72234c`；93 槽中 45 waveform_available、39 missing_waveform、9 compile_failed。本轮未读取 live 输出。
- 两 lane 的 `outputs/<lane>/TOOL_IDENTITY.json`：实际 compiler SHA256 均为 `ca1037be094cbfecb1249a1f220c9c390bc265015dd177ec27800ed365d6ef3a`，自报 OpenVAF-reloaded unknown；ngspice 自报 46。不能用目录名 v24.0.2mob 推定二进制对应公开源码提交。
- 编译运行容器 config ID 分别 `069ae46add7bed372258a47697ee211761db85cce726db86e18e1d77bad64832` / `233b15bcc2bdfd40c915dbf6ed41d731306f64083885d1255ae1bdd37cdcb555`（SHA256）。与 `experiments/backends/support/20261010-ngspice-events.json` 的既有实际诊断 compiler hash、两个 image config hash 一致；该诊断可复用到同二进制的事件假设，不证明新 DUT 的每一因果细节。
- 旧 part2 现有最终分析在 `runs/evas-overnight-20261012/analysis-foundation-openvaf_r_ngspice-part2-final-v1/`。39 槽现有分析为 19 pass、2 numerical_error、18 evidence_insufficient。此处保持原分析，不重新判分。

各原始 case 位于 `<collection>/outputs/<lane>/runs/<case>/`，代表下面列出的 `dut.va`、`tb.cir`、`compile.log`、`simulate.log`、`waveform.txt`、`RESULT.json`。

## 新 part1：先区分出口、编译与真实求解失败

| 范围 | 直接观察 | 归因与限制 |
| --- | --- | --- |
| F03-dc-0…11，全部 Q1–Q3，共 36 槽 | 编译完成；每槽 TRAN 有正数 DataRows；随后 `PPerror: syntax error in line segment`，箭头落在 `v(lt)` 中的 `lt`；无 waveform.txt | 已定位失败阶段为 ngspice `wrdata` 表达式解析。`lt/le/gt/ge` 节点名与比较运算符词法冲突是强推断，须只改出口引用的 probe 确认。不是“比较/逻辑不支持”的证据。 |
| F01-base、F09-base/reordered，共 9 槽 | 编译在模块实例 `leaf a(...)` / `child #(...)` 上报 unexpected token、expected discipline；compile returncode 65，无 simulate | 固定编译器前端拒绝内部层次实例语法。不是 SPICE Newton 或网表导出失败；不能扩大为宏、参数或所有层次能力均缺失。可在宿主 deck 实例化分别编译的叶器件是独立配置能力，不等价于原层次 DUT 通过。 |
| F07-base，3 槽 | 编译完成；初始 OP 失败，count 最后迭代 2422/2424；DataRows 0；后续 no such vector v(u) | 主因发生在求解之前的初始 OP / retained event state，而非 wrdata 缺向量本身。与同二进制既有无条件事件体诊断一致；数组具体 lowering 尚未抽取，不能直接把数组认作根因。 |
| F02、F04、F05、F06、F08、F10 各变体，共 45 槽 | 有 waveform.txt | 只说明出口与执行完成；本轮未把这些槽称为严格科学通过。 |

最小代表 F03-dc-0--Q1：原 DUT 输出 `V(lt)<+(V(u)<0.5)` 等六通道，deck 请求 `wrdata waveform.txt v(u) ... v(lt) v(le) v(gt) v(ge) ...`。log 初始输出 logic_out=0、tern=3，随后 DataRows=186，再报上述 PPerror。F03-dc-8--Q3 的初始 logic_out=1、tern=1，DataRows=2165，出口同错。36 槽逐个模式核对一致。另独立按原常量输入计算 12 个 DC 条件 Q1 的六输出真值，11/12 与日志初始解一致（配套 JSON 保留全部逐项）。F03-dc-1 原输入 0.49999999999999994，deck 保留 17 位，但初始 lt=0/ge=1，相当于按 0.5 比较，原输入真值应 lt=1/ge=0。初始 u 日志只显示 0.5，不能区分输入解析/求解舍入与比较器语义；导出恢复后必须读高精度 actual u 与所有比较输出，才能归因。这个边界差异独立保留，不能将出口修复直接视为全部基础运算科学通过。初始解符合几个预期常量不能代替完整波形验证；也不能从进程 returncode 0 认定仿真成功，ngspice 命令错误仍可能正常 quit。

## 旧 part2：四种原因分别保留

| 范围 | 直接观察 | 可支持的结论 / 未知 |
| --- | --- | --- |
| F16 laplace_np，3 槽 | compile.log 明确 function laplace_np currently not supported；未执行 simulate | 实际固定编译器明确的算子实现限制。不能用 laplace_nd 通过替代 poles 表达式。 |
| F18 slew，3 槽 | compile.log 明确 function slew currently not supported；未执行 simulate | 实际固定编译器明确的算子实现限制。 |
| F17 absdelay，3 槽 | 编译成功；`singular matrix: check node n0#implicit_equation_0`；初始 OP 失败，DataRows 0 | 这是 compiler/OSDI/宿主的历史算子接口或初始化问题候选，不是明确前端不支持，也不是已证明“缩 maxstep 就可解决”。公开固定源码分析曾指出 absdelay descriptor 扩展及宿主消费缺口；实际 compiler 未有公开 commit 身份，因此尚需实际生成 descriptor / residual 的 probe 才能落实具体因果。 |
| F19 transition+timer，3 槽 | 编译成功；初始 OP 失败，count 2422/2424；首 timer 是 1us；DataRows 0 | 失败发生在首事件前。事件 retained state 被重复 eval 更新是有同版本实际证据的强假设；不能归因于 transition 边沿太陡，也不能说 transition 单算子已被单独证明失败。 |
| F13 idt Q1、F15 laplace_nd Q1 | 有真实波形，数值下界分别 2.6113940141e-5 V、2.0149830657e-5 V，超过各 1.01e-5 V 预算；Q2/Q3 原分析均过 | 属于所选求解设置下的实际数值失败。收紧容差/步长后既有运行误差下降支持此归因，但不隔离具体是哪项设置。不能判语言算子缺失。 |
| F14 ddt，3 槽 | 编译、瞬态与导出完成；现有分析拒绝 DC/transient phase、输入导数/拓扑 adapter 证据缺失，qualified observations=0 | 证据不足，不是零误差科学通过，也不是不支持 ddt。需要独立建立 t=0 的 DC 相位、正时刻输入原 PWL 斜率及原 knot 左右约定。 |
| F20 idtmod，3 槽 | 编译、瞬态、导出完成；现有分析报 time outside card extent，两个输出 qualified observations=0 | 参考/出口端点衔接问题。逐槽原波形只最后一行 t=5e-6 超过 card stop=4.9999999999999996e-6（相邻 binary64，差约 8.47e-22s）；不可将全波形作零误差通过。还需保留原端点并明确参考 extent 的合同，不能偷偷删除末点。 |

F20 的独立 paper_observer 还有 non-increasing PWL time points 警告，原 deck 同时含 2.4999999999999998us 与 2.5000000000000002us 等近邻点。警告说明测试台有待检查的精确时刻映射；它没有阻止本批生成波形，不能单独解释 idtmod 数值语义。旧卡 stop 由浮点计算形成，而网表/输出解析后的实际终点落到相邻浮点；这个端点事实足以解释当前参考异常，尚不说明其他时刻的相位边界已正确。

F13 另做独立十进制高精度核算：原首段积分为 y=.125+.25(t/T)^2；用原 binary64 T、失败时刻、真实导出值计算误差约 2.61139401723e-5 V，确实超过原 Q1 预算，而非参考包围不确定造成的假失败。计算输入和输出保存在配套 JSON。

求解设置核对注意：log 第一个 `option` 快照显示默认 reltol=.001/vntol=1e-6，不能据此宣称请求选项未生效。loaded-circuit post-analysis 快照为 Q1 请求 reltol=1e-5/vntol=1e-9/abstol=1e-13/trap；RESULT 的 scoped readback 正确区分这两者。maxstep/stop 仍只有 deck invocation 证据，不是独立 runtime readback。F17/F19 simulate 进程也返回 0，却无波形、DataRows=0；出口缺向量是先前 OP 失败的后果。

## 同版本事件诊断如何复用

原材料：`runs/ngspice-openvaf-diagnosis/raw/ngspice-openvaf-diagnosis-20261010/`，compact receipt `experiments/backends/support/20261010-ngspice-events.json`，原 raw.tar.gz 与各轮 FILE_MANIFEST/PROVENANCE 保留。既有实际诊断 39 次编译、39 次仿真，未改变原任务分母。

已观察：未来 timer 的常量赋值在 t=0 已输出 1；cross 常量赋值也在 t=0 输出 1；改 timer 时间或 initial retained 初值仍生成相同 artifact；timer sampler 在首事件前随输入连续变化（output-input 最大差 0）；删除 timer 的对照保持 0，initial-only-five 保持 5。既有 settings 8 个组合无波形。由此支持实际二进制不具所需 timer/cross gate，而非单纯容差问题。公开固定源码分析与这组实际产物吻合，但二进制公开 commit 仍 unknown。

F07/F19 与这组诊断的 compiler hash 和 image config 精确一致；其初始 count 在 Newton 迭代持续增长与上述行为一致。新的数组或 transition 组合尚未逐个做单因素拆分，因此报告只给强假设。不存在“OSDI 不能动态状态”或“所有 SPICE 都不支持事件”的结论。

## 后续最小 probe（待 root/runner 调度，尚未执行）

1. **F03 出口**：保持 original dut.osdi、原源/deck 激励/选项/observer/预算，仅把 wrdata 的 lt/le/gt/ge 引用改为该安装版本接受的 quoted node 引用，或通过 `let` 建无冲突 alias。先用单个 F03-dc-0--Q1 验证完整所有向量及 DataRows，再原 36 槽导出并独立评价。须保留旧失败及新 deck hash；不可修改 DUT 节点名冒充原 DUT 通过。若 quoted 形式仍错误，再最小一源一节点 lt 对照 ordinary_node 区分词法/出口问题。
2. **F07/F19 事件**：沿用既有同二进制证明，优先抽实际 artifact/编译中间码中的事件 guard 和 retained-state 读写；若要执行，单因素去 timer、自增改常量、stop 在首事件前、去 observer。输出 expected count 必须核验，UIC 或容差改变后仅“有波形”不算修复。transition 与数组分别隔离，诊断变体不替换原评分。
3. **F17 历史接口**：保留原 absdelay，抽实际 OSDI descriptor 扩展、隐式方程 residual/Jacobian 与宿主消费路径；对比 delay=0 与去 delay 的同端口控制，先定位 OP 奇异是否专属于历史接口。不要先盲目放松容差。
4. **F13/F15 数值**：原源码与观察不变，仅一个控制量作原设置 vs 更小 maxstep 的诊断；比较同原时刻数学误差及 actual input。已有 Q2/Q3 成功先复用，避免重复无因试验。
5. **F14/F20 证据**：先只读补 adapter/端点合同分析；F14 建 DC/正时刻原 PWL 导数证明，F20 核真实停止点、参考域与 wrap 邻点。若参考合同需要更正，独立审查后重新分析全部原点，保留旧失败，不改预算/丢点。不得先把证据不足改成 pass。

## F03 quoted-node 提案依据与出口限制

已交 runner 单一探针 F03-dc-0--Q1 的原完整目录及 proposal：仅 wrdata 同时将四引用改为 `v("lt") v("le") v("gt") v("ge")`，保留其他引用及全部原源/模型/输入/选项/观察点。仅改 lt 会在下一个保留名再次失败，四名称属于同一种 grammar 修复。root 已授权 runner 在 v2 执行结束后独占执行一个机制 probe；这里尚无结果。

机制依据为固定公开 ngspice commit `ebdaf58ec76a06ffaac7e0f138360dd1cf5ee4b6` 的 [parse.c](https://raw.githubusercontent.com/imr/ngspice/ebdaf58ec76a06ffaac7e0f138360dd1cf5ee4b6/src/frontend/parse.c)：PPlex 786–804 将裸 lt/le/gt/ge 且后跟括号识别为运算符；866–874 的引号分支直接返回字符串 token。[parse-bison.y](https://raw.githubusercontent.com/imr/ngspice/ebdaf58ec76a06ffaac7e0f138360dd1cf5ee4b6/src/frontend/parse-bison.y) 129/144 接受字符串及函数的字符串参数。parse.c 的 ft_getpnames_quotes 也保留已经加引号的节点引用。实际下载文本保存在本报告旁 ngspice-parser-source，带 hash/source manifest。准确安装 binary 的公开 commit 尚未建立，不能将源码预测冒称安装版实测。

runner 提醒旧 native reader 只去 `v(...)` 包装而不去节点引号。probe 必须读取真实 raw header：若导出 header 保留引号，先记录映射资格缺口；不得擅改 reader/checker 或把导出完成计为科学 pass。引用机制是否有效、实际全部向量是否存在和 reader 映射是否正确是三项独立检查。

本轮只生成这份报告、身份索引及公开 parser 源码留档；没有新 probe 结果、没有生产修复、没有科学对齐声明。新 v2 part2 尚未纳入；将由 runner 封存交付后独立处理。


## F03 quoted export 后续实际复验（新身份，不覆盖旧36槽）

runner已完成独立的36槽 export-only 复验，封存路径 `batch-ng-f03/collected/foundation-openvaf_r_ngspice-f03-quoted/outputs/foundation-openvaf_r_ngspice-f03-quoted`，archive SHA256 `aea811f2a437590748c86c654345e15d09a2e620cf84345c9f85b910f56b2edd`；完整collection由runner核验1110文件。这里另逐槽核 manifest 中 DUT、OSDI、deck、RESULT、waveform 的摘要/大小，并与旧对应槽逐字节对比：36/36 DUT与编译OSDI不变，deck仅四个wrdata引用加引号（lt/le/gt/ge），36/36产生waveform。raw header规范为v(lt)/v(le)/v(gt)/v(ge)，旧reader无需修改。该新证据闭合的是先前36个missing_waveform的导出接口原因，不是36个科学通过或完整资格声明；旧失败原件保留。

实际dc-1相邻输入仍有独立问题：deck正确写入 `0.49999999999999994`（预定binary64 `0x1.fffffffffffffp-2`），但Q1/Q2/Q3的17位raw导出全部u分别为 `5.00000000000000000e-01`，实际binary64 `0x1.0000000000000p-1`。三档186/376/2165行逐行核实，lt全部0、ge全部1。因此旧低精度日志中看似“小于阈值却比较为相等”的现象，现不能归因于Verilog-A比较器能力；观测输入本身没有保持预定相邻值。差异发生于deck literal进入实际source/solver/导出链中的哪一层，当前未知。17位输出使证据比旧六位initial OP表强，但没有独立parser/source内部receipt，不能直接断言是某个parser rounding缺陷。

独立只读取证 `review/ng-f03-quoted-followup-evidence.json` SHA256 `9ef52d202d3311472cb3b145999f5e1edf4e617f4be053aae7cf3fc968af0a9a`；原runner输入事实 `ACTUAL_INPUT_BINARY64_FACTS.json` 保留。正式本地科学重分析由core负责，不能用实际0.5重写冻结要求或以36个waveform代替判分。本轮没有修改source/checker、启动远端或新增probe。
