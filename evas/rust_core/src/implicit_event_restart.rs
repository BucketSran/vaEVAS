//! A finite bridge to the shared fixed-timer calendar and state settlement.
//! This controller alone owns accepted parameters, physical history and records.
//! EventModel/settlement remain stateless candidate evaluators; no second commit.
use super::*;
use crate::events::EventModel;
use crate::ir::{DisplayRecord, EventRecord, EventTrigger, Statement};
use crate::schedule::{independent_schedule, ScheduledEvent};
use std::cell::Cell;

fn unsupported_event(message: &str) -> Error {
    Error::new("unsupported_implicit_dynamics", message)
}

// Complete structural traversal, including unselected arms and zero terms.
// The bridge does not turn a physical event into a passive numeric observer.
fn state_only(expr: &Expression) -> Result<(), Error> {
    match expr {
        Expression::Affine { terms, .. } if terms.is_empty() => Ok(()),
        Expression::State { .. } => Ok(()),
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            state_only(left)?;
            state_only(right)
        }
        _ => Err(unsupported_event("implicit timer bodies require affine held-state expressions; physical reads remain unsupported")),
    }
}
fn body_supported(body: &[Statement]) -> Result<(), Error> {
    for statement in body {
        match statement {
            Statement::ArrayWrite { .. } | Statement::Loop { .. } => {
                return Err(unsupported_event(
                    "implicit timer bodies do not execute runtime array writes or loops",
                ))
            }
            Statement::Assign(a) => state_only(&a.rhs)?,
            Statement::Display { args, .. } => {
                for a in args {
                    state_only(a)?;
                }
            }
            Statement::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } => {
                state_only(left)?;
                state_only(right)?;
                body_supported(then_body)?;
                body_supported(else_body)?;
            }
        }
    }
    Ok(())
}
fn freeze(expr: &Expression, parameters: &[I]) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::State { state } => {
            let value = parameters
                .get(*state)
                .ok_or_else(|| Error::new("invalid_ir", "implicit parameter index"))?;
            if !value.finite() || value.lo != value.hi {
                return Err(unsupported_event(
                    "implicit restart requires certified point held parameters",
                ));
            }
            Expression::Affine {
                constant: value.lo,
                terms: vec![],
            }
        }
        Expression::Affine { .. } | Expression::Operator { .. } => expr.clone(),
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(freeze(left, parameters)?),
            right: Box::new(freeze(right, parameters)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(freeze(left, parameters)?),
            right: Box::new(freeze(right, parameters)?),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(freeze(left, parameters)?),
            right: Box::new(freeze(right, parameters)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(freeze(base, parameters)?),
            exponent: *exponent,
        },
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => Expression::Select {
            relation: *relation,
            left: Box::new(freeze(left, parameters)?),
            right: Box::new(freeze(right, parameters)?),
            then_value: Box::new(freeze(then_value, parameters)?),
            else_value: Box::new(freeze(else_value, parameters)?),
            origin: origin.clone(),
        },
        _ => {
            return Err(unsupported_event(
                "unsupported expression in implicit held-parameter mode",
            ))
        }
    })
}
fn frozen_program(program: &Program, parameters: &[I]) -> Result<Program, Error> {
    let mut frozen = program.clone();
    for c in &mut frozen.contributions {
        c.rhs = freeze(&c.rhs, parameters)?;
    }
    for op in &mut frozen.operators {
        match op {
            OperatorSpec::Idt {
                input, reset: None, ..
            }
            | OperatorSpec::LaplaceNd { input, .. } => *input = freeze(input, parameters)?,
            _ => return Err(unsupported_event(
                "implicit event restarts support unreset integral/proper filter physical states",
            )),
        }
    }
    for bound in &mut frozen.step_bounds {
        bound.value = freeze(&bound.value, parameters)?;
        bound.active = freeze(&bound.active, parameters)?;
    }
    frozen.events.clear();
    frozen.states.clear();
    Ok(frozen)
}

struct Adapter {
    original: Program,
    driven: Vec<String>,
    tolerances: Tolerances,
    model: EventModel,
    calendar: Vec<ScheduledEvent>,
}
impl Adapter {
    fn new(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: &Trajectory,
    ) -> Result<Self, Error> {
        // Validate original references before substituting held parameters.
        let _ = crate::step_bounds::Bounds::new(&program)?;
        for op in &program.operators {
            match op {
                OperatorSpec::Idt { input, .. } | OperatorSpec::LaplaceNd { input, .. } => {
                    validate(input, &program, &op.origin().instance)?
                }
                _ => {
                    return Err(unsupported_event(
                        "implicit event physical operator is unsupported",
                    ))
                }
            }
        }
        for c in &program.contributions {
            let (_, states, _) = integral_dependency_edges(&c.rhs, &program, &c.origin.instance)?;
            if !states.is_empty() {
                return Err(unsupported_event("implicit event parameter changes algebraic constraints; branch reselection is not implemented"));
            }
        }
        for op in &program.operators {
            if let OperatorSpec::LaplaceNd {
                input,
                numerator,
                denominator,
                origin,
            } = op
            {
                let filter = laplace_system(numerator, denominator, origin)?;
                if !filter.d.zero()
                    && !integral_dependency_edges(input, &program, &origin.instance)?
                        .1
                        .is_empty()
                {
                    return Err(unsupported_event("implicit event parameter changes algebraic feedthrough; branch reselection is not implemented"));
                }
            }
        }
        for event in &program.events {
            if !matches!(event.trigger, EventTrigger::Timer { .. }) {
                return Err(unsupported_event("implicit event restart currently requires fixed timers; cross, held and nonpoint windows remain unsupported"));
            }
            body_supported(&event.body)?;
        }
        // Project only the discrete map after proving no body can read any
        // removed physical column. Shared EventModel validates state identities,
        // all predicates, writers and display format/origin without a fake DAE.
        let mut discrete = program.clone();
        discrete.nodes = vec!["0".into()];
        discrete.contributions.clear();
        discrete.operators.clear();
        discrete.step_bounds.clear();
        let mut model = EventModel::new(discrete, vec![], tolerances.clone())?;
        // Removing physical consumers must not erase their timer assignments.
        // This bridge has one shared affine settlement channel, not a second
        // passive-observer pass. All bodies were audited as state-only above.
        model.conditions = crate::event_conditions::Conditions::new_with_numeric(
            &model.program,
            &vec![false; model.program.events.len()],
        )?;
        model.conditions.prepare(&model.program, &model.driven)?;
        model.passive_events.fill(false);
        let clock_trajectory = Trajectory::new(trajectory.config.clone(), driven.len())?;
        // Calendar inputs are unused: the selected fixed timers have no guards.
        let calendar = independent_schedule(&model, &clock_trajectory)?;
        for event in &calendar {
            if event.bounds() != I::point(event.time) {
                return Err(unsupported_event(
                    "implicit event restart requires an exactly representable timer instant",
                ));
            }
        }
        Ok(Self {
            original: program,
            driven,
            tolerances,
            model,
            calendar,
        })
    }
    fn horizon(&self, cursor: usize, trajectory: &Trajectory) -> f64 {
        self.calendar
            .get(cursor)
            .map_or(trajectory.config.stop, |e| e.time)
    }
}

struct Controller {
    parameters: Vec<f64>,
    parameter_bounds: Vec<I>,
    frozen: Program,
    flow: NonlinearContinuous,
    coordinates: Coordinates,
    cursor: usize,
    records: Vec<EventRecord>,
    displays: Vec<DisplayRecord>,
    work: usize,
    // Resource attempts are monotone even when a physical candidate rolls back.
    remaining_work: Cell<usize>,
}
struct Candidate {
    parameters: Vec<f64>,
    parameter_bounds: Vec<I>,
    frozen: Program,
    flow: NonlinearContinuous,
    coordinates: Coordinates,
    cursor: usize,
    records: Vec<EventRecord>,
    displays: Vec<DisplayRecord>,
}
impl Controller {
    fn new(adapter: &Adapter, trajectory: &Trajectory) -> Result<Self, Error> {
        let parameters = adapter.model.initial();
        let parameter_bounds = parameters.iter().copied().map(I::point).collect::<Vec<_>>();
        let frozen = frozen_program(&adapter.original, &parameter_bounds)?;
        let mut remaining_work = MAX_STEPS + trajectory.config.strobetimes.len();
        let (flow, coordinates) = build_segment(
            &frozen,
            trajectory,
            &adapter.driven,
            &adapter.tolerances,
            None,
            adapter.horizon(0, trajectory),
            Some(&mut remaining_work),
        )?;
        let work = flow.steps.len();
        Ok(Self {
            parameters,
            parameter_bounds,
            frozen,
            flow,
            coordinates,
            cursor: 0,
            records: vec![],
            displays: vec![],
            work,
            remaining_work: Cell::new(remaining_work),
        })
    }
    fn prepare(&self, adapter: &Adapter, trajectory: &Trajectory) -> Result<Candidate, Error> {
        let time = adapter.calendar[self.cursor].time;
        let mut end = self.cursor + 1;
        while end < adapter.calendar.len() && adapter.calendar[end].time == time {
            end += 1;
        }
        let batch = &adapter.calendar[self.cursor..end];
        if crate::schedule::common_root(batch).is_none() {
            return Err(unsupported_event(
                "implicit same-time timers lack a common exact identity",
            ));
        }
        let events = batch
            .iter()
            .map(|e| adapter.model.triggers[e.event].event)
            .collect::<Vec<_>>();
        let prepared = crate::settlement::prepare(
            &adapter.model,
            &events,
            (&[], &[]),
            &self.parameters,
            &[],
            &self.parameter_bounds,
            &[],
            None,
        )?;
        let selection =
            adapter
                .model
                .conditions
                .select_at_roots(&events, &[], &[], &self.parameter_bounds)?;
        let (parameters, displays) = adapter.model.apply_with_displays(
            &selection,
            &prepared.solution.voltages,
            &self.parameters,
            time,
        )?;
        if parameters != prepared.states {
            return Err(Error::new(
                "event_consistency",
                "implicit discrete replay changed state",
            ));
        }
        let frozen = frozen_program(&adapter.original, &prepared.bounds)?;
        // This finite bridge never reselects a different algebraic branch.
        if serde_json::to_value(&frozen.contributions).unwrap()
            != serde_json::to_value(&self.frozen.contributions).unwrap()
        {
            return Err(unsupported_event(
                "implicit algebraic constraints changed across timer",
            ));
        }
        let seed = self.flow.state_bounds(I::point(time))?;
        let mut remaining = self.remaining_work.get();
        let result = build_segment(
            &frozen,
            trajectory,
            &adapter.driven,
            &adapter.tolerances,
            Some((time, seed)),
            adapter.horizon(end, trajectory),
            Some(&mut remaining),
        );
        self.remaining_work.set(remaining);
        let (flow, coordinates) = result?;
        let records = events
            .iter()
            .map(|&event| EventRecord {
                time,
                observation_time_bounds: None,
                event,
                origin: adapter.model.program.events[event].origin.label(),
                kind: "timer",
                guard_value: None,
                fired_triggers: vec![],
                before: self.parameters.clone(),
                after: parameters.clone(),
                display_records: displays
                    .iter()
                    .filter(|r| r.event == event)
                    .cloned()
                    .collect(),
            })
            .collect();
        Ok(Candidate {
            parameters,
            parameter_bounds: prepared.bounds,
            frozen,
            flow,
            coordinates,
            cursor: end,
            records,
            displays,
        })
    }
    fn commit(&mut self, candidate: Candidate) {
        self.work += candidate.flow.steps.len();
        self.parameters = candidate.parameters;
        self.parameter_bounds = candidate.parameter_bounds;
        self.frozen = candidate.frozen;
        self.flow = candidate.flow;
        self.coordinates = candidate.coordinates;
        self.cursor = candidate.cursor;
        self.records.extend(candidate.records);
        self.displays.extend(candidate.displays);
    }
    fn observe(
        &self,
        adapter: &Adapter,
        trajectory: &Trajectory,
        time: f64,
    ) -> Result<Solution, Error> {
        observe(
            &self.frozen,
            &adapter.driven,
            &self.coordinates,
            &self.flow.state_bounds(I::point(time))?,
            &trajectory.values(time),
            &trajectory.value_bounds(time),
            &adapter.tolerances,
        )
    }
}

pub(super) fn run(
    program: Program,
    driven: Vec<String>,
    config: TransientInputs,
    tolerances: Tolerances,
) -> Result<Response, Error> {
    let trajectory = Trajectory::new(config, driven.len())?;
    let adapter = Adapter::new(program, driven, tolerances, &trajectory)?;
    let mut controller = Controller::new(&adapter, &trajectory)?;
    let mut solutions = Vec::new();
    let mut states = Vec::new();
    for &time in &trajectory.config.output_times {
        while controller.cursor < adapter.calendar.len()
            && adapter.calendar[controller.cursor].time <= time
        {
            let candidate = controller.prepare(&adapter, &trajectory)?;
            controller.commit(candidate);
        }
        solutions.push(controller.observe(&adapter, &trajectory, time)?);
        states.push(controller.parameters.clone());
    }
    // Execute every remaining event even if no output was requested at stop.
    while controller.cursor < adapter.calendar.len() {
        let candidate = controller.prepare(&adapter, &trajectory)?;
        controller.commit(candidate);
    }
    let trace = TransientTrace {
        display_records: controller.displays,
        times: trajectory.config.output_times.clone(),
        state_names: adapter
            .original
            .states
            .iter()
            .map(|s| format!("{}:{}", s.instance, s.name))
            .collect(),
        states,
        events: controller.records,
        accepted_steps: controller.work,
        discarded_trials: 0,
    };
    let evidence = crate::observation::evidence(
        &adapter.original.nodes,
        &solutions,
        &trajectory.config,
        &adapter.tolerances,
        vec!["implicit_history_evaluation"; solutions.len()],
        true,
        (trace.times.first() == Some(&0.)).then_some(true),
    );
    Ok(Response {
        strobe_evidence: None,
        portability_advisories: None,
        observation_evidence: Some(evidence),
        engine: concat!("evas-implicit-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: crate::ir::SCHEMA_VERSION,
        nodes: adapter.original.nodes,
        solutions,
        transient: Some(trace),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn runtime_loop_and_array_write_stay_outside_implicit_bridge_even_in_dead_arm() {
        let (program, _) = fixture();
        let origin = program.events[0].origin.clone();
        let c = |value| json!({"op":"affine","constant":value,"terms":[]});
        let array = json!({"kind":"array_write","states":[0],"index":c(0.),"first":0,"last":0,"rhs":c(1.),"origin":origin});
        let looping = json!({"kind":"loop","initialize":[{"kind":"assign","state":0,"rhs":c(0.)}],"relation":"lt","left":{"op":"state","state":0},"right":c(1.),"body":[],"update":[{"kind":"assign","state":0,"rhs":c(1.)}],"origin":origin});
        for statement in [array, looping] {
            let guarded: Statement = serde_json::from_value(json!({"kind":"if","relation":"lt","left":c(1.),"right":c(0.),"then_body":[statement],"else_body":[],"origin":origin})).unwrap();
            assert_eq!(
                body_supported(&[guarded]).unwrap_err().kind,
                "unsupported_implicit_dynamics"
            );
        }
    }

    fn fixture() -> (Program, Trajectory) {
        let mut p: Program = serde_json::from_str(include_str!(
            "../../tests/fixtures/implicit-event-restart/program.json"
        ))
        .unwrap();
        // This lifecycle fixture uses the unchanged Program shape. IR32 only
        // adds optional analytic_sources to TransientInputs; this input is PWL.
        // Construct a current test input without rewriting the archived IR31.
        assert_eq!(p.schema_version, 31);
        assert_eq!(crate::ir::SCHEMA_VERSION, 33, "re-audit the fixture");
        // IR33 legacy transport: retain pre-executed numeric seeds.
        // Do not add an initial gate or procedure to this archived input.
        assert!(p.procedures.is_empty());
        assert!(p.real_bindings.is_empty());
        assert!(p.events.iter().all(
            |event| event.procedure_id.is_none() && event.expanded_statement_ordinal.is_none()
        ));
        assert!(p
            .states
            .iter()
            .all(|state| serde_json::to_value(&state.initial).unwrap().is_number()));
        p.schema_version = crate::ir::SCHEMA_VERSION;
        let config = serde_json::from_value(json!({"pwl":[[[0.,0.],[1.,0.]]],"output_times":[0.,0.25,0.5,0.75,1.],"stop":1.,"max_step":1.})).unwrap();
        (p, Trajectory::new(config, 1).unwrap())
    }
    fn adapter(p: Program, trajectory: &Trajectory) -> Adapter {
        Adapter::new(
            p,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-9,
                relative: 1e-9,
            },
            trajectory,
        )
        .unwrap()
    }
    fn display(event: &crate::ir::Event, text: &str) -> Statement {
        Statement::Display {
            format: text.into(),
            args: vec![],
            origin: event.origin.clone(),
        }
    }
    fn serialized<T: serde::Serialize>(value: &T) -> serde_json::Value {
        serde_json::to_value(value).unwrap()
    }

    #[test]
    fn original_physical_coordinates_and_active_mesh_survive_the_timer() {
        let (program, trajectory) = fixture();
        let adapter = adapter(program, &trajectory);
        let mut controller = Controller::new(&adapter, &trajectory).unwrap();
        assert_eq!(controller.flow.certified_end(), 0.5);
        assert!(controller
            .flow
            .steps
            .iter()
            .all(|s| s.end - s.start <= 0.0625));
        let old_seed = controller.flow.state_bounds(I::point(0.5)).unwrap();
        // Physical coordinates come first: z=y+y² and unrelated w=3+t.
        assert!(old_seed[0].lo <= 1.3125 && old_seed[0].hi >= 1.3125);
        assert!(old_seed[1].lo <= 3.5 && old_seed[1].hi >= 3.5);
        let candidate = controller.prepare(&adapter, &trajectory).unwrap();
        assert_eq!(candidate.flow.start, 0.5);
        assert_eq!(candidate.flow.initial, old_seed);
        assert!(candidate
            .flow
            .steps
            .iter()
            .all(|s| s.end - s.start <= 0.03125));
        // Preparation never consumes the accepted event or alters its history.
        assert_eq!(controller.cursor, 0);
        assert_eq!(controller.parameters, [1.]);
        controller.commit(candidate);
        let solution = controller.observe(&adapter, &trajectory, 1.).unwrap();
        let y = adapter
            .original
            .nodes
            .iter()
            .position(|n| n == "y")
            .unwrap();
        let w = adapter
            .original
            .nodes
            .iter()
            .position(|n| n == "w")
            .unwrap();
        assert!((solution.voltages[y] - 1.75).abs() < 1e-8);
        assert!((solution.voltages[w] - 4.).abs() < 1e-8);
    }

    #[test]
    fn late_failure_after_a_warm_commit_rolls_back_display_calendar_and_histories_then_retries() {
        let (mut program, trajectory) = fixture();
        let mut warm = program.events[0].clone();
        warm.trigger = EventTrigger::Timer {
            start: 0.25,
            period: 0.,
            time_tolerance: 1e-12,
            enabled: true,
        };
        if let Statement::Assign(a) = &mut warm.body[0] {
            a.rhs = Expression::Affine {
                constant: 1.,
                terms: vec![],
            };
        }
        warm.body.push(display(&warm, "warm"));
        let committed_display = display(&program.events[0], "committed");
        program.events[0].body.push(committed_display);
        program.events.insert(0, warm);
        // Valid before rate changes: .0625/(2-rate). The late timer maps
        // rate to 2, prepares a display, then fails in future physical mesh.
        program.step_bounds[0].value = serde_json::from_value(json!({"op":"divide", "left":{"op":"affine","constant":0.0625,"terms":[]},
            "right":{"op":"add","left":{"op":"affine","constant":2.,"terms":[]},"right":{"op":"multiply","left":{"op":"affine","constant":-1.,"terms":[]},"right":{"op":"state","state":0}}}})).unwrap();
        let mut adapter = adapter(program, &trajectory);
        let mut controller = Controller::new(&adapter, &trajectory).unwrap();
        controller.commit(controller.prepare(&adapter, &trajectory).unwrap());
        assert_eq!(controller.cursor, 1);
        assert_eq!(controller.displays.len(), 1);
        let old_records = serialized(&controller.records);
        let old_displays = serialized(&controller.displays);
        let old_parameters = controller.parameters.clone();
        let old_bounds = controller.parameter_bounds.clone();
        let old_seed = controller.flow.initial.clone();
        let old_history = controller.flow.steps.clone();
        let old_value = controller
            .observe(&adapter, &trajectory, 0.5)
            .unwrap()
            .voltages;
        let first = controller
            .prepare(&adapter, &trajectory)
            .err()
            .expect("future zero denominator must fail");
        let second = controller
            .prepare(&adapter, &trajectory)
            .err()
            .expect("retry cannot consume failed timer");
        assert_eq!(first.kind, second.kind);
        assert_eq!(controller.cursor, 1);
        assert_eq!(controller.parameters, old_parameters);
        assert_eq!(controller.parameter_bounds, old_bounds);
        assert_eq!(controller.flow.initial, old_seed);
        assert!(Arc::ptr_eq(&controller.flow.steps, &old_history));
        assert_eq!(serialized(&controller.records), old_records);
        assert_eq!(serialized(&controller.displays), old_displays);
        assert_eq!(
            controller
                .observe(&adapter, &trajectory, 0.5)
                .unwrap()
                .voltages,
            old_value
        );
        // Repair only the candidate input control in this same controller.
        adapter.original.step_bounds[0].value = serde_json::from_value(json!({"op":"divide","left":{"op":"affine","constant":0.0625,"terms":[]},"right":{"op":"state","state":0}})).unwrap();
        let candidate = controller.prepare(&adapter, &trajectory).unwrap();
        controller.commit(candidate);
        assert_eq!(controller.cursor, 2);
        assert_eq!(controller.parameters, [2.]);
        assert_eq!(controller.records.len(), 2);
        assert_eq!(
            controller
                .displays
                .iter()
                .map(|r| r.text.as_str())
                .collect::<Vec<_>>(),
            ["warm", "committed"]
        );
        let result = controller.observe(&adapter, &trajectory, 1.).unwrap();
        let y = adapter
            .original
            .nodes
            .iter()
            .position(|n| n == "y")
            .unwrap();
        assert!((result.voltages[y] - 1.75).abs() < 1e-8);
    }

    #[test]
    fn event_restart_cannot_reset_the_shared_candidate_work_budget() {
        let (program, trajectory) = fixture();
        let adapter = adapter(program, &trajectory);
        let controller = Controller::new(&adapter, &trajectory).unwrap();
        controller.remaining_work.set(0);
        assert!(controller.prepare(&adapter, &trajectory).is_err());
        assert_eq!(controller.remaining_work.get(), 0);
        assert_eq!(controller.cursor, 0);
        assert_eq!(controller.parameters, [1.]);
        assert!(controller.records.is_empty());
    }
}
