# 原生 Harbor 参考入口验收

37/37 题的 stock Harbor Oracle 实际参考 Trial 已通过，111/111 个终评条件全部 graded/pass，37 份完整归档的 5031 个成员已核验。分母包括全部任务；旧 ADPLL output_limit、POR timeout 两次未评分尝试及 024 初始化失败另列保留。作者校准、模型试做和原生参考入口是不同证据；本报告只确认参考入口，不能据此推导模型完成状态。

| 类别 | 题数 | 通过条件 |
| --- | ---: | ---: |
| spec | 19 | 53 |
| data | 1 | 6 |
| integrate | 2 | 10 |
| repair | 5 | 10 |
| test | 10 | 32 |

正式路径保留原 `solution/solve.sh` 为 `.source-solve.sh`，由 stock Oracle 原样执行，产生题目约定的 `/work` 输出。外层脚本随后运行机械提交桥接。桥接核对输出 SHA，调用同一个 `harness-public` 的 `evas_write` 与 `evas_submit`；CircuitAgent 在实际 NativeTrial 生命周期冻结最后候选，FrozenCandidateVerifier 用当前私有 package 独立终评。桥接没有模型调用、仿真或自造 agent 循环。同目录提交桥接与实际运行字节相同。data 题约定输出为 `/work/output/dut.va`，多文件任务必须在 binding 中列出全部参考文件。

```sh
#!/bin/sh
set -eu
sh /solution/.source-solve.sh
python3 /solution/submit-reference.py
```

Harbor 为 0.23.0。Oracle 适配源固定为 c29552d3b48944dde57016692d6c9508114d8c53，与已合并 dc13912d538f4b84ec69de468fe51caaafb7d049 完整 tree 相同。ADPLL 512 MiB worker 固定为 c88cb060a061096708a1906d46cefec95cdf8551；独立 bundle/profile 已部署，其实际受控新 Trial 已通过六条件完整终评，依赖已合并为 e67ea626b43d23b9bb9e1730e2dfbfa022e268d1。本轮 API 为 0，Spectre 始终只占一个串行槽。参考 Oracle 的机械执行期限为 300 秒，Native verifier 期限为 1800 秒；这些设置没有更改模型的 1200 秒预算。

每题 JSON 保存源/公开/最终包、runtime/parser/checker、原参考候选和实际 freeze 摘要，实际 Trial ID/reward、完整归档与 receipt 摘要，以及真实镜像/mount 检查。readonly watcher 在 create/start 时、容器删除之前采集 inspect。实际 mount 只指向该 Trial 的 `/logs/agent` 与 `/logs/artifacts`，私有终评包没有挂进容器。stock Oracle 单独接收 solution 上传；这不表示模型会得到参考解，也不声称网络隔离。镜像 SHA 是实际本地 deployment 身份，不表示该镜像可公开下载。

原 `tests/test.sh` 未逐字执行。部署使用 portable `CANDIDATE/VERIFY_OUTPUT` wrapper 调用同一 `verify.py`、runtime 与 checker；科学 case/support/评分未改变。公开澄清题使用 f1 固定题面，科学权威仍 cb789；308 与 clock 使用各自作者 overlay 权威。报告列出实际版本，旧校准归档不会称为 fresh Trial。

ADPLL 首次组合终评因 256 MiB 输出额度未评分，同源六条件作者 PSF 共 349,939,086 bytes，新参考 Trial 的六个 PSF 共 349,939,092 bytes；新版本化 private profile 需要明确 `max_output_bytes=536870912`。POR 首次因共享 180 秒总期限未评分，同源五个作者 job 总耗时 325.199 秒；新独立 private profile 仅设置 `timeout_s=600`，输出仍 256 MiB；新的实际参考 Trial 五条件已全部通过。公共单次仿真 180 秒、模型 agent 1200 秒预算不变。旧失败尝试的输出目录成员共 269,244,328 bytes，这是未压缩输出量；新 gzip 归档为 15,473,726 bytes，不能将两者混为传输归档大小。原 profiles/bundles 不覆盖，原 null score 与失败 ID 全部保留；环境修复后的受控新尝试分别记账，不挑选候选或改判据。

可重跑入口须有操作者提供的合法 Spectre/隔离部署和匹配镜像。按 `versioned-private-resource-overrides.template.json` 创建独立资源配置，填好 `oracle-job.template.json` 的路径占位符并固定 public/final package、原 solve 和 binding 后，用实际 Harbor CLI 执行：

```sh
env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u BENCHMARK_MODEL_KEY \
  PYTHONPATH="$HARNESS_CHECKOUT" harbor run --config "$ORACLE_JOB_JSON"
```

本轮内部调度的审计记录为 `run-one.py --prepared "$PREPARED_DIR" --task "$TASK_ID" --python "$HARBOR_PYTHON" --harness "$HARNESS_CHECKOUT" --grant "$RESOURCE_GRANT_JSON" --execute`。该内部脚本未随本报告发布，负责材料核验、一次执行和删除前 watcher；公开重跑使用上面的 Harbor CLI 和随附模板。Harbor CLI 返回 0 仍须独立核验 native exception/reward、solve/动作/freeze、实际完整 archive 和 mount 才能验收。模板占位符须替换成配置值，Harbor 不会自动展开它们。公开/私有配置分别位于 task 外，私有 operator profile 保持私有并绑定原字节 SHA。

archive/receipt 摘要标识本轮保留的私有实际证据，文档没有提供 raw archive 下载。本机 receipt 摘要也不等于公开可取得的内容。本报告与精简身份、重跑模板共同发布；证据以固定 Git 版本和 JSON 摘要为准。
