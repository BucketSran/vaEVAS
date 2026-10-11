# DAC 与 ADC 测量任务

本路线把四种不同码制分别建成 DAC 模型题，补一个 DAC 完整扫描测量题，并迁移已有的相干 ADC 频谱题。模型题要求真实端口电压传输；测量题要求对实际观测算结果，即使被测器件不理想也可通过。全部使用固定 Spectre，模型试跑不在本轮范围。

| spec 单元 | 任务 | 来源及覆盖 |
| --- | --- | --- |
| E1 | v3-converter-segmented | 014，两个二进制低位和三个4LSB单元，跨段边界及保持 |
| E1 | v3-converter-thermometer | 018，15个单元独立求和，包括最高单元、气泡及稀疏码 |
| E2 | v3-converter-nonideal | 025，实际位权1、2.02、3.96、8.08和满码归一化 |
| E2 | v3-converter-subradix | 243，十位radix1.8，进位边界可非单调 |
| E3 | v3-converter-dac-linearity | 原创静态DAC端点扫描；旧va08 ADC码密度题继续复用，不重复计新来源 |
| E4 | v3-converter-adc-spectrum | 原频谱题同源迁移，保留64点合成记录，增加有效性、重置、ENOB和Nyquist验收 |

四个 DAC 明确改编为时钟上升沿更新并保持。公开合法控制不限自然温度计前缀，因此任何活动单元模式都按真实权重求和。亚基数非单调是目标行为。两个端点条件验证参考关系，码在采样前改变时旧输出仍应保持。

DAC 扫描使用可读固定器件，16个码各采一次。端点步长由实际首末电压确定，DNL与INL报告最大绝对值，单位LSB。例如局部电压多出半个实际步长时，INL最大值为0.5LSB，相邻宽度分别增加和减少0.5LSB。重复或漏采使记录无效。本题补DAC电平扫描，不能声称旧190比较器/RDAC系统已完成。

频谱记录为行为合成12bit unsigned码，不是实测ADC数据。矩形窗、64点相干采样、单bin基波、谐波进入残差、DC排除、Nyquist不翻倍。独立checker用余弦自相关求每个bin功率，VA参考在线积累DFT，另一正确实现先保存记录再批量DFT。实际校准需要同时检验幅度/功率混淆、Nyquist翻倍和无效记录保留旧结果。

`provenance.json`固定原材料字节与去向。344 DEM和190原扫描系统仅保留准备资产，不作为本轮完成条件或新计分项。ADCToolbox仅作方法来源，没有用同库两次调用作为独立真值。

`build_tasks.py`生成Harbor资产、公开实例、私有条件、两种正确实现和针对语义错误的VA变体。`manifest.json`登记完整变体。`prepare.py`复用既有runtime，不另建执行框架；原参考脚本保持原字节，通过固定路径映射的cp执行，产物作为实际候选。公开镜像只COPY public和starter，私有checker与reference不进入解题包。

本地检查 `python3 -B -m unittest discover -s experiments/benchmark_next/converter -p test_checker.py -v` 校验已知单音/谐波功率、端点拟合及实际波形保持判据。它不替代真实Spectre作者校准。远端原始输出留在忽略runs目录，精简结果与全部失败尝试另行固定。

作者校准的预先选择是参考与合法替代跑全部正式条件，语义错版跑登记的针对条件。例如重复码错版用repeat-code，旧结果错版用reset后的截断或无效记录。`manifest.json`中的case_names在执行前固定；没有执行的错版条件不宣称通过，也不据单条件失败声称完整任务得0分。最终登记32个变体、56个已安排作者条件位置。

早期失败包括部署仍仅认可v2前缀，以及ADC频谱台架交换sample_ok和clk/rst的作者连接错误。原尝试不会删除；修正只调整授权部署或台架端口顺序，未放宽评分容差。扫描另补reset后不完整记录，参考需按最终四条件重新验收。
