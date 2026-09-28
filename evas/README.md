# EVAS

此工作区维护 EVAS 的源码、构建配置和仿真器自身的回归测试。
当前已实现重构的第一个切片：严格的限定语法前端、贡献 IR 与 Rust 静态线性求解内核。
完整旧仿真器尚未迁入，新内核尚未替换旧 EVAS 0.8.7。

EVAS 的目标是支持声明范围内的电压域 Verilog-A 行为及其交互，与 Spectre 对标，
并为无需商业许可证的 VABench 复现和 agentic eval 提供执行后端。
支持范围不以现有 benchmark 家族为白名单；本批实现边界与后续约束见 [设计](DESIGN.md)。
修复应由具体问题和可复现用例驱动，并检查受影响的 benchmark 任务。
语义正确性需要独立参考或可解释的预期结果支撑，不能只依据任务是否通过。

## 当前切片的运行和检查

需要 Python 3.10+ 和 Rust/Cargo。以下命令在仓库根目录运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas compile evas/examples/static_sum.json
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
PYTHONPATH=evas/src python3 evas/tests/run_static_regression.py --kernel evas/rust_core/target/debug/evas-kernel --output runs/evas-static-replay
```

最后一个命令要求新的输出目录，读取原 31 条条件的 VA、输入和独立判据。
当前 9 个条件可编译，另 22 个明确拒绝；两档分别是静态求解的采样网格和残差设置，
不代表已经实现瞬态积分、事件定位或取得 DVS 正式资格。
review 停止点及实测结果见 [REVIEW.md](REVIEW.md)。

## 独立验证集

[validation/](validation/README.md) 维护面向电压域行为的独立验证集设计，
用于比较 Spectre、ngspice＋OpenVAF、Gnucap＋modelgen-verilog 与 EVAS。
当前已有七组行为、八张起步契约、共同 VA 源码及
[四后端试点](../experiments/dvs2-starter-pilot/RESULTS.md)。试点检验有限观测，
不代表整组覆盖完成或取得正式 DVS-2 通过资格；本轮没有修改仿真器。
本轮及后续诊断已固定为 [验证集 v1](validation/versions/v1/README.md)，
下一轮先完善判定方法，再补事件边界、动态行为和有状态组合，见
[优化优先级](validation/INDEPENDENT_SET_DESIGN.md#10-v1-之后的优化优先级)。

此验证集的需求、答案和判据独立于 EVAS 当前实现；既有 VABench 家族仅作为应用与回归层。
先审查契约和判定方法，固定各后端设置并取得基线，再依据证据推进 EVAS 修复。
