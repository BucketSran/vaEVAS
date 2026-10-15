use super::*;

fn linear(a: f64, b: f64, c: f64) -> Polynomial {
    Polynomial::Linear([a, b, c].map(I::point).to_vec())
}
fn bits(jet: &[I]) -> Vec<(u64, u64)> {
    jet.iter()
        .map(|v| (v.lo.to_bits(), v.hi.to_bits()))
        .collect()
}

// The preserved pre-memo algorithm is an arithmetic-compatibility oracle only.
// Independent derivatives below separately check mathematical correctness.
#[test]
fn gradient_memo_preserves_old_endpoint_bits_all_domains() {
    let x = linear(1., 0., 0.);
    let y = linear(0., 1., 0.);
    let cases = [
        Polynomial::Multiply(
            Box::new(Polynomial::Exp(Box::new(x.clone()))),
            Box::new(Polynomial::Power(Box::new(y.clone()), 3)),
        ),
        Polynomial::Reciprocal(Box::new(Polynomial::Add(
            Box::new(x.clone()),
            Box::new(y.clone()),
        ))),
        Polynomial::Power(Box::new(x.clone()), 1),
        Polynomial::Power(Box::new(x.clone()), 32),
        Polynomial::Exp(Box::new(linear(0., 0., 1000.))),
        Polynomial::Reciprocal(Box::new(linear(0., 0., 0.))),
    ];
    for order in [0, 1, 4, 12, 24] {
        for initial in [
            I::point(0.5),
            I { lo: -1., hi: 1. },
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY,
            },
        ] {
            let mut variables = vec![vec![I::ZERO; order + 1]; 2];
            variables[0][0] = initial;
            variables[1][0] = I::point(2.);
            if order > 0 {
                variables[0][1] = I::point(0.25);
                variables[1][1] = I { lo: -0.2, hi: 0.1 };
            }
            for f in &cases {
                let mut memo = GradientJets::new(f, &variables, order);
                for k in [0, 1, 0, 1] {
                    assert_eq!(
                        bits(&memo.gradient(k)),
                        bits(&f.old_gradient_jet(&variables, order, k))
                    );
                }
            }
        }
    }
}

#[test]
fn gradient_memo_contains_independent_product_exp_and_reciprocal_derivatives() {
    // f(x,y)=exp(x)*y^3 + 1/(x+y); df/dx=exp(x)*y^3-1/(x+y)^2,
    // df/dy=3*exp(x)*y^2-1/(x+y)^2. At x=0,y=2 these are exact rationals.
    let x = linear(1., 0., 0.);
    let y = linear(0., 1., 0.);
    let product = Polynomial::Multiply(
        Box::new(Polynomial::Exp(Box::new(x.clone()))),
        Box::new(Polynomial::Power(Box::new(y.clone()), 3)),
    );
    let inverse = Polynomial::Reciprocal(Box::new(Polynomial::Add(Box::new(x), Box::new(y))));
    let f = Polynomial::Add(Box::new(product), Box::new(inverse));
    for (k, expected) in [7.75, 11.75].into_iter().enumerate() {
        let answer = f.gradient_jet(&[vec![I::ZERO], vec![I::point(2.)]], 0, k)[0];
        assert!(answer.lo <= expected && answer.hi >= expected);
        assert!(answer.hi - answer.lo < 1e-11);
    }
}

#[test]
fn gradient_memo_does_not_reuse_changed_variables_or_order() {
    let f = Polynomial::Power(Box::new(linear(1., 0., 0.)), 3);
    for (x, expected) in [(2., 12.), (3., 27.), (2., 12.)] {
        let v = vec![vec![I::point(x), I::ONE], vec![I::ZERO; 2]];
        for order in [1, 0, 1] {
            let a = f.gradient_jet(&v, order, 0);
            assert_eq!(a.len(), order + 1);
            assert!(a[0].lo <= expected && a[0].hi >= expected);
        }
    }
}

#[test]
fn gradient_memo_repeated_work_diagnostic_and_nonfinite_refusal() {
    let x = linear(1., 0., 0.);
    let y = linear(0., 1., 0.);
    let f = Polynomial::Multiply(
        Box::new(Polynomial::Exp(Box::new(x))),
        Box::new(Polynomial::Power(Box::new(y), 4)),
    );
    let vars = vec![vec![I::point(0.5); 13], vec![I::point(2.); 13]];
    crate::interval::zero_product_tests::reset_work();
    let mut memo = GradientJets::new(&f, &vars, 12);
    for k in [0, 1, 0, 1, 0, 1, 0, 1] {
        assert_eq!(
            bits(&memo.gradient(k)),
            bits(&f.old_gradient_jet(&vars, 12, k))
        );
    }
    eprintln!(
        "value_jet_work: misses={} hits={} requests={} old_value_requests={}",
        memo.misses,
        memo.hits,
        memo.misses + memo.hits,
        memo.misses + memo.hits
    );
    eprintln!(
        "gradient_interval_scalar_products_all_and_zero={:?}",
        crate::interval::zero_product_tests::work()
    );
    let invalid = Polynomial::Exp(Box::new(linear(0., 0., 1000.)));
    let mut refused = GradientJets::new(&invalid, &vars, 12);
    for _ in 0..2 {
        refused.gradient(0);
    }
    assert!(
        refused.values.is_empty(),
        "nonfinite jets must not enter the memo"
    );
}

#[test]
fn gradient_memo_encloses_independent_time_coefficients() {
    // d/dx [exp(x)*8+1/(x+2)] at x=t. Coefficient n is
    // 8/n! - (-1)^n*(n+1)/2^(n+2).
    let exp = Polynomial::Exp(Box::new(linear(1., 0., 0.)));
    let product = Polynomial::Multiply(Box::new(exp), Box::new(linear(0., 0., 8.)));
    let inverse = Polynomial::Reciprocal(Box::new(linear(1., 0., 2.)));
    let f = Polynomial::Add(Box::new(product), Box::new(inverse));
    let vars = vec![vec![I::ZERO, I::ONE, I::ZERO, I::ZERO], vec![I::ZERO; 4]];
    for (a, expected) in
        f.gradient_jet(&vars, 3, 0)
            .iter()
            .zip([7.75, 8.25, 3.8125, 4. / 3. + 0.125])
    {
        assert!(
            a.lo <= expected && a.hi >= expected,
            "{:?} excludes {}",
            (a.lo, a.hi),
            expected
        );
        assert!(a.hi - a.lo < 1e-11);
    }
}
