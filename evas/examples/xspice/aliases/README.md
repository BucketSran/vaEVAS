# P0 输入别名微例

`affine_input_aliases.va`和`selected_body_alias.va`逐字保留前一阶段静态探针；来源及SHA256见[sources.json](sources.json)。`direct_input_expressions.va`是显式标注的直接表达式等价控制，不能代替别名版本验收。三份文件均为从讨论阈值链提炼的有限微例，不是完整DFF/PFD原件。

ngspice、Spectre及Rust适用路径执行同一VA。动态输入、解析根和采样值、外部RC、预算及实际结果由[验收合同](../../../validation/xspice/README.md#p0-input-aliases)维护。条件采样的原生夹具只覆盖true叶。
