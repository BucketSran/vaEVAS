# R01 timing observers 的17项有限控制

七项array、六项frontend、四项passive控制，在原1e-9 V预算内分别满足独立数学答案，并与同源Spectre原生点配对通过17/17。共63个时刻、66个电压值。积分0.875秒两后端差1e-16 V，其他差为0。这不是新的完整整题通过；原timing仍有 `kernel.unsupported_operator`，原70、19、16和Q统计保持不变。

在本目录运行 `python3 -B verify.py`，可用标准库复算保留的17项有限gate。脚本检查文件SHA、同源输入、精确时间token、独立语句/连续公式、DUT与参考各自误差及两者差、passive状态与显示。校准拒绝超预算值、非有限值、非精确时刻和错误显示次数。它不导入EVAS，不运行kernel或Spectre，不访问网络。`CHECK-RESULT.json` 是实际运行结果。

每例保存VA、deck及passive的obs.va，有限DUT电压/界限/状态/事件/显示、精确原生token、实际API设置、参考有效精度及警告。最新DUT使用release核 `e13f60ee52e5fd558e08ddd468dff6d7c980bfce9daceb9c1e159682f240458a`，112项SOURCE与35项FRONTEND身份在 `source-identity.json`。DUT实际absolute=1e-9、relative=1e-6、maxstep=0.125、stop=1；stderr均为空。参考为Spectre 21.1.0.509.isr12，工具前后与清单复核身份在 `reference-provenance.json`。

原生token完整保留导出位数，时间精确匹配，不插值。独立答案复用执行前冻结的语句/数学判据，并由本包函数重新计算，未从DUT产生expected。array保持整数向零截断和余数符号；frontend保持循环顺序、参数选择和合法比较算术；passive保持状态、积分及边沿样本的有限答案。

`simultaneous-v1-failure.json` 单列v1 PWL deck的SFE-23、returncode=2。该次是配置失败，没有语义结果；后续仅修正 `type=pwl` 后v2成功，原VA、观测器、预算和查询保持。17项成功采用此v2及另三项passive v1成功，没有让历史失败从证据中消失。

Spectre passive Display没有 `$abstime`，保留的进度前缀不等于时间戳。DUT显示自带时刻，参考只能直接比较文本顺序、值和次数，不能将DUT时刻假造为Spectre callback测量。`selection_arm` 隐藏x的0、1、1仅由DUT状态证明，Spectre恒定输出y=1不能独立证明隐藏回调。全时间域、任意同刻排序及广泛组合均不在本包证明范围。

`SUMMARY.json` 保存原timing拒绝的紧凑identity、diagnostic代码和原iabstol/errpreset被忽略警告，不复制原bulk checker。四组完整raw仅本地可用。归档SHA是身份标记，不是公开archive或可下载承诺。

`ORIGINS.json` 标明上游保留stage文件的SHA；各例 `stdout_sha256` 和 `extraction.source_stdout_sha256` 是原完整本地stdout的SHA。`PACKAGE-MANIFEST.json` 的 `normalized_sha256` 是本包路径规范化、有限提取后文件的SHA，两者不能混用。VA/deck/obs逐字节保留，输入SHA相同。manifest覆盖除自身和运行结果之外的文件；`CHECK-RESULT.json` 不作为新的数值oracle。

原全量本地回归1548项中，仅旧诊断位置断言失败；补回错误位置后40项相关检查通过。
最后一次诊断修正和空match臂格式调整后，原17输入已再次实际运行，完整stdout逐字节相同，
重新构建的release核SHA也相同。新源码身份与逐例前后SHA见 [final-source-adaptation.json](final-source-adaptation.json)；
原 source-identity 和执行收据保留，不替换为新身份。最终CI仍须检查本交付头。
