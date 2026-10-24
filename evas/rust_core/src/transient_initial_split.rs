//! Initial gate before cold histories; certified identity zero timers remain
//! ordinary transactions. This is a sufficient scope proof, never execution
//! or removal of a zero-timer body or of its effects/conditions.
use super::*;
use crate::ir::{ProcedureAction, ProcedureControl};

fn self_copy(e: &Expression, state: usize, model: &EventModel) -> Result<bool, Error> {
    cold_charge(model, 1)?;
    match e {
        Expression::State { state: read } => Ok(*read == state),
        // A stored program State is already binary64. These boundaries are
        // identity only on that direct stored value: no arithmetic is erased.
        Expression::RealBoundary { value, .. } => self_copy(value, state, model),
        _ => Ok(false),
    }
}

fn neutral_body(
    body: &[Statement],
    seeds: &BTreeSet<usize>,
    model: &EventModel,
) -> Result<bool, Error> {
    for statement in body {
        cold_charge(model, usize::BITS as usize + 1)?;
        match statement {
            Statement::Assign(a) => {
                if seeds.contains(&a.state) && !self_copy(&a.rhs, a.state, model)? {
                    return Ok(false);
                }
            }
            Statement::If {
                then_body,
                else_body,
                ..
            } => {
                if !neutral_body(then_body, seeds, model)?
                    || !neutral_body(else_body, seeds, model)?
                {
                    return Ok(false);
                }
            }
            Statement::Display { .. } => {}
            // Unknown or indexed writers do not gain this sufficient proof.
            Statement::ArrayWrite { .. } | Statement::Loop { .. } => return Ok(false),
        }
    }
    Ok(true)
}

pub(super) fn prepare(
    model: &EventModel,
    trajectory: &Trajectory,
    initial_ids: &[usize],
    initial_blocks: &[usize],
) -> Result<Option<Prepared>, Error> {
    if model.program.procedures.is_empty() || initial_blocks.is_empty() {
        return Ok(None);
    }
    cold_charge(model, 0)?;
    // A true source band belongs to the existing bounded bootstrap route.
    // Decide before executing initial effects; never retry an executed gate.
    cold_charge(
        model,
        model.driven.len().saturating_mul(3).saturating_add(8),
    )?;
    if trajectory
        .value_bounds(0.)
        .iter()
        .any(|b| !b.finite() || b.lo.to_bits() != b.hi.to_bits())
    {
        return Ok(None);
    }
    for &block in initial_blocks {
        cold_charge(model, 1)?;
        for statement in &model.program.events[block].body {
            cold_charge(model, 1)?;
            if !matches!(statement, Statement::Assign(_)) {
                return Ok(None); // Retain existing display/control qualification.
            }
        }
    }
    // Whole-procedure writers matter, not merely each event's compat view.
    // Exclude ordinary stores/aliases/loops and duplicate gates. Thus every
    // possible earlier t=0 seed writer is covered by neutral_body below.
    let mut gates = BTreeSet::new();
    for procedure in &model.program.procedures {
        cold_charge(model, 1)?;
        for step in &procedure.body {
            cold_charge(model, 1)?;
            match &step.action {
                ProcedureAction::Control(ProcedureControl::EventGate { event }) => {
                    cold_charge(model, usize::BITS as usize * (gates.len() + 1) + 8)?;
                    if !gates.insert(*event) {
                        return Ok(None);
                    }
                }
                ProcedureAction::Control(ProcedureControl::ContributionCapture { .. }) => {}
                _ => return Ok(None),
            }
        }
    }
    for &block in initial_blocks {
        cold_charge(model, usize::BITS as usize)?;
        if !gates.contains(&block) {
            return Ok(None);
        }
    }
    let mut seeds = BTreeSet::new();
    for spec in &model.program.operators {
        cold_charge(model, 8)?;
        if let OperatorSpec::Transition { input, origin, .. } = spec {
            let Expression::State { state } = input else {
                return Ok(None);
            };
            let Some(s) = model.program.states.get(*state) else {
                return Ok(None);
            };
            cold_charge(
                model,
                s.instance.len().saturating_add(origin.instance.len()),
            )?;
            let Some(state) = crate::operators::bare_real_transition_state(spec, &model.program)
            else {
                return Ok(None);
            };
            cold_charge(model, usize::BITS as usize * (seeds.len() + 1) + 8)?;
            seeds.insert(state);
        }
    }
    let mut possible = BTreeSet::new();
    for leaf in &model.triggers {
        cold_charge(model, 1)?;
        let at_zero = match &leaf.trigger {
            EventTrigger::InitialStep { .. } => false,
            EventTrigger::Timer { start, enabled, .. } => *enabled && *start <= 0.,
            // This deliberately includes future/disabled/unknown held clocks.
            // No clock is guessed and none is consumed by this proof.
            EventTrigger::HeldTimer { .. } => true,
            _ if seeds.is_empty() => false,
            _ => return Ok(None),
        };
        if at_zero {
            cold_charge(
                model,
                initial_blocks.len() + usize::BITS as usize * (possible.len() + 1) + 8,
            )?;
            if initial_blocks.contains(&leaf.event) {
                return Ok(None);
            } // OR is not two stages.
            possible.insert(leaf.event);
        }
    }
    for block in possible {
        cold_charge(model, usize::BITS as usize)?;
        if !gates.contains(&block)
            || !neutral_body(&model.program.events[block].body, &seeds, model)?
        {
            return Ok(None);
        }
    }
    // This induction is deliberately syntactic: no writer to any required
    // seed can change it (in either branch), and no ordinary writer exists.
    // Other RHS/guards remain in the actual normal t=0 transaction, where
    // their complete source frames, integer checks and effects must execute.
    for &block in initial_blocks {
        cold_charge(model, model.source_copy_items)?;
        let event = &model.program.events[block];
        check_body(&event.body, model, &event.origin.instance)?;
    }
    cold_charge(
        model,
        model
            .program
            .states
            .len()
            .saturating_mul(8 + std::mem::size_of::<I>()),
    )?;
    let before = model.initial();
    let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
    let mut mixed = MixedCold {
        original_points: BTreeSet::new(),
        allowed: false,
        qualified: None,
    };
    let (states, bounds, records) = prepare_stage(
        model,
        trajectory,
        initial_blocks,
        initial_ids,
        &before,
        &bounds,
        &mut mixed,
    )?;
    cold_charge(model, states.len().saturating_mul(4).saturating_add(8))?;
    if states.len() != model.program.states.len()
        || bounds.len() != states.len()
        || states.iter().zip(&bounds).any(|(v, b)| {
            !v.is_finite()
                || !b.finite()
                || b.lo.to_bits() != v.to_bits()
                || b.hi.to_bits() != v.to_bits()
        })
    {
        return Err(Error::new("initialization_precision", "initial-only cold construction requires the complete stored state domain to be a binary64 point"));
    }
    Ok(Some(Prepared {
        states,
        bounds,
        records,
        deferred_zero: true,
        bounded_held_transition_seeds: false,
        source_context: model.source_context.clone(),
        future: None,
        zero: BTreeSet::new(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request() -> Request {
        serde_json::from_str(include_str!(
            "../tests/fixtures/initial_split_lifecycle.request.json"
        ))
        .unwrap()
    }
    fn trajectory(value: f64) -> Trajectory {
        let mut r = request();
        let mut t = r.transient.take().unwrap();
        t.pwl[0] = vec![[0., value], [1., value]];
        Trajectory::new(t, r.driven.len()).unwrap()
    }
    fn model() -> EventModel {
        let r = request();
        let t = trajectory(0.);
        EventModel::new_with_trajectory(r.program, r.driven, r.tolerances, Some(&t)).unwrap()
    }
    fn controller(m: &EventModel, t: &Trajectory) -> (Controller, Vec<ScheduledEvent>) {
        let p = super::super::prepare(m, t).unwrap().unwrap();
        assert!(p.deferred_zero);
        assert_eq!(p.states, vec![1., 0., 0.]);
        assert_eq!(p.records.len(), 1);
        let ops = Operators::new_until_with_source_context(
            &m.program,
            t,
            &m.driven,
            &p.states,
            1.,
            &m.tolerances,
            m.source_context.clone(),
        )
        .unwrap();
        let circuit = m
            .circuit_at(&p.states, &ops.values(0.).unwrap(), &t.value_bounds(0.))
            .unwrap();
        let solution = circuit.solve(&t.values(0.)).unwrap();
        let q = independent_schedule(m, t).unwrap();
        assert_eq!(p.cursor(&q).unwrap(), 0);
        assert_eq!(q.len(), 2);
        (
            Controller {
                accepted: Frame {
                    states: p.states,
                    state_bounds: p.bounds,
                    operators: ops,
                    circuit,
                    solution,
                    time: 0.,
                    value_proofs: Default::default(),
                    time_proofs: Default::default(),
                },
                event: 0,
                records: p.records,
                outputs: vec![],
            },
            q,
        )
    }
    fn signature(q: &[ScheduledEvent]) -> Vec<(usize, u64, u64, u64)> {
        q.iter()
            .map(|e| {
                (
                    e.event,
                    e.time.to_bits(),
                    e.bounds().lo.to_bits(),
                    e.bounds().hi.to_bits(),
                )
            })
            .collect()
    }
    fn same(a: &Controller, b: &Controller) {
        assert_eq!(a.event, b.event);
        assert_eq!(a.accepted.time, b.accepted.time);
        assert_eq!(a.accepted.states, b.accepted.states);
        assert_eq!(a.accepted.state_bounds, b.accepted.state_bounds);
        assert_eq!(a.accepted.solution.voltages, b.accepted.solution.voltages);
        assert_eq!(
            a.accepted.solution.certified_voltage_bounds,
            b.accepted.solution.certified_voltage_bounds
        );
        assert_eq!(a.accepted.value_proofs, b.accepted.value_proofs);
        assert_eq!(a.accepted.time_proofs, b.accepted.time_proofs);
        assert!(a
            .accepted
            .operators
            .same_reset_history(&b.accepted.operators));
        for t in [0., 0.25, 0.5, 1.] {
            assert_eq!(
                a.accepted.operators.values(t).unwrap(),
                b.accepted.operators.values(t).unwrap()
            );
            assert_eq!(
                a.accepted.operators.bounds(t).unwrap(),
                b.accepted.operators.bounds(t).unwrap()
            );
        }
        assert_eq!(
            serde_json::to_value(&a.records).unwrap(),
            serde_json::to_value(&b.records).unwrap()
        );
        assert_eq!(a.outputs.len(), b.outputs.len());
    }
    #[test]
    fn deferred_zero_first_store_failure_keeps_full_controller_and_future_cursor() {
        let m = model();
        let good = trajectory(0.);
        let bad = trajectory(1.);
        let (mut c, mut q) = controller(&m, &good);
        let (before, bq) = controller(&m, &good);
        let owner = crate::real_expression::work(&m);
        assert!(cold_work(&m).same_owner(owner));
        let original = serde_json::to_value(&m.program).unwrap();
        let mut spent = owner.spent();
        for _ in 0..2 {
            let err = c
                .accept_changed_events(&m, &bad, &mut q, event_acceptance::Strategy::Static)
                .unwrap_err();
            assert_eq!(err.kind, "integer_range");
            same(&c, &before);
            assert_eq!(signature(&q), signature(&bq));
            assert_eq!(serde_json::to_value(&m.program).unwrap(), original);
            assert!(owner.spent() > spent);
            spent = owner.spent();
        }
        for _ in 0..2 {
            c.accept_changed_events(&m, &good, &mut q, event_acceptance::Strategy::Static)
                .unwrap();
        }
        assert_eq!(c.event, 2);
        assert_eq!(c.accepted.states, vec![1., 3., 0.]);
        assert_eq!(
            c.records.iter().map(|r| r.time).collect::<Vec<_>>(),
            vec![0., 0., 0.5]
        );
        let clean = model();
        let (mut c2, mut q2) = controller(&clean, &good);
        for _ in 0..2 {
            c2.accept_changed_events(&clean, &good, &mut q2, event_acceptance::Strategy::Static)
                .unwrap();
        }
        same(&c, &c2);
        assert_eq!(signature(&q), signature(&q2));
    }
    #[test]
    fn true_initial_input_band_defers_before_any_initial_execution() {
        let m = model();
        let r = request();
        let mut raw = serde_json::to_value(r.transient.unwrap()).unwrap();
        raw["pwl_errors_V"] = serde_json::json!([0.125]);
        let t = Trajectory::new(serde_json::from_value(raw).unwrap(), 1).unwrap();
        let ids = m
            .triggers
            .iter()
            .enumerate()
            .filter_map(|(i, e)| matches!(e.trigger, EventTrigger::InitialStep { .. }).then_some(i))
            .collect::<Vec<_>>();
        let blocks = ids.iter().map(|i| m.triggers[*i].event).collect::<Vec<_>>();
        let original = serde_json::to_value(&m.program).unwrap();
        assert!(super::prepare(&m, &t, &ids, &blocks).unwrap().is_none());
        assert_eq!(m.initial(), vec![0., 0., 0.]);
        assert_eq!(serde_json::to_value(&m.program).unwrap(), original);
    }
    #[test]
    fn initialization_same_original_default_work_exhaustion_is_sticky() {
        let m = model();
        let t = trajectory(0.);
        let owner = cold_work(&m).clone();
        assert!(owner.same_owner(crate::real_expression::work(&m)));
        let original = serde_json::to_value(&m.program).unwrap();
        let mut attempts = 0;
        loop {
            match super::super::prepare(&m, &t) {
                Ok(Some(p)) => {
                    assert!(p.deferred_zero);
                    assert_eq!(p.states, vec![1., 0., 0.]);
                    attempts += 1;
                }
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
                _ => panic!("split lost"),
            }
        }
        assert!(attempts > 1);
        assert!(owner.spent() >= 1_000_000_000);
        for _ in 0..2 {
            assert_eq!(
                super::super::prepare(&m, &t).err().unwrap().kind,
                "step_budget"
            );
            assert!(cold_work(&m).same_owner(&owner));
            assert_eq!(serde_json::to_value(&m.program).unwrap(), original);
        }
        let fresh = model();
        assert!(super::super::prepare(&fresh, &t).unwrap().is_some());
        eprintln!(
            "initial split natural attempts={attempts} spent={}",
            owner.spent()
        );
    }
}
