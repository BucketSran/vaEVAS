# 公开自测

复制一份公开.scs网表到/work/test.scs，将候选放在/work/dut.va，
在/work运行可用的Spectre并将out电压导出为time_s、out_V两列CSV。
`python3 /work/public/selfcheck.py --experiment public-1 --candidate-csv /work/observed.csv`
脚本只比较公开波形，不读取终评。控制边沿5 ns内不比较。
CSV比较记录不等于实际VA仿真，必须保留后端执行身份。
