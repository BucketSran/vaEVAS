# EVAS

此工作区将维护 EVAS 的完整源码、构建配置和仿真器自身的回归测试。
源码将在后续审查和迁移时加入，新仓库中的 EVAS 将作为后续联动开发的主线。

EVAS 的目标是支持声明范围内的电压域 Verilog-A 行为及其交互，与 Spectre 对标，
并为无需商业许可证的 VABench 复现和 agentic eval 提供执行后端。
支持范围不以现有 benchmark 家族为白名单；具体语义边界、内部模块及重构方法仍待确定。
修复应由具体问题和可复现用例驱动，并检查受影响的 benchmark 任务。
语义正确性需要独立参考或可解释的预期结果支撑，不能只依据任务是否通过。

## 独立验证集

[validation/](validation/README.md) 维护面向电压域行为的独立验证集设计，
用于比较 Spectre、ngspice＋OpenVAF、Gnucap＋modelgen-verilog 与 EVAS。
当前已有七组行为、八张起步契约、共同 VA 源码及
[四后端试点](../experiments/dvs2-starter-pilot/RESULTS.md)。试点检验有限观测，
不代表整组覆盖完成或取得正式 DVS-2 通过资格；本轮没有修改仿真器。
本轮及后续诊断已固定为 [验证集 v1](validation/versions/v1/README.md)，
下一轮先完善判定方法，再补事件边界、动态行为和有状态组合，见
[验证范围与后续边界](validation/README.md)。

此验证集的需求、答案和判据独立于 EVAS 当前实现；既有 VABench 家族仅作为应用与回归层。
先审查契约和判定方法，固定各后端设置并取得基线，再依据证据推进 EVAS 修复。
