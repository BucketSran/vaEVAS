//! Production Controller retains the accepted factorized SourceSlew across refusals.
use super::*;
use crate::ir::{Expression, Tolerances};
use serde_json::json;

#[test]
fn factorized_source_slew_two_failed_same_controller_preparations_keep_history() {
    let (mut program, trajectory, driven, _) = crate::transition_source_plan::factor_fixture(15);
    // A nonbinary original coefficient has a real target enclosure. Seed zero
    // is exact, but after the positive-time change high gain must refuse it.
    if let crate::ir::OperatorSpec::Slew {
        input, rise, fall, ..
    } = &mut program.operators[0]
    {
        let Expression::Multiply { left, .. } = input else {
            unreachable!()
        };
        **left = Expression::Affine {
            constant: 0.1,
            terms: vec![],
        };
        *rise = 8.;
        *fall = -8.;
    }
    program.contributions[0].rhs=serde_json::from_value(json!({"op":"multiply","left":{"op":"affine","constant":1e12,"terms":[]},"right":{"op":"operator","operator":0}})).unwrap();
    let model = EventModel::new(
        program,
        driven,
        Tolerances {
            absolute: 1e-8,
            relative: 0.,
        },
    )
    .unwrap();
    let states = vec![];
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&trajectory.values(0.)).unwrap();
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds: vec![],
            solution,
            circuit,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let before = controller.accepted.clone();
    let values = before.operators.values(0.5).unwrap();
    let bounds = before.operators.bounds(0.5).unwrap();
    let breakpoint = before.operators.next_breakpoint(0.);
    let root = crate::exact_source::RootTime::point(0.5).unwrap();
    let (result, retry) =
        crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
            for _ in 0..2 {
                let error = prepare_root_window(
                    &model,
                    &trajectory,
                    &controller.accepted,
                    EventMoment {
                        exact_root: Some(&root),
                        representative: 0.5,
                        observation: I::point(0.5),
                        fired_roots: &[],
                        prediction_end: 1.,
                    },
                    &[],
                )
                .err()
                .expect("amplified true target uncertainty must refuse");
                assert!(
                    matches!(error.kind, "event_accuracy" | "waveform_accuracy"),
                    "{:?}",
                    error
                );
                assert_eq!(controller.accepted.time, before.time);
                assert_eq!(
                    controller.accepted.solution.voltages,
                    before.solution.voltages
                );
                assert_eq!(controller.accepted.states, before.states);
                assert_eq!(controller.accepted.state_bounds, before.state_bounds);
                assert_eq!(controller.accepted.value_proofs, before.value_proofs);
                assert!(controller
                    .accepted
                    .operators
                    .same_reset_history(&before.operators));
                assert_eq!(controller.accepted.operators.values(0.5).unwrap(), values);
                assert_eq!(controller.accepted.operators.bounds(0.5).unwrap(), bounds);
                assert_eq!(
                    controller.accepted.operators.next_breakpoint(0.),
                    breakpoint
                );
                assert_eq!(controller.event, 0);
                assert!(controller.records.is_empty());
                assert!(controller.outputs.is_empty());
                println!("factor_same_controller_refusal={}", error.kind);
            }
            Ok(())
        });
    result.unwrap();
    assert!(!retry.counters.contains_key("source_factor_copy_debit"));
    assert!(!retry.counters.contains_key("source_exact_proof_builds"));
    println!("factor_same_controller_retry_counters={:?}", retry.counters);
}
