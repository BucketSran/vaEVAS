实现 `sweep_meter(drive,sense,gain,phase,valid)`，固定只读 `healthy.va` 低通 DUT 连接drive→sense。
VA必须驱动4个频点并从实际 drive、sense 测量稳态幅相。参数f0=1000,f1=4000,f2=16000,f3=8000Hz，可在500–20000Hz；slot默认0.02秒，settle默认0.004秒，window默认0.008秒。
第k槽从 k*slot 起，drive=Ak*sin(2πfk*(t-k*slot))；Ak=amplitude（默认0.12V，合法0.05–0.2），第2槽为0.0001V。
在[槽起点+settle, 槽起点+settle+window]按真实波形同步积分，C=2/window*∫v(t)*exp(-j2πfk*(t-槽起点))dt；gain=|Cout/Cin|，phase=arg(Cout/Cin)，单位rad，范围[-π,π]。
窗末更新报告并保持到下一窗末；有效要求 |Cin|>=0.01V、window*fk>=6、settle>=0.003秒。低幅度、未稳态或窗口不足报告valid=0。有效时valid=1。
固定DUT截止频率为600–4000Hz、增益0.5–2，只读。不能读DUT参数或用公式代替实际测量。合法window为0.001–0.009秒，settle为0.001–0.005秒，且settle+window<slot。
幅值报告误差0.035，包裹相位误差0.035rad，真实激励误差0.002V。覆盖全部频点，包括无效的低幅度窗口。
