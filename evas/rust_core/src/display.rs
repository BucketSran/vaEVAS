//! Pure numeric display formatting. Callers retain records only on acceptance.
use crate::ir::{Error, Expression, Program};

fn conversions(format: &str) -> Result<Vec<(usize, usize, char, usize)>, Error> {
    let b = format.as_bytes();
    let mut result = Vec::new();
    let mut i = 0;
    while i < b.len() {
        if b[i] != b'%' {
            i += 1;
            continue;
        }
        let start = i;
        i += 1;
        let mut precision = 6;
        if b.get(i) == Some(&b'.') {
            i += 1;
            let first = i;
            while b.get(i).is_some_and(u8::is_ascii_digit) {
                i += 1;
            }
            precision = format[first..i].parse::<usize>().unwrap_or(0);
            if b.get(first) == Some(&b'0')
                || !(1..=32).contains(&precision)
                || b.get(i) != Some(&b'g')
            {
                return Err(Error::new(
                    "invalid_ir",
                    "display precision requires %.Ng with N in 1..32",
                ));
            }
        }
        let kind = *b
            .get(i)
            .ok_or_else(|| Error::new("invalid_ir", "incomplete display conversion"))?
            as char;
        if !matches!(kind, '%' | 'd' | 'g') {
            return Err(Error::new(
                "invalid_ir",
                "display supports only %d, %g, %.Ng and %%",
            ));
        }
        i += 1;
        result.push((start, i, kind, precision));
    }
    Ok(result)
}

pub(crate) fn validate(format: &str, count: usize) -> Result<(), Error> {
    if conversions(format)?.iter().filter(|c| c.2 != '%').count() != count {
        return Err(Error::new(
            "invalid_ir",
            "display conversion count differs from argument count",
        ));
    }
    Ok(())
}

fn general(value: f64, precision: usize) -> String {
    // Determine the exponent after rounding, including 9.999... carry cases.
    let scientific = format!("{:.*e}", precision - 1, value);
    let (mantissa, exponent) = scientific.split_once('e').unwrap();
    let exponent = exponent.parse::<i32>().unwrap();
    if exponent < -4 || exponent >= precision as i32 {
        let trimmed = if mantissa.contains('.') {
            mantissa.trim_end_matches('0').trim_end_matches('.')
        } else {
            mantissa
        };
        format!(
            "{}e{}{:02}",
            trimmed,
            if exponent < 0 { '-' } else { '+' },
            exponent.abs()
        )
    } else {
        let decimals = (precision as i32 - exponent - 1).max(0) as usize;
        let fixed = format!("{:.*}", decimals, value);
        if fixed.contains('.') {
            fixed
                .trim_end_matches('0')
                .trim_end_matches('.')
                .to_string()
        } else {
            fixed
        }
    }
}

pub(crate) fn render(format: &str, args: &[f64]) -> Result<String, Error> {
    validate(format, args.len())?;
    let mut output = String::new();
    let mut offset = 0;
    let mut argument = 0;
    for (start, end, kind, precision) in conversions(format)? {
        output.push_str(&format[offset..start]);
        if kind == '%' {
            output.push('%');
        } else {
            let value = args[argument];
            argument += 1;
            if !value.is_finite() {
                return Err(Error::new("nonfinite", "nonfinite display argument"));
            }
            if kind == 'd' {
                if !(-((1u64 << 63) as f64)..(1u64 << 63) as f64).contains(&value) {
                    return Err(Error::new(
                        "invalid_ir",
                        "display %d argument exceeds signed 64-bit range",
                    ));
                }
                output.push_str(&(value.trunc() as i64).to_string());
            } else {
                output.push_str(&general(value, precision));
            }
        }
        offset = end;
    }
    output.push_str(&format[offset..]);
    Ok(output)
}

fn bind(
    expr: &Expression,
    program: &Program,
    owner: &str,
    states: &[f64],
) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::State { state } => {
            if *state >= program.states.len() || program.states[*state].instance != owner {
                return Err(Error::new(
                    "invalid_ir",
                    "display state must belong to its instance",
                ));
            }
            Expression::Affine {
                constant: states[*state],
                terms: vec![],
            }
        }
        Expression::Operator { .. } => {
            return Err(Error::new(
                "unsupported_display",
                "display waveform operator arguments are not supported",
            ))
        }
        Expression::Affine { .. } => expr.clone(),
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind(left, program, owner, states)?),
            right: Box::new(bind(right, program, owner, states)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind(left, program, owner, states)?),
            right: Box::new(bind(right, program, owner, states)?),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(bind(left, program, owner, states)?),
            right: Box::new(bind(right, program, owner, states)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(bind(base, program, owner, states)?),
            exponent: *exponent,
        },
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => {
            if origin.instance != owner {
                return Err(Error::new(
                    "invalid_ir",
                    "display select must belong to its instance",
                ));
            }
            Expression::Select {
                relation: *relation,
                left: Box::new(bind(left, program, owner, states)?),
                right: Box::new(bind(right, program, owner, states)?),
                then_value: Box::new(bind(then_value, program, owner, states)?),
                else_value: Box::new(bind(else_value, program, owner, states)?),
                origin: origin.clone(),
            }
        }
    })
}

pub(crate) fn validate_expression(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<(), Error> {
    crate::expression::validate(
        &bind(expr, program, owner, &vec![0.; program.states.len()])?,
        program.nodes.len(),
    )
}

pub(crate) fn evaluate(
    expr: &Expression,
    program: &Program,
    owner: &str,
    voltages: &[f64],
    states: &[f64],
) -> Result<f64, Error> {
    Ok(crate::expression::evaluate(&bind(expr, program, owner, states)?, voltages)?.value)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn significant_digits_and_integer_measurements() {
        assert_eq!(
            render("n=%d value=%.12g %%", &[3.9, 1.2345678912345]).unwrap(),
            "n=3 value=1.23456789123 %"
        );
        assert_eq!(
            render("%g %g %.3g", &[0.0000123, 1000000., 999.9]).unwrap(),
            "1.23e-05 1e+06 1e+03"
        );
        assert_eq!(render("%g %g", &[0., -0.]).unwrap(), "0 -0");
        assert!(render("%s", &[1.]).is_err());
        assert!(render("%d", &[]).is_err());
    }
}
