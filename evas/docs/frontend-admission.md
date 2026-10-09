# 编译准入契约

默认 `compile_sources` 与 CLI compile/lint 检查预处理后的活跃源码。
依据 VAMS 2.4 §2.6，含小数点的实数字面量必须在两侧有数字；`.25`、`.5`、
`.875`、`1.`、`1.e2` 拒绝，`0.25`、`1.0`、`1e2`、`0.5u` 接受。
未使用的宏定义和 inactive 条件分支不触发字面量检查；实际展开的宏按调用位置诊断。
这些检查也不能被参数覆盖隐藏。

`electrical` 是受支持的 discipline 名称，使用前必须声明。
显式 `include "disciplines.vams"` 可使用 `standard_headers.py` 中的
`evas-voltage-vams-v1` 环境，定义 Voltage/V、Current/I 以及 continuous electrical。
显式 `include "constants.vams"` 提供有限数学宏 `M_PI`。
没有该 include 或用户 define 的 `M_PI` 不再隐式预定义。
调用者提供的同路径文件总是优先，空头文件不等价于标准定义。
不搜索机器文件系统，不隐式为没有 include 的模型添加 discipline。

也可在源文件或自定义 include 中声明同样的 nature/discipline。
当前接受 `nature Voltage` 的 `units="V"; access=V;`，`nature Current` 的
`units="A"; access=I;`，可选有限正 `abstol`，以及
`discipline electrical; potential Voltage; flow Current; domain continuous; enddiscipline`。
重复定义、不兼容属性和更广 nature/discipline 语义明确拒绝。
声明随活跃 include 展开按顺序生效，头文件不会同时作为独立编译根。
Voltage/Current 的声明承认电压域所需类型环境，不增加电流贡献的执行支持；
nature 的 abstol 也不改变 manifest 的求解容差。

旧测试夹具的简化 VA 字符串已显式补 include 并改用有效字面量。
冻结 `evas/validation/`、实验源、结果、收据和哈希不改写；旧归档需其原提交前端复现。
其中 event_relocalization、projected_history、pure_function 的开发回归使用
[显式 successor](../tests/fixtures/README.md)，仅修正头文件与数字拼写。
公开准入测试同时确认冻结原版本拒绝和 successor 接受；这不把原验证收据重标为通过。
当前前端拒绝非法归档源码是预期结果，不证明历史波形的数值正确性。

实现入口是 `frontend.py`、`preprocessor.py`、`syntax.py` 与
`standard_headers.py`；独立公开编译回归在 `tests/test_compile_admission.py`。
该有限准入修复不等价于完整 Spectre/VAMS 语法兼容性认证。
