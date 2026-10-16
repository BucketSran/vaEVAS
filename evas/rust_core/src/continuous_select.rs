//! Source/held predicates freeze a continuous mode, never its physical state.
use super::*;
#[path = "continuous_select_candidates.rs"]
mod candidates;
#[path = "continuous_step_simplify.rs"]
mod step_simplify;

pub(crate) fn resolve_selection(
    expr: &Expression,
    program: &Program,
    driven: &[String],
    nodes: &[I],
    states: &[I],
) -> Result<Expression, Error> {
    resolve_with_source(expr, program, driven, nodes, states, None)
}
type SourceSign<'a> = dyn Fn(&Expression, &Expression) -> Option<i8> + 'a;

fn resolve_with_source(
    expr: &Expression,
    program: &Program,
    driven: &[String],
    nodes: &[I],
    states: &[I],
    exact: Option<&SourceSign<'_>>,
) -> Result<Expression, Error> {
    match expr {
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => {
            let left = resolve_with_source(left, program, driven, nodes, states, exact)?;
            let right = resolve_with_source(right, program, driven, nodes, states, exact)?;
            predicate(&left, program, driven, &origin.instance)?;
            predicate(&right, program, driven, &origin.instance)?;
            let a = affine_bounds::affine(&left, program)?;
            let b = affine_bounds::affine(&right, program)?;
            let value = |row: &Vec<I>| {
                row.iter()
                    .zip(nodes.iter().chain(states))
                    .filter(|(c, _)| !c.zero())
                    .fold(*row.last().unwrap(), |v, (&c, &x)| v + c * x)
            };
            let difference = value(&a) - value(&b);
            let decision = match relation {
                crate::ir::Relation::Lt => (difference.hi < 0., difference.lo >= 0.),
                crate::ir::Relation::Le => (difference.hi <= 0., difference.lo > 0.),
                crate::ir::Relation::Gt => (difference.lo > 0., difference.hi <= 0.),
                crate::ir::Relation::Ge => (difference.lo >= 0., difference.hi < 0.),
            };
            // Point predicates retain the exact binary64 affine product-sum certificate.
            let selected = if decision.0 || decision.1 {
                decision.0
            } else if let Some(sign) = exact.and_then(|f| f(&left, &right)) {
                match relation {
                    crate::ir::Relation::Lt => sign < 0,
                    crate::ir::Relation::Le => sign <= 0,
                    crate::ir::Relation::Gt => sign > 0,
                    crate::ir::Relation::Ge => sign >= 0,
                }
            } else {
                let bind = |e: &Expression| bind_states(e, states);
                let probe = Expression::Select {
                    relation: *relation,
                    left: Box::new(bind(&left)?),
                    right: Box::new(bind(&right)?),
                    then_value: Box::new(Expression::Affine {
                        constant: 1.,
                        terms: vec![],
                    }),
                    else_value: Box::new(Expression::Affine {
                        constant: 0.,
                        terms: vec![],
                    }),
                    origin: origin.clone(),
                };
                matches!(
                    crate::expression::resolve_selects(&probe, nodes)?,
                    Expression::Affine { constant: 1., .. }
                )
            };
            resolve_with_source(
                if selected { then_value } else { else_value },
                program,
                driven,
                nodes,
                states,
                exact,
            )
        }
        Expression::Add { left, right } => Ok(Expression::Add {
            left: Box::new(resolve_with_source(
                left, program, driven, nodes, states, exact,
            )?),
            right: Box::new(resolve_with_source(
                right, program, driven, nodes, states, exact,
            )?),
        }),
        Expression::Multiply { left, right } => Ok(Expression::Multiply {
            left: Box::new(resolve_with_source(
                left, program, driven, nodes, states, exact,
            )?),
            right: Box::new(resolve_with_source(
                right, program, driven, nodes, states, exact,
            )?),
        }),
        Expression::Divide { left, right } => Ok(Expression::Divide {
            left: Box::new(resolve_with_source(
                left, program, driven, nodes, states, exact,
            )?),
            right: Box::new(resolve_with_source(
                right, program, driven, nodes, states, exact,
            )?),
        }),
        Expression::Power { base, exponent } => Ok(Expression::Power {
            base: Box::new(resolve_with_source(
                base, program, driven, nodes, states, exact,
            )?),
            exponent: *exponent,
        }),
        _ => Ok(expr.clone()),
    }
}

fn bind_states(expr: &Expression, states: &[I]) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::State { state } => {
            let x = states
                .get(*state)
                .ok_or_else(|| Error::new("invalid_ir", "missing held predicate state"))?;
            if x.lo != x.hi {
                return Err(Error::new(
                    "condition_precision",
                    "held predicate state is uncertain",
                ));
            }
            Expression::Affine {
                constant: x.lo,
                terms: vec![],
            }
        }
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind_states(left, states)?),
            right: Box::new(bind_states(right, states)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind_states(left, states)?),
            right: Box::new(bind_states(right, states)?),
        },
        _ => expr.clone(),
    })
}

fn predicate(
    expr: &Expression,
    program: &Program,
    driven: &[String],
    owner: &str,
) -> Result<crate::events::AffineState, Error> {
    if crate::analog::has_select(expr) {
        let forms = candidates::forms(expr, &mut 4096)?;
        for form in forms {
            predicate(&form, program, driven, owner)?;
        }
        return crate::events::affine(
            &Expression::Affine {
                constant: 0.,
                terms: vec![],
            },
            program,
            owner,
        );
    }
    let row = crate::events::affine(expr, program, owner)?;
    if !row.operator_dependencies.is_empty()
        || row
            .node_dependencies
            .iter()
            .any(|&n| n != 0 && !driven.contains(&program.nodes[n]))
    {
        return Err(Error::new("unsupported_transient","continuous predicates require directly driven sources and held state; internal voltage/operator predicates are unsupported"));
    }
    Ok(row)
}

pub(crate) fn validate(
    expr: &Expression,
    program: &Program,
    driven: &[String],
    owner: &str,
) -> Result<(), Error> {
    match expr {
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            if origin.instance != owner
                || !origin.valid_expansion()
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
            {
                return Err(Error::new("invalid_ir", "invalid continuous select origin"));
            }
            validate(left, program, driven, owner)?;
            validate(right, program, driven, owner)?;
            predicate(left, program, driven, owner)?;
            predicate(right, program, driven, owner)?;
            validate(then_value, program, driven, owner)?;
            validate(else_value, program, driven, owner)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            validate(left, program, driven, owner)?;
            validate(right, program, driven, owner)
        }
        Expression::Power { base, .. } => validate(base, program, driven, owner),
        _ => super::nonlinear::validate(expr, program, owner),
    }
}

fn physical_expressions(program: &Program) -> impl Iterator<Item = (&Expression, &str)> {
    program
        .contributions
        .iter()
        .map(|c| (&c.rhs, c.origin.instance.as_str()))
        .chain(program.operators.iter().filter_map(|o| match o {
            OperatorSpec::Idt { input, origin, .. }
            | OperatorSpec::LaplaceNd { input, origin, .. }
            | OperatorSpec::Ddt { input, origin, .. }
            | OperatorSpec::Math { input, origin, .. } => Some((input, origin.instance.as_str())),
            _ => None,
        }))
}
pub(super) fn time_parameters(program: &Program) -> BTreeSet<usize> {
    fn states(e: &Expression, out: &mut BTreeSet<usize>) {
        match e {
            Expression::State { state } => {
                out.insert(*state);
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                states(left, out);
                states(right, out);
            }
            Expression::Power { base, .. } => states(base, out),
            Expression::EventMath { args, .. } => {
                for a in args {
                    states(a, out);
                }
            }
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for a in [left, right, then_value, else_value] {
                    states(a, out);
                }
            }
            _ => {}
        }
    }
    fn guards(e: &Expression, out: &mut BTreeSet<usize>) {
        match e {
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                states(left, out);
                states(right, out);
                for a in [left, right, then_value, else_value] {
                    guards(a, out);
                }
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                guards(left, out);
                guards(right, out);
            }
            Expression::Power { base, .. } => guards(base, out),
            Expression::EventMath { args, .. } => {
                for a in args {
                    guards(a, out);
                }
            }
            _ => {}
        }
    }
    let mut out = BTreeSet::new();
    for (e, _) in expressions(program) {
        guards(e, &mut out);
    }
    out
}

fn expressions(program: &Program) -> impl Iterator<Item = (&Expression, &str)> {
    physical_expressions(program).chain(program.step_bounds.iter().flat_map(|b| {
        [
            (&b.active, b.origin.instance.as_str()),
            (&b.value, b.origin.instance.as_str()),
        ]
    }))
}
pub(super) fn physical_needed(program: &Program) -> bool {
    physical_expressions(program).any(|(e, _)| crate::analog::has_select(e))
}
pub(super) fn needed(program: &Program) -> bool {
    expressions(program).any(|(e, _)| crate::analog::has_select(e))
}

pub(super) fn build(
    context: Arc<Context>,
    parameters: Vec<I>,
    start: f64,
    restart: Option<Vec<I>>,
) -> Result<Option<LinearContinuous>, Error> {
    let history_program = step_simplify::program(&context, &parameters)?;
    let program = &history_program;
    let mut cuts = vec![I::point(start), I::point(context.trajectory.config.stop)];
    cuts.extend(
        context
            .trajectory
            .knots
            .iter()
            .copied()
            .filter(|&t| t > start)
            .map(I::point),
    );
    // Ordinary and nested predicates share one complete root analysis. An
    // uncertain endpoint is not evidence that the segment has no crossing.
    let mut roots = candidates::Roots::new();
    for (expr, owner) in expressions(program) {
        validate(expr, program, &context.driven, owner)?;
        roots.collect(
            expr,
            program,
            &context.driven,
            &context.trajectory,
            &parameters,
            &context.time_proofs,
        )?;
    }
    roots.finish(&mut cuts, start, context.trajectory.config.stop)?;
    cuts.retain(|c| c.hi >= start);
    cuts.sort_by(|a, b| a.hi.total_cmp(&b.hi));
    cuts.dedup();
    let mut segments = Vec::new();
    let mut seed = restart;
    let mut result = None;
    for pair in cuts.windows(2) {
        let (begin, end) = (pair[0].hi, pair[1].hi);
        if begin == end {
            continue;
        }
        let mid = begin * 0.5 + pair[1].lo * 0.5;
        if mid <= begin || mid >= pair[1].lo {
            return Err(Error::new(
                "condition_precision",
                "no representable interior of selected mode",
            ));
        }
        let mut nodes = vec![I::ZERO; program.nodes.len()];
        for (name, v) in context
            .driven
            .iter()
            .zip(context.trajectory.value_bounds(mid))
        {
            nodes[program.nodes.iter().position(|n| n == name).unwrap()] = v;
        }
        let mut frozen = program.clone();
        for c in &mut frozen.contributions {
            c.rhs = resolve_selection(&c.rhs, program, &context.driven, &nodes, &parameters)?;
        }
        for o in &mut frozen.operators {
            match o {
                OperatorSpec::Idt { input, .. }
                | OperatorSpec::LaplaceNd { input, .. }
                | OperatorSpec::Ddt { input, .. }
                | OperatorSpec::Math { input, .. } => {
                    *input =
                        resolve_selection(input, program, &context.driven, &nodes, &parameters)?
                }
                _ => {}
            }
        }
        for b in &mut frozen.step_bounds {
            b.active = crate::step_bounds::possible_activation(&b.active, &|e| {
                resolve_selection(e, program, &context.driven, &nodes, &parameters)
            })?;
            b.value = resolve_selection(&b.value, program, &context.driven, &nodes, &parameters)?;
        }
        let mut trajectory = context.trajectory.clone();
        trajectory.solver_points.retain(|&t| t >= begin && t <= end);
        trajectory.solver_points.extend([begin, end]);
        trajectory.solver_points.sort_by(f64::total_cmp);
        trajectory.solver_points.dedup();
        // End construction at this mode boundary, never extrapolate its flow through another regime.
        trajectory.config.stop = end;
        let branch_context = Arc::new(Context {
            program: Arc::new(frozen),
            trajectory,
            driven: context.driven.clone(),
            force_integrals: true,
            detached_timed: context.detached_timed,
            live_parameters: context.live_parameters.clone(),
            time_proofs: context.time_proofs.clone(),
        });
        let mut branch =
            LinearContinuous::build(branch_context.clone(), parameters.clone(), begin, seed)?
                .ok_or_else(|| {
                    Error::new(
                        "unsupported_operator",
                        "selected continuous mode contains no integral network",
                    )
                })?;
        if pair[0].lo != pair[0].hi {
            let first = &branch.segments[0];
            let image = crate::state_space::propagate(
                &first.matrix,
                &first.initial,
                I {
                    lo: 0.,
                    hi: (I::point(pair[0].hi) - I::point(pair[0].lo)).hi,
                },
            )?;
            let enlarged = branch
                .initial
                .iter()
                .zip(image)
                .map(|(&a, b)| a.hull(b))
                .collect();
            branch =
                LinearContinuous::build(branch_context, parameters.clone(), begin, Some(enlarged))?
                    .unwrap();
        }
        let count = branch.initial.len();
        let tail = branch.segments.last().unwrap();
        let mut physical = crate::state_space::propagate(
            &tail.matrix,
            &tail.initial,
            I::point(end) - I::point(tail.start),
        )?[..count]
            .to_vec();
        // The switch lies anywhere in its enclosed root box. Preserve the old-flow
        // range and bound post-switch flow over the whole box when seeding the next mode.
        if pair[1].lo != pair[1].hi {
            let before = crate::state_space::propagate(
                &tail.matrix,
                &tail.initial,
                pair[1] - I::point(tail.start),
            )?;
            for (v, b) in physical.iter_mut().zip(before) {
                *v = v.hull(b);
            }
        }
        seed = Some(physical);
        segments.extend(branch.segments.iter().cloned());
        if result.is_none() {
            result = Some(branch);
        }
    }
    let Some(mut result) = result else {
        return Ok(None);
    };
    result.segments = Arc::new(segments);
    result.stop = context.trajectory.config.stop;
    result.context = context;
    result.parameters = parameters;
    result.start = start;
    result.event_dependent = true;
    result.exact_affine = None;
    Ok(Some(result))
}

// Every part has a physical interval and, for an uncertain switch, its full
// root certificate. PWL corners split coverage but never truncate the proof.
pub(super) fn nonlinear_parts(
    context: &Context,
    parameters: &[I],
    start: f64,
    horizon: f64,
) -> Result<Vec<(I, Option<I>)>, Error> {
    let program = step_simplify::program(context, parameters)?;
    let mut roots = candidates::Roots::new();
    for (expr, owner) in expressions(&program) {
        validate(expr, &program, &context.driven, owner)?;
        roots.collect(
            expr,
            &program,
            &context.driven,
            &context.trajectory,
            parameters,
            &context.time_proofs,
        )?;
    }
    let roots = roots.window_roots(start, horizon)?;
    let mut points = vec![start, horizon];
    points.extend(
        context
            .trajectory
            .knots
            .iter()
            .copied()
            .filter(|t| *t > start && *t < horizon),
    );
    points.extend(
        context
            .trajectory
            .config
            .strobetimes
            .iter()
            .copied()
            .filter(|t| *t > start && *t < horizon),
    );
    for root in &roots {
        points.extend(
            [root.lo, root.hi]
                .into_iter()
                .filter(|t| *t > start && *t < horizon),
        );
    }
    points.sort_by(f64::total_cmp);
    points.dedup();
    Ok(points
        .windows(2)
        .map(|p| {
            let span = I { lo: p[0], hi: p[1] };
            let root = roots
                .iter()
                .find(|r| r.lo < r.hi && span.lo < r.hi && span.hi > r.lo)
                .copied();
            (span, root)
        })
        .collect())
}
pub(super) fn freeze_context(
    context: &Arc<Context>,
    parameters: &[I],
    time: f64,
) -> Result<Arc<Context>, Error> {
    let mut nodes = vec![I::ZERO; context.program.nodes.len()];
    for (name, v) in context
        .driven
        .iter()
        .zip(context.trajectory.value_bounds(time))
    {
        nodes[context
            .program
            .nodes
            .iter()
            .position(|n| n == name)
            .unwrap()] = v;
    }
    let input_nodes: Vec<_> = context
        .driven
        .iter()
        .map(|name| {
            context
                .program
                .nodes
                .iter()
                .position(|n| n == name)
                .unwrap()
        })
        .collect();
    let exact = |left: &Expression, right: &Expression| {
        context.trajectory.original_predicate_sign(
            &bind_states(left, parameters).ok()?,
            &bind_states(right, parameters).ok()?,
            &input_nodes,
            time,
        )
    };
    let mut frozen = step_simplify::program(context, parameters)?;
    for c in &mut frozen.contributions {
        c.rhs = resolve_with_source(
            &c.rhs,
            &context.program,
            &context.driven,
            &nodes,
            parameters,
            Some(&exact),
        )?;
    }
    for o in &mut frozen.operators {
        match o {
            OperatorSpec::Idt { input, .. }
            | OperatorSpec::LaplaceNd { input, .. }
            | OperatorSpec::Ddt { input, .. }
            | OperatorSpec::Math { input, .. } => {
                *input = resolve_with_source(
                    input,
                    &context.program,
                    &context.driven,
                    &nodes,
                    parameters,
                    Some(&exact),
                )?
            }
            _ => {}
        }
    }
    for b in &mut frozen.step_bounds {
        b.active = crate::step_bounds::possible_activation(&b.active, &|e| {
            resolve_with_source(
                e,
                &context.program,
                &context.driven,
                &nodes,
                parameters,
                Some(&exact),
            )
        })?;
        b.value = resolve_with_source(
            &b.value,
            &context.program,
            &context.driven,
            &nodes,
            parameters,
            Some(&exact),
        )?;
    }
    Ok(Arc::new(Context {
        program: Arc::new(frozen),
        trajectory: context.trajectory.clone(),
        driven: context.driven.clone(),
        force_integrals: true,
        detached_timed: context.detached_timed,
        live_parameters: context.live_parameters.clone(),
        time_proofs: context.time_proofs.clone(),
    }))
}

pub(super) fn has_variable_division(expr: &Expression) -> bool {
    match expr {
        Expression::Divide { .. } => true,
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            has_variable_division(left) || has_variable_division(right)
        }
        Expression::Power { base, .. } => has_variable_division(base),
        Expression::Select {
            then_value,
            else_value,
            ..
        } => has_variable_division(then_value) || has_variable_division(else_value),
        _ => false,
    }
}

// Source-root witnesses must be isolated from every
// predicate root, even if that other root is outside the prediction horizon.
pub(super) fn isolated_root_witnesses(
    context: &Context,
    parameters: &[I],
    root: I,
) -> Result<[f64; 2], Error> {
    let fail = || {
        Error::new(
            "condition_precision",
            "root side witness touches another predicate root",
        )
    };
    let left = root.lo.next_down();
    let right = root.hi.next_up();
    if !root.finite() || root.lo >= root.hi || left < 0. || right > context.trajectory.config.stop {
        return Err(fail());
    }
    let program = step_simplify::program(context, parameters)?;
    let mut roots = candidates::Roots::new();
    for (expr, owner) in expressions(&program) {
        validate(expr, &program, &context.driven, owner)?;
        roots.collect(
            expr,
            &program,
            &context.driven,
            &context.trajectory,
            parameters,
            &context.time_proofs,
        )?;
    }
    let neighbors = roots.window_roots(left, right)?;
    if neighbors.is_empty() || neighbors.iter().any(|r| *r != root) {
        return Err(fail());
    }
    Ok([left, right])
}
