# 有限低成本闭包证据

本目录固定波7开发候选的合同与收据。代码基于 `f6465c42`，150个源码文件与release核 `1d0845b6` 已冻结，IR24保持。
PR208仍是草稿，尚未合并。完整源码身份、runner、worker、原checker、normalization、输入索引和预算见 [evidence.json](evidence.json)。
该JSON为仓库内紧凑证据；原件、波形、源码归档和完整运行收据仍是local-only，哈希不代表公开可复现。

最新全量为波7同一150文件源码与 `1d0845b6` 的400原件：269通过、18失败、113拒绝，287完成，清理400/400。
collector已核验102件与其余298件使用相同源码、内核、runner、worker、checker、normalization、输入和预算。
原198份、波5的234份及波6b的261份通过全部保留，相对198新增71份ID在JSON的完整summary中固定。
独立逐例比较波6b新增129、137、138、224、233、295、296、380共8份、无回退；相对波5新增35份、无回退，296恢复。
历史波6b同一149文件源码与 `5935fd87` 的261通过、18失败、121拒绝及296回退仍保留原身份。
波5同一148文件源码与 `c814d0e3` 的234通过、18失败、148拒绝，以及波1同一146文件源码与 `bc68b05d` 的221通过、18失败、161拒绝均保留历史身份。
波5相对波1新增13份，其中128、232是完整全量发现的额外收益，不能归因于单一事件算术切片。
历史198和181通过也保留原收据与源码身份，结果不是跨候选局部增量相加。

本候选的有限合同包括：

- [有限点初始化与别名](../../../../evas/docs/math/events.md#input-initialization)。real仿射初值只接受有限单点包围，integer电压采样仍拒绝。唯一前序输入别名和准确数组槽保留源码顺序；运行事件读取当前物理根输入。
- [typed整数与有限幂](../../../../evas/docs/math/events.md#typed-integer-closure)。整数除法向零截断，余数保留被除数符号；有限real幂保留类型、读取和原预算。160有限运行除数已在波6b验收并由波7保留。
- [普通条件与有理输出](../../../../evas/docs/math/solving.md#普通-analog-条件)。分支临时量在实际读取时检查，正分母比较事实不外泄。纯输入有理guard和输出必须通过完整程序的实际源依赖、符号与电压认证。
- [timer、根身份与bootstrap](../../../../evas/docs/math/events.md#wave6-local-closure)。过去单次held timer、已证明的输入投影根、236非种子包围传播分别有正反例；029、160、236在波6b通过原checker。111的事件认证限制保留。

公开控制包括 `test_frontend_closure.py`、`test_branch_local_closure.py`、`test_initial_sampling_closure.py`、`test_integer_math_closure.py`、
`test_rational_predicate_closure.py`、`test_positive_clamped_divisor.py`、`test_selected_quotient_comparison.py`、`test_input_rational_closure.py` 和 `test_source_rational_guards.py`。
固定波5独立复核的77项合同与6组探针保留历史身份，不能冒充波6b的新执行。
波5全Python执行2024项、2022通过，一项P/2旧拒绝期待已迁移并复验13方法，另CO-SH-01在90秒超时、旧核对照未决，不能称全绿。
四个过时passive夹具已改为真正负start加正period，7/7 private控制通过，未放宽合法过去单次timer合同。

纯输入多项式guard与有限floor已纳入波7，局部合同与独立审查收据保留原身份，单列于JSON的 `wave7_local_contract_evidence`。
裸floor调用保留用户函数优先和合法参数名，显式 `$floor` 继续内建；有限范围、real类型及预算限制见事件手册。
224通过原checker，050、052仍因source transition证明预算拒绝。296已在波7恢复。
历史波6b局部探针复现guard乘加溢出被符号证明绕过；波7finite gate已修复，同一冻结源码与release核的三组负控均明确拒绝，原反例与两种内核身份均保留。
194、时间证明与Slew属于波7之后的开发，尚未正式验收，不计入269；194在波7仍因256组合预算拒绝。

原checker、VA、testbench、精度、输出网格、120秒内核、150秒guardian及256组合、4096展开决策预算保持。
没有新增实际Spectre、正式r53或Q资格。LRM、固定legacy和OpenVAF结论仅供语言与源码顺序参考；有限点、正下界和选择树属于EVAS工程合同。
