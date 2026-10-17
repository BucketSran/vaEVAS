//! A candidate-owned held target selected by continuous transition histories.
//! Plans end before the next parent/source mutation. Each predicate is isolated
//! over a complete interval partition; observation samples never create cuts.
use super::*;

#[derive(Clone)]
pub(super) struct TargetPlan {
    work: crate::transition_source_plan::Work,
    expression: Expression,
    program: Arc<Program>,
    trajectory: Arc<Trajectory>,
    input_nodes: Vec<usize>,
    pub(super) dependencies: BTreeSet<usize>,
    cuts: Vec<I>,
    pub(super) selected: Expression,
    time: f64,
    window: I,
    valid_until: f64,
    parameters: Vec<I>,
    parents: Vec<(usize, Transition)>,
    exact_roots: Vec<(f64, crate::exact_source::RootTime)>,
    guards: Vec<(I, Expression)>,
}

fn failure(message: &str) -> Error {
    Error::new("condition_precision", message)
}
fn constant(x: f64) -> Expression {
    Expression::Affine {
        constant: x,
        terms: vec![],
    }
}

impl TargetPlan {
    pub(super) fn specification(
        e: &Expression,
        p: &Program,
        t: &Trajectory,
        driven: &[String],
        owner: &str,
        work: crate::transition_source_plan::Work,
    ) -> Result<Option<Self>, Error> {
        // Retain the established held/direct-source path whenever no internal
        // history occurs. Expansion is requested only for internal reads.
        let (nodes, _, operator_reads) = crate::continuous::integral_dependency_edges(e, p, owner)?;
        if operator_reads.is_empty()
            && nodes
                .iter()
                .all(|n| *n == 0 || driven.contains(&p.nodes[*n]))
        {
            return Ok(None);
        }
        let expression = crate::causal_voltage::expand(e, p, driven)?;
        fn ops(e: &Expression, out: &mut BTreeSet<usize>) {
            match e {
                Expression::Operator { operator } => {
                    out.insert(*operator);
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    ops(left, out);
                    ops(right, out);
                }
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for e in [left, right, then_value, else_value] {
                        ops(e, out);
                    }
                }
                _ => {}
            }
        }
        let mut dependencies = BTreeSet::new();
        ops(&expression, &mut dependencies);
        if dependencies.is_empty() {
            return Ok(None);
        }
        if dependencies
            .iter()
            .any(|&o| !matches!(p.operators[o], OperatorSpec::Transition { .. }))
        {
            return Err(failure(
                "target predicates require continuous transition histories",
            ));
        }
        for leaf in crate::transition_source_plan::forms(&expression, &work)? {
            let row = crate::affine_bounds::affine(&leaf, p)?;
            if row[..p.nodes.len()].iter().any(|v| !v.zero())
                || row[p.nodes.len() + p.states.len()..row.len() - 1]
                    .iter()
                    .any(|v| !v.zero())
            {
                return Err(Error::new(
                    "unsupported_operator",
                    "transition target leaves must contain held state and constants only",
                ));
            }
        }
        Ok(Some(Self {
            work,
            expression,
            program: Arc::new(p.clone()),
            trajectory: Arc::new(t.clone()),
            input_nodes: driven
                .iter()
                .map(|n| p.nodes.iter().position(|x| x == n).unwrap())
                .collect(),
            dependencies,
            cuts: vec![],
            selected: constant(0.),
            time: 0.,
            window: I::ZERO,
            valid_until: 0.,
            parameters: vec![],
            parents: vec![],
            exact_roots: vec![],
            guards: vec![],
        }))
    }
    pub(super) fn next_after(&self, after: f64) -> Option<f64> {
        self.cuts.iter().find(|c| c.hi > after).map(|c| c.hi)
    }
    pub(super) fn window_at(&self, time: f64) -> Option<I> {
        self.cuts.iter().find(|c| c.hi == time).copied()
    }
    pub(super) fn root_at(&self, time: f64) -> Option<&crate::exact_source::RootTime> {
        let count = self.guards.iter().filter(|(b, _)| b.hi == time).count();
        let roots: Vec<_> = self
            .exact_roots
            .iter()
            .filter(|(t, _)| *t == time)
            .map(|(_, r)| r)
            .collect();
        let first = *roots.first()?;
        (count == roots.len()
            && roots
                .iter()
                .all(|r| r.order(first) == std::cmp::Ordering::Equal))
        .then_some(first)
    }
    pub(super) fn coincides(
        &self,
        time: f64,
        guard: &Expression,
        driven: &[String],
    ) -> Result<bool, Error> {
        self.work.step()?;
        let mut found = false;
        for (_, predicate) in self.guards.iter().filter(|(b, _)| b.hi == time) {
            let projection = crate::event_accuracy::GuardBounds::stateful_parameters(
                &self.program,
                driven,
                &[Some(guard), Some(predicate)],
            )?;
            if !projection.same_zero_set(0, 1) {
                return Ok(false);
            }
            found = true;
        }
        Ok(found)
    }
    pub(super) fn same_epoch(&self, other: &Self) -> bool {
        self.expression == other.expression
            && Arc::ptr_eq(&self.program, &other.program)
            && Arc::ptr_eq(&self.trajectory, &other.trajectory)
            && self.selected == other.selected
            && self.time == other.time
            && self.window == other.window
            && self.cuts == other.cuts
            && self.valid_until == other.valid_until
            && self.parameters == other.parameters
            && self.parents == other.parents
            && self.exact_roots == other.exact_roots
            && self.guards == other.guards
    }
    fn range(
        &self,
        e: &Expression,
        t: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Result<(I, I), Error> {
        self.work.step()?;
        let (inputs, slopes) = self.trajectory.range(t)?;
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        let mut derivatives = nodes.clone();
        for ((&node, value), slope) in self.input_nodes.iter().zip(inputs).zip(slopes) {
            nodes[node] = value;
            derivatives[node] = slope;
        }
        let mut operators = vec![I::ZERO; entries.len()];
        let mut ds = operators.clone();
        let row = crate::affine_bounds::affine(e, &self.program)?;
        for &index in &self.dependencies {
            if row[self.program.nodes.len() + self.program.states.len() + index].zero() {
                continue;
            }
            let Runtime::Transition { history, .. } = &entries[index] else {
                return Err(failure("invalid parent history"));
            };
            let mut history = (**history).clone();
            history.advance_time(t.lo)?;
            (operators[index], ds[index]) = history.continuous_range(t)?;
        }
        let result =
            crate::guard_trajectory::evaluate(e, &nodes, &operators, states, &derivatives, &ds)?;
        if let Some(exact) = self
            .exact_form(e, t, states, entries)
            .and_then(|line| crate::exact_source::affine_range(line, t))
        {
            let value = I {
                lo: result.0.lo.max(exact.lo),
                hi: result.0.hi.min(exact.hi),
            };
            if value.lo > value.hi {
                return Err(failure(
                    "exact target predicate contradicts retained enclosure",
                ));
            }
            return Ok((value, result.1));
        }
        Ok(result)
    }
    fn resolve(
        &self,
        e: &Expression,
        t: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Result<Expression, Error> {
        Ok(match e {
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let a = self.resolve(left, t, states, entries)?;
                let b = self.resolve(right, t, states, entries)?;
                let difference = Expression::Add {
                    left: Box::new(a),
                    right: Box::new(Expression::Multiply {
                        left: Box::new(constant(-1.)),
                        right: Box::new(b),
                    }),
                };
                let (yes, no) = crate::event_numeric::sign(
                    *relation,
                    self.range(&difference, t, states, entries)?.0,
                );
                if !(yes || no) {
                    return Err(failure("history target mode has an unresolved predicate"));
                }
                return self.resolve(
                    if yes { then_value } else { else_value },
                    t,
                    states,
                    entries,
                );
            }
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(self.resolve(left, t, states, entries)?),
                right: Box::new(self.resolve(right, t, states, entries)?),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(self.resolve(left, t, states, entries)?),
                right: Box::new(self.resolve(right, t, states, entries)?),
            },
            _ => e.clone(),
        })
    }
    fn exact_form(
        &self,
        expression: &Expression,
        bounds: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Option<(num_rational::BigRational, num_rational::BigRational)> {
        use crate::exact_source::{binary, Budget};
        let row = crate::affine_bounds::affine(expression, &self.program).ok()?;
        let mut budget = Budget(0);
        let mut result = (binary(0.)?, binary(0.)?);
        let nodes = self.program.nodes.len();
        let ops = nodes + states.len();
        for (i, c) in row.iter().enumerate() {
            if c.zero() {
                continue;
            }
            if c.lo != c.hi {
                return None;
            }
            let line = if i == row.len() - 1 {
                (binary(1.)?, binary(0.)?)
            } else if i == 0 {
                (binary(0.)?, binary(0.)?)
            } else if i < nodes {
                let input = self.input_nodes.iter().position(|&n| n == i)?;
                self.trajectory
                    .exact_sources
                    .get(input)?
                    .as_ref()?
                    .affine_on(bounds)?
            } else if i < ops {
                let value = states[i - nodes];
                if value.lo != value.hi {
                    return None;
                }
                (binary(value.lo)?, binary(0.)?)
            } else {
                let Runtime::Transition { history, .. } = entries.get(i - ops)? else {
                    return None;
                };
                let mut history = (**history).clone();
                history.advance_time(bounds.lo).ok()?;
                history.exact_affine_on(bounds)?
            };
            let a = budget.check(binary(c.lo)? * line.0)?;
            result.0 = budget.check(result.0 + a)?;
            let b = budget.check(binary(c.lo)? * line.1)?;
            result.1 = budget.check(result.1 + b)?;
        }
        Some(result)
    }
    fn exact_root(
        &self,
        expression: &Expression,
        bounds: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Option<crate::exact_source::RootTime> {
        // Only the certified isolator calls this method. A point root was
        // proved zero, rather than merely containing zero within an etol.
        if bounds.lo == bounds.hi {
            return crate::exact_source::RootTime::point(bounds.lo);
        }
        let (a, b) = self.exact_form(expression, bounds, states, entries)?;
        crate::exact_source::RootTime::affine(a, b, bounds)
    }
    pub(super) fn prepared(
        &self,
        time: f64,
        window: I,
        states: &[I],
        entries: &[Runtime],
        until: f64,
    ) -> Result<Self, Error> {
        self.work.debit(2, 8192)?;
        let mut next = self.clone();
        next.time = time;
        next.window = window;
        next.cuts.clear();
        next.exact_roots.clear();
        next.guards.clear();
        let mut end = until;
        for &index in &self.dependencies {
            let entry = &entries[index];
            if let Runtime::Transition {
                history, source, ..
            } = entry
            {
                if let Some(t) = history.forcing_boundary(time) {
                    end = end.min(t);
                }
                if let Some(t) = source.as_ref().and_then(|s| s.next_after(time)) {
                    end = end.min(t);
                }
            }
        }
        if end <= time {
            return Err(failure("no certified future interval for history target"));
        }
        let mut predicates = Vec::new();
        fn collect(
            e: &Expression,
            out: &mut Vec<Expression>,
            work: &crate::transition_source_plan::Work,
        ) -> Result<(), Error> {
            match e {
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for a in [left, right, then_value, else_value] {
                        collect(a, out, work)?;
                    }
                    for a in crate::transition_source_plan::forms(left, work)? {
                        for b in crate::transition_source_plan::forms(right, work)? {
                            if out.len() >= 128 {
                                return Err(failure("history target predicate budget exhausted"));
                            }
                            out.push(Expression::Add {
                                left: Box::new(a.clone()),
                                right: Box::new(Expression::Multiply {
                                    left: Box::new(constant(-1.)),
                                    right: Box::new(b),
                                }),
                            });
                        }
                    }
                }
                Expression::Add { left, right } | Expression::Multiply { left, right } => {
                    collect(left, out, work)?;
                    collect(right, out, work)?;
                }
                _ => {}
            }
            Ok(())
        }
        fn held(e: &Expression, p: &Program, states: &[I]) -> Option<I> {
            let row = crate::affine_bounds::affine(e, p).ok()?;
            let count = p.nodes.len();
            let stop = count + p.states.len();
            if row[..count]
                .iter()
                .chain(&row[stop..row.len() - 1])
                .any(|v| !v.zero())
            {
                return None;
            }
            Some(
                row[count..stop]
                    .iter()
                    .zip(states)
                    .fold(*row.last()?, |sum, (&c, &s)| sum + c * s),
            )
        }
        fn simplify(e: &Expression, p: &Program, states: &[I]) -> Expression {
            let recurse = |e| simplify(e, p, states);
            match e {
                Expression::Select {
                    relation,
                    left,
                    right,
                    then_value,
                    else_value,
                    origin,
                } => {
                    let a = recurse(then_value);
                    let b = recurse(else_value);
                    if a == b
                        || held(&a, p, states)
                            .zip(held(&b, p, states))
                            .is_some_and(|(a, b)| a.lo == a.hi && a == b)
                    {
                        return a;
                    }
                    let left = recurse(left);
                    let right = recurse(right);
                    if let Some((av, bv)) = held(&left, p, states).zip(held(&right, p, states)) {
                        let (yes, no) = crate::event_numeric::sign(*relation, av - bv);
                        if yes {
                            return a;
                        }
                        if no {
                            return b;
                        }
                    }
                    Expression::Select {
                        relation: *relation,
                        left: Box::new(left),
                        right: Box::new(right),
                        then_value: Box::new(a),
                        else_value: Box::new(b),
                        origin: origin.clone(),
                    }
                }
                Expression::Add { left, right } => Expression::Add {
                    left: Box::new(recurse(left)),
                    right: Box::new(recurse(right)),
                },
                Expression::Multiply { left, right } => Expression::Multiply {
                    left: Box::new(recurse(left)),
                    right: Box::new(recurse(right)),
                },
                _ => e.clone(),
            }
        }
        let epoch = simplify(&self.expression, &self.program, states);
        let reusable=time<self.valid_until&&self.parameters==states&&self.parents.iter().all(|(i,old)|matches!(&entries[*i],Runtime::Transition{history,..} if !history.input_changed_from(old)));
        if reusable {
            end = end.min(self.valid_until);
            next.cuts = self
                .cuts
                .iter()
                .copied()
                .filter(|c| c.hi > time && c.hi <= end)
                .collect();
            next.exact_roots = self
                .exact_roots
                .iter()
                .filter(|(t, _)| *t > time && *t <= end)
                .cloned()
                .collect();
            next.guards = self
                .guards
                .iter()
                .filter(|(b, _)| b.hi > time && b.hi <= end)
                .cloned()
                .collect();
        } else {
            self.work.debit(0, 1)?;
            collect(&epoch, &mut predicates, &self.work)?;
            let mut partition = vec![time, end];
            partition.extend(
                self.trajectory
                    .knots
                    .iter()
                    .copied()
                    .filter(|&t| t > time && t < end),
            );
            partition.sort_by(f64::total_cmp);
            partition.dedup();
            for predicate in predicates {
                let proofs = states
                    .iter()
                    .enumerate()
                    .filter_map(|(i, v)| {
                        (v.lo == v.hi)
                            .then(|| crate::exact_source::RootTime::point(v.lo).map(|r| (i, r)))
                            .flatten()
                    })
                    .collect();
                if let Some(curve) = self.trajectory.original_guard_curve_with_states(
                    &predicate,
                    &self.input_nodes,
                    end,
                    &proofs,
                ) {
                    self.work.debit(2, 200_000)?;
                    let roots = curve
                        .isolated_zero_times()
                        .ok_or_else(|| failure("unproved complete history target source cuts"))?;
                    for root in roots {
                        if curve.sign_at_root(&root) != Some(0) {
                            continue;
                        }
                        let bounds = root
                            .bounds()
                            .ok_or_else(|| failure("invalid exact history target root"))?;
                        if bounds.hi > time && bounds.hi <= end {
                            self.work.debit(1, 1)?;
                            next.cuts.push(bounds);
                            next.guards.push((bounds, predicate.clone()));
                            next.exact_roots.push((bounds.hi, root));
                        }
                    }
                    continue;
                }
                for part in partition.windows(2) {
                    let bounds = I {
                        lo: part[0],
                        hi: part[1],
                    };
                    let whole = self.range(&predicate, bounds, states, entries)?.0;
                    if matches!(whole.sign(), Some(-1..=1)) {
                        continue;
                    }
                    let mut value = |t| self.range(&predicate, t, states, entries).map(|v| v.0);
                    let mut derivative =
                        |t| self.range(&predicate, t, states, entries).map(|v| v.1);
                    for root in crate::dynamic_roots::isolate_history(
                        part[0],
                        part[1],
                        &mut value,
                        &mut derivative,
                        0,
                        (end - time) * 1e-12,
                        1e-12,
                    )? {
                        if root.bounds.hi > time {
                            let exact = self.exact_root(&predicate, root.bounds, states, entries);
                            let bounds = exact
                                .as_ref()
                                .and_then(|r| r.refine(root.bounds))
                                .unwrap_or(root.bounds);
                            if let Some(exact) = exact {
                                next.exact_roots.push((bounds.hi, exact));
                            }
                            self.work.debit(1, 1)?;
                            next.cuts.push(bounds);
                            next.guards.push((bounds, predicate.clone()));
                        }
                    }
                }
            }
            next.guards.sort_by(|a, b| a.0.hi.total_cmp(&b.0.hi));
            for pair in next.guards.windows(2) {
                self.work.step()?;
                if pair[0].0.hi >= pair[1].0.lo {
                    let same_root = next
                        .root_at(pair[0].0.hi)
                        .zip(next.root_at(pair[1].0.hi))
                        .is_some_and(|(a, b)| a.order(b) == std::cmp::Ordering::Equal);
                    let same_guard = crate::event_accuracy::GuardBounds::stateful_parameters(
                        &self.program,
                        &self
                            .input_nodes
                            .iter()
                            .map(|&n| self.program.nodes[n].clone())
                            .collect::<Vec<_>>(),
                        &[Some(&pair[0].1), Some(&pair[1].1)],
                    )?
                    .same_zero_set(0, 1);
                    if !same_root && !same_guard {
                        return Err(failure(
                            "overlapping history target roots lack an equality proof",
                        ));
                    }
                }
            }
            next.cuts.sort_by(|a, b| a.hi.total_cmp(&b.hi));
            next.cuts.dedup();
            for pair in next.cuts.windows(2) {
                if pair[0].hi >= pair[1].lo {
                    return Err(failure("history target roots cannot be ordered"));
                }
            }
        }
        let right = next.cuts.first().map_or(end, |c| c.lo);
        let probe = time * 0.5 + right * 0.5;
        let interval = if probe > time && probe < right {
            I::point(probe)
        } else {
            I {
                lo: time,
                hi: right,
            }
        };
        next.selected = self.resolve(&epoch, interval, states, entries)?;
        next.valid_until = end;
        next.parameters = states.to_vec();
        next.parents = self
            .dependencies
            .iter()
            .map(|&i| {
                let Runtime::Transition { history, .. } = &entries[i] else {
                    unreachable!()
                };
                (i, (**history).clone())
            })
            .collect();
        Ok(next)
    }
}

#[cfg(test)]
mod lifecycle_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn request_budget_failure_discards_parent_queue_and_is_not_refunded() {
        let origin = |column| json!({"source":"history-target-budget.va","line":1,"column":column,"instance":"dut"});
        let target = json!({"op":"select","relation":"gt","left":{"op":"operator","operator":0},"right":{"op":"affine","constant":0.5,"terms":[]},"then_value":{"op":"affine","constant":1.,"terms":[]},"else_value":{"op":"affine","constant":0.,"terms":[]},"origin":origin(2)});
        let program:Program=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","z","y"],
            "states":[{"instance":"dut","name":"s","kind":"real","initial":0.}],
            "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.25,"fall":0.25,"origin":origin(1)},
                {"kind":"transition","input":target,"delay":0.,"rise":0.25,"fall":0.25,"origin":origin(2)}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"z","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(3)},
                {"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)}]})).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [1., 0.]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        let mut accepted = Operators::new(&program, &trajectory, &["u".into()], &[0.]).unwrap();
        accepted.history_targets.get_mut(&1).unwrap().work =
            crate::transition_source_plan::Work::limited([0, 8192, 1_000_000_000]);
        let before = accepted.clone();
        let original = accepted.bounds(0.5).unwrap();
        for _ in 0..2 {
            let frozen = accepted.evaluation(0.25).unwrap();
            let error = frozen
                .advanced(I::point(0.25), &[1.], &[I::ONE], &[0])
                .err()
                .unwrap();
            assert_eq!(error.kind, "step_budget");
            assert!(accepted.same_reset_history(&before));
            assert_eq!(accepted.bounds(0.5).unwrap(), original);
            assert_eq!(accepted.next_breakpoint(0.25), before.next_breakpoint(0.25));
        }
    }
}
