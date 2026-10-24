# 原31条件的共享科学定义

本目录维护[验证集](../README.md)原31条件的输入、两档配置和独立有限观察判据。
条件ID、源码卡、参数、刺激和P/F/I含义沿用原定义；不赋予连续时间或后端观察资格。

- `cases.py`维护31条件；`legacy.py`保留其中原v1条件、插值和解析参考。
- `checker.py`维护当前数学与事件历史检查，`legacy_checks.py`保留原v1有限观察检查。
- `history.py`维护独立有理数历史可行性检查及事件合同。事件合同不由v1波形参考生成。

[开发静态回归](../../tests/run_static_regression.py)直接读取本目录，动态程序仍明确拒绝。
[Spectre适配器](../../../experiments/backends/dvs2-spectre-validation/README.md)保留deck、冻结、波形读取和执行职责；
其原`conditions`、`reference`、`check`等入口转调本目录。
新的输入冻结保存全部共享科学源码身份；旧归档、输入、判据和分析收据不回写。
`source_files(repo)`统一枚举科学源码，静态回归、DVS冻结器与当前比较框架共同引用，新增模块也进入身份。
波形读取属于[共享后端证据工具](../../../experiments/backends/evidence/README.md)，
原浮点投影与保留token的读取分别说明，科学定义不反向导入它们。

可在仓库根目录运行独立校准，不启动模拟器：

```sh
PYTHONPATH=evas/src:experiments/backends/dvs2-spectre-validation \
  python3 -B -m unittest test_checks test_event_review test_s1_review test_science_contract -v
```
