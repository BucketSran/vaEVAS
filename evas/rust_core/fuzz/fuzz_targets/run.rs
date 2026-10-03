#![no_main]
use evas_kernel::ir::{parse_request, Expression, Term};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Bounded structured mutations exercise the public in-memory API as well
    // as JSON. Raw float bits include NaN/Inf which JSON cannot represent.
    let mut bytes = [0_u8; 24];
    for (to, from) in bytes.iter_mut().zip(data) {
        *to = *from;
    }
    let bits = u64::from_le_bytes(bytes[8..16].try_into().unwrap());
    let value = f64::from_bits(bits);
    let mut request = parse_request(include_str!("../seeds/static.json")).unwrap();
    match bytes[0] % 9 {
        0 => request.program.contributions[0].positive = usize::from(bytes[1]),
        1 => request.program.contributions[0].negative = usize::from(bytes[1]),
        2 => {
            request.program.contributions[0].rhs = Expression::Affine {
                constant: value,
                terms: vec![Term {
                    node: usize::from(bytes[1]),
                    coefficient: f64::from_bits(!bits),
                }],
            }
        }
        3 => request.samples = vec![vec![value; usize::from(bytes[1] % 4)]],
        4 => request.program.nodes.truncate(usize::from(bytes[1] % 4)),
        5 => request.driven = vec![if bytes[1] % 2 == 0 { "missing" } else { "0" }.into()],
        6 => request.tolerances.absolute = value,
        7 => {
            request.program.contributions[0].rhs = Expression::Power {
                base: Box::new(Expression::Affine {
                    constant: value,
                    terms: vec![],
                }),
                exponent: u32::from(bytes[1]),
            }
        }
        _ => {
            let mut extra = request.program.contributions[0].clone();
            extra.rhs = Expression::Affine {
                constant: value,
                terms: vec![],
            };
            request.program.contributions.push(extra);
        }
    }
    let _ = evas_kernel::run(request);
});
