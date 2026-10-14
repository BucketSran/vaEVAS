"""EVAS voltage-only VAMS environment, used only by explicit standard includes.

Caller-provided inventory entries take precedence. This is an EVAS supported
subset, not a copy of any simulator installation's headers. The mathematical
constants in constants.vams reproduce the VAMS LRM 2.4 Annex D.3 definitions
(Accellera) under that standard's Annex permission; M_PI keeps the historical
short literal, which rounds to the same binary64 value as the LRM text.
"""
STANDARD_ENVIRONMENT = 'evas-voltage-vams-v2'
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
    'constants.vams': '''// Mathematical constants from VAMS LRM 2.4 Annex D.3 (Accellera),
// reproduced under the standard's Annex permission.
`ifndef EVAS_VOLTAGE_CONSTANTS_V2
`define EVAS_VOLTAGE_CONSTANTS_V2
`define M_E 2.7182818284590452354
`define M_LOG2E 1.4426950408889634074
`define M_LOG10E 0.43429448190325182765
`define M_LN2 0.69314718055994530942
`define M_LN10 2.30258509299404568402
`define M_PI 3.141592653589793
`define M_TWO_PI 6.28318530717958647693
`define M_PI_2 1.57079632679489661923
`define M_PI_4 0.78539816339744830962
`define M_1_PI 0.31830988618379067154
`define M_2_PI 0.63661977236758134308
`define M_2_SQRTPI 1.12837916709551257390
`define M_SQRT2 1.41421356237309504880
`define M_SQRT1_2 0.70710678118654752440
`endif
''',
}
