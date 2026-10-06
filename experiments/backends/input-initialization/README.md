# 输入比较初值与共享计数的实际配对

[紧凑证据](evidence.json)记录源码提交 `ee7df138e312d220dd01d3b099a8d4adb259ff65` 的八例 EVAS／Spectre 开发配对。八例均在执行前固定的有限观测预算内符合独立答案。原 EV-HC-01、EV-HC-02 的论文资格仍为 **I**，这份证据不增加原十二卡分母，也不声称连续时间保证或公开完整复现。

## 问题与范围

原迟滞模型有两个缺口：HC02 在 `initial_step` 读取输入比较来决定初态，HC01/HC02 在两个异刻事件块中更新同一计数器。本次配对检查真实启动电平、严格与非严格相等、两个异刻 callback 的次数和输出切换。

| 实际配对 | Spectre 初值 `(out,count)` | 计数序列 | 独立答案与预算 |
|---|---|---|---|
| 原 HC01 | `(0.1,0)` | `0→1→2` | 原卡／oracle，输出与计数标记 0.001 V |
| 原 HC02 高输入 | `(0.9,0)` | `0→1→2` | 原卡／oracle，输出与计数标记 0.001 V |
| HC02 低输入 | `(0.1,0)` | `0` | 冻结恒定输入答案，1e-7 V |
| HC02 `>` exact tie | `(0.1,0)` | `0` | 同上 |
| HC02 `>=` exact tie | `(0.9,0)` | `0` | 同上 |
| HC02 `<` exact tie | `(0.1,0)` | `0` | 同上 |
| HC02 `<=` exact tie | `(0.9,0)` | `0` | 同上 |
| HC01 整数共享计数变体 | `(0.1,0)` | `0→1→2` | 原 HC01 物理答案与窗口，0.001 V |

六个开发变体独立列出，原论文 DUT、卡、阈值和 N 保持原字节。上述 allowance 是预先固定的开发比较预算，不能充当求解器或导出的数学误差证明。恒定控制最大输出观测差不超过 `2.78e-17 V`，均低于原 `1e-7 V` 预算；三个动态例的最大输出观测差为 `1.11e-16 V`。

## 判断来源与方法

唯一科学判断来源是已发布提交 [`cf14a9e654668b027d02413d774f11627cfe7ba0`](https://github.com/BucketSran/vaEVAS/tree/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper) 的 [原卡](https://github.com/BucketSran/vaEVAS/blob/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper/core-v1.json)、[oracle](https://github.com/BucketSran/vaEVAS/blob/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper/oracle.py) 和 [criteria](https://github.com/BucketSran/vaEVAS/blob/cf14a9e654668b027d02413d774f11627cfe7ba0/evas/validation/paper/criteria.py)。分析时核验这些文件与固定提交一致，直接调用原 `event_limits`、`values`、`pwl`；这里没有复制新的科学 checker。恒定 tie 答案在执行前按实际关系运算固定，整数变体沿用 HC01 的同一物理答案。

原生 `count` 初始为 0，每次只增加 1，最终为 2；相邻实际记录夹住每次变化，括定须与原单向合法窗口相交。输出再共用这一个计数历史，不能逐端口挑不同 callback 时刻。两后端分别检查独立答案，Spectre 不作为 EVAS 的 oracle。跳变中的精确时刻和左右记录可不同；没有跨跳变插值或强迫两个后端在中心具有相同 stage。原卡窗口、anchors、未裁切括定及原始请求／响应 SHA 均保留在证据中。

实际 Spectre 为 `21.1.0.509.isr12`。保留 global `reltol=1e-5`、`vabstol=1e-7`、`iabstol=1e-12`、`maxstep=200ps`、`traponly`；conservative 分析的 effective `reltol=1e-6` 按已安装合同解释，旧收据的 inconsistent/I 不覆盖。EVAS 沿用冻结公开开发请求 `absolute=1e-12`、`relative=1e-10`，不宣称两者误差控制等效。

三批实际版本探针和八个具名 Spectre 主运行都保留工具、命令、退出、资源上限与清理收据。全部具名例的记录数等于 accepted steps 加初始行；结合 `strobeoutput=all`、`skipdc=no`、直接 q/n 节点贡献及安装合同，支持这些简单模型的原生初值与计数观测。行数和格式本身不能建立任意电路的原生或数值资格。

## 已知限制

七例实际末点略早于名义 stop，均没有 parsed-float stop 相等记录；整数共享计数例覆盖 stop，并在当前 Python float 解析下与名义 4us 相等。`exact_stop_rows` 仅统计这种 parsed-float equality，不是 raw／deck 十进制 token 的精确相等，也不是中心身份或 serialization 误差证书。整数例原始末时间 token 为 `4.000000000000000e-06`，deck stop token 为 `3.9999999999999998e-06`，精确 Decimal 差为 `+2e-22 s`。没有修改 raw 时间或补写缺失端点。原 HC01／HC02 用原 observation qualification 再经 `criteria.assess` 返回 I；原生来源说明不替代严格 ASCII 导出误差界、输入／电压独立误差证书、精确中心身份界或终点覆盖。

本次八例实际覆盖四种关系的 exact tie、原始高低启动和 real／integer 的异刻共享自增。一般仿射驱动组合、同批冲突／回退、整数减法与溢出边界、t0 timer／算子历史顺序仍只有本地回归或其他既有证据，未由这八例外推实际 Spectre 对齐。

## 身份与材料可用性

`evidence.json` 是 **repository-contained** 摘要，含八份完整 DUT 文本与源码 SHA、deck／输入／期望／checker 身份、EVAS 源码闭包与 kernel SHA、实际 Spectre 版本／二进制／setup SHA、请求及响应、执行命令、原生波形／收据和三批归档／清单身份。EVAS CLI 的 `build_revision=null` 原样保留，不伪造发布构建身份。

大波形、完整请求／响应、安装文档和一次性分析脚本均为 **local-only**，在证据中以 vaEVAS 工作区相对路径和 SHA 识别；它们不是下载链接。三份 raw 归档的清单已核验，分别为 104、92、92 文件；原批次还包含本报告以外的科学执行，不将这些额外条件计入本报告八例。取得持有人授权的原材料与相应 Spectre 工具／license／setup 后，才能核验或重新运行。仅有这份摘要不能宣称完整公开复现。

本地分析命令和脚本身份已记录：先 `cargo build --locked`（`evas/rust_core`），公开编译 DUT 后向 Rust kernel 传递冻结 JSON；五例运行最终源码，追加三例在核验相同 kernel／源码闭包后复用已冻结 EVAS raw。实际 Spectre 由已有 runner 的有界 stage 执行，本分析不启动远端、不重试、不更改 source 或 tolerance。
