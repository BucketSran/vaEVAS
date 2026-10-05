# 四后端比较记录

[维护契约](../../../evas/docs/COMPARISON.md)定义数据集、身份与复验规则。
[当前计划表](PLANNED.md)由[snapshot-20261006-planned.json](snapshot-20261006-planned.json)
生成。它含历史31条件的两档记录和今晚8条件的32项计划，不是新论文集。
当前32项均为 T。待服务器/本地资源协调完成后，新观察进入新快照。

## 检查与生成

从仓库根目录执行：

```sh
python3 -B -m unittest discover -s experiments/backends/comparison -p 'test_*.py' -v
python3 -B experiments/backends/comparison/records.py \
  experiments/backends/comparison/snapshot-20261006-planned.json \
  --output experiments/backends/comparison/PLANNED.md --check
```

渲染器校验固定分母、逐配置唯一性、输入身份、独立 checker、证据文件哈希、
失败阶段和误差单位/预算。缺少原始私有波形不会抹掉历史收据；缺少收据或
精简分析则不能声称本地复验。重复配置、删掉失败、把旧工件称为当前工件均会拒绝。
同一组在当前子集没有条件时显示“不适用 N=0”；待冻结集显示 pending 和 N=unknown。

不覆盖既有快照和表。新文件可用下列命令生成：

```sh
python3 -B experiments/backends/comparison/seed.py runs/cmp/new-planned.json
python3 -B experiments/backends/comparison/records.py runs/cmp/new-planned.json \
  --output runs/cmp/new-planned.md
```

`--target new-targets.json`仅改变查看的目标身份，不改旧测量。
目标格式与快照中的 `targets` 一致。EVAS 的 runtime identity覆盖 Python前端、Rust/IR
源文件及 Cargo身份；新观察还须提供实际内核哈希。提交号不同且没有同一 runtime
的明确复用理由时标为 stale。身份相同只表示与声明目标一致，不表示重新执行。

## 冻结与执行8条件

[freeze.py](freeze.py)复用既有模型、刺激、参数、基础档和独立检查器，只生成以下条件：
`v1-main`, `v2-main`, `v3-main`, `v4-c0`, `v5-main`, `v6-standard`, `v7-linear-main`, `c1-main`。
所有后端的 DUT 字节、物理输入和外部精度要求相同。ngspice使用 OSDI 编译，
没有电压IR旁路。Gnucap使用文档化的具名零参考与 `short=1e-9`。

```sh
python3 -B experiments/backends/comparison/freeze.py runs/cmp/fresh-inputs
```

[runner.py](runner.py)每次只执行一个明确分配的后端，共8配置，无重试；
编译/仿真各90秒，Spectre许可证等待30秒。输出必须是新目录。资源分配由协调者负责；
`--allocation`写入收据，不授予额外执行权限。容器链路使用既有环境的单CPU、
单线程与4GiB进程地址空间限制；不声称整个进程树有4GiB RSS硬上限。
Gnucap前端和C++步骤在一个90秒编译阶段内运行。原始阶段命令、日志哈希和失败全部保留。

本地EVAS先按[构建入口](../../../evas/README.md#构建与运行)构建本工作树的内核，再执行：

```sh
python3 -B experiments/backends/comparison/runner.py runs/cmp/fresh-inputs \
  runs/cmp/fresh-evas --backend evas --kernel evas/rust_core/target/debug/evas-kernel \
  --allocation COORDINATOR_ALLOCATION
```

EVAS使用当前 `compile_sources`/`transient` API和明确选择的内核，不调用历史容器EVAS。
基线内核没有CLI版本握手，版本为unknown，工件哈希与响应中的 engine身份单独保存。
Spectre参数为 `--backend spectre --spectre-profile EXISTING_PROFILE`；
其余后端为 `--backend openvaf_ngspice` 或 `--backend gnucap`，并提供
`--environment EXISTING_ACTIVE_ENVIRONMENT`。服务器Python须用 `-X utf8`。
私有配置、安装包和原始波形不提交。

## 许可证与可用性

表按Spectre、OpenVAF-R、ngspice、Gnucap、modelgen-verilog和EVAS逐组件记录。
上游许可证与实际安装工件的许可证核实分开，未完成的映射保持unknown。
OpenVAF-R自己的版本回显仍为unknown，不能用发布包标签替代。
历史精简分析/收据在仓库内可取得；历史原始归档仍为私有材料。
许可证来源链接保存在同一结构化快照中，不声称上游当前文件证明旧二进制的完整许可。
