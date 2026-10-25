# 历史候选逐项清单

本表由 `register.json` 生成，包含108项主候选与另列的U30后备。105项原确认、3项终审建议的来源状态保持不变；本轮只重新安排建设。所有任务仍待建设和验收。

P0首批15项，P1第二批65项，P2后置28项，其中包含既定六项基础题。建设成本L/M/H分别为低/中/高，是作者工作量估计，与题目难度分开。HOLD不计入108。具体定义见[建设规则](README.md#建设顺序与进入正式集的条件)。

每项都还需独立参考、正常与违约对照、评分校准和最小starter审核。下面的“改造”列出各题特有工作，不表示共同工作已经完成。

Grok意见来自[Issue #159中的评论](https://github.com/BucketSran/vaEVAS/issues/159#issuecomment-6401348069)，针对历史来源代表。新S/R/T/I职责由本规划提出，评论没有直接验收它们。[逐条对应及补充原文](review-response.json)记录了意见来源、版本和参数/行为上下文。

| 候选 / 来源案例 | 任务内容 | 功能家族 | 动作 | 预估难度 | 优先级 / 建设成本 | 状态 | 原始题号和版本 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [C055-R1](#c055-r1) / C055 | Acquisition Limited Sample And Hold | 采样保持与多通道读出 | R | M | P0 / M | 已确认候选 | [v1:vbr1_l1_acquisition_limited_sample_and_hold:bugfix](../../../../../benchmark/material/historyref/v1/tasks/CT03_sampling_and_analog_memory/vbr1_l1_acquisition_limited_sample_and_hold/forms/bugfix/prompt.md) |
| [C055-S1](#c055-s1) / C055 | Acquisition Limited Sample And Hold | 采样保持与多通道读出 | S | M | P0 / M | 已确认候选 | [v4:071-acquisition-limited-sample-and-hold](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/071-acquisition-limited-sample-and-hold/public/instruction.md) |
| [C056-R1](#c056-r1) / C056 | Aperture Delay Track And Hold | 采样保持与多通道读出 | R | M | P0 / M | 已确认候选 | [v1:vbr1_l1_aperture_delay_track_and_hold:bugfix](../../../../../benchmark/material/historyref/v1/tasks/CT03_sampling_and_analog_memory/vbr1_l1_aperture_delay_track_and_hold/forms/bugfix/prompt.md) |
| [C056-S1](#c056-s1) / C056 | Aperture Delay Track And Hold | 采样保持与多通道读出 | S | M | P0 / L | 已确认候选 | [v4:072-aperture-delay-track-and-hold](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/072-aperture-delay-track-and-hold/public/instruction.md) |
| [C057-S1](#c057-s1) / C057 | Sample And Hold With Droop Leakage | 采样保持与多通道读出 | S | M | P1 / L | 已确认候选 | [v4:042-sample-and-hold-with-droop-leakage](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/042-sample-and-hold-with-droop-leakage/public/instruction.md) |
| [C060-S1](#c060-s1) / C060 | Correlated Double Sampler Offset-cancel Macro | 采样保持与多通道读出 | S | M | P0 / M | 已确认候选 | [v4:308-correlated-double-sampler-offset-cancel](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/308-correlated-double-sampler-offset-cancel/public/instruction.md) |
| [C061-S1](#c061-s1) / C061 | Dual Track Sample Hold | 采样保持与多通道读出 | S | M | P1 / M | 已确认候选 | [v4:236-dual-track-sample-hold](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold/public/instruction.md) |
| [C064-S1](#c064-s1) / C064 | Multi-channel Sample/Mux/Readout | 采样保持与多通道读出 | S | M | P1 / M | 已确认候选 | v4:349-multichannel-sample-readout（历史修订），原件local-only，行为摘录随清单保留 |
| [C066-S1](#c066-s1) / C066 | 上升沿模拟采样保持 | 采样保持与多通道读出 | S | B | P2 / L | 已确认候选 | [v4:024-clocked-sample-and-hold](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/024-clocked-sample-and-hold/public/instruction.md) |
| [C067-S1](#c067-s1) / C067 | Sample Hold Droop Front End | 采样保持与多通道读出 | S | M | P1 / M | 已确认候选 | v4:100-sample-hold-droop-front-end（历史修订），原件local-only，行为摘录随清单保留 |
| [C083-S1](#c083-s1) / C083 | 时钟采样均匀二进制ADC | ADC与转换控制 | S | B | P2 / L | 已确认候选 | [v4:023-clocked-adc-quantizer](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/023-clocked-adc-quantizer/public/instruction.md) |
| [C089-S1](#c089-s1) / C089 | Pipeline ADC Stage | ADC与转换控制 | S | M | P1 / L | 已确认候选 | v4:003-pipeline-adc-stage（历史修订），原件local-only，行为摘录随清单保留 |
| [C100-S1](#c100-s1) / C100 | 比较器双边沿握手SAR控制 | ADC与转换控制 | S | M | P1 / M | 已确认候选 | v3:243-l2-sar-logic-7b，原件local-only，行为摘录随清单保留 |
| [C103-S1](#c103-s1) / C103 | Pipe ADC Gain Control Loop | ADC与转换控制 | S | M | P1 / M | 已确认候选 | [v4:194-pipe-adc-gain-control-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/194-pipe-adc-gain-control-loop/public/instruction.md) |
| [C105-S1](#c105-s1) / C105 | Two-stage Pipeline ADC Mini Chain | ADC与转换控制 | S | H | P0 / M | 已确认候选 | v4:343-pipeline-adc-two-stage（历史修订），原件local-only，行为摘录随清单保留 |
| [C109-S1](#c109-s1) / C109 | 4-bit SAR ADC System | ADC与转换控制 | S | H | P0 / M | 已确认候选 | [v4:342-sar-adc-system-4b](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/public/instruction.md) |
| [C111-S1](#c111-s1) / C111 | SAR Front-End Logic 4b | ADC与转换控制 | S | M | P2 / M | 已确认候选 | [v4:186-sarfend-logic-4b](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/186-sarfend-logic-4b/public/instruction.md) |
| [C112-S1](#c112-s1) / C112 | 4-bit Self-Timed SAR Logic | ADC与转换控制 | S | H | P1 / M | 已确认候选 | [v4:192-sar-logic-4b-self-timed](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/192-sar-logic-4b-self-timed/public/instruction.md) |
| [C113-S1](#c113-s1) / C113 | Sigma-delta Modulator Mini Loop | ADC与转换控制 | S | M | P1 / M | 已确认候选 | [v4:350-sigma-delta-mini-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/350-sigma-delta-mini-loop/public/instruction.md) |
| [C114-S1](#c114-s1) / C114 | Synchronous 8-bit DFF Chain V2 | ADC与转换控制 | S | M | P2 / M | 已确认候选 | v4:177-sync-8b-dffs-v2（历史修订），原件local-only，行为摘录随清单保留 |
| [C118-S1](#c118-s1) / C118 | DWA DEM Encoder | DAC与重构 | S | M | P1 / M | 已确认候选 | v4:027-dwa-dem-encoder（历史修订），原件local-only，行为摘录随清单保留 |
| [C128-S1](#c128-s1) / C128 | 连续端点归一化二进制DAC | DAC与重构 | S | B | P2 / L | 已确认候选 | [v4:015-binary-weighted-voltage-dac](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/015-binary-weighted-voltage-dac/public/instruction.md) |
| [C155-S1](#c155-s1) / C155 | SAR CDAC Residue | DAC与重构 | S | M | P1 / M | 已确认候选 | [v4:119-sar-cdac-residue](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/119-sar-cdac-residue/public/instruction.md) |
| [C169-T1](#c169-t1) / C169 | Linearity RDAC Offset Sweep | DAC与重构 | T | H | P1 / H | 已确认候选 | [v4:190-linearity-rdac-offset-sweep](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/190-linearity-rdac-offset-sweep/public/instruction.md) |
| [C170-T1](#c170-t1) / C170 | Offset RDAC Search Flow | DAC与重构 | T | H | P1 / H | 已确认候选 | [v4:184-offset-rdac-search-flow](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/184-offset-rdac-search-flow/public/instruction.md) |
| [C176-S1](#c176-s1) / C176 | Debounce Latch | 比较器与门限 | S | M | P0 / L | 已确认候选 | [v4:005-debounce-latch](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/005-debounce-latch/public/instruction.md) |
| [C179-S1](#c179-s1) / C179 | Propagation Delay Comparator | 比较器与门限 | S | M | P1 / M | 已确认候选 | [v4:039-propagation-delay-comparator](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/039-propagation-delay-comparator/public/instruction.md) |
| [C193-S1](#c193-s1) / C193 | Offset-calibrated Comparator System | 比较器与门限 | S | M | P2 / H | 已确认候选 | [v4:345-offset-calibrated-comparator-system](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/345-offset-calibrated-comparator-system/public/instruction.md) |
| [C196-T1](#c196-t1) / C196 | Comparator Delay Overdrive Meter | 比较器与门限 | T | M | P1 / M | 已确认候选 | [v4:170-comparator-delay-overdrive-meter](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/170-comparator-delay-overdrive-meter/public/instruction.md) |
| [C202-T1](#c202-t1) / C202 | Start Gated Offset Search | 比较器与门限 | T | M | P1 / M | 已确认候选 | [v4:110-start-gated-offset-search](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/110-start-gated-offset-search/public/instruction.md) |
| [C203-S1](#c203-s1) / C203 | Sampled True-RMS-to-DC Converter | 放大与模拟信号处理 | S | M | P1 / L | 已确认候选 | [v4:074-sampled-true-rms-to-dc-converter](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/074-sampled-true-rms-to-dc-converter/public/instruction.md) |
| [C214-S1](#c214-s1) / C214 | Amplifier Filter Chain | 放大与模拟信号处理 | S | B-M | P2 / L | 已确认候选 | [v4:083-amplifier-filter-chain](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/083-amplifier-filter-chain/public/instruction.md) |
| [C219-S1](#c219-s1) / C219 | Chopper-Stabilized Differential Amplifier | 放大与模拟信号处理 | S | H | P1 / M | 已确认候选 | v4:091-chopper-stabilized-differential-amplifier（历史修订），原件local-only，行为摘录随清单保留 |
| [C221-S1](#c221-s1) / C221 | Common-mode Feedback Loop | 放大与模拟信号处理 | S | M | P1 / M | 已确认候选 | [v4:390-common-mode-feedback-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/390-common-mode-feedback-loop/public/instruction.md) |
| [C245-S1](#c245-s1) / C245 | Two-stage Op-amp Slew Macromodel | 放大与模拟信号处理 | S | M | P1 / M | 已确认候选 | v4:398-two-stage-opamp-slew-macromodel（历史修订），原件local-only，行为摘录随清单保留 |
| [C248-T1](#c248-t1) / C248 | Settling Window Detector | 放大与模拟信号处理 | T | M | P1 / M | 已确认候选 | [v4:063-settling-window-detector](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/063-settling-window-detector/public/instruction.md) |
| [C250-S1](#c250-s1) / C250 | First Order Lowpass | 滤波、积分与包络 | S | B | P2 / L | 已确认候选 | [v4:007-first-order-lowpass](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/007-first-order-lowpass/public/instruction.md) |
| [C260-S1](#c260-s1) / C260 | 连续一阶低通加输出采样 | 滤波、积分与包络 | S | M | P0 / M | 已确认候选 | v3:437-laplace-nd-lowpass-filter，原件local-only，行为摘录随清单保留 |
| [C263-S1](#c263-s1) / C263 | Switched-capacitor Integrator Phase Pair | 滤波、积分与包络 | S | M | P1 / M | 已确认候选 | v4:307-switched-capacitor-integrator-phase-pair（历史修订），原件local-only，行为摘录随清单保留 |
| [C264-S1](#c264-s1) / C264 | 离散一阶低通加输出采样 | 滤波、积分与包络 | S | M | P0 / M | 已确认候选 | v3:441-zi-nd-discrete-filter，原件local-only，行为摘录随清单保留 |
| [C266-S1](#c266-s1) / C266 | Slew Limited Envelope | 滤波、积分与包络 | S | M | P0 / M | 已确认候选 | v3:324-slew-limited-envelope，原件local-only，行为摘录随清单保留 |
| [C268-S1](#c268-s1) / C268 | Bang-Bang Phase Detector | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:001-bang-bang-phase-detector](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/001-bang-bang-phase-detector/public/instruction.md) |
| [C270-S1](#c270-s1) / C270 | PLL Feedback Clock Divider | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:012-clock-divider](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/012-clock-divider/public/instruction.md) |
| [C273-S1](#c273-s1) / C273 | Lock Detector | PLL、时钟与时间测量 | S | M | P2 / L | 已确认候选 | [v4:009-lock-detector](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/009-lock-detector/public/instruction.md) |
| [C275-S1](#c275-s1) / C275 | 即时互清三态PFD | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:011-pfd-up-dn-logic](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/011-pfd-up-dn-logic/public/instruction.md) |
| [C278-S1](#c278-s1) / C278 | ADPLL Ratio Hop Timer | PLL、时钟与时间测量 | S | H | P1 / H | 已确认候选 | [v4:081-adpll-ratio-hop-timer](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/081-adpll-ratio-hop-timer/public/instruction.md) |
| [C279-S1](#c279-s1) / C279 | BBPD Data Edge Alignment | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:084-bbpd-data-edge-alignment](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/084-bbpd-data-edge-alignment/public/instruction.md) |
| [C282-S1](#c282-s1) / C282 | Charge Pump PFD State Machine | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:301-charge-pump-pfd-state-machine](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/301-charge-pump-pfd-state-machine/public/instruction.md) |
| [C286-S1](#c286-s1) / C286 | Differential VCO With Clip And Idtmod | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | v4:300-differential-vco-clip-idtmod（历史修订），原件local-only，行为摘录随清单保留 |
| [C290-S1](#c290-s1) / C290 | DLL Delay-line Lock | PLL、时钟与时间测量 | S | H | P1 / H | 已确认候选 | [v4:361-dll-delay-line-lock](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/361-dll-delay-line-lock/public/instruction.md) |
| [C292-S1](#c292-s1) / C292 | Edge Delay Line with Deglitch Window | PLL、时钟与时间测量 | S | H | P1 / M | 已确认候选 | [v4:064-edge-delay-line-with-deglitch](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/064-edge-delay-line-with-deglitch/public/instruction.md) |
| [C299-S1](#c299-s1) / C299 | Fractional-N Divider Accumulator Flow | PLL、时钟与时间测量 | S | H | P1 / H | 已确认候选 | [v4:302-fractional-n-divider-accumulator-flow](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/302-fractional-n-divider-accumulator-flow/public/instruction.md) |
| [C300-S1](#c300-s1) / C300 | Fractional-N Synthesizer Mini Loop | PLL、时钟与时间测量 | S | M | P2 / M | 已确认候选 | v4:363-fractional-n-synthesizer-mini-loop（历史修订），原件local-only，行为摘录随清单保留 |
| [C301-S1](#c301-s1) / C301 | Frequency-word DCO with Divider Monitor | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | v4:362-frequency-word-dco-divider-monitor（历史修订），原件local-only，行为摘录随清单保留 |
| [C302-S1](#c302-s1) / C302 | Glitchless Clock Mux Selector | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | v4:322-glitchless-clock-mux-selector（历史修订），原件local-only，行为摘录随清单保留 |
| [C308-S1](#c308-s1) / C308 | Deterministic Jittered Clock Source | PLL、时钟与时间测量 | S | M | P1 / L | 已确认候选 | v4:070-jittered-clock-source-deterministic（历史修订），原件local-only，行为摘录随清单保留 |
| [C312-S1](#c312-s1) / C312 | Non-overlapping Clock Generator | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | v4:375-nonoverlap-clock-generator（历史修订），原件local-only，行为摘录随清单保留 |
| [C316-S1](#c316-s1) / C316 | 时钟先后序列累计监控系统 | PLL、时钟与时间测量 | S | H | P2 / M | 已确认候选 | v4:351-pll-timing-monitor-system（历史修订），原件local-only，行为摘录随清单保留 |
| [C328-S1](#c328-s1) / C328 | TDC Event Measurement System | PLL、时钟与时间测量 | S | M | P1 / M | 已确认候选 | [v4:346-tdc-measurement-system](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/346-tdc-measurement-system/public/instruction.md) |
| [C331-T1](#c331-t1) / C331 | Duty-cycle Window Monitor | PLL、时钟与时间测量 | T | M | P1 / M | 已确认候选 | [v4:324-duty-cycle-window-monitor](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/324-duty-cycle-window-monitor/public/instruction.md) |
| [C339-T1](#c339-t1) / C339 | Time Difference Detector | PLL、时钟与时间测量 | T | M | P1 / M | 已确认候选 | [v4:117-time-diff-detector](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/117-time-diff-detector/public/instruction.md) |
| [C343-S1](#c343-s1) / C343 | PFD With External Active Low Reset | PLL、时钟与时间测量 | S | M | P2 / M | 已确认候选 | [v4:249-pfd-active-low-reset](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/249-pfd-active-low-reset/public/instruction.md) |
| [C348-S1](#c348-s1) / C348 | AGC Receiver Leveling Loop | RF、均衡与调制信号源 | S | M | P1 / M | 已确认候选 | [v4:082-agc-receiver-leveling-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/082-agc-receiver-leveling-loop/public/instruction.md) |
| [C353-S1](#c353-s1) / C353 | Deserializer DEMUX Alignment Macro | RF、均衡与调制信号源 | S | M | P1 / M | 已确认候选 | v4:393-deserializer-demux-alignment-macro（历史修订），原件local-only，行为摘录随清单保留 |
| [C354-S1](#c354-s1) / C354 | DFE Error-proxy Loop | RF、均衡与调制信号源 | S | M | P2 / M | 已确认候选 | [v4:331-dfe-error-proxy-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/331-dfe-error-proxy-loop/public/instruction.md) |
| [C358-S1](#c358-s1) / C358 | 3-tap FFE Transmitter | RF、均衡与调制信号源 | S | B-M | P2 / L | 已确认候选 | v4:353-ffe-transmitter-3tap（历史修订），原件local-only，行为摘录随清单保留 |
| [C360-S1](#c360-s1) / C360 | IQ Downconversion Chain | RF、均衡与调制信号源 | S | M | P1 / M | 已确认候选 | [v4:094-iq-downconversion-chain](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/094-iq-downconversion-chain/public/instruction.md) |
| [C371-S1](#c371-s1) / C371 | Clocked Sine Source | RF、均衡与调制信号源 | S | B-M | P2 / M | 已确认候选 | [v4:102-clocked-sine-source](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/102-clocked-sine-source/public/instruction.md) |
| [C384-S1](#c384-s1) / C384 | Complete Calibration Loop | 校准与伺服 | S | M | P1 / M | 已确认候选 | [v4:086-complete-calibration-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/086-complete-calibration-loop/public/instruction.md) |
| [C385-S1](#c385-s1) / C385 | Instrumentation Amplifier Offset-trim System | 校准与伺服 | S | M | P1 / M | 已确认候选 | v4:306-instrumentation-amplifier-offset-trim（历史修订），原件local-only，行为摘录随清单保留 |
| [C396-S1](#c396-s1) / C396 | 异步断言、两拍释放的复位同步器 | 电源与复位 | S | B | P2 / L | 已确认候选 | v3:070-active-low-reset-synchronizer，原件local-only，行为摘录随清单保留 |
| [C399-S1](#c399-s1) / C399 | Charge-pump Voltage Multiplier Controller | 电源与复位 | S | M | P1 / M | 已确认候选 | v4:373-charge-pump-voltage-multiplier-controller（历史修订），原件local-only，行为摘录随清单保留 |
| [C400-S1](#c400-s1) / C400 | Clock-and-data Valid Qualifier | 电源与复位 | S | M | P1 / L | 已确认候选 | v4:395-clock-data-valid-qualifier（历史修订），原件local-only，行为摘录随清单保留 |
| [C402-S1](#c402-s1) / C402 | Dynamic Supply Level Driver | 电源与复位 | S | B | P2 / L | 已确认候选 | [v4:296-dynamic-supply-level-driver](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/296-dynamic-supply-level-driver/public/instruction.md) |
| [C403-S1](#c403-s1) / C403 | LDO Load-Step Recovery Flow | 电源与复位 | S | M | P1 / M | 已确认候选 | [v4:095-ldo-load-step-recovery](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/095-ldo-load-step-recovery/public/instruction.md) |
| [C408-S1](#c408-s1) / C408 | Power and Reset Sequencer | 电源与复位 | S | M | P1 / M | 已确认候选 | [v4:347-power-reset-sequencer-system](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/347-power-reset-sequencer-system/public/instruction.md) |
| [C411-S1](#c411-s1) / C411 | Rail Ramp Rate Startup Monitor | 电源与复位 | S | M | P1 / L | 已确认候选 | v4:297-rail-ramp-rate-startup-monitor（历史修订），原件local-only，行为摘录随清单保留 |
| [C417-S1](#c417-s1) / C417 | Supply Supervisor with Brownout POR | 电源与复位 | S | M | P1 / M | 已确认候选 | v4:399-supply-supervisor-brownout-por（历史修订），原件local-only，行为摘录随清单保留 |
| [C421-S1](#c421-s1) / C421 | Bandgap Startup and Trim System | 电源与复位 | S | M | P1 / M | 已确认候选 | v4:371-bandgap-startup-trim-system（历史修订），原件local-only，行为摘录随清单保留 |
| [U04-T1](#u04-t1) / C137 | 外部ADC静态线性度的独立表征 | ADC与转换控制 | T | H | P1 / H | 已确认候选 | [v4:087-converter-static-linearity-measurement](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/087-converter-static-linearity-measurement/public/instruction.md) |
| [U05-I1](#u05-i1) / C158 | DEM选元驱动失配分段DAC的集成 | DAC与重构 | I | M | P1 / H | 已确认候选 | [v4:344-segmented-dac-dem-system](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/344-segmented-dac-dem-system/public/instruction.md) |
| [U12-I1](#u12-i1) / C359 | 实际镜像观测驱动的I/Q校准集成 | 校准与伺服 | I | H | P2 / H | 已确认候选 | [v4:333-image-reject-mixer-calibration-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/333-image-reject-mixer-calibration-loop/public/instruction.md) |
| [U14-S1](#u14-s1) / C364 | 具有幅相非线性和有限记忆的PA包络模型 | RF、均衡与调制信号源 | S | M-H | P2 / H | 已确认候选 | v4:339-pa-ampm-memory-tap-macro（历史修订），原件local-only，行为摘录随清单保留 |
| [U01-I1](#u01-i1) / C020 | 模拟配置的原子提交与生效时刻 | 逻辑、编码与配置 | I | M | P1 / M | 已确认候选 | [v4:057-config-shift-register-64b](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/057-config-shift-register-64b/public/instruction.md) |
| [U02-I1](#u02-i1) / C065 | 共享采集通路的串扰与吞吐预算 | 采样保持与多通道读出 | I | H | P2 / H | 已确认候选 | [v4:311-muxed-track-hold-array-readout](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/311-muxed-track-hold-array-readout/public/instruction.md) |
| [U03-T1](#u03-t1) / C086 | 交织采样的增益、偏置和时间失配分离 | 采样保持与多通道读出 | T | H | P2 / H | 已确认候选 | v4:312-interleaved-adc-skew-monitor（历史修订），原件local-only，行为摘录随清单保留 |
| [U06-T1](#u06-t1) / C164 | DAC建立时间与毛刺冲量测量 | DAC与重构 | T | H | P2 / H | 已确认候选 | v4:319-unary-dac-glitch-energy-metric（历史修订），原件local-only，行为摘录随清单保留 |
| [U07-T1](#u07-t1) / C199 | 比较器本征迟滞与延迟影响的分离表征 | 比较器与门限 | T | H | P1 / H | 已确认候选 | [v4:111-hysteresis-trip-characterizer](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/public/instruction.md) |
| [U08-T1](#u08-t1) / C230 | 滤波与放大通路的幅相响应测量流程 | 滤波、积分与包络 | T | H | P1 / H | 已确认候选 | v3:287-gain-extraction-flow，原件local-only，行为摘录随清单保留 |
| [U09-I1](#u09-i1) / C351 | 由实际接收质量驱动的均衡闭环 | RF、均衡与调制信号源 | I | H | P2 / H | 已确认候选 | [v4:329-ctle-adaptation-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/329-ctle-adaptation-loop/public/instruction.md) |
| [U10-I1](#u10-i1) / C404 | 双电源域的信号隔离与安全恢复 | 电源与复位 | I | M | P1 / M | 已确认候选 | [v4:384-level-shifter-enable-rail-tracking](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/384-level-shifter-enable-rail-tracking/public/instruction.md) |
| [U11-T1](#u11-t1) / C192 | 有噪声比较器的失调与判决概率表征 | 比较器与门限 | T | H | P2 / H | 已确认候选 | [v4:112-latched-comparator-delay](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/112-latched-comparator-delay/public/instruction.md) |
| [U13-T1](#u13-t1) / C334 | 有时间预算和不确定度的频率测量 | PLL、时钟与时间测量 | T | M | P1 / M | 已确认候选 | [v4:061-event-counter-windowed-16b](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/061-event-counter-windowed-16b/public/instruction.md) |
| [U15-S1](#u15-s1) / C287 | 可编程延迟单元的脉冲保持与待发事件管理 | PLL、时钟与时间测量 | S | M-H | P0 / M | 已确认候选 | [v4:360-digitally-controlled-delay-cell](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/360-digitally-controlled-delay-cell/public/instruction.md) |
| [U16-S1](#u16-s1) / C295 | 含两端细时间的细粗TDC行为模型 | PLL、时钟与时间测量 | S | M-H | P0 / M | 已确认候选 | v4:325-fine-coarse-tdc-encoder（历史修订），原件local-only，行为摘录随清单保留 |
| [U17-S1](#u17-s1) / C355 | 使用历史判决反馈的两抽头DFE接收器 | RF、均衡与调制信号源 | S | M | P0 / M | 已确认候选 | [v4:354-dfe-receiver-2tap](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/public/instruction.md) |
| [U18-S1](#u18-s1) / C397 | 带软启动、载波和资格状态的Buck控制器 | 电源与复位 | S | M | P0 / M | 已确认候选 | [v4:372-buck-converter-controller-macro](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/372-buck-converter-controller-macro/public/instruction.md) |
| [U19-T1](#u19-t1) / C281 | 采样边沿前后时间裕量的因果观测 | PLL、时钟与时间测量 | T | M-H | P1 / H | 已确认候选 | [v4:327-cdr-eye-monitor](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/327-cdr-eye-monitor/public/instruction.md) |
| [U20-I1](#u20-i1) / C383 | 失配CDAC权重辨识与校正路径集成 | 校准与伺服 | I | H | P2 / H | 已确认候选 | [v4:317-capacitor-mismatch-calibration-engine](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/317-capacitor-mismatch-calibration-engine/public/instruction.md) |
| [U21-R1](#u21-r1) / cpplltrackingreacquiretimer | CPPLL反馈方向与重锁定故障诊断 | PLL、时钟与时间测量 | R | H | P2 / H | 已确认候选 | v4:088-cppll-tracking-reacquire-timer（历史修订），原件local-only，行为摘录随清单保留 |
| [U22-I1](#u22-i1) / dutycyclecorrector | 输出占空比驱动的校正闭环 | PLL、时钟与时间测量 | I | M-H | P1 / H | 已确认候选 | [v4:359-duty-cycle-corrector](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/359-duty-cycle-corrector/public/instruction.md) |
| [U23-S1](#u23-s1) / quadraturephaseinterpolator | 完整四象限的相位插值模型 | PLL、时钟与时间测量 | S | M-H | P2 / H | 已确认候选 | v4:358-quadrature-phase-interpolator（历史修订），原件local-only，行为摘录随清单保留 |
| [U24-I1](#u24-i1) / bangbangcdrloop | 稀疏数据边沿驱动的相位恢复闭环 | PLL、时钟与时间测量 | I | H | P2 / H | 已确认候选 | [v4:357-bangbang-cdr-loop](../../../../../benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/357-bangbang-cdr-loop/public/instruction.md) |
| [U25-T1](#u25-t1) / C403 | LDO负载阶跃与恢复的独立表征 | 电源与复位 | T | M-H | P1 / H | 已确认候选 | [v1:vbr1_l2_ldo_load_step_recovery_flow:tb](../../../../../benchmark/material/historyref/v1/tasks/CT07_bias_reference_power_management/vbr1_l2_ldo_load_step_recovery_flow/forms/tb/prompt.md) |
| [U26-T1](#u26-t1) / C278 | ADPLL变频比与伪锁定的独立验证 | PLL、时钟与时间测量 | T | H | P1 / H | 已确认候选 | [v1:vbr1_l2_adpll_lock_ratio_hop_timer_flow:tb](../../../../../benchmark/material/historyref/v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l2_adpll_lock_ratio_hop_timer_flow/forms/tb/prompt.md) |
| [U27-T1](#u27-t1) / C116 | SAR转换协议与内部观测一致性验证 | ADC与转换控制 | T | M-H | P1 / H | 终审建议候选 | [v1:vbr1_l2_weighted_sar_adc_dac_loop:tb](../../../../../benchmark/material/historyref/v1/tasks/CT01_data_converter_models/vbr1_l2_weighted_sar_adc_dac_loop/forms/tb/prompt.md) |
| [U28-T1](#u28-t1) / C348 | AGC捕获、过载与恢复的独立表征 | RF、均衡与调制信号源 | T | M-H | P1 / H | 终审建议候选 | [v1:vbr1_l2_agc_receiver_leveling_loop:tb](../../../../../benchmark/material/historyref/v1/tasks/CT08_rf_afe_behavioral_macromodels/vbr1_l2_agc_receiver_leveling_loop/forms/tb/prompt.md) |
| [U29-T1](#u29-t1) / C393 | 欠压复位断言与释放资格验证 | 电源与复位 | T | M-H | P1 / H | 终审建议候选 | [v1:vbr1_l1_power_on_reset_detector:tb](../../../../../benchmark/material/historyref/v1/tasks/CT07_bias_reference_power_management/vbr1_l1_power_on_reset_detector/forms/tb/prompt.md) |
| [U30-R1](#u30-r1) / C090 | SAR完成握手导致结果提前捕获的诊断修复 | ADC与转换控制 | R | M，待实测 | HOLD / H | 条件后备 | [v1:vbr1_l1_sar_logic:bugfix](../../../../../benchmark/material/historyref/v1/tasks/CT01_data_converter_models/vbr1_l1_sar_logic/forms/bugfix/prompt.md) |

## 逐项建设与意见处理

### C055-R1

Acquisition Limited Sample And Hold。P0，建设成本M，补行为边界。

- 可复用：v1有限采集故障起点、跟踪窗口接口和复位/保持场景。
- 需要改：把公开提示改为正常合同与故障症状；补alpha更新、timer起相及复位取消规则，独立确认故障对。
- 排序理由：有真实故障素材且修复职责明确；与C055-S1共建对象、同组划分。
- Grok意见处理：部分采纳。采纳有限采集代表；同源归并用于案例计数，R仍需诊断并修复，不能因与S同源直接删除。
- 对应历史条目：`acquisitionlimitedsampleandhold`。

### C055-S1

Acquisition Limited Sample And Hold。P0，建设成本M，补行为边界。

- 可复用：alpha=0.42、tick=1ns的有限采集机制，跟踪/保持接口。
- 需要改：公开每次获取更新式、首次tick和sample/rst/timer同刻规则；按跟踪窗长度校准误差，删除实现骨架。
- 排序理由：有限带宽与保持切换有独立考点，建设范围可控。
- Grok意见处理：部分采纳。采纳其有时序机制的判断；原文仍需明确定量获取式及事件边界，不能仅凭摘录完整判为成题。
- 对应历史条目：`acquisitionlimitedsampleandhold`。

### C056-R1

Aperture Delay Track And Hold。P0，建设成本M，补行为边界。

- 可复用：v1即时采样错误、正确孔径时刻要求及输入变化场景。
- 需要改：保留真实故障，移除根因直述；定义忙时再触发和读入时刻，用孔径内改变输入区分采样延后与输出延后。
- 排序理由：孔径故障可用独立波形区分，先核实诊断任务不退化为照提示改一行。
- Grok意见处理：部分采纳。与S归同一电路，但修复工程与从规格建模交付不同；不按旧bugfix标签自动计题。
- 对应历史条目：`aperturedelaytrackandhold`。

### C056-S1

Aperture Delay Track And Hold。P0，建设成本L，补行为边界。

- 可复用：延迟200ps后读取vin、越轨值保留和保持输出规则。
- 需要改：补taperture合法域、未完成采样的再触发策略和同刻读入约定；不把延迟前采样加输出延迟当等价解。
- 排序理由：单一因果问题清楚，可与R共享作者验证素材。
- Grok意见处理：部分采纳。采纳独立机制；完整题面仍需处理多个待发采样，位宽/摆幅变体不另计。
- 对应历史条目：`aperturedelaytrackandhold`。

### C057-S1

Sample And Hold With Droop Leakage。P1，建设成本L，补行为边界。

- 可复用：decay=0.985、1ns泄漏更新及捕获/复位行为。
- 需要改：明确泄漏相位、捕获与泄漏同刻顺序和复位释放；区分保持泄漏与C055获取动态。
- 排序理由：原动态可继承，排在有限采集与孔径代表之后。
- Grok意见处理：采纳方向。采纳时序代表，保留在保持期持续更新这一差异；不将近似采样版本全部单列。
- 对应历史条目：`sampleandholdwithdroopleakage`。

### C060-S1

Correlated Double Sampler Offset-cancel Macro。P0，建设成本M，补行为边界。

- 可复用：成对参考/信号采样、差分消偏、offset_dbg和valid接口。
- 需要改：规定两种采样请求同拍、重复参考、先信号后参考及完成后再使用规则；只保留必要模块边界。
- 排序理由：跨周期配对明确，能与普通采样题形成独立差异。
- Grok意见处理：部分采纳。采纳CDS工程价值；不把一次相减当全部职责，评分需检查样本配对和有效性。
- 对应历史条目：`correlateddoublesampleroffsetcancel`。

### C061-S1

Dual Track Sample Hold。P1，建设成本M，补行为边界。

- 可复用：低相输入级获取、高相输出级获取，两套alpha及轨间钳位。
- 需要改：规定timer与相位边沿的次序、初态和动态电源轨处理；分别检查两级保持，不能改成一次复制。
- 排序理由：已有数值参数，可在单级采集对象之后整理。
- Grok意见处理：采纳方向。采纳独立两级状态；与理想采样合并会丢掉相位传递机制。
- 对应历史条目：`dualtracksamplehold`。

### C064-S1

Multi-channel Sample/Mux/Readout。P1，建设成本M，补行为边界。

- 可复用：四通道同时捕获、循环读指针、暂停读出和通道号。
- 需要改：明确sample/read同拍读旧值还是新值、重复采集和复位中断；校验输出值与通道标签归属。
- 排序理由：状态配对有价值；无需先新增串扰模型即可形成独立S题。
- Grok意见处理：部分采纳。采纳多通道职责，但仅按摘录不能确定采读同拍语义；需补此合同。
- 对应历史条目：`multichannelsamplereadout`。

### C066-S1

上升沿模拟采样保持。P2，建设成本L，基础整理。

- 可复用：上升沿采样、沿间保持的最小电路和端口。
- 需要改：明确首次采样前输出与本地轨约定，保留少量边界校准；不添加人为多阶段流程。
- 排序理由：固定六项基础层之一，随主任务校准，避免扩张简单采样题。
- Grok意见处理：部分采纳。采纳作为基础代表及近似版本归并；不采纳由规格完整推导为主难度题。
- 对应历史条目：`clockedsampleandhold`。

### C067-S1

Sample Hold Droop Front End。P1，建设成本M，补行为边界。

- 可复用：孔径预约、valid脉冲、采样时轨间钳位及tau/dt参数。
- 需要改：明确低时钟期间的下垂更新式、目标电平与采样/下垂冲突；保留采样瞬间电源轨。
- 排序理由：复合采样前端有价值，先复用C056与C057的边界经验。
- Grok意见处理：采纳缺口。完整修订原题有tau=90ns和dt=0.5ns，但没有唯一的下垂更新关系，采纳此缺口。
- 对应历史条目：`sampleholddroopfrontend`。

### C083-S1

时钟采样均匀二进制ADC。P2，建设成本L，基础整理。

- 可复用：八个均匀量化区间、端点饱和与码保持。
- 需要改：明确区间等号、合法参考跨度和首次有效码；保持基础题规模。
- 排序理由：固定六项基础层之一，也是ADC验证任务的简单对照。
- Grok意见处理：部分采纳。采纳量化代表；有采样不意味着高工程难度，不按位宽增加新题。
- 对应历史条目：`clockedadc3bit`。

### C089-S1

Pipeline ADC Stage。P1，建设成本L，补行为边界。

- 可复用：PHI1采样、PHI2三域判决及增益二残差式。
- 需要改：明确阈值等号、两相重叠/缺失及复位前历史；检查码与残差来自同一样本。
- 排序理由：残差关系已有，能为C105提供较低建设成本的比较对象。
- Grok意见处理：部分采纳。采纳独立MDAC机制；实际规格需补相位边界，不靠1.5-bit名称证明难度。
- 对应历史条目：`pipelineadcstage`。

### C100-S1

比较器双边沿握手SAR控制。P1，建设成本M，补行为边界。

- 可复用：七位双边沿比较器握手、MSB到LSB和电容控制接口。
- 需要改：补比较器两端冲突、复位打断、最后一次恢复及延迟事件取消；与C112列出协议差异。
- 排序理由：协议较完整，排在四位系统代表之后核验差异。
- Grok意见处理：部分采纳。采纳握手机制；七位本身不构成新考点，保留须以双边沿协议差异为依据。
- 对应历史条目：`l2sarlogic4b`。

### C103-S1

Pipe ADC Gain Control Loop。P1，建设成本M，补行为边界。

- 可复用：正负激励相、7位后端码、差值64目标和增益码饱和。
- 需要改：明确首次成对数据形成时才更新的规则及每相观测；若声称闭环收敛，需给增益码实际作用的对象。
- 排序理由：保留控制器S职责可控，与多权重辨识分开。
- Grok意见处理：部分采纳。采纳配对测量责任；旧接口接外部后端码，不能仅凭标题声称已经提供完整闭环。
- 对应历史条目：`pipeadcgaincontrolloop`。

### C105-S1

Two-stage Pipeline ADC Mini Chain。P0，建设成本M，补行为边界。

- 可复用：两级量化、残差观测、两拍发布及valid接口。
- 需要改：固定粗量化电平与残差闭式、第二级门限、样本缓存及连续/空拍对齐；补必要接口，不用固定五文件代替难度。
- 排序理由：完整流水流程代表，补规格后能独立计算逐样本答案。
- Grok意见处理：采纳缺口。完整修订原题仍未唯一规定粗电平与残差量化关系，采纳；两拍延迟已经明确，应沿用。
- 对应历史条目：`pipelineadctwostage`。

### C109-S1

4-bit SAR ADC System。P0，建设成本M，补行为边界。

- 可复用：四位SAR试位、保持样本、CDAC公式和done输出。
- 需要改：补忙时start、同刻start/clk/reset及vss非零时转换参考；固定监测口的试位前后含义。
- 排序理由：小型完整转换系统适合先建立健康对象和作者验证。
- Grok意见处理：部分采纳。采纳系统代表；同源TB可作配套，但独立协议检查职责另见U27。
- 对应历史条目：`saradcsystem4b`。

### C111-S1

SAR Front-End Logic 4b。P2，建设成本M，补行为边界。

- 可复用：前周期结果发布、测试字捕获和互补电容控制。
- 需要改：核test覆盖与恢复握手的独立价值，明确同刻发布/初始化及非法比较器组合；与C100/C112分组。
- 排序理由：与两项SAR控制候选接近，先做代表后复核是否独立录取。
- Grok意见处理：部分采纳。采纳有时序职责；不因接口或4位形式不同就优先新增，须保留跨转换发布这一差异。
- 对应历史条目：`sarfendlogic4b`。

### C112-S1

4-bit Self-Timed SAR Logic。P1，建设成本M，补行为边界。

- 可复用：自定时四次决策、100ps逻辑延迟和底板切换规则。
- 需要改：规定比较器同时翻转、复位清除待发事件和末位结束；保留由比较器恢复驱动下一步的责任。
- 排序理由：独立于C109的自定时协议，待公共转换对象稳定后整理。
- Grok意见处理：部分采纳。采纳自定时机制；不能与固定时钟SAR仅按位数合并，也不能忽略事件竞争。
- 对应历史条目：`sarlogic4bselftimed`。

### C113-S1

Sigma-delta Modulator Mini Loop。P1，建设成本M，补行为边界。

- 可复用：前一位反馈、积分钳位及16样本计数饱和到15。
- 需要改：保留明确离散更新式，核对输入合法域、计数使用新位还是旧位及复位窗口；不宣称未验证的噪声整形指标。
- 排序理由：已有确定递推，重点是反馈次序和窗口归属。
- Grok意见处理：部分采纳。采纳带历史反馈的代表；“sigma-delta”标题不证明该指定递推的真实调制器性能。
- 对应历史条目：`sigmadeltaminiloop`。

### C114-S1

Synchronous 8-bit DFF Chain V2。P2，建设成本M，补行为边界。

- 可复用：ck9到ck1九位多相对齐与最后发布的历史协议。
- 需要改：标题明确实际九位；公开相位合法序列、同刻相位及未完成帧处理，比较与C105/C353的差异。
- 排序理由：相近对齐任务较多，作为后续协议变体复核。
- Grok意见处理：部分采纳。采纳对齐资产；不因题名8-bit或多时钟端口就另算高难，保留九相历史传递的实际差异。
- 对应历史条目：`sync8bdffsv2`。

### C118-S1

DWA DEM Encoder。P1，建设成本M，整理既有规格。

- 可复用：16单元环形指针、边界单元、码0选一单元及电压译码。
- 需要改：解释特殊选元合同，检验回绕与ptr_init；将简单v2b作为配套，不能据名改成常规DWA的code个单元。
- 排序理由：原选元式已完整，可为U05集成提供对象。
- Grok意见处理：部分采纳。采纳选元机制；同族DWA条目应按实际掩码与更新规则归并，而非仅名称。
- 对应历史条目：`dwademencoder`。

### C128-S1

连续端点归一化二进制DAC。P2，建设成本L，基础整理。

- 可复用：4位连续DAC、码15到vref的端点归一化关系。
- 需要改：公开分母15和动态本地参考行为，校准端点与位权，不扩位宽题。
- 排序理由：固定六项基础层之一，与SAR分母16的试探DAC区别明确。
- Grok意见处理：部分采纳。采纳基础DAC代表；公式不同可保留资产，但不据此扩充主难度题。
- 对应历史条目：`binaryweightedvoltagedac`、`weighteddecoder6bit`。

### C155-S1

SAR CDAC Residue。P1，建设成本M，补行为边界。

- 可复用：初始及时钟捕获、S6下降沿加半参考、其余沿减权重。
- 需要改：规定采样与开关同刻优先级、多开关同刻累加及重复沿；检查残差历史而非静态码和。
- 排序理由：保留电容切换历史，可支撑后续校准任务。
- Grok意见处理：采纳方向。采纳独立开关事件残差，不能把它并成普通静态DAC；参数位宽变体仍合并。
- 对应历史条目：`sarcdacresidue`。

### C169-T1

Linearity RDAC Offset Sweep。P1，建设成本H，新增对象或真值。

- 可复用：RDAC全码扫描、方向翻转减半搜索和参考网格。
- 需要改：保留已有初值/LSB，提供独立RDAC与比较器对象和测量误差定义；检验跨码搜索，避免只复刻指定状态机。
- 排序理由：工程用途明确，但T职责和独立被测对象成本高于规格整理。
- Grok意见处理：部分采纳。不采纳缺初始参考和LSB：参数段已有公式；采纳需形成可检查测量职责，完整流程对象仍待建设。
- 对应历史条目：`linearityrdacoffsetsweep`。

### C170-T1

Offset RDAC Search Flow。P1，建设成本H，新增对象或真值。

- 可复用：六拍RDAC细化、交接拍、八拍失调搜索及重启边界。
- 需要改：沿用已给参考网格，配健康外部对象与独立残差评价；与C169区分细化搜索和全码扫描，防止重复。
- 排序理由：两阶段测量有差异，先与C169共享作者对象后确定独立价值。
- Grok意见处理：部分采纳。不采纳缺LSB与初值：参数段已给1/16和-17/2 LSB；不把旧流程完整性等同测量任务已成立。
- 对应历史条目：`offsetrdacsearchflow`。

### C176-S1

Debounce Latch。P0，建设成本L，补行为边界。

- 可复用：12ns连续资格、输入下降取消、复位取消和定时到期复核。
- 需要改：补重新触发及到期/下降/复位同刻规则，保留最小接口，校准过期预约不得误触发。
- 排序理由：小规模且有真实异步因果难点，首批代表。
- Grok意见处理：部分采纳。不采纳缺资格时长：参数stable=12n已经公开；仍需补事件竞争，采纳其独立时序价值。
- 对应历史条目：`debouncelatch`。

### C179-S1

Propagation Delay Comparator。P1，建设成本M，补行为边界。

- 可复用：过驱动相关对数延迟、上下限和下降沿复位；时间测量辅助口。
- 需要改：明确零过驱动下限、迟到判决取消与时钟最短间隔；计时辅助模块由环境提供或单独说明求解职责。
- 排序理由：独立于简单门限，健康对象可供C196/U07复用。
- Grok意见处理：部分采纳。采纳延迟与过驱动机制；不能把附带计时器自动算成第二道任务。
- 对应历史条目：`propagationdelaycomparator`。

### C193-S1

Offset-calibrated Comparator System。P2，建设成本H，补行为边界。

- 可复用：4位偏移码、threshold_dbg映射与四次更新完成协议。
- 需要改：澄清“有符号码”与0..15编码，cal_ref实际意义及重启窗口；保留控制器模型，不把四次更新ready称为校准收敛。
- 排序理由：与U07/U20及其他校准题重叠，先核清独立责任。
- Grok意见处理：部分采纳。采纳可形成指定行为题；完整摘录没有证明误差由实际比较器反馈，不能直接当完整校准系统录取。
- 对应历史条目：`offsetcalibratedcomparatorsystem`。

### C196-T1

Comparator Delay Overdrive Meter。P1，建设成本M，补行为边界。

- 可复用：外部比较器的时钟到判决间隔、输入过驱动与极性观测。
- 需要改：明确超时、新时钟覆盖、双输出同时到达；保留端口虽名ps/mV却输出SI值的合同，评分测真实时差。
- 排序理由：独立观测已存在，作者对象范围较小。
- Grok意见处理：部分采纳。采纳测量代表；不能按端口后缀擅自换单位，完整原文已说明转换在评价端完成。
- 对应历史条目：`comparatordelayoverdrivemeter`。

### C202-T1

Start Gated Offset Search。P1，建设成本M，新增对象或真值。

- 可复用：START门控、方向反转减半及差分共模驱动。
- 需要改：补健康比较器、可搜索失调域、终止/超时与精度预算；检查START重启后历史隔离，不能只逐拍抄固定序列。
- 排序理由：门控搜索可复用，先与U07共享对象及测量判据。
- Grok意见处理：部分采纳。采纳搜索用途；作为T需验证搜索能测对象，旧递推合同本身更接近驱动器S素材。
- 对应历史条目：`startgatedoffsetsearch`。

### C203-S1

Sampled True-RMS-to-DC Converter。P1，建设成本L，整理既有规格。

- 可复用：四个有效样本的RMS、禁用暂停和异步复位清窗。
- 需要改：保留公式和四样本窗，核同刻reset/clk及valid持续；用非恒定正负样本区分RMS与均值。
- 排序理由：已有明确状态与答案，整理成本低。
- Grok意见处理：采纳方向。采纳非线性窗口统计代表；不因公式短而排除，也不扩展窗口长度变体。
- 对应历史条目：`sampledtruermstodcconverter`。

### C214-S1

Amplifier Filter Chain。P2，建设成本L，整理既有规格。

- 可复用：限幅增益、两级低通及第二级使用s1_next的规定。
- 需要改：保持同拍级联更新规则和初态，移除多余骨架；与C260/C264比较独立贡献，条件不足时保留扩展。
- 排序理由：与滤波代表有重叠，待核心动态题校准后决定正式地位。
- Grok意见处理：部分采纳。采纳可成模型题；两级递推并不自动升为高难完整工程任务。
- 对应历史条目：`amplifierfilterchain`。

### C219-S1

Chopper-Stabilized Differential Amplifier。P1，建设成本M，补行为边界。

- 可复用：双边沿斩波/解调、内部失调、低通与hold/reset行为。
- 需要改：核hold与reset/enable优先级、仅输出钳位的状态差异及残差判据；不声称真实晶体管噪声抑制。
- 排序理由：数值链完整，作者需独立验证状态与输出饱和。
- Grok意见处理：采纳方向。采纳完整信号链价值；保留斩波位置与内部失调位置的差异，不能并成简单符号翻转。
- 对应历史条目：`chopperstabilizeddifferentialamplifier`。

### C221-S1

Common-mode Feedback Loop。P1，建设成本M，补行为边界。

- 可复用：残差前后两次计算、无符号trim饱和和共模对称校正。
- 需要改：限定可校正共模范围；输出钳位时不保证差分幅度保持，评分区分饱和与真实锁定。
- 排序理由：已有更新式，补域与失锁条件即可形成清楚任务。
- Grok意见处理：部分采纳。采纳反馈机制；“完整”不消除单向执行器和钳位带来的可达域限制。
- 对应历史条目：`commonmodefeedbackloop`。

### C245-S1

Two-stage Op-amp Slew Macromodel。P1，建设成本M，补行为边界。

- 可复用：两级增益参数、负载代理扰动、限步和两拍建立资格。
- 需要改：明确stage1闭式及输出更新取值顺序；按离散限步模型命名，不冒充连续器件运放动态。
- 排序理由：动态对象可复用，先修清楚模型，再服务建立测量。
- Grok意见处理：部分采纳。stage1_gain=20已公开，不能说比例完全缺失；但原文未写唯一stage1关系，采纳补完整行为式。
- 对应历史条目：`twostageopampslewmacromodel`。

### C248-T1

Settling Window Detector。P1，建设成本M，补行为边界。

- 可复用：真实输入/目标/容差观测、连续20ns驻留与进入时间编码。
- 需要改：明确定时起点、初始在窗、动态tol/target和离窗同刻；检验时间码是进入时刻而非等待时长。
- 排序理由：独立观察对象已明确，可服务U25但保留测量器交付差异。
- Grok意见处理：部分采纳。采纳测量责任；区别于固定120ns置done的同名素材，不用预定时刻冒充建立时间。
- 对应历史条目：`settlingwindowdetector`。

### C250-S1

First Order Lowpass。P2，建设成本L，基础整理。

- 可复用：500ps周期离散低通、alpha和零初态。
- 需要改：公开alpha合法域及timer起相，名称明确为离散一阶；避免按连续RC答案评分。
- 排序理由：固定六项基础层之一，作为动态测量的简单对照。
- Grok意见处理：部分采纳。采纳基础滤波代表；不按各种laplace/zi写法继续扩张基础层。
- 对应历史条目：`firstorderlowpass`。

### C260-S1

连续一阶低通加输出采样。P0，建设成本M，整理既有规格。

- 可复用：100ns连续一阶低通及外部时钟采样、仅清采样输出的复位。
- 需要改：把指定laplace调用转为传递函数与状态行为，补初态和误差；保留连续历史，不给实现放置骨架。
- 排序理由：连续历史与采样状态分离有明确价值，整理为首批代表。
- Grok意见处理：部分采纳。不采纳缺系数/截止：Task Contract已给100ns和完整laplace式；采纳应让规格可独立理解。
- 对应历史条目：`laplacendlowpassfilter`、`laplacenppolefilter`。

### C263-S1

Switched-capacitor Integrator Phase Pair。P1，建设成本M，补行为边界。

- 可复用：phi1采样、phi2积分、拒绝重叠及phase_metric定义。
- 需要改：精确定义重叠、重复phi1、无phi1的phi2及拒绝后恢复；区分内部积分状态与输出钳位。
- 排序理由：采样对与积分有独立历史，建设范围中等。
- Grok意见处理：部分采纳。采纳两相积分机制；“拒绝重叠”的检测范围仍需明确，不能只检查理想相位序列。
- 对应历史条目：`switchedcapacitorintegratorphasepair`。

### C264-S1

离散一阶低通加输出采样。P0，建设成本M，整理既有规格。

- 可复用：zi系数0.25、1/-0.75及100ns内部更新与外部输出采样。
- 需要改：整理成可独立理解的离散传递合同，核初态、采样相位、插值及双采样同刻关系，不猜测等价递推。
- 排序理由：与C260形成连续/离散区别，不能按语法版本重复计题。
- Grok意见处理：部分采纳。不采纳缺zi系数：Task Contract已公开完整调用；采纳需要公开完整动态语义和精度。
- 对应历史条目：`zinddiscretefilter`、`zinpdiscretefilter`。

### C266-S1

Slew Limited Envelope。P0，建设成本M，整理既有规格。

- 可复用：峰值保持/释放、0..0.8钳位和分别为8e8/3e8 V/s的斜率。
- 需要改：改写为状态与斜率合同，核两个不同目标输出的限速、复位目标变化与连续轨迹；不提供完整slew调用骨架。
- 排序理由：与滤波任务互补，原数值模型可直接用于作者参考推导。
- Grok意见处理：部分采纳。不采纳缺上升下降斜率：参数段已有；采纳对行为可检查性的要求，保留采样目标与连续输出差异。
- 对应历史条目：`slewlimitedenvelope`。

### C268-S1

Bang-Bang Phase Detector。P1，建设成本M，补行为边界。

- 可复用：数据沿观察clk/retimed_data关系及下一时钟沿清脉冲。
- 需要改：明确阈值等号、同刻data/clk和重复数据沿的更新规则；不扩大为完整CDR捕获问题。
- 排序理由：局部检测器职责独立，能为后续CDR提供健康部件。
- Grok意见处理：部分采纳。采纳相位检测代表；原合同仍有边沿相遇边界，不以“时序”标签证明已完备。
- 对应历史条目：`bangbangphasedetector`。

### C270-S1

PLL Feedback Clock Divider。P1，建设成本M，补行为边界。

- 可复用：动态整数分频、奇数高低段、÷1和换码清资格。
- 需要改：明确码变化生效及首段极性，检验输出完整周期与输入沿数；防止将每N沿翻转误当÷N。
- 排序理由：分频语义清楚，可支撑PLL验证，但不排在首批新增对象之前。
- Grok意见处理：采纳方向。采纳动态分频机制；8/9、16/17等近似变体优先作参数或配套，不能只换位宽加题。
- 对应历史条目：`clockdivider`。

### C273-S1

Lock Detector。P2，建设成本L，补行为边界。

- 可复用：最近反馈沿与连续need次参考资格、复位历史隔离。
- 需要改：明确无历史、同刻边沿及参考停摆的合同边界；保留局部资格器名称，不声称排除所有伪锁。
- 排序理由：时钟类已有较多主例，先作为系统验证的配套再校准独立难度。
- Grok意见处理：部分采纳。采纳可成局部模型题；最近沿计数不足以证明整个PLL锁定，需与U26职责区分。
- 对应历史条目：`lockdetector`。

### C275-S1

即时互清三态PFD。P1，建设成本M，补行为边界。

- 可复用：REF/DIV置位、相反沿到来即时互清的三态PFD。
- 需要改：明确完全同时边沿和模拟平滑重叠的观察窗口；与C343延迟互清分别保存。
- 排序理由：原规则较清楚，事件相遇可独立评价。
- Grok意见处理：采纳方向。采纳独立PFD语义；不同互清机制有实际区别，不把全部PFD按名称合并。
- 对应历史条目：`pfdupdownstate`。

### C278-S1

ADPLL Ratio Hop Timer。P1，建设成本H，补行为边界。

- 可复用：ADPLL端口、DCO频率/码范围、变比和锁定资格参数。
- 需要改：先选定给定控制律的建模合同，或公开性能约束的设计合同；明确捕获域和时序误差，不按未公开的唯一轨迹评分。
- 排序理由：系统价值高，先完成控制律/评分口径，不能因L2标题就先建。
- Grok意见处理：采纳缺口。采纳缺控制码更新关系的判断；若允许自主设计控制律，缺更新式不自动是错误，但必须补可验收性能边界。
- 对应历史条目：`adpllratiohoptimer`。

### C279-S1

BBPD Data Edge Alignment。P1，建设成本M，补行为边界。

- 可复用：0.8ns死区、名义周期、双向数据沿及UP/DN脉冲。
- 需要改：明确名义下一沿与实际下一沿区别，限定时钟变化域；补中点平局和脉冲重叠规则，保证因果可实现。
- 排序理由：可与C268形成不同观测机制，但先处理因果性。
- Grok意见处理：部分采纳。不采纳缺死区宽度：deadzone已公开；采纳需要可检查时间关系，预测名义沿不能偷读未来实际沿。
- 对应历史条目：`bbpddataedgealignment`。

### C282-S1

Charge Pump PFD State Machine。P1，建设成本M，整理既有规格。

- 可复用：三态饱和PFD、固定tstep积分和控制电压钳位。
- 需要改：保留离散电压更新式，说明不是保守电流电荷泵；核ref/fb/timer同刻及积分饱和恢复。
- 排序理由：已有独立更新关系，和即时互清PFD机制不同。
- Grok意见处理：采纳方向。采纳状态与积分组合；不因使用charge pump名称扩大物理模型主张。
- 对应历史条目：`chargepumppfdstatemachine`。

### C286-S1

Differential VCO With Clip And Idtmod。P1，建设成本M，整理既有规格。

- 可复用：差分控频、频率钳位、模一相位和差分正弦输出。
- 需要改：将指定idtmod/clip写法整理为频率积分合同；核相位初态、控频阶跃连续性和观测误差。
- 排序理由：关键是相位历史而非语法，原解析关系可继承。
- Grok意见处理：采纳方向。采纳连续相位机制；不按sin/idtmod等实现写法扩充同功能题。
- 对应历史条目：`differentialvcoclipidtmod`。

### C290-S1

DLL Delay-line Lock。P1，建设成本H，补行为边界。

- 可复用：DLL两沿比较、每沿锁存延迟、码饱和及四次锁定。
- 需要改：限定可达相位域、最小边沿间距及同刻事件；校准两独立边沿延迟造成的脉宽变化，不混用U15保持脉宽合同。
- 排序理由：待延迟部件与测量先稳定，作为系统层任务。
- Grok意见处理：部分采纳。采纳完整DLL价值；完整行为仍需合法域和健康参考，不能按标题认定所有时序均可实现。
- 对应历史条目：`dlldelaylinelock`。

### C292-S1

Edge Delay Line with Deglitch Window。P1，建设成本M，补行为边界。

- 可复用：资格tick、额外延迟tick、反向前取消和拒绝脉冲。
- 需要改：明确tick起相、资格后反向事件、重叠待发沿及报告脉宽；保留默认参数计分范围或明确扩展。
- 排序理由：先复用C176和U15经验，避免同时建立多套冲突事件规则。
- Grok意见处理：部分采纳。采纳独立去毛刺延迟；摘录未闭合资格后事件管理，不能直接录取。
- 对应历史条目：`edgedelaylinewithdeglitch`。

### C299-S1

Fractional-N Divider Accumulator Flow。P1，建设成本H，补行为边界。

- 可复用：分数累加器溢出选N-1、每计数段翻转及PI参数。
- 需要改：明确相位误差符号和配对、PI递推次序、可捕获域；保持完整fb周期为两个翻转段的定义。
- 排序理由：系统代表有价值，但比单分频器更需独立闭环校准。
- Grok意见处理：部分采纳。采纳分数分频闭环方向；“有公式”不等于控制律与捕获条件均完整，需核正常参考。
- 对应历史条目：`fractionalndivideraccumulatorflow`。

### C300-S1

Fractional-N Synthesizer Mini Loop。P2，建设成本M，补行为边界。

- 可复用：N/N+1分频选择、16段平均监测和输入DCO沿来源。
- 需要改：公开累加模数、先选后累加次序和动态frac生效；与C299明确N+1与N-1、开环分频与闭环的差别。
- 排序理由：先做分频与PLL代表，再检查此变体是否独立录取。
- Grok意见处理：采纳缺口。采纳缺累加模数，4位frac不能替代明确模数合同；不能把单调平均值当完整真值。
- 对应历史条目：`fractionalnsynthesizerminiloop`。

### C301-S1

Frequency-word DCO with Divider Monitor。P1，建设成本M，整理既有规格。

- 可复用：频率字钳位、每沿采码、下一半周期生效及监测分频。
- 需要改：统一重启首沿、reset取消和周期量测；明确div_clk每N个DCO上升沿翻转，因此完整周期为2N。
- 排序理由：健康时钟源可为多个T任务复用，合同较明确。
- Grok意见处理：采纳方向。采纳待发沿不重定时的机制；代码字数与频段变体不另计。
- 对应历史条目：`frequencyworddcodividermonitor`。

### C302-S1

Glitchless Clock Mux Selector。P1，建设成本M，补行为边界。

- 可复用：两源均低时切换、切换时4ns标记及首输出沿资格。
- 需要改：规定切换请求反复变化、停钟、禁用恢复和标记重触发；限定能完成切换的输入域并报告等待。
- 排序理由：典型工程协议，先补可达条件再评分。
- Grok意见处理：部分采纳。采纳无毛刺切换价值；两时钟总无共同低电平时不能暗中要求必定切换。
- 对应历史条目：`glitchlessclockmuxselector`。

### C308-S1

Deterministic Jittered Clock Source。P1，建设成本L，整理既有规格。

- 可复用：按seed和沿号计算的确定性半周期调制、待发沿保持。
- 需要改：补第一个沿与初始半周期、enable改变时沿号继续规则；按真实边沿时刻验证，不按幅值随机代理验证。
- 排序理由：规则可解析，能支撑孔径及频率测量的作者激励。
- Grok意见处理：采纳方向。采纳真实时间扰动源；区别于历史把随机数加到幅值的jitter命名素材。
- 对应历史条目：`jitteredclocksourcedeterministic`。

### C312-S1

Non-overlapping Clock Generator。P1，建设成本M，补行为边界。

- 可复用：互斥两相、dead_ticks与reset/disable清待定状态。
- 需要改：定义死区内反向请求是替换还是忽略、tick对齐及短周期域；验证两相阈值层面不重叠。
- 排序理由：可复用延迟事件校准，避免通过模糊请求行为增加难度。
- Grok意见处理：部分采纳。采纳非重叠时序价值；未写重触发时不能仅凭完整摘录放行。
- 对应历史条目：`nonoverlapclockgenerator`。

### C316-S1

时钟先后序列累计监控系统。P2，建设成本M，补行为边界。

- 可复用：时钟先后累计、偏移二进制相位码、锁定/重资格计数。
- 需要改：明确重复单边沿配对、同刻与计数复位；名称保持先后序列监控，不将phase code解释为秒或真实相位。
- 排序理由：时钟监控较密集，先做U26真实关系验证再复核此代表。
- Grok意见处理：部分采纳。采纳可成指定行为题；其累计先后数不是物理相位，主集需保持解释边界。
- 对应历史条目：`plltimingmonitorsystem`。

### C328-S1

TDC Event Measurement System。P1，建设成本M，补行为边界。

- 可复用：start/stop武装、计数锁存、新start重启和溢出停止。
- 需要改：明确start/stop/clk同刻、重复start和第256沿；保证溢出与正常停止可区分。
- 排序理由：状态可独立推导，可为U16提供基线。
- Grok意见处理：采纳方向。采纳同步粗TDC职责；与细粗TDC保留量化机制差异，不按位数加题。
- 对应历史条目：`tdcmeasurementsystem`。

### C331-T1

Duty-cycle Window Monitor。P1，建设成本M，补行为边界。

- 可复用：完整高低周期测量、duty_metric与窗口资格。
- 需要改：明确duty_min/max来自端口、初次完整周期、停钟超时和供电映射；用不同占空比的真实输入验证。
- 排序理由：观测对象简单，可与U22共享测量部件。
- Grok意见处理：部分采纳。采纳测量价值；完整周期与无有效周期的报告必须明确，不能只算固定钟的比例。
- 对应历史条目：`dutycyclewindowmonitor`。

### C339-T1

Time Difference Detector。P1，建设成本M，补行为边界。

- 可复用：前窗首个双输入沿时差、缺沿保持和电压限幅编码。
- 需要改：公开差值符号、窗口边界归属、缺沿状态和首次输出；不能把缺沿保持解释为新有效测量。
- 排序理由：独立答案清楚，作为时间测量方向的中等建设项。
- Grok意见处理：采纳方向。采纳窗口测时代表；和简单周期计数区别在前窗配对及缺测行为。
- 对应历史条目：`timediffdetector`。

### C343-S1

PFD With External Active Low Reset。P2，建设成本M，补行为边界。

- 可复用：外部低有效复位、双状态出现后80ps延迟互清。
- 需要改：明确复位取消待发互清、delay=0、额外输入沿和旧定时器不得清新周期；删重复属性段。
- 排序理由：保留有价值事件变体，先完成主PFD和延迟代表。
- Grok意见处理：采纳方向。采纳与C275即时互清不同的机制；不是因多一个reset端口而单独计题。
- 对应历史条目：`pfdactivelowreset`。

### C348-S1

AGC Receiver Leveling Loop。P1，建设成本M，整理既有规格。

- 可复用：v4目标0.18V、非对称增益步进、输出/增益钳位和监测次序。
- 需要改：公开可达输入域、饱和未收敛状态及输出用旧增益、gain_mon用新增益的窗口；校准恢复轨迹。
- 排序理由：可建立U28健康对象，原闭环更新已经明确。
- Grok意见处理：部分采纳。评论据较简略AGC素材；当前首选v4已给目标和完整更新式，不采纳原件缺公式的推断，仍采纳动态可验收要求。
- 对应历史条目：`agcreceiverlevelingloop`。

### C353-S1

Deserializer DEMUX Alignment Macro。P1，建设成本M，补行为边界。

- 可复用：四槽串并转换、align重定位及已采槽有效性。
- 需要改：定义align与clk同刻、重新对齐是否清旧槽、word_valid保持范围；比较与C114发布协议。
- 排序理由：协议资产完整，作者校准主要在帧边界。
- Grok意见处理：部分采纳。采纳重对齐责任；简单移位变体不另列，保留中途重新同步的差异。
- 对应历史条目：`deserializerdemuxalignmentmacro`。

### C354-S1

DFE Error-proxy Loop。P2，建设成本M，整理既有规格。

- 可复用：两个自适应权重、旧历史反馈及更新后残差的显式递推。
- 需要改：保持这是误差代理模型；核正确输出切片与生输入判决的区别，不能宣称实际均衡质量得到改善。
- 排序理由：同族已有更明确工程职责，保留候选但后置。
- Grok意见处理：部分采纳。采纳可独立实现的递推题；不将代理残差下降等同接收质量改善，先比较U17/U09。
- 对应历史条目：`dfeerrorproxyloop`。

### C358-S1

3-tap FFE Transmitter。P2，建设成本L，整理既有规格。

- 可复用：当前/前一/前二符号的三项加权、码控系数和限幅。
- 需要改：明确中性历史及pre/post名称对应实际历史位置；不增加未来符号接口来强凑“预游标”。
- 排序理由：可作均衡配套和变体，暂不优先独立建设。
- Grok意见处理：部分采纳。采纳有限历史模型；公式完整不自动有足够难度，后续与DFE一起校准。
- 对应历史条目：`ffetransmitter3tap`。

### C360-S1

IQ Downconversion Chain。P1，建设成本M，整理既有规格。

- 可复用：v4完整四相系数表、混频式、两路0.85更新及复位相位。
- 需要改：保留表与公式，核第一相、钳位顺序与双路状态；说明离散LO包络模型范围。
- 排序理由：双路信号链可继承，先整理再判断与IQ校准任务差异。
- Grok意见处理：部分采纳。不采纳首选原题缺相位表和输出式：v4完整段已写明；评论摘录不足以否定原件。
- 对应历史条目：`iqdownconversionchain`。

### C371-S1

Clocked Sine Source。P2，建设成本M，补行为边界。

- 可复用：时钟采样正弦、每实例随机状态、sigma=0及差分参考。
- 需要改：固定随机序列评价口径与复位是否重置RNG；区分同实现可重复和跨后端数值序列相同，不隐含后者。
- 排序理由：可为U08服务，独立题资格待实测。
- Grok意见处理：部分采纳。采纳激励资产；其主要用途是测量配套，不能靠随机函数名称提升难度。
- 对应历史条目：`clockedsinesource`。

### C384-S1

Complete Calibration Loop。P1，建设成本M，整理既有规格。

- 可复用：v4完整残差、trim更新、一阶对象与饱和的关系。
- 需要改：明确目标/初态合法域和饱和不可达情形，独立验实际out而非metric；保留完整更新式。
- 排序理由：闭环关系明确，可作为多种校准升级的简单基线。
- Grok意见处理：部分采纳。不采纳首选原题缺对象和更新式：v4代码块已给出；采纳要确认真实闭环方向与可达范围。
- 对应历史条目：`completecalibrationloop`。

### C385-S1

Instrumentation Amplifier Offset-trim System。P1，建设成本M，补行为边界。

- 可复用：静态偏移二进制修调、残差累加及差分放大。
- 需要改：明确非校准期间trim输入改动的生效时刻、累加范围及校准激励域；ready三次更新不等同消偏完成。
- 排序理由：有实际残差反馈，补激励与完成语义后有价值。
- Grok意见处理：部分采纳。采纳校准控制机制；需要防止把真实差分信号当偏置消掉，完整摘录尚不能保证工程适用域。
- 对应历史条目：`instrumentationamplifieroffsettrim`。

### C396-S1

异步断言、两拍释放的复位同步器。P2，建设成本L，基础整理。

- 可复用：低有效异步复位断言、两次有效时钟后释放。
- 需要改：统一中文标题为“异步断言、两拍释放”，明确初始高复位输入与同刻边沿，不增加多域流程。
- 排序理由：固定六项基础层之一，为U29提供简单对照。
- Grok意见处理：部分采纳。采纳基础复位代表；不能按两级DFF形式扩张题量，保留安全断言的必要性。
- 对应历史条目：`activehighresetsynchronizer`。

### C399-S1

Charge-pump Voltage Multiplier Controller。P1，建设成本M，补行为边界。

- 可复用：离散泵升/泄漏、电压上限、迟滞调节与三次资格。
- 需要改：补phase脉宽/非重叠规则、禁用泄漏更新时基和目标不可达；只保留电压状态模型。
- 排序理由：与Buck控制有不同对象状态，但需先闭合时基规则。
- Grok意见处理：部分采纳。采纳调节机制；无电荷或电流对象时不能宣称验证真实倍压器效率。
- 对应历史条目：`chargepumpvoltagemultipliercontroller`。

### C400-S1

Clock-and-data Valid Qualifier。P1，建设成本L，补行为边界。

- 可复用：数据沿年龄、上电过期状态和先加龄后资格。
- 需要改：明确data与clk同刻、max_age合法域及停钟行为；独立检查到期与重新获得资格。
- 排序理由：规则较齐，作为电源/时序协议的局部任务。
- Grok意见处理：部分采纳。采纳年龄资格用途；单状态数不决定价值，但不应扩大成数据链可靠性验证。
- 对应历史条目：`clockdatavalidqualifier`。

### C402-S1

Dynamic Supply Level Driver。P2，建设成本L，基础整理。

- 可复用：本地电源归一化输入、动态输出轨和供电不足回低。
- 需要改：补零/负供电跨度、阈值等号及平滑观测容差；保持电压域基础模型。
- 排序理由：固定六项基础层之一，支撑U10但不替代隔离恢复协议。
- Grok意见处理：部分采纳。采纳供电相关基础代表；不按每种rail阈值复制主集题。
- 对应历史条目：`dynamicsupplyleveldriver`。

### C403-S1

LDO Load-Step Recovery Flow。P1，建设成本M，整理既有规格。

- 可复用：v4电压负载代理、上下阶跃冲量、0.30恢复和目标公式。
- 需要改：统一内部状态与输出钳位、复位负载历史及阶跃等号；明确代理单位不是安培。
- 排序理由：可作为U25健康对象的起点，需独立核验参考解。
- Grok意见处理：采纳方向。采纳可成指定动态模型；与U25同源但S写模型、T做独立表征，两种交付不能机械合并。
- 对应历史条目：`ldoloadsteprecovery`。

### C408-S1

Power and Reset Sequencer。P1，建设成本M，补行为边界。

- 可复用：电源资格、核复位释放、模拟/数字使能和ready的逐拍次序。
- 需要改：明确enable_req撤销与重启、异步欠压及同刻电源/时钟；检查正常最终完成，不能只检查输出始终低。
- 排序理由：工程协议清楚，可与U10/U29共享电源场景。
- Grok意见处理：部分采纳。采纳完整启动流程；按顺序输出并不等于已覆盖中断恢复边界。
- 对应历史条目：`powerresetsequencersystem`。

### C411-S1

Rail Ramp Rate Startup Monitor。P1，建设成本L，补行为边界。

- 可复用：0.72..1.08V供电窗、每样本dv范围及三次稳定资格。
- 需要改：明确初始前样本、使能恢复和采样间隔含义；名称中的ramp rate按每拍变化而非V/s解释。
- 排序理由：低成本保留启动采样机制，避免与纯阈值POR混同。
- Grok意见处理：部分采纳。不采纳缺供电窗上下限：参数已公开；仍须明确delta_v与时间斜率的区别。
- 对应历史条目：`railrampratestartupmonitor`。

### C417-S1

Supply Supervisor with Brownout POR。P1，建设成本M，整理既有规格。

- 可复用：上下迟滞阈值、四拍释放、异步欠压和必须新跨阈值的恢复。
- 需要改：保留释放时已高电压仍等待新跨越的历史合同；补带内计数中断、同刻和停钟，不与C393混写。
- 排序理由：有价值历史变体，与U29采用不同合同且分别校准。
- Grok意见处理：部分采纳。采纳独立supervisor模型；完整性不代表该恢复规则适合所有系统，须在题面显式说明。
- 对应历史条目：`supplysupervisorbrownoutpor`。

### C421-S1

Bandgap Startup and Trim System。P1，建设成本M，补行为边界。

- 可复用：两拍启动、温度电压代理的参考式、trim_lsb与三拍ready。
- 需要改：明确4位修调编码、加减步长和对参考的符号，校准可达温度代理域；不宣称物理带隙温漂。
- 排序理由：能补参考启动与校准结合，先完成确定关系。
- Grok意见处理：部分采纳。trim_lsb=2mV已经公开；采纳缺码更新和校正映射，不能只凭“降低误差”给唯一评分。
- 对应历史条目：`bandgapstartuptrimsystem`。

### U04-T1

外部ADC静态线性度的独立表征。P1，建设成本H，新增对象或真值。

- 可复用：历史转换接口、码/重构观测和扫描素材。
- 需要改：提供独立非理想ADC及阈值真值、输入和采样接口；定义INL参考线、DNL、缺码与预算，禁止读取内部表直接报告。
- 排序理由：独立测量价值高，需先造健康对象与真值，放第二批。
- Grok意见处理：部分采纳。采纳历史行为可独立实现；旧题自己量化再查重构表，不是外部ADC静态线性度测量，仍需改造职责。
- 对应历史条目：`converterstaticlinearitymeasurement`。

### U05-I1

DEM选元驱动失配分段DAC的集成。P1，建设成本H，新增对象或真值。

- 可复用：分段解码、DWA旋转、指针及选元掩码。
- 需要改：让所选失配单元实际决定输出，提供健康单元权重对象、平均误差目标与合法输入域；不沿用与掩码无关的理想vref*code/63输出。
- 排序理由：先复用C118选元机制，再建设失配DAC集成对象。
- Grok意见处理：部分采纳。采纳DEM资产；原输出绕过选元权重，摘录完整也不能证明DEM产生工程效果。
- 对应历史条目：`segmenteddacdemsystem`。

### U12-I1

实际镜像观测驱动的I/Q校准集成。P2，建设成本H，新增对象或真值。

- 可复用：I/Q端口、trim状态和电压域混频素材。
- 需要改：用实际镜像观测驱动校正，补独立I/Q失配对象、可辨识激励与真值；只采用明确包络模型。
- 排序理由：核心观测与对象都需新增，后置建设。
- Grok意见处理：部分采纳。采纳代理指标不是镜像的核心意见；当前v4已给代理式和更新量，补这些公式本身仍不能形成真实镜像校准。
- 对应历史条目：`imagerejectmixercalibrationloop`。

### U14-S1

具有幅相非线性和有限记忆的PA包络模型。P2，建设成本H，新增对象或真值。

- 可复用：幅度压缩及前样本记忆素材，drive/reset接口。
- 需要改：建设有限记忆复包络行为关系，用成对I/Q电压表现幅相；公开系数、采样、初态与禁用恢复，独立验证实际相位。
- 排序理由：原素材不能直接满足新标题，需新增模型与参考，后置。
- Grok意见处理：部分采纳。Grok列为可成题仅适用于旧代理合同；pm_metric是幅差代理，不能继承为AM/PM相移。
- 对应历史条目：`paampmmemorytapmacro`。

### U01-I1

模拟配置的原子提交与生效时刻。P1，建设成本M，新增对象或真值。

- 可复用：串行配置加载和并行寄存器接口。
- 需要改：提供可用装载器、影子/生效存储和模拟消费者；定义最小帧、原子commit及采样生效边界，不叠加CRC或全SPI。
- 排序理由：模块边界清楚、增量可控，第二批优先的I任务。
- Grok意见处理：部分采纳。采纳移位资产可用；原64位移位只是基础S，原子提交的I职责是本规划新增，不能算已由评论认证。
- 对应历史条目：`configshiftregister64b`。

### U02-I1

共享采集通路的串扰与吞吐预算。P2，建设成本H，新增对象或真值。

- 可复用：多通道保持、选择和无效选码处理。
- 需要改：新增可独立验证的共享通路建立/串扰等效对象，公开源变化域与帧时限，再考察采集读出安排。
- 排序理由：新物理等效关系与真值成本高，后置于C064。
- Grok意见处理：部分采纳。采纳多通道原模型；旧独立保持加mux没有共享通路误差，不能直接宣称串扰/吞吐工程约束。
- 对应历史条目：`muxedtrackholdarrayreadout`。

### U03-T1

交织采样的增益、偏置和时间失配分离。P2，建设成本H，新增对象或真值。

- 可复用：两路采样接口、重置后资格和观测组织。
- 需要改：建立真正改变采样时刻的交织对象，分离增益/偏置/时间失配；补激励带宽、可辨识域与独立参数真值。
- 排序理由：完整对象与辨识实验均新增，先完成较成熟测量题。
- Grok意见处理：采纳重建。采纳样本电压差不是时间偏差；旧skew_metric只能作代理素材，补一个比例系数不足以完成改造。
- 对应历史条目：`interleavedadcskewmonitor`。

### U06-T1

DAC建立时间与毛刺冲量测量。P2，建设成本H，新增对象或真值。

- 可复用：DAC码变换、前码历史和报告接口。
- 需要改：提供有实际开关延迟/建立过程的DUT或有来源波形，定义基线、积分窗与恢复判据；输出V·s毛刺冲量，不冒称焦耳。
- 排序理由：对象和测量真值成本高，C136等先作配套，不先造大题。
- Grok意见处理：采纳重建。采纳码差代理没有毛刺波形与积分含义；独立测量对象是必要新增资产。
- 对应历史条目：`unarydacglitchenergymetric`。

### U07-T1

比较器本征迟滞与延迟影响的分离表征。P1，建设成本H，新增对象或真值。

- 可复用：外部输入/比较器输出的上升下降翻转点捕获。
- 需要改：给带独立阈值和延迟的健康对象族，要求分离本征迟滞与动态延迟，定义等待上限、精度和预算；首版不加噪声。
- 排序理由：独立工程问题明确，作为第二批T代表。
- Grok意见处理：部分采纳。采纳翻转测量素材；单次斜坡在输出翻转时取vin测到的包含延迟，不等于本征迟滞。
- 对应历史条目：`hysteresistripcharacterizer`。

### U08-T1

滤波与放大通路的幅相响应测量流程。P1，建设成本H，新增对象或真值。

- 可复用：差分源、dither、放大链和历史测量接口。
- 需要改：新增明确的被测通路与独立传递函数真值、实验访问接口和幅相容差；允许相关或正弦拟合，不指定完整实现。
- 排序理由：有完整流程素材，需先把对象、观测和答案闭合。
- Grok意见处理：部分采纳。原参数段已有ACTUAL_GAIN等数值，不能说完全无增益；仍采纳端口关系及真正幅相测量职责不足。
- 对应历史条目：`gainextractionflow`。

### U09-I1

由实际接收质量驱动的均衡闭环。P2，建设成本H，新增对象或真值。

- 可复用：boost码、差分增强通路与控制器分工。
- 需要改：提供健康离散通道、质量观测和训练/留出序列，让实际输出决定调节；公开步长和可达域，不冒称连续CTLE。
- 排序理由：闭环对象与质量目标新增较多，后置建设。
- Grok意见处理：部分采纳。采纳boost更新及误差含义需明确；adapt_tol已经公开，且补步长仍不能解决外部指标不受输出影响的问题。
- 对应历史条目：`ctleadaptationloop`。

### U10-I1

双电源域的信号隔离与安全恢复。P1，建设成本M，新增对象或真值。

- 可复用：低侧阈值、高侧轨跟随与enable/reset电平转换。
- 需要改：给两个域的有效范围和健康部件，定义隔离、上电次序及恢复协议；只检查电压功能，不声称反向电流或高阻安全。
- 排序理由：集成边界明确，可作为第二批I代表。
- Grok意见处理：部分采纳。采纳level-shifter基础资产；旧单模块不等于双域安全恢复，I职责需新协议与消费者。
- 对应历史条目：`levelshifterenablerailtracking`。

### U11-T1

有噪声比较器的失调与判决概率表征。P2，建设成本H，新增对象或真值。

- 可复用：含offset、vn、seed与延迟的随机比较器接口。
- 需要改：提供固定分布假设及隐藏参数真值，限定采样预算、置信误差和正常误报；明确输出极性与独立随机序列。
- 排序理由：统计校准新增较多，排在确定性U07之后。
- Grok意见处理：部分采纳。vn=1m和normal分布已公开，不采纳缺标准差；仍需明确真值/统计验收，不能复刻同一随机序列当答案。
- 对应历史条目：`latchedcomparatordelay`。

### U13-T1

有时间预算和不确定度的频率测量。P1，建设成本M，新增对象或真值。

- 可复用：窗口启停、事件计数和done接口。
- 需要改：给量化/有误差的参考时基，定义频率域、分辨率、时间预算与超时；不允许靠无限精度时间戳消除题目权衡。
- 排序理由：所需新对象较小，可在基础时钟源后建设。
- Grok意见处理：部分采纳。采纳计数素材；计边沿不等于完成有不确定度的频率测量，原完整行为仅是仪表部件。
- 对应历史条目：`eventcounterwindowed16b`。

### U15-S1

可编程延迟单元的脉冲保持与待发事件管理。P0，建设成本M，补行为边界。

- 可复用：load锁码、延迟映射和复位取消待发沿。
- 需要改：解决逐沿锁不同延迟与保持整脉宽的冲突，选定逐脉冲锁码或合法改码域；补load同刻、未加载和最小脉宽。
- 排序理由：机制独特且改造有界，首批建立事件管理代表。
- Grok意见处理：部分采纳。不采纳原行为已完全可成题：高低沿之间改码时两条要求冲突；采纳延迟单元的工程价值。
- 对应历史条目：`digitallycontrolleddelaycell`。

### U16-S1

含两端细时间的细粗TDC行为模型。P0，建设成本M，补行为边界。

- 可复用：start/stop、粗计数、stop细时间与valid接口。
- 需要改：补起点和终点两端细时间的量化关系，定义参考预热、码饱和/无效、同刻事件及输出协议。
- 排序理由：粗细时间结合有独立价值，公开数学关系即可避免凭模糊公式制造难度。
- Grok意见处理：部分采纳。旧细时间只描述stop相位，可成原代理题；不能直接当完整间隔TDC，采纳资产但扩展责任需明示。
- 对应历史条目：`finecoarsetdcencoder`。

### U17-S1

使用历史判决反馈的两抽头DFE接收器。P0，建设成本M，补行为边界。

- 可复用：两拍判决历史、反馈校正、tap_lsb与切片输入观测。
- 需要改：补tap码到有符号权重、判决编码、中性初态；校准旧历史/当前判决的可区分序列，减少固定文件拆分。
- 排序理由：独立因果关系清楚，首批中等难度代表。
- Grok意见处理：部分采纳。tap_lsb=20mV已给，不能说完全无系数；仍采纳反馈合成和编码未闭合的缺口。
- 对应历史条目：`dfereceiver2tap`。

### U18-S1

带软启动、载波和资格状态的Buck控制器。P0，建设成本M，整理既有规格。

- 可复用：软启动、0.05占空比步进、模20载波和三拍pgood。
- 需要改：保留已有关系，补vfb/vref域、目标下降及reset/disable优先级；删除不必要文件数量约束。
- 排序理由：原对象较成熟，多状态协同有价值，首批整理。
- Grok意见处理：部分采纳。不采纳缺步进和pgood判据：完整原文已有；采纳要求行为可检查，建设集中边界与评分。
- 对应历史条目：`buckconvertercontrollermacro`。

### U19-T1

采样边沿前后时间裕量的因果观测。P1，建设成本H，补行为边界。

- 可复用：采样附近数据边沿、600ps观察窗和资格接口。
- 需要改：定义可因果报告的窗关闭时刻、前后裕量单位、双侧均有沿及窗重叠；提供轨迹真值，不称完整眼图/BER。
- 排序理由：测量职责有价值，先完成时序观测合同，第二批推进。
- Grok意见处理：采纳缺口。采纳缺可判定裕量公式；还需解决要求采样即valid却观察未来late沿、early/late强互斥的问题。
- 对应历史条目：`cdreyemonitor`。

### U20-I1

失配CDAC权重辨识与校正路径集成。P2，建设成本H，新增对象或真值。

- 可复用：码累加、饱和及校正输出接口，corr_lsb作为旧编码素材。
- 需要改：提供实际失配CDAC、可控测试模式与校正部件，公开可辨识域，按独立权重真值和留出码评价。
- 排序理由：对象与辨识流程均需新增，后置建设。
- Grok意见处理：部分采纳。corr_lsb已有但符号更新步长未完整；采纳缺口，且仅补步长无法把外部err_in变成真实权重辨识。
- 对应历史条目：`capacitormismatchcalibrationengine`。

### U21-R1

CPPLL反馈方向与重锁定故障诊断。P2，建设成本H，故障核实。

- 可复用：历史cppll故障工程、参考阶跃和实际反馈观测。
- 需要改：先独立复现反馈方向/重锁故障并建立正确参考；公开正常分频约定、捕获域、锁定驻留和误差，不告诉根因。
- 排序理由：未完成故障重现与正常参考，先保留候选并后置。
- Grok意见处理：采纳缺口。采纳正常控制/验收合同不足；公开kp/ki并未唯一给出更新关系。不能把规格错误直接伪装成真实R。
- 对应历史条目：`cpplltrackingreacquiretimer`。

### U22-I1

输出占空比驱动的校正闭环。P1，建设成本H，新增对象或真值。

- 可复用：完整周期仪表、trim码和逐脉冲锁存下降沿延迟。
- 需要改：让仪表测clk_out并驱动下一完整脉冲；提供健康部件与可校正占空比域、饱和未锁及取消/恢复协议。
- 排序理由：已有真实执行器，先建立U15/C331后形成I任务。
- Grok意见处理：部分采纳。不采纳原合同足以表示校正闭环：仪表读输入，trim不改变被测误差；采纳其可复用部件。
- 对应历史条目：`dutycyclecorrector`。

### U23-S1

完整四象限的相位插值模型。P2，建设成本H，补行为边界。

- 可复用：I/Q参考、32级码和象限接口。
- 需要改：补0/90/180/270度相位映射、跨周期编号和动态改码生效；建立独立参考，旧gold不当正确答案。
- 排序理由：多相调度与回绕成本高，后置于单参考延迟代表。
- Grok意见处理：采纳重建。采纳0/2与1/3重复非反相选择做不出四象限；补标签或调一个延迟参数不能解决。
- 对应历史条目：`quadraturephaseinterpolator`。

### U24-I1

稀疏数据边沿驱动的相位恢复闭环。P2，建设成本H，新增对象或真值。

- 可复用：BBPD、滤波码和延迟执行器的部件分工。
- 需要改：用闭合观察窗做因果配对，修正控制方向/误差单位，给健康部件、有限相位域及最大无转换间隔。
- 排序理由：核心因果合同与可达域未闭合，后置。
- Grok意见处理：部分采纳。不采纳原合同已可形成正确CDR：nearest可能需要未来沿，更新方向与延迟执行器还须核对；采纳稀疏边沿职责。
- 对应历史条目：`bangbangcdrloop`。

### U25-T1

LDO负载阶跃与恢复的独立表征。P1，建设成本H，新增对象或真值。

- 可复用：v1 LDO对象接口、负载代理激励和输出/控制观测。
- 需要改：提供健康DUT族与独立动态参考，组织上下阶跃并测跌落/过冲与持续回窗；网表装配由环境提供。
- 排序理由：实际动态对象明确，第二批优先T任务，与C403共建。
- Grok意见处理：部分采纳。采纳LDO来源；案例归C403，T交付独立测量不与S机械合并。原固定80ns脚本和save清单不能直接录取。
- 对应历史条目：`ldoloadsteprecovery`。

### U26-T1

ADPLL变频比与伪锁定的独立验证。P1，建设成本H，新增对象或真值。

- 可复用：ADPLL变比激励、ref/fb/vout/lock观测与多信号关系。
- 需要改：在C278健康对象基础上提供正常/违约族、合法变比和时间预算；独立测分频与持续重锁，拒绝只信lock。
- 排序理由：依赖C278正常参考，第二批系统验证，不能先抄旧TB。
- Grok意见处理：部分采纳。采纳ADPLL合同需明确；评论没有直接审查新T职责，控制律可在供给DUT侧固定，但公开验收关系必须完整。
- 对应历史条目：`adpllratiohoptimer`。

### U27-T1

SAR转换协议与内部观测一致性验证。P1，建设成本H，新增对象或真值。

- 可复用：v1 SAR采样、试位、DAC、比较和done监测接口。
- 需要改：固定完整转换协议与健康对象，说明边沿前后监测值；提供正常/违约轨迹，检查同一样本贯穿试位和结果发布。
- 排序理由：协议验证价值清楚，但健康DUT和负控需作者建设。
- Grok意见处理：采纳缺口。采纳旧SAR合同缺唯一权重/试位细节；保留TB接口而新建独立验证责任，不因与S同源直接合并任务。
- 对应历史条目：`weightedsaradcdacloop`。

### U28-T1

AGC捕获、过载与恢复的独立表征。P1，建设成本H，新增对象或真值。

- 可复用：v1 AGC对象与输入包络、输出、增益观测；v4完整更新可对照。
- 需要改：固定可达/不可达幅度域、持续合格窗和实验预算；独立测捕获、削顶与恢复，不用DUT自报metric当真值。
- 排序理由：可与C348共建健康对象，第二批动态表征。
- Grok意见处理：部分采纳。v1 TB只给意图，采纳需要固定对象合同；C348首选v4已给目标和更新，不能把全族判成缺式子。
- 对应历史条目：`agcreceiverlevelingloop`。

### U29-T1

欠压复位断言与释放资格验证。P1，建设成本H，新增对象或真值。

- 可复用：电源激励、POR接口与四拍释放素材，保留C393修订来源。
- 需要改：固定异步断言/同步释放合同和健康对象，补阈值等号、毛刺可观测宽度；检查停钟、欠压打断及不能永不释放。
- 排序理由：安全协议明确，第二批建设；与C417迟滞合同分开。
- Grok意见处理：部分采纳。v1 TB的Public Behavioral Targets已有约0.62V和约四拍，不采纳完全无阈值拍数；仍需精确定义并解决旧gold同步检查与异步断言不一致。
- 对应历史条目：`poweronresetdetector`。

### U30-R1

SAR完成握手导致结果提前捕获的诊断修复。HOLD，建设成本H，故障核实。

- 可复用：v1 SAR提前RDY的真实buggy/fixed素材及结果接口。
- 需要改：新增按RDY捕获的健康消费者并复现末位影响；公开正常协议和捕获窗口，去掉根因提示但不伪造复杂度。
- 排序理由：仍为条件后备，不计108；先确认消费者失效与修复价值。
- Grok意见处理：部分采纳。采纳SAR代表；R可保留独立职责，但评论没有验证诊断难度，不能据“完整”提升后备。
- 对应历史条目：`sarlogic`。
