"""Check Rust event arithmetic against Python's independent exact fractions."""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["DEV:cross-language-arithmetic"]

from fractions import Fraction
import json
import math
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest


class IntervalEnclosure(unittest.TestCase):
    def test_binary64_operations_enclose_exact_rational_results(self):
        module=Path(__file__).resolve().parents[1]/'rust_core/src/interval.rs'
        harness='''#[allow(dead_code)]
#[path=MODULE] mod interval;
use interval::Interval as I;
use std::io::{self, BufRead};
fn main() {
    for line in io::stdin().lock().lines() {
        let line=line.unwrap();
        let mut fields=line.split_whitespace();
        let a=I::point(f64::from_bits(fields.next().unwrap().parse().unwrap()));
        let b=I::point(f64::from_bits(fields.next().unwrap().parse().unwrap()));
        for result in [a+b,a-b,a*b,a/b] {
            println!("{} {}",result.lo.to_bits(),result.hi.to_bits());
        }
    }
}'''.replace('MODULE',json.dumps(str(module)))
        rng=random.Random(72043)
        def decode(bits):
            return struct.unpack('>d',struct.pack('>Q',bits))[0]
        def encode(value):
            return struct.unpack('>Q',struct.pack('>d',value))[0]
        pairs=[]
        while len(pairs)<4096:
            a,b=decode(rng.getrandbits(64)),decode(rng.getrandbits(64))
            if math.isfinite(a) and math.isfinite(b) and b:
                pairs.append((a,b))
        # Cancellation, subnormal products, halfway additions, overflow.
        pairs.extend([(1.,2**-53),(1.,-1.),(2**-1074,.5),
                      (1e308,-1e308),(1e308,1e308),(0.,2**-1074)])
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'bounds.rs'
            binary=Path(directory)/'bounds'
            source.write_text(harness)
            subprocess.run(['rustc','--edition=2021',str(source),'-o',str(binary)],
                           check=True,capture_output=True,text=True)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True,
                                  input=''.join(f'{encode(a)} {encode(b)}\n' for a,b in pairs))
        bounds=iter(result.stdout.splitlines())
        for a,b in pairs:
            x,y=Fraction(a),Fraction(b)
            for exact in [x+y,x-y,x*y,x/y]:
                lo,hi=(decode(int(v)) for v in next(bounds).split())
                self.assertLessEqual(lo,exact,(a,b,lo,hi))
                self.assertGreaterEqual(hi,exact,(a,b,lo,hi))
        self.assertEqual(list(bounds),[])

    def test_four_product_sign_matches_exact_fractions_across_exponents(self):
        module=Path(__file__).resolve().parents[1]/'rust_core/src/interval.rs'
        harness='''#[allow(dead_code)]
#[path=MODULE] mod interval;
use std::io::{self,BufRead};
fn main() { for line in io::stdin().lock().lines() {
let x:Vec<_>=line.unwrap().split_whitespace().map(|s| f64::from_bits(s.parse().unwrap())).collect();
let t:Vec<_>=x.chunks(2).map(|p| (p[0],p[1])).collect();
println!("{}",interval::sum_products_sign(&t).unwrap()); }}'''.replace('MODULE',json.dumps(str(module)))
        rng=random.Random(121206)
        def decode(bits): return struct.unpack('>d',struct.pack('>Q',bits))[0]
        def encode(value): return struct.unpack('>Q',struct.pack('>d',value))[0]
        cases=[]
        while len(cases)<2048:
            values=[decode(rng.getrandbits(64)) for _ in range(8)]
            if all(math.isfinite(v) for v in values): cases.append(values)
        for a,b in [(1e308,1e308),(2**-1074,2**-1074),(1.,2**-53)]:
            cases.extend([[a,b,-a,b,0.,0.,0.,0.],[a,b,-a,b,2**-1074,2**-1074,0.,0.]])
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'sign.rs'; binary=Path(directory)/'sign'
            source.write_text(harness)
            subprocess.run(['rustc','--edition=2021',str(source),'-o',str(binary)],check=True,capture_output=True)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True,
                input=''.join(' '.join(str(encode(v)) for v in row)+'\n' for row in cases))
        signs=list(map(int,result.stdout.splitlines()))
        self.assertEqual(len(signs),len(cases))
        for row,sign in zip(cases,signs):
            exact=sum(Fraction(a)*Fraction(b) for a,b in zip(row[::2],row[1::2]))
            self.assertEqual(sign,(exact>0)-(exact<0),row)
