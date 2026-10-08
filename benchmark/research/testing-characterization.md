# 电路测试与表征材料调研

核查日期：2026-10-08。仓库基线 `b86845e1ef80498a8eed708a56bed993f7a7f17c`。本专题只收集、读取材料，未创建正式题或运行仿真。原件、源码、版本摘要及 PDF 身份清单位于本机 `runs/benchmark-material-survey-20261008/testing-raw/`，不随笔记发布。下文任务与 checker 建议均未实施或校准。

范围是代理交付 Verilog-A 核心文件，使用电压端口与事件，最终由实际 Spectre 检查。三个子类型可共用同一电路：生成激励；完成测量；运行时约束检查。多条件表征是覆盖维度，不与这些子类型互斥。已有 CSV/波形提取指标只覆盖部分流程；本类要求 VA 激励或 VA 测量/监控模块成为核心交付物，Python 可作独立评分器。未纳入电路优化、仿真收敛或问答任务。

## 1. ADCToolbox，Zhishuai Zhang / Lu Jie，2025–2026

**主源与实读。** [仓库](https://github.com/Arcadia-1/ADCToolbox)，固定 `8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9`。读 `python/src/adctoolbox/spectrum/compute_spectrum.py` L126–175、`aout/compute_inl_from_ramp.py` 的定义/前提，以及 `python/tests/unit/spectrum/test_compute_spectrum_sndr.py` 和 `unit/aout/test_inl_from_ramp.py`。[FFT 实现](https://github.com/Arcadia-1/ADCToolbox/blob/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9/python/src/adctoolbox/spectrum/compute_spectrum.py)、[ramp 测试](https://github.com/Arcadia-1/ADCToolbox/blob/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9/python/tests/unit/aout/test_inl_from_ramp.py)。

**已有证据。** 有 Python/MATLAB 算法、合成信号例子、`reference_dataset/sinewave_noise_200uV.csv` 和 `dout_SAR_12b_weight_2.csv`。MIT；保留原版权。SNDR 使用信号功率/其余带内功率；ENOB=(SNDR−1.76)/6.02。Ramp DNL=count/mean(count)−1，原始 transition INL 为累积 DNL。代码明说它不验证输入是否来自线性匀速 ramp。

**改题建议。** 输入 ADC 电压域 DUT、采样时钟、量程与窗口合同；交付 VA sine/ramp 激励与采样导出模块，必要时 VA 单频测量模块。独立 checker 从固定时间采样读取 Spectre 数据，不直接调用候选自身统计。正例为 coherent 正弦及均匀 ramp；负例为缺码、非匀速 ramp、漏采/重复采样、谐波混入 fundamental。已有 ramp 单测有 count=30/10 对应 DNL=+0.5/−0.5、缺码 DNL=−1 的精确真值。合成 noise 的理论 SNR 是统计目标，需要固定 seed、record length 与容差。缺口是现成材料为 Python/MATLAB，没有可直接提交的 VA testbench，ADC code 数据也需定义电压端口编码。

## 2. Analog Design Bench，Arcadia / contributors，2026

**主源与实读。** [固定 README](https://huggingface.co/datasets/Arcadia-2026/analog-design-bench/blob/fde04406e104064eb66c31c689d6312d4b670dc3/README.md)，revision `fde04406e104064eb66c31c689d6312d4b670dc3`。读 `data/tasks.jsonl` 中运放/ring amp/oscillator/biquad instruction；实际读运放 `tests/benches/tb_op_ac.spi`、oscillator/biquad `tests/verify.py`、LDO instruction/reference。原题是提交晶体管级 `circuit.spi` 的设计任务，不是 VA 测量题。

**已有证据。** 公开 instruction、参考电路、bench、checker 和 reference scalars；没有预录制 raw waveform 数据集。软件 Apache-2.0，instruction/SPICE/参考数据等内容 CC BY-NC 4.0；商用内容许可另议，不能把软件许可套到题面与网表。[LICENSE](https://huggingface.co/datasets/Arcadia-2026/analog-design-bench/blob/fde04406e104064eb66c31c689d6312d4b670dc3/LICENSE)。

- 运放 bench 断环 AC，`loop_gain=-vout/vinn`，测首次下降 0 dB crossing 并检查回穿。27 点 PVT，与三点双向 step 分开声明。[bench](https://huggingface.co/datasets/Arcadia-2026/analog-design-bench/blob/fde04406e104064eb66c31c689d6312d4b670dc3/tasks/sky130-two-stage-miller-opamp-gain60-ugb200-pm60-noise50uv-pvt/tests/benches/tb_op_ac.spi)
- Ring amp 四种输入记录检验两种 transfer slope；双向 settling 相对于命令目标的最后入带。Oscillator 五个代表 PVT 点以十周期测频率，checker 验证完整点集合。[oscillator checker](https://huggingface.co/datasets/Arcadia-2026/analog-design-bench/blob/fde04406e104064eb66c31c689d6312d4b670dc3/tasks/sky130-low-power-oscillator-2mhz-pvt/tests/verify.py)
- Biquad 25 点 OP+AC/noise，加三点幅度/频率 stress，checker 拟合 f0/Q，并解析运行生成 raw。LDO 是启动/line-step/load-step/输出网络交叉表征的来源：输出要达到目标后保持，不能只在一点 crossing。[LDO instruction](https://huggingface.co/datasets/Arcadia-2026/analog-design-bench/blob/fde04406e104064eb66c31c689d6312d4b670dc3/tasks/sky130-ldo-ota5-robust-pvt-mc/instruction.md)

**改题建议。** 给固定 VA 放大器/滤波器/调压器 DUT，交付 VA step/sine/ramp 或在线 settling/振幅/周期测量模块。保留命令目标、双极性、多输入幅度和逐条件表，不照搬 ngspice 与晶体管 PVT。独立 checker 用解析传递函数、命令目标和 Spectre 保存数据；正例为已知一阶/二阶响应，负例为恒定输出、单向 gain、先入带后振铃、漏跑条件。LDO 只取输出电压性质，负载与电流网络由固定环境承担。缺口是 ngspice reference 不能作为 Spectre 对齐证据；biquad 展平 reference_metrics 的部分 THD 阈值与 instruction/checker 不同，应读合同/源码。未借用其发布结果声称本次通过。

## 3. Assertion Based Self-checking…，TI，DVCon 2011

**主源与实读。** Balasubramanian、Sundar、Fischer。[官方归档](https://dvcon-proceedings.org/document/assertion-based-self-checking-of-analog-circuits-for-circuit-verification-and-model-validation-in-spice-and-co-simulation-environments/)标记 United States、2011。[原论文](https://dvcon-proceedings.org/wp-content/uploads/assertion-based-self-checking-of-analog-circuits-for-circuit-verification-and-model-validation-in-spice-and-co-simulation-environments.pdf)，7 页。重点读 §3.1、§4.1.1 的四段 VA 源码、§4.1.2 与 §5。原件与 SHA-256 保存在上述本机目录。

**已有证据。** 提供 `digitizer`、`min_time_diff`、`within_limits`、`time_delay` 代码片段和 power-up/sleep 场景图。阈值 crossing 与 `$realtime` 测事件间隔；`within_limits` 实际只在 enable 上升 crossing 检查 x；DVR 概念检查节点过压。全文没有完整 assertion 库或 runnable release，且首页声明相关专利，未见开放代码许可。片段有 `mg/msg` 等疑似排版/代码错误，不能直接当可运行参考。

**改题建议。** 给电源启动/休眠电压输入、阈值、检查窗口与最小事件间隔，交付 VA 监控器及机器可读错误结果。真值由分段线性 PWL 的事件时间与闭区间规则计算；正例按时启动且采样在界内，负例包括缺事件、初始已高、反序事件、恰好阈值、enable 后越界。需明确“采样点检查”还是“整个开启区间检查”，后者必须补越界 crossing/持续时间检测。Spectre 终验需正负例实际触发，不能只看源码或一条正常曲线。许可缺口使它适合作为学习方法与自行设计合同的材料。

## 4. Assertion-based Verification for Analog and Mixed Signal Designs，Srinivas Aluri / TI，2017 archive

**主源与实读。** [归档页](https://dvcon-proceedings.org/document/assertion-based-verification-for-analog-andmixed-signal-designs/)、[PDF](https://dvcon-proceedings.org/wp-content/uploads/assertion-based-verification-for-analog-andmixed-signal-designs.pdf)。归档标 2017 poster，PDF 有 2017 logo、2022 页脚，保留这种元数据歧义。实际读 pp.4–8，渲染并看 p.5–6 源码截图 `ti-abv-05.png`/`06.png`。

**已有证据。** 电压 range macro 经 `absdelta` 将模拟变化转换为事件；随后 PSL/SVA 组合供电/参考电压条件检查。示例含参考电压和 testmux 场景。资产是截图与集成说明，不含独立源码包、波形数据或开放许可。依赖 AMS 的 `vunit`/PSL/SVA；这不是纯 VA 现成参考。

**改题建议。** 保留电压端口，将事件触发与 enable 条件写成 VA monitor 核心文件，由固定 Spectre environment 驱动供电与参考。独立真值用 PWL 控制条件及界值；正例参考有效且 monitor 电压合规，负例为条件刚成立时越界、短脉冲越界、禁用期间越界、条件真值从未成立。检查 coverage 以防 vacuous pass。`absdelta` 有变化/时间容差，实际触发样本不证明所有连续时刻合规；纯 Spectre 不得默认支持原 PSL/SVA glue。它更适合补充 TI2011 的事件语义，不单独优先落题。

## 5. Verification of Complex Analog Integrated Circuits，Ken Kundert / Henry Chang，CICC 2006

**主源与实读。** [作者站 PDF](https://kenkundert.com/docs/cicc06.pdf)，20 页，正文说明 2006-09-26 更新，封面另有旧 version 标记。重点读 §3.3、§3.4、§4.2 与 Listings 1–4，尤其 pp.16–18。原件 `kundert2006.pdf`。

**已有证据。** stimulus/monitor/assertion 与 DUT wrapper 分工；Listing 4 扫 bias 设置和 DAC codes，比较输出电压与 `code*full_scale/1024`，接外部 RC load。只给解释性片段，含省略号与伪码，不是完整 executable suite。许可允许个人/课堂完整不修改副本，其他公开分发需许可；无代码开源授权。

**改题建议。** 给固定电压域 DAC/可编程放大器和接口，交付 VA code-voltage 激励以及测量 monitor；wrapper 保持端口稳定。真值独立由映射表/增益合同和固定负载响应产生。正例遍历全部 code/mode，负例漏 code、bit order 错、stuck output、disabled 状态不合法、采样过早。若选参考发生器，则检查供电/使能条件与输出电压，不扩展电流域。原文的 HDL 控制/AMS 片段应重写为 VA 可运行核心，Spectre 保持终验；它的主要价值是测试完整性与接口组织，不是可直接复制的资产。

## 6. Study on Behavior-Level Modeling and Top-Down Approach Design of ADPLL，Sai Chandra Teja Radhapuram / Osaka University，2020 repository

**主源与实读。** [学校 VoR PDF](https://ir.library.osaka-u.ac.jp/repo/ouka/all/76226/30869_Dissertation.pdf)、[DOI](https://doi.org/10.18910/76226)。仓储 citation 为 2020，正文封面 December 2018。实读 §2.5 pp.41–46、Figs.2.19–2.21、Appendix A pp.97–98 和 Appendix B DCO/controller code。原件 `adpll-thesis.pdf`。

**已有证据。** ADPLL reference-frequency step 的行为响应与 z/s-domain step model 相互比较；文中约 20 µs 是特定实现下响应，不是可通用的 lock limit。Appendix A 仅给限幅负 gm 与 thermal-noise VA 小模块，完整 ADPLL 并非一份纯 VA；Appendix B 有 FPGA HDL。没有 raw transient 数据/完整 Spectre deck或开放许可证。

**改题建议。** 学习“启动、频率阶跃、重锁”激励组织，给独立固定电压域 PLL reference，交付 VA clock stimulus 与 edge-time/phase-error monitor。独立 checker 依据命令频比、持续 K 周期频差/相位差阈值判 lock；正例稳态持续满足，负例短暂过阈、漏边、cycle slip、阶跃后沿用旧窗口。锁定容差/持续窗口必须新定，不能把论文 settling 近似式直接当非线性真值。其电流 noise/gm 不符合当前电压域核心，适合作为方法参考，不直接移植；尚缺可复现 voltage-domain DUT 和 Spectre 数值基线。

## 7. Low-pass filter model，Aleksandr Sidun / AnalogHub，2026 页面更新

**主源与实读。** [文章](https://analoghub.ie/category/verilogModels/article/LPF)、[固定 VA 源码](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/LPF.va)，repo `33a495131027283f22c51ca423f1aed0aa1ae98e`。全读 26 行 LPF.va；页面 2026-03-31 更新，源码年份未单列。

**已有证据。** 有 VA 源码、AC 示例截图，无数值 waveform/checker。第一阶重复 `V(out)<+laplace_nd(...)` 两次；按贡献相加语义，应为 2H，而非单位 passband。二阶分母是 `(s+ωc)^2`，在声明 fc 处相对 DC 是 −6.02 dB，不是 −3 dB。两点是源码数学推断，本轮未运行。repo 未见 LICENSE，文章标 all rights reserved，不能默认可复用代码。

**改题建议。** 自建有明确传递函数的固定 DUT，输入 fc/order/amplitude，交付 VA 扫频正弦激励与 steady-state 振幅/相位测量模块。独立真值是一阶 `1/(1+s/ωc)` 或二阶合同，正例正确单位增益，负例重复 contribution、二阶 fc 定义错误、未等稳态、把输入振幅当峰峰值。用 AC 与 transient 两条独立提取路径核对，实际 Spectre 校准；源代码适合学习/负例动机，缺许可与可运行测量 bench，不能直接当正确解。

## 8. Voltage-controlled oscillator model，Aleksandr Sidun / AnalogHub，2026 页面更新

**主源与实读。** [文章](https://analoghub.ie/category/verilogModels/article/vcoModel)、[vco1.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/vco1.va)、[vco2.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/vco2.va)。固定 repo 同上。全读两个模型。

**已有证据。** model1 用 `freq=Start_freq+Gain_Hz_per_V*V(in)`，`idtmod` 累积相位后输出 cosine，`$bound_step` 限步长。model2 却用 `Stop_frequency/Start_frequency` 作为 gain，缺少电压范围定义，与页面起止频率文字目标不符。无 noise/jitter 源，不能用这两份理想模型声称完成 phase-noise 表征。许可同 LPF，未见 open-source LICENSE。

**改题建议。** 给固定合法控制电压范围的 VCO DUT，交付 VA control sweep/step 和周期、幅度测量模块。独立真值为各恒定控制点 `f=f0+Kv*v`，正例五个控制点并跨十周期提取；负例把 Hz/V 写成 V/Hz、frequency ratio 当 tuning span、phase wrap 误计 crossing、漏周期或启动窗口混入测量。动态条件可用积分频率得到相位，但必须定义测量 window 与阈值；自建受控电压域 fixture，经 Spectre 正负例校准，不能照抄 model2 当真值。

## 三项优先学习源

1. TI2011。与 VA 核心交付物最贴近，原文代码短，可学习阈值事件、事件间隔、使能采样和错误报告；重点是补明确的时间合同与缺事件处理。
2. Analog Design Bench。具体 外部端口测量合同、双向与多点检查、完整条件集合与公开 checker 最有用；选择电压性质并重新建立 Spectre 证据。
3. ADCToolbox。数学指标定义、已知合成正负例与真实数据接口较齐全，MIT 降低软件复用阻力；优先学测量有效性与独立算法校准，避免把算法正确误当激励正确。

## 三个候选方向，尚不是正式题

| 方向与子类型 | VA 核心交付物 | 独立真值与负例 | 入题前缺口 |
| --- | --- | --- | --- |
| 电源启动/休眠电压时间合同，运行时约束检查 | 事件间隔、窗口电压、缺事件报告 monitor | PWL 精确事件时间；提前enable、漏ready、迟启动、enable后尖峰 | 明确闭区间/连续监控或采样语义；Spectre正负例、阈值与报告接口 |
| 放大器/滤波器阶跃与多幅度表征，激励+测量 | VA 双向step/多频sine及gain/settling monitor | 已知一阶/二阶电压传递函数，独立波形checker；stuck、单向gain、振铃回出band | 固定DUT和条件集；测量窗口/终止规则；Spectre双路径校准 |
| VCO 调谐与 PLL 重锁的时序测量，激励+测量 | VA控制序列、周期/频比/相位监控 | VCO解析频率，PLL固定reference边沿序列；漏边、错频比、短暂lock | 先从VCO做起；PLL纯电压域reference、持续lock定义与数值基线尚缺 |

这些候选均要求提交可运行 `.va`，实际 Spectre 执行并用独立 checker 验证。运行时被采样/事件触发检查到的性质，只能支持所声明的时间、容差与条件覆盖；不能宣称连续时间形式证明。所有材料的已有发布结果与上述改题建议分开，尚未构造、执行或评分任何候选题。
