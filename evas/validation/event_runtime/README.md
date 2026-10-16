# IR23 运行期观察循环的有限实际对照

三条同源模型在 Spectre21.1.0.509.isr12 和先前冻结的 L Python-v3/v5 release 内核上，均完成并符合独立整数答案。15个要求的原生源电压观察点齐全，参考、EVAS及配对电压误差均为0，预算100nV。当前目录是待root整合的紧凑交付候选，不表示已发布或已在F新集成版本重跑；不计原CDS恢复或新Q资格。

| 模型 | 独立答案 | 两端实际结果 |
| --- | --- | --- |
| sequential | n=3，顺序数组值1、3、6，acc=10，退出i=3，a3=0 | 完全一致，te=.5 s |
| nested | 动态外层2次、固定整数内层各3次，共8次循环体迭代。最终a=(3,5,7)，acc=21，i=2，j=3 | 完全一致，te=.5 s |
| quotient | n=4，整型(n+1)/2=2、(n+1)%2=1；循环写a1=2、a2=3，acc=5，退出i=2 | 完全一致，te=.5 s |

观察实例不贡献物理电压，独立固定源提供u=1 V。timer .25设置运行期n，timer .5执行并显示te、退出变量与数组值。每个JSON实际保留Loop、CheckedInteger、CheckedIndex、ArrayRead、ArrayWrite，nested保留两层Loop。三条IR项数/深度为363/16、315/16、835/21，原100000/96和每事件4096次上限未变。预算、溢出、负商余、同controller回滚仍由独立回归负责，不从这三个正例推断。

实际参考三条均退出0、未超时，按顺序执行。同源VA/SCS逐字节匹配冻结输入。PSF HEADER读回reltol=1e-9、abstol(V)=1e-7、maxstep=.25、stop=1、method=traponly、lteratio=3.5、relref=sigglobal。PSF没有strobeperiod字段，因此不补造“实际设置”；原生VALUE区独立确认完整0/.25/.5/.75/1网格。没有插值。起止Spectre二进制和两份环境setup文件的hash均一致。

EVAS证据绑定旧L Python-v3和内核SHA256 `9612009ae60c6e016e7895b67df1d86688013ee74eeb9e4bbed5b6a339a716ba`。相应源码hash在 `source-identities.json`，旧执行身份在 `receipt.json`；本包没有重新模拟EVAS。原CDS的三个120秒超时和未运行checker结论不变。

## 本目录可复核的内容

每个子目录包含相同VA/SCS、唯一原生日志结果行、EVAS结果行、五个原生十进制源电压观察点及实际PSF设置摘录。完整整数合同在 `CONTRACT.json`，结果在 `result.json`。

```sh
python3 -B analyze_package.py --self-test
python3 -B analyze_package.py
```

`analyze.py` 是先前已校准的原生日志解析器，未改动。包分析器先调用它，再以精确十进制有理数严格核对整数及te，避免浮点读入掩盖微小的非整数。原解析器3条接受/18条拒绝控制、精确十进制1条接受/1条拒绝控制、原生网格/电压1条接受/5条拒绝控制均通过，见 `calibration.log`。任何要求时刻缺失、重复、非有限值或电压超预算都会失败。静态复核不重新执行模拟器。

原始PSF、完整stdout/spectre日志、内核、执行/传输收据及私有setup配置只保留在本地。这里提供其身份hash和紧凑摘录，没有公开下载链接；hash本身不能让读者获取或独立重做远端执行。stdout会折行，唯一完整原生记录取自Spectre自身的spectre.log，未拼接或补字段。正式整合后，本目录内容可随仓库提供，其原始执行材料仍是local-only。

先前packet-v1漏传inputs.py，runner在import时失败，Spectre尚未启动。该包装失败原样保留在本地，不算三条原生模拟失败，也不改记为数值失败。本次实际三条结果来自修正后的packet-v2。
