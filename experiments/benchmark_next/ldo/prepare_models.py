"""Freeze nominal TT SKY130 model expressions for Spectre SPICE import.

Original random mismatch slopes are zero in deterministic TT. Spectre interprets
sqrt(l*w*mult) in the PDK's SPICE model statement as statistical syntax and
rejects it. Substitution removes only the zero stochastic contribution.
"""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
src=HERE/'source/raw_models.spice'
text=src.read_text()
pattern=r'\{([^{}]*?)\+sky[^{}]*sqrt\(l\*w\*mult\)[^{}]*\}'
slopes=set(re.findall(r'(sky130_fd_pr__\w+__\w+_slope_spectre)\*',text))
for slope in slopes:
 assert re.search(r'\.param\s+'+re.escape(slope)+r'\s*=\s*0(?:\.0)?(?:\s|$)',text),slope
result,n=re.subn(pattern,lambda m:'{'+m[1]+'}',text)
assert n>0
result=result.replace('{',"'").replace('}',"'")
# Every stochastic slope multiplied above is fixed at zero in nominal TT.
assert not re.search(r'\+sky[^\n]*sqrt\(l\*w\*mult\)',result)
(HERE/'source/models.spice').write_text(result)
(HERE/'source/model-translation.json').write_text(json.dumps(dict(pdk_revision='f62031a1be9aefe902d6d54cddd6f59b57627436',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),translated_sha256=hashlib.sha256(result.encode()).hexdigest(),zero_mismatch_expressions_substituted=n,reason='Deterministic nominal TT zero stochastic slopes; Spectre SPICE parser SFE-1016'),indent=2)+'\n')
