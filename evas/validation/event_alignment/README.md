# 事件与下游历史的工程对照合同

这组资产检查 7 个小模型的有限共同观察点、事件 stamp、独立来源计数和样本。
T1/T2/C1/C2/M1/H1 是要求完整正确输出的工程用例；N1 是可分辨近邻时间用例，单独统计。
N2 的亚 ULP 物理阶段诊断不在首批资产中。

实现、源码冻结、Spectre 执行和 EVAS 判定是不同事实。本目录没有运行模拟的证据。
独立检查器不导入 EVAS，不把 Spectre 当作数学 oracle，也不宣称连续时间精度证明。
实际 Spectre 执行由外层 runner 负责，并在执行前冻结模型、card、checker 和 deck 哈希。
模型或条件修改必须采用新 identity，旧结果不能改写成新模型的结果。

## 端口与 card

每个 `dut.va` 的顶层是 `probe(u,clk,y,z,q,n,m,s,h1,h2,h3,r)`。
`u` 和 `clk` 是 PWL 输入，`r` 接地，其余为显式电压输出。
内部标量使用 `state_n/state_s/state_h1` 等名称，避免与电气端口重名。
所有未使用输出仍显式定义，不能用缺信号代替零值。

`case.json` 必需字段如下。

| 字段 | 含义 |
| --- | --- |
| `id` | 用例 identity 名称 |
| `stop` | 工程时域终点，秒 |
| `times` | 要求出现的共同观察时间，含均匀网格及显式锚点 |
| `inputs` | 输入端口到 `[[time,value],...]` PWL 的映射 |
| `voltage_nodes` | 每行必须提供的命名输出 |
| `description` | 模型的问题 |
| `criteria` | 冻结预算、事件来源、stamp 和期末计数 |
| `settings` | EVAS 设置与两档 Spectre 设置 |
| `module/ports/ground_port` | runner 的顶层绑定信息 |

Spectre 的 `strobeperiod` 只覆盖均匀网格，runner 还必须落实 `times` 中的非均匀锚点。
需保存所有命名信号和 accepted-point 数据。禁止只保存稀疏计数后猜测回调次序。
检查器对缺少共同点的运行报告失败；不得通过插值补出名义必需点后称为实际同点输出。

两档Spectre设置同时收紧容差和maxstep，因此是两配置稳定性检查，
不能据此把结果变化单独归因于某一个设置。

## 模型与独立答案

以下时间以 `U=1 us` 表示。每次事件保存 `V(clk,r)`，独立输入为 `clk=t/U`。
`h1/h2/h3` 初值为 -1，发生后保存该事件的时钟采样，且之后保持。

| id | 事件与波形 | 主要观察 |
| --- | --- | --- |
| T1 | 2U 置1，6U置0；d=.25U，tr=1U，tf=2U | 延迟、两条完整边沿、目标、两个计数 |
| T2 | 2U置1，2.5U置0；d=2U，tr=tf=1U | 4U起升，4.5U达.5，5U归零，队列不吞脉冲 |
| C1 | u=t/(2U)，上穿.7；采样u为目标；d=.25U，tr=tf=1U | 根、样本、目标与边沿共用事件时刻 |
| C2 | timer 2U置1；u=t/U上穿6时采样y并置0；tr=10U，tf=20U | 中断样本.4，反向斜率−1/(20U)，14U归零 |
| M1 | T1同一事件目标同时驱动 `idt(1e6*a,0)` | 积分面积与transition起点共用实际事件时刻 |
| H1 | A原定6U，2U改到4U；B原定7U，5U禁用 | A一次、B零次，两个旧根不残留 |
| N1 | 2U timer，2U+5ps cross，2U+10ps timer | 三来源独立输出、stamp严格次序，最终y=111 |

transition 的独立答案由线性边沿合同推导。若实际事件时刻以 U 归一化为 a,b：

- T1/M1：`y=clip(t-a-.25)-clip((t-b-.25)/2)`。
- T2：第二activation前为`clip(t-a-2)`；之后为`max(0,b-a-(t-b-2))`。
- C1：样本和平台为`a/2`，`y=(a/2)*clip(t-a-.25)`。
- C2：中断样本`(b-a)/10`，前段斜率1/10，后段斜率−1/20。
- M1：`z=1e6*U*(max(0,t-a)-max(0,t-b))`。

这里 `t` 也以 U 归一化。以上公式明确使用同一组持久stamp，禁止按每个查询点重新拟合事件时刻。
T1/M1的第一边沿必先完成；T2和C2的中断方向、历史起点在冻结事件窗口内不改变。

## 冻结预算和判定

普通 timer/cross 时间窗口为1ps；N1的cross为.1ps，其timer仍为1ps。
电压预算是1uV，样本与stamp预算分别是0.1uV。
stamp的0.1uV观测预算经时钟斜率换算为0.1ps；检查器单独报告该不确定性和相对名义窗口的位移。
一个stamp点落在名义窗口外最多0.1ps，只有在其观测区间仍与声明窗口相交时才可解释。
这是有限stamp观测的不确定性，不是修改timer的时间容差。
下游波形预算仍保持1uV，样本预算仍保持0.1uV。

每例必须成功输出，从0覆盖到stop，信号有限、时间有序，并包含全部 `times`。
为避免十进制导出和末位表示误差制造工程假失败，coverage/grid匹配允许
`max(1fs,64*ulp(stop))` 的时间表示差。
精确停止边界另作诊断，本合同不据此证明亚ULP事件或隐藏回调。
离散输出位于stamp数值误差形成的事件包围内时可采用前态或后态，
但同一观察点的所有离散消费者必须共享同一个事件发生标志。
各观察点的前/后态要求还必须相交于同一个全运行事件时刻区间，不能先后反转；连续输出仍检查。
窗口外的计数、样本、目标和stamp必须符合这一次固定历史。

检查器先验证最终stamp、名义窗口、严格来源次序和独立期末计数。
随后用同一组stamp检查全部观察点，包括stamp持久性、积分面积和transition波形。
报告还给出全运行共同事件时刻可行区间，边界观察不能各自独立选择发生时刻。
本批模型的stamp初值为−1，事件后值至少为1.4，远大于数值预算。
每行stamp因此唯一决定该事件前/后态，检查器不使用贪心best分支选择。
全部消费者采用这一个前/后态，全部行再约束同一个可行时刻区间。
缺输出、缺共同点、超预算、错误计数、拒绝、超时和没有波形都不能算工程通过。
N1的有限stamp次序不等于隐藏callback次序的完整证明。

## 检查接口和校准

规范化输入为：

```python
rows = [{"time": 0.0, "voltages": {"y": 0.0, "z": 0.0, ...}}]
result = inspect(case, rows)
```

可选 `decimal_tokens` 是相同长度的行数组：

```python
decimal_tokens = [{"time": "0", "voltages": {"y": "0", ...}}]
result = inspect(case, rows, decimal_tokens)
```

token保留原导出十进制精度，不提供原本未观察的回调证据。
CLI接受纯rows数组，或包含 `rows` 与可选 `decimal_tokens` 的对象。

```sh
python3 -B evas/validation/event_alignment/checker.py \
  evas/validation/event_alignment/T1/case.json /absolute/path/normalized.json
python3 -B -m unittest discover -s evas/validation/event_alignment -p 'test_checker.py' -v
```

校准的正控由独立手算PWL锚点和积分面积生成，不调用checker的reference函数。
负控覆盖错误共享时间、错误采样、中断样本、吞脉冲、撤销根残留、改期根执行错误、
漏来源、错stamp、stamp漂移、缺网格、缺信号、非有限值和不完整运行。
它们验证检查器可以检出这些可观测错误，不代替模拟器行为测试。

同机release性能比较仅在冻结模型的正确性通过后进行。两版本输入、输出要求和精度预算相同，
同时记录实际事件数、输出点数和失败情况。工作量不等或运行拒绝时不报告速度比。
