# R01 最终候选的有限参考证据

七项基础模型与最终候选 `bbf1a3bcb617b3a1b6bf524cd470f73daad07dc9` 重新配对后，按原判据通过7/7。三项初态模型的18个精确原生查询点，以及10条显示记录的顺序、次数和值，也符合独立答案和同一候选的保存结果。本目录保存可读的小型输入和有限响应。三份原始 VA 含尾随空格，以 `dut-source.json` 字符串保存原字节；静态复核解码后核对同一原源 SHA256。完整 Spectre 波形、日志、运行环境只在本地，归档 SHA256 不能代表公开可下载的证据。

这些是新增控制，原70、19、16及Q统计和 #131 均保持原状。历史失败与旧核配对结果仍在原证据中保留。本目录不把新增通过转成原成绩，也不证明更广组合或整个连续时间域正确。

## 判据与结果范围

基础模型为 `initial_integer`、`display_final`、`bsource_chain`、`bsource_feedback`、`rational_bound_state`、`held_exponential` 和 `selected_feedback`。每例查询0、0.25、0.5、0.75、1秒，读取原生十进制 token，不插值、不用邻近点替代。`initial_integer` 的绝对电压预算为0，其余为1e-8 V，相对比较预算均为0。

`oracle.py` 保留原独立有理数级数及余项包围。基础批的原分析在全部保存原生行上核过解析式，并核对五个查询时刻的最终 EVAS 与 Spectre 响应。各例 `evidence.json` 保存原分析的行数、最大误差、资格及分析SHA256。这里的静态脚本仅复算保留下来的有限查询点，不能独立重放未收录的完整波形。

初态三例每例查询0、0.125、0.25、0.5、0.75、1秒，固定预算1e-8 V。`ordered_records` 和 `prior_initial_condition` 的 y 均为六个1，显示顺序为 before=0、after=3、timer=3。`zero_or_neighbor` 的 y 为1、1、1、1.5、2、2，显示顺序为 before=0、after=3、timer=4、neighbor=5。

初态答案来自已保存的独立 Astra 分析。该分析对照原 unit 断言和语句顺序推导：n 默认0，initial 先显示0、赋3、显示3；带条件的零 timer 读取3；OR 的两个零叶共用回调体，仅增至4；正邻居再增至5。active 的零回调使 a=1，0.25秒变2，半秒 transition 在0.5秒为1.5，在0.75秒为2。`initial-unit-contract.py` 保存同源 unit。原 PLAN.expected_display 是由 DUT 生成的，不能作为独立 oracle；本包不使用它校核。

## 身份与精度

基础 raw 的35项输入清单、185项输出清单，以及初态 raw 的10项输入清单、92项输出清单逐项重算SHA256，全部匹配。VA、Spectre deck和基础 REQUEST 与冻结输入逐字节相同。两批 Spectre 前后工具身份一致，版本为21.1.0.509.isr12。清单、工具、完整本地归档和PSF的SHA256见 `provenance.json` 与各例 `evidence.json`。

最终 EVAS 的289项执行收据源码哈希和内核SHA256均匹配。基础执行前后源码及内核保持不变。`source-identity.json` 保存相对源码路径及哈希，不含私有机器配置。内核为 debug 核，SHA256为 `db5284c07ea10939f42519322b975f4e02bd1d625c828ca182fbe5b219b9a07f`。二进制自报 build_revision 为空，收据绑定不等于可重复构建证明。后续文档提交不改变这份数值执行身份。

请求及实际设置分别保留。基础批请求 maxstep=1/8192秒、reltol=1e-10，PSF实际打印 maxstep=0.000122070、reltol=1e-11、tolerance.relative=1e-10、vabstol=1e-12、traponly。maxstep 是打印值，不能解释为比冻结 deck 更精确的有效参数证明。初态请求 reltol=1e-9，PSF实际为 reltol=1e-10、tolerance.relative=1e-9、vabstol=1e-11、maxstep=0.03125、gear2only。本包保存原生 token 的全部导出位数，不用 binary64 重新格式化替代原文本。

## 仍有的限制

初态 deck 的 `strobeoutput=strobe` 无效，Spectre 发出 SFE-1994 并忽略该值。实际输出仍包含所需18个精确原生点，因此有限比较成立，但不证明请求的 strobe 模式执行成功。原警告保留在每例JSON。

三项初态 Display 原文本没有 `$abstime`。直接观察支持顺序、次数和值，不能单凭日志证明隐藏回调发生在数学上精确的0或0.25秒；名义时刻还依赖源码语义和波形推断。基础 `display_final` 有时间文本，保留其直接时间记录。

外部 maxstep 比模型 `$bound_step` 更细，本批不能证明其内部网格约束。通过有限点及原生保存点检查也不能证明非线性奇点、多根历史、其他初态或任意联合组合。EVAS 与 Spectre 的数值方法不作等价声明。

## 静态复核

在本目录运行 `python3 -B verify_finite.py`。脚本只使用标准库和本目录独立 oracle，核对文件哈希、精确查询 token、有限点独立答案、DUT响应及显示顺序。校准包含正确值接受、错误参考值拒绝、非精确查询时刻拒绝、错误DUT拒绝、错误显示顺序拒绝及非有限值拒绝。它不导入EVAS，不构建，不运行仿真，不访问远端。`STATIC-CHECK.json` 是本次实际运行结果。
