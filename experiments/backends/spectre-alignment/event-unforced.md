# 无近根强制 strobe 的事件控制

新增4次Spectre数值调用、0版本，均完成并确认清理；本次r3仅重分析既有输出，0新调用；累计70/24。required anchors仅0/stop，每例54个原生行。首批freeze与缺root anchor判决不变。完整字段见[event-unforced-evidence.json](event-unforced-evidence.json)。

| 条件 | 执行 | 有限观测检查 | 存储callback相对数学根延后 | sample误差 |
| --- | --- | --- | ---: | ---: |
| wide/on | completed | physical_event_time失败 | 737.036ps | .772839mV |
| wide/off | completed | x/sample/count通过；callback time未观察 | 不可用 | .772839mV |
| tight/on | completed | 所有可观察义务通过 | .454747ps | .000476837mV |
| tight/off | completed | x/sample/count通过；callback time未观察 | 不可用 | .000476837mV |

表中延迟取stop处最后一行观察端口；wide/on逐27行latched读值的延迟范围为737.036209841–737.036267916ps，最大737.036267916ps，极差约58.075as。tight/on逐27行均为.454747350834ps。firedtime是latched real经电压端口输出后的观测值，非直接内部事件trace；微小漂移保留，不能据此推断多次callback。冻结checker已逐行检查100ps义务。

外部时间预算仍100ps、sample预算仍1mV；allowed localization window=min(ttol,expr_tol/slope)；expr_tol=.0625V、slope=2^20V/s，wide ttol=2^-24s对应59.604644775390625ns，tight ttol=2^-40s对应.9094947017729282ps。两组on的全部逐行值都在各自窗口内；wide符合该窗口不能抵消物理时间失败。off窗口内与物理时间判定仍unknown，不能补推通过。两组off/on逐54个native时刻公共输出与时间网格完全相同，不能据此给off补造隐藏callback time。相对于首批，移除的是含root的整组近根forced strobes；这揭示该例的callback/sample差异，尚未隔离是哪一个被移除的strobe造成影响，不外推一般事件规则。

同一合法observer-off源的两次EVAS原生同点请求均完成，0版本；每例54/54精确配对，无超stop、无未配对行。EVAS采用数学根sample=.375，wide/tight样值最大差分别.772839mV/.000476837mV，均在固定1mV内；count一致、x最大差1.11e-16V。on源的`$abstime`拒绝保持，不能称on源完整对齐。EVAS EventRecord.time是nominal/代表数学根事件点，不是Spectre实际callback `$abstime`。

实际effective reltol从请求1e-5收紧为1e-6；vabstol=100nV、iabstol=1pA、traponly。maxstep请求2^-25s，显示29.8023ns；stop请求2^-20s，显示953.674ns：这两个显示值与请求的同值有限位显示相符，不是reltol那种真实收紧，也不能证明隐藏精确值不变。远端沿用串行90s/次、license30s、4GiB、单CPU/线程、32MiB/单文件、256MiB/条件轮询；本地只宣称串行90s。collection归档192046字节，科学manifest已逐文件核验，operator child_exit_code=0、cleanup_confirmed=true、余进程空。

一次派发前manifest metadata形状错误在本地检查中被捕获，实际0数值/0版本；原freeze/allocation与错误manifest保存在revisions/pre-dispatch-manifest-schema，修正后新freeze经root核验授权。没有模拟器自动重试。原17项独立checker校准及4例dry closure通过。r3 checker新增显式ports fail-closed合同与3项校准，总20项；原r2 checker/结果保留，新增分析预算不改，全部既有输出重新检查，0执行。

源码、raw、请求/响应、stdout/stderr与所有失败为本机local-only；本结果不签发paper P，不扩大PR79 exception，不完成源码/导出/stop资格。

工具复用身份文件SHA62466870…与本批TOOL_IDENTITY文件SHAb806ce14…不同，只因为后者新增identity_reuse收据字段。逐字段语义比较确认binary、binary_sha256、setup、setup_sha256、version、probe及其余原字段全部相同；去掉新增字段后的语义digest相等。文件包装hash变化没有更换binary/setup或产生版本查询；完整字段digest对照见证据JSON。
