# D7 精确事件边界的 Spectre 单变量诊断

2026-10-06，新增六次真实 Spectre 21.1.0.509.isr12 64bit 串行执行均退出0、无超时。
六例在真实精确 t=3 均导出 count=1，EVAS 均为2；t=3+5e-8 和延长 stop=3.0000001 均为2。
因此六例均保留 `EXACT_EVENT_STATE_DIFFERENCE`，没有整体对齐通过或合并批准结论。
原24次执行及原数值八配置的4 PASS / 1 FAIL / 3 INCONCLUSIVE 分母和结论保持不变。

本轮保留 EVAS 的精确常导数根证书；没有发现足以修改 EVAS 源码的反例。
步长和积分方法影响数值轨迹及事件导出偏移，收紧单项容差没有恢复本例精确边界状态一致。
可审核的结论是特定版本、特定模型与设置的兼容差异，不能称一般 Spectre 行为或 LRM 违规。
是否接受这一明确范围的例外仍待项目审查与用户决定。

## 执行前冻结与身份

物理模型是 z'=0.5sign、z(0)=0、初始sign=1、阈值±0.5，每次有向cross将sign取反并累加count。
独立数学根是1、3秒；EVAS的到达段所有/stop提交约定要求在根处分别读到count1、2。
六例VA逐字相同，均继承原batch-03 half-after完整609输出请求，stop=3.0000001。
五个变更均单独相对baseline，不是逐项累加。
外部电压每端1µV、双端2µV、完整事件括区±2e-7s、计数差0，在执行前固定。
精确事件计数、完整导出括区、远离事件的平台计数与延长stop计数分开判定。

默认设置为reltol=1e-12、vabstol=1e-14、iabstol=1e-18、step/maxstep=.005、traponly，
cross ttol/vtol=1e-10。六项求解器控制的有效设置由实际日志独立回显并经已有parser读取。
stop仅有舍入日志摘要3与完整raw末点3.0000001，没有全精度日志回显；
ttol/vtol仅由冻结netlist的实例参数证明请求值，六份日志没有其独立有效值回显，故effective未知。
输出括区变化是观测事实，不能替代缺失的参数回显。
冻结contract保留parent的`spectre_requested`和旧设置说明；每例`single_changed_setting`、实际netlist
与本轮分析的derived requested明确覆盖唯一变化，不把继承字段冒称新例的完整请求。

复用原remote_runner及真实工具路径；每例CPU1、4GiB地址空间、32MiB单文件、90秒含30秒license wait，
串行、不retry。预检launcher/setup哈希，六份实际日志均核验版本；没有新逐例/proc映像抓取。
回收清单核验74个冻结输入/收据所列raw文件哈希。baseline解析后的完整时间/波形序列与原batch-03逐项相同。执行与采集收据见[紧凑记录](d7-alignment-followup-results.json)。

ttol/vtol属于模型参数，分别以新sim.json在固定EVAS head
`ffc602cb82445617599e62cb3ac0f7b85f8dced6`实际执行，均退出0、无超时并满足独立答案。
内核SHA为`48ad82b0948efc9e03a6d7e5cba11c94fa43a233169affbe1ce8b9f2e3329ac5`。
该固定head的完整 `dynamic_roots.rs` 文件SHA为
`347f537d44c275e9666102a1a44549e8d477b5b3b92e8aa84f899c6c49790241`，包括测试代码。
原端点诊断的production提取SHA另有其范围，不能替代这份完整文件身份。
本轮后续提交只改文档/证据，模拟器源码未变。原实际build identity记录当时git_status为空、
fixed head、完整source_sha256、build command/log SHA及上述kernel SHA；新两份收据的kernel SHA与之完全相同。
本轮事后逐项核验原source manifest的全部文件与fixed Git快照及当前文件相符，production diff为空。
原build身份、全源码清单摘要及实际复用链就地保留于紧凑记录。
新ttol/vtol收据本身没有dirty/source snapshot字段；本轮不补造这些字段。
进入工作树时观察到clean，且模型参数执行先于本轮文档写入；这是会话观察，不能冒称执行瞬间的独立dirty快照。
其余四例复用原batch-03同物理模型的EVAS raw及收据，独立答案与有限电压配对通过。
这些Spectre专用solver控制没有声称同名EVAS映射，也没有冒称四例新EVAS执行。

## 六例事实

下表第二括区的前点都为真实t=3、count1，后点为真实count2。它只是输出转换的括区，
不能把后点当作内部callback精确时间。六例两次完整括区都在冻结±2e-7s内，普通平台及延长stop计数通过。
连续电压最大独立误差低于1.18e-9V，双端有限电压比较也低于2µV。
紧凑记录内的pair PASS只覆盖609个连续电压点与600个普通计数点。普通count比较排除
`|t-1|<=2e-7`或`|t-3|<=2e-7`的九个请求，唯独延长stop=3.0000001仍比较。
count_error=0适用于这600点及另列的精确事件检查；精确事件依然FAIL，不能把pair PASS引用为609点计数一致。

| 唯一变化 | 第二括区后点 s | t=3 的z V | 精确t=1 count | 精确t=3 count |
| --- | ---: | ---: | ---: | ---: |
| baseline，无变化 | 3.000000001250754 | -0.4999999993996228 | 1 | 1 |
| maxstep=.001 | 3.000000000250001 | -0.4999999998999995 | 0 | 1 |
| method=gear2only | 3.000000000067259 | -0.4999999999913707 | 1 | 1 |
| vtol=1e-12 | 3.000000001203749 | -0.4999999993986257 | 缺观察 | 1 |
| ttol=1e-12 | 3.000000001202251 | -0.4999999993991245 | 缺观察 | 1 |
| vabstol=1e-16 | 3.000000001241916 | -0.4999999994040422 | 1 | 1 |

vtol和ttol两例未真实导出exact1；近邻分别为1.000000000001和1.0000000000005。
不能用这些近邻count1填写exact1通过。这两例609请求覆盖单独为INCONCLUSIVE，
其余四例覆盖通过；六例都有真实exact3，足以确认该边界的计数失败。
普通网格表示偏移仍只在无跨事件的有限窗口内用独立0.5*dt电压变化界记录，不插值离散状态。

## 推断与未知

事实是所有t=3数值轨迹都尚在下阈值之上。按继续保持-0.5V/s线性外推，
到下阈值的等效时间余量是`2*(z(3)+.5)`。baseline约1.200754ns，maxstep约.200001ns，
gear2only约.017259ns；各第二括区后点的偏移约为这个余量再加.05ns。
单独ttol收紧后，后一项约为.0005ns；单独vtol收紧后约为.001ns。
这是原始数值的算术关系，支持“累计轨迹误差与cross后侧定位共同影响精确边界观测”的解释。
有限输出不能证明内部积分算法、实际过零或callback时间，也不能证明其对所有容差/版本成立。

[LRM 2.4 §5.10.3.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
将cross事件约束在实际过零之后的时间/表达式容差内；这不保证解析数学根处的离散观察相同。
按解析根直接计算的约1.2ns偏移也不能独立证明Spectre违反1e-10的cross容差，
因为本例数值轨迹在解析根处尚未达到阈值。
EVAS继续选择已经认证的精确根及事件后观察，不能硬编码上述延迟去模拟某个Spectre设置。

本轮未重跑原stop=3，因此其count1结论继续明确复用原真实执行。
新增六例都延长stop用于定位；没有用延长后的count2重新判原stop失败通过。
工程允许窗口内的转换顺序、电压和最终计数可作为有限匹配证据；精确stop/event离散状态兼容仍有缺口。
没有证明普遍步长收敛、其他Spectre版本、一般非点根、或#70双向自换向。

## 可复算性与检查

本地原始目录为daily entry下`runs/d7-alignment-followup-20261006/`，
紧凑收据只公开逻辑archive ID与可移植`${SPECTRE_BIN}`命令模板，模板不是实跑精确命令。
真实机器安装路径、完整argv与服务器归档位址仅保留于local-only原始RESULT/collection收据；
公开摘要继续绑定其原SHA与archive SHA，不修改raw或历史证据。
可用性为local-only/授权服务器可取，不声称公开raw复现。
冻结准备、dispatch、collection、analyze、两例EVAS启动器和完整input/raw/收据都在此新目录，旧包未改。
复算命令是`python3 -B runs/d7-alignment-followup-20261006/analyze.py`。
新增校准实际断言宽括区、错误计数转换、exact计数1替代2、缺exact观察均拒绝，正控通过；
沿用已校准的原数值oracle/配对checker并绑定其SHA。分析首版要求所有关键点exact而在缺exact1处中止，
保留旧脚本后修正为逐项记录缺观察；没有放宽精确事件门槛或重跑模拟器。
两例EVAS启动器首版用了错误manifest键，执行前即报KeyError；修正后各实际执行一次。
GLM复核后的设置/配对范围说明与build复用链属于事后证据解释补充；
原receipt、冻结contract、ANALYSIS与raw字节均保留，没有补造执行当时字段。所有新增结论仅属于开发诊断。
