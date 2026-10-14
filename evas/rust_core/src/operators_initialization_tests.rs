//! Constructor certificates for an independent continuous graph beside a transition.
//! The fixture is local IR, with no filesystem or frontend dependency.
use super::*;
use serde_json::json;

struct Fixture {
    program: Program,
    trajectory: Trajectory,
    driven: Vec<String>,
    tolerances: Tolerances,
}
impl Fixture {
    fn new() -> Self {
        let origin = |column| json!({"source":"initialization.va","line":1,"column":column,"instance":"dut"});
        let branch = |name: &str| json!({"instance":"dut","local_positive":name,"local_negative":"r","kind":"voltage"});
        let program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","c","u","y","z"],
            "states":[
                {"instance":"dut","name":"q","kind":"real","initial":0.0},
                {"instance":"dut","name":"unused","kind":"real","initial":0.0}
            ],
            "operators":[
                {"kind":"idt","input":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":-1.0}]}},"ic":0.0,"reset":null,"origin":origin(1)},
                {"kind":"transition","input":{"op":"add","left":{"op":"state","state":0},"right":{"op":"select","relation":"gt","left":{"op":"affine","constant":0.0,"terms":[{"node":2,"coefficient":1.0}]},"right":{"op":"affine","constant":0.5,"terms":[]},"then_value":{"op":"affine","constant":1.0,"terms":[]},"else_value":{"op":"affine","constant":0.0,"terms":[]},"origin":origin(2)}},"delay":0.0,"rise":0.125,"fall":0.125,"origin":origin(3)}
            ],
            "contributions":[
                {"branch":branch("c"),"positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(4)},
                {"branch":branch("y"),"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(5)},
                {"branch":branch("z"),"positive":4,"negative":0,"rhs":{"op":"state","state":0},"origin":origin(6)}
            ]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [1.0, 1.0]]],
                output_times: vec![0.0, 0.125, 1.0],
                strobetimes: vec![],
                stop: 1.0,
                max_step: 0.125,
            },
            1,
        )
        .unwrap();
        Self {
            program,
            trajectory,
            driven: vec!["u".into()],
            tolerances: Tolerances::default(),
        }
    }
    fn initialized(&self, states: &[f64], bounds: &[I]) -> Result<(Operators, Operators), Error> {
        Operators::new_initialized_until(
            &self.program,
            &self.trajectory,
            &self.driven,
            states,
            bounds,
            1.0,
            &self.tolerances,
        )
    }
}
const FINAL: [f64; 2] = [1.0, 2.0];
fn final_bounds() -> [I; 2] {
    [I::ONE, I::point(2.0)]
}

#[test]
fn final_certificate_requires_full_finite_point_equal_vectors() {
    let fixture = Fixture::new();
    // Establish that this exact graph is admitted before changing only its certificate.
    fixture.initialized(&FINAL, &final_bounds()).unwrap();
    let shapes = [
        ("empty", vec![], vec![]),
        ("state prefix", vec![1.0], final_bounds().to_vec()),
        ("bound prefix", FINAL.to_vec(), vec![I::ONE]),
        ("both prefixes", vec![1.0], vec![I::ONE]),
        ("extra state", vec![1.0, 2.0, 3.0], final_bounds().to_vec()),
        (
            "extra bound",
            FINAL.to_vec(),
            vec![I::ONE, I::point(2.0), I::point(3.0)],
        ),
    ];
    for (name, states, bounds) in shapes {
        let error = fixture.initialized(&states, &bounds).err().expect(name);
        eprintln!("{name}: {}: {}", error.kind, error.message);
        assert_eq!(error.kind, "unsupported_initial_history", "{name}");
        assert!(
            error.message.contains("full-length"),
            "{name}: {}",
            error.message
        );
    }
    // The unused held slot must be checked too, not just transition dependencies.
    let bad = [
        ("NaN state", [1.0, f64::NAN], final_bounds()),
        (
            "infinite state",
            [1.0, f64::INFINITY],
            [I::ONE, I::point(f64::INFINITY)],
        ),
        ("nonpoint bound", FINAL, [I::ONE, I { lo: 1.0, hi: 2.0 }]),
        ("unequal point", FINAL, [I::ONE, I::point(3.0)]),
        (
            "one ULP unequal point",
            FINAL,
            [I::ONE, I::point(f64::from_bits(2.0_f64.to_bits() + 1))],
        ),
        (
            "NaN bound",
            FINAL,
            [
                I::ONE,
                I {
                    lo: f64::NAN,
                    hi: f64::NAN,
                },
            ],
        ),
        ("infinite bound", FINAL, [I::ONE, I::point(f64::INFINITY)]),
    ];
    for (name, states, bounds) in bad {
        let error = fixture.initialized(&states, &bounds).err().expect(name);
        eprintln!("{name}: {}: {}", error.kind, error.message);
        assert_eq!(error.kind, "unsupported_initial_history", "{name}");
        assert!(
            error.message.contains("finite point"),
            "{name}: {}",
            error.message
        );
    }
}

#[test]
fn retry_uses_final_parameters_and_preserves_ready_source_future_cut() {
    let fixture = Fixture::new();
    let error = fixture
        .initialized(&FINAL, &[I::ONE, I { lo: 1.0, hi: 2.0 }])
        .err()
        .unwrap();
    assert_eq!(error.kind, "unsupported_initial_history");
    let (candidate, replay) = fixture.initialized(&FINAL, &final_bounds()).unwrap();
    let (clean, _) = fixture.initialized(&FINAL, &final_bounds()).unwrap();
    assert!(candidate.same_reset_history(&replay));
    assert_eq!(candidate.values(0.0).unwrap(), vec![0.0, 1.0]);
    assert_eq!(candidate.bounds(0.0).unwrap(), vec![I::ZERO, I::ONE]);
    for time in [0.0, 0.125, 0.5, 0.625, 1.0] {
        assert_eq!(candidate.values(time).unwrap(), clean.values(time).unwrap());
        assert_eq!(candidate.bounds(time).unwrap(), clean.bounds(time).unwrap());
    }
    // q's declaration initial is zero; using final q=1 must rebuild c'=q-c.
    let values = candidate.values(0.125).unwrap();
    assert!((values[0] - (1.0 - (-0.125_f64).exp())).abs() < 1e-12);
    assert_eq!(values[1], 1.0);
    let sources: Vec<_> = candidate
        .entries
        .iter()
        .filter_map(|entry| match entry {
            Runtime::Transition {
                source: Some(source),
                ..
            } => Some(source),
            _ => None,
        })
        .collect();
    assert_eq!(sources.len(), 1);
    assert!(!sources[0].pending_initialization());
    assert_eq!(sources[0].next_after(0.0), Some(0.5));
}

#[test]
fn replay_detects_changed_transition_and_keeps_admission_boundaries() {
    let fixture = Fixture::new();
    let (candidate, mut replay) = fixture.initialized(&FINAL, &final_bounds()).unwrap();
    assert!(candidate.same_reset_history(&replay));
    let continuous = candidate.continuous.as_ref().unwrap();
    assert!(continuous.detached_from_transitions());
    // A real event seed is required to form an anchor; changing q establishes it.
    let event_flow = continuous
        .mapped_event(0.0, I::ZERO, &[I::point(2.0), I::point(2.0)])
        .unwrap();
    assert!(event_flow.detached_from_transitions());
    let anchored = event_flow
        .anchored(
            crate::exact_time::Clock {
                start: 0.0,
                period: 0.0,
                index: 0,
            },
            0.0,
            1.0,
        )
        .unwrap();
    assert!(matches!(anchored, Continuous::Anchored(_)));
    assert!(!anchored.detached_from_transitions());
    let Runtime::Transition { history, .. } = &mut replay.entries[1] else {
        panic!("fixture lost its transition");
    };
    *history = Box::new(Transition::enclosed(9.0, I::point(9.0), 0.0, 0.125, 0.125).unwrap());
    assert!(!candidate.same_reset_history(&replay));

    // Add one y-to-c edge to the otherwise admitted, fully defined model.
    // Even a zero numeric coefficient must retain the forbidden timed edge.
    for coefficient in [1.0, 0.0] {
        let mut feedback = Fixture::new();
        let OperatorSpec::Idt { input, .. } = &mut feedback.program.operators[0] else {
            panic!("fixture lost its integral");
        };
        *input = Expression::Add {
            left: Box::new(input.clone()),
            right: Box::new(Expression::Affine {
                constant: 0.0,
                terms: vec![crate::ir::Term {
                    node: 3,
                    coefficient,
                }],
            }),
        };
        let error = feedback.initialized(&FINAL, &final_bounds()).err().unwrap();
        eprintln!(
            "feedback coefficient {coefficient}: {}: {}",
            error.kind, error.message
        );
        assert_eq!(error.kind, "unsupported_operator");
        assert!(error.message.contains("unsupported dynamic operator"));
    }
}
