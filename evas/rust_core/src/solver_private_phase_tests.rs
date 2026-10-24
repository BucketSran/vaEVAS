//! Full current domains survive private IR coordinates and phase recertification.
use super::*;
use crate::transition_source_plan::Work;
fn fixture() -> (Circuit, Solution, Work, crate::ir::Origin) {
    let p: Program =
        serde_json::from_str(include_str!("../tests/fixtures/ir33_private_phase.json")).unwrap();
    let work = Work::default();
    let proofs = crate::event_value_proof::Proofs::new();
    let context = crate::event_value_proof::Context::candidate_frame(
        &proofs,
        p.nodes.len(),
        &[],
        &[0.25],
        &work,
    )
    .unwrap()
    .try_with_operators(&[I { lo: 0.2, hi: 0.3 }])
    .unwrap();
    let plan = Arc::new(
        crate::procedure::execute(
            &p,
            &[],
            &[I::ZERO, I { lo: 0.4, hi: 0.6 }],
            &[],
            Some(&context),
            &work,
        )
        .unwrap(),
    );
    let circuit = plan
        .circuit(
            &p,
            &[],
            &[],
            &[0.25],
            Tolerances {
                absolute: 1.,
                relative: 0.,
            },
            &work,
        )
        .unwrap();
    let solution = Solution {
        voltages: vec![0., 0.5],
        certified_voltage_bounds: Some(vec![[0., 0.], [0.4, 0.6]]),
        max_residual_v: 0.,
        max_residual_ratio: 0.,
        max_scaled_residual_ratio: None,
        max_voltage_correction_v: None,
        max_voltage_correction_ratio: None,
    };
    (circuit, solution, work, p.contributions[0].origin.clone())
}
fn rows(origin: &crate::ir::Origin) -> Vec<ForcingRow> {
    vec![(
        1,
        0,
        1,
        -0.125,
        0.125,
        I::point(0.125),
        Expression::Affine {
            constant: -0.125,
            terms: vec![],
        },
        origin.clone(),
    )]
}
#[test]
fn private_forcing_coordinates_use_latest_operator_box_and_phase_residual_certificate() {
    let (mut circuit, mut solution, _work, origin) = fixture();
    assert!(circuit.nodes.len() > solution.voltages.len());
    circuit
        .install_forcing_phase(
            1,
            0.,
            &mut solution,
            rows(&origin),
            &[I { lo: 0.2, hi: 0.3 }],
            true,
        )
        .unwrap();
    assert_eq!(solution.voltages, [0., 0.625]);
    assert_eq!(
        circuit
            .forcing_legacy_voltage_view(1, 0., &solution.voltages, &[1])
            .unwrap(),
        [0., 0.5]
    );
    // The final history certificate widened after extension. It certifies the
    // reduced relation 2*u before the physical 1/8 source is projected again.
    solution.certified_voltage_bounds = Some(vec![[0., 0.], [0.25, 0.75]]);
    circuit
        .install_forcing_phase(
            1,
            0.,
            &mut solution,
            rows(&origin),
            &[I {
                lo: 0.125,
                hi: 0.375,
            }],
            true,
        )
        .unwrap();
    assert_eq!(solution.voltages, [0., 0.625]);
    let bound = solution.certified_voltage_bounds.as_ref().unwrap()[1];
    assert!(bound[0] <= 0.375 && bound[1] >= 0.875);
    let view = circuit.procedure_view().unwrap();
    let points = view.expand(&solution.voltages).unwrap();
    let private = view
        .expand_bounds(
            &[
                I::ZERO,
                I {
                    lo: bound[0],
                    hi: bound[1],
                },
            ],
            &points,
            &[I {
                lo: 0.125,
                hi: 0.375,
            }],
        )
        .unwrap();
    let matching = points
        .iter()
        .enumerate()
        .skip(view.node_count)
        .filter(|(_, v)| v.abs() == 0.5)
        .collect::<Vec<_>>();
    assert!(!matching.is_empty());
    for (i, point) in matching {
        let expected = if *point > 0. {
            (0.25, 0.75)
        } else {
            (-0.75, -0.25)
        };
        assert!(private[i].lo <= expected.0 && private[i].hi >= expected.1);
    }
    let before = serde_json::to_value(&solution).unwrap();
    let snapshot = circuit.forcing_frame_snapshot();
    circuit
        .install_forcing_phase(
            1,
            0.,
            &mut solution,
            rows(&origin),
            &[I {
                lo: 0.125,
                hi: 0.375,
            }],
            false,
        )
        .unwrap();
    assert_eq!(serde_json::to_value(&solution).unwrap(), before);
    assert_eq!(circuit.forcing_frame_snapshot(), snapshot);
}
#[test]
fn private_forcing_actual_widening_fails_original_tolerance_and_preserves_accepted_candidate() {
    let (circuit, solution, _, origin) = fixture();
    let before = circuit.forcing_frame_snapshot();
    for _ in 0..2 {
        let mut trial = circuit.clone();
        let mut value = solution.clone();
        trial.tolerances.absolute = 0.01;
        let error = trial
            .install_forcing_phase(
                1,
                0.,
                &mut value,
                rows(&origin),
                &[I {
                    lo: 0.125,
                    hi: 0.375,
                }],
                true,
            )
            .unwrap_err();
        assert_eq!(error.kind, "residual_failure");
        assert_eq!(circuit.forcing_frame_snapshot(), before);
        assert_eq!(solution.voltages, [0., 0.5]);
    }
}
#[test]
fn private_forcing_expansion_keeps_original_exhausted_owner_across_retries() {
    let (circuit, solution, work, origin) = fixture();
    let before = circuit.forcing_frame_snapshot();
    work.debit(2, 1_000_000_000 - work.spent()).unwrap();
    for _ in 0..2 {
        let mut trial = circuit.clone();
        let mut value = solution.clone();
        assert_eq!(
            trial
                .install_forcing_phase(1, 0., &mut value, rows(&origin), &[I::point(0.25)], true)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(circuit.forcing_frame_snapshot(), before);
    }
    let (mut fresh, mut value, _, origin) = fixture();
    fresh
        .install_forcing_phase(
            1,
            0.,
            &mut value,
            rows(&origin),
            &[I { lo: 0.2, hi: 0.3 }],
            true,
        )
        .unwrap();
}
