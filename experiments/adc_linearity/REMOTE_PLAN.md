# ADC 首题 Spectre 首批校准计划

状态是准备完成，未启动远程仿真。本计划冻结输入与资源，在实际运行前由协调者核对
Spectre实际版本和资源。它不记录第二份任务进度。

输入是 `benchmark/tasks/va08-adc-linearity/tests/cases.json`、原创reference与
`prepare.py`产生的六个错版。`prepare.py`生成各ADC、网表和candidate的 SHA256 manifest，
执行时保存同一输入身份，不在运行中改阈值、容差或求解设置。

| candidate | 场景 | 独立预期 |
| --- | --- | --- |
| reference | ideal-fast / alternating-slow / missing-code / endpoint-shift | 四项全部通过 |
| old-code | ideal-fast | samples.csv读取时间不符；转换尚未更新 |
| missing-first | ideal-fast | 缺少index0，样本记录少于4096 |
| missing-last | ideal-fast | 缺少index4095，样本记录少于4096 |
| all-samples | endpoint-shift | 内码DNL分母错误，原始bus重算不符 |
| reversed-bits | alternating-slow | 逐次code与原始bus/阈值真值不符 |
| ideal-only | alternating-slow | 非均匀码宽的DNL/INL不应全为0 |

共10次场景仿真，这是定向校准分母，未计划28次全交叉。参考解正常后才归因错版失败；
若真实ADC不符独立真值，停止判候选并保留环境错误。非目标编译错误也不能证明该错误类别
被checker拒绝，需要修复校准资产后重跑受影响病例。

每场景固定 stop=4.102ms、maxstep=20ns、单线程、conservative、reltol=1e-6、vabstol=1e-9。
每场景timeout90秒，总仿真上限900秒，加7个candidate版本查询最多210秒。
调度上限1 CPU、1 GiB内存、2 GiB总磁盘，单文件256 MiB。
PSF ASCII保存13个字段，约205k基础时间点另加边沿点，预计单场景60至150 MB。
必须在调度端显式设置足够文件上限，不能使用32 MiB默认上限后悄悄调整。
保留10场景波形预计0.6至1.5 GB，实际超过2 GiB时停止并交接资源问题。

参考解执行 `tests/test.sh` 全四场景；各错版执行 `tests/test.sh --case <表中场景>`。
每次设置独立 `VERIFY_OUTPUT`，设置 `CANDIDATE` 与 `SPECTRE`绝对路径，预建 `/work/output`。
候选输出固定目录意味着这些运行须串行。记录 `spectre -W` 实际输出、输入身份、完整日志、
退出码与波形身份。目录中有旧产物时换新目录，不能据此复用reward。

本地 Python 语法、渲染身份和6项checker行为回归可执行；本机没有 Spectre/openvaf。
Icarus Verilog 不接受 Verilog-A，不能充当VA语法验收。
VA真实编译、浮动电压输出节点、总线端口展开、timer及文件I/O须由首个reference病例检查，
仅静态阅读网表和原创VA不能证明框架可执行。
