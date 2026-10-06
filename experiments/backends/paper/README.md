# 新纸面批次的后端准备

本目录准备 [core-v1 cards](../../../evas/validation/paper/core-v1.json) 的
12 个条件与 48 个四后端配置，不改变旧比较器的固定 32 配置计划。
数学判据与评分由 `evas/validation/paper/` 拥有。这里不运行后端，也不判定条件通过。

```sh
python3 -B -m unittest discover -s experiments/backends/paper -p 'test_*.py' -v
python3 -B experiments/backends/paper/inputs.py runs/paper-a1-inputs-NEW
```

输出目录必须新建。冻结内容包括卡片原字节、每配置的精确 `dut.va`、
后端 deck、真实顶层绑定、请求设置/时间、观测要求、适配器源码及其身份。
`verify(root)` 核对文件集合、哈希、大小和 12×4 计划。
SI-01 原源码中的 `paper_isolation` 顶层包含 A/B 两个真实实例，所有后端
都请求该顶层，不能用外部平铺请求替代该条件。

请求网格包含全局最多 200 ps、规定窗口内最多 20 ps 间隔、所有名义中心和
anchor。SPICE deck 请求最多 20 ps 内部步长，保留原生输出，不强制网格插值。
`requested_times.json` 是共同的观测义务；deck 尚未证明能产生每一个精确中心。
后续执行必须核验实际输出来源、时间/电压误差、局部间隔和中心行。
编译器是否接受原源、deck 是否有效、工具版本/二进制/镜像身份及有效设置
在准备阶段均未知。`qualification_requirements.json` 保留这些待办。
准备文件不是实际比较证据，实际执行须先由协调者批准冻结批次并绑定工具身份。

`read_native(path, backend)` 复用已有 CSV、Spectre ASCII PSF 和 SPICE 文本
读取器，完整保留时间与数值。格式解析不证明原生采样或准确性。
`normalize_observation(card, backend, rows, origins, qualification, contract=...)`
保存原行与逐行 `accepted`、`interpolated` 或 `unknown` 来源，并报告缺列、
非有限值、重复时间、截断、实际全局/局部间隔和精确中心行。
它不重采样、不修补缺失输入、不消除 modulo 端点原始值。

资格字段与 checker 的 `assess_observation` 接口对齐。时间、电压和实际输入
不确定度必须独立给出，且 `qualification_evidence` 按 source/time/voltage/inputs
及适用的 native_counters/native_phase 角色记录 `{method, artifact_path, sha256}`。
适配器只核验可读取证据的哈希及声明，科学误差界仍需审查 method 报告。
缺证据时 `qualified=false`。密集网格、solver tolerance 与相互一致的后端
不能建立误差界。插值误差须单独有界并包含在总导出误差内；插值/未知记录
不会成为原生计数/phase 或精确端点证据。

此模块只交付有限批次与观测准备。实际编译/执行、工具 preflight、有效设置
readback、具体误差证书和比较结果仍由后续执行阶段产生。历史失败与新结果
分别保留，自动重试为零，默认每阶段 90 s、许可证等待 30 s，具体远程分配
由协调者管理。
