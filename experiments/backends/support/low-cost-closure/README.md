# 有限低成本闭包证据

本目录固定wave12统一开发候选的合同与收据。158个生产源码文件与release核 `83da6b2b521c` 已冻结，IR25；198通过的比较基线仍为 `f6465c42`。
PR208仍是草稿，尚未合并。完整源码身份、runner、worker、原checker、normalization、输入索引和预算见 [evidence.json](evidence.json)。
该JSON为仓库内紧凑证据；原件、波形、源码归档和完整运行收据仍是local-only，哈希不代表公开可复现。

最新全量为wave12同一158文件源码与 `83da6b2b521c` 的400原件：292通过、18失败、90拒绝，310完成，清理400/400。
collector已核验42件与其余358件使用相同源码、内核、runner、worker、checker、normalization、输入和预算。
原198及有效波10的278份通过全部保留，比波10新增014、015、017、057、100、124、150、190、223、240、310、311、312、350，共14份，无回退；18项旧checker失败字典保持。
按原固定成员从同次400重算125子集，92通过、9失败、24拒绝，清理125/125。距350还差58份，完整400结果不替代开发回归或共同资格。
Rust457项和2项IR通过，原1项忽略保留。3项IR身份旧断言已同步为IR25，所属8项重验通过。本地完整Python2210项收齐，2206通过、3项已迁移的旧断言失败、CO-SH-01未优化debug核90秒超时；原报告保留。
CO-SH-01在历史debug核也超时；本轮按既有CI opt1构建、保留debug断言和溢出检查，原90秒的两份完整请求通过。
生产源码已推送 `8111d3dc`，8111d3dc的CI完整Python2210项全通过。两个安装job因源码包漏掉新回滚夹具失败，清单已补齐，安装复验中。局部重验不冒充新的完整优化回归。
历史波10为278通过、18失败、104拒绝。波11的274通过、12失败、114拒绝保留为失败候选；十份Select旧通过回退已由wave12完整400验证恢复。
历史波8为272通过、18失败、110拒绝，新增026、098、194，原收据保持。
历史波7的150文件源码与 `1d0845b6` 的269通过、18失败、113拒绝保留原身份。
波7独立逐例比较波6b新增129、137、138、224、233、295、296、380共8份、无回退；相对波5新增35份、无回退，296恢复。
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
224通过原checker，050、052当时因source transition证明预算拒绝，波10在原预算内复用证书后通过，wave12保留。296已在波7恢复。
历史波6b局部探针复现guard乘加溢出被符号证明绕过；波7finite gate已修复，同一冻结源码与release核的三组负控均明确拒绝，原反例与两种内核身份均保留。
波8纳入194的[隔离整数输出读取](../../../../evas/docs/math/events.md#settled-integer-reads)与098的[点时间证明](../../../../evas/docs/math/events.md#held-time-point-proof)，026也通过原checker。
局部作者与独立审查身份单列在JSON；Rust的421通过、1项原忽略仅在117份完整Rust／构建／夹具闭包逐字节一致后复用，不冒充新的release执行。
Slew、后续证明缓存及tanh不属于历史波8身份，不计入当时272；它们已纳入wave12的292。194在历史波7因256组合预算拒绝的记录保留。

wave12另统一验收只读声明、紧凑物理Select、整数不变范围及初始化种子不变性。
初始化formal和concrete各保留原2m配额，input-aware证明只消费concrete余量；精确表达式访问、算术和每次幂乘均计入该账本，耗尽不退还。
两组独审与缩小预算的合法IR反例通过；这证明计费缺陷已修复，不声称复现原2m公开请求越额。
可选全局整数证明耗尽原100000工作量时只退回完整signed32未知范围，原索引、类型和运行时错误继续拒绝。
公开合同见 `test_initial_seed_invariance.py`、`test_integer_invariants.py`、`test_compact_physical_select.py`，各修复独审身份单列于JSON。

原checker、VA、testbench、精度、输出网格、120秒内核、150秒guardian及256组合、4096展开决策预算保持。
没有新增实际Spectre、正式r53或Q资格。LRM、固定legacy和OpenVAF结论仅供语言与源码顺序参考；有限点、正下界和选择树属于EVAS工程合同。
