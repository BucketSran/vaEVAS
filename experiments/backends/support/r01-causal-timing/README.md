# R01 原 timing 任务与有限对照证据

固定 c5bad 核实际在 **111.992 s** 内完成原 timing-0（原限额 120 s，9001 行），冻结原 checker 和 **2219 项 protected circuit 检查通过**。这份包保留结果身份与有限摘录；完整原 raw 仍在本地。运行 `python3 -B verify.py` 可校验 retained 文件 hash 并复算有限数值，不运行模拟器，也不宣称从公开完整波形重跑原 checker。

修复覆盖实际阻塞：连续历史与被动 observer 分开维护；事件期限及查询侧保留因果身份；initial observer 读取已稳定初态时，不再把 Riccati 预测越过已知未来 timer。原 initial 控制在 parent bcaa 上耗尽 16384 trial；同源 c5bad 控制及更紧精度实际 Spectre 五点对照通过。实施能力以代码、冻结来源和实际回复为准，不从模型评论或有限控制推演更广支持。

| 证据 | 保留的结果 | 仍受的限制 |
|---|---|---|
| 原 timing-0 | 最新原任务完成 1/1；55 条记录的类型次数相同，62 个 reference 时间字段；291 个边沿窗口外的有限点通过 | 比较沿用原插值、排除原 5 ns 控制边沿窗口；不证明完整全时域或隐藏 callback 左右侧 |
| N09 六个原控制 | 0538 历史同源 6/6；最新 c5bad 同分母 6/6、44 个原 native time、169 个电压配对 | 两次核身份分别保留；六控通过不扩为完整全时域准入 |
| 三个 deadline，ordinary/forced | 已有前四点及独立解析全点通过 | 原精确末点 .5 缺失，完整原生配对仍 0/6；v2/v3 pilot 仍缺 .5 |
| 两个 passive history | 每例已有 4/7 精确点电压通过，Display 一次 sample 1 | 完整仍 0/2；中/上邻位及 .75 缺失，下邻位 Spectre count=1 与原数学/DUT count=0 不同 |
| Initial Riccati v1/v2 | v1 .5 超预算且缺2；授权更紧精度 v2 原 5/5 native、1e-8 V 数学/配对及 initial=1 一次通过 | 两版无 explicit ground，实际 Spectre 自动 gmin；v1 失败不删除 |

原任务有限对照最大 held1 差 **19.8972 µV**、serial 差 **16.2382 µV**，均低于原 2 mV。sample_time 输出用 `1e-6 s/V` 编码：最大差 `5.005562631055227e-11 V` 对应约 `5.006e-17 s`，原 `0.00025 V` 门槛对应 `250 ps`。不能将电压差直接读为秒。包内保留原字段、实际 bracket 和单位映射，逐点复算得到原收据最大差。

原 fresh 实际 Spectre 与历史同四文件/原设置，12024 native 行的 VALUE 正文字节完全相同，支持复用已完成的 fresh 参考；header 日期和完整文件 hash 区别保留。实际工具 21.1.0.509.isr12、binary/profile 前后 hash 与 effective settings 分别记录。原参考 reltol 请求1e-6、实际1e-7、gear2only；新 passive/initial 对照的请求与实际精度另列，不能互相替代。

原 Display 用 %.12g，reference 的 62 个时间字段没有对应精确 native token；原 checker 使用线性插值及原字段预算。deadline/passive Display 本身无时间戳；AHDL count/seen/q 是实际保存的有限状态，不能伪造 callback 根证据。缺 native 不插值、不缩分母；所有非有限和超预算负校准保留。

HISTORICAL-FAILURES.json 保留 11 次原 full 失败的核/输入身份、耗时、限额和诊断；initial parent 红与 v1 reference 失败另随 fixture 保留。原 70 项没有整体重跑，原 16 项最新合格集合为12/16，首次11/16与c2超时保留；同核c2原120s下单例复测42.912s通过，4项joint-affine缺口不变。合并已复核17项为13项完整+原checker通过（附加finite输入有六项差值失败，另见retained-old16）；另53项未当前验收，不能作13/70正式总成绩。这里新增原 timing 完成这一项，**不改 Q 表、不作 Q3 声明**。

`PACKAGE-MANIFEST.json` 校验包内字节；`ORIGINS.json` 区分来源文件 SHA 与规范化后的文件 SHA，后者由包 manifest 给出。source/deck 是同字节有限输入；收据摘录去除机器私有路径。`build_extracts.py <local-run-root>` 用显式提供的本地证据目录重提取，读取 bulk 但不运行模拟器；源完整 raw、ELF、机器 profile 和远端 runner 不在包内。包约 0.94 MB，保留全部 291 点 bracket 与有限原生记录；没有公开 archive/download 或完整 raw 重现的承诺。
