# PR14 / PR15 合并前验证

本目录保留原 PR14/15 协议，并在同一原条件矩阵下收纳后续新 EVAS 检查点。
本目录记录历史 analog/Spectre 对照、PR23 与 PR26，不作为当前 main 的能力清单。
最新 IR15 联合验证见[当前交付证据](../parallel-gap-integration/README.md#当前证据)；
[PR26 复位对照](RESULTS.md#idt-reset-merge-validation)及[收据](results/idt-reset-merge-validation.json)保留原身份。
大历史 JSON 采用无损 gzip，原路径/哈希与固定历史入口见[归档清单](../parallel-gap-integration/results/historical-receipts.json)。
`analog_matrix_compare.py` 可直接读取归档后的 analog 收据，`reused_receipt_sha256` 仍针对原解压字节。
它继续检查冻结运行时，不允许用当前 IR15 代替历史 `9c5d6c5` 的源码做原执行重判。

## analog 缺口对照入口

原 31 矩阵的冻结和 Spectre 执行继续用 `../dvs2-spectre-validation/run_suite.py`
与其 `remote.py`，EVAS 编译/执行继续用 `matrix.py`。本轮只新增分析入口和六个有理数
诊断；原 DUT、输入、两档设置与 checker 未改。逐项结果见[矩阵](results/analog-gap-comparison.md)。

以下命令从仓库根目录执行，使用新的目录；Spectre 命令在已配置的主机执行。

```sh
python3 -B experiments/pr14-pr15-validation/analog_boundaries.py build runs/NEW-BOUNDARIES
python3 -B experiments/pr14-pr15-validation/analog_boundaries.py evas runs/NEW-BOUNDARIES --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/pr14-pr15-validation/analog_boundaries.py spectre runs/NEW-BOUNDARIES --spectre-profile /PRIVATE/profile.json
python3 -B experiments/pr14-pr15-validation/analog_boundaries.py check runs/NEW-BOUNDARIES --remote runs/DOWNLOADED-SPECTRE-BOUNDARIES --output runs/NEW-BOUNDARY-ANALYSIS.json
python3 -B -m unittest discover -s experiments/pr14-pr15-validation -p 'test_analog_boundaries.py' -v
```

只发送冻结 `INPUT_MANIFEST.json` 所列输入及清单到新远端目录；不要发送本地 EVAS 产物
或私有 profile。远端结果归档包含全部 manifest 所列文件，下载后再分析。

`analog_matrix_compare.py matrix ROOT OUTPUT --old-root OLD_ACCEPTANCE_ROOT` 对本轮的
`ROOT/spectre-remote` 与最近验收 raw 工件配对，显式验证复用的源码、内核、输入和旧清单。
`analog_matrix_compare.py features ROOT OUTPUT` 分析 `ROOT/feature-affected` 三分支专项，
与同一 Spectre 矩阵核对共同输入。收据保存既定目录结构及原始身份；目前这些 raw 工件
仅本地/thu-sui 可取得，外部读者应另建新执行身份，不能将缺失归档当成复用成功。

## 原 PR14 / PR15 验证协议（历史）

以下记录合并前的冻结验证：执行阶段只验证，未改 EVAS 求解器、原条件或阈值。
后续交付状态见[能力总表](../../evas/docs/CAPABILITIES.md)，不回写本轮被测提交或结果。

- 候选：PR15 `e01fb5b69288118af39470800df3a9819cdd4a5f`，包含 PR14
  `36380248d0e427fa31ff73758b7617a4d4c23e86`。两个独立分支的内核分别复核 absdelay。
- 专项：6 个 absdelay、8 个 slew 场景，各两档；固定有理数折线为答案。
  初始历史、零延迟扩展、超出终点的延迟、仿射多源与参考、独立调用点、分数插值与增益、
  限速追赶、反向追赶、自然跟随、符号反射、拐点重合、斜率等于限值及时间尺度变化。
  EVAS 和 Spectre 各自验收全部导出点；共同 U/16 网格必须完整。
  电压目标固定为 1 mV，输入误差上限 0.1 μV。细化步长、相对及绝对容差，目标不变。
- 原矩阵：31 条件 × 四后端 × 两档 = 248 单元，全部新执行或新编译尝试。
  原 `conditions`、DUT 字节、基础/细化设置、`check_results.py` 不变。
  EVAS 列使用新内核的瞬态 API；明确拒绝仍在分母。另三列保持原固定版本。
  新内核的静态非线性能力不等于它能执行这些条件的瞬态分析。
- Spectre 每个配置 90 秒、许可证等待 30 秒、单线程；原容器每阶段 90 秒，
  不拉新镜像。同后端的同字节模型只编译一次，明确编译失败也保留并关联全部受影响单元。
- 使用新 `runs/pr14-pr15-validation-20260929-01/`，旧结果保持原样。
  冻结清单、源码/工具身份、实际设置、失败及原始输出分别保留；大产物仅本地/thu-sui 可取得。
  本轮不做速度排名，不声称完整语言或连续时间资格。

入口：`operators.py build/evas/spectre/check`；`matrix.py build/evas/analyze`。
构建原 Spectre 输入沿用 `../dvs2-spectre-validation/run_suite.py` 和其 `remote.py`。
开放后端沿用原容器运行器，生成快照仅修改本轮配置预算并省略旧 EVAS 的版本探测。

```sh
python3 -B -m unittest discover -s experiments/pr14-pr15-validation -p 'test_*.py' -v
```

原结果见 [31 条件矩阵](RESULTS.md#原-31-条件矩阵)，专项失败和只改变步长的追加诊断见 [RESULTS.md](RESULTS.md)。
本目录的脚本、数学答案、整理后的结果和收据随仓库发布；原始波形、日志和独立 PR14
全栈回放包装脚本仍仅本地/thu-sui 保留。外部读者可以检查协议与摘要、重新执行，
但目前不能下载本轮完整原始材料；不宣称完整公开复现。
