# 来源与边界

来源349：[v4源任务](../../reference/v4/release/benchmarkv4-r53/tasks/349-multichannel-sample-readout/public/instruction.md)。本题将DUT从零构建改成复用健康024单通道资产的扩展，保留四通道采样与顺序读出职责。固定baseline与#133的024合同相同；实际健康校准仍待完成，不能据此宣布完成。

新增公开同沿读旧帧语义。保留来源reset清bank要求，候选须在固定无reset单通道部件外实现清零适配；正常采样与保持仍复用健康基线。原来源理想行为不是器件测量数据。归属Spectre扩展集，开源复现未证明。运行与模型试做状态见实验manifest。

固定024移植版本SHA256为`e58e5baa42c0ec8a82b194da6f63370bf8f08dd819821a7d7f7d25d3abe27e69`。#133作者删除非标准default_transition，保留标准Verilog-A include与tedge合同；这是作者环境准备，不是候选评分职责。
