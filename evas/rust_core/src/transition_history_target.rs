//! A candidate-owned held target selected by continuous transition histories.
//! Plans end before the next parent/source mutation. Each predicate is isolated
//! over a complete interval partition; observation samples never create cuts.
use super::*;

#[derive(Clone)]
pub(super) struct TargetPlan {
    predicate_only: bool,
    metered: bool,
    predicate_states: BTreeSet<usize>,
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

// The existing equality contract treats signed zeros numerically. Dedup needs
// every floating field's bits too; keep that stricter contract local here.
fn same_predicate_operand(
    a: &Expression,
    b: &Expression,
    w: &crate::transition_source_plan::Work,
) -> Result<bool, Error> {
    w.debit(2, 0)?;
    if !crate::history_admission::same_expression_full(a, b, w)? {
        return Ok(false);
    }
    fn bits(
        a: &Expression,
        b: &Expression,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        w.step()?;
        Ok(match (a, b) {
            (
                Expression::Affine {
                    constant: a,
                    terms: at,
                },
                Expression::Affine {
                    constant: b,
                    terms: bt,
                },
            ) => {
                w.step()?;
                if a.to_bits() != b.to_bits() {
                    return Ok(false);
                }
                for (a, b) in at.iter().zip(bt) {
                    w.step()?;
                    if a.coefficient.to_bits() != b.coefficient.to_bits() {
                        return Ok(false);
                    }
                }
                true
            }
            (Expression::State { .. }, Expression::State { .. })
            | (Expression::Operator { .. }, Expression::Operator { .. }) => true,
            (Expression::Add { left: a, right: b }, Expression::Add { left: c, right: d })
            | (
                Expression::Multiply { left: a, right: b },
                Expression::Multiply { left: c, right: d },
            )
            | (
                Expression::Divide { left: a, right: b },
                Expression::Divide { left: c, right: d },
            ) => bits(a, c, w)? && bits(b, d, w)?,
            (
                Expression::Select {
                    left: a,
                    right: b,
                    then_value: at,
                    else_value: ae,
                    ..
                },
                Expression::Select {
                    left: c,
                    right: d,
                    then_value: bt,
                    else_value: be,
                    ..
                },
            ) => bits(a, c, w)? && bits(b, d, w)? && bits(at, bt, w)? && bits(ae, be, w)?,
            _ => false,
        })
    }
    bits(a, b, w)
}

// Same prepared context and epoch only. Audit each complete pair before using
// an existing full AST representative; equal interval rows are insufficient.
fn retain_history_predicate(
    out: &mut Vec<Expression>,
    a: &Expression,
    b: Expression,
    program: &Program,
    work: &crate::transition_source_plan::Work,
) -> Result<(), Error> {
    work.debit(2, 0)?;
    let ar = crate::history_admission::affine_paid(a, program, work)?;
    let br = crate::history_admission::affine_paid(&b, program, work)?;
    let n = ar.len() - 1;
    for k in 0..=n {
        work.step()?;
        // Exactly the original Add(a, Multiply(constant(-1), b)) order.
        let negative = if k == n {
            I::point(-1.) * br[n]
        } else {
            I::ZERO * br[n] + br[k] * I::point(-1.)
        };
        if !(ar[k] + negative).finite() {
            return Err(Error::new(
                "unsupported_condition",
                "nonfinite original history affine coefficient",
            ));
        }
    }
    for old in out.iter() {
        work.step()?;
        if let Expression::Add { left, right } = old {
            work.step()?;
            if let Expression::Multiply {
                left: scale,
                right: old_b,
            } = right.as_ref()
            {
                work.step()?;
                if let Expression::Affine { constant, terms } = scale.as_ref() {
                    work.debit(2, 2)?;
                    if constant.to_bits() == (-1.0f64).to_bits()
                        && terms.is_empty()
                        && same_predicate_operand(a, left, work)?
                        && same_predicate_operand(&b, old_b, work)?
                    {
                        return Ok(());
                    }
                }
            }
        }
    }
    if out.len() >= 128 {
        return Err(failure("history target predicate budget exhausted"));
    }
    work.debit(2, 5)?;
    let value = Expression::Add {
        left: Box::new(crate::history_admission::copy_expression(a, work)?),
        right: Box::new(Expression::Multiply {
            left: Box::new(constant(-1.)),
            right: Box::new(b),
        }),
    };
    crate::history_storage::push_vec(out, value, work)
}

impl TargetPlan {
    pub(super) fn predicate_specification(
        token: &crate::history_admission::Admission,
        index: usize,
    ) -> Result<Option<Self>, Error> {
        let w = token.context.borrow_work();
        w.step()?;
        fn selected(
            e: &Expression,
            w: &crate::transition_source_plan::Work,
        ) -> Result<bool, Error> {
            w.step()?;
            Ok(match e {
                Expression::Select { .. } => true,
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => selected(left, w)? || selected(right, w)?,
                _ => false,
            })
        }
        let e = &token.expanded[index];
        if !selected(e, w)? {
            return Ok(None);
        }
        fn dependencies(
            e: &Expression,
            w: &crate::transition_source_plan::Work,
            states: &mut BTreeSet<usize>,
            operators: &mut BTreeSet<usize>,
            read: bool,
        ) -> Result<(), Error> {
            w.step()?;
            match e {
                Expression::State { state } if read => {
                    w.debit(2, 1)?;
                    states.insert(*state);
                }
                Expression::Operator { operator } if read => {
                    w.debit(2, 1)?;
                    operators.insert(*operator);
                }
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    dependencies(left, w, states, operators, true)?;
                    dependencies(right, w, states, operators, true)?;
                    dependencies(then_value, w, states, operators, read)?;
                    dependencies(else_value, w, states, operators, read)?;
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    dependencies(left, w, states, operators, read)?;
                    dependencies(right, w, states, operators, read)?;
                }
                _ => (),
            }
            Ok(())
        }
        let mut predicate_states = BTreeSet::new();
        let mut parents = BTreeSet::new();
        dependencies(e, w, &mut predicate_states, &mut parents, false)?;
        for parent in &parents {
            w.step()?;
            if !token.dependencies[index].contains(parent) {
                return Err(failure(
                    "predicate dependency is outside original admission",
                ));
            }
        }
        w.debit(2, token.context.event_input_nodes().len() as u64)?;
        Ok(Some(Self {
            predicate_only: true,
            metered: true,
            predicate_states,
            work: w.clone(),
            expression: crate::history_admission::copy_expression(e, w)?,
            program: token.context.program_arc(),
            trajectory: token.context.trajectory_arc(),
            input_nodes: token.context.event_input_nodes().to_vec(),
            dependencies: parents,
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
    pub(super) fn charge_copy(&self) -> Result<(), Error> {
        if !self.metered {
            return Ok(());
        }
        self.work.debit(2, 18)?;
        if !self.predicate_only {
            self.work.debit(
                2,
                (self.dependencies.len() + self.predicate_states.len() + 1).saturating_mul(64)
                    as u64,
            )?;
        }
        crate::history_admission::charge_expression_copy(&self.expression, &self.work)?;
        crate::history_admission::charge_expression_copy(&self.selected, &self.work)?;
        self.work.debit(
            2,
            (self.input_nodes.len()
                + self.dependencies.len()
                + self.predicate_states.len()
                + self.cuts.len() * 2
                + self.parameters.len() * 2) as u64,
        )?;
        for (_, parent) in &self.parents {
            self.work.debit(2, 2)?;
            parent.charge_held_copy(&|n| self.work.debit(2, n as u64))?;
        }
        for (_, root) in &self.exact_roots {
            self.work.debit(2, (1 + root.copy_items()) as u64)?;
        }
        for (_, guard) in &self.guards {
            self.work.debit(2, 2)?;
            crate::history_admission::charge_expression_copy(guard, &self.work)?;
        }
        Ok(())
    }
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
            predicate_only: false,
            metered: false,
            predicate_states: BTreeSet::new(),
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
    pub(super) fn specification_shared(
        e: &Expression,
        p: &Program,
        driven: &[String],
        owner: &str,
        context: Arc<crate::transition_source_plan::ProofContext>,
    ) -> Result<Option<Self>, Error> {
        let w = context.borrow_work();
        w.debit(2, 0)?;
        crate::history_admission::validate_relation_paid(e, p, owner, w)?;
        let (nodes, _, operators) = crate::continuous::integral_dependency_edges(e, p, owner)?;
        let mut internal = !operators.is_empty();
        for node in nodes {
            w.step()?;
            let mut source = node == 0;
            for name in driven {
                w.step()?;
                w.debit(2, name.len().min(p.nodes[node].len()) as u64)?;
                if name == &p.nodes[node] {
                    source = true;
                    break;
                }
            }
            internal |= !source;
        }
        if !internal {
            return Ok(None);
        }
        let expression = crate::causal_voltage::expand_paid(e, p, driven, w)?;
        let dependencies = crate::history_admission::qualify_history_expression(&expression, p, w)?;
        if dependencies.is_empty() {
            return Ok(None);
        }
        for leaf in crate::history_admission::target_forms(&expression, w)? {
            let row = crate::history_admission::affine_paid(&leaf, p, w)?;
            for value in row[..p.nodes.len()]
                .iter()
                .chain(&row[p.nodes.len() + p.states.len()..row.len() - 1])
            {
                w.step()?;
                if !value.zero() {
                    return Err(Error::new(
                        "unsupported_operator",
                        "transition target leaves must contain held state and constants only",
                    ));
                }
            }
        }
        fn states(
            e: &Expression,
            w: &crate::transition_source_plan::Work,
            out: &mut BTreeSet<usize>,
        ) -> Result<(), Error> {
            w.step()?;
            match e {
                Expression::State { state } => {
                    crate::event_value_proof::history::map_edit::<()>(out.len(), w)?;
                    out.insert(*state);
                }
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for e in [left, right, then_value, else_value] {
                        states(e, w, out)?
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    states(left, w, out)?;
                    states(right, w, out)?;
                }
                _ => (),
            }
            Ok(())
        }
        let mut predicate_states = BTreeSet::new();
        states(&expression, w, &mut predicate_states)?;
        w.debit(2, (20 + context.event_input_nodes().len()) as u64)?;
        Ok(Some(Self {
            predicate_only: false,
            metered: true,
            predicate_states,
            work: w.clone(),
            expression,
            program: context.program_arc(),
            trajectory: context.trajectory_arc(),
            input_nodes: context.event_input_nodes().to_vec(),
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
    fn store<T>(&self, values: &mut Vec<T>, value: T) -> Result<(), Error> {
        if self.metered && !self.predicate_only {
            crate::history_storage::push_vec(values, value, &self.work)?;
        } else {
            values.push(value)
        }
        Ok(())
    }
    pub(super) fn next_after(&self, after: f64) -> Option<f64> {
        self.cuts.iter().find(|c| c.hi > after).map(|c| c.hi)
    }
    pub(super) fn window_at(&self, time: f64) -> Option<I> {
        self.cuts.iter().find(|c| c.hi == time).copied()
    }
    pub(super) fn next_after_paid(&self, after: f64) -> Result<Option<f64>, Error> {
        if !self.metered {
            return Ok(self.next_after(after));
        }
        self.work.debit(2, 0)?;
        for cut in &self.cuts {
            self.work.step()?;
            if cut.hi > after {
                return Ok(Some(cut.hi));
            }
        }
        Ok(None)
    }
    pub(super) fn window_at_paid(&self, time: f64) -> Result<Option<I>, Error> {
        if !self.metered {
            return Ok(self.window_at(time));
        }
        self.work.debit(2, 0)?;
        for cut in &self.cuts {
            self.work.step()?;
            if cut.hi == time {
                return Ok(Some(*cut));
            }
        }
        Ok(None)
    }
    pub(super) fn root_at(&self, time: f64) -> Option<&crate::exact_source::RootTime> {
        let count = self.guards.iter().filter(|(b, _)| b.hi == time).count();
        let mut roots = self
            .exact_roots
            .iter()
            .filter(|(t, _)| *t == time)
            .map(|(_, r)| r);
        let first = roots.next()?;
        let mut found = 1;
        for root in roots {
            found += 1;
            if root.order(first) != std::cmp::Ordering::Equal {
                return None;
            }
        }
        (count == found).then_some(first)
    }
    pub(super) fn root_at_paid(
        &self,
        time: f64,
    ) -> Result<Option<&crate::exact_source::RootTime>, Error> {
        if !self.metered {
            return Ok(self.root_at(time));
        }
        self.work.debit(2, 0)?;
        let mut count = 0;
        for (b, _) in &self.guards {
            self.work.step()?;
            if b.hi == time {
                count += 1
            }
        }
        let mut first: Option<&crate::exact_source::RootTime> = None;
        let mut found = 0;
        for (t, root) in &self.exact_roots {
            self.work.step()?;
            if *t != time {
                continue;
            }
            found += 1;
            if let Some(first) = first {
                if root.order_with_work(first, &self.work)? != std::cmp::Ordering::Equal {
                    return Ok(None);
                }
            } else {
                first = Some(root)
            }
        }
        Ok(if count == found { first } else { None })
    }
    pub(super) fn coincides(
        &self,
        time: f64,
        guard: &Expression,
        driven: &[String],
    ) -> Result<bool, Error> {
        self.work.step()?;
        if self.metered {
            return Ok(false);
        }
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
    pub(super) fn same_epoch_paid(&self, other: &Self) -> Result<bool, Error> {
        let w = &self.work;
        w.debit(2, 0)?;
        w.debit(2, 12)?;
        if self.predicate_only != other.predicate_only
            || self.metered != other.metered
            || !Arc::ptr_eq(&self.program, &other.program)
            || !Arc::ptr_eq(&self.trajectory, &other.trajectory)
            || self.time != other.time
            || self.window != other.window
            || self.valid_until != other.valid_until
        {
            return Ok(false);
        }
        macro_rules! sequence {
            ($a:expr,$b:expr) => {{
                w.step()?;
                if $a.len() != $b.len() {
                    return Ok(false);
                }
                for (a, b) in $a.iter().zip($b) {
                    w.step()?;
                    if a != b {
                        return Ok(false);
                    }
                }
            }};
        }
        sequence!(&self.predicate_states, &other.predicate_states);
        if !crate::history_admission::same_expression_full(&self.expression, &other.expression, w)?
            || !crate::history_admission::same_expression_full(&self.selected, &other.selected, w)?
        {
            return Ok(false);
        }
        sequence!(&self.cuts, &other.cuts);
        sequence!(&self.parameters, &other.parameters);
        w.step()?;
        if self.parents.len() != other.parents.len() {
            return Ok(false);
        }
        for ((a, ah), (b, bh)) in self.parents.iter().zip(&other.parents) {
            w.step()?;
            if a != b || !ah.same_history_paid(bh, w)? {
                return Ok(false);
            }
        }
        w.step()?;
        if self.exact_roots.len() != other.exact_roots.len() {
            return Ok(false);
        }
        for ((a, ar), (b, br)) in self.exact_roots.iter().zip(&other.exact_roots) {
            w.step()?;
            if a != b
                || !crate::event_value_proof::history::same_rat(ar.rational(), br.rational(), w)?
            {
                return Ok(false);
            }
        }
        w.step()?;
        if self.guards.len() != other.guards.len() {
            return Ok(false);
        }
        for ((a, ae), (b, be)) in self.guards.iter().zip(&other.guards) {
            w.step()?;
            if a != b || !crate::history_admission::same_expression_full(ae, be, w)? {
                return Ok(false);
            }
        }
        Ok(true)
    }
    #[cfg(test)]
    pub(super) fn same_frame(&self, other: &Self) -> bool {
        self.input_nodes == other.input_nodes
            && self.dependencies == other.dependencies
            && self.same_epoch(other)
    }
    pub(super) fn same_epoch(&self, other: &Self) -> bool {
        self.predicate_only == other.predicate_only
            && self.metered == other.metered
            && self.predicate_states == other.predicate_states
            && self.expression == other.expression
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
        let (inputs, slopes) = if self.metered {
            self.trajectory.history_range(t, &self.work)?
        } else {
            self.trajectory.range(t)?
        };
        if self.metered {
            self.work
                .debit(2, (self.program.nodes.len() * 4 + entries.len() * 4) as u64)?;
        }
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        let mut derivatives = nodes.clone();
        for ((&node, value), slope) in self.input_nodes.iter().zip(inputs).zip(slopes) {
            nodes[node] = value;
            derivatives[node] = slope;
        }
        let mut operators = vec![I::ZERO; entries.len()];
        let mut ds = operators.clone();
        let row = if self.metered {
            crate::history_admission::affine_paid(e, &self.program, &self.work)?
        } else {
            crate::affine_bounds::affine(e, &self.program)?
        };
        for &index in &self.dependencies {
            if row[self.program.nodes.len() + self.program.states.len() + index].zero() {
                continue;
            }
            let Runtime::Transition { history, .. } = &entries[index] else {
                return Err(failure("invalid parent history"));
            };
            if self.metered {
                history.charge_held_copy(&|n| self.work.debit(2, n as u64))?;
            }
            let mut history = (**history).clone();
            if self.metered {
                history.history_advance_time(t.lo, &self.work)?;
            } else {
                history.advance_time(t.lo)?;
            }
            (operators[index], ds[index]) = if self.metered {
                history.history_continuous_range(t, &self.work)?
            } else {
                history.continuous_range(t)?
            };
        }
        let result = if self.metered {
            let mut value = *row.last().unwrap();
            let mut derivative = I::ZERO;
            let state_end = nodes.len() + states.len();
            for (i, &coefficient) in row[..row.len() - 1].iter().enumerate() {
                self.work.step()?;
                let (v, d) = if i < nodes.len() {
                    (nodes[i], derivatives[i])
                } else if i < state_end {
                    (states[i - nodes.len()], I::ZERO)
                } else {
                    (operators[i - state_end], ds[i - state_end])
                };
                value = value + coefficient * v;
                derivative = derivative + coefficient * d;
            }
            (value, derivative)
        } else {
            crate::guard_trajectory::evaluate(e, &nodes, &operators, states, &derivatives, &ds)?
        };
        if !result.0.finite() || !result.1.finite() {
            return Err(failure("nonfinite history predicate enclosure"));
        }
        if self.metered && matches!(result.0.sign(), Some(-1 | 1)) {
            return Ok(result);
        }
        let exact = if let Some(line) = self.exact_form(e, t, states, entries)? {
            if self.metered {
                crate::exact_source::history_paid::affine_range(line, t, &self.work)?
            } else {
                crate::exact_source::affine_range(line, t)
            }
        } else {
            None
        };
        if let Some(exact) = exact {
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
        if self.metered {
            self.work.step()?;
            match e {
                Expression::Select { .. } => self.work.debit(2, 4)?,
                Expression::Add { .. } | Expression::Multiply { .. } => self.work.debit(2, 2)?,
                _ => crate::history_admission::charge_expression_copy(e, &self.work)?,
            }
        }
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
    ) -> Result<Option<(num_rational::BigRational, num_rational::BigRational)>, Error> {
        if self.metered {
            return self.exact_form_paid(expression, bounds, states, entries);
        }
        use crate::exact_source::{binary, Budget};
        macro_rules! some {
            ($value:expr) => {
                match $value {
                    Some(value) => value,
                    None => return Ok(None),
                }
            };
        }
        let row = if self.metered {
            crate::history_admission::affine_paid(expression, &self.program, &self.work)?
        } else {
            match crate::affine_bounds::affine(expression, &self.program) {
                Ok(row) => row,
                Err(_) => return Ok(None),
            }
        };
        // Unmarked callers retain the existing exact accumulator and local cap.
        let mut budget = Budget(0);
        let mut result = (some!(binary(0.)), some!(binary(0.)));
        let nodes = self.program.nodes.len();
        let ops = nodes + states.len();
        for (i, c) in row.iter().enumerate() {
            if self.metered {
                self.work.step()?;
            }
            if c.zero() {
                continue;
            }
            if c.lo != c.hi {
                return Ok(None);
            }
            let line = if i == row.len() - 1 {
                (some!(binary(1.)), some!(binary(0.)))
            } else if i == 0 {
                (some!(binary(0.)), some!(binary(0.)))
            } else if i < nodes {
                let input = some!(self.input_nodes.iter().position(|&n| n == i));
                let curve = some!(some!(self.trajectory.exact_sources.get(input)).as_ref());
                some!(curve.affine_on(bounds))
            } else if i < ops {
                let value = states[i - nodes];
                if value.lo != value.hi {
                    return Ok(None);
                }
                (some!(binary(value.lo)), some!(binary(0.)))
            } else {
                let Some(Runtime::Transition { history, .. }) = entries.get(i - ops) else {
                    return Ok(None);
                };
                if self.metered {
                    history.charge_held_copy(&|n| self.work.debit(2, n as u64))?;
                }
                let mut history = (**history).clone();
                if self.metered {
                    history.history_advance_time(bounds.lo, &self.work)?;
                } else if history.advance_time(bounds.lo).is_err() {
                    return Ok(None);
                }
                some!(history.exact_affine_on(bounds))
            };
            let a = some!(budget.check(some!(binary(c.lo)) * line.0));
            result.0 = some!(budget.check(result.0 + a));
            let b = some!(budget.check(some!(binary(c.lo)) * line.1));
            result.1 = some!(budget.check(result.1 + b));
        }
        Ok(Some(result))
    }
    fn exact_form_paid(
        &self,
        expression: &Expression,
        bounds: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Result<Option<(num_rational::BigRational, num_rational::BigRational)>, Error> {
        use crate::exact_source::history_paid::Paid;
        let row = crate::history_admission::affine_paid(expression, &self.program, &self.work)?;
        let mut p = Paid::new(&self.work);
        let result = (|| {
            let mut result = (p.binary(0.)?, p.binary(0.)?);
            let nodes = self.program.nodes.len();
            let ops = nodes + states.len();
            for (i, c) in row.iter().enumerate() {
                p.pay(1)?;
                if c.zero() {
                    continue;
                }
                if c.lo != c.hi {
                    return None;
                }
                let line = if i == row.len() - 1 {
                    (p.binary(1.)?, p.binary(0.)?)
                } else if i == 0 {
                    (p.binary(0.)?, p.binary(0.)?)
                } else if i < nodes {
                    let mut input = None;
                    for (k, n) in self.input_nodes.iter().enumerate() {
                        p.pay(1)?;
                        if *n == i {
                            input = Some(k);
                            break;
                        }
                    }
                    let curve = self.trajectory.exact_sources.get(input?)?.as_ref()?;
                    p.accept(curve.affine_history(bounds, &self.work))??
                } else if i < ops {
                    let v = states[i - nodes];
                    if v.lo != v.hi {
                        return None;
                    }
                    (p.binary(v.lo)?, p.binary(0.)?)
                } else {
                    let Runtime::Transition { history, .. } = entries.get(i - ops)? else {
                        return None;
                    };
                    p.accept(history.charge_held_copy(&|n| self.work.debit(2, n as u64)))?;
                    let mut history = (**history).clone();
                    p.accept(history.history_advance_time(bounds.lo, &self.work))?;
                    p.accept(history.history_exact_affine_on(bounds, &self.work))??
                };
                let c = p.binary(c.lo)?;
                let a = p.op(&c, &line.0, '*')?;
                result.0 = p.op(&result.0, &a, '+')?;
                let b = p.op(&c, &line.1, '*')?;
                result.1 = p.op(&result.1, &b, '+')?;
            }
            Some(result)
        })();
        p.finish(result)
    }
    fn exact_root(
        &self,
        expression: &Expression,
        bounds: I,
        states: &[I],
        entries: &[Runtime],
    ) -> Result<Option<crate::exact_source::RootTime>, Error> {
        if bounds.lo == bounds.hi {
            if self.metered {
                let mut p = crate::exact_source::history_paid::Paid::new(&self.work);
                let value = p
                    .binary(bounds.lo)
                    .map(crate::exact_source::history_paid::root);
                return p.finish(value);
            }
            return Ok(crate::exact_source::RootTime::point(bounds.lo));
        }
        let Some((a, b)) = self.exact_form(expression, bounds, states, entries)? else {
            return Ok(None);
        };
        if self.metered {
            crate::exact_source::history_paid::affine_root(a, b, bounds, &self.work)
        } else {
            Ok(crate::exact_source::RootTime::affine(a, b, bounds))
        }
    }
    pub(super) fn prepared(
        &self,
        time: f64,
        window: I,
        states: &[I],
        entries: &[Runtime],
        until: f64,
    ) -> Result<Self, Error> {
        if self.metered {
            self.charge_copy()?;
        } else {
            self.work.debit(2, 8192)?;
        }
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
                let boundary = if self.metered {
                    history.history_boundary(time, true, &self.work)?
                } else {
                    history.forcing_boundary(time)
                };
                if let Some(t) = boundary {
                    end = end.min(t);
                }
                if self.metered && source.is_some() {
                    return Err(failure(
                        "shared history target requires held Transition parents",
                    ));
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
        fn collect_paid(
            e: &Expression,
            out: &mut Vec<Expression>,
            work: &crate::transition_source_plan::Work,
            target: bool,
            program: &Program,
        ) -> Result<(), Error> {
            work.step()?;
            match e {
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for child in [left, right, then_value, else_value] {
                        collect_paid(child, out, work, target, program)?;
                    }
                    for a in if target {
                        crate::history_admission::target_forms(left, work)?
                    } else {
                        crate::history_admission::forms(left, work)?
                    } {
                        for b in if target {
                            crate::history_admission::target_forms(right, work)?
                        } else {
                            crate::history_admission::forms(right, work)?
                        } {
                            if target {
                                if out.len() >= 128 {
                                    return Err(failure(
                                        "history target predicate budget exhausted",
                                    ));
                                }
                                work.debit(2, 5)?;
                                let expression = Expression::Add {
                                    left: Box::new(crate::history_admission::copy_expression(
                                        &a, work,
                                    )?),
                                    right: Box::new(Expression::Multiply {
                                        left: Box::new(constant(-1.)),
                                        right: Box::new(b),
                                    }),
                                };
                                crate::history_storage::push_vec(out, expression, work)?;
                            } else {
                                retain_history_predicate(out, &a, b, program, work)?;
                            }
                        }
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    collect_paid(left, out, work, target, program)?;
                    collect_paid(right, out, work, target, program)?;
                }
                _ => (),
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
        let epoch = if self.metered {
            std::borrow::Cow::Borrowed(&self.expression)
        } else {
            std::borrow::Cow::Owned(simplify(&self.expression, &self.program, states))
        };
        let parameters = if self.metered {
            self.work
                .debit(2, (self.predicate_states.len() * 2) as u64)?;
            let mut parameters = Vec::with_capacity(self.predicate_states.len());
            for &state in &self.predicate_states {
                self.work.step()?;
                parameters.push(states[state]);
            }
            Some(parameters)
        } else {
            None
        };
        let parameters_same = if let Some(parameters) = &parameters {
            let mut same = self.parameters.len() == parameters.len();
            if same {
                for (a, b) in self.parameters.iter().zip(parameters) {
                    self.work.step()?;
                    if a != b {
                        same = false;
                        break;
                    }
                }
            }
            same
        } else {
            self.parameters == states
        };
        let mut parents_same = true;
        for (i, old) in &self.parents {
            if self.metered {
                self.work.step()?;
            }
            if !matches!(&entries[*i],Runtime::Transition{history,..} if !history.input_changed_from(old))
            {
                parents_same = false;
                break;
            }
        }
        let reusable = time < self.valid_until && parameters_same && parents_same;
        if reusable {
            end = end.min(self.valid_until);
            if self.metered {
                next.cuts.clear();
                next.exact_roots.clear();
                next.guards.clear();
                for cut in &self.cuts {
                    self.work.step()?;
                    if cut.hi > time && cut.hi <= end {
                        self.work.debit(2, 2)?;
                        self.store(&mut next.cuts, *cut)?
                    }
                }
                for (t, root) in &self.exact_roots {
                    self.work.step()?;
                    if *t > time && *t <= end {
                        let root = root.clone_with_work(&self.work)?;
                        self.work.debit(2, 1)?;
                        self.store(&mut next.exact_roots, (*t, root))?;
                    }
                }
                for (b, guard) in &self.guards {
                    self.work.step()?;
                    if b.hi > time && b.hi <= end {
                        let guard = crate::history_admission::copy_expression(guard, &self.work)?;
                        self.work.debit(2, 2)?;
                        self.store(&mut next.guards, (*b, guard))?;
                    }
                }
            } else {
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
            }
        } else {
            self.work.debit(0, 1)?;
            if self.metered {
                collect_paid(
                    &epoch,
                    &mut predicates,
                    &self.work,
                    !self.predicate_only,
                    &self.program,
                )?;
            } else {
                collect(&epoch, &mut predicates, &self.work)?;
            }
            let partition = if self.metered {
                self.work.debit(2, 1)?;
                let mut partition = vec![time];
                for &knot in &self.trajectory.knots {
                    self.work.step()?;
                    if knot > time && knot < end {
                        self.work.debit(2, 1)?;
                        self.store(&mut partition, knot)?
                    }
                }
                self.work.debit(2, 1)?;
                self.store(&mut partition, end)?;
                partition
            } else {
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
                partition
            };
            for predicate in predicates {
                let mut source_only = true;
                if self.metered {
                    let row = crate::history_admission::affine_paid(
                        &predicate,
                        &self.program,
                        &self.work,
                    )?;
                    for v in
                        &row[self.program.nodes.len() + self.program.states.len()..row.len() - 1]
                    {
                        self.work.step()?;
                        if !v.zero() {
                            source_only = false;
                            break;
                        }
                    }
                }
                let source_curve = if source_only {
                    let mut proofs = crate::exact_source::TimeProofs::new();
                    for (i, v) in states.iter().enumerate() {
                        if self.metered {
                            self.work.step()?;
                        }
                        if v.lo == v.hi {
                            let root = if self.metered {
                                let mut p =
                                    crate::exact_source::history_paid::Paid::new(&self.work);
                                let value =
                                    p.binary(v.lo).map(crate::exact_source::history_paid::root);
                                p.finish(value)?
                            } else {
                                crate::exact_source::RootTime::point(v.lo)
                            };
                            if let Some(root) = root {
                                if self.metered {
                                    self.work.debit(2, 2)?;
                                }
                                if self.metered && !self.predicate_only {
                                    crate::event_value_proof::history::insert(
                                        &mut proofs,
                                        i,
                                        root,
                                        &self.work,
                                    )?;
                                } else {
                                    proofs.insert(i, root);
                                }
                            }
                        }
                    }
                    if self.metered {
                        self.trajectory.original_guard_curve_history(
                            &predicate,
                            &self.input_nodes,
                            end,
                            &proofs,
                            &self.work,
                        )?
                    } else {
                        self.trajectory.original_guard_curve_with_states(
                            &predicate,
                            &self.input_nodes,
                            end,
                            &proofs,
                        )
                    }
                } else {
                    None
                };
                if let Some(curve) = source_curve {
                    let roots = if self.metered {
                        curve.roots_history(&self.work)?
                    } else {
                        self.work.debit(2, 200_000)?;
                        curve.isolated_zero_times()
                    }
                    .ok_or_else(|| failure("unproved complete history target source cuts"))?;
                    for root in roots {
                        let sign = if self.metered {
                            curve.sign_history(&root, &self.work)?
                        } else {
                            curve.sign_at_root(&root)
                        };
                        if sign != Some(0) {
                            continue;
                        }
                        let bounds = if self.metered {
                            root.bounds_with_work(&self.work)?
                        } else {
                            root.bounds()
                        }
                        .ok_or_else(|| failure("invalid exact history target root"))?;
                        if bounds.hi > time && bounds.hi <= end {
                            self.work.debit(1, 1)?;
                            let guard = if self.metered {
                                crate::history_admission::copy_expression(&predicate, &self.work)?
                            } else {
                                predicate.clone()
                            };
                            if self.metered {
                                self.work.debit(2, 5)?;
                            }
                            self.store(&mut next.cuts, bounds)?;
                            self.store(&mut next.guards, (bounds, guard))?;
                            self.store(&mut next.exact_roots, (bounds.hi, root))?;
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
                            let exact =
                                self.exact_root(&predicate, root.bounds, states, entries)?;
                            let refined = if let Some(r) = exact.as_ref() {
                                if self.metered {
                                    r.refine_with_work(root.bounds, &self.work)?
                                } else {
                                    r.refine(root.bounds)
                                }
                            } else {
                                None
                            };
                            let bounds = refined.unwrap_or(root.bounds);
                            if let Some(exact) = exact {
                                if self.metered {
                                    self.work.debit(2, 1)?;
                                }
                                self.store(&mut next.exact_roots, (bounds.hi, exact))?;
                            }
                            self.work.debit(1, 1)?;
                            let guard = if self.metered {
                                crate::history_admission::copy_expression(&predicate, &self.work)?
                            } else {
                                predicate.clone()
                            };
                            if self.metered {
                                self.work.debit(2, 4)?;
                            }
                            self.store(&mut next.cuts, bounds)?;
                            self.store(&mut next.guards, (bounds, guard))?;
                        }
                    }
                }
            }
            if self.metered {
                for i in 1..next.guards.len() {
                    let mut j = i;
                    while j > 0 {
                        self.work.step()?;
                        if next.guards[j - 1].0.hi <= next.guards[j].0.hi {
                            break;
                        }
                        self.work.debit(2, 6)?;
                        if !self.predicate_only {
                            self.work.debit(
                                2,
                                (std::mem::size_of::<(I, Expression)>()
                                    .div_ceil(std::mem::size_of::<usize>())
                                    * 3) as u64,
                            )?;
                        }
                        next.guards.swap(j - 1, j);
                        j -= 1;
                    }
                }
            } else {
                next.guards.sort_by(|a, b| a.0.hi.total_cmp(&b.0.hi));
            }
            for pair in next.guards.windows(2) {
                self.work.step()?;
                if pair[0].0.hi >= pair[1].0.lo {
                    let a = next.root_at_paid(pair[0].0.hi)?;
                    let b = next.root_at_paid(pair[1].0.hi)?;
                    let same_root = if let (Some(a), Some(b)) = (a, b) {
                        if self.metered {
                            a.order_with_work(b, &self.work)? == std::cmp::Ordering::Equal
                        } else {
                            a.order(b) == std::cmp::Ordering::Equal
                        }
                    } else {
                        false
                    };
                    let same_guard = if self.metered {
                        same_root
                            || crate::history_admission::same_expression(
                                &pair[0].1, &pair[1].1, &self.work,
                            )?
                    } else {
                        crate::event_accuracy::GuardBounds::stateful_parameters(
                            &self.program,
                            &self
                                .input_nodes
                                .iter()
                                .map(|&n| self.program.nodes[n].clone())
                                .collect::<Vec<_>>(),
                            &[Some(&pair[0].1), Some(&pair[1].1)],
                        )?
                        .same_zero_set(0, 1)
                    };
                    if !same_root && !same_guard {
                        return Err(failure(
                            "overlapping history target roots lack an equality proof",
                        ));
                    }
                }
            }
            if self.metered {
                for i in 1..next.cuts.len() {
                    let mut j = i;
                    while j > 0 {
                        self.work.step()?;
                        if next.cuts[j - 1].hi <= next.cuts[j].hi {
                            break;
                        }
                        self.work.debit(2, 6)?;
                        if !self.predicate_only {
                            self.work.debit(2, 6)?;
                        }
                        next.cuts.swap(j - 1, j);
                        j -= 1;
                    }
                }
                let mut count = 0;
                for i in 0..next.cuts.len() {
                    self.work.step()?;
                    if count == 0 || next.cuts[count - 1] != next.cuts[i] {
                        next.cuts[count] = next.cuts[i];
                        count += 1
                    }
                }
                next.cuts.truncate(count);
            } else {
                next.cuts.sort_by(|a, b| a.hi.total_cmp(&b.hi));
                next.cuts.dedup();
            }
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
        next.parameters = if let Some(parameters) = parameters {
            parameters
        } else {
            states.to_vec()
        };
        if self.metered {
            for &i in &self.dependencies {
                self.work.step()?;
                let Runtime::Transition { history, .. } = &entries[i] else {
                    return Err(failure("invalid parent history"));
                };
                self.work.debit(2, 2)?;
                history.charge_held_copy(&|n| self.work.debit(2, n as u64))?;
            }
        }
        if self.metered && !self.predicate_only {
            next.parents.clear();
            for &i in &self.dependencies {
                self.work.step()?;
                let Runtime::Transition { history, .. } = &entries[i] else {
                    return Err(failure("invalid parent history"));
                };
                self.store(&mut next.parents, (i, (**history).clone()))?;
            }
        } else {
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
        }
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
                analytic_sources: vec![],
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

#[cfg(test)]
mod predicate_bit_tests {
    use super::*;
    use crate::history_consumer_fixture as fixture;
    #[test]
    fn shape_admission_predicate_signed_zero_candidates_remain_distinct_and_ordered() {
        let f = fixture::fixture();
        let p: Program = serde_json::from_value(f["program"].clone()).unwrap();
        let w = crate::transition_source_plan::Work::default();
        let plus = constant(0.);
        let minus = constant(-0.);
        let b = constant(1.);
        let mut values = Vec::new();
        retain_history_predicate(&mut values, &plus, b.clone(), &p, &w).unwrap();
        retain_history_predicate(&mut values, &minus, b.clone(), &p, &w).unwrap();
        assert_eq!(
            values.len(),
            2,
            "signed-zero original ASTs are not exact duplicates"
        );
        for (e, bits) in values.iter().zip([0.0f64.to_bits(), (-0.0f64).to_bits()]) {
            let Expression::Add { left, .. } = e else {
                panic!()
            };
            let Expression::Affine { constant, .. } = left.as_ref() else {
                panic!()
            };
            assert_eq!(constant.to_bits(), bits);
        }
        retain_history_predicate(&mut values, &plus, b.clone(), &p, &w).unwrap();
        assert_eq!(
            values.len(),
            2,
            "exact duplicates preserve their first representative"
        );
        let mut coefficient_guards = Vec::new();
        for x in [0.0, -0.0] {
            let a = Expression::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 1,
                    coefficient: x,
                }],
            };
            retain_history_predicate(&mut coefficient_guards, &a, b.clone(), &p, &w).unwrap();
        }
        assert_eq!(
            coefficient_guards.len(),
            2,
            "zero coefficient reads retain their complete original bits"
        );
    }
    #[test]
    fn shape_admission_predicate_bits_keep_origin_nodes_and_full_128_cap() {
        let f = fixture::fixture();
        let p: Program = serde_json::from_value(f["program"].clone()).unwrap();
        let w = crate::transition_source_plan::Work::default();
        let original: Expression =
            serde_json::from_value(f["program"]["operators"][0]["input"].clone()).unwrap();
        assert!(same_predicate_operand(&original, &original, &w).unwrap());
        for key in ["instance", "source", "line", "column"] {
            let mut other = f["program"]["operators"][0]["input"].clone();
            other["origin"][key] = match key {
                "instance" | "source" => serde_json::json!("different"),
                _ => serde_json::json!(2),
            };
            let other: Expression = serde_json::from_value(other).unwrap();
            assert!(
                !same_predicate_operand(&original, &other, &w).unwrap(),
                "origin {key}"
            );
        }
        let a = Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 0.,
            }],
        };
        let b = Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 2,
                coefficient: 0.,
            }],
        };
        assert!(
            !same_predicate_operand(&a, &b, &w).unwrap(),
            "zero coefficient node reads remain distinct"
        );
        let mut values = Vec::new();
        for mask in 0..129 {
            let a = Expression::Affine {
                constant: 0.,
                terms: (0..8)
                    .map(|bit| crate::ir::Term {
                        node: 1,
                        coefficient: if mask & (1 << bit) == 0 { 0. } else { -0. },
                    })
                    .collect(),
            };
            let result = retain_history_predicate(&mut values, &a, constant(1.), &p, &w);
            if mask < 128 {
                result.unwrap();
                assert_eq!(values.len(), mask + 1);
            } else {
                assert_eq!(
                    result.unwrap_err().message,
                    "history target predicate budget exhausted"
                );
                assert_eq!(values.len(), 128);
            }
        }
    }
}
