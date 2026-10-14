"""Refresh only retained package byte hashes; does not bless numerical claims."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
files={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(P.rglob('*')) if f.is_file() and f.name not in ['PACKAGE-MANIFEST.json','VERIFY-RESULT.json'] and '__pycache__' not in f.parts}
(P/'PACKAGE-MANIFEST.json').write_text(json.dumps({'files':files},indent=2)+'\n')
