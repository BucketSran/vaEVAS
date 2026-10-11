//! Shared linear continuous-time trajectories for voltage-domain operators.
//!
//! This module is intentionally side-effect free.  A constructed trajectory is
//! a closed-form function of the accepted source PWLs and the compiled affine
//! network; querying an output sample never advances or commits history.

use crate::affine_bounds;
use crate::interval::Interval as I;
use crate::ir::{BranchIdentity, Error, Expression, OperatorSpec, Origin, Program};
use crate::pwl::Trajectory;
use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

const MAX_LAPLACE_ORDER: usize = 8;

#[path = "continuous_derivatives.rs"]
mod derivatives;
#[path = "nonlinear_dynamics.rs"]
mod nonlinear;

pub(crate) use nonlinear::run_implicit;

// Polynomial direct terms need the original algebraic voltage constraints,
// even when the contribution itself contains only an operator reference.
pub(crate) fn needs_polynomial_feedthrough(program: &Program) -> bool {
    program.operators.iter().any(|op| {
        let OperatorSpec::LaplaceNd {
            input,
            numerator,
            denominator,
            origin,
        } = op
        else {
            return false;
        };
        laplace_system(numerator, denominator, origin).is_ok_and(|filter| !filter.d.zero())
            && affine_for_operator_input(input, program, origin).is_err()
    })
}

pub(crate) fn validate_integral_input(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<(), Error> {
    nonlinear::validate(expr, program, owner)
}

type DependencySets = (BTreeSet<usize>, BTreeSet<usize>, BTreeSet<usize>);

pub(crate) fn integral_dependency_edges(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<DependencySets, Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            let (mut n, mut s, mut o) = integral_dependency_edges(left, program, owner)?;
            let (nn, ss, oo) = integral_dependency_edges(right, program, owner)?;
            n.extend(nn);
            s.extend(ss);
            o.extend(oo);
            Ok((n, s, o))
        }
        Expression::Power { base, .. } => integral_dependency_edges(base, program, owner),
        _ => {
            let a = crate::events::affine(expr, program, owner)?;
            Ok((
                a.node_dependencies,
                a.state_dependencies,
                a.operator_dependencies,
            ))
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum ContinuousKind {
    Idt,
    LaplaceNd,
    Ddt,
}

#[derive(Clone, Debug)]
pub(crate) struct OperatorSlot {
    pub(crate) operator: usize,
    continuous: bool,
    pub(crate) value: usize,
}

#[path = "exact_affine_history.rs"]
mod exact_affine;
#[path = "continuous_history.rs"]
mod history;
#[path = "continuous_runtime.rs"]
mod runtime;
pub(crate) use runtime::Continuous;

#[derive(Clone)]
pub(crate) struct LinearContinuous {
    slots: Vec<OperatorSlot>,
    segments: Vec<Segment>,
    value_count: usize,
    dc_values: Vec<I>,
    stop: f64,
    context: Arc<Context>,
    parameters: Vec<I>,
    start: f64,
    initial: Vec<I>,
    event_dependent: bool,
    // Physical state after the last event map, before propagation to its
    // representative. Used only for ordered event observations, not queries.
    event_seed: Option<(I, Vec<I>)>,
    exact_affine: Option<exact_affine::History>,
    exact_states: Vec<bool>,
    exact_seed: Option<Vec<Option<num_rational::BigRational>>>,
}

struct Context {
    program: Program,
    trajectory: Trajectory,
    driven: Vec<String>,
}

fn local_context(context: &Arc<Context>, horizon: f64) -> Arc<Context> {
    let mut trajectory = context.trajectory.clone();
    trajectory.config.stop = horizon;
    trajectory.config.output_times = vec![0., horizon];
    trajectory.config.pwl = vec![vec![[0., 0.], [horizon, 0.]]; context.driven.len()];
    trajectory.knots = vec![0., horizon];
    trajectory.solver_points = vec![0., horizon];
    Arc::new(Context {
        program: context.program.clone(),
        trajectory,
        driven: context.driven.clone(),
    })
}

#[derive(Clone)]
struct Segment {
    start: f64,
    end: f64,
    initial: Vec<I>,
    matrix: Vec<Vec<I>>,
    values: Vec<Vec<I>>,
    derivatives: Vec<Vec<I>>,
}

#[derive(Clone)]
struct NetworkOperator {
    operator: usize,
    kind: ContinuousKind,
    origin: Origin,
    states: Vec<usize>,
    input: Option<Vec<I>>,
    laplace: Option<LaplaceSystem>,
    held_reset: bool,
}

#[derive(Clone)]
struct LaplaceSystem {
    a: Vec<Vec<I>>,
    b: Vec<I>,
    c: Vec<I>,
    d: I,
}

#[derive(Clone)]
struct AlgebraicSystem {
    rows: Vec<Vec<I>>,
    dc_rows: Vec<Vec<I>>,
    x_count: usize,
    width: usize,
    node_columns: Vec<Option<usize>>,
    operator_columns: Vec<Option<usize>>,
    source_columns: Vec<Option<usize>>,
    state_count: usize,
    parameters: Vec<I>,
}

impl LinearContinuous {
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
    ) -> Result<Option<Self>, Error> {
        Self::build(
            Arc::new(Context {
                program: program.clone(),
                trajectory: trajectory.clone(),
                driven: driven.to_vec(),
            }),
            states.iter().copied().map(I::point).collect(),
            0.0,
            None,
        )
    }

    fn build(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
    ) -> Result<Option<Self>, Error> {
        let (program, trajectory, driven) =
            (&context.program, &context.trajectory, &context.driven);
        let driven_nodes = driven_node_indices(program, driven)?;
        let network_ids = select_network_operators(program, &driven_nodes)?;
        if network_ids.is_empty() {
            return Ok(None);
        }
        let source_count = driven_nodes.len();
        let mut source_columns = vec![None; program.nodes.len()];
        for (column, &node) in driven_nodes.iter().enumerate() {
            source_columns[node] = Some(column);
        }
        let mut operators = Vec::new();
        let mut slots = Vec::new();
        let mut state_count = 0;
        for operator in network_ids {
            let spec = &program.operators[operator];
            let origin = spec.origin().clone();
            let (kind, states, input, laplace) = match spec {
                OperatorSpec::Idt { input, .. } => {
                    let row = affine_for_operator_input(input, program, &origin)?;
                    let state = state_count;
                    state_count += 1;
                    (ContinuousKind::Idt, vec![state], Some(row), None)
                }
                OperatorSpec::LaplaceNd {
                    input,
                    numerator,
                    denominator,
                    ..
                } => {
                    let row = affine_for_operator_input(input, program, &origin)?;
                    let system = laplace_system(numerator, denominator, &origin)?;
                    let states: Vec<_> = (state_count..state_count + system.a.len()).collect();
                    state_count += system.a.len();
                    (ContinuousKind::LaplaceNd, states, Some(row), Some(system))
                }
                OperatorSpec::Ddt { input, .. } => {
                    let row = affine_for_operator_input(input, program, &origin)?;
                    (ContinuousKind::Ddt, Vec::new(), Some(row), None)
                }
                _ => unreachable!("network operator selection returned a non-continuous operator"),
            };
            let value = operators.len();
            let held_reset = if let OperatorSpec::Idt {
                reset: Some(reset), ..
            } = spec
            {
                let dependencies = structural_affine(reset, program, &origin)?;
                if !dependencies.node_dependencies.is_empty()
                    || !dependencies.operator_dependencies.is_empty()
                {
                    return Err(unsupported(
                        &origin,
                        "joint idt reset must depend only on instance event state and constants",
                    ));
                }
                crate::operators::ResetExpression::new(reset.clone()).active(&parameters)?
            } else {
                false
            };
            operators.push(NetworkOperator {
                operator,
                kind,
                origin,
                states,
                input,
                laplace,
                held_reset,
            });
            slots.push(OperatorSlot {
                operator,
                continuous: kind != ContinuousKind::Ddt,
                value,
            });
        }
        let algebraic = AlgebraicSystem::new(
            program,
            &operators,
            &driven_nodes,
            &source_columns,
            state_count,
            source_count,
            &parameters,
        )?;
        let solved =
            affine_bounds::eliminate(algebraic.rows.clone(), algebraic.x_count, algebraic.width)?;
        let x_to_forcing = back_substitute_eliminated(&solved, algebraic.x_count, algebraic.width)?;
        let state_derivatives =
            build_state_derivatives(program, &operators, &algebraic, &x_to_forcing)?;
        let value_rows = build_value_rows(&operators, &algebraic, &x_to_forcing)?;
        // States and source values are continuous, but a source's PWL slope
        // can jump. Follow the solved output relation rather than just the
        // outer operator kind when certifying a guard's continuity.
        let slope_start = state_count + source_count;
        for (slot, row) in slots.iter_mut().zip(&value_rows) {
            slot.continuous &= row[slope_start..slope_start + source_count]
                .iter()
                .all(|value| value.zero());
        }
        let derivative_rows =
            build_derivative_rows(&value_rows, &state_derivatives, state_count, source_count);
        // DC fixes every derivative output to zero. Its algebraic solve is
        // distinct from the transient mass relation, including downstream DC
        // filter initialization when an explicit integral IC is nonstationary.
        let dc_solved = affine_bounds::eliminate(
            algebraic.dc_rows.clone(),
            algebraic.x_count,
            algebraic.width,
        )?;
        let dc_mapping =
            back_substitute_eliminated(&dc_solved, algebraic.x_count, algebraic.width)?;
        let dc_derivatives = build_state_derivatives(program, &operators, &algebraic, &dc_mapping)?;
        let dc_value_rows = build_value_rows(&operators, &algebraic, &dc_mapping)?;
        let mut initial = if let Some(restart) = restart {
            restart
        } else {
            initial_state(program, &operators, &algebraic, &dc_derivatives, trajectory)?
        };
        for op in &operators {
            if op.held_reset {
                let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] else {
                    unreachable!()
                };
                initial[op.states[0]] = I::point(*ic);
            }
        }
        // The DC phase uses the same solved network and initial states as the
        // transient phase, with source slopes set to zero for every output.
        // Do not patch only ddt after downstream outputs have been evaluated.
        let mut dc_forcing = initial.clone();
        dc_forcing.extend(trajectory.value_bounds(0.0));
        dc_forcing.extend(vec![I::ZERO; source_count]);
        dc_forcing.push(I::ONE);
        let dc_values = dc_value_rows
            .iter()
            .map(|row| dot(row, &dc_forcing, "continuous DC value"))
            .collect::<Result<Vec<_>, _>>()?;
        let segments = build_segments(
            trajectory,
            state_count,
            source_count,
            &source_columns,
            &state_derivatives,
            &value_rows,
            &derivative_rows,
            initial,
            start,
        )?;
        let initial = segments[0].initial[..state_count].to_vec();
        let event_dependent = operators.iter().any(|op| {
            let spec = &program.operators[op.operator];
            matches!(spec, OperatorSpec::Idt { reset: Some(_), .. })
                || continuous_operator_input(spec).is_some_and(|(input, origin)| {
                    history_event_dependency(
                        input,
                        program,
                        origin,
                        &driven_nodes,
                        &mut BTreeSet::new(),
                    )
                })
        });
        let mut exact_states = vec![false; state_count];
        for op in &operators {
            if matches!(
                program.operators[op.operator],
                OperatorSpec::Idt { reset: None, .. }
            ) {
                for &state in &op.states {
                    exact_states[state] = true;
                }
            }
        }
        let exact_affine =
            exact_affine::History::build(&exact_states, &segments, start, state_count, None);
        Ok(Some(Self {
            slots,
            segments,
            value_count: operators.len(),
            dc_values,
            stop: trajectory.config.stop,
            context,
            parameters,
            start,
            initial,
            event_dependent,
            event_seed: None,
            exact_affine,
            exact_states,
            exact_seed: None,
        }))
    }

    pub(crate) fn operator_value_index(&self, operator: usize) -> Option<usize> {
        self.slots
            .iter()
            .find(|slot| slot.operator == operator)
            .map(|slot| slot.value)
    }

    pub(crate) fn is_continuous(&self, slot: usize) -> bool {
        self.slots
            .iter()
            .find(|entry| entry.value == slot)
            .is_some_and(|entry| entry.continuous)
    }

    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        self.eval_rows(time, Query::Value)
    }

    pub(crate) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        if !time.finite() || time.lo > time.hi {
            return Err(Error::new(
                "event_resolution",
                "continuous trajectory range query requires a finite ordered time interval",
            ));
        }
        self.ensure_time(time.lo)?;
        self.ensure_time(time.hi)?;
        if time == I::ZERO {
            return Ok(self.dc_values.clone());
        }
        // An interval starting at zero includes the DC observation as well
        // as the right-side transient limit, which may differ by feedthrough.
        let mut out: Vec<Option<I>> = if time.lo == 0.0 {
            self.dc_values.iter().copied().map(Some).collect()
        } else {
            vec![None; self.value_count]
        };
        for segment in &self.segments {
            let lo = time.lo.max(segment.start);
            let hi = time.hi.min(segment.end);
            if lo > hi {
                continue;
            }
            let values = self.eval_segment_rows(segment, I { lo, hi }, Query::Value)?;
            for (slot, value) in out.iter_mut().zip(values) {
                *slot = Some(match *slot {
                    Some(current) => current.hull(value),
                    None => value,
                });
            }
        }
        out.into_iter()
            .map(|value| {
                value.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "continuous trajectory range query has no covered segment",
                    )
                })
            })
            .collect()
    }

    pub(crate) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        if !time.finite() || time.lo > time.hi {
            return Err(Error::new(
                "event_resolution",
                "continuous derivative query requires a finite ordered time interval",
            ));
        }
        self.ensure_time(time.lo)?;
        self.ensure_time(time.hi)?;
        let mut out: Vec<Option<I>> = vec![None; self.value_count];
        for segment in &self.segments {
            let lo = time.lo.max(segment.start);
            let hi = time.hi.min(segment.end);
            if lo > hi {
                continue;
            }
            let values = self.eval_segment_rows(segment, I { lo, hi }, Query::Derivative)?;
            for (slot, value) in out.iter_mut().zip(values) {
                *slot = Some(match *slot {
                    Some(current) => current.hull(value),
                    None => value,
                });
            }
        }
        out.into_iter()
            .map(|value| {
                value.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "continuous derivative query has no covered segment",
                    )
                })
            })
            .collect()
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.segments
            .iter()
            .map(|segment| segment.start)
            .chain([self.stop])
            .find(|&time| time > after)
    }

    fn ensure_time(&self, time: f64) -> Result<(), Error> {
        if time.is_finite() && time >= self.start && time <= self.stop {
            Ok(())
        } else {
            Err(Error::new(
                "invalid_inputs",
                "continuous trajectory query must be within the finite source history",
            ))
        }
    }

    fn segment_at(&self, time: f64) -> Result<&Segment, Error> {
        self.ensure_time(time)?;
        let index = self
            .segments
            .partition_point(|segment| segment.start <= time);
        let index = index.saturating_sub(1).min(self.segments.len() - 1);
        Ok(&self.segments[index])
    }

    fn eval_rows(&self, time: f64, query: Query) -> Result<Vec<I>, Error> {
        if matches!(query, Query::Value) && time == 0.0 {
            return Ok(self.dc_values.clone());
        }
        let segment = self.segment_at(time)?;
        self.eval_segment_rows(segment, I::point(time), query)
    }

    fn eval_segment_rows(&self, segment: &Segment, time: I, query: Query) -> Result<Vec<I>, Error> {
        let forcing = self.segment_state(segment, time)?;
        let rows = match query {
            Query::Value => &segment.values,
            Query::Derivative => &segment.derivatives,
        };
        rows.iter()
            .map(|row| dot(row, &forcing, "continuous value"))
            .collect()
    }

    fn segment_state(&self, segment: &Segment, time: I) -> Result<Vec<I>, Error> {
        let elapsed = time - I::point(segment.start);
        if !elapsed.finite() || elapsed.lo < 0.0 {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot bound continuous trajectory elapsed time",
            ));
        }
        crate::state_space::propagate(&segment.matrix, &segment.initial, elapsed)
    }
}

fn history_event_dependency(
    expr: &Expression,
    program: &Program,
    origin: &Origin,
    driven: &[usize],
    seen: &mut BTreeSet<usize>,
) -> bool {
    match expr {
        Expression::State { .. } => true,
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            history_event_dependency(left, program, origin, driven, seen)
                || history_event_dependency(right, program, origin, driven, seen)
        }
        Expression::Power { base, .. } => {
            history_event_dependency(base, program, origin, driven, seen)
        }
        _ => {
            let Ok(deps) = structural_affine(expr, program, origin) else {
                return true;
            };
            for node in deps.node_dependencies {
                if node == 0 || driven.contains(&node) || !seen.insert(node) {
                    continue;
                }
                for c in &program.contributions {
                    if (c.positive == node || c.negative == node)
                        && history_event_dependency(&c.rhs, program, &c.origin, driven, seen)
                    {
                        return true;
                    }
                }
            }
            for op in deps.operator_dependencies {
                if !seen.insert(program.nodes.len() + op) {
                    continue;
                }
                let spec = &program.operators[op];
                if matches!(spec, OperatorSpec::Idt { reset: Some(_), .. }) {
                    return true;
                }
                if let Some((input, origin)) = continuous_operator_input(spec) {
                    if history_event_dependency(input, program, origin, driven, seen) {
                        return true;
                    }
                }
            }
            false
        }
    }
}

#[derive(Clone, Copy)]
enum Query {
    Value,
    Derivative,
}

impl AlgebraicSystem {
    fn new(
        program: &Program,
        operators: &[NetworkOperator],
        driven_nodes: &[usize],
        source_columns: &[Option<usize>],
        state_count: usize,
        source_count: usize,
        parameters: &[I],
    ) -> Result<Self, Error> {
        let mut operator_columns = vec![None; program.operators.len()];
        let mut column = 0;
        let mut network_outputs = BTreeSet::new();
        for op in operators {
            operator_columns[op.operator] = Some(column);
            network_outputs.insert(op.operator);
            column += 1;
        }
        let driven: BTreeSet<_> = driven_nodes.iter().copied().collect();
        let mut active_nodes = BTreeSet::new();
        for op in operators {
            if let Some(input) = &op.input {
                add_rhs_internal_nodes(&mut active_nodes, input, program, &driven);
            }
        }
        loop {
            let before = active_nodes.len();
            for contribution in &program.contributions {
                let row = affine_bounds::affine(&contribution.rhs, program)?;
                let active_lhs = active_nodes.contains(&contribution.positive)
                    || active_nodes.contains(&contribution.negative);
                if row_refs_network(&row, program, &network_outputs)
                    || active_lhs
                    || row_refs_nodes(&row, &active_nodes)
                {
                    if contribution.positive != 0 && !driven.contains(&contribution.positive) {
                        active_nodes.insert(contribution.positive);
                    }
                    if contribution.negative != 0 && !driven.contains(&contribution.negative) {
                        active_nodes.insert(contribution.negative);
                    }
                    add_rhs_internal_nodes(&mut active_nodes, &row, program, &driven);
                }
            }
            if active_nodes.len() == before {
                break;
            }
        }
        let mut node_columns = vec![None; program.nodes.len()];
        for &node in &active_nodes {
            node_columns[node] = Some(column);
            column += 1;
        }
        let x_count = column;
        let width = state_count + source_count + source_count + 1;
        let mut grouped = BTreeMap::<BranchIdentity, Vec<I>>::new();
        for contribution in &program.contributions {
            let rhs = affine_bounds::affine(&contribution.rhs, program)?;
            let relevant = active_nodes.contains(&contribution.positive)
                || active_nodes.contains(&contribution.negative)
                || row_refs_network(&rhs, program, &network_outputs)
                || row_refs_nodes(&rhs, &active_nodes);
            if !relevant {
                continue;
            }
            validate_affine_structure(&contribution.rhs, program, &contribution.origin)?;
            if !grouped.contains_key(&contribution.branch) {
                let mut row = vec![I::ZERO; x_count + width];
                add_node(
                    &mut row,
                    contribution.positive,
                    I::ONE,
                    &node_columns,
                    source_columns,
                    state_count,
                )?;
                add_node(
                    &mut row,
                    contribution.negative,
                    -I::ONE,
                    &node_columns,
                    source_columns,
                    state_count,
                )?;
                grouped.insert(contribution.branch.clone(), row);
            }
            let row = grouped.get_mut(&contribution.branch).unwrap();
            add_expression(
                row,
                &rhs,
                -I::ONE,
                program,
                &node_columns,
                &operator_columns,
                source_columns,
                state_count,
                parameters,
            )?;
        }
        let mut rows = Vec::new();
        for row in grouped.into_values() {
            if row[..x_count].iter().any(|x| !x.zero()) {
                rows.push(row);
            } else if row[x_count..].iter().any(|x| !x.zero()) {
                return Err(Error::new(
                    "unsupported_operator",
                    "continuous network has a redundant constraint that is not an identity",
                ));
            }
        }
        for op in operators {
            let mut row = vec![I::ZERO; x_count + width];
            row[operator_columns[op.operator].unwrap()] = I::ONE;
            match op.kind {
                ContinuousKind::Idt => {
                    row[x_count + op.states[0]] = row[x_count + op.states[0]] - I::ONE;
                }
                ContinuousKind::LaplaceNd => {
                    let system = op.laplace.as_ref().unwrap();
                    for (&state, &coefficient) in op.states.iter().zip(&system.c) {
                        row[x_count + state] = row[x_count + state] - coefficient;
                    }
                    add_expression(
                        &mut row,
                        op.input.as_ref().unwrap(),
                        -system.d,
                        program,
                        &node_columns,
                        &operator_columns,
                        source_columns,
                        state_count,
                        parameters,
                    )?;
                }
                ContinuousKind::Ddt => {
                    // DC derivative zero. Transient equations are derived
                    // together after the voltage constraints have been mapped.
                }
            }
            rows.push(row);
        }
        residual_rows_to_rhs(&mut rows, x_count);
        let mut system = Self {
            dc_rows: rows.clone(),
            rows,
            x_count,
            width,
            node_columns,
            operator_columns,
            source_columns: source_columns.to_vec(),
            state_count,
            parameters: parameters.to_vec(),
        };
        system.rows = derivatives::transient_rows(program, operators, &system)?;
        Ok(system)
    }
}

fn residual_rows_to_rhs(rows: &mut [Vec<I>], x_count: usize) {
    for row in rows {
        for value in &mut row[x_count..] {
            *value = -*value;
        }
    }
}

fn select_network_operators(
    program: &Program,
    driven_nodes: &[usize],
) -> Result<Vec<usize>, Error> {
    let mut selected = BTreeSet::new();
    let driven: Vec<_> = driven_nodes
        .iter()
        .map(|&n| program.nodes[n].clone())
        .collect();
    for (index, spec) in program.operators.iter().enumerate() {
        if crate::operators::transition_filter::projection(program, &driven, index).is_some() {
            continue;
        }
        match spec {
            OperatorSpec::Idt {
                input,
                reset,
                origin,
                ..
            } if has_network_dependency(input, program, driven_nodes, origin)? => {
                selected.insert(index);
            }
            OperatorSpec::LaplaceNd {
                input,
                numerator,
                denominator,
                origin,
                ..
            } if numerator.len() != 1
                || denominator.len() != 2
                || has_network_dependency(input, program, driven_nodes, origin)? =>
            {
                selected.insert(index);
            }
            OperatorSpec::Ddt { .. } => {
                selected.insert(index);
            }
            _ => {}
        }
    }
    loop {
        let before = selected.len();
        let mut active_nodes = BTreeSet::new();
        for index in selected.clone() {
            let Some((input, origin)) = continuous_operator_input(&program.operators[index]) else {
                continue;
            };
            let deps = structural_affine(input, program, origin)?;
            add_structural_internal_nodes(&mut active_nodes, &deps.node_dependencies, driven_nodes);
            select_operator_dependencies(
                &mut selected,
                &deps.operator_dependencies,
                program,
                origin,
            )?;
        }
        close_selected_through_voltage_relations(
            program,
            driven_nodes,
            &mut selected,
            active_nodes,
        )?;
        if selected.len() == before {
            break;
        }
    }
    Ok(selected.into_iter().collect())
}

fn close_selected_through_voltage_relations(
    program: &Program,
    driven_nodes: &[usize],
    selected: &mut BTreeSet<usize>,
    mut active_nodes: BTreeSet<usize>,
) -> Result<(), Error> {
    loop {
        let before = active_nodes.len();
        let network_outputs = selected.clone();
        for contribution in &program.contributions {
            let deps = structural_affine(&contribution.rhs, program, &contribution.origin)?;
            let active_lhs = active_nodes.contains(&contribution.positive)
                || active_nodes.contains(&contribution.negative);
            if active_lhs
                || deps
                    .node_dependencies
                    .iter()
                    .any(|node| active_nodes.contains(node))
                || deps
                    .operator_dependencies
                    .iter()
                    .any(|operator| network_outputs.contains(operator))
            {
                validate_affine_structure(&contribution.rhs, program, &contribution.origin)?;
                if contribution.positive != 0 && !driven_nodes.contains(&contribution.positive) {
                    active_nodes.insert(contribution.positive);
                }
                if contribution.negative != 0 && !driven_nodes.contains(&contribution.negative) {
                    active_nodes.insert(contribution.negative);
                }
                add_structural_internal_nodes(
                    &mut active_nodes,
                    &deps.node_dependencies,
                    driven_nodes,
                );
                select_operator_dependencies(
                    selected,
                    &deps.operator_dependencies,
                    program,
                    &contribution.origin,
                )?;
            }
        }
        if active_nodes.len() == before {
            break;
        }
    }
    Ok(())
}

fn continuous_operator_input(spec: &OperatorSpec) -> Option<(&Expression, &Origin)> {
    match spec {
        OperatorSpec::Idt { input, origin, .. }
        | OperatorSpec::LaplaceNd { input, origin, .. }
        | OperatorSpec::Ddt { input, origin, .. } => Some((input, origin)),
        _ => None,
    }
}

fn select_operator_dependencies(
    selected: &mut BTreeSet<usize>,
    dependencies: &BTreeSet<usize>,
    program: &Program,
    origin: &Origin,
) -> Result<(), Error> {
    for &operator in dependencies {
        if selected.contains(&operator) {
            continue;
        }
        if selectable_continuous_dependency(&program.operators[operator]) {
            selected.insert(operator);
        } else {
            return Err(unsupported(
                origin,
                "continuous network cannot depend on an unsupported dynamic operator, even if the numeric coefficient cancels",
            ));
        }
    }
    Ok(())
}

fn selectable_continuous_dependency(spec: &OperatorSpec) -> bool {
    matches!(
        spec,
        OperatorSpec::Idt { .. } | OperatorSpec::LaplaceNd { .. } | OperatorSpec::Ddt { .. }
    )
}

fn has_network_dependency(
    expr: &Expression,
    program: &Program,
    driven_nodes: &[usize],
    origin: &Origin,
) -> Result<bool, Error> {
    let deps = structural_affine(expr, program, origin)?;
    Ok(deps
        .node_dependencies
        .iter()
        .any(|node| *node != 0 && !driven_nodes.contains(node))
        || !deps.state_dependencies.is_empty()
        || !deps.operator_dependencies.is_empty())
}

fn structural_affine(
    expr: &Expression,
    program: &Program,
    origin: &Origin,
) -> Result<crate::events::AffineState, Error> {
    crate::events::affine(expr, program, &origin.instance)
}

fn add_structural_internal_nodes(
    nodes: &mut BTreeSet<usize>,
    dependencies: &BTreeSet<usize>,
    driven_nodes: &[usize],
) {
    for &node in dependencies {
        if node != 0 && !driven_nodes.contains(&node) {
            nodes.insert(node);
        }
    }
}

fn affine_for_operator_input(
    input: &Expression,
    program: &Program,
    origin: &Origin,
) -> Result<Vec<I>, Error> {
    validate_affine_structure(input, program, origin)?;
    affine_bounds::affine(input, program).map_err(|mut error| {
        error.message.push_str(&format!(" at {}", origin.label()));
        error
    })
}

fn validate_affine_structure(
    expr: &Expression,
    program: &Program,
    origin: &Origin,
) -> Result<(), Error> {
    crate::events::affine(expr, program, &origin.instance).map(|_| ())
}

fn laplace_system(
    numerator: &[f64],
    denominator: &[f64],
    origin: &Origin,
) -> Result<LaplaceSystem, Error> {
    if denominator.len() < 2 || denominator.len() > MAX_LAPLACE_ORDER + 1 {
        return Err(unsupported(
            origin,
            "laplace_nd continuous network supports denominator order 1..8",
        ));
    }
    if numerator.is_empty() || numerator.len() > denominator.len() {
        return Err(unsupported(
            origin,
            "laplace_nd continuous network requires a proper nonempty numerator",
        ));
    }
    if numerator.iter().chain(denominator).any(|x| !x.is_finite()) {
        return Err(unsupported(
            origin,
            "laplace_nd coefficients must be finite",
        ));
    }
    let n = denominator.len() - 1;
    let dn = I::point(denominator[n]);
    let d0 = I::point(denominator[0]);
    if dn.zero() || d0.zero() {
        return Err(unsupported(
            origin,
            "laplace_nd denominator d0 and leading coefficient must be nonzero",
        ));
    }
    let mut b = vec![I::ZERO; n + 1];
    for (slot, coefficient) in b.iter_mut().zip(numerator) {
        *slot = I::point(*coefficient);
    }
    let d: Vec<_> = denominator.iter().map(|x| I::point(*x)).collect();
    let feedthrough = b[n] / dn;
    if !feedthrough.finite() {
        return Err(unsupported(
            origin,
            "laplace_nd feedthrough coefficient cannot be bounded",
        ));
    }
    let scales = laplace_state_scales(denominator, n, origin)?;
    let mut a = vec![vec![I::ZERO; n]; n];
    for (row, arow) in a.iter_mut().enumerate().take(n.saturating_sub(1)) {
        arow[row + 1] = scales[row + 1] / scales[row];
    }
    for (column, coefficient) in d.iter().take(n).enumerate() {
        a[n - 1][column] = -*coefficient / dn * scales[column] / scales[n - 1];
    }
    let mut input = vec![I::ZERO; n];
    input[n - 1] = (I::ONE / dn) / scales[n - 1];
    let c: Vec<_> = b
        .iter()
        .zip(&d)
        .zip(&scales)
        .take(n)
        .map(|((&bi, &di), &scale)| (bi - feedthrough * di) * scale)
        .collect();
    if a.iter()
        .flatten()
        .chain(&input)
        .chain(&c)
        .any(|x| !x.finite())
    {
        return Err(unsupported(
            origin,
            "laplace_nd state-space coefficients cannot be bounded",
        ));
    }
    Ok(LaplaceSystem {
        a,
        b: input,
        c,
        d: feedthrough,
    })
}

fn laplace_state_scales(
    denominator: &[f64],
    order: usize,
    origin: &Origin,
) -> Result<Vec<I>, Error> {
    if order == 0 {
        return Ok(Vec::new());
    }
    let ratio = (denominator[order].abs() / denominator[0].abs()).powf(1.0 / order as f64);
    if !ratio.is_finite() || ratio <= 0.0 {
        return Err(unsupported(
            origin,
            "laplace_nd denominator does not define a finite state scaling",
        ));
    }
    let exponent = ratio.log2().round().clamp(-512.0, 512.0) as i32;
    let step = 2.0_f64.powi(-exponent);
    let mut scales = Vec::with_capacity(order);
    let mut scale = 1.0_f64;
    for _ in 0..order {
        if !scale.is_finite() || scale == 0.0 {
            return Err(unsupported(
                origin,
                "laplace_nd state scaling cannot be represented finitely",
            ));
        }
        scales.push(I::point(scale));
        scale *= step;
    }
    Ok(scales)
}

fn build_state_derivatives(
    program: &Program,
    operators: &[NetworkOperator],
    algebraic: &AlgebraicSystem,
    x_to_forcing: &[Vec<I>],
) -> Result<Vec<Vec<I>>, Error> {
    let mut rows = vec![vec![I::ZERO; algebraic.width]; algebraic.state_count];
    for op in operators {
        match op.kind {
            ContinuousKind::Idt => {
                if !op.held_reset {
                    rows[op.states[0]] =
                        expand_input(op.input.as_ref().unwrap(), program, algebraic, x_to_forcing)?;
                }
            }
            ContinuousKind::LaplaceNd => {
                let input =
                    expand_input(op.input.as_ref().unwrap(), program, algebraic, x_to_forcing)?;
                let system = op.laplace.as_ref().unwrap();
                for (local, &state) in op.states.iter().enumerate() {
                    let row = &mut rows[state];
                    for (&other, &coefficient) in op.states.iter().zip(&system.a[local]) {
                        row[other] = row[other] + coefficient;
                    }
                    for (value, &coefficient) in row.iter_mut().zip(&input) {
                        *value = *value + system.b[local] * coefficient;
                    }
                }
            }
            ContinuousKind::Ddt => {}
        }
    }
    Ok(rows)
}

fn build_value_rows(
    operators: &[NetworkOperator],
    algebraic: &AlgebraicSystem,
    x_to_forcing: &[Vec<I>],
) -> Result<Vec<Vec<I>>, Error> {
    operators
        .iter()
        .map(|op| {
            let column = algebraic.operator_columns[op.operator].unwrap();
            x_to_forcing.get(column).cloned().ok_or_else(|| {
                Error::new(
                    "unsupported_operator",
                    "continuous operator output was not solved by the algebraic network",
                )
            })
        })
        .collect()
}

fn build_derivative_rows(
    values: &[Vec<I>],
    state_derivatives: &[Vec<I>],
    state_count: usize,
    source_count: usize,
) -> Vec<Vec<I>> {
    values
        .iter()
        .map(|row| {
            let mut result = vec![I::ZERO; row.len()];
            for (state, coefficient) in row.iter().copied().take(state_count).enumerate() {
                if coefficient.zero() {
                    continue;
                }
                for (slot, value) in result.iter_mut().zip(&state_derivatives[state]) {
                    *slot = *slot + coefficient * *value;
                }
            }
            for source in 0..source_count {
                result[state_count + source_count + source] =
                    result[state_count + source_count + source] + row[state_count + source];
            }
            result
        })
        .collect()
}

fn initial_state(
    program: &Program,
    operators: &[NetworkOperator],
    algebraic: &AlgebraicSystem,
    state_derivatives: &[Vec<I>],
    trajectory: &Trajectory,
) -> Result<Vec<I>, Error> {
    if algebraic.state_count == 0 {
        return Ok(Vec::new());
    }
    let source0 = trajectory.value_bounds(0.0);
    let mut rows = Vec::new();
    for op in operators {
        match &program.operators[op.operator] {
            OperatorSpec::Idt { ic, .. } => {
                if !ic.is_finite() {
                    return Err(unsupported(
                        &op.origin,
                        "idt initial condition must be finite",
                    ));
                }
                let mut row = vec![I::ZERO; algebraic.state_count + 1];
                row[op.states[0]] = I::ONE;
                row[algebraic.state_count] = I::point(*ic);
                rows.push(row);
            }
            OperatorSpec::LaplaceNd { .. } => {
                for &state in &op.states {
                    let derivative = &state_derivatives[state];
                    let mut row = vec![I::ZERO; algebraic.state_count + 1];
                    row[..algebraic.state_count]
                        .copy_from_slice(&derivative[..algebraic.state_count]);
                    let mut known = *derivative.last().unwrap();
                    for (source, value) in source0.iter().enumerate() {
                        known = known + derivative[algebraic.state_count + source] * *value;
                    }
                    row[algebraic.state_count] = -known;
                    rows.push(row);
                }
            }
            OperatorSpec::Ddt { .. } => {}
            _ => {}
        }
    }
    let eliminated = affine_bounds::eliminate(rows, algebraic.state_count, 1)?;
    let solved = back_substitute_eliminated(&eliminated, algebraic.state_count, 1)?;
    let initial: Vec<_> = solved.into_iter().map(|row| row[0]).collect();
    if initial.iter().all(|value| value.finite()) {
        Ok(initial)
    } else {
        Err(Error::new(
            "waveform_accuracy",
            "continuous DC initial state cannot be bounded",
        ))
    }
}

#[allow(clippy::too_many_arguments)]
fn build_segments(
    trajectory: &Trajectory,
    state_count: usize,
    source_count: usize,
    _source_columns: &[Option<usize>],
    state_derivatives: &[Vec<I>],
    value_rows: &[Vec<I>],
    derivative_rows: &[Vec<I>],
    initial_state: Vec<I>,
    start_time: f64,
) -> Result<Vec<Segment>, Error> {
    let mut state = initial_state;
    let mut segments = Vec::new();
    let mut knots = vec![start_time];
    knots.extend(
        trajectory
            .solver_points
            .iter()
            .copied()
            .filter(|t| *t > start_time),
    );
    if knots.len() == 1 {
        knots.push(start_time);
    }
    for window in knots.windows(2) {
        let (start, end) = (window[0], window[1]);
        let source_start = trajectory.value_bounds(start);
        let source_end = trajectory.value_bounds(end);
        let duration = I::point(end) - I::point(start);
        let slopes = if start == end {
            vec![I::ZERO; source_count]
        } else {
            source_start
                .iter()
                .zip(&source_end)
                .map(|(&a, &b)| (b - a) / duration)
                .collect::<Vec<_>>()
        };
        if slopes.iter().any(|x| !x.finite()) {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot bound continuous source slopes",
            ));
        }
        let width = state_count + source_count + source_count + 1;
        let mut matrix = vec![vec![I::ZERO; width]; width];
        for (row, derivative) in state_derivatives.iter().enumerate() {
            for (col, &value) in derivative.iter().enumerate() {
                matrix[row][col] = matrix[row][col] + value;
            }
        }
        for source in 0..source_count {
            matrix[state_count + source][state_count + source_count + source] = I::ONE;
        }
        let mut initial = vec![I::ZERO; matrix.len()];
        initial[..state_count].copy_from_slice(&state);
        for (source, value) in source_start.iter().enumerate() {
            initial[state_count + source] = *value;
        }
        for (source, slope) in slopes.iter().enumerate() {
            initial[state_count + source_count + source] = *slope;
        }
        initial[state_count + source_count + source_count] = I::ONE;
        let segment = Segment {
            start,
            end,
            initial: initial.clone(),
            matrix,
            values: value_rows.to_vec(),
            derivatives: derivative_rows.to_vec(),
        };
        let next = crate::state_space::propagate(&segment.matrix, &segment.initial, duration)?;
        state = next[..state_count].to_vec();
        segments.push(segment);
    }
    Ok(segments)
}

fn expand_input(
    row: &[I],
    program: &Program,
    algebraic: &AlgebraicSystem,
    x_to_forcing: &[Vec<I>],
) -> Result<Vec<I>, Error> {
    let mut out = vec![I::ZERO; algebraic.x_count + algebraic.width];
    add_expression(
        &mut out,
        row,
        I::ONE,
        program,
        &algebraic.node_columns,
        &algebraic.operator_columns,
        &algebraic.source_columns,
        algebraic.state_count,
        &algebraic.parameters,
    )?;
    substitute_x(&mut out, x_to_forcing, algebraic.x_count);
    Ok(out)
}

fn substitute_x(row: &mut Vec<I>, x_to_forcing: &[Vec<I>], x_count: usize) {
    if row.len() == x_count + x_to_forcing.first().map_or(0, Vec::len) {
        let mut expanded = row[x_count..].to_vec();
        for (coefficient, xrow) in row[..x_count].iter().zip(x_to_forcing) {
            if coefficient.zero() {
                continue;
            }
            for (target, &value) in expanded.iter_mut().zip(xrow) {
                *target = *target + *coefficient * value;
            }
        }
        *row = expanded;
    }
}

fn back_substitute_eliminated(
    rows: &[Vec<I>],
    x_count: usize,
    width: usize,
) -> Result<Vec<Vec<I>>, Error> {
    if rows.len() < x_count || rows.iter().any(|row| row.len() < x_count + width) {
        return Err(Error::new(
            "unsupported_operator",
            "continuous algebraic elimination returned an incomplete system",
        ));
    }
    let mut solved = vec![vec![I::ZERO; width]; x_count];
    for column in (0..x_count).rev() {
        let row = &rows[column];
        if row[column] != I::ONE {
            return Err(Error::new(
                "unsupported_operator",
                "continuous algebraic elimination did not normalize a pivot",
            ));
        }
        let mut rhs = row[x_count..x_count + width].to_vec();
        for upper in column + 1..x_count {
            let coefficient = row[upper];
            if coefficient.zero() {
                continue;
            }
            for (target, &value) in rhs.iter_mut().zip(&solved[upper]) {
                *target = *target - coefficient * value;
            }
        }
        if rhs.iter().all(|value| value.finite()) {
            solved[column] = rhs;
        } else {
            return Err(Error::new(
                "waveform_accuracy",
                "continuous algebraic back substitution produced nonfinite bounds",
            ));
        }
    }
    Ok(solved)
}

#[allow(clippy::too_many_arguments)]
fn add_expression(
    row: &mut [I],
    expr: &[I],
    scale: I,
    program: &Program,
    node_columns: &[Option<usize>],
    operator_columns: &[Option<usize>],
    source_columns: &[Option<usize>],
    state_count: usize,
    parameters: &[I],
) -> Result<(), Error> {
    let source_count = source_columns.iter().filter(|x| x.is_some()).count();
    let x_count = row.len() - (state_count + source_count + source_count + 1);
    for (node, &coefficient) in expr[..program.nodes.len()].iter().enumerate() {
        add_node(
            row,
            node,
            scale * coefficient,
            node_columns,
            source_columns,
            state_count,
        )?;
    }
    let state_base = program.nodes.len();
    let operator_base = state_base + program.states.len();
    for (state, &coefficient) in expr[state_base..operator_base].iter().enumerate() {
        let column = row.len() - 1;
        row[column] = row[column] + scale * coefficient * parameters[state];
    }
    for (operator, &coefficient) in expr[operator_base..operator_base + program.operators.len()]
        .iter()
        .enumerate()
    {
        if coefficient.zero() {
            continue;
        }
        let Some(column) = operator_columns[operator] else {
            return Err(Error::new(
                "unsupported_operator",
                "continuous network cannot depend on a non-network dynamic operator",
            ));
        };
        row[column] = row[column] + scale * coefficient;
    }
    let constant_column = x_count + state_count + source_count + source_count;
    row[constant_column] = row[constant_column] + scale * *expr.last().unwrap();
    Ok(())
}

fn add_node(
    row: &mut [I],
    node: usize,
    coefficient: I,
    node_columns: &[Option<usize>],
    source_columns: &[Option<usize>],
    state_count: usize,
) -> Result<(), Error> {
    if coefficient.zero() || node == 0 {
        return Ok(());
    }
    if let Some(column) = node_columns[node] {
        row[column] = row[column] + coefficient;
        return Ok(());
    }
    if let Some(source) = source_columns[node] {
        let source_count = source_columns.iter().filter(|x| x.is_some()).count();
        let x_count = row.len() - (state_count + source_count + source_count + 1);
        row[x_count + state_count + source] = row[x_count + state_count + source] + coefficient;
        return Ok(());
    }
    Err(Error::new(
        "unsupported_operator",
        "continuous network references an internal voltage that is not solved by the network",
    ))
}

fn row_refs_network(row: &[I], program: &Program, network_outputs: &BTreeSet<usize>) -> bool {
    let operator_base = program.nodes.len() + program.states.len();
    network_outputs
        .iter()
        .any(|&op| !row[operator_base + op].zero())
}

fn row_refs_nodes(row: &[I], nodes: &BTreeSet<usize>) -> bool {
    nodes.iter().any(|&node| !row[node].zero())
}

fn add_rhs_internal_nodes(
    nodes: &mut BTreeSet<usize>,
    row: &[I],
    program: &Program,
    driven: &BTreeSet<usize>,
) {
    for (node, coefficient) in row[..program.nodes.len()].iter().enumerate() {
        if node != 0 && !coefficient.zero() && !driven.contains(&node) {
            nodes.insert(node);
        }
    }
}

fn driven_node_indices(program: &Program, driven: &[String]) -> Result<Vec<usize>, Error> {
    let mut out = Vec::new();
    for name in driven {
        let index = program
            .nodes
            .iter()
            .position(|node| node == name)
            .ok_or_else(|| Error::new("invalid_inputs", "unknown directly driven node"))?;
        if index == 0 || out.contains(&index) {
            return Err(Error::new(
                "invalid_inputs",
                "driven nodes must be unique and cannot include ground",
            ));
        }
        out.push(index);
    }
    Ok(out)
}

fn dot(row: &[I], values: &[I], what: &str) -> Result<I, Error> {
    let value = row
        .iter()
        .zip(values)
        .fold(I::ZERO, |sum, (&a, &b)| sum + a * b);
    if value.finite() {
        Ok(value)
    } else {
        Err(Error::new(
            "waveform_accuracy",
            format!("cannot bound {what} with finite interval arithmetic"),
        ))
    }
}

fn point_value(value: I) -> Result<f64, Error> {
    if value.lo == value.hi && value.lo.is_finite() {
        Ok(value.lo)
    } else if value.finite() {
        Ok((value.lo + value.hi) * 0.5)
    } else {
        Err(Error::new(
            "numerical_failure",
            "continuous value query produced a nonfinite interval",
        ))
    }
}

fn unsupported(origin: &Origin, message: &'static str) -> Error {
    Error::new(
        "unsupported_operator",
        format!("{message} at {}", origin.label()),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{
        BranchIdentity, Contribution, ContributionKind, Origin, State, StateKind, Term,
        TransientInputs, SCHEMA_VERSION,
    };

    fn origin() -> Origin {
        Origin {
            source: "continuous_test.va".to_string(),
            line: 1,
            column: 1,
            instance: "uut".to_string(),
            expansion: Vec::new(),
        }
    }

    fn program_with_idt(input: Expression, ic: f64) -> Program {
        Program {
            schema_version: SCHEMA_VERSION,
            nodes: vec!["0".to_string(), "y".to_string()],
            contributions: vec![Contribution {
                branch: BranchIdentity {
                    instance: "uut".to_string(),
                    local_positive: "y".to_string(),
                    local_negative: "0".to_string(),
                    kind: ContributionKind::Voltage,
                },
                positive: 1,
                negative: 0,
                rhs: Expression::Operator { operator: 0 },
                origin: origin(),
            }],
            states: Vec::new(),
            events: Vec::new(),
            operators: vec![OperatorSpec::Idt {
                input,
                ic,
                reset: None,
                origin: origin(),
            }],
        }
    }

    fn no_source_trajectory(stop: f64) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                strobetimes: Vec::new(),
                pwl: Vec::new(),
                output_times: vec![0.0, stop],
                stop,
                max_step: stop,
            },
            0,
        )
        .unwrap()
    }

    #[test]
    fn forced_points_partition_propagation_without_becoming_source_knots() {
        let program = program_with_idt(
            Expression::Affine {
                constant: 1.0,
                terms: vec![Term {
                    node: 1,
                    coefficient: -1.0,
                }],
            },
            0.0,
        );
        let mut config = no_source_trajectory(1.0).config;
        config.strobetimes = vec![0.2, 0.7];
        let trajectory = Trajectory::new(config, 0).unwrap();
        assert_eq!(trajectory.knots, vec![0.0, 1.0]);
        let continuous = Continuous::new(&program, &trajectory, &[], &[])
            .unwrap()
            .unwrap();
        let Continuous::Linear(flow) = continuous else {
            panic!("expected affine propagation")
        };
        assert_eq!(
            flow.segments.iter().map(|s| s.end).collect::<Vec<_>>(),
            vec![0.2, 0.7, 1.0]
        );
        for &time in &[0.2, 0.7, 1.0] {
            let value = flow.bounds(time).unwrap()[0];
            assert!((0.5 * (value.lo + value.hi) - (1.0 - (-time).exp())).abs() < 1e-7);
        }
    }

    fn cancelled_node(node: usize) -> Expression {
        Expression::Add {
            left: Box::new(Expression::Affine {
                constant: 0.0,
                terms: vec![Term {
                    node,
                    coefficient: 1.0,
                }],
            }),
            right: Box::new(Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: -1.0,
                    terms: Vec::new(),
                }),
                right: Box::new(Expression::Affine {
                    constant: 0.0,
                    terms: vec![Term {
                        node,
                        coefficient: 1.0,
                    }],
                }),
            }),
        }
    }

    fn cancelled_state(state: usize) -> Expression {
        Expression::Add {
            left: Box::new(Expression::State { state }),
            right: Box::new(Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: -1.0,
                    terms: Vec::new(),
                }),
                right: Box::new(Expression::State { state }),
            }),
        }
    }
    fn ramp_filter_program(tau: f64) -> Program {
        Program {
            schema_version: SCHEMA_VERSION,
            nodes: vec!["0".to_string(), "u".to_string(), "y".to_string()],
            contributions: vec![Contribution {
                branch: BranchIdentity {
                    instance: "uut".to_string(),
                    local_positive: "y".to_string(),
                    local_negative: "0".to_string(),
                    kind: ContributionKind::Voltage,
                },
                positive: 2,
                negative: 0,
                rhs: Expression::Operator { operator: 0 },
                origin: origin(),
            }],
            states: Vec::new(),
            events: Vec::new(),
            operators: vec![OperatorSpec::LaplaceNd {
                input: Expression::Affine {
                    constant: 0.0,
                    terms: vec![Term {
                        node: 1,
                        coefficient: 1.0,
                    }],
                },
                numerator: vec![1.0],
                denominator: vec![1.0, 2.0 * tau, tau * tau],
                origin: origin(),
            }],
        }
    }

    fn ramp_filter_trajectory(tau: f64) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                strobetimes: Vec::new(),
                pwl: vec![vec![[0.0, 0.0], [2.0 * tau, 2.0]]],
                output_times: vec![0.0, 0.5 * tau, tau, 2.0 * tau],
                stop: 2.0 * tau,
                max_step: 0.5 * tau,
            },
            1,
        )
        .unwrap()
    }

    fn normalized_two_pole_ramp(x: f64) -> f64 {
        x - 2.0 + (x + 2.0) * (-x).exp()
    }
    fn ddt_filter_program(numerator: Vec<f64>, denominator: Vec<f64>) -> Program {
        let mut program = ramp_filter_program(1.0);
        let input = Expression::Affine {
            constant: 0.0,
            terms: vec![Term {
                node: 1,
                coefficient: 1.0,
            }],
        };
        program.operators = vec![
            OperatorSpec::Ddt {
                input,
                origin: origin(),
            },
            OperatorSpec::LaplaceNd {
                input: Expression::Operator { operator: 0 },
                numerator,
                denominator,
                origin: origin(),
            },
        ];
        program.contributions[0].rhs = Expression::Operator { operator: 1 };
        program
    }

    #[test]
    fn ddt_identity_filter_dc_and_range_bounds_share_one_phase() {
        let program = ddt_filter_program(vec![1.0, 1.0], vec![1.0, 1.0]);
        let trajectory = ramp_filter_trajectory(1.0);
        let continuous = Continuous::new(
            &program,
            &trajectory,
            &["u".to_string()],
            &vec![0.0; program.states.len()],
        )
        .unwrap()
        .unwrap();
        let d = continuous.operator_value_index(0).unwrap();
        let y = continuous.operator_value_index(1).unwrap();
        for slot in [d, y] {
            let initial = continuous.bounds(0.0).unwrap()[slot];
            assert!(initial.lo <= 0.0 && initial.hi >= 0.0, "{initial:?}");
            assert!(initial.hi - initial.lo <= 1e-12, "{initial:?}");
            assert_eq!(continuous.range_bounds(I::ZERO).unwrap()[slot], initial);
            let both = continuous.range_bounds(I { lo: 0.0, hi: 0.25 }).unwrap()[slot];
            assert!(both.lo <= 0.0 && both.hi >= 1.0, "{both:?}");
            let positive = continuous.range_bounds(I::point(0.25)).unwrap()[slot];
            assert!(positive.lo <= 1.0 && positive.hi >= 1.0, "{positive:?}");
            assert!(
                positive.lo > 0.0,
                "DC must not leak into a positive-time query: {positive:?}"
            );
        }
        let initial = continuous.bounds(0.0).unwrap();
        let positive = continuous.bounds(0.25).unwrap();
        continuous.values(1.0).unwrap();
        assert_eq!(continuous.bounds(0.0).unwrap(), initial);
        assert_eq!(continuous.bounds(0.25).unwrap(), positive);
    }

    #[test]
    fn continuous_guard_classification_follows_ddt_feedthrough() {
        for (numerator, expected) in [(vec![1.0, 1.0], false), (vec![1.0], true)] {
            let program = ddt_filter_program(numerator, vec![1.0, 1.0]);
            let continuous = Continuous::new(
                &program,
                &ramp_filter_trajectory(1.0),
                &["u".to_string()],
                &vec![0.0; program.states.len()],
            )
            .unwrap()
            .unwrap();
            assert!(!continuous.is_continuous(continuous.operator_value_index(0).unwrap()));
            assert_eq!(
                continuous.is_continuous(continuous.operator_value_index(1).unwrap()),
                expected
            );
        }
    }
    fn assert_close(actual: f64, expected: f64, tolerance: f64) {
        assert!(
            (actual - expected).abs() <= tolerance,
            "expected {expected:.16e}, got {actual:.16e}, abs error {:.3e}",
            (actual - expected).abs()
        );
    }

    #[test]
    fn cancelled_internal_relay_enters_continuous_network_as_exact_zero() {
        let program = Program {
            schema_version: SCHEMA_VERSION,
            nodes: vec!["0".to_string(), "z".to_string(), "y".to_string()],
            contributions: vec![Contribution {
                branch: BranchIdentity {
                    instance: "uut".to_string(),
                    local_positive: "y".to_string(),
                    local_negative: "0".to_string(),
                    kind: ContributionKind::Voltage,
                },
                positive: 2,
                negative: 0,
                rhs: Expression::Operator { operator: 0 },
                origin: origin(),
            }],
            states: Vec::new(),
            events: Vec::new(),
            operators: vec![OperatorSpec::Idt {
                input: cancelled_node(1),
                ic: 0.0,
                reset: None,
                origin: origin(),
            }],
        };
        let trajectory = no_source_trajectory(1.0);
        let continuous =
            Continuous::new(&program, &trajectory, &[], &vec![0.0; program.states.len()])
                .unwrap()
                .expect("structural internal dependency should dispatch to the continuous network");

        assert_close(continuous.values(1.0).unwrap()[0], 0.0, 1e-12);
    }

    #[test]
    fn cancelled_internal_relay_keeps_event_history_dependency() {
        let program = Program {
            schema_version: SCHEMA_VERSION,
            nodes: vec!["0".to_string(), "z".to_string(), "y".to_string()],
            contributions: vec![
                Contribution {
                    branch: BranchIdentity {
                        instance: "uut".to_string(),
                        local_positive: "z".to_string(),
                        local_negative: "0".to_string(),
                        kind: ContributionKind::Voltage,
                    },
                    positive: 1,
                    negative: 0,
                    rhs: cancelled_state(0),
                    origin: origin(),
                },
                Contribution {
                    branch: BranchIdentity {
                        instance: "uut".to_string(),
                        local_positive: "y".to_string(),
                        local_negative: "0".to_string(),
                        kind: ContributionKind::Voltage,
                    },
                    positive: 2,
                    negative: 0,
                    rhs: Expression::Operator { operator: 0 },
                    origin: origin(),
                },
            ],
            states: vec![State {
                instance: "uut".to_string(),
                name: "n".to_string(),
                kind: StateKind::Real,
                initial: 0.0.into(),
            }],
            events: Vec::new(),
            operators: vec![OperatorSpec::Idt {
                input: cancelled_node(1),
                ic: 0.0,
                reset: None,
                origin: origin(),
            }],
        };
        let trajectory = no_source_trajectory(1.0);
        let continuous = Continuous::new(&program, &trajectory, &[], &[0.0])
            .unwrap()
            .unwrap();
        assert!(continuous.changes_on_event());
        assert_eq!(continuous.values(1.0).unwrap(), vec![0.0]);
    }
    #[test]
    fn selection_closes_through_voltage_relation_producers() {
        let program = Program {
            schema_version: SCHEMA_VERSION,
            nodes: vec![
                "0".to_string(),
                "u".to_string(),
                "z".to_string(),
                "y".to_string(),
            ],
            contributions: vec![
                Contribution {
                    branch: BranchIdentity {
                        instance: "uut".to_string(),
                        local_positive: "z".to_string(),
                        local_negative: "0".to_string(),
                        kind: ContributionKind::Voltage,
                    },
                    positive: 2,
                    negative: 0,
                    rhs: Expression::Operator { operator: 0 },
                    origin: origin(),
                },
                Contribution {
                    branch: BranchIdentity {
                        instance: "uut".to_string(),
                        local_positive: "y".to_string(),
                        local_negative: "0".to_string(),
                        kind: ContributionKind::Voltage,
                    },
                    positive: 3,
                    negative: 0,
                    rhs: Expression::Operator { operator: 1 },
                    origin: origin(),
                },
            ],
            states: Vec::new(),
            events: Vec::new(),
            operators: vec![
                OperatorSpec::Idt {
                    input: Expression::Affine {
                        constant: 0.0,
                        terms: vec![Term {
                            node: 1,
                            coefficient: 1.0,
                        }],
                    },
                    ic: 0.0,
                    reset: None,
                    origin: origin(),
                },
                OperatorSpec::Idt {
                    input: Expression::Affine {
                        constant: 0.0,
                        terms: vec![Term {
                            node: 2,
                            coefficient: 1.0,
                        }],
                    },
                    ic: 0.0,
                    reset: None,
                    origin: origin(),
                },
            ],
        };
        let trajectory = Trajectory::new(
            TransientInputs {
                strobetimes: Vec::new(),
                pwl: vec![vec![[0.0, 1.0], [1.0, 1.0]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        let driven = vec!["u".to_string()];
        let continuous = Continuous::new(
            &program,
            &trajectory,
            &driven,
            &vec![0.0; program.states.len()],
        )
        .unwrap()
        .expect("downstream feedback idt should pull in the voltage producer idt");
        let z_value = continuous.operator_value_index(0).unwrap();
        let y_value = continuous.operator_value_index(1).unwrap();
        let values = continuous.values(1.0).unwrap();

        assert_close(values[z_value], 1.0, 1e-9);
        assert_close(values[y_value], 0.5, 1e-9);
    }

    #[test]
    fn selected_network_keeps_cancelled_event_state_dependency() {
        let cancelled_state = Expression::Add {
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: -1.0,
                    terms: Vec::new(),
                }),
                right: Box::new(Expression::State { state: 0 }),
            }),
        };
        let mut program = program_with_idt(
            Expression::Add {
                left: Box::new(Expression::Affine {
                    constant: 0.0,
                    terms: vec![Term {
                        node: 1,
                        coefficient: 1.0,
                    }],
                }),
                right: Box::new(cancelled_state),
            },
            0.0,
        );
        program.states = vec![State {
            instance: "uut".to_string(),
            name: "n".to_string(),
            kind: StateKind::Real,
            initial: 0.0.into(),
        }];
        let trajectory = no_source_trajectory(1.0);
        let continuous = Continuous::new(&program, &trajectory, &[], &[0.0])
            .unwrap()
            .unwrap();
        assert!(continuous.changes_on_event());
    }

    #[test]
    fn laplace_ramp_filter_is_invariant_under_physical_time_rescaling() {
        for tau in [1.0_f64, 1.0e-3, 1.0e-6] {
            let program = ramp_filter_program(tau);
            let trajectory = ramp_filter_trajectory(tau);
            let driven = vec!["u".to_string()];
            let continuous = Continuous::new(
                &program,
                &trajectory,
                &driven,
                &vec![0.0; program.states.len()],
            )
            .unwrap()
            .expect("second-order laplace should use the continuous network");
            for x in [0.0_f64, 0.5, 1.0, 2.0] {
                let value = continuous.values(x * tau).unwrap()[0];
                assert_close(value, normalized_two_pole_ramp(x), 2e-8);
            }
        }
    }
    #[test]
    fn self_feedback_idt_preserves_positive_initial_condition_sign() {
        let program = program_with_idt(
            Expression::Affine {
                constant: 0.0,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.0,
                }],
            },
            3.0,
        );
        let trajectory = no_source_trajectory(1.0);
        let continuous =
            Continuous::new(&program, &trajectory, &[], &vec![0.0; program.states.len()])
                .unwrap()
                .expect("self-feedback idt should enter the continuous network");

        assert_close(continuous.values(0.0).unwrap()[0], 3.0, 1e-12);
        let t = 0.5_f64;
        assert_close(continuous.values(t).unwrap()[0], 3.0 * t.exp(), 1e-9);
    }

    #[test]
    fn relaxation_idt_solves_one_minus_y_feedback() {
        let program = program_with_idt(
            Expression::Affine {
                constant: 1.0,
                terms: vec![Term {
                    node: 1,
                    coefficient: -1.0,
                }],
            },
            0.0,
        );
        let trajectory = no_source_trajectory(1.0);
        let continuous =
            Continuous::new(&program, &trajectory, &[], &vec![0.0; program.states.len()])
                .unwrap()
                .expect("feedback idt should enter the continuous network");

        let t = 1.0_f64;
        assert_close(continuous.values(t).unwrap()[0], 1.0 - (-t).exp(), 1e-9);
    }
}
