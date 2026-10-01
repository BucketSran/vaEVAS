//! Validated polynomial ODE propagation for integral call-site states.
//! A Picard enclosure proves a finite trajectory tube. Order-12 interval Taylor
//! coefficients propagate accepted uncertainty; order 13 over the tube bounds
//! the entire-step remainder. Output queries are immutable dense observations.
use super::*;

const ORDER: usize = 12;
const MAX_STEPS: usize = 16_384;
const TUBE_ATTEMPTS: usize = 16;
type Jet = Vec<I>;

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

#[derive(Clone)]
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
        )
    }

    fn build(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
    ) -> Result<Self, Error> {
        let mut result = Self::initialized(context, parameters, start, restart)?;
        result.propagate()?;
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
        let mut initial = Vec::new();
        let mut event_dependent = false;
        for (i, spec) in program.operators.iter().enumerate() {
            let OperatorSpec::Idt {
                input,
                ic,
                reset,
                origin,
            } = spec
            else {
                return Err(Error::new("unsupported_operator", "nonlinear continuous network currently requires explicit-IC idt operators without filter or derivative operators"));
            };
            validate(input, program, &origin.instance)?;
            if !ic.is_finite() {
                return Err(unsupported(origin, "nonfinite nonlinear integral IC"));
            }
            event_dependent |=
                history_event_dependency(input, program, origin, &driven, &mut BTreeSet::new());
            let held_reset = if let Some(reset) = reset {
                let dependencies = crate::events::affine(reset, program, &origin.instance)?;
                if !dependencies.node_dependencies.is_empty()
                    || !dependencies.operator_dependencies.is_empty()
                {
                    return Err(unsupported(
                        origin,
                        "nonlinear integral reset must depend on event state and constants",
                    ));
                }
                event_dependent = true;
                crate::operators::ResetExpression::new(reset.clone()).active(&parameters)?
            } else {
                false
            };
            initial.push(I::point(*ic));
            let mut structural =
                vec![
                    I::ZERO;
                    program.nodes.len() + program.states.len() + program.operators.len() + 1
                ];
            collect_structure(input, program, &origin.instance, &mut structural)?;
            operators.push(NetworkOperator {
                operator: i,
                kind: ContinuousKind::Idt,
                origin: origin.clone(),
                states: vec![i],
                input: Some(structural),
                laplace: None,
                held_reset,
            });
        }
        if initial.len() + 2 * driven.len() + 1 > 32 {
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
            initial.len(),
            driven.len(),
            &parameters,
        )?;
        let rows = affine_bounds::eliminate(system.rows.clone(), system.x_count, system.width)?;
        let mapping = back_substitute_eliminated(&rows, system.x_count, system.width)?;
        let functions = program
            .operators
            .iter()
            .enumerate()
            .map(|(i, op)| {
                let OperatorSpec::Idt { input, .. } = op else {
                    unreachable!()
                };
                if operators[i].held_reset {
                    Ok(Polynomial::Linear(vec![I::ZERO; system.width]))
                } else {
                    Polynomial::compile(input, program, &system, &mapping)
                }
            })
            .collect::<Result<Vec<_>, _>>()?;
        let mut initial = restart.unwrap_or(initial);
        for (i, op) in operators.iter().enumerate() {
            if op.held_reset {
                let OperatorSpec::Idt { ic, .. } = &program.operators[i] else {
                    unreachable!()
                };
                initial[i] = I::point(*ic);
            }
        }
        Ok(Self {
            context,
            parameters,
            functions,
            initial,
            steps: Vec::new(),
            start,
            event_dependent,
        })
    }

    fn jets(&self, state: &[I], source: &[I], slopes: &[I], order: usize) -> Vec<Jet> {
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
                .functions
                .iter()
                .map(|f| f.jet(&variables, n)[n] / I::point((n + 1) as f64))
                .collect();
            for (variable, value) in variables.iter_mut().zip(derivatives) {
                variable[n + 1] = value;
            }
        }
        variables[..state.len()].to_vec()
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
        let (tube, _) = self.picard_enclosure(state, &source_tube, elapsed)?;
        let coefficients = self.jets(state, source, slopes, ORDER);
        let remainder: Vec<_> = self
            .jets(&tube, &source_tube, slopes, ORDER + 1)
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
        elapsed: I,
    ) -> Option<(Vec<I>, Vec<I>)> {
        let evaluate = |state: &[I]| {
            let variables: Vec<_> = state.iter().chain(source).map(|&v| vec![v]).collect();
            self.functions
                .iter()
                .map(|p| p.jet(&variables, 0)[0])
                .collect::<Vec<_>>()
        };
        let mut derivative = evaluate(initial);
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
            derivative = evaluate(&tube);
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

    fn propagate(&mut self) -> Result<(), Error> {
        let trajectory = &self.context.trajectory;
        let mut state = self.initial.clone();
        let mut knots = vec![self.start];
        knots.extend(trajectory.knots.iter().copied().filter(|t| *t > self.start));
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
            }
        }
        Ok(())
    }

    pub(super) fn operator_value_index(&self, op: usize) -> Option<usize> {
        (op < self.initial.len()).then_some(op)
    }
    pub(super) fn changes_on_event(&self) -> bool {
        self.event_dependent
    }
    pub(super) fn same_history(&self, other: &Self) -> bool {
        self.start == other.start
            && self.initial == other.initial
            && self.parameters == other.parameters
    }
    pub(super) fn next_breakpoint(&self, time: f64) -> Option<f64> {
        self.context
            .trajectory
            .knots
            .iter()
            .copied()
            .find(|t| *t > time)
    }
    pub(super) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        if !time.finite()
            || time.lo < self.start
            || time.hi > self.context.trajectory.config.stop
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
    pub(super) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        let state = self.range_bounds(time)?;
        let source = self.source_bounds(time);
        let variables: Vec<_> = state.iter().chain(&source).map(|&v| vec![v]).collect();
        Ok(self
            .functions
            .iter()
            .map(|p| p.jet(&variables, 0)[0])
            .collect())
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
    pub(super) fn validate_event_window(&self, window: I, events: &[usize]) -> Result<(), Error> {
        if self.event_dependent && window.lo != window.hi {
            // The current settlement certifies samples/conditions at the
            // representative time, not over the event window. Do not extend
            // that certificate to ideal-root parameter values. Check actual
            // firing bodies even when the sampled representative is unchanged.
            for &id in events {
                let event = &self.context.program.events[id];
                if time_sensitive_body(&event.body, &self.context.program, &event.origin.instance)?
                {
                    return Err(Error::new("event_resolution", "uncertain nonlinear restart cannot certify event sampling or input-dependent branches over its time window"));
                }
            }
        }
        Ok(())
    }
    pub(super) fn restarted(&self, time: f64, window: I, parameters: &[I]) -> Result<Self, Error> {
        if !self.event_dependent || self.parameters == parameters {
            return Ok(self.clone());
        }
        if !time.is_finite() || !window.finite() || window.hi != time {
            return Err(Error::new(
                "event_resolution",
                "nonlinear event representative must be the upper endpoint of its time enclosure",
            ));
        }
        let mut next = Self::initialized(
            self.context.clone(),
            parameters.to_vec(),
            time,
            Some(self.range_bounds(window)?),
        )?;
        if window.lo != window.hi {
            let elapsed = I {
                lo: 0.0,
                hi: (I::point(time) - I::point(window.lo)).hi,
            };
            let (_, image) = next
                .picard_enclosure(&next.initial, &self.source_bounds(window), elapsed)
                .ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "cannot certify nonlinear event-to-representative trajectory tube",
                    )
                })?;
            // Include BOTH pre-event history uncertainty and post-event flow.
            // Only reset states were clamped; every other call-site history
            // survives, including all rounding and event-time uncertainty.
            next.initial = image;
        }
        next.propagate()?;
        Ok(next)
    }
}

fn time_sensitive_body(
    body: &[crate::ir::Statement],
    program: &Program,
    owner: &str,
) -> Result<bool, Error> {
    let reads_time = |expr| {
        let dependencies = crate::events::affine(expr, program, owner)?;
        Ok::<_, Error>(
            !dependencies.node_dependencies.is_empty()
                || !dependencies.operator_dependencies.is_empty(),
        )
    };
    for statement in body {
        match statement {
            crate::ir::Statement::Assign(a) if reads_time(&a.rhs)? => return Ok(true),
            crate::ir::Statement::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } if reads_time(left)?
                || reads_time(right)?
                || time_sensitive_body(then_body, program, owner)?
                || time_sensitive_body(else_body, program, owner)? =>
            {
                return Ok(true);
            }
            _ => {}
        }
    }
    Ok(false)
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
            initial: vec![I::ONE],
            steps: vec![],
            start: 0.0,
            event_dependent: false,
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
        let base = NonlinearContinuous::new(&program, &trajectory, &["u".into()], &[0.0]).unwrap();
        let original = base.range_bounds(I::point(0.75)).unwrap();
        let window = I {
            lo: 0.5 - 1.0 / 1024.0,
            hi: 0.5 + 1.0 / 1024.0,
        };
        // Interior representatives still require a separate timing contract.
        let failure = base
            .restarted(window.lo, window, &[I::point(2.0)])
            .err()
            .unwrap();
        assert_eq!(failure.kind, "event_resolution");
        assert_eq!(base.range_bounds(I::point(0.75)).unwrap(), original);
        let candidate = base.restarted(window.hi, window, &[I::point(2.0)]).unwrap();
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
        let retry = base.restarted(window.hi, window, &[I::point(2.0)]).unwrap();
        assert_eq!(retry.range_bounds(I::point(0.75)).unwrap(), future);
    }
}
