# 来源和改编

本题对应批准规格 [#150](https://github.com/BucketSran/vaEVAS/issues/150)，设计单元 D3。固定基线 main `81eb66258b59b0a0cd48cd3decaa767be02cdd58`。

来源 v4 390 只提供工程主题和接口比较依据，来自仓库 `benchmark/reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/` 的固定快照。本题题面、控制器、健康行为环境和独立判据为新编写资产，没有复制受限来源实现。上游 v4 许可未知，不因来源记录而授予再分发权。

D1采用明确的上升沿 N/N+1 平均比率，替代302旧的toggle计数符号；已有v2 fine-TDC仍为原独立任务，没有改名。D2归并306的静态trim和369的有符号持续控制，因为它们在本题同一个可辨识零输入窗口合同内作用于同一真实执行器。390对应D3，差模保持单独验收。

所有激励和环境均为行为合成数据，不是测得硅片数据或晶体管模型。任务是Spectre扩展集，Docker不带商业工具；尚无同题开源后端复验资格。作者校准结果与候选、checker、条件身份归属 [路线记录](../../../experiments/benchmark_next/calibration/README.md)。没有模型试做，也不增加已有成绩分母。
