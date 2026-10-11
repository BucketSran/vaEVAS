# 来源与身份

源case0007与tiny-tapeout-adpll固定来源见[电路卡](../../workbench/circuits/tiny-tapeout-adpll.md)。原RTL的计数反馈与粗调思想被改编，所给电压域健康资产、DCO细调与TDC合同由本题作者建立，并非原作者现成VA源码。行为数据为合成规格，未冒充晶体管或硅片测量。

原DCO低六位无效问题由出题方执行器解决，fine参数真实进入积分频率路径。候选负责TDC、跟踪控制与模式集成。候选不能修环境作为评分职责。真实healthy coarse、fine actuator、reference、alternative和语义mutant的作者运行校准已完成，模型试做尚未完成。

归属Spectre扩展集，开源同题复现未证明。此任务不计v4来源数；349另为P1唯一归口。模型试做与来源mapping见实验manifest。

当前作者正负校准的固定身份与完整分母见[作者校准最终报告](../../../experiments/benchmark_v2/author-calibration-final.md)。该结论不代表模型试做或完整 spec 验收完成；历史来源与旧运行仍保留原版本。
