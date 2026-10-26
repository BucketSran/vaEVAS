"""Recreate compact fixtures from the explicitly authorized historical inputs."""
from pathlib import Path
import ast
import hashlib
import json

OUT = Path(__file__).resolve().parent
B = OUT.parent.parent
HISTORY = B.parent / 'test-scheme-audit'
DEST = OUT / 'source/evas/validation/checker_calibration/fixtures'
DEST.mkdir(parents=True, exist_ok=True)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
manifest = []
def emit(name, original, value, recipe):
    data = packed(value)
    (DEST / name).write_bytes(data)
    raw = original.read_bytes()
    manifest.append(dict(fixture=name, sha256=sha(data), bytes=len(data),
                         original=str(original.relative_to(B.parent)), original_bytes=len(raw),
                         original_sha256=sha(raw), extraction=recipe))
p = HISTORY / 'passing-oracles/source-math-calibration-raw.json'
controls = json.loads(p.read_bytes())['controls']
emit('source_math.json', p, controls, 'Parse JSON; select controls array unchanged; sort keys and compact JSON with trailing LF. All14 controls preserve7 correct/7 wrong records and independent_answer.')
raw = HISTORY / 'passing-raw'
for method, count in [('test_bound_caps_actual_nonlinear_integration_segments',1),
                      ('test_sampled_clock_activation_preserves_physics_and_caps_inner_segments',2)]:
    for i in range(count):
        for suffix in ['request.json', 'original-response.json'] + (['diagnostics.json'] if i == 0 else []):
            p = raw / f'{method}--identity--{i}.{suffix}'
            emit(p.name, p, json.loads(p.read_bytes()), 'Parse entire original JSON unchanged; sort keys and compact JSON with trailing LF. No scientific values or diagnostic records removed.')
p = OUT / 'source/evas/src/evas/program_real_validation.py'
raw = p.read_bytes()
predicates = []
for node in ast.walk(ast.parse(raw)):
    if isinstance(node, ast.If) and ast.unparse(node.test) == 'isinstance(value, UnsupportedSystemCall)':
        for statement in node.body:
            if isinstance(statement, ast.If) and ('value.op' in ast.unparse(statement.test) or 'owner is None' in ast.unparse(statement.test)):
                predicates.append(ast.unparse(statement))
assert len(predicates) == 2
data = packed(predicates)
(DEST / 'validator_predicates.json').write_bytes(data)
manifest.append(dict(fixture='validator_predicates.json', sha256=sha(data), bytes=len(data),
    original='git:842bde7101164330fa03e7aee58b45d1789cbed1:evas/src/evas/program_real_validation.py',
    original_sha256=sha(raw), original_bytes=len(raw),
    extraction='Parse original validator AST; locate UnsupportedSystemCall branch; preserve parseable ast.unparse source of exactly the two original If statements; compare after parsing on the executing interpreter selected by value.op or owner is None. No predicate edit.'))
(DEST / 'provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
print('fixture entries',len(manifest),'total bytes',sum(x['bytes'] for x in manifest))
