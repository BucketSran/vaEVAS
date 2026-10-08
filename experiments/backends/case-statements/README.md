# 有限标量 case 的 DC 对照

这份摘要重分析一次已完成的 Spectre 仿真和一次成功的 EVAS 请求。[固定模型、刺激与独立答案](../../../evas/validation/cases/case_statements/)使用五个 DC 输入 `0,1,2,-1,0.5`，普通 case 输出为 `3,3,7,9,9`，纯函数 case 输出为 `3,4,5,5,5`。它覆盖源码首个匹配、多标签、default 的位置及函数顺序赋值。

[comparison.json](comparison.json)保留双方有限样本、身份、设置及失败说明。绝对判据固定为 `1e-8 V`。九个冻结查询时刻的 90 个标量在 Spectre 原始网格中均有唯一实际样本。全部 16 个原生时刻的 160 个标量也与独立答案一致，双方最大差值为 `0 V`，没有插值。有限比较为 P，正式资格为 I。DC 刺激不能证明动态穿越相等边界、任意状态 case、四态匹配、运行时循环或分析生命周期，也不能证明连续全轨迹精度。

实际 EVAS 执行源码为 `3352f12d59574f0cf07f889966a891df1ac8b0e2`，输出报告 `evas-events-0.14.0` / IR18；内核 SHA-256 为 `51b8033a2d1f2d96c06773396f35273cff30618eb9bc12777321e91c1b3b687a`。JSON 的 `frontend_syntax_sha256` 专指 Python syntax.py，模型身份单独登记，不能混用。原 PAIR 把 syntax.py 哈希命名为 source_sha256，摘要纠正字段名并保留原 PAIR 哈希。协调者记录执行时生产源码干净，内核嵌入构建修订与独立请求协议版本未取得。后续文档和读回工具修复没有作为新源码执行证据。

Spectre 的实际版本为 `21.1.0.509.isr12`，二进制、设置脚本、执行 deck 与原 deck 的哈希见 JSON。为适配现有采集器，执行 deck 将分析名 tr 改为 tran，要求 17 位输出、九个 strobe 时刻及 traponly/iabstol。模型、刺激、独立答案和预算没有改变。EVAS 请求同一原生网格与 DC 输入，发送 `reltol=1e-6`、`vabstol=1e-9 V`、stop=1 s、max_step=.125 s。没有额外独立的 EVAS 有效设置读回。

Spectre 日志和 PSF 共同读回 stop=1 s、maxstep=.125 s、reltol=`1e-6`、abstol(V)=`1e-9 V`、abstol(I)=`1e-12 A` 和 traponly。`settings-readback.json` 的原行与作用域保存于摘要。原 RESULT 的 effective_settings 是 I，因为采集器未找到 requested_settings.json；原 RESULT 保留，没有改写为成功。后续读回是新的分析证据，不能改变旧记录。

最早本地读回工具不接受日志的 `125 ms`。维护修复扩展 SI 前缀，并通过单独 RED 回归再重新读取原日志/PSF。RED 文件保留在 `worktrees/operator-contract-closure/runs/issue-closure/readback-red.log`。最早配对脚本还错误读取每个 solution 的 time 字段，产生 KeyError；修正脚本从 `transient.times` 取时刻，并复用已成功的 EVAS 原响应，没有重跑模拟器。原脚本和修正脚本均保留在 `current/runs/issue-closure-20261008/analyze_case.py` 与 `analyze_case_v2.py`。这两次最早异常输出只有当时工具会话记录，没有独立可检索异常文件；不能声称全部旧失败输出都已归档。

[check.py](check.py)复用 [function-branches 的 PSF 解析器](../function-branches/check.py)，核对固定模型/答案身份、精确时刻、全体十个通道和完整分母。摘要入口重算双方对独立答案的误差及双方差值，并检查所记判决、数量和最大值。四个 fixture 哈希和十九个 raw 哈希的必需 key 集合必须完整，空映射、缺 key、额外 key 和非法 digest 均拒绝。执行身份投影由原 PAIR、原响应、TOOL_IDENTITY 和 PREPARATION 冻结，其摘要由检查器固定；关键身份字段不能与该投影分离。检查器还读取原执行提交的 syntax.py 验证源码哈希，不以当前 HEAD 替代原执行。raw 入口额外核验原文件哈希，从原 PSF/EVAS 原响应重建数值，核对 normalized.json 和摘要。映射和数组的形状必须明确符合协议，短电压数组或非对象电压表拒绝。异常数据返回 ERROR/2，数值失败返回 1，通过返回 0。摘要算术通过不能替代原数据身份核验。

从仓库根目录执行：

```sh
python3 -B -m unittest discover -s experiments/backends/case-statements -p 'test_*.py' -v
python3 -B experiments/backends/case-statements/check.py
python3 -B experiments/backends/case-statements/check.py --raw /path/to/frontend-reference-v1
```

13 项校准检查通过，包含独立接受、错值失败、缺点、重复/倒序时刻、缺失/额外通道、非有限值、伪造分母/最大值/身份、删除或清空哈希映射、伪造执行 head/内核/IR/模型身份与重复 JSON key 的拒绝。错值保留 90/160 完整分母。CLI 校准检查非对象电压表返回 ERROR/2、数值错值返回 1 且保留完整分母；短 raw 电压数组通过模拟身份门后的真实 CLI handler/adapter 校准返回 ERROR/2，此构造校准不是仿真或来源证据。共享 PSF 校准另检验截断、重复信号、第二 VALUE 段和非法行。raw 与摘要重算均得到 90/160、最大误差与差值 0，P/I。

原始 PSF、日志、双方请求/输出和收集清单是 local-only，位于拥有项目的 `current/runs/issue-closure-20261008/frontend-reference-v1/`；远端原始材料仍保留，执行通道锁已释放。收集归档 SHA-256 为 `1b5f830afebee09468c072539af74ec94ba267b6f6d085470e567c8643209f25`，清单核验 28 个文件。仓库保留维护输入、检查器和紧凑摘要，没有公共 raw 下载地址，因此不构成完整原始数据公开可复现的声明。发布与合并状态由现有 PR 管理。
