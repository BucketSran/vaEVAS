# 四后端比较记录

[维护契约](../../../evas/docs/COMPARISON.md)定义数据集、身份与复验规则。
[当前结果表](TABLE.md)由[snapshot-20261006-accounted-v2.json](snapshot-20261006-accounted-v2.json)
生成。今晚固定8条件、基础档、四后端共32配置：Spectre和当前EVAS各8项有新有限观察P；
OpenVAF/ngspice与Gnucap各8项因既有容器层缺失保持T，共16项尚未取得观察。
不得将32项完整记账称为32项已完成实验。历史31条件、两档开发回放另列，新论文集N仍unknown。
[原计划](PLANNED.md)及[EVAS先行快照](EVAS8.md)保留，不用最新结果回填旧记录。

表C固定了va07的正确参考源码、constant-tighter条件和checker身份；四后端公共外壳、
精度映射与连续时间资格仍待冻结。原EVAS单后端历史回放不进入四方C分母。

## 历史格式与派生快照

schema2 从原具名观察静态重聚合，不增加仿真次数。V1 保存最大绝对输出误差及1mV预算；
V2 分别保存差模误差及2mV预算、共模误差及1mV预算，B取各物理性质的归一化最大值。
物理量、单位和预算逐项保留；预算来源以固定revision及内容寻址的PROTOCOL源码归档绑定。
历史248行的判定、指标绑定到matrix中唯一backend/condition/profile/source_run_id及其receipt；
今晚16项观察绑定到各执行receipt里的observation。改判定、指标、预算或选择器会拒绝。

三个schema1旧快照保持原字节。它们的V2指标把单端误差除以1mV，数学解释失效；
新版渲染器明确标注并排除该项B比较。旧PLANNED.md、EVAS8.md是原历史表，不能作为修正后的
V2归一化结果。旧快照仍可校验和阅读；旧格式其他有效观察和A计数没有被弃用。
[新派生快照](snapshot-20261006-accounted-v2.json)保留父快照SHA及静态重聚合边界。
旧格式不能用于新执行导入，先显式派生到schema2。

应用候选的原revision/source/checker身份不变。新快照保存内容寻址源码、原仓库相对path和固定
40hex revision；校验归档SHA及该revision的Git blob，不执行源码或访问网络。旧格式的可变源码
引用如与当前工作树不同，则按其固定revision的本地Git blob解释；本地缺少该blob会明确失败。
1006 checker修复不改变历史候选；若使用新checker执行，需要新候选和新验证，不能修改旧SHA冒充。

## 检查与生成

从仓库根目录执行：

```sh
python3 -B -m unittest discover -s experiments/backends/comparison -p 'test_*.py' -v
python3 -B experiments/backends/comparison/records.py \
  experiments/backends/comparison/snapshot-20261006-accounted-v2.json \
  --output experiments/backends/comparison/TABLE.md --check
```

渲染器校验固定分母、逐配置唯一性、输入身份、独立 checker、证据文件哈希、
失败阶段和误差单位/预算。缺少原始私有波形不会抹掉历史收据；缺少收据或
精简分析则不能声称本地复验。重复配置、删掉失败、把旧工件称为当前工件均会拒绝。
同一组在当前子集没有条件时显示“不适用 N=0”；待冻结集显示 pending 和 N=unknown。

不覆盖既有快照。维护的TABLE指向当前派生快照；历史表保留。新文件可用下列命令生成：

```sh
python3 -B experiments/backends/comparison/derive.py \
  experiments/backends/comparison/snapshot-20261006-accounted.json runs/cmp/new-derived.json
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

## 本次执行与复用边界

本次启动16个仿真配置，无重复仿真；两个容器身份预检失败，未启动其16个配置的编译或仿真。
Spectre首项仿真后，设置审计误导入旧同名模块；修复为精确模块路径后复用已有首项波形，
再执行剩余7项。阶段命令/日志保持原哈希，收据同时保存初始及分析脚本身份。
[evidence/sources](evidence/sources/)保留实际执行版本源码，含初始、恢复及失败预检版本。
当前runner是维护入口，其哈希不替代实际运行脚本。原始波形与完整阶段日志仅在本任务runs/cmp保留；
仓库内精简收据和分析可独立校验身份，但没有原始波形时不能声称重新执行。

`ingest.py`验证返回工件清单及冻结输入，再把执行收据或失败预检导入一个新快照。
预检失败保留T、基础设施阶段和原错误，不记为模型不支持。修改目标runtime时旧结果自动标stale；
新实验需另行分配资源，不使用维护命令隐式重试。

## integration EVAS8 刷新

`refresh.py` 只做固定 `cmp8-base` 的静态合并，不启动后端。先在获授权的最终integration
版本生成独立fresh快照：8个EVAS/base是真实新执行，外部24项未执行；随后与parent快照合并。
维护表的EVAS8指向fresh实际receipt，Spectre8标reused并绑定原receipt，其他16项保持T/unrun。
这些T的环境失败理由来自原预检，本轮没有外部启动、安装环境或重新确认可用性。

schema2的receipt复用只允许在有界refresh中使用。两份小输入manifest/provenance归档到新的
证据目录；物理condition、DUT、设置、Spectre deck、checker及外部runtime均须匹配。
整份manifest因EVAS runtime/provenance变化可以不同，原Spectre receipt的manifest身份不改。
原measurement/run_id、observation、waveform/metrics、原32分母以及无关历史/application
候选保持。新EVAS的八项必须属于一个新执行身份，失败/timeout仍按X/I进入同一分母。
旧schema1/schema2、matrix复用及静态derive保持兼容。

```sh
python3 -B experiments/backends/comparison/refresh.py PARENT_SNAPSHOT FRESH_SNAPSHOT OLD_INPUTS NEW_INPUTS NEW_SNAPSHOT --evidence NEW_COMPACT_PROOF_DIR
python3 -B experiments/backends/comparison/records.py NEW_SNAPSHOT --output NEW_TABLE.md
```

输出文件必须不存在；检查新表后，将维护入口 `TABLE.md` 更新为该内容并绑定新快照。
这两个静态命令不授权build或simulation。一般ingest仍拒绝覆写已测配置；fresh执行必须由新的
run/receipt生成，不以换一个revision字段冒充实测。所有旧snapshot/receipt文件保留原字节，
新维护snapshot以path/SHA绑定parent和fresh；工具新增本身不表示最终integration EVAS8已运行。
