//! Demand-driven, candidate-local zero-time voltage and initial-state certificates.
//! Voltage equations are solved jointly; unresolved state/voltage cycles are refused.
use super::{check_state, predicate, unsupported};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, OperatorSpec, Program, StateInitial};
use std::collections::{BTreeMap, BTreeSet, HashSet};

pub(super) fn resolve(
    program: &Program,
    nodes: Vec<I>,
    known: HashSet<usize>,
) -> Result<Vec<f64>, Error> {
    let initial_nodes = nodes.clone();
    let initial_known = known.clone();
    let mut resolver = Resolver {
        program,
        nodes,
        known,
        required: BTreeSet::new(),
        allow_seeds: true,
        seed_mode: false,
        states: vec![None; program.states.len()],
        state_stack: HashSet::new(),
        node_stack: HashSet::new(),
        work: 0,
    };
    for (index, state) in program.states.iter().enumerate() {
        if let StateInitial::Constant(value) = state.initial {
            check_state(value, &state.kind)?;
            resolver.states[index] = Some(value);
        }
    }
    let values: Vec<_> = (0..program.states.len())
        .map(|index| resolver.state(index))
        .collect::<Result<_, _>>()?;
    // Partial certificates only order dependencies. Before publishing state
    // values, solve the demanded closure again with every original contribution
    // and recheck every original initial predicate against the complete system.
    resolver.nodes = initial_nodes;
    resolver.known = initial_known;
    resolver.node_stack.clear();
    resolver.allow_seeds = false;
    resolver.solve_nodes(resolver.required.clone())?;
    for (state, &expected) in program.states.iter().zip(&values) {
        if let StateInitial::Predicate(expression) = &state.initial {
            let actual = predicate(
                expression,
                &state.instance,
                &state.kind,
                &resolver.nodes,
                &resolver.known,
            )?;
            if actual != expected {
                return Err(unsupported(
                    "initial predicate changed after complete voltage certification",
                ));
            }
        }
    }
    Ok(values)
}

#[derive(Clone)]
struct Resolver<'a> {
    program: &'a Program,
    nodes: Vec<I>,
    known: HashSet<usize>,
    required: BTreeSet<usize>,
    allow_seeds: bool,
    seed_mode: bool,
    states: Vec<Option<f64>>,
    state_stack: HashSet<usize>,
    node_stack: HashSet<usize>,
    work: usize,
}

fn constant(value: f64) -> Expression {
    Expression::Affine {
        constant: value,
        terms: vec![],
    }
}

impl Resolver<'_> {
    fn charge(&mut self) -> Result<(), Error> {
        self.work += 1;
        if self.work > 100_000 {
            return Err(unsupported("initial voltage dependency work exhausted"));
        }
        Ok(())
    }

    fn state(&mut self, index: usize) -> Result<f64, Error> {
        self.charge()?;
        let state = self
            .program
            .states
            .get(index)
            .ok_or_else(|| Error::new("invalid_ir", "unknown initial state"))?;
        if let Some(value) = self.states[index] {
            return Ok(value);
        }
        if !self.state_stack.insert(index) {
            return Err(unsupported("cyclic initial state/voltage dependency"));
        }
        if self.state_stack.len() > 128 {
            return Err(unsupported("initial state dependency depth exceeds 128"));
        }
        let StateInitial::Predicate(expression) = &state.initial else {
            unreachable!()
        };
        let mut dependencies = BTreeSet::new();
        self.node_dependencies(expression, &mut dependencies)?;
        self.solve_nodes(dependencies).map_err(|mut error| {
            error
                .message
                .push_str(&format!(" for {}:{}", state.instance, state.name));
            error
        })?;
        let value = predicate(
            expression,
            &state.instance,
            &state.kind,
            &self.nodes,
            &self.known,
        )
        .map_err(|mut error| {
            error
                .message
                .push_str(&format!(" for {}:{}", state.instance, state.name));
            error
        })?;
        check_state(value, &state.kind)?;
        self.states[index] = Some(value);
        self.state_stack.remove(&index);
        Ok(value)
    }

    // Inspect original terms and all select arms, including zero/cancelled terms.
    fn node_dependencies(
        &mut self,
        e: &Expression,
        out: &mut BTreeSet<usize>,
    ) -> Result<(), Error> {
        self.charge()?;
        match e {
            Expression::Affine { terms, .. } => {
                for term in terms {
                    if term.node >= self.nodes.len() {
                        return Err(Error::new("invalid_ir", "unknown initial voltage node"));
                    }
                    out.insert(term.node);
                }
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.node_dependencies(left, out)?;
                self.node_dependencies(right, out)?;
            }
            Expression::Power { base, .. } => self.node_dependencies(base, out)?,
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for child in [left, right, then_value, else_value] {
                    self.node_dependencies(child, out)?;
                }
            }
            // Callers separately validate state/history ownership and semantics.
            // This walk only retains the complete original voltage dependency set.
            Expression::State { .. }
            | Expression::Operator { .. }
            | Expression::IntegerPrimitive { .. } => {}
            // IR33 samples an affine probe through a real boundary. The
            // dependency is the inner voltage, same as expression::predicate_nodes.
            Expression::RealBoundary { value, .. } | Expression::Forcing { value, .. } => {
                self.node_dependencies(value, out)?;
            }
            Expression::RealBinary { left, right, .. } => {
                self.node_dependencies(left, out)?;
                self.node_dependencies(right, out)?;
            }
            _ => return Err(unsupported("unsupported initial voltage dependency")),
        }
        Ok(())
    }

    fn bind(&mut self, e: &Expression, owner: &str, target: bool) -> Result<Expression, Error> {
        self.charge()?;
        Ok(match e {
            Expression::RealBoundary { value, .. } | Expression::Forcing { value, .. } => {
                self.bind(value, owner, target)?
            }
            Expression::RealBinary {
                operation,
                left,
                right,
                origin,
            } => Expression::RealBinary {
                operation: *operation,
                left: Box::new(self.bind(left, owner, target)?),
                right: Box::new(self.bind(right, owner, target)?),
                origin: origin.clone(),
            },
            Expression::State { state } => {
                if self
                    .program
                    .states
                    .get(*state)
                    .is_none_or(|s| s.instance != owner)
                {
                    return Err(Error::new("invalid_ir", "initial state owner mismatch"));
                }
                constant(self.state(*state)?)
            }
            Expression::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                // Source-typed integer tree over same-owner integer states, e.g.
                // `(code >> k) & 1` in a held transition target. Evaluate with the
                // same checked signed32 ops as at run time; the tree reads no voltage.
                // Main's resolver stores point seeds only (no separate exact[] track).
                crate::integer_primitive::validate(*function, args, origin, self.program, owner)?;
                let mut used = Vec::new();
                crate::integer_primitive::states(args, &mut used);
                let mut values = BTreeMap::new();
                for state in used {
                    if values.contains_key(&state) {
                        continue;
                    }
                    let value = self.state(state)?;
                    values.insert(
                        state,
                        crate::integer_primitive::point(I::point(value), origin)?,
                    );
                }
                let mut visits = 0_usize;
                let value = crate::integer_primitive::evaluate(
                    *function,
                    args,
                    origin,
                    &mut |state| Ok(values[&state]),
                    &mut || {
                        visits += 1;
                        Ok(())
                    },
                )?;
                for _ in 0..visits {
                    self.charge()?;
                }
                constant(f64::from(value))
            }
            Expression::Operator { operator } if !target => {
                let spec = self
                    .program
                    .operators
                    .get(*operator)
                    .ok_or_else(|| Error::new("invalid_ir", "unknown initial operator"))?;
                if spec.origin().instance != owner {
                    return Err(Error::new("invalid_ir", "initial operator owner mismatch"));
                }
                let OperatorSpec::Transition {
                    input,
                    delay,
                    rise,
                    fall,
                    ..
                } = spec
                else {
                    return Err(unsupported(
                        "initial voltage depends on an uncertified history",
                    ));
                };
                // Bind known held operands before resolving an input-selected target.
                // Preserve all original dependencies even when an arm is inactive.
                let bound = self.bind(input, owner, true)?;
                let selected = crate::expression::resolve_selects(&bound, &self.nodes)?;
                let row = crate::affine_bounds::affine(&selected, self.program)?;
                let values: Vec<_> = self.nodes.iter().map(|node| node.lo).collect();
                let value = crate::expression::evaluate(&selected, &values)?.value;
                let bounds = *row.last().unwrap();
                let history =
                    crate::transition::Transition::enclosed(value, bounds, *delay, *rise, *fall)?;
                // Initial held operands are exact. Refuse rather than discard
                // an arithmetic enclosure that cannot be represented as a point seed.
                if bounds.lo != bounds.hi {
                    return Err(unsupported(
                        "initial transition target is not point-certified",
                    ));
                }
                constant(history.value_bounds(0.)?.lo)
            }
            Expression::Affine { constant: c, terms } => {
                crate::expression::validate(e, self.nodes.len())?;
                if target && terms.iter().any(|term| term.node != 0) {
                    return Err(unsupported("initial transition target reads a voltage"));
                }
                Expression::Affine {
                    constant: *c,
                    terms: terms.clone(),
                }
            }
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(self.bind(left, owner, target)?),
                right: Box::new(self.bind(right, owner, target)?),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(self.bind(left, owner, target)?),
                right: Box::new(self.bind(right, owner, target)?),
            },
            Expression::Divide { left, right } => Expression::Divide {
                left: Box::new(self.bind(left, owner, target)?),
                right: Box::new(self.bind(right, owner, target)?),
            },
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                origin,
            } => {
                if origin.instance != owner || !origin.valid_expansion() {
                    return Err(Error::new("invalid_ir", "invalid initial selection owner"));
                }
                let bound = Expression::Select {
                    relation: *relation,
                    left: Box::new(self.bind(left, owner, target)?),
                    right: Box::new(self.bind(right, owner, target)?),
                    then_value: Box::new(self.bind(then_value, owner, target)?),
                    else_value: Box::new(self.bind(else_value, owner, target)?),
                    origin: origin.clone(),
                };
                // Conditional circuit branches need already certified predicates.
                // Unknown voltages cannot be treated as their zero-filled storage.
                if let Expression::Select { left, right, .. } = &bound {
                    let mut guards = BTreeSet::new();
                    self.node_dependencies(left, &mut guards)?;
                    self.node_dependencies(right, &mut guards)?;
                    self.solve_nodes(guards)?;
                }
                crate::expression::resolve_selects(&bound, &self.nodes)?
            }
            _ => return Err(unsupported("unsupported initial voltage expression")),
        })
    }

    fn solve_nodes(&mut self, requested: BTreeSet<usize>) -> Result<(), Error> {
        self.required.extend(&requested);
        // Independent requested voltages are not one unresolved component.
        // A driver's initial state may read another requested, independent
        // voltage. Resolve that dependency before diagnosing an actual cycle.
        for node in requested {
            self.solve_component(node)?;
        }
        Ok(())
    }

    // A seed uses only complete branch groups whose state/history operands
    // already have certificates. Never use one summand of an unresolved branch.
    fn ready_expression(&self, e: &Expression) -> bool {
        self.ready(e, false)
    }

    fn ready(&self, e: &Expression, target: bool) -> bool {
        match e {
            Expression::Affine { terms, .. } => !target || terms.iter().all(|t| t.node == 0),
            Expression::RealBoundary { value, .. } | Expression::Forcing { value, .. } => {
                self.ready(value, target)
            }
            Expression::RealBinary { left, right, .. } => {
                self.ready(left, target) && self.ready(right, target)
            }
            Expression::State { state } => self.states.get(*state).is_some_and(Option::is_some),
            Expression::IntegerPrimitive { args, .. } => {
                let mut used = Vec::new();
                crate::integer_primitive::states(args, &mut used);
                used.iter()
                    .all(|state| self.states.get(*state).is_some_and(Option::is_some))
            }
            Expression::Operator { operator } if !target => {
                match self.program.operators.get(*operator) {
                    Some(OperatorSpec::Transition { input, .. }) => self.ready(input, true),
                    _ => false,
                }
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.ready(left, target) && self.ready(right, target)
            }
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                // A conditional seed must not invent unknown guard voltages.
                fn known(e: &Expression, nodes: &HashSet<usize>) -> bool {
                    match e {
                        Expression::Affine { terms, .. } => {
                            terms.iter().all(|t| nodes.contains(&t.node))
                        }
                        Expression::RealBoundary { value, .. }
                        | Expression::Forcing { value, .. } => known(value, nodes),
                        Expression::RealBinary { left, right, .. } => {
                            known(left, nodes) && known(right, nodes)
                        }
                        Expression::State { .. } => true,
                        Expression::Add { left, right }
                        | Expression::Multiply { left, right }
                        | Expression::Divide { left, right } => {
                            known(left, nodes) && known(right, nodes)
                        }
                        _ => false,
                    }
                }
                known(left, &self.known)
                    && known(right, &self.known)
                    && [left, right, then_value, else_value]
                        .iter()
                        .all(|c| self.ready(c, target))
            }
            _ => false,
        }
    }

    fn solve_component(&mut self, node: usize) -> Result<(), Error> {
        if self.known.contains(&node) {
            return Ok(());
        }
        if self.allow_seeds && !self.seed_mode {
            let mut seed = self.clone();
            seed.seed_mode = true;
            seed.allow_seeds = false;
            seed.node_stack.clear();
            let result = seed.solve_component(node);
            self.work = seed.work;
            if self.work > 100_000 {
                return Err(unsupported("initial voltage dependency work exhausted"));
            }
            if result.is_ok() {
                self.nodes = seed.nodes;
                self.known = seed.known;
                return Ok(());
            }
        }
        if 1 + self.node_stack.len() > 256 {
            return Err(unsupported(
                "initial voltage joint system exceeds 256 unknowns",
            ));
        }
        if self.node_stack.contains(&node) {
            return Err(unsupported("cyclic initial state/voltage dependency"));
        }
        let mut pending = vec![node];
        let mut unknown = BTreeSet::from([node]);
        self.node_stack.insert(node);
        let mut equations = BTreeMap::new();
        while let Some(node) = pending.pop() {
            self.charge()?;
            let contributions: Vec<_> = self
                .program
                .contributions
                .iter()
                .filter(|c| c.positive == node || c.negative == node)
                .filter(|c| {
                    !self.seed_mode
                        || self
                            .program
                            .contributions
                            .iter()
                            .filter(|other| other.branch == c.branch)
                            .all(|other| self.ready_expression(&other.rhs))
                })
                .collect();
            if contributions.is_empty() {
                return Err(unsupported(
                    "initial comparison depends on an undriven voltage",
                ));
            }
            for c in contributions {
                if c.positive >= self.nodes.len() || c.negative >= self.nodes.len() {
                    return Err(Error::new(
                        "invalid_ir",
                        "initial branch endpoint out of range",
                    ));
                }
                let mut dependencies = BTreeSet::from([c.positive, c.negative]);
                // Audit before affine arithmetic can cancel any coefficient.
                self.node_dependencies(&c.rhs, &mut dependencies)?;
                let rhs = self.bind(&c.rhs, &c.origin.instance, false)?;
                for dependency in dependencies {
                    if !self.known.contains(&dependency) && !unknown.contains(&dependency) {
                        if !self.node_stack.insert(dependency) {
                            return Err(unsupported("cyclic initial state/voltage dependency"));
                        }
                        unknown.insert(dependency);
                        pending.push(dependency);
                        if unknown.len() > 256 {
                            return Err(unsupported(
                                "initial voltage joint system exceeds 256 unknowns",
                            ));
                        }
                    }
                }
                let rhs = crate::affine_bounds::affine(&rhs, self.program)?;
                let entry = equations.entry(c.branch.clone()).or_insert_with(|| {
                    let mut row = vec![I::ZERO; self.nodes.len() + 1];
                    row[c.positive] = row[c.positive] + I::ONE;
                    row[c.negative] = row[c.negative] - I::ONE;
                    (c.positive, c.negative, row, BTreeSet::new())
                });
                if entry.0 != c.positive || entry.1 != c.negative {
                    return Err(Error::new(
                        "invalid_ir",
                        "inconsistent initial branch orientation",
                    ));
                }
                // A branch can be reached from both endpoints. Count each original
                // contribution once, while retaining same-branch accumulation.
                let index = self
                    .program
                    .contributions
                    .iter()
                    .position(|x| std::ptr::eq(x, c))
                    .unwrap();
                if entry.3.insert(index) {
                    for (value, coefficient) in entry.2[..self.nodes.len()].iter_mut().zip(&rhs) {
                        *value = *value - *coefficient;
                    }
                    *entry.2.last_mut().unwrap() = *entry.2.last().unwrap() - *rhs.last().unwrap();
                }
            }
        }
        let unknown: Vec<_> = unknown.into_iter().collect();
        let count = unknown.len();
        if count > 256 {
            return Err(unsupported(
                "initial voltage joint system exceeds 256 unknowns",
            ));
        }
        let rows = equations
            .into_values()
            .map(|(_, _, row, _)| {
                let forcing = (0..self.nodes.len())
                    .filter(|node| self.known.contains(node))
                    .fold(*row.last().unwrap(), |sum, node| {
                        sum + row[node] * self.nodes[node]
                    });
                unknown
                    .iter()
                    .map(|&node| row[node])
                    .chain([-forcing])
                    .collect()
            })
            .collect();
        let rows = crate::affine_bounds::eliminate(rows, count, 1).map_err(|error| {
            unsupported(format!(
                "initial voltage system is not uniquely certified: {}",
                error.message
            ))
        })?;
        let mut values = vec![I::ZERO; count];
        for r in (0..count).rev() {
            values[r] = rows[r][count]
                - ((r + 1)..count).fold(I::ZERO, |sum, column| {
                    sum + rows[r][column] * values[column]
                });
            if !values[r].finite() {
                return Err(unsupported("nonfinite initial voltage certificate"));
            }
        }
        for (&node, value) in unknown.iter().zip(values) {
            self.nodes[node] = value;
            self.known.insert(node);
            self.node_stack.remove(&node);
        }
        Ok(())
    }
}
