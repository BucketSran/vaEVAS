# XSPICE 编译入口的独立验收

本目录验证 EVAS 公开 CLI 生成的模型在真实 ngspice 网表中的行为。参考来自实际原生 Spectre 执行；不会自动启动服务器、获取许可证或把复制的参考算作新运行。

当前代码适配 IR33。下文 r53/P0/P1 的 Spectre 次数与结论来自 IR28 历史收据；当前版本的有限初始化复验单列于[IR33 收据](../../../experiments/backends/xspice-entry/ir33-initialization.json)，不替代完整同源对照。

从仓库根目录执行：

```sh
PYTHONPATH=evas/src python3 -B evas/validation/xspice/calibrate.py runs/new-calibration
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate.py \
  --output runs/new-xspice-suite --sdk /path/to/sdk.json \
  --reference /path/to/retained-native-batch
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_instances.py \
  --output runs/new-xspice-instances --sdk /path/to/sdk.json
```

校准输出目录须先存在，仿真输出目录必须不存在。`--python` 可以选择已安装 wheel 的解释器；此时清除 `PYTHONPATH`，确保执行的是安装包。

`validate.py` 通过公开 CLI 编译并构建五个特化，每个构建做一次隔离加载探针；随后执行五电路×两档精度和六个回退运行，共16个电路进程。正例包含 cross、timer、延迟目标生效三处强制回退；三个错误控故意泄漏完整候选帧。每次仿真限制30秒，调用顺序执行。

同源 Spectre 目录须有 `spectre/<case>-<profile>/sample_hold.va`、`tb.scs`、`psf/tran.tran.tran`、`spectre.log` 和 `result.json`。每个参考的物理 VA 与网表必须逐字节相同，源/波形/日志/回执哈希写入新结果。原始模型和设置不同会拒绝复用。

五个电路为 timer 先/后于 cross、短于输出延迟的脉冲、采样输入反馈和时钟反馈。独立答案在 `reference.py`，依据仿射激励的解析 RC 响应及分段线性边沿，未导入被测生成器或 C 历史函数。`check.py` 检查每个已接受点，瞬时状态仅排除固定事件不确定窗；连续输出不排除事件窗。`rollback.py` 核对实际注入种类、完整已接受帧的哈希继承，以及首次回退的状态/游标/队列/边沿不变量。

固定门槛为事件时刻50 ps、电压20 µV；回退与正常运行配对另限50 nV。跨后端连续输出在共同1 ns网格比较。两档 NG reltol 为1e-9/1e-10，绝对容差为1e-12/1e-13 V及1e-15/1e-16 A，maxstep为1 ns/0.25 ns。本轮原生 Spectre conservative 的实际 reltol 为1e-10/1e-11；各引擎仍须分别通过独立合同。

`calibrate.py` 包含一个正确答案及六个错误控，分别检出事件顺序、timer 游标、重启完整下降沿、丢失延迟短脉冲、非有限值及100 nV回退漂移。波形一致不能代替同进程拒步证明；泄漏控最终波形仍过门槛时，应由状态不变量拒绝。

`validate_instances.py` 使用默认无故障入口，检查同一网表中的两个独立实例、RC 反馈、含空格构建路径、不生成默认 trace，以及未经编译启用的故障请求被拒绝。

这些是有限模型的后端准入与组合检查，不是 Rust 内核的Q资格、完整SPICE支持或性能成绩。源码/工具/原始记录与实际通过数由[本轮证据](../../../experiments/backends/xspice-entry/README.md)登记。

## 容差边界与参考准入

`boundary.py` 保留 DC 初值 guard=-VTOL/2 的 crossing，防止把表达式定位容差当作迟滞幅度门槛。固定源阈值0 V，时钟从-0.5 mV上升到0.5 V，VTOL=1 mV，maxstep=10 ps，停止1.6 µs。可先准备并运行 NG，再经显式授权运行该目录生成的原生 Spectre 输入，最后用 `--analyze` 配对。历史漏事件基线保留，不由修正版覆盖。

`native_reference.py` 在仿真或评分前检查成功退出、未超时、Spectre版本及0错误瞬态完成标记、STARTED输入哈希和工具身份。`check_reference_admission.py` 使用真实参考的临时元数据副本，确认失败退出、超时和缺失完成日志都被拒绝；原始参考只读。

<a id="r53-bounded-pilot"></a>

## r53 有限接入合同

六份源码及原始位置由 [sources.json](../../examples/xspice/r53/sources.json) 固定，分别为 benchmarkv4-r53 的068、104、115、124、148、210。它们不代表课题组完整原件。执行源码、独立答案、边界和失败记录见 [r53 收据](../../../experiments/backends/xspice-entry/r53-evidence.json)。

从仓库根目录运行，每个输出目录须不存在：

```sh
python3 -B evas/validation/xspice/calibrate_r53.py runs/r53-calibration
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_r53.py \
  --output runs/r53-events --sdk /path/to/sdk.json --families 104,210,148,115,068
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_chain.py \
  --output runs/r53-chain --sdk /path/to/sdk.json
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_tanh.py \
  --output runs/r53-tanh --sdk /path/to/sdk.json
```

事件合同在执行前固定为1 ps时间预算，另加 `1e-18 s` 的数值匹配余量，以及20 µV的电压预算。独立预期来自 RC 解析解、源规定的采样值和计数序列；没有导入生成器或复制 C 历史算法。所有已接受波形点都评分。连续输出和 RC 观察支路使用每个边沿分别早到或晚到的解析包络，事件窗口没有从连续输出评分中剔除。采样状态另检查事件数量、时刻、初态和数值，整数计数须精确为整数。tanh 反馈解由唯一单调方程求根，导数使用独立的 `sech²` 公式检查。

单路与四路采样都接外部 RC 输入和输出观察支路。148使用两实例、四种输入及端口重排，检查每次同步捕获；115运行超过三个完整周期，检查每次回绕和随后回低。068以两个带不同负载及有限参考电阻的实例检查非零初态、四相时钟和参考端回流。组合电路实际连接068时钟、RC时钟网络、104采样器及输出RC，分别向时钟和采样器注入拒步。每个事件模型保留正常、正确回退及完整候选帧泄漏负控。

`calibrate_r53.py` 检查解析正例，并检出通道交换、丢采样、事件迟到、错误初态、错误参考、缺失RC、标记不回低和非有限值。tanh 另实际构建零导数负控，电压关系仍正确时，导数检查必须拒绝。新检查不替代、修改或放宽原 r53 checker；旧 checker 的六项复验单独记账。

`validate_r53.py` 每个网表默认限120秒，可用 `--run-timeout` 调整执行预算；链路和tanh每个网表限30秒。生成和构建另有有限超时。成功、执行失败与评分异常都由 `trace_files.py` 无损压缩 CSV，解压 SHA256 核对成功才移除未压缩副本；旧运行只读。已有 ENOSPC 中断保留为未完成尝试。原五电路的同源 Spectre 参考继续逐字节准入；每个新正常电路的 `spectre-inputs/preparation.json` 保留当时准备输入的状态；后续原生执行与分析使用新的批次和收据。115与068修复后，固定七例同源 Spectre 对照7/7通过；原RC超差、收敛失败及重试保留，明细见[r53收据](../../../experiments/backends/xspice-entry/r53-evidence.json)。

### 同源 Spectre 对照与重分析

`run_spectre_remote.py` 在既有许可主机上串行执行已冻结的多源VA网表，校验输入清单、记录实际工具与启动哈希，禁止覆盖已有 `STARTED.json` 的执行。`--profile` 与 `--lock` 使用该主机已有配置，本地重分析不会启动远程进程。多模型链路保留两份原VA，仅增加内部状态保存和PSF输出精度。

```sh
python3 -B evas/validation/xspice/calibrate_spectre_r53.py   --phase /path/to/frozen-phase --pilot /path/to/batch/spectre/104   --output runs/new-native-calibration
python3 -B evas/validation/xspice/validate_spectre_r53.py   --phase /path/to/frozen-phase --protocol /path/to/versioned-protocol.json   --batch /path/to/batch --output runs/new-native-analysis
```

各输出目录须不存在。分析检查原VA、冻结网表、成功进程/完成日志、启动收据及实际工具身份，再使用原独立答案检查所有原生波形点和已保存的VA状态。连续配对沿用固定1ns共同网格和20µV门槛，使用线性插值并包含stop；这不表示全时域同点一致。`--cases` 可作部分检查，但只有完整覆盖固定七例才能令顶层 `passed` 为true，部分成功由 `selection_passed` 表示。

本轮Spectre为21.1.0.509.isr12，conservative实际reltol=1e-11，请求值为1e-10。124保留原插值失败，再添加既定1ns网格原生观测通过。115原10ps配置约40.01µV、1ps重试约56.35µV均失败；修复XSPICE跨零双容差接受后，原完整电路的最大配对差约0.168µV。068原gear2only/10ps和traponly/1ps均发生SPECTRE-16927；切换精确等价电容方程恢复收敛，再修复本地默认timer提前触发后，完整配对差约0.167µV。所有原失败保留，未用部分波形补记通过。


### 115与068修复回归

`validate_cross_tolerances.py` 用同一115源码和RC时钟检查首个接受事件，实际守卫残差必须不超过编译时绑定的默认1nV容差；仅满足1ps时间容差不够。它另将host的`minbreak`设为1ps和100fs，分别要求时间分辨率及表达式分辨率不足时明确失败。两项拒绝不计为正常物理电路通过。

`validate_timer_deadlines.py` 用原完整068电路检查默认timer的每次实际状态变化不提前。短5.1ns探针未暴露旧版第二次事件提前的问题，因此回归保留完整57ns。该检查不能替代原全部波形点和固定共同网格的配对验收。

```sh
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_cross_tolerances.py \
  --output runs/new-cross-tolerances --sdk /path/to/sdk.json
PYTHONPATH=evas/src python3 -B evas/validation/xspice/validate_timer_deadlines.py \
  --output runs/new-timer-deadlines --sdk /path/to/sdk.json
```

068的原生参考在`simulatorOptions options`追加`cthresh=0`，保持VA、全部外围器件、激励、标量容差及科学验收判据不变。安装版Spectre21.1的`-h options`明确说明，`cthresh`选择电容的精确等价方程，避免小步长下的收敛问题，不改变电容量或精度。没有添加对地电容、旁路电阻或删除RC支路。修复阶段八次原生尝试共两次进程成功、六次失败；其中去RC的诊断成功不进入固定七例的通过分母。原始回执和官方帮助摘录见[r53收据](../../../experiments/backends/xspice-entry/r53-evidence.json)。

<a id="p0-input-aliases"></a>

## P0：动态阈值、事件采样与下游RC

复用IR28已有输入别名能力，没有修改编译器或运行时。[两份别名VA](../../examples/xspice/aliases/sources.json)与前一阶段编译探针逐字相同；直接表达式版本单列为等价控制，不能替代别名失败。每个模型经当前安装包公开入口编译，ngspice与Spectre执行同一VA。来源为有限微例，不是完整DFF/PFD原件。

固定六例为移动阈值`ramp`、恒定CLK仅供电变化触发`supply`、条件采样别名`selected`、两实例共同平移`commonmode`、直接表达式控制`direct`和原近零守卫`nearzero`。前五例各接输出RC观察支路，分别以解析根、采样值和独立RC闭式解检查全部原生点。`selected`只覆盖条件的true叶，不证明换支或false叶。

沿用已接受微例判据：各后端事件误差≤0.1ps，保持值及输出平台≤0.1mV，输出边沿≤5mV，RC全轨迹≤0.1mV。配对预算分别为0.2ps、0.2mV和10mV，RC不排除边沿。保留1ns共同平台网格与stop，另检查固定边沿分点及两侧边沿内原生点并集。近零例逐字保留原VA、网表、刺激和50ps/20µV判据，不能套用微例预算。

```sh
python3 -B evas/validation/xspice/calibrate_aliases.py runs/new-alias-calibration
env -u PYTHONPATH /path/to/installed/bin/python -B evas/validation/xspice/validate_aliases.py \
  --output runs/new-alias-ng --sdk /path/to/sdk.json
env -u PYTHONPATH /path/to/installed/bin/python -B evas/validation/xspice/validate_alias_rust.py runs/new-alias-rust
python3 -B evas/validation/xspice/validate_spectre_aliases.py \
  --phase runs/new-alias-phase --prepare --local runs/new-alias-ng --nearzero runs/new-nearzero
```

输出目录须不存在。`--prepare`仅冻结输入，不启动远程；近零输入由原`boundary.py`准备。获授权后使用已有`run_spectre_remote.py`串行运行：先核对一例试跑，再完成固定六例。新分析目录使用：

```sh
python3 -B evas/validation/xspice/validate_spectre_aliases.py \
  --phase /path/to/frozen-phase --protocol /path/to/versioned-protocol.json --output runs/new-alias-analysis
```

分析校验工具、启动输入、VA与网表哈希、NG原始证据和近零期望身份，重新评分两后端波形并检查实际采样状态。部分选择只有`selection_passed`，完整六例和两侧别名/直接表达式等价检查均通过才计整组通过。原`preparation.json`保留输入准备时的收据；追加观测保存后，以冻结网表、input-manifest及实际STARTED哈希为准。

当前六例6/6通过；前五例NG五次正常、一次正确重试、一次泄漏负控和一次加密观察共八次运行通过。首次重试及接受帧继承检查不以波形相同替代，泄漏负控须被回退不变量拒绝。正常与正确重试另限50nV。Rust只验同源VA纯电压适用路径，不计外部RC。28项正负校准和两项审阅修复均闭合；初版网格漏边沿、未冻结期望身份的探针、旧协议及重分析保留。详见[P0收据](../../../experiments/backends/xspice-entry/p0-evidence.json)。

<a id="p1-parameterized-clock"></a>

## P1：零起点、最终初态与参数化时钟

按已确认Q14至Q16使用同一[标准整理版](../../examples/xspice/clock1800/README.md)，所有timer/transition表达式和时序参数保持原件；仅适配discipline及六状态显式零初始化。来源哈希与差异可追溯，原件原样不据此取得资格。共享IR28和Rust内核未改。

`clock_cases.py`以独立有理日历定义固定15例：零起点、反向关断、正延迟、1fs正起点、二进制独立同刻、声明反序、0.5ps近邻分离、默认32路、42路变体、空循环、每组一次循环、两实例、1000周期、stop前/后。默认0至3700ns共75次发生；42路变体使用2400ns周期、运行至4900ns，检查高于32位的身份。纯时钟64为准入上限，未声称64路满载实测。

科学预算在运行前固定：各后端事件≤0.1ps，保持量/平台及t0≤0.1mV，20ps边沿≤6mV；配对分别≤0.2ps、0.2mV及12mV。正常与正确重试另限50nV，不按周期数累计预算。原两参数timer写法保留默认前端1ps；只有近邻微例显式5fs，不能互相替代。

```sh
python3 -B evas/validation/xspice/calibrate_clock.py runs/new-clock-calibration
env -u PYTHONPATH /path/to/installed/bin/python -B evas/validation/xspice/validate_clock.py \
  --output runs/new-clock-ng --sdk /path/to/sdk.json
env -u PYTHONPATH /path/to/installed/bin/python -B evas/validation/xspice/validate_clock_rust.py runs/new-clock-rust
python3 -B evas/validation/xspice/validate_spectre_clock.py \
  --phase runs/new-clock-phase --prepare --local runs/new-clock-ng
python3 -B evas/validation/xspice/validate_spectre_clock.py \
  --phase /path/to/frozen-phase --protocol /path/to/versioned-protocol.json --output runs/new-clock-native-analysis
```

输出目录须不存在，`--prepare`只冻结输入；实际Spectre须通过已有授权和串行远程入口执行。原生准入检查VA/网表/合同、STARTED、工具、成功退出及完成日志，冻结NG原始波形和追踪。完整15例及两个后端的独立声明反序等价都通过才允许顶层`passed=true`；部分选择只记`selection_passed`。

`clock_reference.py`检查全部原生点，并补独立1ns网格与边沿四分点，避免稀疏波形丢脉冲仍过验；t0不受邻近正事件窗豁免。瞬时状态另查初值、数量、时刻及数值，整数计数精确。NG追踪核对每调用点的周期身份、名义非提前窗口、最终DC候选及首接受帧。NG接受时间数组与模型回调坐标有末位舍入时，以完整Frame哈希和游标匹配候选，并要求坐标相差不超过4ulp；该坐标核对不放宽科学预算。

最终安装包21项NG检查含15个正常电路、DC正确重试、DC泄漏负控、整批正确重试、整批泄漏负控、加密观察及高位身份重试，共19项正例或正确重试、两项预期负控。DC负控必须实际激活且破坏候选重建，可因不收敛没有完整波形；不能计作物理电路通过。整批负控须完成波形、有实际注入和首次回退，再由完整帧恢复不变量检出泄漏。31项校准覆盖缺边沿、t0、预算边界、状态/日程和未激活负控。

Rust公共入口另执行同源15例，检查各查询点电压/状态及事件身份、数量与独立日历；不替代XSPICE的主机回退证明。检查器修正后可用`--reanalyze`在新目录对保留响应重新评分，不启动内核。科学判据不变，旧分析保留。最终结果、所有失败和重试见[P1收据](../../../experiments/backends/xspice-entry/p1-evidence.json)。
