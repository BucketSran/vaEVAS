# 公共头文件

[Cadence 模型入口](../README.md) · [历史来源总表](../../SOURCES.md#公共头文件)

这些文件来自 SPECTRE211Hotfix 安装目录，供查阅标准常量与 discipline 定义。
它们不是 IC618Hotfix4 或 ICADVM201 随库附带文件的同版本认证替代；实际运行优先采用对应仿真器自己的头文件。
本目录可作为 include 搜索目录，所有模型原有的 include 语句保持不变。

| 文件 | 内容 |
| --- | --- |
| [constants.vams](constants.vams) | 数学与物理常量 |
| [constants.h](constants.h) | 旧名称的常量头文件 |
| [disciplines.vams](disciplines.vams) | electrical、机械等 nature/discipline 定义 |
| [discipline.h](discipline.h) | 原库使用的旧名称 discipline 定义 |
| [disciplines.h](disciplines.h) | 另一个原始名称的 discipline 定义 |
| [shdl_strings.vams](shdl_strings.vams) | SpectreHDL 字符串／兼容定义，按需查阅 |
