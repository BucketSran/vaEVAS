//! Lower continuous source-only clamps to enclosed internal PWL sources.
//! No serialized IR change, output-grid approximation, or new integrator.
use crate::events::affine;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, OperatorSpec, Program, Relation, Term};
use crate::pwl::Trajectory;

fn unsupported() -> Error {
    Error::new("unsupported_transient", "continuous select requires a finite source-only affine clamp; event/state/internal feedback and discontinuous selects are unsupported")
}

fn constant(e: &Expression) -> Option<f64> {
    match e {
        Expression::Affine { constant, terms } if terms.is_empty() && constant.is_finite() => {
            Some(*constant)
        }
        _ => None,
    }
}

fn recognize(e: &Expression) -> Option<(&Expression, f64, f64)> {
    let Expression::Select {
        relation,
        left,
        right,
        then_value,
        else_value,
        ..
    } = e
    else {
        return None;
    };
    let Expression::Select {
        relation: other,
        left: base,
        right: bound,
        then_value: clipped,
        else_value: original,
        ..
    } = else_value.as_ref()
    else {
        return None;
    };
    if left != base || base != original || right != then_value || bound != clipped {
        return None;
    }
    let (a, b) = (constant(right)?, constant(bound)?);
    let (lo, hi) = match (relation, other) {
        (Relation::Lt | Relation::Le, Relation::Gt | Relation::Ge) => (a, b),
        (Relation::Gt | Relation::Ge, Relation::Lt | Relation::Le) => (b, a),
        _ => return None,
    };
    (lo < hi).then_some((base, lo, hi))
}

// Validate before appending hidden nodes: an original out-of-range index
// must not accidentally become a valid reference to a generated source.
fn validate_original(e: &Expression, p: &Program, owner: &str) -> Result<(), Error> {
    match e {
        Expression::Affine { constant, terms } => {
            let mut seen = std::collections::BTreeSet::new();
            if !constant.is_finite()
                || terms.iter().any(|t| {
                    t.node >= p.nodes.len() || !t.coefficient.is_finite() || !seen.insert(t.node)
                })
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid original clamp-program affine expression",
                ));
            }
        }
        Expression::State { state } if *state >= p.states.len() => {
            return Err(Error::new(
                "invalid_ir",
                "invalid original clamp-program state index",
            ))
        }
        Expression::Operator { operator } if *operator >= p.operators.len() => {
            return Err(Error::new(
                "invalid_ir",
                "invalid original clamp-program operator index",
            ))
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            validate_original(left, p, owner)?;
            validate_original(right, p, owner)?;
        }
        Expression::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid original clamp-program power",
                ));
            };
            validate_original(base, p, owner)?;
        }
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            if origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid original clamp select owner",
                ));
            }
            for child in [left, right, then_value, else_value] {
                validate_original(child, p, owner)?;
            }
        }
        _ => {}
    }
    Ok(())
}

struct Lowering<'a> {
    original: &'a Program,
    trajectory: &'a Trajectory,
    driven_nodes: Vec<usize>,
    expressions: Vec<Expression>,
    sources: Vec<Vec<[f64; 2]>>,
    errors: Vec<f64>,
}

impl Lowering<'_> {
    fn source(&self, expression: &Expression) -> Result<(Vec<[f64; 2]>, f64), Error> {
        crate::expression::validate(expression, self.original.nodes.len())?;
        let (base, lo, hi) = recognize(expression).ok_or_else(unsupported)?;
        let origin = match expression {
            Expression::Select { origin, .. } => origin,
            _ => unreachable!(),
        };
        if !origin.valid_expansion()
            || !self
                .original
                .contributions
                .iter()
                .any(|c| c.origin.instance == origin.instance)
        {
            return Err(Error::new("invalid_ir", "invalid clamp owner"));
        }
        let a = affine(base, self.original, &origin.instance)?;
        if !a.state_dependencies.is_empty()
            || !a.operator_dependencies.is_empty()
            || a.node_dependencies
                .iter()
                .any(|n| *n != 0 && !self.driven_nodes.contains(n))
        {
            return Err(unsupported());
        }
        let coefficients = crate::affine_bounds::affine(base, self.original)?;
        let mut nodes = vec![0.0; self.original.nodes.len()];
        let mut bound_nodes = vec![I::ZERO; nodes.len()];
        let mut original = Vec::new();
        let mut error = I::ZERO;
        for &time in &self.trajectory.knots {
            for ((&node, value), bounds) in self
                .driven_nodes
                .iter()
                .zip(self.trajectory.values(time))
                .zip(self.trajectory.value_bounds(time))
            {
                nodes[node] = value;
                bound_nodes[node] = bounds;
            }
            let value = a.value(&nodes, &[])?;
            let exact = coefficients[..nodes.len()]
                .iter()
                .zip(&bound_nodes)
                .fold(*coefficients.last().unwrap(), |sum, (&c, &v)| sum + c * v);
            let difference = I::point(value) - exact;
            if !difference.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite clamp endpoint enclosure",
                ));
            }
            error = error.hull(I::point(difference.magnitude()));
            original.push((time, value));
        }
        let mut points = Vec::new();
        let endpoint_error = error;
        let mut kink_error = I::ZERO;
        for pair in original.windows(2) {
            let [(start, a), (end, b)] = [pair[0], pair[1]];
            points.push([start, a.clamp(lo, hi)]);
            let mut roots = Vec::new();
            let mut segment_error = I::ZERO;
            for threshold in [lo, hi] {
                if threshold > a.min(b) && threshold < a.max(b) {
                    let duration = I::point(end) - I::point(start);
                    let delta = I::point(b) - I::point(a);
                    let root =
                        I::point(start) + (I::point(threshold) - I::point(a)) * duration / delta;
                    if !root.finite() || root.lo <= start || root.hi >= end {
                        return Err(Error::new(
                            "waveform_accuracy",
                            "cannot enclose clamp kink strictly inside source segment",
                        ));
                    }
                    let time = root.lo * 0.5 + root.hi * 0.5;
                    let shift = (I::point(time) - root).magnitude();
                    let vertical = (delta / duration) * I::point(shift);
                    if !vertical.finite() {
                        return Err(Error::new(
                            "waveform_accuracy",
                            "nonfinite clamp kink displacement",
                        ));
                    }
                    // Uniform source error: endpoints alone cannot enclose a
                    // displaced kink's narrow tent-shaped interpolation error.
                    segment_error = segment_error + I::point(vertical.magnitude());
                    roots.push((time, threshold, root));
                }
            }
            roots.sort_by(|a, b| a.0.total_cmp(&b.0));
            if roots.windows(2).any(|p| p[0].2.hi >= p[1].2.lo) {
                return Err(Error::new(
                    "waveform_accuracy",
                    "cannot certify distinct clamp kink ordering",
                ));
            }
            kink_error = kink_error.hull(segment_error);
            points.extend(roots.into_iter().map(|(t, v, _)| [t, v]));
        }
        error = endpoint_error + kink_error;
        let &(time, value) = original.last().unwrap();
        points.push([time, value.clamp(lo, hi)]);
        if !error.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite clamp source bound",
            ));
        }
        Ok((points, error.hi))
    }

    fn expression(&mut self, e: &mut Expression) -> Result<(), Error> {
        match e {
            Expression::Select { .. } => {
                let k = if let Some(k) = self.expressions.iter().position(|old| old == e) {
                    k
                } else {
                    let (points, error) = self.source(e)?;
                    self.expressions.push(e.clone());
                    self.sources.push(points);
                    self.errors.push(error);
                    self.expressions.len() - 1
                };
                *e = Expression::Affine {
                    constant: 0.0,
                    terms: vec![Term {
                        node: self.original.nodes.len() + k,
                        coefficient: 1.0,
                    }],
                };
            }
            Expression::Add { left, right } | Expression::Multiply { left, right } => {
                self.expression(left)?;
                self.expression(right)?;
            }
            Expression::Power { base, .. } => self.expression(base)?,
            _ => {}
        }
        Ok(())
    }
}

pub(crate) fn lower(
    program: &mut Program,
    driven: &mut Vec<String>,
    trajectory: &mut Trajectory,
) -> Result<usize, Error> {
    let output_count = program.nodes.len();
    let has_select = program
        .contributions
        .iter()
        .any(|c| crate::analog::has_select(&c.rhs))
        || program.operators.iter().any(|o| match o {
            OperatorSpec::IdtMod { input, .. } => crate::analog::has_select(input),
            _ => false,
        });
    if !has_select {
        return Ok(output_count);
    }
    if !program.events.is_empty() || !program.states.is_empty() {
        return Err(unsupported());
    }
    // Only the existing immutable phase integral / sine composition is
    // admitted. In particular derivative histories need a different contract
    // at uncertain kink windows and are not silently enabled by this lowering.
    if program
        .operators
        .iter()
        .any(|o| !matches!(o, OperatorSpec::IdtMod { .. } | OperatorSpec::Sin { .. }))
    {
        return Err(unsupported());
    }
    let original = program.clone();
    for c in &original.contributions {
        // Validate against the immutable user program, before private source
        // nodes can accidentally turn an original out-of-range endpoint valid.
        if c.positive >= output_count || c.negative >= output_count {
            return Err(Error::new(
                "invalid_ir",
                "clamp contribution endpoint is outside the original program",
            ));
        }
        validate_original(&c.rhs, &original, &c.origin.instance)?;
    }
    for o in &original.operators {
        let input = match o {
            OperatorSpec::IdtMod { input, .. } | OperatorSpec::Sin { input, .. } => input,
            _ => unreachable!(),
        };
        validate_original(input, &original, &o.origin().instance)?;
    }
    let driven_nodes = driven
        .iter()
        .map(|n| {
            original
                .nodes
                .iter()
                .position(|p| p == n)
                .ok_or_else(|| Error::new("invalid_inputs", "unknown clamp driven node"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    let mut lowering = Lowering {
        original: &original,
        trajectory,
        driven_nodes,
        expressions: Vec::new(),
        sources: Vec::new(),
        errors: Vec::new(),
    };
    let mut candidate = program.clone();
    for c in &mut candidate.contributions {
        lowering.expression(&mut c.rhs)?;
    }
    for o in &mut candidate.operators {
        match o {
            OperatorSpec::IdtMod { input, .. } => lowering.expression(input)?,
            _ => {}
        }
    }
    let sources = lowering.sources;
    let errors = lowering.errors;
    let mut next_trajectory = trajectory.clone();
    let mut next_driven = driven.clone();
    for (k, (points, error)) in sources.into_iter().zip(errors).enumerate() {
        let mut name = format!("$evas_clamp_{k}");
        while candidate.nodes.contains(&name) {
            name.push('_');
        }
        candidate.nodes.push(name.clone());
        next_driven.push(name);
        next_trajectory.add_enclosed_source(points, error)?;
    }
    *program = candidate;
    *driven = next_driven;
    *trajectory = next_trajectory;
    Ok(output_count)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::TransientInputs;
    use num_rational::BigRational as R;

    fn affine_node(node: usize) -> serde_json::Value {
        serde_json::json!({"op":"affine","constant":0.0,"terms":[{"node":node,"coefficient":1.0}]})
    }
    fn scalar(x: f64) -> serde_json::Value {
        serde_json::json!({"op":"affine","constant":x,"terms":[]})
    }
    fn program() -> Program {
        let base = affine_node(1);
        let lo = scalar(0.25);
        let hi = scalar(0.75);
        let origin = serde_json::json!({"source":"clamp.va","line":1,"column":1,"instance":"dut","expansion":[]});
        let inner = serde_json::json!({"op":"select","relation":"gt","left":base,"right":hi,"then_value":hi,"else_value":base,"origin":origin});
        let clamp = serde_json::json!({"op":"select","relation":"lt","left":base,"right":lo,"then_value":lo,"else_value":inner,"origin":origin});
        serde_json::from_value(serde_json::json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","phase"],"contributions":[{"branch":{"instance":"dut","local_positive":"phase","local_negative":"0","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}],"states":[],"events":[],"operators":[{"kind":"idt_mod","input":clamp,"ic":0.0,"modulus":10.0,"offset":0.0,"origin":origin}]})).unwrap()
    }
    fn trajectory() -> Trajectory {
        Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, -0.1], [1.0, 1.1]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap()
    }
    fn rational(x: f64) -> R {
        R::from_float(x).unwrap()
    }

    #[test]
    fn original_rational_clamp_is_enclosed_between_shifted_roots() {
        let mut p = program();
        let mut t = trajectory();
        let mut driven = vec!["u".to_string()];
        lower(&mut p, &mut driven, &mut t).unwrap();
        // Original exact binary64 affine source, including nonrepresentable
        // root times. Neither oracle nor test uses the production root solver.
        for i in 0..=1000 {
            let time = i as f64 / 1000.0;
            let exact = (rational(-0.1) + (rational(1.1) - rational(-0.1)) * rational(time))
                .max(rational(0.25))
                .min(rational(0.75));
            let b = t.value_bounds(time)[1];
            assert!(
                rational(b.lo) <= exact && exact <= rational(b.hi),
                "t={time} bound={b:?}"
            );
        }
    }

    #[test]
    fn derived_bound_reaches_integral_not_just_trajectory() {
        let mut p = program();
        let mut t = trajectory();
        let mut driven = vec!["u".to_string()];
        lower(&mut p, &mut driven, &mut t).unwrap();
        let h = crate::operators::Operators::new(&p, &t, &driven, &[]).unwrap();
        // Exact clipped-ramp area: lo*rlo + middle trapezoid + hi*(1-rhi).
        let a = rational(-0.1);
        let slope = rational(1.1) - a.clone();
        let left = (rational(0.25) - a.clone()) / slope.clone();
        let right = (rational(0.75) - a) / slope;
        let area = rational(0.25) * left.clone()
            + (rational(0.25) + rational(0.75)) * (right.clone() - left) / rational(2.0)
            + rational(0.75) * (rational(1.0) - right);
        let bound = h.bounds(1.0).unwrap()[0];
        assert!(rational(bound.lo) <= area && area <= rational(bound.hi));
        assert!(bound.lo < bound.hi);
        // Existing enclosed closed-form integral must consume a changed source
        // uncertainty. This control would fail if direct_points dropped it.
        t.add_enclosed_source(vec![[0.0, 1.0], [1.0, 1.0]], 0.01)
            .unwrap();
        let node = p.nodes.len();
        p.nodes.push("uncertain".into());
        driven.push("uncertain".into());
        if let OperatorSpec::IdtMod { input, .. } = &mut p.operators[0] {
            *input = Expression::Affine {
                constant: 0.0,
                terms: vec![Term {
                    node,
                    coefficient: 1.0,
                }],
            };
        }
        let uncertain = crate::operators::Operators::new(&p, &t, &driven, &[]).unwrap();
        let b = uncertain.bounds(1.0).unwrap()[0];
        assert!(b.lo <= 0.99 && b.hi >= 1.01);
        let clone = h.clone();
        assert_eq!(h.bounds(0.5).unwrap(), clone.bounds(0.5).unwrap());
        assert_eq!(h.bounds(1.0).unwrap(), bound_vec(bound));
    }
    fn bound_vec(b: I) -> Vec<I> {
        vec![b]
    }

    #[test]
    fn rejected_lowering_leaves_program_and_source_unchanged() {
        let mut p = program();
        p.states.push(crate::ir::State {
            instance: "dut".into(),
            name: "q".into(),
            kind: crate::ir::StateKind::Real,
            initial: 0.0,
        });
        let before = serde_json::to_string(&p).unwrap();
        let mut t = trajectory();
        let sources = t.config.pwl.clone();
        let mut driven = vec!["u".into()];
        assert_eq!(
            lower(&mut p, &mut driven, &mut t).unwrap_err().kind,
            "unsupported_transient"
        );
        assert_eq!(serde_json::to_string(&p).unwrap(), before);
        assert_eq!(t.config.pwl, sources);
        assert_eq!(driven, vec!["u"]);
    }

    #[test]
    fn appended_node_cannot_hide_original_invalid_contribution_endpoints() {
        for positive in [true, false] {
            let mut p = program();
            let original_count = p.nodes.len();
            if positive {
                p.contributions[0].positive = original_count;
            } else {
                p.contributions[0].negative = original_count;
            }
            let before = serde_json::to_string(&p).unwrap();
            let mut t = trajectory();
            let sources = t.config.pwl.clone();
            let mut driven = vec!["u".to_string()];
            assert_eq!(
                lower(&mut p, &mut driven, &mut t).unwrap_err().kind,
                "invalid_ir"
            );
            assert_eq!(serde_json::to_string(&p).unwrap(), before);
            assert_eq!(t.config.pwl, sources);
            assert_eq!(driven, vec!["u"]);
        }
    }

    #[test]
    fn appended_node_cannot_hide_original_invalid_index_or_owner() {
        let mut p = program();
        p.contributions[0].rhs = Expression::Affine {
            constant: 0.0,
            terms: vec![Term {
                node: 3,
                coefficient: 1.0,
            }],
        };
        assert_eq!(
            lower(&mut p, &mut vec!["u".into()], &mut trajectory())
                .unwrap_err()
                .kind,
            "invalid_ir"
        );
        let mut p = program();
        if let OperatorSpec::IdtMod {
            input: Expression::Select { origin, .. },
            ..
        } = &mut p.operators[0]
        {
            origin.instance = "other".into();
        }
        assert_eq!(
            lower(&mut p, &mut vec!["u".into()], &mut trajectory())
                .unwrap_err()
                .kind,
            "invalid_ir"
        );
    }
}
