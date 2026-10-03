# Verilog-A 资料历史来源

[功能总览](README.md) · [课题组资料](lab/README.md) · [Cadence 模型](cadence/README.md)

本文件集中记录所有整理后文件的来源。功能、端口和使用提示见分类目录。资料仅供课题组内部研究，仓库已设为私有，不对外分发。

## 恢复背景

- 整理日期：2026-10-03。原始恢复包位于本机 `vaEvas/output/veriloga-source-recovery-20261003`；本目录不依赖该路径即可查阅源码与本表。
- 历史来源仓库为 `Arcadia-1/behavioral-veriloga-eval`。从提交 `af6bb188d74762812cde3370f0477046d2476410` 的 v3 导入审计整理出 184 条任务记录，对应 169 个历史路径、33 个用户目录。
- 读取时旧仓库 HEAD 为 `fc1f3b36316b6a988b6b06fad48e47546bce95c5`。后续同编号任务可能已被重写，本表的任务名指历史导入版本。
- 本次从课题组目录恢复 181 个 Verilog-A 源文件候选，对应 124 个历史路径；从两套 Cadence 安装库恢复 344 个 .va 实文件。相同内容合并存放位置，但保留所有原路径；不同源码版本分别保存。
- 实际整理为 106 个课题组文件和 213 个 Cadence 文件版本（171 个 module 名），另附 6 个公共头文件。这是资料文件数量，不是独立功能数量或 benchmark 题数。
- 课题组目录下发现与本次 Cadence 安装文件相同的副本，统一放入 `cadence/`，同时在下表保留课题组工程位置。`lab/` 中与官方文件不同的版本不自动视为原创，也不自动认定为官方派生。
- 历史别名与现存文件按文件名、cell 或 module 对应；当年 1663 个模块、去重后 1097 个模块的原始汇总包尚未找到，因此历史对应仍是来源候选，不能保证与当年导入文件相同。
- 原始设计 testbench、完整工程和仿真结果尚未系统恢复。目录或文件存在证明来源位置，不能独立证明已在设计中验证通过。

## 原始位置约定

- 课题组路径保持服务器绝对路径，分别标明读取使用的 SSH 主机别名 `thu-jin` 或 `thu-sui`。
- Cadence 官方资料指从已安装发行版本提取的源码，不是从 benchmark gold 或手册示例重写。安装根目录如下，模型条目用版本和相对路径定位。
  - IC618Hotfix4：`/home/cadence/ic618/IC618Hotfix4/tools/dfII/samples/artist/`。
  - ICADVM201：`/home/cadence/ICADVM/ICADVM201/tools/dfII/samples/artist/`。
  - 公共头文件：`/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/`。
- 本次只整理 Verilog-A 源码与 include；OA 符号、库元数据、原始符号链接以及 SpectreHDL 非 Verilog-A 文件仍保留在恢复底稿，未混入功能模型目录。

## 逐文件来源

<a id="lab-data_converters-adc12_parallel_code_readout"></a>
### [lab/data_converters/adc12_parallel_code_readout.va](lab/data_converters/adc12_parallel_code_readout.va)

- 课题组工程候选：`/home/zhangm/tsmc40/coursedesign_cyclicADC/ADC12bit_decoder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/ADC12bit_decoder.va`；v3 导入记录：`178-source-cyclic-decoder-12bit`。

<a id="lab-data_converters-adc7_code_readout_guoxy"></a>
### [lab/data_converters/adc7_code_readout_guoxy.va](lab/data_converters/adc7_code_readout_guoxy.va)

- 课题组工程候选：`/home/guoxy/SMIC28/ZDYF/ZDYF_PIPE_YQH/ideal_ADC_OUT_7BITS/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `guoxy/ideal_ADC_OUT_7BITS.va`；v3 导入记录：`194-source-ideal-adc-out-7bits`。

<a id="lab-data_converters-adc7_code_readout_lxy"></a>
### [lab/data_converters/adc7_code_readout_lxy.va](lab/data_converters/adc7_code_readout_lxy.va)

- 课题组工程候选：`/home/lixingyu/UHS_ADC_SUB/TEST_D2A_SINGLE_ADC_7B/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `lixingyu/TEST_D2A_SINGLE_ADC_7B.va`；v3 导入记录：`236-source-single-adc-7b-weighted`。

<a id="lab-data_converters-binary2_to_three_unit_controls"></a>
### [lab/data_converters/binary2_to_three_unit_controls.va](lab/data_converters/binary2_to_three_unit_controls.va)

- 课题组工程候选：`/home/cuiyl/tsmc180/DAC/bin2ther_2b/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `cuiyl/bin2ther_2b.va`；v3 导入记录：`265-source-bin2ther-2b`。

<a id="lab-data_converters-cdac_4bit_ideal"></a>
### [lab/data_converters/cdac_4bit_ideal.va](lab/data_converters/cdac_4bit_ideal.va)

- 课题组工程候选：`/home/wangxy/project_28/wxy_lib/L2_CDAC_4b_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/L2_CDAC_4b_ideal.va`；v3 导入记录：`198-source-l2-cdac-4b-residue`。

<a id="lab-data_converters-cdac_6bit_stage1"></a>
### [lab/data_converters/cdac_6bit_stage1.va](lab/data_converters/cdac_6bit_stage1.va)

- 课题组工程候选：`/home/zhangym/Practice/TSMC28/Project1/PIPE_SAR_CP/cdac_6b_ideal_stage1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangym/cdac_6b_ideal_stage1.va`；v3 导入记录：`241-source-cdac-6b-stage1-up`。

<a id="lab-data_converters-cdac_8bit_bidirectional"></a>
### [lab/data_converters/cdac_8bit_bidirectional.va](lab/data_converters/cdac_8bit_bidirectional.va)

- 课题组工程候选：`/home/caiyizeng25/SMIC28/SAR_200M_8b/SAR_200M_8b/cdac_ideal_bidirect/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/cdac_ideal_bidirect.va`；v3 导入记录：`225-source-cdac-bidirect-residue`。

<a id="lab-data_converters-cdac_8bit_monotonic_down"></a>
### [lab/data_converters/cdac_8bit_monotonic_down.va](lab/data_converters/cdac_8bit_monotonic_down.va)

- 课题组工程候选：`/home/caiyizeng25/SMIC28/SAR_200M_8b/SAR_200M_8b/cdac_ideal_monodown/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/cdac_ideal_monodown.va`；v3 导入记录：`240-source-cdac-monodown-7b`。

<a id="lab-data_converters-cyclic_adc_serial_decoder"></a>
### [lab/data_converters/cyclic_adc_serial_decoder.va](lab/data_converters/cyclic_adc_serial_decoder.va)

- 课题组工程候选：`/home/zhangm/tsmc40/coursedesign_cyclicADC/cyclic_decoder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/cyclic_decoder.va`；v3 导入记录：`193-source-cyclic-decoder-10b`。

<a id="lab-data_converters-dac4_clocked_midpoint"></a>
### [lab/data_converters/dac4_clocked_midpoint.va](lab/data_converters/dac4_clocked_midpoint.va)

- 课题组工程候选：`/home/wangxy/smic28/z_2025_TISAR/DAC_4b/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/DAC_4b.va`；v3 导入记录：`125-source-clocked-dac-4b-binary`。

<a id="lab-data_converters-dac4_ready_bipolar"></a>
### [lab/data_converters/dac4_ready_bipolar.va](lab/data_converters/dac4_ready_bipolar.va)

- 课题组工程候选：`/home/wangxy/project_28/wxy_lib/L1_DAC_4b_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/L1_DAC_4b_ideal.va`；v3 导入记录：`197-source-l1-dac-4b-bipolar`。

<a id="lab-data_converters-dac4_restore_midpoint"></a>
### [lab/data_converters/dac4_restore_midpoint.va](lab/data_converters/dac4_restore_midpoint.va)

- 课题组工程候选：`/home/wangxy/project_28/z_bhw_pipeSAR2025/DAC_restore_4bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/DAC_restore_4bit.va`；v3 导入记录：`113-source-clocked-dac-restore-4b`、`249-source-dac-restore-4bit-clocked`。

<a id="lab-data_converters-dac4_weighted_ready"></a>
### [lab/data_converters/dac4_weighted_ready.va](lab/data_converters/dac4_weighted_ready.va)

- 课题组工程候选：`/home/yueyh/tsmc40/pipe_sar/L2_CDAC_4bit_swi/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `yueyh/L2_CDAC_4bit_swi.va`；v3 导入记录：`239-source-l2-cdac-4b-switch`。

<a id="lab-data_converters-dac6_differential_calc"></a>
### [lab/data_converters/dac6_differential_calc.va](lab/data_converters/dac6_differential_calc.va)

- 课题组工程候选：`/home/zhangm/tsmc40/PLL_study_va/DAC_CALC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/DAC_5V.va`；v3 导入记录：`185-source-dac-5v-weighted-7b`。

<a id="lab-data_converters-dac6_differential_calc_convdelay"></a>
### [lab/data_converters/dac6_differential_calc_convdelay.va](lab/data_converters/dac6_differential_calc_convdelay.va)

- 课题组工程候选：`/home/zhangm/backup110/rraminterface/DAC_CALC_VA/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/DAC_CALC_VA.va`；v3 导入记录：`182-source-differential-dac-calc-6b`。

<a id="lab-data_converters-dac6_restore_midpoint"></a>
### [lab/data_converters/dac6_restore_midpoint.va](lab/data_converters/dac6_restore_midpoint.va)

- 课题组工程候选：`/home/wangxy/project_180/z_2025_PipelindSAR/L1_DAC_restore_6bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/L1_DAC_restore_6bit.va`；v3 导入记录：`251-source-dac-restore-6bit-1p8`。

<a id="lab-data_converters-dac6_weighted_ready"></a>
### [lab/data_converters/dac6_weighted_ready.va](lab/data_converters/dac6_weighted_ready.va)

- 课题组工程候选：`/home/zhangym/Practice/TSMC28/Project1/PIPE_SAR_CP/_va_6b_dac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangym/_va_6b_dac.va`；v3 导入记录：`246-source-va-dac-6b-se`。

<a id="lab-data_converters-dac7_restore_midpoint"></a>
### [lab/data_converters/dac7_restore_midpoint.va](lab/data_converters/dac7_restore_midpoint.va)

- 课题组工程候选：`/home/wangxy/project_28/z_bhw_pipeSAR2025/DAC_restore_7bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/DAC_restore_7bit.va`；v3 导入记录：`118-source-clocked-dac-restore-7b`、`250-source-dac-restore-7bit-clocked`。

<a id="lab-data_converters-dac7_single_ended_5v"></a>
### [lab/data_converters/dac7_single_ended_5v.va](lab/data_converters/dac7_single_ended_5v.va)

- 课题组工程候选：`/home/zhangm/tsmc40/PLL_study_va/DAC_5V/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/DAC_5V.va`；v3 导入记录：`185-source-dac-5v-weighted-7b`。

<a id="lab-data_converters-dac7_weighted_ready"></a>
### [lab/data_converters/dac7_weighted_ready.va](lab/data_converters/dac7_weighted_ready.va)

- 课题组工程候选：`/home/yueyh/tsmc28n/10b_200M_pipesar/L2_7B_DAC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `yueyh/L2_7B_DAC.va`；v3 导入记录：`238-source-l2-7b-dac-ready`。

<a id="lab-data_converters-dac_4bit_bipolar_20mv"></a>
### [lab/data_converters/dac_4bit_bipolar_20mv.va](lab/data_converters/dac_4bit_bipolar_20mv.va)

- 课题组工程候选：`/home/shigao/SMIC28/10G_4BIT_SUBADC.SVM/DAC4bit_1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/DAC4bit_1.va`；v3 导入记录：`117-source-bipolar-dac-4b-continuous`、`256-source-dac4bit-small-swing`。

<a id="lab-data_converters-dac_4bit_bipolar_98mv"></a>
### [lab/data_converters/dac_4bit_bipolar_98mv.va](lab/data_converters/dac_4bit_bipolar_98mv.va)

- 课题组工程候选：`/home/chengqidong25/SMIC28/ADC10G4BIT/10G_4BIT_SUBADC/DAC4bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `chengqidong25/DAC4bit.va`；v3 导入记录：`264-source-dac4bit-bipolar-252m`。

<a id="lab-data_converters-dac_4bit_weighted_signed"></a>
### [lab/data_converters/dac_4bit_weighted_signed.va](lab/data_converters/dac_4bit_weighted_signed.va)

- 课题组工程候选：`/home/caiyizeng25/SMIC28/ZhiCun/ZhiCun/dac_ideal_4b/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/dac_ideal_4b.va`；v3 导入记录：`200-source-dac-ideal-4b-offset`。

<a id="lab-data_converters-dac_6bit_decoder"></a>
### [lab/data_converters/dac_6bit_decoder.va](lab/data_converters/dac_6bit_decoder.va)

- 课题组工程候选：`/home/lis/TSMC28/two_stage_pipesar/DEC_6bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `lis/DEC_6bit.va`；v3 导入记录：`274-source-weighted-decoder-6bit`。

<a id="lab-data_converters-differential_clocked_quantizer"></a>
### [lab/data_converters/differential_clocked_quantizer.va](lab/data_converters/differential_clocked_quantizer.va)

- 课题组工程候选：`/home/zhangsh/VerilogA/QTZ/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangsh/QTZ.va`；v3 导入记录：`237-source-qtz-differential-2level`。

<a id="lab-data_converters-flash8_clocked_count_readout"></a>
### [lab/data_converters/flash8_clocked_count_readout.va](lab/data_converters/flash8_clocked_count_readout.va)

- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022/FLASH_SUM8_DELAY/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022_NOV/FLASH_SUM8_DELAY/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/adc_data_cadence/PIPE_SAR_1P3G_2022_NOV/FLASH_SUM8_DELAY/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/FLASH_SUM8_DELAY.va`；v3 导入记录：`180-source-flash-sum8-fraction`。

<a id="lab-data_converters-flash_adc_31level"></a>
### [lab/data_converters/flash_adc_31level.va](lab/data_converters/flash_adc_31level.va)

- 课题组工程候选：`/home/zhangsh/VerilogA/ADC_31LEVEL/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangsh/ADC_31LEVEL.va`；v3 导入记录：`183-source-flash-adc-threshold-taps`。

<a id="lab-data_converters-ideal_adc_vfs_thresholds"></a>
### [lab/data_converters/ideal_adc_vfs_thresholds.va](lab/data_converters/ideal_adc_vfs_thresholds.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_INH_APF_CTP/IDEAL_ADC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/IDEAL_ADC.va`；v3 导入记录：`167-source-ideal-adc-4bit-quantizer`。

<a id="lab-data_converters-ideal_adc_vref_thresholds"></a>
### [lab/data_converters/ideal_adc_vref_thresholds.va](lab/data_converters/ideal_adc_vref_thresholds.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2025_CTP_1P2G_70dB/IDEAL_ADC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/IDEAL_ADC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/IDEAL_ADC/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/IDEAL_ADC.va`；v3 导入记录：`167-source-ideal-adc-4bit-quantizer`。

<a id="lab-data_converters-ideal_dac_numeric_differential"></a>
### [lab/data_converters/ideal_dac_numeric_differential.va](lab/data_converters/ideal_dac_numeric_differential.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/IDEAL_DAC_V/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/IDEAL_DAC_V/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/IDEAL_DAC_V.va`；v3 导入记录：`168-source-ideal-dac-4bit-differential`。

<a id="lab-data_converters-pipeline_code_restore_10bit_redundant"></a>
### [lab/data_converters/pipeline_code_restore_10bit_redundant.va](lab/data_converters/pipeline_code_restore_10bit_redundant.va)

- 课题组工程候选：`/home/wangxy/project_28/z_bhw_pipeSAR2025/DAC_restore_10bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/DAC_restore_10bit.va`；v3 导入记录：`190-source-dac-restore-10bit-offset`。

<a id="lab-data_converters-redundant_code_readout_2b"></a>
### [lab/data_converters/redundant_code_readout_2b.va](lab/data_converters/redundant_code_readout_2b.va)

- 课题组工程候选：`/home/shigao/TSMC28/Ran_channel/RanChannel/V_DECODER_2B/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/V_DECODER_2B.va`；v3 导入记录：`173-source-weighted-sar-decoder-9b`。

<a id="lab-data_converters-redundant_code_readout_7b5"></a>
### [lab/data_converters/redundant_code_readout_7b5.va](lab/data_converters/redundant_code_readout_7b5.va)

- 课题组工程候选：`/home/shigao/TSMC28/SAR_10bit/SAR_10bit/V_DECODER_7B5/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/V_DECODER_7B5.va`；v3 导入记录：`209-source-weighted-decoder-7b5`。

<a id="lab-data_converters-sar11_redundant_readout_ldy"></a>
### [lab/data_converters/sar11_redundant_readout_ldy.va](lab/data_converters/sar11_redundant_readout_ldy.va)

- 课题组工程候选：`/home/liudongyang/3G_Pipe/TB_SAR_SUM/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `liudongyang/TB_SAR_SUM.va`；v3 导入记录：`206-source-sar-sum-weighted-11b`。

<a id="lab-data_converters-sar11_redundant_readout_shigao"></a>
### [lab/data_converters/sar11_redundant_readout_shigao.va](lab/data_converters/sar11_redundant_readout_shigao.va)

- 课题组工程候选：`/home/shigao/TSMC28/2025_TI_SAR_reproduct/2025_TI_SAR_reproduct/V_SAR_sum/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/V_SAR_sum.va`；v3 导入记录：`127-source-sar-weighted-sum`。

<a id="lab-data_converters-sar13_serial_decoder"></a>
### [lab/data_converters/sar13_serial_decoder.va](lab/data_converters/sar13_serial_decoder.va)

- 课题组工程候选：`/home/zhangm/tsmc40/NC_SPLIT_PIPELINE/SAR_13bit_decoder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/SAR_13bit_decoder.va`；v3 导入记录：`261-source-sar-13bit-serial-decoder`。

<a id="lab-data_converters-sar4_code_readout"></a>
### [lab/data_converters/sar4_code_readout.va](lab/data_converters/sar4_code_readout.va)

- 课题组工程候选：`/home/gaoya/tsmc180/ADC_aplira/ADC_LIB/LT_READOUT_SAR4_NEW/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/gaoya/tsmc180ms/APLIRA/APLIRA/LT_READOUT_SAR4_NEW/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `gaoya/LT_READOUT_SAR4_NEW.va`；v3 导入记录：`254-source-lt-readout-sar4`。

<a id="lab-data_converters-sar4_signed_weighted_readout"></a>
### [lab/data_converters/sar4_signed_weighted_readout.va](lab/data_converters/sar4_signed_weighted_readout.va)

- 课题组工程候选：`/home/liaoyuhui/tsmc180/SAR_LYH/_tool_4bit_sar/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `liaoyuhui/_tool_4bit_sar.va`；v3 导入记录：`255-source-tool-4bit-sar-signed-dac`。

<a id="lab-data_converters-sar5_serial_decoder"></a>
### [lab/data_converters/sar5_serial_decoder.va](lab/data_converters/sar5_serial_decoder.va)

- 课题组工程候选：`/home/zhangm/tsmc40/NC_SPLIT_PIPELINE/SAR_5bit_decoder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/SAR_5bit_decoder.va`；v3 导入记录：`177-source-sar-5bit-serial-decoder`。

<a id="lab-data_converters-sar6_serial_decoder"></a>
### [lab/data_converters/sar6_serial_decoder.va](lab/data_converters/sar6_serial_decoder.va)

- 课题组工程候选：`/home/zhangm/tsmc40/NC_SPLIT_PIPELINE/SAR_6bit_decoder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/SAR_5bit_decoder.va`；v3 导入记录：`177-source-sar-5bit-serial-decoder`。

<a id="lab-data_converters-thermometer8_to_binary4"></a>
### [lab/data_converters/thermometer8_to_binary4.va](lab/data_converters/thermometer8_to_binary4.va)

- 课题组工程候选：`/home/liudongyang/3G_Pipe/tb_therm8_to_bin4/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `liudongyang/tb_therm8_to_bin4.va`；v3 导入记录：`270-source-therm8-to-bin4-count`。

<a id="lab-comparators-clocked_comparator_offset_noise"></a>
### [lab/comparators/clocked_comparator_offset_noise.va](lab/comparators/clocked_comparator_offset_noise.va)

- 课题组工程候选：`/home/jielu/DB180/NEXAFE/NEXDSM/L2_comp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `jielu/L2_comp.va`；v3 导入记录：`126-source-latched-comparator-delay`。

<a id="lab-comparators-clocked_comparator_reset_high"></a>
### [lab/comparators/clocked_comparator_reset_high.va](lab/comparators/clocked_comparator_reset_high.va)

- 课题组工程候选：`/home/caiyizeng25/SMIC28/SAR_1G_8b/SAR_1G_8b/L2_CMP_Ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/L2_CMP_Ideal.va`；v3 导入记录：`202-source-l2-cmp-ideal-clocked`。

<a id="lab-comparators-clocked_comparator_reset_low"></a>
### [lab/comparators/clocked_comparator_reset_low.va](lab/comparators/clocked_comparator_reset_low.va)

- 课题组工程候选：`/home/caiyizeng25/SMIC28/SAR_200M_8b/SAR_200M_8b/comp_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/comp_ideal.va`；v3 导入记录：`116-source-clocked-comparator-reset-low`、`263-source-clocked-comparator-dual-output`。

<a id="lab-calibration_control-comparator_offset_search_adaptive"></a>
### [lab/calibration_control/comparator_offset_search_adaptive.va](lab/calibration_control/comparator_offset_search_adaptive.va)

- 课题组工程候选：`/home/caiyizeng25/TSMC28/SAR_Learn25/GMY_PSAR2023_local/V_comp_offset/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/V_comp_offset.va`；v3 导入记录：`122-source-offset-search-comparator`。

<a id="lab-calibration_control-comparator_offset_search_cm0p9v"></a>
### [lab/calibration_control/comparator_offset_search_cm0p9v.va](lab/calibration_control/comparator_offset_search_cm0p9v.va)

- 课题组工程候选：`/home/wangxy/project_28/wxy_lib/L2_comparator_4b_offset/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/L2_comparator_4b_offset.va`；v3 导入记录：`203-source-comparator-offset-driver`。

<a id="lab-calibration_control-comparator_offset_search_enabled"></a>
### [lab/calibration_control/comparator_offset_search_enabled.va](lab/calibration_control/comparator_offset_search_enabled.va)

- 课题组工程候选：`/home/shigao/SMIC28/10G_4BIT_SUBADC/V_comparator_offset/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/V_comparator_offset.va`；v3 导入记录：`123-source-start-gated-offset-search`。

<a id="lab-calibration_control-comparator_offset_search_halving"></a>
### [lab/calibration_control/comparator_offset_search_halving.va](lab/calibration_control/comparator_offset_search_halving.va)

- 课题组工程候选：`/home/guoxy/SMIC28/ZDYF/ZDYF_PIPE_YQH/ideal_COMP_OS_DETECT/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `guoxy/ideal_COMP_OS_DETECT.va`；v3 导入记录：`124-source-comp-os-detect`。

<a id="lab-calibration_control-comparator_offset_search_zhangym"></a>
### [lab/calibration_control/comparator_offset_search_zhangym.va](lab/calibration_control/comparator_offset_search_zhangym.va)

- 课题组工程候选：`/home/zhangym/Practice/TSMC28/Project1/sar_learn/_va_offset/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangym/_va_offset.va`；v3 导入记录：`247-source-offset-halving-search`。

<a id="lab-calibration_control-comparator_rdac_calibration_sweep"></a>
### [lab/calibration_control/comparator_rdac_calibration_sweep.va](lab/calibration_control/comparator_rdac_calibration_sweep.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/VA_comparator_offset_calib_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/VA_comparator_offset_calib_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/VA_comparator_offset_calib_rdac.va`；v3 导入记录：`219-source-offset-rdac-search-flow`。

<a id="lab-calibration_control-comparator_rdac_linearity_scan"></a>
### [lab/calibration_control/comparator_rdac_linearity_scan.va](lab/calibration_control/comparator_rdac_linearity_scan.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/VA_comparator_offset_calib_linearity_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/VA_comparator_offset_calib_linearity_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/VA_comparator_offset_calib_linearity_rdac.va`；v3 导入记录：`228-source-linearity-rdac-offset-sweep`。

<a id="lab-calibration_control-comparator_sar_search"></a>
### [lab/calibration_control/comparator_sar_search.va](lab/calibration_control/comparator_sar_search.va)

- 课题组工程候选：`/home/dmanager/shared_lib/common/exchange/_tool_iSAR/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `dmanager/_tool_iSAR.va`；v3 导入记录：`207-source-iterative-isar-dac`。

<a id="lab-calibration_control-foreground_comparator_cload_calibration"></a>
### [lab/calibration_control/foreground_comparator_cload_calibration.va](lab/calibration_control/foreground_comparator_cload_calibration.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/VA_calib_foreground_cload/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/VA_calib_foreground_cload/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/VA_calib_foreground_cload.va`；v3 导入记录：`214-source-foreground-cload-calibrator`。

<a id="lab-calibration_control-foreground_comparator_rdac_calibration"></a>
### [lab/calibration_control/foreground_comparator_rdac_calibration.va](lab/calibration_control/foreground_comparator_rdac_calibration.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/VA_calib_foreground_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/VA_calib_foreground_rdac/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/VA_calib_foreground_rdac.va`；v3 导入记录：`218-source-foreground-rdac-calibrator`。

<a id="lab-calibration_control-pipeline_adc_gain_calibration_flat_view"></a>
### [lab/calibration_control/pipeline_adc_gain_calibration_flat_view.va](lab/calibration_control/pipeline_adc_gain_calibration_flat_view.va)

- 课题组工程候选：`/home/lixingyu/UHS_ADC_SUB/TEST_D2A_PIPE_ADC_GAIN_CAL/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `lixingyu/TEST_D2A_PIPE_ADC_GAIN_CAL.va`；v3 导入记录：`232-source-pipe-adc-gain-control-loop`。

<a id="lab-calibration_control-pipeline_adc_gain_calibration_nested_view"></a>
### [lab/calibration_control/pipeline_adc_gain_calibration_nested_view.va](lab/calibration_control/pipeline_adc_gain_calibration_nested_view.va)

- 课题组工程候选：`/home/lixingyu/UHS_ADC_SUB/TEST_D2A_PIPE_ADC_GAIN_CAL/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `lixingyu/TEST_D2A_PIPE_ADC_GAIN_CAL.va`；v3 导入记录：`232-source-pipe-adc-gain-control-loop`。

<a id="lab-calibration_control-sar_logic_4bit"></a>
### [lab/calibration_control/sar_logic_4bit.va](lab/calibration_control/sar_logic_4bit.va)

- 课题组工程候选：`/home/yueyh/tsmc40/pipe_sar/L2_4bit_sar_logic/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `yueyh/L2_4bit_sar_logic.va`；v3 导入记录：`234-source-l2-sar-logic-4b`。

<a id="lab-calibration_control-sar_logic_7bit"></a>
### [lab/calibration_control/sar_logic_7bit.va](lab/calibration_control/sar_logic_7bit.va)

- 课题组工程候选：`/home/yueyh/tsmc40/pipe_sar/L2_7bit_sar_logic/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `yueyh/L2_7bit_sar_logic.va`；v3 导入记录：`243-source-l2-sar-logic-7b`。

<a id="lab-calibration_control-trim_code_4bit"></a>
### [lab/calibration_control/trim_code_4bit.va](lab/calibration_control/trim_code_4bit.va)

- 课题组工程候选：`/home/guoxy/SMIC28/ZDYF/ZDYF_PIPE_YQH/ideal_TRIM_CTRL_4BITS/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `guoxy/ideal_TRIM_CTRL_4BITS.va`；v3 导入记录：`227-source-trim-ctrl-4bit`。

<a id="lab-calibration_control-trim_code_4bit_cal4bit"></a>
### [lab/calibration_control/trim_code_4bit_cal4bit.va](lab/calibration_control/trim_code_4bit_cal4bit.va)

- 课题组工程候选：`/home/chengqidong25/SMIC28/ADC10G4BIT/10G_4BIT_SUBADC/CAL4bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `chengqidong25/CAL4bit.va`；v3 导入记录：`296-source-cal4bit-modulo`。

<a id="lab-calibration_control-trim_code_5bit"></a>
### [lab/calibration_control/trim_code_5bit.va](lab/calibration_control/trim_code_5bit.va)

- 课题组工程候选：`/home/guoxy/SMIC28/ZDYF/ZDYF_PIPE_YQH/ideal_TRIM_CTRL_5BITS/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `guoxy/ideal_TRIM_CTRL_5BITS.va`；v3 导入记录：`269-source-trim-ctrl-5bit`。

<a id="lab-clock_sampling-bus11_edge_sampler_csv"></a>
### [lab/clock_sampling/bus11_edge_sampler_csv.va](lab/clock_sampling/bus11_edge_sampler_csv.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021/2021_ZOOM_NSSAR/SINGLE_EDGE_SAMPLER/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/SINGLE_EDGE_SAMPLER.va`；v3 导入记录：`175-source-four-channel-edge-sampler`。

<a id="lab-clock_sampling-clocked_mux_8channel"></a>
### [lab/clock_sampling/clocked_mux_8channel.va](lab/clock_sampling/clocked_mux_8channel.va)

- 课题组工程候选：`/home/wangxy/smic28/z_2025_TISAR/DAC_4bit_restore_8channel/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangxy/DAC_4bit_restore_8channel.va`；v3 导入记录：`199-source-ideal-clkmux-8channel`。

<a id="lab-clock_sampling-flash_code_pipeline_alignment"></a>
### [lab/clock_sampling/flash_code_pipeline_alignment.va](lab/clock_sampling/flash_code_pipeline_alignment.va)

- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022/FLASH_DATA_ALIGN_V2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022_NOV/FLASH_DATA_ALIGN_V2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/adc_data_cadence/PIPE_SAR_1P3G_2022_NOV/FLASH_DATA_ALIGN_V2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/FLASH_DATA_ALIGN_V2.va`；v3 导入记录：`192-source-flash-data-align-pipeline`。

<a id="lab-clock_sampling-mux4_falling_edge"></a>
### [lab/clock_sampling/mux4_falling_edge.va](lab/clock_sampling/mux4_falling_edge.va)

- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022/MUX4T1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/PIPE_SAR_1P3G_2022_NOV/MUX4T1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhangm/tsmc28/adc_data_cadence/PIPE_SAR_1P3G_2022_NOV/MUX4T1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/MUX4T1.va`；v3 导入记录：`170-source-clocked-four-input-mux`、`216-source-clocked-mux4-sampler`。

<a id="lab-clock_sampling-one_shot_lab_copy"></a>
### [lab/clock_sampling/one_shot_lab_copy.va](lab/clock_sampling/one_shot_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/single_shot/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/single_shot/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/single_shot.va`；v3 导入记录：`115-source-single-shot-pulse`、`262-source-single-shot-timer-pulse`。

<a id="lab-clock_sampling-pfd_upbar_down"></a>
### [lab/clock_sampling/pfd_upbar_down.va](lab/clock_sampling/pfd_upbar_down.va)

- 课题组工程候选：`/home/zhangym/Practice/TSMC28/Project1/PLL_Term_Project/L2_PFD/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangym/L2_PFD.va`；v3 导入记录：`226-source-pfd-reset-pulse`。

<a id="lab-clock_sampling-pfd_with_reset_pulse"></a>
### [lab/clock_sampling/pfd_with_reset_pulse.va](lab/clock_sampling/pfd_with_reset_pulse.va)

- 课题组工程候选：`/home/zhangsh/VerilogA/PFD/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangsh/PFD.va`；v3 导入记录：`231-source-pfd-tdomain-reset-window`。

<a id="lab-clock_sampling-pll_delay_path_mux"></a>
### [lab/clock_sampling/pll_delay_path_mux.va](lab/clock_sampling/pll_delay_path_mux.va)

- 课题组工程候选：`/home/zhaoty/pll/PLL/MUX4/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoty/MUX4.va`；v3 导入记录：`297-source-mux4-priority`。

<a id="lab-clock_sampling-sample_hold_lab_copy"></a>
### [lab/clock_sampling/sample_hold_lab_copy.va](lab/clock_sampling/sample_hold_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/sah_ideal/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/sah_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/sah_ideal.va`；v3 导入记录：`114-source-sample-and-hold-ideal`、`252-source-sample-hold-5v-clock`。

<a id="lab-clock_sampling-two_channel_interleaved_alignment"></a>
### [lab/clock_sampling/two_channel_interleaved_alignment.va](lab/clock_sampling/two_channel_interleaved_alignment.va)

- 课题组工程候选：`/home/guoxy/SMIC28/ZDYF/ZDYF_PIPE_YQH/ideal_PIPE_10B_TI_ALIGN/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `guoxy/ideal_PIPE_10B_TI_ALIGN.va`；v3 导入记录：`204-source-pipe-2lane-edge-align`。

<a id="lab-clock_sampling-voltage_programmed_clock_divider"></a>
### [lab/clock_sampling/voltage_programmed_clock_divider.va](lab/clock_sampling/voltage_programmed_clock_divider.va)

- 课题组工程候选：`/home/zhangm/tsmc40/PLL_study_va/divider/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/divider.va`；v3 导入记录：`281-source-programmable-divider-by-n`。

<a id="lab-clock_sampling-zoom_sampling_clock_1600ns"></a>
### [lab/clock_sampling/zoom_sampling_clock_1600ns.va](lab/clock_sampling/zoom_sampling_clock_1600ns.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021/2021_ZOOM_NSSAR/CLOCK_VA_SAMPLE_1600n/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/CLOCK_VA_SAMPLE_1600n.va`；v3 导入记录：`233-source-clock-sample-1600n-sequencer`。

<a id="lab-clock_sampling-zoom_sampling_clock_1800ns"></a>
### [lab/clock_sampling/zoom_sampling_clock_1800ns.va](lab/clock_sampling/zoom_sampling_clock_1800ns.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021/2021_ZOOM_NSSAR/CLOCK_VA_SAMPLE_1800n/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/CLOCK_VA_SAMPLE_1800n.va`；v3 导入记录：`223-source-adc-sample-clock-sequencer`。

<a id="lab-clock_sampling-zoom_sar_multiphase_clock"></a>
### [lab/clock_sampling/zoom_sar_multiphase_clock.va](lab/clock_sampling/zoom_sar_multiphase_clock.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021/2021_ZOOM_NSSAR/CLOCK_VA/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/CLOCK_VA.va`；v3 导入记录：`242-source-adc-zoom-timing-sequencer`。

<a id="lab-logic-and2"></a>
### [lab/logic/and2.va](lab/logic/and2.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021_28nm/verilogaLib/and2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/and2.va`；v3 导入记录：`128-source-two-input-and-gate`。

<a id="lab-logic-and3"></a>
### [lab/logic/and3.va](lab/logic/and3.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/cyclicADC/and3/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/and3.va`；v3 导入记录：`139-source-three-input-and-gate`。

<a id="lab-logic-cyclic_adc_decision_logic"></a>
### [lab/logic/cyclic_adc_decision_logic.va](lab/logic/cyclic_adc_decision_logic.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/cyclicADC/digital_logic1/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/digital_logic1.va`；v3 导入记录：`278-source-decision-router-logic`。

<a id="lab-logic-dff_0_to_5v"></a>
### [lab/logic/dff_0_to_5v.va](lab/logic/dff_0_to_5v.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/d_ff/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/d_ff.va`；v3 导入记录：`299-source-bipolar-dff-sample`。

<a id="lab-logic-dff_async_set_reset_jitter"></a>
### [lab/logic/dff_async_set_reset_jitter.va](lab/logic/dff_async_set_reset_jitter.va)

- 课题组工程候选：`/home/zhangm/TED/ted-release/ted/tools/verilog/behaviorLib/DFFRSHQ/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/DFFRSHQ.va`；v3 导入记录：`221-source-dff-set-reset-hold`。

<a id="lab-logic-dff_minus5_to_5v"></a>
### [lab/logic/dff_minus5_to_5v.va](lab/logic/dff_minus5_to_5v.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/d_ff/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/d_ff.va`；v3 导入记录：`299-source-bipolar-dff-sample`。

<a id="lab-logic-dff_reset_both_outputs_low"></a>
### [lab/logic/dff_reset_both_outputs_low.va](lab/logic/dff_reset_both_outputs_low.va)

- 课题组工程候选：`/home/hexy/tsmc40/SAR_noise_reduction/dff_rst/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `hexy/dff_rst.va`；v3 导入记录：`121-source-dff-reset-voltage`。

<a id="lab-logic-dff_set_reset_supply_referenced"></a>
### [lab/logic/dff_set_reset_supply_referenced.va](lab/logic/dff_set_reset_supply_referenced.va)

- 课题组工程候选：`/home/gaoya/tsmc180/ADC_aplira/ADC_LIB/L4_DFF_VA/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/gaoya/tsmc180ms/APLIRA/APLIRA/L4_DFF_VA/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `gaoya/L4_DFF_VA.va`；v3 导入记录：`266-source-dff-set-reset`。

<a id="lab-logic-mod6_counter_onehot"></a>
### [lab/logic/mod6_counter_onehot.va](lab/logic/mod6_counter_onehot.va)

- 课题组工程候选：`/home/caiyizeng25/TSMC28/SAR_Learn25/GMY_PSAR2023_local/V_counter/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `caiyizeng25/V_counter.va`；v3 导入记录：`224-source-pipeline-counter-onehot`。

<a id="lab-logic-nand2"></a>
### [lab/logic/nand2.va](lab/logic/nand2.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021_28nm/verilogaLib/nand2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/nand2.va`；v3 导入记录：`137-source-two-input-nand-gate`。

<a id="lab-logic-nor2"></a>
### [lab/logic/nor2.va](lab/logic/nor2.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021_28nm/verilogaLib/nor2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/nor2.va`；v3 导入记录：`138-source-two-input-nor-gate`。

<a id="lab-logic-or2"></a>
### [lab/logic/or2.va](lab/logic/or2.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021_28nm/verilogaLib/or2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/or2.va`；v3 导入记录：`135-source-two-input-or-gate`。

<a id="lab-logic-or3"></a>
### [lab/logic/or3.va](lab/logic/or3.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/cyclicADC/or3/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/or3.va`；v3 导入记录：`140-source-three-input-or-gate`。

<a id="lab-logic-rs_latch_lab_copy"></a>
### [lab/logic/rs_latch_lab_copy.va](lab/logic/rs_latch_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/rs_ff/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/rs_ff/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/rs_ff.va`；v3 导入记录：`166-source-rs-latch-voltage`。

<a id="lab-logic-toggle_ff_lab_copy"></a>
### [lab/logic/toggle_ff_lab_copy.va](lab/logic/toggle_ff_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/t_ff/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/t_ff/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/t_ff.va`；v3 导入记录：`210-source-toggle-flip-flop`。

<a id="lab-logic-xor2"></a>
### [lab/logic/xor2.va](lab/logic/xor2.va)

- 课题组工程候选：`/home/tangxy/Documents/Design_2021_28nm/verilogaLib/xor2/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `tangxy/xor2.va`；v3 导入记录：`129-source-two-input-xor-gate`。

<a id="lab-logic-xor3"></a>
### [lab/logic/xor3.va](lab/logic/xor3.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/cyclicADC/xor3/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/xor3.va`；v3 导入记录：`141-source-three-input-xor-gate`。

<a id="lab-analog-analog_mux_lab_copy"></a>
### [lab/analog/analog_mux_lab_copy.va](lab/analog/analog_mux_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/analog_mux/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/analog_mux/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/analog_mux.va`；v3 导入记录：`130-source-analog-mux-threshold`。

<a id="lab-analog-diffamp_clamped_0_to_0p9v"></a>
### [lab/analog/diffamp_clamped_0_to_0p9v.va](lab/analog/diffamp_clamped_0_to_0p9v.va)

- 课题组工程候选：`/home/wangx/tsmc28/2022_SAR/diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/diffamp.va`；v3 导入记录：`156-source-differential-amplifier-core`。

<a id="lab-analog-differential_polynomial_vcvs_high_order_defaults"></a>
### [lab/analog/differential_polynomial_vcvs_high_order_defaults.va](lab/analog/differential_polynomial_vcvs_high_order_defaults.va)

- 课题组工程候选：`/home/cuiyl/tsmc180mixsignal/DS_DAC/LI_VCVS_NLIN/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `cuiyl/LI_VCVS_NLIN.va`；v3 导入记录：`151-source-polynomial-differential-vcvs`。

<a id="lab-analog-differential_polynomial_vcvs_linear_defaults"></a>
### [lab/analog/differential_polynomial_vcvs_linear_defaults.va](lab/analog/differential_polynomial_vcvs_linear_defaults.va)

- 课题组工程候选：`/home/cuiyl/tsmc180/DS_DAC/LI_VCVS_NLIN/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `cuiyl/LI_VCVS_NLIN.va`；v3 导入记录：`151-source-polynomial-differential-vcvs`。

<a id="lab-analog-differential_unity_buffer"></a>
### [lab/analog/differential_unity_buffer.va](lab/analog/differential_unity_buffer.va)

- 课题组工程候选：`/home/liudongyang/3G_Pipe/TOOL_buffer/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `liudongyang/TOOL_buffer.va`；v3 导入记录：`134-source-differential-buffer`。

<a id="lab-analog-supply_headroom_limiter"></a>
### [lab/analog/supply_headroom_limiter.va](lab/analog/supply_headroom_limiter.va)

- 课题组工程候选：`/home/zhangm/TED/ted-release/ted/tools/verilog/behaviorLib/LIMITER/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/LIMITER.va`；v3 导入记录：`147-source-limiter-rails`。

<a id="lab-analog-three_way_analog_mux_lab_copy"></a>
### [lab/analog/three_way_analog_mux_lab_copy.va](lab/analog/three_way_analog_mux_lab_copy.va)

- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/multiplexer/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/multiplexer/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/multiplexer.va`；v3 导入记录：`155-source-three-way-threshold-mux`。

<a id="lab-analog-voltage_ratio_divider_lab_copy"></a>
### [lab/analog/voltage_ratio_divider_lab_copy.va](lab/analog/voltage_ratio_divider_lab_copy.va)

- 课题组工程候选：`/home/zhangm/TED/ted-release/ted/tools/verilog/ahdlLib/divider/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/divider.va`；v3 导入记录：`281-source-programmable-divider-by-n`。

<a id="lab-measurement_stimulus-constant_code_source_7bit"></a>
### [lab/measurement_stimulus/constant_code_source_7bit.va](lab/measurement_stimulus/constant_code_source_7bit.va)

- 课题组工程候选：`/home/shigao/TSMC28/2025_TI_SAR_reproduct/2025_TI_SAR_reproduct/V_ENCODER_7B/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/shigao/TSMC28/SAR_10bit/SAR_10bit/V_ENCODER_7B/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `shigao/V_ENCODER_7B.va`；v3 导入记录：`174-source-control-word-encoder-7b`。

<a id="lab-measurement_stimulus-crossing_pulse_detector_lab_copy"></a>
### [lab/measurement_stimulus/crossing_pulse_detector_lab_copy.va](lab/measurement_stimulus/crossing_pulse_detector_lab_copy.va)

- 课题组工程候选：`/home/zhangm/TED/ted-release/ted/tools/verilog/ahdlLib/crossing_detector/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/crossing_detector.va`；v3 导入记录：`119-source-crossing-pulse-detector`。

<a id="lab-measurement_stimulus-dac7_clocked_code_stimulus"></a>
### [lab/measurement_stimulus/dac7_clocked_code_stimulus.va](lab/measurement_stimulus/dac7_clocked_code_stimulus.va)

- 课题组工程候选：`/home/zhangm/backup110/HV_7BITDAC/DAC7B_TB_VA/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhangm/DAC7B_TB_VA.va`；v3 导入记录：`217-source-dac7-code-generator`。

<a id="lab-measurement_stimulus-differential_edge_time_detector"></a>
### [lab/measurement_stimulus/differential_edge_time_detector.va](lab/measurement_stimulus/differential_edge_time_detector.va)

- 课题组工程候选：`/home/yangqihan/TSMC28/PIPE1/PIPE_ADC1/ideal_TIME_DIFF_DETECTOR/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `yangqihan/ideal_TIME_DIFF_DETECTOR.va`；v3 导入记录：`133-source-time-diff-detector`。

<a id="lab-measurement_stimulus-encoder_thermometer_stimulus"></a>
### [lab/measurement_stimulus/encoder_thermometer_stimulus.va](lab/measurement_stimulus/encoder_thermometer_stimulus.va)

- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2025_CTP_1P2G_70dB/VA_encoder_test/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28NM/CTP_2025_1P2G_70DB/2026_CTP_1P2G_70dB/VA_encoder_test/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组工程候选：`/home/zhaoh/TSMC28n_2025/2025_CTP_1P2G/VA_encoder_test/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoh/VA_encoder_test.va`；v3 导入记录：`212-source-onehot-progress-encoder`。

<a id="lab-measurement_stimulus-flash8_population_readout"></a>
### [lab/measurement_stimulus/flash8_population_readout.va](lab/measurement_stimulus/flash8_population_readout.va)

- 课题组工程候选：`/home/zhaoty/Z_pipeline/TB_flash/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `zhaoty/TB_flash.va`；v3 导入记录：`172-source-flash-thermometer-centered-sum`。

<a id="cadence-data_converters-adc_8bit"></a>
### [cadence/data_converters/adc_8bit.va](cadence/data_converters/adc_8bit.va)

- Cadence `ICADVM201`：`ahdlLib/adc_8bit/veriloga/veriloga.va`（读取主机 `thu-sui`）。
- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/adc_8bit.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`ahdlLib/adc_8bit/veriloga/veriloga.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/adc_8bit.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/adc_8bit/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/adc_8bit/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/adc_8bit.va`；v3 导入记录：`295-source-clocked-adc3bit`。

<a id="cadence-data_converters-adc_8bit_ideal"></a>
### [cadence/data_converters/adc_8bit_ideal.va](cadence/data_converters/adc_8bit_ideal.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/adc_8bit_ideal.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/adc_8bit_ideal.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-dac_8bit"></a>
### [cadence/data_converters/dac_8bit.va](cadence/data_converters/dac_8bit.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/dac_8bit.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/dac_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-dac_8bit_ideal"></a>
### [cadence/data_converters/dac_8bit_ideal.va](cadence/data_converters/dac_8bit_ideal.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/dac_8bit_ideal.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/dac_8bit_ideal.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/dac_8bit_ideal/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/dac_8bit_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/dac_8bit_ideal.va`；v3 导入记录：`191-source-dac-8bit-ideal-scalar`。

<a id="cadence-data_converters-decimator__ic618hotfix4"></a>
### [cadence/data_converters/decimator__ic618hotfix4.va](cadence/data_converters/decimator__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/decimator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-decimator__icadvm201"></a>
### [cadence/data_converters/decimator__icadvm201.va](cadence/data_converters/decimator__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/decimator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-quantizer"></a>
### [cadence/data_converters/quantizer.va](cadence/data_converters/quantizer.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/quantizer.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/quantizer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-sah_ideal__ic618hotfix4"></a>
### [cadence/data_converters/sah_ideal__ic618hotfix4.va](cadence/data_converters/sah_ideal__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/sah_ideal.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-sah_ideal__icadvm201"></a>
### [cadence/data_converters/sah_ideal__icadvm201.va](cadence/data_converters/sah_ideal__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/sah_ideal.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-sigmadelta_1storder__ic618hotfix4"></a>
### [cadence/data_converters/sigmadelta_1storder__ic618hotfix4.va](cadence/data_converters/sigmadelta_1storder__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/sigmadelta_1storder.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-data_converters-sigmadelta_1storder__icadvm201"></a>
### [cadence/data_converters/sigmadelta_1storder__icadvm201.va](cadence/data_converters/sigmadelta_1storder__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/sigmadelta_1storder.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-charge_pump__ic618hotfix4"></a>
### [cadence/clock_pll/charge_pump__ic618hotfix4.va](cadence/clock_pll/charge_pump__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/charge_pump.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-charge_pump__icadvm201"></a>
### [cadence/clock_pll/charge_pump__icadvm201.va](cadence/clock_pll/charge_pump__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/charge_pump.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-dig_pll"></a>
### [cadence/clock_pll/dig_pll.va](cadence/clock_pll/dig_pll.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/dig_pll.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/dig_pll.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-dig_pll_lpf"></a>
### [cadence/clock_pll/dig_pll_lpf.va](cadence/clock_pll/dig_pll_lpf.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/dig_pll_lpf.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/dig_pll_lpf.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-dig_vco__ic618hotfix4"></a>
### [cadence/clock_pll/dig_vco__ic618hotfix4.va](cadence/clock_pll/dig_vco__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/dig_vco.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-dig_vco__icadvm201"></a>
### [cadence/clock_pll/dig_vco__icadvm201.va](cadence/clock_pll/dig_vco__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/dig_vco.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-freq_ph_detector__ic618hotfix4"></a>
### [cadence/clock_pll/freq_ph_detector__ic618hotfix4.va](cadence/clock_pll/freq_ph_detector__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/freq_ph_detector.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-freq_ph_detector__icadvm201"></a>
### [cadence/clock_pll/freq_ph_detector__icadvm201.va](cadence/clock_pll/freq_ph_detector__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/freq_ph_detector.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-phase_detector"></a>
### [cadence/clock_pll/phase_detector.va](cadence/clock_pll/phase_detector.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/phase_detector.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/phase_detector.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/phase_detector/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/phase_detector/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/phase_detector.va`；v3 导入记录：`235-source-phase-detector-chopper`。

<a id="cadence-clock_pll-pll"></a>
### [cadence/clock_pll/pll.va](cadence/clock_pll/pll.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/pll.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/pll.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-single_shot__ic618hotfix4"></a>
### [cadence/clock_pll/single_shot__ic618hotfix4.va](cadence/clock_pll/single_shot__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/single_shot.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-single_shot__icadvm201"></a>
### [cadence/clock_pll/single_shot__icadvm201.va](cadence/clock_pll/single_shot__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/single_shot.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-clock_pll-vco"></a>
### [cadence/clock_pll/vco.va](cadence/clock_pll/vco.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/vco.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/vco.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-and_gate"></a>
### [cadence/logic/and_gate.va](cadence/logic/and_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/and_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/and_gate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-d_ff__ic618hotfix4"></a>
### [cadence/logic/d_ff__ic618hotfix4.va](cadence/logic/d_ff__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/d_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-d_ff__icadvm201"></a>
### [cadence/logic/d_ff__icadvm201.va](cadence/logic/d_ff__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/d_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-full_adder"></a>
### [cadence/logic/full_adder.va](cadence/logic/full_adder.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/full_adder.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/full_adder.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/full_adder/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/full_adder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/full_adder.va`；v3 导入记录：`163-source-full-adder-logic`。

<a id="cadence-logic-full_subtractor"></a>
### [cadence/logic/full_subtractor.va](cadence/logic/full_subtractor.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/full_subtractor.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/full_subtractor.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/full_subtractor/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/full_subtractor/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/full_subtractor.va`；v3 导入记录：`165-source-full-subtractor-logic`。

<a id="cadence-logic-half_adder"></a>
### [cadence/logic/half_adder.va](cadence/logic/half_adder.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/half_adder.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/half_adder.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/half_adder/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/half_adder/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/half_adder.va`；v3 导入记录：`162-source-half-adder-logic`。

<a id="cadence-logic-half_subtractor"></a>
### [cadence/logic/half_subtractor.va](cadence/logic/half_subtractor.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/half_subtractor.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/half_subtractor.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/half_subtractor/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/half_subtractor/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/half_subtractor.va`；v3 导入记录：`164-source-half-subtractor-logic`。

<a id="cadence-logic-jk_clk_ff__ic618hotfix4"></a>
### [cadence/logic/jk_clk_ff__ic618hotfix4.va](cadence/logic/jk_clk_ff__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/jk_clk_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-jk_clk_ff__icadvm201"></a>
### [cadence/logic/jk_clk_ff__icadvm201.va](cadence/logic/jk_clk_ff__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/jk_clk_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-jk_ff__ic618hotfix4"></a>
### [cadence/logic/jk_ff__ic618hotfix4.va](cadence/logic/jk_ff__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/jk_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-jk_ff__icadvm201"></a>
### [cadence/logic/jk_ff__icadvm201.va](cadence/logic/jk_ff__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/jk_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-nand_gate"></a>
### [cadence/logic/nand_gate.va](cadence/logic/nand_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/nand_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/nand_gate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-nor_gate"></a>
### [cadence/logic/nor_gate.va](cadence/logic/nor_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/nor_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/nor_gate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-not_gate"></a>
### [cadence/logic/not_gate.va](cadence/logic/not_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/not_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/not_gate.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/not_gate/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/not_gate/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/not_gate.va`；v3 导入记录：`120-source-not-gate-voltage`。

<a id="cadence-logic-or_gate"></a>
### [cadence/logic/or_gate.va](cadence/logic/or_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/or_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/or_gate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-parallel_reg_8"></a>
### [cadence/logic/parallel_reg_8.va](cadence/logic/parallel_reg_8.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/parallel_reg_8.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/parallel_reg_8.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-rs_ff__ic618hotfix4"></a>
### [cadence/logic/rs_ff__ic618hotfix4.va](cadence/logic/rs_ff__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/rs_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-rs_ff__icadvm201"></a>
### [cadence/logic/rs_ff__icadvm201.va](cadence/logic/rs_ff__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/rs_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-serial_reg_8"></a>
### [cadence/logic/serial_reg_8.va](cadence/logic/serial_reg_8.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/serial_reg_8.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/serial_reg_8.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-t_ff__ic618hotfix4"></a>
### [cadence/logic/t_ff__ic618hotfix4.va](cadence/logic/t_ff__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/t_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-t_ff__icadvm201"></a>
### [cadence/logic/t_ff__icadvm201.va](cadence/logic/t_ff__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/t_ff.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-logic-xnor_gate"></a>
### [cadence/logic/xnor_gate.va](cadence/logic/xnor_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/xnor_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/xnor_gate.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/xnor_gate/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/xnor_gate/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/xnor_gate.va`；v3 导入记录：`298-source-xnor-gate-voltage`。

<a id="cadence-logic-xor_gate"></a>
### [cadence/logic/xor_gate.va](cadence/logic/xor_gate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/logic/xor_gate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/logic/xor_gate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-amp"></a>
### [cadence/analog/amp.va](cadence/analog/amp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/amp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/amp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/amp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/amp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/amp.va`；v3 导入记录：`149-source-offset-gain-amplifier`。

<a id="cadence-analog-analog_mux__ic618hotfix4"></a>
### [cadence/analog/analog_mux__ic618hotfix4.va](cadence/analog/analog_mux__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/analog_mux.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-analog_mux__icadvm201"></a>
### [cadence/analog/analog_mux__icadvm201.va](cadence/analog/analog_mux__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/analog_mux.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-attenuator"></a>
### [cadence/analog/attenuator.va](cadence/analog/attenuator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/attenuator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/attenuator.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/attenuator/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/attenuator/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/attenuator.va`；v3 导入记录：`142-source-attenuator-gain`。

<a id="cadence-analog-comparator"></a>
### [cadence/analog/comparator.va](cadence/analog/comparator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/comparator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/comparator.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/chenr/tsmc40/Delay_DWA_Ideal/comparator_ideal/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/comparator/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/comparator/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `chenr/comparator_ideal.va`；v3 导入记录：`146-source-smooth-comparator-tanh`。
- 历史来源别名 `wangx/comparator.va`；v3 导入记录：`292-source-smooth-tanh-comparator`。

<a id="cadence-analog-controlled_integ__ic618hotfix4"></a>
### [cadence/analog/controlled_integ__ic618hotfix4.va](cadence/analog/controlled_integ__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/controlled_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-controlled_integ__icadvm201"></a>
### [cadence/analog/controlled_integ__icadvm201.va](cadence/analog/controlled_integ__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/controlled_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-current_dba"></a>
### [cadence/analog/current_dba.va](cadence/analog/current_dba.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/current_dba.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/current_dba.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-deadband"></a>
### [cadence/analog/deadband.va](cadence/analog/deadband.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/deadband.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/deadband.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/deadband/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/deadband/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/deadband.va`；v3 导入记录：`143-source-deadband-window`、`289-source-deadband-voltage`。

<a id="cadence-analog-deadband_diffamp"></a>
### [cadence/analog/deadband_diffamp.va](cadence/analog/deadband_diffamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/deadband_diffamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/deadband_diffamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/deadband_diffamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/deadband_diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/deadband_diffamp.va`；v3 导入记录：`144-source-differential-deadband`、`290-source-deadband-diffamp`。

<a id="cadence-analog-diffamp"></a>
### [cadence/analog/diffamp.va](cadence/analog/diffamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/diffamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/diffamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/diffamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/diffamp.va`；v3 导入记录：`156-source-differential-amplifier-core`。

<a id="cadence-analog-diffdriver"></a>
### [cadence/analog/diffdriver.va](cadence/analog/diffdriver.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/diffdriver.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/diffdriver.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/diffdriver/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/diffdriver/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/diffdriver.va`；v3 导入记录：`152-source-differential-gain-driver`。

<a id="cadence-analog-differentiator"></a>
### [cadence/analog/differentiator.va](cadence/analog/differentiator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/differentiator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/differentiator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-flow2val"></a>
### [cadence/analog/flow2val.va](cadence/analog/flow2val.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/flow2val.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/flow2val.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-hard_current_clamp"></a>
### [cadence/analog/hard_current_clamp.va](cadence/analog/hard_current_clamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/hard_current_clamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/hard_current_clamp.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-hard_voltage_clamp"></a>
### [cadence/analog/hard_voltage_clamp.va](cadence/analog/hard_voltage_clamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/hard_voltage_clamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/hard_voltage_clamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/hard_voltage_clamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/hard_voltage_clamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/hard_voltage_clamp.va`；v3 导入记录：`145-source-hard-voltage-clamp`。

<a id="cadence-analog-hysteresis__ic618hotfix4"></a>
### [cadence/analog/hysteresis__ic618hotfix4.va](cadence/analog/hysteresis__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/hysteresis.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-hysteresis__icadvm201"></a>
### [cadence/analog/hysteresis__icadvm201.va](cadence/analog/hysteresis__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/hysteresis.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-integrator"></a>
### [cadence/analog/integrator.va](cadence/analog/integrator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/integrator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/integrator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-level_shifter"></a>
### [cadence/analog/level_shifter.va](cadence/analog/level_shifter.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/level_shifter.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/level_shifter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-limiting_diffamp"></a>
### [cadence/analog/limiting_diffamp.va](cadence/analog/limiting_diffamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/limiting_diffamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/limiting_diffamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/limiting_diffamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/limiting_diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/limiting_diffamp.va`；v3 导入记录：`153-source-limiting-differential-amplifier`、`291-source-limiting-diffamp`。

<a id="cadence-analog-log_amp"></a>
### [cadence/analog/log_amp.va](cadence/analog/log_amp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/log_amp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/log_amp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/log_amp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/log_amp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/log_amp.va`；v3 导入记录：`157-source-logarithmic-amplifier`。

<a id="cadence-analog-lpf_1storder"></a>
### [cadence/analog/lpf_1storder.va](cadence/analog/lpf_1storder.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/lpf_1storder.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/lpf_1storder.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-multiplexer__ic618hotfix4"></a>
### [cadence/analog/multiplexer__ic618hotfix4.va](cadence/analog/multiplexer__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/multiplexer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-multiplexer__icadvm201"></a>
### [cadence/analog/multiplexer__icadvm201.va](cadence/analog/multiplexer__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/multiplexer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-opamp"></a>
### [cadence/analog/opamp.va](cadence/analog/opamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/opamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/opamp.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-repeater__ic618hotfix4"></a>
### [cadence/analog/repeater__ic618hotfix4.va](cadence/analog/repeater__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/repeater.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-repeater__icadvm201"></a>
### [cadence/analog/repeater__icadvm201.va](cadence/analog/repeater__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/repeater.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-saturating_integ__ic618hotfix4"></a>
### [cadence/analog/saturating_integ__ic618hotfix4.va](cadence/analog/saturating_integ__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/saturating_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-saturating_integ__icadvm201"></a>
### [cadence/analog/saturating_integ__icadvm201.va](cadence/analog/saturating_integ__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/saturating_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-soft_current_clamp"></a>
### [cadence/analog/soft_current_clamp.va](cadence/analog/soft_current_clamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/soft_current_clamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/soft_current_clamp.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-soft_voltage_clamp"></a>
### [cadence/analog/soft_voltage_clamp.va](cadence/analog/soft_voltage_clamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/soft_voltage_clamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/soft_voltage_clamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/soft_voltage_clamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/soft_voltage_clamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/soft_voltage_clamp.va`；v3 导入记录：`158-source-soft-voltage-clamp`。

<a id="cadence-analog-switch_cap_integ__ic618hotfix4"></a>
### [cadence/analog/switch_cap_integ__ic618hotfix4.va](cadence/analog/switch_cap_integ__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mixed/switch_cap_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-switch_cap_integ__icadvm201"></a>
### [cadence/analog/switch_cap_integ__icadvm201.va](cadence/analog/switch_cap_integ__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mixed/switch_cap_integ.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-val2flow"></a>
### [cadence/analog/val2flow.va](cadence/analog/val2flow.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/val2flow.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/val2flow.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-analog-vargain_diffamp"></a>
### [cadence/analog/vargain_diffamp.va](cadence/analog/vargain_diffamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/vargain_diffamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/vargain_diffamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/vargain_diffamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/vargain_diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/vargain_diffamp.va`；v3 导入记录：`159-source-variable-gain-differential-amplifier`、`280-source-vargain-diffamp-clip`。

<a id="cadence-analog-vc_vg_diffamp"></a>
### [cadence/analog/vc_vg_diffamp.va](cadence/analog/vc_vg_diffamp.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/vc_vg_diffamp.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/vc_vg_diffamp.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/vc_vg_diffamp/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/vc_vg_diffamp/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/vc_vg_diffamp.va`；v3 导入记录：`160-source-voltage-controlled-gain-amplifier`。

<a id="cadence-analog-voltage_dba"></a>
### [cadence/analog/voltage_dba.va](cadence/analog/voltage_dba.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/voltage_dba.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/voltage_dba.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-adc_dnl_8bit__ic618hotfix4"></a>
### [cadence/measurement_stimulus/adc_dnl_8bit__ic618hotfix4.va](cadence/measurement_stimulus/adc_dnl_8bit__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/adc_dnl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-adc_dnl_8bit__icadvm201"></a>
### [cadence/measurement_stimulus/adc_dnl_8bit__icadvm201.va](cadence/measurement_stimulus/adc_dnl_8bit__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/adc_dnl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-adc_inl_8bit__ic618hotfix4"></a>
### [cadence/measurement_stimulus/adc_inl_8bit__ic618hotfix4.va](cadence/measurement_stimulus/adc_inl_8bit__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/adc_inl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-adc_inl_8bit__icadvm201"></a>
### [cadence/measurement_stimulus/adc_inl_8bit__icadvm201.va](cadence/measurement_stimulus/adc_inl_8bit__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/adc_inl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-ammeter"></a>
### [cadence/measurement_stimulus/ammeter.va](cadence/measurement_stimulus/ammeter.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/ammeter.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/ammeter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-audio_src"></a>
### [cadence/measurement_stimulus/audio_src.va](cadence/measurement_stimulus/audio_src.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/audio_src.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/audio_src.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-bit_error_rate"></a>
### [cadence/measurement_stimulus/bit_error_rate.va](cadence/measurement_stimulus/bit_error_rate.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/bit_error_rate.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/bit_error_rate.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-code_gen_2bit"></a>
### [cadence/measurement_stimulus/code_gen_2bit.va](cadence/measurement_stimulus/code_gen_2bit.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/code_gen_2bit.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/code_gen_2bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-code_gen_4bit"></a>
### [cadence/measurement_stimulus/code_gen_4bit.va](cadence/measurement_stimulus/code_gen_4bit.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/code_gen_4bit.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/code_gen_4bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-crossing_detector__ic618hotfix4"></a>
### [cadence/measurement_stimulus/crossing_detector__ic618hotfix4.va](cadence/measurement_stimulus/crossing_detector__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/crossing_detector.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-crossing_detector__icadvm201"></a>
### [cadence/measurement_stimulus/crossing_detector__icadvm201.va](cadence/measurement_stimulus/crossing_detector__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/crossing_detector.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-dac_dnl_8bit__ic618hotfix4"></a>
### [cadence/measurement_stimulus/dac_dnl_8bit__ic618hotfix4.va](cadence/measurement_stimulus/dac_dnl_8bit__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/dac_dnl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-dac_dnl_8bit__icadvm201"></a>
### [cadence/measurement_stimulus/dac_dnl_8bit__icadvm201.va](cadence/measurement_stimulus/dac_dnl_8bit__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/dac_dnl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-dac_inl_8bit__ic618hotfix4"></a>
### [cadence/measurement_stimulus/dac_inl_8bit__ic618hotfix4.va](cadence/measurement_stimulus/dac_inl_8bit__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/dac_inl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-dac_inl_8bit__icadvm201"></a>
### [cadence/measurement_stimulus/dac_inl_8bit__icadvm201.va](cadence/measurement_stimulus/dac_inl_8bit__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/dac_inl_8bit.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-delta_probe"></a>
### [cadence/measurement_stimulus/delta_probe.va](cadence/measurement_stimulus/delta_probe.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/delta_probe.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/delta_probe.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-find_probe"></a>
### [cadence/measurement_stimulus/find_probe.va](cadence/measurement_stimulus/find_probe.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/find_probe.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/find_probe.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-find_slope"></a>
### [cadence/measurement_stimulus/find_slope.va](cadence/measurement_stimulus/find_slope.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/find_slope.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/find_slope.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-freq_meter__ic618hotfix4"></a>
### [cadence/measurement_stimulus/freq_meter__ic618hotfix4.va](cadence/measurement_stimulus/freq_meter__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/freq_meter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-freq_meter__icadvm201"></a>
### [cadence/measurement_stimulus/freq_meter__icadvm201.va](cadence/measurement_stimulus/freq_meter__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/freq_meter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-noise_src"></a>
### [cadence/measurement_stimulus/noise_src.va](cadence/measurement_stimulus/noise_src.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/noise_src.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/noise_src.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-offset_meas"></a>
### [cadence/measurement_stimulus/offset_meas.va](cadence/measurement_stimulus/offset_meas.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/offset_meas.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/offset_meas.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-power_meter__ic618hotfix4"></a>
### [cadence/measurement_stimulus/power_meter__ic618hotfix4.va](cadence/measurement_stimulus/power_meter__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/power_meter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-power_meter__icadvm201"></a>
### [cadence/measurement_stimulus/power_meter__icadvm201.va](cadence/measurement_stimulus/power_meter__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/power_meter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-qmeter__ic618hotfix4"></a>
### [cadence/measurement_stimulus/qmeter__ic618hotfix4.va](cadence/measurement_stimulus/qmeter__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/qmeter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-qmeter__icadvm201"></a>
### [cadence/measurement_stimulus/qmeter__icadvm201.va](cadence/measurement_stimulus/qmeter__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/qmeter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-rand_bit_stream"></a>
### [cadence/measurement_stimulus/rand_bit_stream.va](cadence/measurement_stimulus/rand_bit_stream.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/rand_bit_stream.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/rand_bit_stream.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-sampler"></a>
### [cadence/measurement_stimulus/sampler.va](cadence/measurement_stimulus/sampler.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/sampler.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/sampler.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-slew_rate_meas__ic618hotfix4"></a>
### [cadence/measurement_stimulus/slew_rate_meas__ic618hotfix4.va](cadence/measurement_stimulus/slew_rate_meas__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/slew_rate_meas.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-slew_rate_meas__icadvm201"></a>
### [cadence/measurement_stimulus/slew_rate_meas__icadvm201.va](cadence/measurement_stimulus/slew_rate_meas__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/slew_rate_meas.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-stat_probe"></a>
### [cadence/measurement_stimulus/stat_probe.va](cadence/measurement_stimulus/stat_probe.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/stat_probe.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/stat_probe.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-swept_sine_src"></a>
### [cadence/measurement_stimulus/swept_sine_src.va](cadence/measurement_stimulus/swept_sine_src.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/swept_sine_src.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/swept_sine_src.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-three_phase_src"></a>
### [cadence/measurement_stimulus/three_phase_src.va](cadence/measurement_stimulus/three_phase_src.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/three_phase_src.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/three_phase_src.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-varfreq_sin"></a>
### [cadence/measurement_stimulus/varfreq_sin.va](cadence/measurement_stimulus/varfreq_sin.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/func/varfreq_sin.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/func/varfreq_sin.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-voltmeter"></a>
### [cadence/measurement_stimulus/voltmeter.va](cadence/measurement_stimulus/voltmeter.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/voltmeter.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/voltmeter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-measurement_stimulus-zmeter"></a>
### [cadence/measurement_stimulus/zmeter.va](cadence/measurement_stimulus/zmeter.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/measure/zmeter.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/measure/zmeter.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-cap"></a>
### [cadence/devices/cap.va](cadence/devices/cap.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/cap.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/cap.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-cccs_hdl"></a>
### [cadence/devices/cccs_hdl.va](cadence/devices/cccs_hdl.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/cccs_hdl.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/cccs_hdl.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-ccvs_hdl"></a>
### [cadence/devices/ccvs_hdl.va](cadence/devices/ccvs_hdl.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/ccvs_hdl.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/ccvs_hdl.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-diode_sch__ic618hotfix4"></a>
### [cadence/devices/diode_sch__ic618hotfix4.va](cadence/devices/diode_sch__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/diode_sch.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-diode_sch__icadvm201"></a>
### [cadence/devices/diode_sch__icadvm201.va](cadence/devices/diode_sch__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/diode_sch.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-diode_simple"></a>
### [cadence/devices/diode_simple.va](cadence/devices/diode_simple.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/diode_simple.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/diode_simple.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-fullwave_rectifier_2p__ic618hotfix4"></a>
### [cadence/devices/fullwave_rectifier_2p__ic618hotfix4.va](cadence/devices/fullwave_rectifier_2p__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/power-elec/fullwave_rectifier_2p.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-fullwave_rectifier_2p__icadvm201"></a>
### [cadence/devices/fullwave_rectifier_2p__icadvm201.va](cadence/devices/fullwave_rectifier_2p__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/power-elec/fullwave_rectifier_2p.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-halfwave_rectifier_2p__ic618hotfix4"></a>
### [cadence/devices/halfwave_rectifier_2p__ic618hotfix4.va](cadence/devices/halfwave_rectifier_2p__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/power-elec/halfwave_rectifier_2p.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-halfwave_rectifier_2p__icadvm201"></a>
### [cadence/devices/halfwave_rectifier_2p__icadvm201.va](cadence/devices/halfwave_rectifier_2p__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/power-elec/halfwave_rectifier_2p.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-ind"></a>
### [cadence/devices/ind.va](cadence/devices/ind.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/ind.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/ind.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-mos_level1"></a>
### [cadence/devices/mos_level1.va](cadence/devices/mos_level1.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/mos_level1.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/mos_level1.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-mos_tft__ic618hotfix4"></a>
### [cadence/devices/mos_tft__ic618hotfix4.va](cadence/devices/mos_tft__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/mos_tft.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-mos_tft__icadvm201"></a>
### [cadence/devices/mos_tft__icadvm201.va](cadence/devices/mos_tft__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/mos_tft.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-n_jfet"></a>
### [cadence/devices/n_jfet.va](cadence/devices/n_jfet.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/n_jfet.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/n_jfet.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-npn_bjt"></a>
### [cadence/devices/npn_bjt.va](cadence/devices/npn_bjt.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/semi-dev/npn_bjt.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/semi-dev/npn_bjt.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-open_ckt_fault"></a>
### [cadence/devices/open_ckt_fault.va](cadence/devices/open_ckt_fault.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/open_ckt_fault.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/open_ckt_fault.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-power_sink"></a>
### [cadence/devices/power_sink.va](cadence/devices/power_sink.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/power_sink.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/power_sink.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-res"></a>
### [cadence/devices/res.va](cadence/devices/res.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/res.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/res.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-short_ckt_fault"></a>
### [cadence/devices/short_ckt_fault.va](cadence/devices/short_ckt_fault.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/short_ckt_fault.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/short_ckt_fault.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-sw"></a>
### [cadence/devices/sw.va](cadence/devices/sw.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/sw.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/sw.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-thyristor__ic618hotfix4"></a>
### [cadence/devices/thyristor__ic618hotfix4.va](cadence/devices/thyristor__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/power-elec/thyristor.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-thyristor__icadvm201"></a>
### [cadence/devices/thyristor__icadvm201.va](cadence/devices/thyristor__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/power-elec/thyristor.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-tuning_res__ic618hotfix4"></a>
### [cadence/devices/tuning_res__ic618hotfix4.va](cadence/devices/tuning_res__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/tuning_res.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-tuning_res__icadvm201"></a>
### [cadence/devices/tuning_res__icadvm201.va](cadence/devices/tuning_res__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/tuning_res.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-untrimmed_cap"></a>
### [cadence/devices/untrimmed_cap.va](cadence/devices/untrimmed_cap.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/untrimmed_cap.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/untrimmed_cap.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-untrimmed_ind"></a>
### [cadence/devices/untrimmed_ind.va](cadence/devices/untrimmed_ind.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/untrimmed_ind.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/untrimmed_ind.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-untrimmed_res"></a>
### [cadence/devices/untrimmed_res.va](cadence/devices/untrimmed_res.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/analog/untrimmed_res.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/analog/untrimmed_res.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-vccs_hdl"></a>
### [cadence/devices/vccs_hdl.va](cadence/devices/vccs_hdl.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/vccs_hdl.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/vccs_hdl.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-devices-vcvs_hdl"></a>
### [cadence/devices/vcvs_hdl.va](cadence/devices/vcvs_hdl.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/basic/vcvs_hdl.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/basic/vcvs_hdl.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-damper"></a>
### [cadence/multidomain/damper.va](cadence/multidomain/damper.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/damper.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/damper.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-dc_motor"></a>
### [cadence/multidomain/dc_motor.va](cadence/multidomain/dc_motor.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/em-dev/dc_motor.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/em-dev/dc_motor.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-em_relay__ic618hotfix4"></a>
### [cadence/multidomain/em_relay__ic618hotfix4.va](cadence/multidomain/em_relay__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/em-dev/em_relay.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-em_relay__icadvm201"></a>
### [cadence/multidomain/em_relay__icadvm201.va](cadence/multidomain/em_relay__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/em-dev/em_relay.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-gearbox"></a>
### [cadence/multidomain/gearbox.va](cadence/multidomain/gearbox.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/gearbox.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/gearbox.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-mag_core"></a>
### [cadence/multidomain/mag_core.va](cadence/multidomain/mag_core.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mag-dev/mag_core.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mag-dev/mag_core.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-mag_gap"></a>
### [cadence/multidomain/mag_gap.va](cadence/multidomain/mag_gap.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mag-dev/mag_gap.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mag-dev/mag_gap.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-mag_winding"></a>
### [cadence/multidomain/mag_winding.va](cadence/multidomain/mag_winding.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mag-dev/mag_winding.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mag-dev/mag_winding.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-mass"></a>
### [cadence/multidomain/mass.va](cadence/multidomain/mass.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/mass.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/mass.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-restrainer__ic618hotfix4"></a>
### [cadence/multidomain/restrainer__ic618hotfix4.va](cadence/multidomain/restrainer__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/restrainer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-restrainer__icadvm201"></a>
### [cadence/multidomain/restrainer__icadvm201.va](cadence/multidomain/restrainer__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/restrainer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-road"></a>
### [cadence/multidomain/road.va](cadence/multidomain/road.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/road.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/road.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-spring"></a>
### [cadence/multidomain/spring.va](cadence/multidomain/spring.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/spring.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/spring.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-three_phase_motor"></a>
### [cadence/multidomain/three_phase_motor.va](cadence/multidomain/three_phase_motor.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/em-dev/three_phase_motor.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/em-dev/three_phase_motor.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-trafo_hdl"></a>
### [cadence/multidomain/trafo_hdl.va](cadence/multidomain/trafo_hdl.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mag-dev/trafo_hdl.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mag-dev/trafo_hdl.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-wheel__ic618hotfix4"></a>
### [cadence/multidomain/wheel__ic618hotfix4.va](cadence/multidomain/wheel__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/mech/wheel.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-multidomain-wheel__icadvm201"></a>
### [cadence/multidomain/wheel__icadvm201.va](cadence/multidomain/wheel__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/mech/wheel.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-error_calc"></a>
### [cadence/control/error_calc.va](cadence/control/error_calc.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/error_calc.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/error_calc.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-lag_compensator"></a>
### [cadence/control/lag_compensator.va](cadence/control/lag_compensator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/lag_compensator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/lag_compensator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-lead_compensator"></a>
### [cadence/control/lead_compensator.va](cadence/control/lead_compensator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/lead_compensator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/lead_compensator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-lead_lag_compensator"></a>
### [cadence/control/lead_lag_compensator.va](cadence/control/lead_lag_compensator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/lead_lag_compensator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/lead_lag_compensator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-p_controller"></a>
### [cadence/control/p_controller.va](cadence/control/p_controller.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/p_controller.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/p_controller.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-pd_controller"></a>
### [cadence/control/pd_controller.va](cadence/control/pd_controller.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/pd_controller.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/pd_controller.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-pi_controller"></a>
### [cadence/control/pi_controller.va](cadence/control/pi_controller.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/pi_controller.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/pi_controller.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-control-pid_controller"></a>
### [cadence/control/pid_controller.va](cadence/control/pid_controller.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/control/pid_controller.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/control/pid_controller.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-absolute_value"></a>
### [cadence/math/absolute_value.va](cadence/math/absolute_value.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/absolute_value.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/absolute_value.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/absolute_value/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/absolute_value/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/absolute_value.va`；v3 导入记录：`148-source-absolute-value`、`288-source-absolute-value`。

<a id="cadence-math-adder"></a>
### [cadence/math/adder.va](cadence/math/adder.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/adder.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/adder.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-adder_4"></a>
### [cadence/math/adder_4.va](cadence/math/adder_4.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/adder_4.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/adder_4.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-cube"></a>
### [cadence/math/cube.va](cadence/math/cube.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/cube.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/cube.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-cube_root"></a>
### [cadence/math/cube_root.va](cadence/math/cube_root.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/cube_root.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/cube_root.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-divider"></a>
### [cadence/math/divider.va](cadence/math/divider.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/divider.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/divider.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/divider/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/divider/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/divider.va`；v3 导入记录：`150-source-safe-voltage-divider`、`279-source-safe-analog-divider`。

<a id="cadence-math-exponential"></a>
### [cadence/math/exponential.va](cadence/math/exponential.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/exponential.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/exponential.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-multiplier"></a>
### [cadence/math/multiplier.va](cadence/math/multiplier.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/multiplier.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/multiplier.va`（读取主机 `thu-sui`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/multiplier/veriloga/verilog.vams`（读取主机 `thu-jin`）。
- 课题组中找到的同一官方源码副本：`/home/wangx/Documents/Cadence_PDK/smic18mm_1P6M_200502021831/ahdlLib/multiplier/veriloga/veriloga.va`（读取主机 `thu-jin`）。
- 历史来源别名 `wangx/multiplier.va`；v3 导入记录：`154-source-analog-multiplier`。

<a id="cadence-math-natural_log"></a>
### [cadence/math/natural_log.va](cadence/math/natural_log.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/natural_log.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/natural_log.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-polynomial"></a>
### [cadence/math/polynomial.va](cadence/math/polynomial.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/polynomial.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/polynomial.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-power_of"></a>
### [cadence/math/power_of.va](cadence/math/power_of.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/power_of.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/power_of.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-reciprocal"></a>
### [cadence/math/reciprocal.va](cadence/math/reciprocal.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/reciprocal.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/reciprocal.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-signum"></a>
### [cadence/math/signum.va](cadence/math/signum.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/signum.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/signum.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-square"></a>
### [cadence/math/square.va](cadence/math/square.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/square.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/square.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-square_root"></a>
### [cadence/math/square_root.va](cadence/math/square_root.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/square_root.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/square_root.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-subtractor"></a>
### [cadence/math/subtractor.va](cadence/math/subtractor.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/subtractor.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/subtractor.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-math-subtractor_4"></a>
### [cadence/math/subtractor_4.va](cadence/math/subtractor_4.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/math/subtractor_4.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/math/subtractor_4.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-am_demodulator"></a>
### [cadence/communications/am_demodulator.va](cadence/communications/am_demodulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/am_demodulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/am_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-am_modulator"></a>
### [cadence/communications/am_modulator.va](cadence/communications/am_modulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/am_modulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/am_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-decider__ic618hotfix4"></a>
### [cadence/communications/decider__ic618hotfix4.va](cadence/communications/decider__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/decider.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-decider__icadvm201"></a>
### [cadence/communications/decider__icadvm201.va](cadence/communications/decider__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/decider.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-fm_demodulator"></a>
### [cadence/communications/fm_demodulator.va](cadence/communications/fm_demodulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/fm_demodulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/fm_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-fm_modulator"></a>
### [cadence/communications/fm_modulator.va](cadence/communications/fm_modulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/fm_modulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/fm_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-mixer"></a>
### [cadence/communications/mixer.va](cadence/communications/mixer.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/mixer.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/mixer.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pcm_demodulator__ic618hotfix4"></a>
### [cadence/communications/pcm_demodulator__ic618hotfix4.va](cadence/communications/pcm_demodulator__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/pcm_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pcm_demodulator__icadvm201"></a>
### [cadence/communications/pcm_demodulator__icadvm201.va](cadence/communications/pcm_demodulator__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/pcm_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pcm_modulator__ic618hotfix4"></a>
### [cadence/communications/pcm_modulator__ic618hotfix4.va](cadence/communications/pcm_modulator__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/pcm_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pcm_modulator__icadvm201"></a>
### [cadence/communications/pcm_modulator__icadvm201.va](cadence/communications/pcm_modulator__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/pcm_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pm_demodulator"></a>
### [cadence/communications/pm_demodulator.va](cadence/communications/pm_demodulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/pm_demodulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/pm_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-pm_modulator"></a>
### [cadence/communications/pm_modulator.va](cadence/communications/pm_modulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/pm_modulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/pm_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qam_16ary_demod__ic618hotfix4"></a>
### [cadence/communications/qam_16ary_demod__ic618hotfix4.va](cadence/communications/qam_16ary_demod__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/qam_16ary_demod.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qam_16ary_demod__icadvm201"></a>
### [cadence/communications/qam_16ary_demod__icadvm201.va](cadence/communications/qam_16ary_demod__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/qam_16ary_demod.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qam_16ary_mod"></a>
### [cadence/communications/qam_16ary_mod.va](cadence/communications/qam_16ary_mod.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/qam_16ary_mod.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/qam_16ary_mod.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qpsk_demodulator__ic618hotfix4"></a>
### [cadence/communications/qpsk_demodulator__ic618hotfix4.va](cadence/communications/qpsk_demodulator__ic618hotfix4.va)

- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/qpsk_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qpsk_demodulator__icadvm201"></a>
### [cadence/communications/qpsk_demodulator__icadvm201.va](cadence/communications/qpsk_demodulator__icadvm201.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/qpsk_demodulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-qpsk_modulator"></a>
### [cadence/communications/qpsk_modulator.va](cadence/communications/qpsk_modulator.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/qpsk_modulator.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/qpsk_modulator.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

<a id="cadence-communications-trans_channel"></a>
### [cadence/communications/trans_channel.va](cadence/communications/trans_channel.va)

- Cadence `ICADVM201`：`spectreHDL/Verilog-A/telecom/trans_channel.va`（读取主机 `thu-sui`）。
- Cadence `IC618Hotfix4`：`spectreHDL/Verilog-A/telecom/trans_channel.va`（读取主机 `thu-sui`）。
- 本次直接从安装库恢复；未据功能相似性绑定到 v3 任务。

## 公共头文件

- [constants.h](cadence/include/constants.h) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/constants.h`（读取主机 `thu-sui`）。
- [constants.vams](cadence/include/constants.vams) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/constants.vams`（读取主机 `thu-sui`）。
- [discipline.h](cadence/include/discipline.h) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/discipline.h`（读取主机 `thu-sui`）。
- [disciplines.h](cadence/include/disciplines.h) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/disciplines.h`（读取主机 `thu-sui`）。
- [disciplines.vams](cadence/include/disciplines.vams) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/disciplines.vams`（读取主机 `thu-sui`）。
- [shdl_strings.vams](cadence/include/shdl_strings.vams) ← `/home/cadence/spectre/SPECTRE211Hotfix/tools/spectre/etc/ahdl/shdl_strings.vams`（读取主机 `thu-sui`）。

## 尚待定位的历史来源

以下 45 项仅有历史来源线索，本次未找到可读取候选，没有生成替代模型。目录扫描有范围、时间和权限限制，未找到不表示不存在；`/home/zhangz`、`/home/guoxue25` 的读取遇到权限拒绝。

| 历史来源 | v3 导入记录 |
| --- | --- |
| `caiyizeng25/L3_SAR2_cdac_7b_ideal.va` | `136-source-sar-cdac-residue` |
| `caiyizeng25/L3_SAR2_logic_7b_ideal.va` | `244-source-l3-sar2-logic-7b` |
| `caiyizeng25/L3_SAR_comparator_ideal.va` | `112-source-clocked-sar-comparator`、`248-source-sar-comparator-reset-high` |
| `gaoya/LT_READ_SAR6B.va` | `258-source-lt-read-sar6b-weighted` |
| `gaoya/LT_READ_SAR7B.va` | `259-source-lt-read-sar7b-weighted` |
| `guoxue25/SARFEND_LOGIC_FT_4B.va` | `222-source-sarfend-logic-4b` |
| `hexy/COMP_OS_TEST.va` | `208-source-offset-bisection-driver` |
| `hexy/level_shifter.va` | `273-source-level-shifter-offset` |
| `hexy/maxDetector.va` | `132-source-max-detector-hold` |
| `hexy/samplehold.va` | `268-source-samplehold-rising-edge` |
| `huangsy/ACCUM_3_bit.va` | `276-source-accum3-pulse` |
| `huangsy/DIV8.va` | `171-source-divide-by-eight-clock` |
| `huangsy/DIV8_9.va` | `189-source-divide-by-8-9-switch` |
| `huangsy/PD_RS.va` | `272-source-rs-phase-detector` |
| `huangsy/PD_XOR.va` | `277-source-xor-phase-detector` |
| `huangsy/PFD.va` | `267-source-pfd-up-down-state` |
| `liudongyang/L2_cdac_8b_ideal.va` | `245-source-cdac-8b-monodown` |
| `liudongyang/PIPE8B_DATA_ALIGN.va` | `215-source-pipe15-data-align` |
| `liukezhuo/coarse_QTZ3bit.va` | `271-source-coarse-qtz-3bit-residue` |
| `taoy/OPAMP.va` | `161-source-ideal-differential-opamp` |
| `taoy/v_DIVIDER_2.va` | `184-source-divide-by-two-toggle` |
| `taoy/v_PFD.va` | `300-source-pfd-active-low-reset` |
| `zengsy/Counter_2b_VA.va` | `131-source-two-bit-counter-marker` |
| `zengsy/DIV_16_17_VA.va` | `176-source-dual-modulus-divider-16-17` |
| `zhangad/dac_10bit_ideal.va` | `294-source-subradix-dac10` |
| `zhangad/dac_4bit_flash_ideal.va` | `186-source-folded-flash-dac-4b`、`293-source-flash-folded-dac4` |
| `zhangfm/VA_Lx_ADC_ideal.va` | `195-source-va-lx-adc-ideal-4b` |
| `zhangfm/VA_Lx_DAC_ideal.va` | `196-source-va-lx-dac-ideal-4b` |
| `zhangfm/comparator_ideal.va` | `257-source-comparator-reset-low-1p8` |
| `zhangm/FLASH_8_LEVEL.va` | `179-source-flash-8level-sum-delay` |
| `zhangm/SYNC_8B_DFFS_V2.va` | `211-source-sync-8b-dffs-v2` |
| `zhangm/TDC_IDEAL.va` | `213-source-tdc-ideal-edge-delta` |
| `zhangm/TI_2C_DEMUX_VA.va` | `181-source-two-channel-sample-demux` |
| `zhangm/tb_REF_FLASH_15L_DECODER.va` | `188-source-ref-flash-15level-decoder` |
| `zhangm/tb_REF_FLASH_8L_DEC.va` | `187-source-ref-flash-8level-decoder` |
| `zhangz/DAC_serial_16b_nobridge_va.va` | `260-source-dac-serial-16b-nobridge` |
| `zhangz/DAC_serial_PPSAR_va.va` | `253-source-sum5-signed-sar-weight` |
| `zhangz/DAC_serial_va.va` | `205-source-dac-serial-accumulator` |
| `zhangz/L2_Divider_2.va` | `275-source-divide-by-two-toggle` |
| `zhangz/L2_PFD.va` | `282-source-pfd-timer-reset` |
| `zhangz/L3_SPI_MUX_Big_V1.va` | `220-source-spi-shift-mux` |
| `zhangz/L3_logic_4b.va` | `230-source-sar-logic-4b-self-timed` |
| `zhangz/PFD_20201101.va` | `201-source-linear-pfd-gain` |
| `zhangz/SAR_logic_DAS_va.va` | `229-source-sar-das-logic-6b` |
| `zhangzixuan/_tool_delay_two_period.va` | `169-source-two-period-sample-delay` |
