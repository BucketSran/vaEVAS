# 原始电路来源

Ajacci sky130_ajc_ip__por 固定commit db8745ef4d7d85a1852fc60c251ba34c6cebe497。保留真实analog源；仅por_dig使用按原Verilog旧状态语义转写的VA，数字边界已经原XSPICE独立oracle与实际Spectre校准，两项short/long均通过，证据位于experiments/benchmark_v2/testing_characterization/por_digital_spectre_r2.json。两个电平转换单元选择同版本官方CDL源视图，PDK SPICE brace表达式改为等值单引号并移除公式外重复双引号、指数加u改为Decimal精确值以避免Spectre忽略后缀。原抽取SPICE含悬空节点，独立实际测试不合格；未修改器件模型或阈值。公开生成文件清理行尾空白；实例AD/AS/PD/PS/NRD/NRS中W/nf引用按原调用的几何值作括号展开，保持原算术。282个重复全局参数逐项等值，Spectre显式redefinedparams=warning保留原ngspice后定义覆盖语义。

{
  "por": "db8745ef4d7d85a1852fc60c251ba34c6cebe497",
  "fd_pr": "f62031a1be9aefe902d6d54cddd6f59b57627436",
  "fd_sc_hvl": "4fd4f858d16c558a6a488b200649e909bb4dd800",
  "fd_sc_hd": "ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1",
  "deck_sha256": "c75569af75bbd4c6e2dd7997b56414671c104258fd8fdb34ba46e596dac8d722",
  "cell_view": "cdl-level-shifters",
  "mode": "short one-shots, force_short_oneshot=1, no sleep",
  "processing": [
    "recursive include flatten",
    "CACE configuration substitution",
    "ngspice W/NF bin selection wnflag=1",
    "obsolete non-SPICE include omitted",
    "unused upstream varactor dev/gauss annotations retained; nominal source deck does not instantiate these devices"
  ]
}

完整Spectre闭环及正负例校准仍待实际执行，不能据资产存在宣布发布资格。
