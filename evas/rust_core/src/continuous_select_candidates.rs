//! Conservative mode enumeration for predicates containing selected values.
//! Every possible affine arm contributes roots, even when that arm is inactive.
//! Extra cuts are safe; missing a parent root can change an integral silently.
use super::*;

fn precision(message: &str) -> Error {
    Error::new("condition_precision", message)
}
fn spend(budget: &mut usize) -> Result<(), Error> {
    if *budget == 0 {
        return Err(precision("nested predicate expansion budget exhausted"));
    }
    *budget -= 1;
    Ok(())
}

pub(super) fn nested(expr: &Expression) -> bool {
    match expr {
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            crate::analog::has_select(left)
                || crate::analog::has_select(right)
                || nested(then_value)
                || nested(else_value)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => nested(left) || nested(right),
        Expression::Power { base, .. } => nested(base),
        _ => false,
    }
}

pub(super) fn forms(expr: &Expression, budget: &mut usize) -> Result<Vec<Expression>, Error> {
    spend(budget)?;
    match expr {
        Expression::Select {
            then_value,
            else_value,
            ..
        } => {
            let mut out = forms(then_value, budget)?;
            out.extend(forms(else_value, budget)?);
            Ok(out)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            let a = forms(left, budget)?;
            let b = forms(right, budget)?;
            let mut out = Vec::new();
            for left in &a {
                for right in &b {
                    spend(budget)?;
                    let left = Box::new(left.clone());
                    let right = Box::new(right.clone());
                    out.push(match expr {
                        Expression::Add { .. } => Expression::Add { left, right },
                        Expression::Multiply { .. } => Expression::Multiply { left, right },
                        _ => Expression::Divide { left, right },
                    });
                }
            }
            Ok(out)
        }
        Expression::Power { .. } => Err(Error::new(
            "unsupported_transient",
            "non-affine nested predicate power",
        )),
        // A power containing a selection is not an admitted affine predicate.
        // Leave it intact so the existing affine validator rejects it.
        _ => Ok(vec![expr.clone()]),
    }
}

struct Root {
    value: I,
    left: Expression,
    right: Expression,
    segment: usize,
}

fn original_predicate_curve(
    left: &Expression,
    right: &Expression,
    program: &Program,
    driven: &[String],
    trajectory: &Trajectory,
    states: &[I],
) -> Option<crate::exact_source::Curve> {
    // Preserve the original expression tree, not rounded affine coefficients.
    // An uncertain held value or unavailable original source gives no proof.
    let guard = Expression::Add {
        left: Box::new(bind_states(left, states).ok()?),
        right: Box::new(Expression::Multiply {
            left: Box::new(Expression::Affine {
                constant: -1.0,
                terms: vec![],
            }),
            right: Box::new(bind_states(right, states).ok()?),
        }),
    };
    let input_nodes = driven
        .iter()
        .map(|name| program.nodes.iter().position(|n| n == name))
        .collect::<Option<Vec<_>>>()?;
    trajectory.original_guard_curve_until(&guard, &input_nodes, *trajectory.knots.last()?)
}
pub(super) struct Roots {
    roots: Vec<Root>,
    budget: usize,
    // A root analysis belongs to an expression pair on this one fixed source/
    // held-state context. Repeated occurrences do not add physical boundaries.
    analyzed: Vec<(Expression, Expression)>,
}
impl Roots {
    pub(super) fn new() -> Self {
        Self {
            roots: vec![],
            budget: 8192,
            analyzed: vec![],
        }
    }
    pub(super) fn collect(
        &mut self,
        expr: &Expression,
        program: &Program,
        driven: &[String],
        trajectory: &Trajectory,
        states: &[I],
    ) -> Result<(), Error> {
        spend(&mut self.budget)?;
        match expr {
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                // Conditions nested inside conditions also introduce cuts.
                for child in [left, right, then_value, else_value] {
                    self.collect(child, program, driven, trajectory, states)?;
                }
                let a = forms(left, &mut self.budget)?;
                let b = forms(right, &mut self.budget)?;
                for left in &a {
                    for right in &b {
                        predicate(left, program, driven, &origin.instance)?;
                        predicate(right, program, driven, &origin.instance)?;
                        if self.analyzed.iter().any(|(a, b)| a == left && b == right) {
                            continue;
                        }
                        spend(&mut self.budget)?;
                        let a = affine_bounds::affine(left, program)?;
                        let b = affine_bounds::affine(right, program)?;
                        // A held-only condition cannot introduce a temporal
                        // root within this epoch. Physical mode resolution still
                        // rejects an uncertain comparison; mesh activation may
                        // conservatively request either branch's bound.
                        if a[..program.nodes.len()].iter().all(|x| x.zero())
                            && b[..program.nodes.len()].iter().all(|x| x.zero()) {
                            self.analyzed.push((left.clone(),right.clone()));
                            continue;
                        }
                        let exact = original_predicate_curve(
                            left, right, program, driven, trajectory, states,
                        );
                        let at = |time| {
                            let mut nodes = vec![I::ZERO; program.nodes.len()];
                            for (name, v) in driven.iter().zip(trajectory.value_bounds(time)) {
                                nodes[program.nodes.iter().position(|n| n == name).unwrap()] = v;
                            }
                            let eval = |row: &Vec<I>| {
                                row.iter()
                                    .zip(nodes.iter().chain(states))
                                    .filter(|(c, _)| !c.zero())
                                    .fold(*row.last().unwrap(), |v, (&c, &x)| v + c * x)
                            };
                            eval(&a) - eval(&b)
                        };
                        for (segment, pair) in trajectory.knots.windows(2).enumerate() {
                            spend(&mut self.budget)?;
                            let (lo, hi) = (at(pair[0]), at(pair[1]));
                            let (Some(ls), Some(hs)) = (lo.sign(), hi.sign()) else {
                                return Err(precision(
                                    "uncertain nested predicate segment endpoint",
                                ));
                            };
                            // Affine interpolation cannot cross zero between same-sign
                            // endpoints. Exact zero endpoints are already PWL knots.
                            if ls == hs || ls == 0 || hs == 0 {
                                continue;
                            }
                            let mut root = I::point(pair[0])
                                - lo * (I::point(pair[1]) - I::point(pair[0])) / (hi - lo);
                            if !root.finite() || root.lo <= pair[0] || root.hi >= pair[1] {
                                return Err(precision(
                                    "cannot isolate nested predicate breakpoint",
                                ));
                            }
                            if let Some(point) = exact
                                .as_ref()
                                .and_then(|curve| curve.root_in([pair[0], pair[1]], [lo, hi], root))
                                .and_then(|time| time.bounds())
                                .filter(|b| b.lo == b.hi)
                            {
                                root = point;
                            }
                            // Equal enclosures are not evidence that two roots agree.
                            // Reuse only the identical expression on the identical segment.
                            if self.roots.iter().any(|r| {
                                r.segment == segment && r.left == *left && r.right == *right
                            }) {
                                continue;
                            }
                            self.roots.push(Root {
                                value: root,
                                left: left.clone(),
                                right: right.clone(),
                                segment,
                            });
                        }
                        // Failed scans must remain failures if a caller retries.
                        self.analyzed.push((left.clone(), right.clone()));
                    }
                }
                Ok(())
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.collect(left, program, driven, trajectory, states)?;
                self.collect(right, program, driven, trajectory, states)
            }
            Expression::Power { base, .. } => {
                self.collect(base, program, driven, trajectory, states)
            }
            _ => Ok(()),
        }
    }
    // Keep full certificates at physical endpoints. The nonlinear consumer
    // owns a certified history segment over the clipped physical coverage.
    pub(super) fn window_roots(self, start: f64, horizon: f64) -> Result<Vec<I>, Error> {
        let mut roots: Vec<_> = self.roots.into_iter().map(|r| r.value)
            .filter(|r| r.hi >= start && r.lo <= horizon).collect();
        roots.sort_by(|a,b| a.lo.total_cmp(&b.lo).then(a.hi.total_cmp(&b.hi)));
        for pair in roots.windows(2) {
            let (a,b)=(pair[0],pair[1]);
            if a.hi >= b.lo && !(a.lo==a.hi && a==b) {
                return Err(precision("distinct physical root certificates overlap"));
            }
        }
        roots.dedup();
        Ok(roots)
    }
    pub(super) fn finish(self, cuts: &mut Vec<I>, start: f64, horizon: f64) -> Result<(), Error> {
        for root in self.roots {
            let c = root.value;
            if c.hi < start || c.lo > horizon {
                continue;
            }
            if c.lo != c.hi && (c.lo <= start || c.hi >= horizon) {
                return Err(precision(
                    "nested predicate root overlaps integration endpoint",
                ));
            }
            cuts.push(c);
        }
        cuts.sort_by(|a, b| a.lo.total_cmp(&b.lo).then(a.hi.total_cmp(&b.hi)));
        for pair in cuts.windows(2) {
            let (a, b) = (pair[0], pair[1]);
            if a.hi >= b.lo && !(a.lo == a.hi && b.lo == b.hi && a.lo == b.lo) {
                return Err(precision(
                    "distinct nested predicate root enclosures overlap",
                ));
            }
        }
        // Every consumer freezes one mode using a representable interior point.
        // Enforce this here for both linear and nonlinear propagation.
        cuts.dedup();
        for pair in cuts.windows(2) {
            let midpoint = pair[0].hi * 0.5 + pair[1].lo * 0.5;
            if midpoint <= pair[0].hi || midpoint >= pair[1].lo {
                return Err(precision("no representable interior of selected mode"));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "continuous_select_cache_tests.rs"]
mod cache_tests;
