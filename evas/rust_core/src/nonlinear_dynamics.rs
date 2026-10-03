//! Validated polynomial ODE propagation for integral and filter call-site states.
//! A Picard enclosure proves a finite trajectory tube. Order-12 interval Taylor
//! coefficients propagate accepted uncertainty; order 13 over the tube bounds
//! the entire-step remainder. Output queries are immutable dense observations.
use super::*;

const ORDER: usize = 12;
const MAX_STEPS: usize = 16_384;
const TUBE_ATTEMPTS: usize = 16;
type Jet = Vec<I>;

#[path = "implicit_dynamics.rs"]
mod implicit;
pub(crate) use implicit::run as run_implicit;

#[derive(Clone)]
enum Polynomial {
    Linear(Vec<I>),
    Add(Box<Self>, Box<Self>),
    Multiply(Box<Self>, Box<Self>),
    Power(Box<Self>, u32),
}

pub(super) fn validate(expr: &Expression, program: &Program, owner: &str) -> Result<(), Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            validate(left, program, owner)?;
            validate(right, program, owner)
        }
        Expression::Power { base, exponent } if (1..=32).contains(exponent) => {
            validate(base, program, owner)
        }
        Expression::Select { .. } | Expression::Power { .. } => Err(Error::new(
            "unsupported_operator",
            "integral input must be a polynomial with powers 1..32",
        )),
        _ => crate::events::affine(expr, program, owner).map(|_| ()),
    }
}

impl Polynomial {
    fn compile(
        expr: &Expression,
        program: &Program,
        system: &AlgebraicSystem,
        mapping: &[Vec<I>],
    ) -> Result<Self, Error> {
        let result = match expr {
            Expression::Add { left, right } => Self::Add(
                Box::new(Self::compile(left, program, system, mapping)?),
                Box::new(Self::compile(right, program, system, mapping)?),
            ),
            Expression::Multiply { left, right } => Self::Multiply(
                Box::new(Self::compile(left, program, system, mapping)?),
                Box::new(Self::compile(right, program, system, mapping)?),
            ),
            Expression::Power { base, exponent } => Self::Power(
                Box::new(Self::compile(base, program, system, mapping)?),
                *exponent,
            ),
            _ => Self::Linear(expand_input(
                &affine_bounds::affine(expr, program)?,
                program,
                system,
                mapping,
            )?),
        };
        Ok(result)
    }

    fn dc_affine(&self, known: &[Option<I>]) -> Option<Vec<I>> {
        match self {
            Self::Linear(row) => {
                let mut row = row.clone();
                for (i, value) in known.iter().enumerate() {
                    if let Some(value) = value {
                        let last = row.len() - 1;
                        row[last] = row[last] + row[i] * *value;
                        row[i] = I::ZERO;
                    }
                }
                Some(row)
            }
            Self::Add(a, b) => Some(
                a.dc_affine(known)?
                    .into_iter()
                    .zip(b.dc_affine(known)?)
                    .map(|(a, b)| a + b)
                    .collect(),
            ),
            Self::Multiply(a, b) => {
                let a = a.dc_affine(known)?;
                let b = b.dc_affine(known)?;
                let constant = |row: &[I]| row[..row.len() - 1].iter().all(|v| v.zero());
                if constant(&a) {
                    Some(b.iter().map(|&v| *a.last().unwrap() * v).collect())
                } else if constant(&b) {
                    Some(a.iter().map(|&v| *b.last().unwrap() * v).collect())
                } else {
                    None
                }
            }
            Self::Power(a, n) => {
                let mut row = a.dc_affine(known)?;
                if *n == 1 {
                    return Some(row);
                }
                if row[..row.len() - 1].iter().any(|v| !v.zero()) {
                    return None;
                }
                let last = row.len() - 1;
                row[last] = (0..*n).fold(I::ONE, |value, _| value * row[last]);
                Some(row)
            }
        }
    }

    fn jet(&self, variables: &[Jet], order: usize) -> Jet {
        match self {
            Self::Linear(row) => {
                let mut out = vec![I::ZERO; order + 1];
                out[0] = *row.last().unwrap();
                for (&coefficient, variable) in row.iter().zip(variables) {
                    for (slot, value) in out.iter_mut().zip(variable) {
                        *slot = *slot + coefficient * *value;
                    }
                }
                out
            }
            Self::Add(a, b) => a
                .jet(variables, order)
                .into_iter()
                .zip(b.jet(variables, order))
                .map(|(x, y)| x + y)
                .collect(),
            Self::Multiply(a, b) => {
                multiply(&a.jet(variables, order), &b.jet(variables, order), order)
            }
            Self::Power(a, n) => {
                let a = a.jet(variables, order);
                let mut out = vec![I::ZERO; order + 1];
                out[0] = I::ONE;
                for _ in 0..*n {
                    out = multiply(&out, &a, order);
                }
                out
            }
        }
    }
}

fn multiply(a: &[I], b: &[I], order: usize) -> Jet {
    (0..=order)
        .map(|n| (0..=n).fold(I::ZERO, |sum, k| sum + a[k] * b[n - k]))
        .collect()
}

#[derive(Clone, PartialEq)]
struct DenseStep {
    start: f64,
    end: f64,
    coefficients: Vec<Jet>,
    remainder: Vec<I>,
}

impl DenseStep {
    fn range(&self, time: I) -> Vec<I> {
        let h = time - I::point(self.start);
        let h13 = (0..=ORDER).fold(I::ONE, |v, _| v * h);
        self.coefficients
            .iter()
            .zip(&self.remainder)
            .map(|(row, &r)| row.iter().rev().fold(I::ZERO, |sum, &a| sum * h + a) + r * h13)
            .collect()
    }
}

#[derive(Clone)]
pub(crate) struct NonlinearContinuous {
    context: Arc<Context>,
    parameters: Vec<I>,
    functions: Vec<Polynomial>,
    implicit: Option<implicit::ImplicitField>,
    operators: Vec<NetworkOperator>,
    values: Vec<Vec<I>>,
    initial: Vec<I>,
    steps: Vec<DenseStep>,
    start: f64,
    event_dependent: bool,
}

impl NonlinearContinuous {
    pub(super) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
    ) -> Result<Self, Error> {
        Self::build(
            Arc::new(Context {
                program: program.clone(),
                trajectory: trajectory.clone(),
                driven: driven.to_vec(),
            }),
            states.iter().copied().map(I::point).collect(),
            0.0,
            None,
            horizon,
        )
    }

    fn build(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
        horizon: f64,
    ) -> Result<Self, Error> {
        let mut result = Self::initialized(context, parameters, start, restart)?;
        result.propagate_until(horizon)?;
        Ok(result)
    }

    // Compile the new mode and apply reset before propagating. A candidate
    // restart must first enclose its uncertain event-to-representative flow.
    fn initialized(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
    ) -> Result<Self, Error> {
        let program = &context.program;
        let driven = driven_node_indices(program, &context.driven)?;
        let mut sources = vec![None; program.nodes.len()];
        for (i, &node) in driven.iter().enumerate() {
            sources[node] = Some(i);
        }
        let mut operators = Vec::new();
        let mut state_count = 0;
        let mut event_dependent = false;
        for (i, spec) in program.operators.iter().enumerate() {
            let origin = spec.origin();
            let (kind, input, states, laplace, held_reset) = match spec {
                OperatorSpec::Idt { input, ic, reset, .. } => {
                    validate(input, program, &origin.instance)?;
                    if !ic.is_finite() {
                        return Err(unsupported(origin, "nonfinite nonlinear integral IC"));
                    }
                    let held = if let Some(reset) = reset {
                        let dependencies = crate::events::affine(reset, program, &origin.instance)?;
                        if !dependencies.node_dependencies.is_empty()
                            || !dependencies.operator_dependencies.is_empty()
                        {
                            return Err(unsupported(origin,
                                "nonlinear integral reset must depend on event state and constants"));
                        }
                        event_dependent = true;
                        crate::operators::ResetExpression::new(reset.clone()).active(&parameters)?
                    } else { false };
                    let state = state_count;
                    state_count += 1;
                    (ContinuousKind::Idt, input, vec![state], None, held)
                }
                OperatorSpec::LaplaceNd { input, numerator, denominator, .. } => {
                    validate(input, program, &origin.instance)?;
                    let filter = laplace_system(numerator, denominator, origin)?;
                    if !filter.d.zero() && affine_for_operator_input(input, program, origin).is_err() {
                        return Err(unsupported(origin, "polynomial filter input requires a strictly proper transfer function"));
                    }
                    let states = (state_count..state_count + filter.a.len()).collect();
                    state_count += filter.a.len();
                    (ContinuousKind::LaplaceNd, input, states, Some(filter), false)
                }
                _ => return Err(unsupported(origin,
                    "polynomial continuous network supports explicit-IC integrals and affine-input proper filters; derivative/function coupling needs a certified reduction")),
            };
            event_dependent |=
                history_event_dependency(input, program, origin, &driven, &mut BTreeSet::new());
            let mut structural =
                vec![
                    I::ZERO;
                    program.nodes.len() + program.states.len() + program.operators.len() + 1
                ];
            if let Ok(row) = affine_for_operator_input(input, program, origin) {
                structural = row;
            } else {
                collect_structure(input, program, &origin.instance, &mut structural)?;
            }
            operators.push(NetworkOperator {
                operator: i,
                kind,
                origin: origin.clone(),
                states,
                input: Some(structural),
                laplace,
                held_reset,
            });
        }
        if state_count + 2 * driven.len() + 1 > 32 {
            return Err(Error::new(
                "waveform_accuracy",
                "nonlinear state/source dimension exceeds 32",
            ));
        }
        let system = AlgebraicSystem::new(
            program,
            &operators,
            &driven,
            &sources,
            state_count,
            driven.len(),
            &parameters,
        )?;
        let rows = affine_bounds::eliminate(system.rows.clone(), system.x_count, system.width)?;
        let mapping = back_substitute_eliminated(&rows, system.x_count, system.width)?;
        let values = build_value_rows(&operators, &system, &mapping)?;
        let mut functions = vec![Polynomial::Linear(vec![I::ZERO; system.width]); state_count];
        for op in &operators {
            match &program.operators[op.operator] {
                OperatorSpec::Idt { input, .. } if !op.held_reset => {
                    functions[op.states[0]] =
                        Polynomial::compile(input, program, &system, &mapping)?;
                }
                OperatorSpec::LaplaceNd { input, .. } => {
                    let input = Polynomial::compile(input, program, &system, &mapping)?;
                    let filter = op.laplace.as_ref().unwrap();
                    for (local, &state) in op.states.iter().enumerate() {
                        let mut row = vec![I::ZERO; system.width];
                        for (&other, &coefficient) in op.states.iter().zip(&filter.a[local]) {
                            row[other] = row[other] + coefficient;
                        }
                        let mut gain = vec![I::ZERO; system.width];
                        *gain.last_mut().unwrap() = filter.b[local];
                        functions[state] = Polynomial::Add(
                            Box::new(Polynomial::Linear(row)),
                            Box::new(Polynomial::Multiply(
                                Box::new(Polynomial::Linear(gain)),
                                Box::new(input.clone()),
                            )),
                        );
                    }
                }
                _ => {}
            }
        }
        let mut initial = if let Some(state) = restart {
            // Restart is an IVP with accepted physical history. It must not
            // impose a new DC equilibrium on the event's future vector field.
            state
        } else {
            // Only cold initialization needs filter DC equations. Integral
            // states pin their IC, not their derivative to zero.
            let mut dc_derivatives = vec![vec![I::ZERO; system.width]; state_count];
            let mut known = vec![None; system.width - 1];
            for op in &operators {
                if let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] {
                    known[op.states[0]] = Some(I::point(*ic));
                }
            }
            for (slot, value) in known[state_count..]
                .iter_mut()
                .zip(context.trajectory.value_bounds(0.0))
            {
                *slot = Some(value);
            }
            for slot in &mut known[state_count + driven.len()..] {
                *slot = Some(I::ZERO);
            }
            for op in operators
                .iter()
                .filter(|op| op.kind == ContinuousKind::LaplaceNd)
            {
                for &state in &op.states {
                    dc_derivatives[state] = functions[state].dc_affine(&known).ok_or_else(||
                        unsupported(&op.origin, "nonlinear filter DC feedback requires a certified algebraic initialization"))?;
                }
            }
            initial_state(
                program,
                &operators,
                &system,
                &dc_derivatives,
                &context.trajectory,
            )?
        };
        for op in &operators {
            if op.held_reset {
                let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] else {
                    unreachable!()
                };
                initial[op.states[0]] = I::point(*ic);
            }
        }
        Ok(Self {
            context,
            parameters,
            functions,
            implicit: None,
            operators,
            values,
            initial,
            steps: Vec::new(),
            start,
            event_dependent,
        })
    }

    fn derivative_jets(&self, variables: &[Jet], slopes: &[I], order: usize) -> Option<Vec<Jet>> {
        if let Some(field) = &self.implicit {
            field.jets(&self.functions, variables, slopes, order)
        } else {
            Some(
                self.functions
                    .iter()
                    .map(|f| f.jet(variables, order))
                    .collect(),
            )
        }
    }

    fn jets(&self, state: &[I], source: &[I], slopes: &[I], order: usize) -> Option<Vec<Jet>> {
        let mut variables: Vec<_> = state
            .iter()
            .chain(source)
            .map(|&v| {
                let mut row = vec![I::ZERO; order + 1];
                row[0] = v;
                row
            })
            .collect();
        for (variable, &slope) in variables[state.len()..].iter_mut().zip(slopes) {
            if order > 0 {
                variable[1] = slope;
            }
        }
        for n in 0..order {
            let derivatives: Vec<_> = self
                .derivative_jets(&variables, slopes, n)?
                .into_iter()
                .map(|row| row[n] / I::point((n + 1) as f64))
                .collect();
            for (variable, value) in variables.iter_mut().zip(derivatives) {
                variable[n + 1] = value;
            }
        }
        Some(variables[..state.len()].to_vec())
    }

    fn trial(
        &self,
        start: f64,
        end: f64,
        state: &[I],
        source: &[I],
        slopes: &[I],
    ) -> Option<DenseStep> {
        let duration = I::point(end) - I::point(start);
        let elapsed = I {
            lo: 0.0,
            hi: duration.hi,
        };
        let source_tube: Vec<_> = source
            .iter()
            .zip(slopes)
            .map(|(&u, &m)| u + elapsed * m)
            .collect();
        let (tube, _) = self.picard_enclosure(state, &source_tube, slopes, elapsed)?;
        let coefficients = self.jets(state, source, slopes, ORDER)?;
        let remainder: Vec<_> = self
            .jets(&tube, &source_tube, slopes, ORDER + 1)?
            .into_iter()
            .map(|row| row[ORDER + 1])
            .collect();
        let step = DenseStep {
            start,
            end,
            coefficients,
            remainder,
        };
        let tail_power = (0..=ORDER).fold(I::ONE, |v, _| v * duration);
        let values = step.range(I::point(end));
        if values.iter().any(|v| !v.finite())
            || step.remainder.iter().zip(&values).any(|(&r, v)| {
                !(r * tail_power).finite()
                    || (r * tail_power).magnitude() > 1e-16 * (1.0 + v.magnitude())
            })
        {
            return None;
        }
        Some(step)
    }

    // Bounds all flows starting anywhere in `initial`, with any source value
    // in `source`, over any duration in [0, elapsed.hi]. This needs no PWL
    // slope assumption and is therefore also valid across a source corner.
    fn picard_enclosure(
        &self,
        initial: &[I],
        source: &[I],
        slopes: &[I],
        elapsed: I,
    ) -> Option<(Vec<I>, Vec<I>)> {
        let evaluate = |state: &[I]| {
            let variables: Vec<_> = state.iter().chain(source).map(|&v| vec![v]).collect();
            self.derivative_jets(&variables, slopes, 0)
                .map(|rows| rows.into_iter().map(|row| row[0]).collect::<Vec<_>>())
        };
        let mut derivative = evaluate(initial)?;
        for _ in 0..TUBE_ATTEMPTS {
            let tube: Vec<_> = initial
                .iter()
                .zip(&derivative)
                .map(|(&v, &d)| {
                    let radius =
                        (I::point(elapsed.hi) * I::point(d.magnitude().max(1e-15)) * I::point(2.0))
                            .hi;
                    let expanded = v + I {
                        lo: -radius,
                        hi: radius,
                    };
                    // Even zero flows and sub-ulp durations require a strict
                    // tube around every possible initial value.
                    I {
                        lo: expanded.lo.next_down(),
                        hi: expanded.hi.next_up(),
                    }
                })
                .collect();
            if tube.iter().any(|v| !v.finite()) {
                return None;
            }
            derivative = evaluate(&tube)?;
            let image: Vec<_> = initial
                .iter()
                .zip(&derivative)
                .map(|(&v, &d)| v + elapsed * d)
                .collect();
            if image
                .iter()
                .zip(&tube)
                .all(|(v, z)| v.finite() && v.lo > z.lo && v.hi < z.hi)
            {
                return Some((tube, image));
            }
        }
        None
    }

    pub(super) fn certified_end(&self) -> f64 {
        self.steps.last().map_or(self.start, |step| step.end)
    }

    // Extend only a disposable candidate; retained dense steps and their
    // endpoint enclosures stay unchanged when an event leaves the mode intact.
    fn propagate_until(&mut self, horizon: f64) -> Result<(), Error> {
        let _timing = crate::diagnostics::span("history.nonlinear_propagate");

        let trajectory = &self.context.trajectory;
        if !horizon.is_finite() || horizon < self.start || horizon > trajectory.config.stop {
            return Err(Error::new(
                "event_resolution",
                "invalid nonlinear prediction horizon",
            ));
        }
        let start = self.certified_end();
        if horizon <= start {
            return Ok(());
        }
        let mut state = self.steps.last().map_or_else(
            || self.initial.clone(),
            |step| step.range(I::point(step.end)),
        );
        let mut knots = vec![start];
        knots.extend(
            trajectory
                .knots
                .iter()
                .copied()
                .filter(|t| *t > start && *t < horizon),
        );
        knots.push(horizon);
        for segment in knots.windows(2) {
            let (a, b) = (segment[0], segment[1]);
            let slopes: Vec<_> = trajectory
                .value_bounds(b)
                .iter()
                .zip(trajectory.value_bounds(a))
                .map(|(&v, u)| (v - u) / (I::point(b) - I::point(a)))
                .collect();
            let mut start = a;
            while start < b {
                if self.steps.len() >= MAX_STEPS {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "validated nonlinear integration exceeded 16384 internal steps",
                    ));
                }
                let source = trajectory.value_bounds(start);
                let mut end = (start + 0.125).min(b);
                let mut accepted = None;
                for _ in 0..64 {
                    if end <= start {
                        break;
                    }
                    if let Some(step) = self.trial(start, end, &state, &source, &slopes) {
                        accepted = Some(step);
                        break;
                    }
                    crate::diagnostics::record(
                        "nonlinear_candidate",
                        "rejected",
                        Some(start),
                        Some(end),
                        1,
                        Some("tube or Taylor remainder not certified"),
                    );
                    crate::diagnostics::counter("nonlinear_rejected_trials", 1);
                    end = start + (end - start) * 0.5;
                }
                let step = accepted.ok_or_else(|| {
                    Error::new(
                        "waveform_accuracy",
                        "cannot certify a finite nonlinear trajectory tube or Taylor remainder",
                    )
                })?;
                state = step.range(I::point(step.end));
                start = step.end;
                self.steps.push(step);
                crate::diagnostics::counter("nonlinear_certified_candidate_steps", 1);
                crate::diagnostics::record(
                    "nonlinear_candidate",
                    "certified",
                    Some(self.steps.last().unwrap().start),
                    Some(start),
                    1,
                    None,
                );
            }
        }
        Ok(())
    }

    pub(super) fn operator_value_index(&self, op: usize) -> Option<usize> {
        self.operators.iter().position(|slot| slot.operator == op)
    }
    pub(super) fn operator_spec(&self, slot: usize) -> &OperatorSpec {
        &self.context.program.operators[self.operators[slot].operator]
    }
    pub(super) fn reset_active(&self, slot: usize) -> bool {
        self.operators[slot].held_reset
    }
    pub(super) fn changes_on_event(&self) -> bool {
        self.event_dependent
    }
    pub(super) fn same_history(&self, other: &Self) -> bool {
        self.start == other.start
            && self.certified_end() == other.certified_end()
            && self.initial == other.initial
            && self.parameters == other.parameters
            && self.steps == other.steps
    }
    pub(super) fn next_breakpoint(&self, time: f64) -> Option<f64> {
        self.context
            .trajectory
            .knots
            .iter()
            .copied()
            .find(|t| *t > time)
    }
    fn state_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        if !time.finite()
            || time.lo < self.start
            || time.hi > self.certified_end()
            || time.lo > time.hi
        {
            return Err(Error::new(
                "event_resolution",
                "nonlinear history query outside accepted trajectory",
            ));
        }
        let mut result: Vec<_> = self
            .initial
            .iter()
            .map(|&v| (time.lo == self.start).then_some(v))
            .collect();
        for step in &self.steps {
            let range = I {
                lo: time.lo.max(step.start),
                hi: time.hi.min(step.end),
            };
            if range.lo > range.hi {
                continue;
            }
            for (slot, value) in result.iter_mut().zip(step.range(range)) {
                *slot = Some(slot.map_or(value, |v| v.hull(value)));
            }
        }
        result
            .into_iter()
            .map(|v| {
                v.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "nonlinear trajectory query has no certified step",
                    )
                })
            })
            .collect()
    }
    pub(super) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        let state = self.state_bounds(time)?;
        let source = self.source_bounds(time);
        let forcing: Vec<_> = state
            .into_iter()
            .chain(source.iter().copied())
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ONE])
            .collect();
        self.values
            .iter()
            .map(|row| dot(row, &forcing, "nonlinear operator output"))
            .collect()
    }
    pub(super) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        let state = self.state_bounds(time)?;
        let (source, slopes) = self.context.trajectory.range(time)?;
        let variables: Vec<_> = state.iter().chain(&source).map(|&v| vec![v]).collect();
        let forcing: Vec<_> = self
            .derivative_jets(&variables, &slopes, 0)
            .ok_or_else(|| Error::new("waveform_accuracy", "cannot certify implicit derivative"))?
            .into_iter()
            .map(|row| row[0])
            .chain(slopes)
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ZERO])
            .collect();
        self.values
            .iter()
            .map(|row| dot(row, &forcing, "nonlinear operator derivative"))
            .collect()
    }
    fn source_bounds(&self, time: I) -> Vec<I> {
        let trajectory = &self.context.trajectory;
        let mut source = trajectory.value_bounds(time.lo);
        for t in std::iter::once(time.hi).chain(
            trajectory
                .knots
                .iter()
                .copied()
                .filter(|t| *t > time.lo && *t < time.hi),
        ) {
            for (u, v) in source.iter_mut().zip(trajectory.value_bounds(t)) {
                *u = u.hull(v);
            }
        }
        source
    }
    pub(super) fn event_bounds(&self, window: I) -> Result<Vec<I>, Error> {
        if window.lo < self.start && window.hi == self.start {
            // Candidate initial already encloses R(z(tau)) and the new flow
            // to b. Include the full source window for direct filter paths.
            let source = self.source_bounds(window);
            let forcing: Vec<_> = self
                .initial
                .iter()
                .copied()
                .chain(source.iter().copied())
                .chain(vec![I::ZERO; source.len()])
                .chain([I::ONE])
                .collect();
            self.values
                .iter()
                .map(|row| dot(row, &forcing, "nonlinear event sample"))
                .collect()
        } else {
            self.range_bounds(window)
        }
    }

    pub(super) fn restarted(
        &self,
        time: f64,
        window: I,
        parameters: &[I],
        horizon: f64,
    ) -> Result<Self, Error> {
        let mut next = self.mapped_event(time, window, parameters)?;
        if !self.event_dependent || self.parameters == parameters {
            next.propagate_until(horizon)?;
            return Ok(next);
        }
        if window.lo != window.hi {
            let elapsed = I {
                lo: 0.0,
                hi: (I::point(time) - I::point(window.lo)).hi,
            };
            let (_, image) = next
                .picard_enclosure(&next.initial, &self.source_bounds(window), &[], elapsed)
                .ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "cannot certify nonlinear event-to-representative trajectory tube",
                    )
                })?;
            next.initial = image;
        }
        next.propagate_until(horizon)?;
        Ok(next)
    }

    pub(super) fn mapped_event(
        &self,
        time: f64,
        window: I,
        parameters: &[I],
    ) -> Result<Self, Error> {
        if !self.event_dependent || self.parameters == parameters {
            return Ok(self.clone());
        }
        if !time.is_finite() || !window.finite() || window.hi != time {
            return Err(Error::new(
                "event_resolution",
                "nonlinear event representative must be the upper endpoint of its time enclosure",
            ));
        }
        Self::initialized(
            self.context.clone(),
            parameters.to_vec(),
            time,
            Some(self.state_bounds(window)?),
        )
    }
}

fn collect_structure(
    expr: &Expression,
    program: &Program,
    owner: &str,
    row: &mut [I],
) -> Result<(), Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            collect_structure(left, program, owner, row)?;
            collect_structure(right, program, owner, row)
        }
        Expression::Power { base, .. } => collect_structure(base, program, owner, row),
        _ => {
            let deps = crate::events::affine(expr, program, owner)?;
            for node in deps.node_dependencies {
                row[node] = I::ONE;
            }
            for op in deps.operator_dependencies {
                row[program.nodes.len() + program.states.len() + op] = I::ONE;
            }
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scalar(quadratic_sign: f64) -> NonlinearContinuous {
        let program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0"],
            "contributions":[]
        }))
        .unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![],
                output_times: vec![0.0, 0.125],
                stop: 0.125,
                max_step: 0.125,
            },
            0,
        )
        .unwrap();
        NonlinearContinuous {
            context: Arc::new(Context {
                program,
                trajectory,
                driven: vec![],
            }),
            parameters: vec![],
            implicit: None,
            initial: vec![I::ONE],
            steps: vec![],
            start: 0.0,
            event_dependent: false,
            operators: Vec::new(),
            values: vec![vec![I::ONE, I::ZERO]],
            functions: vec![Polynomial::Multiply(
                Box::new(Polynomial::Linear(vec![I::ZERO, I::point(quadratic_sign)])),
                Box::new(Polynomial::Power(
                    Box::new(Polynomial::Linear(vec![I::ONE, I::ZERO])),
                    2,
                )),
            )],
        }
    }

    #[test]
    fn candidate_horizon_extension_preserves_prefix_and_rejected_retry() {
        let mut accepted = scalar(-1.0);
        accepted.propagate_until(0.0625).unwrap();
        let prefix = accepted.range_bounds(I::point(0.0625)).unwrap();
        assert_eq!(
            accepted.range_bounds(I::point(0.125)).err().unwrap().kind,
            "event_resolution"
        );
        let mut failed = accepted.clone();
        assert_eq!(
            failed.propagate_until(0.25).err().unwrap().kind,
            "event_resolution"
        );
        assert_eq!(accepted.certified_end(), 0.0625);
        assert_eq!(accepted.range_bounds(I::point(0.0625)).unwrap(), prefix);
        let mut discarded = accepted.clone();
        discarded.propagate_until(0.125).unwrap();
        let future = discarded.range_bounds(I::point(0.125)).unwrap();
        assert_eq!(discarded.range_bounds(I::point(0.0625)).unwrap(), prefix);
        assert!(!accepted.same_history(&discarded));
        drop(discarded);
        let mut retry = accepted.clone();
        retry.propagate_until(0.125).unwrap();
        assert_eq!(retry.range_bounds(I::point(0.125)).unwrap(), future);
        let mut uninterrupted = scalar(-1.0);
        uninterrupted.propagate_until(0.125).unwrap();
        // Equal modes and end times do not identify dense history once
        // horizons can split a certified step into different prefixes.
        assert!(!uninterrupted.same_history(&retry));
        // y(1/8)=8/9. Exact products establish containment without
        // blessing the floating-point division as an exact oracle.
        assert!(
            crate::interval::sum_products_sign(&[(future[0].lo, 9.0), (-8.0, 1.0)]).unwrap() <= 0
        );
        assert!(
            crate::interval::sum_products_sign(&[(future[0].hi, 9.0), (-8.0, 1.0)]).unwrap() >= 0
        );
    }

    #[test]
    fn taylor_remainder_encloses_exact_rational_decay_without_query_mutation() {
        let flow = scalar(-1.0);
        let step = flow.trial(0.0, 1.0 / 32.0, &[I::ONE], &[], &[]).unwrap();
        let at_end = step.range(I::point(1.0 / 32.0))[0];
        // Exact real answer is 32/33. Compare exact products, not a rounded
        // division oracle; the enclosure must contain that rational itself.
        assert!(
            crate::interval::sum_products_sign(&[(at_end.lo, 33.0), (-32.0, 1.0)]).unwrap() <= 0
        );
        assert!(
            crate::interval::sum_products_sign(&[(at_end.hi, 33.0), (-32.0, 1.0)]).unwrap() >= 0
        );
        let whole = step.range(I {
            lo: 0.0,
            hi: 1.0 / 32.0,
        })[0];
        assert!(whole.lo <= at_end.lo && whole.hi >= 1.0);
        let _ = step.range(I::point(1.0 / 64.0));
        assert_eq!(step.range(I::point(1.0 / 32.0))[0], at_end);
    }

    #[test]
    fn trajectory_tube_failure_is_rejected_and_initial_uncertainty_survives() {
        let flow = scalar(1.0);
        assert!(flow.trial(0.0, 1.0, &[I::ONE], &[], &[]).is_none());
        let uncertain = I {
            lo: 1.0,
            hi: 1.0 + 1e-10,
        };
        let step = flow.trial(0.0, 1.0 / 32.0, &[uncertain], &[], &[]).unwrap();
        let at_start = step.range(I::ZERO)[0];
        assert!(at_start.lo <= uncertain.lo && at_start.hi >= uncertain.hi);
        let at_end = step.range(I::point(1.0 / 32.0))[0];
        assert!(at_end.hi - at_end.lo >= uncertain.hi - uncertain.lo);
    }

    #[test]
    fn uncertain_restart_encloses_new_flow_across_source_corner_without_mutating_base() {
        use serde_json::json;
        let origin = json!({"source":"window.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"q","kind":"integer","initial":0}],
            "operators":[{"kind":"idt","ic":0,"origin":origin,
                "input":{"op":"multiply","left":{"op":"state","state":0},
                    "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}}}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [0.5, 1.0], [1.0, 0.0]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        let base = NonlinearContinuous::new(
            &program,
            &trajectory,
            &["u".into()],
            &[0.0],
            trajectory.config.stop,
        )
        .unwrap();
        let original = base.range_bounds(I::point(0.75)).unwrap();
        let window = I {
            lo: 0.5 - 1.0 / 1024.0,
            hi: 0.5 + 1.0 / 1024.0,
        };
        // Interior representatives still require a separate timing contract.
        let failure = base
            .restarted(window.lo, window, &[I::point(2.0)], trajectory.config.stop)
            .err()
            .unwrap();
        assert_eq!(failure.kind, "event_resolution");
        assert_eq!(base.range_bounds(I::point(0.75)).unwrap(), original);
        let candidate = base
            .restarted(window.hi, window, &[I::point(2.0)], trajectory.config.stop)
            .unwrap();
        let at_start = candidate.range_bounds(I::point(window.hi)).unwrap()[0];
        // q switches from 0 to 2 at any tau in the window, u is a triangle.
        // At tau=lo, integral(tau..hi) 2*u^2 is exactly numerator/denominator.
        // Including the interior source maximum u(.5)=1 is essential here.
        let numerator = (2_u64 * (1 << 30) - 16 * 511_u64.pow(3)) as f64;
        let denominator = (3_u64 * (1 << 30)) as f64;
        assert!(at_start.lo <= 0.0);
        assert!(
            crate::interval::sum_products_sign(&[(at_start.hi, denominator), (-numerator, 1.0)])
                .unwrap()
                >= 0
        );
        let future = candidate.range_bounds(I::point(0.75)).unwrap();
        assert_eq!(base.range_bounds(I::point(0.75)).unwrap(), original);
        drop(candidate);
        let retry = base
            .restarted(window.hi, window, &[I::point(2.0)], trajectory.config.stop)
            .unwrap();
        assert_eq!(retry.range_bounds(I::point(0.75)).unwrap(), future);
    }
}
