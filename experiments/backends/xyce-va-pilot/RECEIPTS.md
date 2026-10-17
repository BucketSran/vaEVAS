# 试点运行收据（issue #200）

日期：2026-10-17。目录：`runs/xyce-va-pilot-20261017/`。

## R1 gold 解 ngspice 基线（步骤 1 前半）

- 环境：`ghcr.io/arcadia-1/circuit-bench-sky130-ngspice@sha256:bd5c425675eb99fc1a2c3bca10b63a871c457613767e2c6984d6c207b3160500`（Docker, linux）
- 输入：bench = Arcadia-1/analog-design-bench @ `sky130-bottom-plate-sampler-pvt`（clone depth 1, 2026-10-17），gold = `solution/circuit.spi`
- 命令：容器内 `python3 verify.py`（bench 自带 verifier，9 PVT 点并行 4 worker）
- 结果：6/6 通过
  - bipolar_acquisition: 2.937 mV（判据 5 mV）
  - hold_isolation: capture 2.992 / shift 0.0082 / reacquire 2.988 mV
  - SFDR worst 88.395 dB @ ff/1.98V/-40C（判据 ≥80）
  - gain error worst 0.3847%（判据 ≤0.5%）
  - stored CM worst 21.3 mV（判据 ≤25 mV）
  - source power worst 0.4976 mW（判据 ≤0.6 mW）
- 耗时 58.7 s wall
- 复现：`docker run --rm -e MODEL=/opt/sky130/continuous/sky130.lib.spice -v <bench>:/app <image> sh -c 'cp /app/solution/circuit.spi /app/circuit.spi && mkdir -p /app/analog_arena_tests && cp -r /app/tests/. /app/analog_arena_tests/ && cd /app && python3 /app/analog_arena_tests/verify.py'`

## R2 Xyce 7.10 + ADMS 环境构建 + gold 解 Xyce 基线（步骤 1 后半）

- 环境：自建镜像 `xyce-7.10-adms:arm64`（linux/arm64），Dockerfile 见本目录 `Dockerfile`，
  构建日志 `build-xyce.log`，摘要 `build-summary.txt`
- 组件与身份：
  - Xyce Release 7.10-opensource（官方源码包 `Xyce-7.10.tar.gz`，sha256
    `93027b1e7dc195538bfb1886f07057ccd6d4be19b7b45943475108c7fb1e587b`，来自
    xyce.sandia.gov/download/1812/）
  - Trilinos 12.12.1（官方 Building Guide 指定版本，sha256
    `fc8c65f192f6dc9a754069919e3fc040640d547ceb4dd8d7efdfb214207ce949`），serial 最小包集
  - ADMS = Qucs/ADMS release-2.3.7（commit `06e1a6cbe1979db94c49e34bc47c0dbe304883db`，
    本地打包 sha256 `04208628962ef552ef5d2b943a264b34bc8c75142d3f3e59604e8adab8d3a160`），
    `admsXml 2.3.7` + `buildxyceplugin` + `/opt/Xyce-7.10/share/xml` 模板齐备（VA 插件链路可用）
  - /opt/sky130 多阶段拷贝自 R1 的 ngspice bench 镜像
- 输入：同 R1（gold = `bench/solution/circuit.spi`），tt 点（1.80 V / 27 C / .lib tt）
- 网表改写（ngspice -> Xyce 7.10，逐条，见 `run/tb_fft_tt_xyce.spi`）：
  1. `.save <量列表>` -> `.print tran <同列表>`，配合 `Xyce -a -r out.raw`（-a=ASCII raw）
  2. `.options` 删去 `filetype=ascii`（ngspice 专属 raw 选项），`method=gear reltol/abstol/vntol` 原样保留
  3. `{supply}`、`{supply/2}`、`{temperature}` 花括号表达式**不加引号**——7.10 对
     `{"supply"}` 报 "Unrecognized character: \""，与旧文档相反
  4. `.lib "<file>" tt`、PULSE 7 参数、SIN 6 参数、`.temp {temperature}`、`.include` 均直接兼容，未改
  5. raw 变量名差异：节点电压 `VSP`（无 v() 前缀）、源电流 `VDD#branch`（无 i(v) 前缀），
     分析脚本侧做映射
- 命令：容器内 `Xyce -a -r /work/tb_fft_tt_xyce.raw tb_fft_tt_xyce.spi`（tran 900n，
  30448 点，求解 30.6 s；BSIM4.5 版本告警属正常，Xyce 按 4.6.1 处理）
- 观测量提取：`analyze_raw.py`（复刻 verify.py 的 80 held-sample/SFDR/增益/共模/源功率算法），
  数据 `run/metrics_tt_ngspice.json`、`run/metrics_tt_xyce.json`、对比 `run/compare_tt_ngspice_xyce.json`
- tt 点工具差（ngspice 46 vs Xyce 7.10，同一 gold、同一 tt 网表）：
  | 量 | ngspice | Xyce | 差 |
  |---|---|---|---|
  | SFDR (dB) | 99.004 | 97.119 | -1.885 |
  | 差分增益误差 | 0.3817% | 0.3987% | +0.017 pct-pt |
  | 存储共模误差 (mV) | 17.976 | 17.972 | -0.004 |
  | 总源功率 (mW) | 0.401 | 0.404 | +0.003 |
  | 80 held-sample 最大差 | — | — | 0.705 mV（rms 0.529 mV） |
- 结论：两器 tt 点一致性良好（采样误差 < 0.71 mV，共模/功率差 < 1%）；SFDR 差 1.9 dB
  来源于 80 点谱底噪声水平差异，均远高于 80 dB 判据。Xyce 基线可用于后续 VA 器件对比。

### R2 复核补记（主会话独立验证）

- 发现并补齐：Xyce raw 变量名（`VSP`/`VDD#BRANCH`）→ verify.py 期望名（`v(vsp)`/`i(vdd)`）
  的规范化步骤原收据未记录。已由主会话独立执行（`run/_normalized_tt_xyce.raw`），
  用 `analyze_raw.py` 重算四项指标与 `metrics_tt_xyce.json` 逐位一致
  （sfdr 97.119093671 / gain 0.003987124 / CM 0.017972358 / power 0.000404349）。
- R2 数据链完整成立。

## R3 理想 VA 开关替换 XM_P/XM_N——Xyce 7.10 联合仿真（步骤 2 + 步骤 3 tt 点）

- 环境：同 R2 镜像 `xyce-7.10-adms:arm64`（注意：镜像缺 `bc`，buildxyceplugin 依赖之，
  需 `apt-get update && apt-get install -y bc` 后再编译；仅编译期需要，跑仿真不需要）
- ADMS 编译（零 VA 语法改写，`va/ideal_sw.va` 原样通过）：
  - 命令：容器内 `cp va/ideal_sw.va /tmp/ && cd /tmp && buildxyceplugin ideal_sw.va <dest_dir>`
  - `from (0:inf)`、`tanh`、`include "disciplines.vams"`（admsXml 自动生成简化 vams 头）均直接支持
  - 产物：`va/build/Xyce_Plugin_ideal_sw.so`
- 插件加载与实例化语法（试出来的，Xyce 7.10 无 .load 器件语法）：
  - 命令行：`Xyce -plugin /work/va/build/Xyce_Plugin_ideal_sw.so -a -r out.raw netlist.spi`
    （`-plugin <path>`，多插件逗号分隔）
  - 网表实例化：**不能用 X 前缀**（报 "Subcircuit IDEAL_SW has not been defined"），
    正确语法 `Y<module> <inst> <nodes> <modelname>`（参照官方 user_plugin/rlc_adms.cir 的
    `Yrlc rlc1 1 0 R=1k` 模式）；**必须配 `.model <name> ideal_sw level=1 <params>` 模型卡**，
    否则报 "Model is required for device YIDEAL_SW!..."（实例参数不能替代模型卡）
  - 替换行（`run/circuit_va_tt_xyce.spi`）：
    `.model iswmod ideal_sw level=1 ron=500 roff=1e9 vth=0.9 steep=20` +
    `Yideal_sw SW_P vsp vgp vinp vss iswmod` / `Yideal_sw SW_N vsn vgn vinn vss iswmod`；
    其余网表与 gold 完全一致（diff 仅 70/71 两行 + 新增 1 行 .model）
- 运行：tt 点 tb_fft tran 900n。steep=20：72.4 s / 31357 点 / failed steps 1772
  （gold 同机复跑 22.9 s / failed steps 1833——VA 版失败步数与 gold 同量级，无稳定性劣化）
- 向量名规范化：同 R2 补记（VSP→v(vsp)、VDD#BRANCH→i(vdd) 等），脚本内联于
  `_normalized_tt_va_xyce.raw` 生成过程；指标用 `analyze_raw.py` 提取
- tt 点对比（四组；ngspice-VA 为 N/A：ngspice 走 OpenVAF/OSDI 路线，试点镜像无该工具链，
  留待单独容器）：
  | 量 | ngspice-gold | Xyce-gold | Xyce-VA steep=20 | Xyce-VA steep=100 |
  |---|---|---|---|---|
  | SFDR (dB) | 99.004 | 97.119 | 108.646 | 108.732 |
  | 差分增益误差 | 0.3817% | 0.3987% | 0.0135% | 0.0136% |
  | 存储共模误差 (mV) | 17.976 | 17.972 | 20.509 | 20.510 |
  | 总源功率 (mW) | 0.4005 | 0.4044 | 0.3845 | 0.3844 |
- 与 VA 草稿预期方向核对：
  - 采样精度改善：符合。增益误差 0.40%→0.014%（约 29×），Ron 常数化消除了信号依赖衰减
  - SFDR：符合"可能变化"且大幅变好 97.1→108.6 dB（谐波源头的开关 Ron 非线性消失）
  - 存储共模偏移下降：**不符合**。17.97→20.51 mV（+2.5 mV）。核查：两组的共模偏移
    在 80 个 held-sample 上都是平坦常量（gold 17.90–17.96，VA 20.46–20.50 mV），说明
    偏移主体来自未替换的 CM 支路（XM_CM_P/N、XM_TS、boot_drv），输入管替换后残余 +2.5 mV
    的合理解释是 gold 中 MOS 关断沟道电荷注入/时钟馈通对 vsp 的上踢与 CM 支路偏移部分
    互相抵消，理想开关去掉该注入后净偏移反而略增。仍远低于 25 mV 判据
  - 源功率下降 0.404→0.384 mW：去掉 MOS 开关损耗，方向合理
- steep 扫描（20 vs 100）：SFDR/增益/共模/功率四项指标基本不变（SFDR +0.09 dB），
  求解开销上升（72.4 s→101.8 s，failed steps 1772→1800，更陡 tanh 沿使牛顿迭代更费）。
  结论：steep=20 已足够"理想"，加陡无精度收益只损速度；若做后续 PVT 全矩阵用 steep=20
- 产物清单（run/）：circuit_va_tt_xyce.spi、tb_fft_tt_va_xyce.spi、tb_fft_tt_va_xyce.raw/.log、
  _normalized_tt_va_xyce.raw、metrics_tt_va_xyce.json；steep100 同名 *_steep100_*；
  compare_tt_va_sw.json（四组汇总）。va/build/ 插件 .so、va/test/ysw_test.spi（最小验证网表）
- 2×2 矩阵状态：tt 列（Xyce-gold / Xyce-VA）完成；ngspice 列 gold 有、VA 缺（N/A 见上）

## R4 OpenVAF + ngspice OSDI——ngspice-VA 象限补全（步骤 3 收尾）

- 工具身份与获取：
  - OpenVAF：**OpenVAF-Reloaded** fork（github.com/OpenVAF-Reloaded/OpenVAF），
    commit `5063fdadc254842cdf16112241d6df81fde48d43`（2026-10-14）。官方（pascalkuthe
    及 Reloaded 的 fides.fe.uni-lj.si）**均无 aarch64 预编译版**（仅 linux/win x64），
    故在 arm64 Ubuntu 24.04 容器内从源码构建（rust stable + llvm-18/clang-18 + libpolly-18，
    cargo vendor 后离线编译）。Dockerfile 见本目录 `Dockerfile.openvaf`，镜像 tag
    `openvaf-src:arm64`。`openvaf --version` 报 "OpenVAF-reloaded unknown"（shallow clone
    无 tag），以 commit hash 为准。选 LLVM-18 是因为 Ubuntu 24.04 arm64 的 llvm-18-dev
    自带 Polly（LLVM-15 无 polly 包，jammy arm64 连 libpolly-15-dev 都没有）
  - ngspice：**ngspice-46**（bench 镜像，同 R1/R2，linux/arm64，binary 内置 OSDI 运行时）
- OpenVAF 编译：`openvaf ideal_sw.va`（容器内）——**一次通过，VA 零改写**。
  `from (0:inf)`、`tanh`、`include "disciplines.vams"`（OpenVAF 内置 vams 头）均直接支持。
  产物 `run/ideal_sw.osdi`（72 KB，OSDI v0.4，arm64）
- ngspice OSDI 实例化语法（与 Xyce 的 Y 前缀不同）：
  - 加载：**`.osdi` 不是可用的 dot 卡**（报 "unimplemented dot command '.osdi'"），须在
    `.control` / `.endc` 块内用 `pre_osdi /run/ideal_sw.osdi`（"pre_" = 电路解析前加载；
    注意结束符是 `.endc` 不是 `endc`，写错会连锁炸 sky130 库的 .param 解析）
  - 实例：`N` 前缀，`NSW_P vsp vgp vinp vss iswmod`（Xyce 版的 `Yideal_sw SW_P ...`
    改名），模型卡 `.model iswmod ideal_sw ron=500 roff=1e9 vth=0.9 steep=20`
    （不需要 Xyce 的 `level=1`）
  - 运行：`ngspice -b -r <out.raw> -o <log> deck.spi`（`-r` 必须有，否则 batch 模式报
    "no .plot/.print/.fourier lines" 拒跑——R1 的 verify.py 内部即带 -r 语义）
  - 网表：`run/circuit_va_tt_ngspice.spi`（对 gold circuit.spi 的 diff 仅 70/71 两行
    替换 + 1 行 .model，与 Xyce 版等价）、`run/tb_fft_tt_va_ngspice.spi`
  - 命令：容器内 `ngspice -b -r /run/tb_fft_tt_va_ngspice.raw -o tb_fft_tt_va_ngspice tb_fft_tt_va_ngspice.spi`，
    tran 900n，20.9 s（同机 gold 复跑 12.0 s）
- tt 点结果（analyze_raw.py，变量名天然匹配无需规范化）：见下表 ngspice-VA 列。
  - 注意：ngspice-VA 的 SFDR 73.56 dB 受 3 次谐波（FFT bin k=12，-73.6 dBc）限制。
    诊断：把 .options 收紧到 reltol=1e-6 abstol=1e-14 vntol=1e-9 复跑
    （`run/tb_fft_tt_va_ngspice_tight.*`，185 s），SFDR → 106.75 dB、增益误差 → 0.0136%，
    与 Xyce-VA（108.65 / 0.0135%）对齐；held samples 两器差 <0.8 mV（rms 0.47 mV）。
    结论：73.56 dB 是 gear+reltol=5e-4 宽容差下 OSDI 平滑开关处的截断误差伪影，
    非模型本身差异；为与其它三格同条件（同 .options），矩阵主值仍用宽容差结果并附注
- 2×2 矩阵补全（tt 点，四项指标）：
  | 量 | ngspice-gold | ngspice-VA | Xyce-gold | Xyce-VA |
  |---|---|---|---|---|
  | SFDR (dB) | 99.004 | 73.564（收紧容差 106.745） | 97.119 | 108.646 |
  | 差分增益误差 | 0.3817% | 0.00217%（收紧 0.0136%） | 0.3987% | 0.0135% |
  | 存储共模误差 (mV) | 17.976 | 20.525 | 17.972 | 20.509 |
  | 总源功率 (mW) | 0.4005 | 0.3819 | 0.4044 | 0.3845 |
  - 象限间方向一致性核对：VA 替换在两器上方向完全一致——共模误差 +2.5 mV、源功率
    下降、增益误差大幅改善；唯 SFDR 一格受 ngspice 宽容差伪影拖低（见上注）
- 产物（run/）：ideal_sw.osdi、circuit_va_tt_ngspice.spi、tb_fft_tt_va_ngspice.spi/.raw/.log、
  metrics_tt_va_ngspice.json、tb_fft_tt_va_ngspice_tight.spi/.raw、
  metrics_tt_va_ngspice_tight.json

## R7 Xyce 波形输出收窄配方（`-r` 全量转储的替代）— 2026-10-17 下午补
- 动机：R2 的 `-r` 全量转储 483 变量 / 239 MB（ASCII，`-a`），PVT 扫描的计时会被写盘淹没
- 源码依据（Xyce 7.10）：`-r` 走 OverrideRaw 输出器，无条件转储 `getSolutionNodeMap()` 全部节点，
  `.print` 不参与过滤、无 `.save` 卡；`.print ... format=raw` 走 TimeRaw 输出器，只写 `.print`
  列出的变量（`N_IO_OutputMgr.C` `parsePRINTBlock` 支持 RAW/CSV/TECPLOT/PROBE/STD 等 token，
  ASCII/二进制由命令行 `-a` 控制）
- 实测（tt 点同网表，仅改 `.print` 行加 `format=raw`、去掉 `-r`）：
  `run/tb_fft_tt_xyce_rawfmt.spi` → `tb_fft_tt_xyce_rawfmt.spi.raw`（注意输出名是网表全名再接 .raw，
  且写到 Xyce 进程 CWD 而非网表目录，容器内需显式 cd）
  - 14 变量（TIME + 13 个 .print 量）/ 30448 点（与全量版点数一致，求解行为未变）/ 7.09 MB ASCII
  - analyze_raw.py 复核：SFDR 97.119 dB、增益 0.3987%、共模 17.972 mV——与全量版逐位一致
  - 文件体积 34× 缩减；计时未在受控条件下重测（本次 41–50 s 属冷页缓存，不与 R2 的 22.7 s 比）
- 结论：后续 PVT/批量实验统一用 `.print format=raw`（ASCII 需配 `-a`）或 std/CSV 格式，`-r` 仅在
  需要全节点波形诊断时使用
