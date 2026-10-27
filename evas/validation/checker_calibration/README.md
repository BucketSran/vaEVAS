# 检测器永久校准

从仓库根目录运行：

```sh
python3 -B -m unittest discover -s evas/validation/checker_calibration -v
```

该命令发现 22 个唯一控制身份，运行时不需要网络、runs 目录或内核。测试阻止 `subprocess.run`、`subprocess.Popen` 和未替换的 runtime `_invoke`。它只动态加载并执行五个明确指定的原测试方法，不导出原 TestCase。

## 控制及通过含义

- SourceMath 两方法各执行正确代表与窄 box、错误代表与宽 box、正确代表与宽 box，以及上下边界内和相邻 float 越界四种控制。独立答案来自原正指数 Decimal 公式和已归档控制。预算沿用原 request 的 `absolute=1e-12`、`relative=1e-10`，计算 `absolute + relative*abs(actual)`。边界使用精确有理数，两个相邻 binary64 值夹住预算边界，不新增容差。负控必须在代表或 box 的预算断言失败。
- DeferredRdist 合法原 validator 通过，原方法先验证原位置的合法 leaf，再逐项检查 function、seed、arity 的指定错误。内存 mutant 仅移除原 UnsupportedSystemCall 分支的两项签名与 seed predicate，必须出现三条 `CompileError not raised` 失败，不接受其他解析错误。fixture 固定被移除的原 AST。
- BoundStep 两方法回放历史 request、response 和 diagnostic。正确记录通过，掉初始解或错误时间必须经公共 `validate_response` 拒绝。既有错误末值控制继续由原数值断言拒绝。历史 DUT 输出只证明格式及检测器控制，不是新的独立科学 oracle。

22 项外层校准全部通过，含 9 项接受控制、13 项预期拒绝控制。方法内 subtest 另计，不加到外层测试分母。这些结果不授予 E1、仿真器支持或科学语义资格。

## Fixture 来源与维护

`fixtures/provenance.json` 列出每份固定 fixture 的 SHA256、字节数、原文件路径、原始字节 SHA256、原字节数及抽取配方。九份 JSON 来自既有 `test-scheme-audit/passing-oracles` 与 `passing-raw`，只压缩键和空白，保留所选 JSON 的全部内容。另一个 fixture 从固定 Git 的 validator 抽取两项原 AST。测试启动时核对 fixture 的 SHA 和大小。

原材料只读保留，抽取配方和原始字节身份见 `provenance.json`。普通 CI 使用仓库内 fixture，不访问历史目录。若原请求或检测器合同改变，应复核来源与受影响控制，不能直接更新 fixture 以隐藏检测失败。

该目录属于 `evas/validation` 的检测器接受与拒绝校准。`provenance-paper` 作业通过上述命令执行这些控制；独立发现入口将方法登记到同一资产目录。普通 EVAS 回归仍单独执行，不能以检测器校准代替实际 DUT 观察。
