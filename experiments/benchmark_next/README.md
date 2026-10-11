# 下一批 Verilog-A 题目

本目录对应五份独立规格。每条路线分别交付 PR，目录内实际存在的路线以当前分支为准；规格清单不代表五条路线均已合入 main。

| 路线 | 规格 | 工程内容 |
| --- | --- | --- |
| `ota/` | [#147](https://github.com/BucketSran/vaEVAS/issues/147) | 连续 OTA、真实电路数据建模、阶跃测量 |
| `ldo/` | [#148](https://github.com/BucketSran/vaEVAS/issues/148) | 真实 LDO 启动及响应驱动 line/load 测试台 |
| `filter/` | [#149](https://github.com/BucketSran/vaEVAS/issues/149) | CTLE、可编程低通、I/Q 变频、动态包络和扫频测量 |
| `calibration/` | [#150](https://github.com/BucketSran/vaEVAS/issues/150) | 分数 PLL、连续失调校准及共模伺服 |
| `converter/` | [#151](https://github.com/BucketSran/vaEVAS/issues/151) | 四种 DAC 合同、DAC 静态扫描及 ADC 相干指标 |

进入相应目录的 `README.md` 查看任务映射、构建和运行入口；作者校准报告记录正确实现、合法替代实现及编译成功的语义错版，机器收据绑定材料、判据、实际后端与原始归档身份。完整运行资料保存在所属工作区的 ignored `runs/`，本地路径不代表公开下载。

题目沿用 [五类工程动作](../../benchmark/docs/task-types.md) 和现有 Harbor 格式。公开材料、候选源码、固定环境与私有评分资产分别维护，参考解实际产物经过后端执行再由独立 checker 判断。本轮不做模型解题实验；作者校准也不等于已完成 Harbor Agent Trial 或正式 benchmark 发布。

各题固定其评分后端。真实源电路能在 ngspice 运行，不自动证明对应 VA 任务已可开源复现。后端资格与校准限制以每条路线的实际证据为准。
