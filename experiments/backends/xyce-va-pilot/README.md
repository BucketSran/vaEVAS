# sky130 VA 开关联合仿真试点（Xyce 7.10 / ngspice 46）

回答 [issue #200](https://github.com/BucketSran/vaEVAS/issues/200) 的问题：真实晶体管 SPICE 网表 +
Verilog-A 器件在开源仿真器下的联合仿真链路能否打通，各差异来源各占多少。载体为
Arcadia-1/analog-design-bench 的 `sky130-bottom-plate-sampler-pvt`（gold 解 = 真实 MOS 开关），
把两只输入采样管替换为 39 行的连续理想开关 VA（`va/ideal_sw.va`，tanh 压控电导，无事件语义，
刻意留在 ADMS/OpenVAF 支持范围内），其余网表不动。

## 结论

- 链路打通：同一份 VA 在 Xyce 7.10（ADMS 插件，`Y` 前缀实例 + `.model ... level=1`）与
  ngspice 46（OpenVAF→OSDI，`N` 前缀实例 + `.control pre_osdi` 加载）下均**零改写**编译并联合求解成功。
- 工具差（gold 解，tt 点，同容差 `method=gear reltol=5e-4`）：SFDR −1.9 dB（谱底差异，非谐波
  偏移）、held sample 最大差 0.705 mV，均为判据余量的一小部分；唯一有直接证据的来源是
  sky130 模型卡声明 BSIM4.5 而 Xyce 只按 4.6.1 方程求值（逐器件运行时告警）。
- VA 替换差：增益误差 0.40%→0.014%（约 29×，常数 Ron 消除信号依赖衰减）、SFDR 97.1→108.6 dB
  （开关 Ron 非线性这一谐波源头消失）；存储共模偏移**反向** +2.5 mV（推断：gold 中 MOS 关断
  电荷注入与 CM 支路偏移部分抵消，理想化后净偏移显现），仍远低于 25 mV 判据。
- 容差陷阱：ngspice+OSDI 在宽容差下 SFDR 掉到 73.56 dB（3 次谐波伪影），收紧到
  reltol=1e-6 后回到 106.75 dB——开关电容类 bench 的 SFDR 对容差极其敏感，跨工具比较必须锁死容差。

## 四象限结果（tt 点：1.80 V / 27 °C）

| 量 | ngspice-gold | ngspice-VA | Xyce-gold | Xyce-VA (steep=20) |
| --- | ---: | ---: | ---: | ---: |
| SFDR (dB) | 99.004 | 73.564（紧容差 106.745） | 97.119 | 108.646 |
| 差分增益误差 | 0.3817% | 0.00217%（紧容差 0.0136%） | 0.3987% | 0.0135% |
| 存储共模误差 (mV) | 17.976 | 20.525 | 17.972 | 20.509 |
| 总源功率 (mW) | 0.4005 | 0.3819 | 0.4044 | 0.3845 |

ngspice 与 Xyce 的 gold 基线均满足 bench 判据（ngspice 全 9 个 PVT 点 6/6 通过，
worst 值见 [RECEIPTS.md](RECEIPTS.md) R1）。steep=20→100 四项指标几乎不动（SFDR +0.09 dB）
但求解时间 72.4→101.8 s，故 steep=20 足够，后续 PVT 用 steep=20。

## 工具与计时身份

| 项 | ngspice 侧 | Xyce 侧 |
| --- | --- | --- |
| 仿真器 | ngspice-46（bench 官方镜像，OSDI 运行时内置） | Xyce Release 7.10-opensource（源码自建，见 build-summary.txt） |
| VA 编译 | OpenVAF-Reloaded @ `5063fda`（arm64 源码构建） | Qucs/ADMS release-2.3.7 @ `06e1a6c` |
| tt 点墙钟（含 docker 启动） | gold 13.9 s / VA 20.9 s | gold 22.7 s / VA 72.4 s |
| 输出时间点 | 16043（14 变量，`.save` 限定） | 30448（`-r` 全量 483 变量 / 239 MB） |

Xyce 慢的主因是 1.9 倍密的时间网格（每点成本反而略低），且其 `-r` 输出器无条件转储全部节点。
已实测收窄配方：`.print ... format=raw` 只写所列变量（239 MB→7.09 MB，34×），点数与指标
逐位不变（RECEIPTS.md R7），后续批量实验应采用。

## 目录内容

- [RECEIPTS.md](RECEIPTS.md) — R1–R7 完整收据（环境身份、命令、逐项核对）
- [va/ideal_sw.va](va/ideal_sw.va) — 理想开关 VA 源码；[va/test/ysw_test.spi](va/test/ysw_test.spi) 最小验证网表
- [netlists/](netlists/) — gold 工具版与 VA 替换版网表（容器内绝对路径 `/opt/sky130`、
  `/run`、`/work` 按收据原样保留）
- [results/](results/) — 逐格指标 JSON 与两份对比汇总（`compare_tt_*.json`）
- [analyze_raw.py](analyze_raw.py) — 复刻 bench verify.py 算法的观测量提取脚本
- [Dockerfile](Dockerfile) / [Dockerfile.openvaf](Dockerfile.openvaf) / [build-summary.txt](build-summary.txt) — 构建身份
- [2026-10-17-open-source-va-scs-joint-survey.md](2026-10-17-open-source-va-scs-joint-survey.md) — 立项调研（开源生态无单点联合方案）

大波形（.raw，5–244 MB/份）与构建日志按仓库惯例留在 ignored `runs/xyce-va-pilot-20261017/`，
指标 JSON 已足够复算全部结论。

## 范围与下一步

本试点为 tt 单点，未做 9 点 PVT 全矩阵的 VA 列；未审计 BSIM4.5 与 4.6.1 的方程级差异；
Xyce 收紧容差对照（reltol=1e-6）未跑。VA 开关为纯连续写法，事件语义（cross/transition）
接入见 [issue #181](https://github.com/BucketSran/vaEVAS/issues/181) 的协议实验，二期再会合。
