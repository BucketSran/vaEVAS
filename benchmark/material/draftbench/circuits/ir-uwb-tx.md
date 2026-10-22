# IR-UWB TX 种子链 Verilog-A 系统资产

[进入功能族总览](ir-uwb-tx/README.md)。8DPPM+8FSK、4.032 Gb/s 种子发射链的 9 个模块和系统顶层，按 `module/`、`system/`、`test/` 存放；行为约定见 [SPEC.md](ir-uwb-tx/SPEC.md)。

用于 [#223](https://github.com/BucketSran/vaEVAS/issues/223)：先交付发射系统的 Verilog-A，再从中切出 vaBench 题目。尚未新增题包。gold 为本项目自建（公开渠道没有找到 IR-UWB TX 的 Verilog-A 实现），目前只在旧 EVAS 0.8.7 上验证；当前 EVAS 的运行缺口见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)，Spectre 未运行。
