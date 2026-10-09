"""EVAS voltage-only VAMS environment v1, used only by explicit standard includes.

Caller-provided inventory entries take precedence. This is an EVAS supported
subset, not a copy of any simulator installation's headers.
"""
STANDARD_ENVIRONMENT = 'evas-voltage-vams-v1'
STANDARD_HEADERS = {
    'disciplines.vams': '''`ifndef EVAS_VOLTAGE_DISCIPLINES_V1
`define EVAS_VOLTAGE_DISCIPLINES_V1
nature Voltage;
  units = "V";
  access = V;
  abstol = 1u;
endnature
nature Current;
  units = "A";
  access = I;
  abstol = 1p;
endnature
discipline electrical;
  potential Voltage;
  flow Current;
  domain continuous;
enddiscipline
`endif
''',
    'constants.vams': '''`ifndef EVAS_VOLTAGE_CONSTANTS_V1
`define EVAS_VOLTAGE_CONSTANTS_V1
`define M_PI 3.141592653589793
`endif
''',
}
