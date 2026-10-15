# IR23 接口与失败语义

生产者与内核必须同时使用 schema 23。旧 IR 不静默迁移。新增 wire 节点：

| 节点 | 字段 |
| --- | --- |
| `kind=loop` | `initialize:[Statement]`, `relation:lt/le/gt/ge`, `left`, `right`, `body:[Statement]`, `update:[Statement]`, `origin` |
| `op=checked_integer` | `value`, `origin` |
| `op=checked_index` | `index`, `first:i32`, `last:i32`, `origin` |
| `op=array_read` | `states:[usize]`, `index`, `first`, `last`, `origin` |
| `kind=array_write` | `states`, `index`, `rhs`, `first`, `last`, `origin` |

首片 Loop 只接收 scalar integer 控制、同一控制变量的一条初始化与更新、方向一致的常量非零整数步长；循环体不能写控制变量。运行时重新读取每次条件及变化后的终止边界，4096 是事件级全循环共享预算，不由 wire 字段放大。仍为真时耗尽预算返回 `event_loop_budget`，没有成功截断。

`states[k]` 对应升序声明索引 `first+k`。内核验证映射非空、无重复、长度恰等于边界跨度、每个 ID 合法、同一 owner 与元素类型；静态 writer 集合包含所有可能槽位。读取和写入各自检查下标，不能依靠 wrapper 存在而省略。写入的 index 和 rhs 都读取本条语句写入前的候选 frame，之后只改选中的槽位。没有跨语句或跨循环迭代的数值缓存。

`checked_integer` 要求有限、整数及 signed32；它保存每个源 typed 算术中间节点的失败义务，不能只检查最终抵消结果。它不是实数到整数的泛化转换；源整数商余保持向零截断的原 lowering。`checked_index` 另检查原闭区间边界；数组节点也独立防御畸形 raw IR。

动态取值失败使用 `integer_range` / `array_index_range` 并保留源 origin。结构校验遍历未选分支和死代码；运行时 `Select` 未选臂不求值。未知或非事件位置明确拒绝。所有新语义受原候选提交/失败回滚控制，包括已接受前缀之后的失败与同控制器重试。普通 output/strobe 观察不能增减事件迭代或改变轨迹。
