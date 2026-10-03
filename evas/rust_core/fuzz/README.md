# 内核模糊测试

在 `evas/rust_core/` 运行。需要 nightly Rust 和 `cargo-fuzz`：

```sh
cargo install cargo-fuzz --version 0.13.2 --locked
rustup toolchain install nightly --profile minimal
mkdir -p fuzz/corpus/parse_request fuzz/corpus/run
cp fuzz/seeds/static.json fuzz/corpus/parse_request/static.json
cargo +nightly fuzz run parse_request -- -max_total_time=60 -max_len=65536
cargo +nightly fuzz run run -- -max_total_time=60 -max_len=24
```

`parse_request` 处理任意字节中的 UTF-8 JSON，检查解析入口不会 panic。
`run` 从一个小型合法静态请求出发，改变节点索引、维度、系数、容差和表达式。
原始浮点位模式包括 NaN 和无穷大。合法变体可以成功，非法变体应返回错误，不能 panic。
后者有意限定资源与模型大小，尚未覆盖一般瞬态程序、历史或事件组合。

`seeds/` 是固定起点；自动生成的语料、崩溃输入和构建产物分别在忽略的
`corpus/`、`artifacts/`、`target/`。发现崩溃后，先保留并最小化输入，再写普通回归和修复。
有限时间内未崩溃只说明该轮未发现问题，不证明任意输入安全。
