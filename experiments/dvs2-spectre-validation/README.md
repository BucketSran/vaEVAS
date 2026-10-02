# Spectre 对照与事件专项

本目录保存 thu-sui 上的 Spectre 执行，以及与各次 EVAS 检查点的对照。
它包括原 31 条件两档验证、`cross` 触零/平台边界、`timer` 同刻更新和
`transition` 历史精度实验。

实验用独立数学关系判断结果。Spectre 是重要参考后端，但它的输出不会直接成为
EVAS 的黄金答案；版本、步长、容差与事件历史差异分别记录。

## 原 31 条件

Spectre 21.1.0.509.isr12 在两档各达到 **31/31**，共 62 条配置、1,333,719 个导出点。
[历史完整报告](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#original-31-condition-comparison)说明范围和观测结果，
[执行协议](PROTOCOL.md)固定输入、预算与判据。
[收据](results/RECEIPT.json)、[分析](results/analysis.json)和
[生效设置](results/effective-settings.json)保留实际身份。

这些结果属于固定历史批次。有限观察满足不代表完整连续时间资格，正式 DVS 资格仍为 I；
执行时间包含启动、编译等成本，不作为当前 EVAS 与 Spectre 的速度比较。

## 专项报告索引

完整实验记录从[固定历史提交](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md)查阅，保留原来的版本、失败、数学解释与命令。
下面按研究问题阅读，不需要按 PR 编号猜能力范围。

| 问题 | 报告 |
| --- | --- |
| 事件检查器能否检出漏事件、重复和共同历史矛盾？ | [独立校准](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#事件检查器的独立校准补充) |
| 孤立触零为何可能产生额外跳变？ | [触零实验](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pwl-触零边界实验)、[修复回放](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#孤立触零契约回放045) |
| 零平台、端点和停止点如何处理？ | [边界实验](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#零平台和停止点边界046) |
| 固定 timer 的事件前后解怎样联立？ | <a id="pr12-fixed-timer-comparison"></a>[timer 初版对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-fixed-timer-comparison) |
| timer 试算与整数顺序赋值有哪些反例？ | <a id="pr12-timer-repair-051"></a>[0.5.1 修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-repair-051)、<a id="pr12-timer-hardening-052"></a>[0.5.2 加固](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-hardening-052)、<a id="pr12-integer-sequence-053"></a>[0.5.3 整数顺序](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053) |
| 大绝对时间的 transition 历史误差为何不能只检查残差？ | <a id="pr13-transition-061"></a>[0.6.1 精度修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr13-transition-061)、[0.6.0 对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr13-transition-060) |

上述 EVAS 版本是各次实验的被测身份，当前能力见[能力表](../../evas/docs/CAPABILITIES.md)。

## 工具的分工

| 入口 | 作用 |
| --- | --- |
| [run_suite.py](run_suite.py) | 生成共同 DUT、刺激、网表与冻结清单 |
| [remote.py](remote.py) | 在已有 Spectre 环境执行并保存日志/波形 |
| [check_results.py](check_results.py) | 用独立答案检查结果与事件历史 |
| [report.py](report.py) | 汇总结果、身份与实际设置 |
| `cross_*.py`、`timer_*.py`、`transition_reference.py` | 专项输入、执行或分析；具体命令在对应报告中 |

## 如何复核与重新执行

从仓库根目录运行公开检查器校准，无需 Spectre：

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B scripts/verify_validation_version.py
```

只生成一份新输入，可运行 `python3 -B experiments/dvs2-spectre-validation/run_suite.py runs/NEW-INPUTS`。
实际执行还需要 Spectre 安装、许可证与私有配置；远端命令见 [PROTOCOL](PROTOCOL.md)
和各专项报告。既有结果重判需要相应原始归档，并写到新路径。

公开材料包括协议、脚本、精简结果与收据。完整波形、日志和机器配置仅本地/thu-sui 保留；
公开哈希不等于可下载原始数据。新执行和历史重判必须使用各自的身份，不能覆盖原报告。
