# 完整运行产物

将静态或瞬态 manifest 的完整结果保存到一个新目录：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas.results run evas/validation/smoke/idt.json \
  --kernel evas/rust_core/target/debug/evas-kernel --out runs/idt-output
```

`--out` 指定的路径必须不存在，已有文件或目录不会被覆盖或删除。
`--timeout` 设置数值执行的秒数上限，默认值沿用 runtime；内核身份查询另有五秒上限。
静态模式要求 `driven` 和 `samples`，瞬态模式要求 `transient`；缺少或混用模式均拒绝。

目录包含以下文件：

- `input.json` 保存原始 manifest 字节；`source-N.va` 保存本次编译使用的精确源码。
  记录保留原始路径、哈希与快照文件名映射。
- `request.json` 保存生效内核请求，包括已解析 IR 和电压容差。
  `result.json` 保留原始解码后的机器响应。
- `observations.csv` 首列为静态 `sample_index` 或瞬态 `time_s`，随后按内核节点顺序列出
  `<node>_V`，包括地。CSV 引号保留节点名称，有限 binary64 数值不做展示舍入，可往返恢复。
- `manifest.json` 是带版本的运行记录，也是唯一完成标记。它保存模式、观察数、列单位/映射、
  文件大小/哈希、源码/前端身份、所选包/内核身份及失败原因。

产物格式为 `bundle_version=1`。`manifest.json` 初始状态为 `running`。
响应通过校验且所有必需文件已关闭后，最后一次原子替换才能将其改为 `complete`。
校验包含 IR 与有序节点身份、精确行数、有限电压/诊断及请求的瞬态时间覆盖。
执行后再次核对所选内核哈希。build revision 和请求协议元数据沿用身份接口的显式未知值，
不能用当前 checkout 推断二进制来源。

输入/源码访问失败、编译拒绝、内核失败、超时、响应不完整或写入失败均返回退出码 2，
stderr 输出结构化诊断。可写时保存 `failed` 状态；若连失败记录都无法写入，
stderr 保留额外写入错误，完成标记仍为缺失或 `running`。
部分快照、响应或 CSV 可保留用于定位，但只有 `manifest.json` 的 `complete` 才表示完整运行；
`manifest.tmp` 不是完成标记。读取者还应核验记录中的文件哈希。

原有 JSON API 和 CLI 命令保持可用。本接口不提供流式输出、SCS save/export、分块取消、
打包或发布安装。源码快照可能包含客户数据，运行目录应留在所属客户/项目位置，不提交原始批量产物。

实现见 [results.py](../src/evas/results.py)，公共入口和文件写入失败回归见
[test_result_outputs.py](../tests/test_result_outputs.py)。独立静态答案为
`2*u+0.25` 在 `u=-0.5,0,0.75 V` 的 `-0.75,0.25,1.75 V`；
瞬态 `idt(1,0.25)` 在 `t=0,0.25,0.5 s` 的答案为 `0.25,0.5,0.75 V`，
采用 `reltol=0,vabstol=1e-9 V`，外部绝对容差 `1e-9 V`。
这些是本地产物序列化检查，不是仿真器资格或已发表后端证据。
