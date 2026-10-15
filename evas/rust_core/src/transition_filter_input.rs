//! Feed-forward affine source coefficients for one accepted transition.
use crate::interval::Interval as I;
use crate::ir::{Expression, OperatorSpec, Program};
use crate::pwl::Trajectory;
use std::collections::BTreeSet;

#[derive(Clone, PartialEq)]
pub(crate) struct Spec {
    pub parent: usize,
    a: Vec<I>,
    b: Vec<I>,
}
#[derive(Clone, PartialEq)]
pub(crate) struct Bound {
    spec: Spec,
    sources: Vec<Vec<[f64; 2]>>,
}
#[derive(Clone)]
struct Form {
    // Structural live-source dependence survives cancellation and zero scale.
    live_source: bool,
    parent: Option<usize>,
    a: Vec<I>,
    b: Vec<I>,
}
impl Form {
    fn constant(width: usize, c: I) -> Self {
        let mut b = vec![I::ZERO; width];
        b[width - 1] = c;
        Self {
            live_source: false,
            parent: None,
            a: vec![I::ZERO; width],
            b,
        }
    }
    fn scalar(&self) -> Option<I> {
        (self.parent.is_none() && !self.live_source).then(|| *self.b.last().unwrap())
    }
    fn scale(mut self, scale: I) -> Self {
        for x in self.a.iter_mut().chain(&mut self.b) {
            *x = *x * scale;
        }
        self
    }
    fn add(mut self, rhs: Self) -> Option<Self> {
        if self.parent.is_some() && rhs.parent.is_some() && self.parent != rhs.parent {
            return None;
        }
        self.parent = self.parent.or(rhs.parent);
        self.live_source |= rhs.live_source;
        for (x, y) in self
            .a
            .iter_mut()
            .chain(&mut self.b)
            .zip(rhs.a.into_iter().chain(rhs.b))
        {
            *x = *x + y;
        }
        Some(self)
    }
    fn multiply(self, rhs: Self) -> Option<Self> {
        if let Some(c) = self.scalar() {
            return Some(rhs.scale(c));
        }
        if let Some(c) = rhs.scalar() {
            return Some(self.scale(c));
        }
        let (plain, edge) = if self.parent.is_none() {
            (self, rhs)
        } else {
            (rhs, self)
        };
        // A source-affine coefficient may multiply a constant affine function
        // of one edge. Neither two source slopes nor two edges may multiply.
        if plain.parent.is_some() || edge.parent.is_none() || edge.live_source {
            return None;
        }
        let ca = *edge.a.last()?;
        let cb = *edge.b.last()?;
        Some(Self {
            live_source: plain.live_source,
            parent: edge.parent,
            a: plain.b.iter().map(|&x| x * ca).collect(),
            b: plain.b.iter().map(|&x| x * cb).collect(),
        })
    }
}
struct Parser<'a> {
    program: &'a Program,
    driven: &'a [String],
    owner: &'a str,
    visiting: BTreeSet<usize>,
}
impl Parser<'_> {
    fn node(&mut self, node: usize) -> Option<Form> {
        let width = self.driven.len() + 1;
        if node == 0 {
            return Some(Form::constant(width, I::ZERO));
        }
        if let Some(k) = self
            .driven
            .iter()
            .position(|n| n == &self.program.nodes[node])
        {
            let mut out = Form::constant(width, I::ZERO);
            out.b[k] = I::ONE;
            out.live_source = true;
            return Some(out);
        }
        if !self.visiting.insert(node) {
            return None;
        }
        let cs: Vec<_> = self
            .program
            .contributions
            .iter()
            .filter(|c| c.positive == node || c.negative == node)
            .collect();
        let first = *cs.first()?;
        // Only unique grounded voltage definitions are aliases. Multiple
        // contributions on that same branch add, just as the circuit does.
        if !((first.positive == node && first.negative == 0)
            || (first.positive == 0 && first.negative == node))
            || cs.iter().any(|c| {
                c.branch != first.branch
                    || c.positive != first.positive
                    || c.negative != first.negative
            })
        {
            return None;
        }
        let mut out = Form::constant(width, I::ZERO);
        for c in cs {
            out = out.add(
                self.expression(&c.rhs)?
                    .scale(I::point(if c.positive == node { 1. } else { -1. })),
            )?;
        }
        self.visiting.remove(&node);
        Some(out)
    }
    fn expression(&mut self, e: &Expression) -> Option<Form> {
        let width = self.driven.len() + 1;
        match e {
            Expression::Affine { constant, terms } => {
                let mut f = Form::constant(width, I::point(*constant));
                // Visit every original term, including explicit zero terms.
                for t in terms {
                    f = f.add(self.node(t.node)?.scale(I::point(t.coefficient)))?;
                }
                Some(f)
            }
            Expression::Operator { operator } => {
                let OperatorSpec::Transition { input, origin, .. } =
                    &self.program.operators[*operator]
                else {
                    return None;
                };
                if origin.instance != self.owner {
                    return None;
                }
                let a = crate::events::affine(input, self.program, self.owner).ok()?;
                if !a.node_dependencies.is_empty() || !a.operator_dependencies.is_empty() {
                    return None;
                }
                let mut f = Form::constant(width, I::ZERO);
                f.parent = Some(*operator);
                f.a[width - 1] = I::ONE;
                Some(f)
            }
            Expression::Add { left, right } => self.expression(left)?.add(self.expression(right)?),
            Expression::Multiply { left, right } => {
                self.expression(left)?.multiply(self.expression(right)?)
            }
            Expression::Divide { left, right } => {
                let a = self.expression(left)?;
                let b = self.expression(right)?;
                let c = b.scalar()?;
                if c.lo <= 0. && c.hi >= 0. {
                    return None;
                }
                Some(a.scale(I::ONE / c))
            }
            // No selections, direct event states, powers or nonlinear math.
            _ => None,
        }
    }
}
pub(crate) fn specification(program: &Program, driven: &[String], index: usize) -> Option<Spec> {
    let OperatorSpec::LaplaceNd {
        input,
        numerator,
        denominator,
        origin,
    } = &program.operators[index]
    else {
        return None;
    };
    if numerator.len() != 1
        || denominator.len() != 2
        || !numerator[0].is_finite()
        || denominator.iter().any(|x| !x.is_finite() || *x <= 0.)
    {
        return None;
    }
    let mut parser = Parser {
        program,
        driven,
        owner: &origin.instance,
        visiting: BTreeSet::new(),
    };
    let f = parser.expression(input)?;
    if f.a.iter().chain(&f.b).any(|x| !x.finite()) {
        return None;
    }
    Some(Spec {
        parent: f.parent?,
        a: f.a,
        b: f.b,
    })
}
impl Spec {
    pub(crate) fn bind(self, trajectory: &Trajectory) -> Option<Bound> {
        if !trajectory.has_only_physical_inputs() {
            return None;
        }
        Some(Bound {
            spec: self,
            sources: trajectory.config.pwl.clone(),
        })
    }
}
impl Bound {
    pub(crate) fn boundary(&self, time: f64) -> Option<f64> {
        self.sources
            .iter()
            .enumerate()
            .filter(|(k, _)| !self.spec.a[*k].zero() || !self.spec.b[*k].zero())
            .flat_map(|(_, s)| s.iter().map(|p| p[0]))
            .filter(|&t| t > time)
            .min_by(f64::total_cmp)
    }
    pub(crate) fn line(&self, time: f64) -> ((I, I), (I, I)) {
        let mut a = (*self.spec.a.last().unwrap(), I::ZERO);
        let mut b = (*self.spec.b.last().unwrap(), I::ZERO);
        for (k, s) in self.sources.iter().enumerate() {
            // Eligibility retained the original dependency graph. Arithmetic
            // need only bind source rows actually used in this affine form.
            if self.spec.a[k].zero() && self.spec.b[k].zero() {
                continue;
            }
            let n = s.partition_point(|p| p[0] <= time).saturating_sub(1);
            let (v, d) = if n + 1 >= s.len() {
                (I::point(s[n][1]), I::ZERO)
            } else {
                let d = (I::point(s[n + 1][1]) - I::point(s[n][1]))
                    / (I::point(s[n + 1][0]) - I::point(s[n][0]));
                (
                    I::point(s[n][1]) + d * (I::point(time) - I::point(s[n][0])),
                    d,
                )
            };
            a.0 = a.0 + self.spec.a[k] * v;
            a.1 = a.1 + self.spec.a[k] * d;
            b.0 = b.0 + self.spec.b[k] * v;
            b.1 = b.1 + self.spec.b[k] * d;
        }
        (a, b)
    }
    pub(crate) fn range(&self, times: I, edge: I) -> I {
        let mut a = I::ZERO;
        let mut b = I::ZERO;
        let mut start = times.lo;
        loop {
            let end = self.boundary(start).unwrap_or(times.hi).min(times.hi);
            let ((av, ad), (bv, bd)) = self.line(start);
            let h = I {
                lo: 0.,
                hi: (I::point(end) - I::point(start)).hi,
            };
            let ar = av + ad * h;
            let br = bv + bd * h;
            if start == times.lo {
                a = ar;
                b = br;
            } else {
                a = a.hull(ar);
                b = b.hull(br);
            }
            if end >= times.hi {
                break;
            }
            start = end;
        }
        a * edge + b
    }
}

#[cfg(test)]
pub(super) fn test_bound(a: [f64; 2], b: [f64; 2], points: Vec<[f64; 2]>) -> Bound {
    Bound {
        spec: Spec {
            parent: 0,
            a: a.map(I::point).to_vec(),
            b: b.map(I::point).to_vec(),
        },
        sources: vec![points],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    fn affine(node: usize) -> Value {
        json!({"op":"affine","constant":0,"terms":[{"node":node,"coefficient":1}]})
    }
    fn product(a: Value, b: Value) -> Value {
        json!({"op":"multiply","left":a,"right":b})
    }
    fn plus(a: Value, b: Value) -> Value {
        json!({"op":"add","left":a,"right":b})
    }
    fn zero() -> Value {
        json!({"op":"affine","constant":0,"terms":[]})
    }
    fn op(k: usize) -> Value {
        json!({"op":"operator","operator":k})
    }
    fn program(input: Value) -> Program {
        let origin = json!({"source":"live.va","line":1,"column":1,"instance":"M"});
        serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","u","h","y","f"],"states":[{"instance":"M","name":"q","kind":"real","initial":0}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":1,"fall":1,"origin":origin},
                {"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":1,"fall":1,"origin":origin},
                {"kind":"laplace_nd","input":input,"numerator":[1],"denominator":[1,1],"origin":origin}],
            "contributions":[
                {"branch":{"instance":"M","local_positive":"h","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":affine(1),"origin":origin},
                {"branch":{"instance":"M","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":product(affine(2),op(0)),"origin":origin},
                {"branch":{"instance":"M","local_positive":"f","local_negative":"r","kind":"voltage"},"positive":4,"negative":0,"rhs":op(2),"origin":origin}]
        })).unwrap()
    }
    #[test]
    fn original_dependencies_survive_zero_scale_cancellation_and_all_select_arms() {
        let valid = product(affine(1), op(0));
        assert!(specification(&program(valid.clone()), &["u".into()], 2).is_some());
        let invalid = [
            plus(valid.clone(), product(zero(), affine(4))),
            plus(valid.clone(), product(zero(), op(1))),
            plus(
                valid.clone(),
                product(zero(), json!({"op":"state","state":0})),
            ),
            product(product(zero(), affine(1)), product(affine(1), op(0))),
            json!({"op":"select","relation":"gt","left":affine(1),"right":zero(),"then_value":valid,"else_value":product(zero(),affine(4)),"origin":{"source":"live.va","line":1,"column":1,"instance":"M"}}),
        ];
        for expr in invalid {
            assert!(specification(&program(expr), &["u".into()], 2).is_none());
        }
    }
    #[test]
    fn voltage_definition_cycles_ambiguity_and_source_parent_are_not_aliases() {
        let mut p = program(affine(3));
        assert!(specification(&p, &["u".into()], 2).is_some());
        p.contributions[0].rhs = serde_json::from_value(affine(3)).unwrap();
        assert!(specification(&p, &["u".into()], 2).is_none());
        let mut p = program(affine(3));
        let mut duplicate = p.contributions[0].clone();
        duplicate.branch.local_positive = "another".into();
        p.contributions.push(duplicate);
        assert!(specification(&p, &["u".into()], 2).is_none());
        let mut p = program(affine(3));
        if let OperatorSpec::Transition { input, .. } = &mut p.operators[0] {
            *input = serde_json::from_value(affine(1)).unwrap();
        }
        assert!(specification(&p, &["u".into()], 2).is_none());
    }
}
