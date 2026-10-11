# Astra T1 修复增量复核

固定审查范围为 `fe60e30693305b9316f0e1754b8df5a43a54e911..1469bda0a271e51c0498e677e1c3e3141439f1a6` 的 foundation reference 和对应测试。通过 `git show` 在内存载入固定文件，未依赖会继续变化的工作区代码。

前轮两项 P2 在 T1 卡片和 reference API 范围内已解决。本次增量没有新 P1/P2 发现。共享 checker 正确传入经过验证的同行计数阶段，仍属于其独立集成审查义务；本结论不替代该检查。

## 两项修复核对

1. `precision_breadth_foundation.py:293-325,337-341` 新增 `reference_counter_stages`，检查计数器身份、整数类型及初末值范围。F07 的 first/last/y 和 F19 的 state 使用已验证阶段；F19 的连续 transition 仍使用原全局 callback 窗。

   我重跑原反例，F07 的变化行现在返回 first=[1,1]、last=[12,12]、y=[13,13]、count=[1,1]；F19 同类行返回 state=[.5,.5]、count=[1,1]。另在 1.5 µs 固定 count=1，点 callback 参考 y 约为 `[.24999999999998654,.2500000000000137]`，完整合法 callback 窗的参考为 `[.24989999999998652,.2501000000000137]`。因此离散阶段修复没有裁掉连续历史的不确定度。

2. `precision_breadth_foundation.py:144-152` 增加 `F09-reordered` 和 `F10-reordered`，分别交换实例声明与贡献顺序。同 group_id、相同数学答案，源码确实不同。卡片现在共 20 组、44 个必测变体。新增测试核对不同 source 及共同时间点上的相同 reference。

## 时间盒与 ddt 边界

`precision_breadth_foundation.py:328-381` 默认采用 `16*ulp(stop)`，并接受 checker 显式传入的非负有限 `reference_time_uncertainty_s`。参考返回 `time_uncertainty_included=True`，避免 checker 再以输出斜率重复追加同一项。时间盒仍在已声明物理域内截到 start/stop；这不改变 callback 窗。

F20 的 wrap 判断使用整个时间盒的未包裹相位。最近的两个 binary64 邻点若仍跨 wrap，会保留 `[0,1]` 普通电压范围，不被当作确定一侧。sin 的 Lipschitz 扩张仍存在，未因较宽时间盒改成只取端点。

F14 只有 `time_s` 精确等于已声明折点才标 undefined。折点的相邻 binary64 行不再伪装成数学无定义点，而是按时间盒返回两侧值。独立复核 T 左右最近邻均返回 `[-1,.5]`，2T 左右最近邻均返回 `[-1,0]`，并且 undefined 为空。精确 T、2T 仍需共享 checker 验证卡片的左右观察义务。DC phase 必须有外部证据的原要求保留。

事件 metadata 也已统一为 early_s/late_s 偏移量，默认 reference 在读取时转换为名义时刻减 early、加 late。timer 为 ±100 ps，cross 为 [0,100 ps]，与源码常量一致。

## 执行证据和边界

- 固定提交的全部 22 项 foundation 单元校准重新执行，22/22 通过。
- 重新执行两种原计数阶段反例、连续 callback 区间保留检查，以及两个 ddt 折点四个最近邻检查。
- 读取 `foundation-compile-preflight.json`，独立核对 44 个 ID、每个 source SHA256 和 reference 文件 SHA256，均与 `1469bda0` 相符。该收据明确标为 compile-only；原 42 个相同源码记录复用，两个反序源码单独编译。此次没有再次编译。

没有调用 EVAS 内核、其他后端或远端任务。22 项通过是数学参考和卡片 API 的校准，不是四后端数值对齐。前轮关于基础闭式解、Taylor 余项、exp 区间及 dyadic NP/ND 绑定的审查可沿用；它们未在此增量中改变。
