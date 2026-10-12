"""Calibrate the actual Rust elementary enclosures against an independent oracle.

Run: python3 -B evas/validation/calibrate_elementary.py OUTPUT_DIRECTORY
The new directory retains the generated probe, compiler receipt and all vectors.
No package dependencies or machine-specific source paths are required.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calibrate(output, rustc):
    root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=False)
    sources = [root / 'evas/rust_core/src' / name
               for name in ('interval.rs', 'math_functions.rs')]
    for path in sources:
        shutil.copyfile(path, output / path.name)
    probe = output / 'probe.rs'
    probe.write_text('''#[derive(Debug)] pub struct Error { kind: String, message: String }
impl Error { pub fn new(k: &str, m: &str) -> Self { Self {kind:k.into(),message:m.into()} } }
mod ir { pub use crate::Error; }
mod interval;
mod math_functions;
fn main() {
    let a:Vec<String>=std::env::args().collect();
    let x=f64::from_bits(u64::from_str_radix(&a[2],16).unwrap());
    let b=match a[1].as_str(){
        "exp"=>math_functions::exp(interval::Interval::point(x)),
        "ln"=>math_functions::ln(interval::Interval::point(x)),
        "sqrt"=>math_functions::sqrt(interval::Interval::point(x)),
        _=>panic!()
    }.unwrap();
    println!("{:016x} {:016x}", b.lo.to_bits(),b.hi.to_bits());
}
''')
    compiler_entry = Path(shutil.which(rustc) or rustc).absolute()
    compiler = compiler_entry.resolve(strict=True)
    # Rustup proxies dispatch by argv[0]; resolving the symlink alone would
    # execute the manager instead of the compiler.
    resolution_argv = None
    if compiler.name == 'rustup':
        resolution_argv = [str(compiler), 'which', 'rustc']
        compiler = Path(subprocess.check_output(resolution_argv, text=True).strip()).resolve(strict=True)
    version = subprocess.check_output([str(compiler), '--version'], text=True).strip()
    command = [str(compiler), '--edition=2021', '-O', str(probe),
               '-o', str(output / 'probe')]
    compiled = subprocess.run(command, text=True, capture_output=True, timeout=120)
    (output / 'compiler.stdout').write_text(compiled.stdout)
    (output / 'compiler.stderr').write_text(compiled.stderr)
    receipt = {'argv': command, 'returncode': compiled.returncode,
               'compiler_version': version, 'compiler_path': str(compiler),
               'compiler_sha256': sha(compiler), 'compiler_entry': str(compiler_entry),
               'compiler_resolution_argv': resolution_argv, 'probe_sha256': sha(probe),
               'source_sha256': {str(p.relative_to(root)): sha(p) for p in sources},
               'driver_sha256': sha(Path(__file__))}
    (output / 'BUILD.json').write_text(json.dumps(receipt, indent=2) + '\n')
    compiled.check_returncode()
    vectors = {
        'exp': [-512., -64., -1., -1/3, 0., math.nextafter(0., 1.), .5, 1., 64., 512.],
        'ln': [math.nextafter(0., 1.), sys.float_info.min, 1e-200, .125,
               math.nextafter(1., 0.), 1., math.nextafter(1., 2.), 2., sys.float_info.max],
        'sqrt': [0., math.nextafter(0., 1.), sys.float_info.min, 1e-200,
                 .125, 1., 2., sys.float_info.max],
    }
    records = []
    with localcontext() as context:
        context.prec = 100
        for function, values in vectors.items():
            for x in values:
                proc = subprocess.run([str(output / 'probe'), function,
                                       struct.pack('>d', x).hex()],
                                      text=True, capture_output=True, check=True, timeout=10)
                lo, hi = [struct.unpack('>d', bytes.fromhex(v))[0]
                          for v in proc.stdout.split()]
                exact = None
                value = Fraction(x)
                if function == 'sqrt':
                    a, b = math.isqrt(value.numerator), math.isqrt(value.denominator)
                    if a*a == value.numerator and b*b == value.denominator:
                        exact = Fraction(a, b)
                elif function == 'exp' and x == 0:
                    exact = Fraction(1)
                elif function == 'ln' and x == 1:
                    exact = Fraction(0)
                if exact is not None:
                    reference = [str(exact)]
                    contained = Fraction(lo) <= exact <= Fraction(hi)
                    oracle = 'exact rational identity'
                else:
                    answer = getattr(Decimal(x), function)()
                    reference = [str(answer.next_minus()), str(answer.next_plus())]
                    contained = Decimal(lo) <= Decimal(reference[0]) <= Decimal(reference[1]) <= Decimal(hi)
                    oracle = '100-digit correctly rounded Decimal with one decimal ULP expansion'
                records.append({'function': function, 'input_hex': x.hex(),
                                'lo_hex': lo.hex(), 'hi_hex': hi.hex(),
                                'reference': reference, 'oracle': oracle,
                                'contained': contained})
    result = {'records': records, 'passed': sum(r['contained'] for r in records),
              'total': len(records), 'build_receipt_sha256': sha(output / 'BUILD.json'),
              'probe_binary_sha256': sha(output / 'probe'),
              'scope': 'point enclosure calibration; not a proof for every input or consumer'}
    (output / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"containment {result['passed']}/{result['total']}")
    if result['passed'] != result['total']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--rustc', default='rustc')
    args = parser.parse_args()
    calibrate(args.output.resolve(), args.rustc)
