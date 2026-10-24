//! Select reachable event-body paths using certified input enclosures.
//! State predicates see accepted state and prior selected assignments; assignments settle jointly
//! with the voltage equations. No accepted simulation history is stored here.
use crate::event_accuracy::GuardBounds;
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, Origin, Program, Relation, Statement};

#[derive(Clone, Default, PartialEq, Eq)]
pub(crate) struct Selection {
    pub(crate) actions: Vec<(usize, Vec<usize>)>,
    pub(crate) ordered_steps: Vec<(usize, Vec<SelectedStep>)>,
    // Retain all predicate reads, including certified alternative arms.
    // An ambiguous equivalent choice records both possible directions.
    pub(crate) decisions: Vec<(usize, bool)>,
    // Group identifiers exist only after one exact occurrence was proved.
    pub(crate) procedure_groups: Vec<Option<usize>>,
    pub(crate) plan: Option<std::sync::Arc<crate::procedure::Plan>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prior_write_invalidates_root_identity_even_when_state_interval_is_unchanged() {
        let origin =
            serde_json::json!({"source":"ordered.va","line":1,"column":1,"instance":"dut"});
        let guard = serde_json::json!({"op":"add",
            "left":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]},
            "right":{"op":"multiply","left":{"op":"affine","constant":-1.0,"terms":[]},
                "right":{"op":"state","state":0}}});
        let mut program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.0}],
            "events":[{"origin":origin,"trigger":{"kind":"cross","guard":guard,
                "direction":1,"time_tolerance":0.001,"expression_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"multiply",
                    "left":{"op":"affine","constant":-1.0,"terms":[]},
                    "right":{"op":"state","state":0}}},
                    {"kind":"if","relation":"gt","left":guard,
                     "right":{"op":"affine","constant":0.0,"terms":[]},
                     "then_body":[],"else_body":[],"origin":origin}]}]
        }))
        .unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".to_string()]).unwrap();
        let noop = conditions
            .select_at_roots(
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
            )
            .unwrap();
        // The unchanged original Program is valid through both-arm equivalence,
        // not through an invalid reuse of the pre-write root identity.
        assert_eq!(noop.decisions, vec![(0, true), (0, false)]);
        let Statement::If {
            then_body,
            else_body,
            ..
        } = &mut program.events[0].body[1]
        else {
            panic!("fixture condition")
        };
        *then_body = serde_json::from_value(serde_json::json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":1.0,"terms":[]}}])).unwrap();
        *else_body = serde_json::from_value(serde_json::json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":2.0,"terms":[]}}])).unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".to_string()]).unwrap();
        let error = conditions
            .select_at_roots(
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
            )
            .err()
            .expect("same interval is not proof that q=-q preserves the old value");
        assert_eq!(error.kind, "event_condition");
    }

    #[test]
    fn post_root_reads_use_certified_sides_and_refuse_an_unsided_zero() {
        let origin = serde_json::json!({"source":"right.va","line":1,"column":1,"instance":"dut"});
        let u = serde_json::json!({"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]});
        let zero = serde_json::json!({"op":"affine","constant":0.0,"terms":[]});
        let assign = |v: f64| serde_json::json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":v,"terms":[]}}]);
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.0}],
            "events":[{"origin":origin,"trigger":{"kind":"cross","guard":u,"direction":0,
                "time_tolerance":0.001,"expression_tolerance":0.001},
                "body":[{"kind":"if","relation":"gt","left":u,"right":zero,
                    "then_body":assign(1.0),"else_body":assign(2.0),"origin":origin}]}]
        }))
        .unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".to_string()]).unwrap();
        let select = |sides: Vec<(usize, i8)>, events: Vec<usize>| {
            let _scope = PostRootSides::install(sides, Vec::new(), events, None);
            conditions
                .select_at_roots(&[0], &[I::ZERO], &[0], &[I::ZERO])
                .map(|selection| selection.decisions)
        };
        // A timer-fired body observes g(t)=0 at its own time.
        assert_eq!(select(vec![], vec![]).unwrap(), vec![(0, false)]);
        // A tau+ body reads the certified side; 0 is a proven plateau.
        assert_eq!(select(vec![(0, 1)], vec![0]).unwrap(), vec![(0, true)]);
        assert_eq!(select(vec![(0, -1)], vec![0]).unwrap(), vec![(0, false)]);
        assert_eq!(select(vec![(0, 0)], vec![0]).unwrap(), vec![(0, false)]);
        // Without one consistent side the exact zero proves nothing at tau+.
        for sides in [vec![], vec![(0, 1), (0, -1)]] {
            assert_eq!(select(sides, vec![0]).unwrap_err().kind, "event_condition");
        }
        // The scope is restored after each batch.
        assert_eq!(post_root_side(0), None);
        assert!(!post_root_event(0));
    }

    #[test]
    fn right_window_proves_a_floor_plateau_but_not_a_straddled_bin() {
        // cross(u) body: q = floor(k*w); if (q < 1) p = 1; else p = 2.
        // At tau, u = w = 0.5; k*w is 1.5 (inside a bin) or 1 (on its edge).
        let origin = serde_json::json!({"source":"window.va","line":1,"column":1,"instance":"dut"});
        let node = |n: usize, k: f64| serde_json::json!({"op":"affine","constant":0.0,"terms":[{"node":n,"coefficient":k}]});
        let constant = |v: f64| serde_json::json!({"op":"affine","constant":v,"terms":[]});
        let assign = |state: usize, rhs: serde_json::Value| serde_json::json!({"kind":"assign","state":state,"rhs":rhs});
        let program = |k: f64| -> Program {
            serde_json::from_value(serde_json::json!({
                "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","w"],"contributions":[],
                "states":[{"instance":"dut","name":"q","kind":"real","initial":0.0},
                          {"instance":"dut","name":"p","kind":"real","initial":0.0}],
                "events":[{"origin":origin,"trigger":{"kind":"cross","guard":node(1, 1.0),"direction":1,
                    "time_tolerance":0.001,"expression_tolerance":0.001},
                    "body":[assign(0, serde_json::json!({"op":"event_math","function":"floor",
                                "args":[node(2, k)],"origin":origin})),
                            {"kind":"if","relation":"lt","left":{"op":"state","state":0},"right":constant(1.0),
                             "then_body":[assign(1, constant(1.0))],"else_body":[assign(1, constant(2.0))],
                             "origin":origin}]}]
            }))
            .unwrap()
        };
        let select = |k: f64, window: Option<I>| {
            let program = program(k);
            let mut conditions = Conditions::new_with_numeric(&program, &[true]).unwrap();
            conditions
                .prepare(&program, &["u".to_string(), "w".to_string()])
                .unwrap();
            let window = window.map(|w| RightWindow {
                inputs: vec![w, w],
                operators: Vec::new(),
            });
            let _scope = PostRootSides::install(vec![(0, 1)], Vec::new(), vec![0], window);
            conditions
                .select_at_roots(&[0], &[I::point(0.5); 2], &[0], &[I::ZERO; 2])
                .map(|selection| selection.decisions)
        };
        let after = I {
            lo: 0.5,
            hi: 0.5 + 1e-7,
        };
        let around = I {
            lo: 0.5 - 1e-7,
            hi: 0.5 + 1e-7,
        };
        // floor(3w) = 1 over either window: q<1 is false just after tau.
        assert_eq!(select(3.0, Some(after)).unwrap(), vec![(0, false)]);
        assert_eq!(select(3.0, Some(around)).unwrap(), vec![(0, false)]);
        // Without a window the moving input proves nothing about q at tau+.
        assert_eq!(select(3.0, None).unwrap_err().kind, "event_condition");
        // floor(2w) stays 1 on a window above its edge; a window meeting bin 0
        // cannot decide q<1 and is refused rather than read from tau.
        assert_eq!(select(2.0, Some(after)).unwrap(), vec![(0, false)]);
        assert_eq!(
            select(2.0, Some(around)).unwrap_err().kind,
            "event_condition"
        );
    }

    #[test]
    fn empty_and_inactive_selections_preserve_results_but_reject_unknown_indices() {
        let origin = serde_json::json!({"source":"empty.va","line":1,"column":1,"instance":"M"});
        let program:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"M","name":"q","kind":"real","initial":0}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},
                "body":[{"kind":"if","relation":"gt","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[]},
                    "then_body":[],"else_body":[],"origin":origin}]}]
        })).unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".into()]).unwrap();
        // No reachable event used these inputs/bounds before the optimization.
        assert!(conditions.select_at_roots(&[], &[], &[], &[]).unwrap() == Selection::default());
        conditions.restrict_events(&[false]);
        assert!(conditions.select_at_roots(&[0], &[], &[], &[]).unwrap() == Selection::default());
        assert_eq!(
            conditions
                .select_at_roots(&[1], &[], &[], &[])
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
}

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum SelectedStep {
    Assign(usize),
    Display(usize),
}

enum Step {
    ArrayWrite {
        index: Expression,
        first: i32,
        last: i32,
        start: usize,
        predicate: usize,
        origin: Origin,
    },
    Loop {
        initialize: Vec<Step>,
        predicate: usize,
        body: Vec<Step>,
        update: Vec<Step>,
        origin: Origin,
    },
    Assign(usize),
    Display(usize),
    If {
        predicate: usize,
        yes: Vec<Step>,
        no: Vec<Step>,
    },
}

struct Predicate {
    event: usize,
    relation: Relation,
    expression: Expression,
    origin: Origin,
    dependencies: AffineState,
    numeric: bool,
}

// LRM 2.4 section 5.10.3.1: a cross event occurs after the threshold crossing,
// inside the time/expression tolerance box. A body fired only by cross leaves
// observes the right limit tau+ of its certified roots. Continuous values keep
// their root enclosure there. A predicate with the same exact zero set as a
// fired guard g, d = k*g, has sign k*s where s is the certified side of g just
// after tau (0: proven plateau). Another state-independent predicate proved
// exactly zero at tau takes the sign of its certified time derivative on
// (tau, tau+e]. Otherwise the selected path is replayed with enclosures over
// the right window W = [lo, next_up(hi)], which contains (tau, tau+e] for every
// root tau in the batch window: a comparison holding for the whole window
// enclosure of d holds just after tau, and d in [0,0] is a proven plateau.
// A time-varying difference that is exactly zero at tau without one of these
// certificates cannot be decided by g(tau)=0; it is refused unless both
// branches are proved equivalent. A body fired by a timer leaf in the same
// batch executes at that exact time, where the fired guards certify g(t)=0.
#[derive(Default)]
struct PostRoot {
    // (calendar leaf, certified guard sign just after its root; 0: plateau)
    sides: Vec<(usize, i8)>,
    // (predicate, certified derivative sign on the post-root interval; 0: plateau)
    slopes: Vec<(usize, i8)>,
    // Event bodies fired only by cross leaves in this batch; they read at tau+.
    events: Vec<usize>,
    window: Option<RightWindow>,
}

/// Enclosures over the right window of one batch: driven inputs, and the
/// accepted operator histories (None: an operator column has no certificate).
#[derive(Clone)]
pub(crate) struct RightWindow {
    pub(crate) inputs: Vec<I>,
    pub(crate) operators: Vec<Option<I>>,
}

thread_local! {
    static POST_ROOT: std::cell::RefCell<PostRoot> =
        std::cell::RefCell::new(PostRoot::default());
}

/// Scope the certified post-root facts of one calendar batch. Dropping the
/// scope restores the enclosing value, so nothing survives its batch.
pub(crate) struct PostRootSides(PostRoot);
impl PostRootSides {
    pub(crate) fn install(
        sides: Vec<(usize, i8)>,
        slopes: Vec<(usize, i8)>,
        events: Vec<usize>,
        window: Option<RightWindow>,
    ) -> Self {
        Self(POST_ROOT.with(|cell| {
            cell.replace(PostRoot {
                sides,
                slopes,
                events,
                window,
            })
        }))
    }
}
impl Drop for PostRootSides {
    fn drop(&mut self) {
        let previous = std::mem::take(&mut self.0);
        POST_ROOT.with(|cell| *cell.borrow_mut() = previous);
    }
}

fn unique(entries: &[(usize, i8)], key: usize) -> Option<i8> {
    let mut found = entries.iter().filter(|(k, _)| *k == key).map(|(_, s)| *s);
    let first = found.next()?;
    found.all(|s| s == first).then_some(first)
}

/// Certified guard side of a fired leaf just after its root, if any.
pub(crate) fn post_root_side(leaf: usize) -> Option<i8> {
    POST_ROOT.with(|cell| unique(&cell.borrow().sides, leaf))
}

fn post_root_slope(predicate: usize) -> Option<i8> {
    POST_ROOT.with(|cell| unique(&cell.borrow().slopes, predicate))
}

/// Whether this event body reads at the right limit of its cross roots.
fn post_root_event(event: usize) -> bool {
    POST_ROOT.with(|cell| cell.borrow().events.contains(&event))
}

fn post_root_window() -> Option<RightWindow> {
    POST_ROOT.with(|cell| cell.borrow().window.clone())
}

/// Right-window reads of one body walk. A numeric read of an unsolved node
/// is unbounded, so it never yields a window certificate.
struct WindowReads {
    inputs: Vec<I>,
    operators: Vec<Option<I>>,
    nodes: Vec<I>,
}

/// First-order dependence of a value on the reads that move over the right
/// window: sparse (column, coefficient) pairs, driven inputs first and then
/// operator histories. Empty: the value is the same at te as at tau.
type Moving = Vec<(usize, I)>;

fn add_moving(moving: &mut Moving, column: usize, coefficient: I) {
    match moving.iter_mut().find(|(k, _)| *k == column) {
        Some((_, sum)) => *sum = *sum + coefficient,
        None => moving.push((column, coefficient)),
    }
}

/// Facts of the selected path that later reads depend on.
#[derive(Clone)]
struct PathFacts {
    // Dependence of each state on moving reads; None: unknown. A state not
    // written in this body keeps its accepted value: empty.
    moving: Vec<Option<Moving>>,
    // State enclosures over the right window on this path; None: unknown.
    window: Vec<Option<I>>,
}

/// Values of one row's read columns; an unknown value is admitted only under
/// an exactly zero coefficient, where it cannot contribute.
fn window_columns(columns: &[I], values: &[Option<I>]) -> Option<Vec<I>> {
    columns
        .iter()
        .enumerate()
        .map(|(k, c)| match values.get(k).copied().flatten() {
            Some(v) => Some(v),
            None if c.zero() => Some(I::ZERO),
            None => None,
        })
        .collect()
}

fn expression_size(e: &Expression) -> usize {
    match e {
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => 1 + expression_size(left) + expression_size(right),
        Expression::Power { base, .. } => 1 + expression_size(base),
        Expression::IntegerRound { value, .. } | Expression::CheckedInteger { value, .. } => {
            1 + expression_size(value)
        }
        Expression::CheckedIndex { index, .. } | Expression::ArrayRead { index, .. } => {
            1 + expression_size(index)
        }
        Expression::EventMath { args, .. } => 1 + args.iter().map(expression_size).sum::<usize>(),
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            1 + expression_size(left)
                + expression_size(right)
                + expression_size(then_value)
                + expression_size(else_value)
        }
        Expression::Affine { terms, .. } => 1 + terms.len(),
        _ => 1,
    }
}

/// Interval value of a numeric event expression over the right window. As
/// for the root read, a floor or a real-to-integer conversion must stay in
/// one bin and a selection must be decided over the whole enclosure.
fn window_bounds(e: &Expression, nodes: &[I], states: &[I]) -> Result<I, Error> {
    fn resolve(e: &Expression, nodes: &[I], states: &[I]) -> Result<Expression, Error> {
        let r = |e: &Expression| resolve(e, nodes, states).map(Box::new);
        Ok(match e {
            Expression::IntegerRound { value, origin } => Expression::Affine {
                constant: crate::event_numeric::nearest_box(
                    crate::event_numeric::bounds(&resolve(value, nodes, states)?, nodes, states)?,
                    origin,
                )?
                .lo,
                terms: vec![],
            },
            Expression::Add { left, right } => Expression::Add {
                left: r(left)?,
                right: r(right)?,
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: r(left)?,
                right: r(right)?,
            },
            Expression::Divide { left, right } => Expression::Divide {
                left: r(left)?,
                right: r(right)?,
            },
            Expression::Power { base, exponent } => Expression::Power {
                base: r(base)?,
                exponent: *exponent,
            },
            Expression::CheckedInteger { value, origin } => Expression::CheckedInteger {
                value: r(value)?,
                origin: origin.clone(),
            },
            Expression::CheckedIndex {
                index,
                first,
                last,
                origin,
            } => Expression::CheckedIndex {
                index: r(index)?,
                first: *first,
                last: *last,
                origin: origin.clone(),
            },
            Expression::ArrayRead {
                states: slots,
                index,
                first,
                last,
                origin,
            } => Expression::ArrayRead {
                states: slots.clone(),
                index: r(index)?,
                first: *first,
                last: *last,
                origin: origin.clone(),
            },
            Expression::EventMath {
                function,
                args,
                origin,
            } => Expression::EventMath {
                function: *function,
                args: args
                    .iter()
                    .map(|a| resolve(a, nodes, states))
                    .collect::<Result<_, _>>()?,
                origin: origin.clone(),
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
                left: r(left)?,
                right: r(right)?,
                then_value: r(then_value)?,
                else_value: r(else_value)?,
                origin: origin.clone(),
            },
            _ => e.clone(),
        })
    }
    crate::event_numeric::bounds(&resolve(e, nodes, states)?, nodes, states)
}

fn side_value(side: i8) -> I {
    match side {
        1 => I {
            lo: f64::MIN_POSITIVE,
            hi: f64::MAX,
        },
        -1 => I {
            lo: -f64::MAX,
            hi: -f64::MIN_POSITIVE,
        },
        _ => I::ZERO,
    }
}

/// Root observation of a predicate with the same exact zero set as a fired guard.
#[derive(Clone, Copy, PartialEq)]
enum RootRead {
    /// Certified value: k*s just after tau, or g(t)=0 for a timer-fired body.
    Value(I),
    /// d(tau)=0 is proved, but its side just after tau is not certified.
    Unsided,
}

/// Root facts shared by one event body walk.
#[derive(Clone, Copy)]
struct RootFacts<'a> {
    at_root: &'a [bool],
    certified: &'a [bool],
    // The body reads at the right limit tau+ of its cross roots.
    post: bool,
    // Right-window reads of a tau+ body, if the batch installed them.
    window: Option<&'a WindowReads>,
}

pub(crate) struct Conditions {
    bodies: Vec<Vec<Step>>,
    predicates: Vec<Predicate>,
    bounds: Option<GuardBounds>,
    // Exact zero-set certificates, indexed by calendar leaf, not event body.
    // Each entry keeps the sign of k in predicate difference = k * guard.
    root_predicates: Vec<Vec<(usize, i8)>>,
    assignments: Vec<Vec<AssignmentBounds>>,
    action_identity: Vec<Vec<ActionIdentity>>,
    stateful_events: Vec<bool>,
    state_count: usize,
    node_count: usize,
    driven_nodes: Vec<usize>,
    active_events: Vec<bool>,
    procedure_ids: Vec<Option<usize>>,
    ordinals: Vec<Option<u64>>,
    procedure_program: Option<std::sync::Arc<Program>>,
    procedure_work: Option<crate::transition_source_plan::Work>,
}

const MAX_BRANCH_PROOF_ATTEMPTS: usize = 64;

#[derive(PartialEq, Eq)]
struct ActionIdentity {
    state: usize,
    // Canonical serialization preserves every original expression
    // field, including +0.0 versus -0.0. Point values are not identity.
    rhs: Vec<u8>,
}

struct AssignmentBounds {
    state: usize,
    expression: Expression,
    dependencies: AffineState,
    row: usize,
    numeric: bool,
}

fn compile(
    body: &[Statement],
    p: &Program,
    owner: &str,
    next: &mut usize,
    displays: &mut usize,
    predicates: &mut Vec<Predicate>,
    general: bool,
) -> Result<Vec<Step>, Error> {
    body.iter()
        .map(|statement| match statement {
            Statement::ArrayWrite {
                states,
                index,
                first,
                last,
                origin,
                ..
            } => {
                if !general {
                    return Err(Error::new(
                        "unsupported_transient",
                        "array writes require an isolated observer event",
                    ));
                }
                crate::event_numeric::validate_array(
                    states, index, *first, *last, origin, p, owner,
                )?;
                let dependencies = crate::event_numeric::dependencies(index, p, owner)?;
                let predicate = predicates.len();
                predicates.push(Predicate {
                    event: usize::MAX,
                    relation: Relation::Ge,
                    expression: *index.clone(),
                    origin: origin.clone(),
                    dependencies,
                    numeric: true,
                });
                let start = *next;
                *next += states.len();
                Ok(Step::ArrayWrite {
                    index: *index.clone(),
                    first: *first,
                    last: *last,
                    start,
                    predicate,
                    origin: origin.clone(),
                })
            }
            Statement::Loop {
                initialize,
                relation,
                left,
                right,
                body,
                update,
                origin,
            } => {
                if !general {
                    return Err(Error::new(
                        "unsupported_loop",
                        "runtime loops require an isolated observer event",
                    ));
                }
                validate_loop(
                    initialize, *relation, left, right, body, update, origin, p, owner,
                )?;
                let init = compile(initialize, p, owner, next, displays, predicates, general)?;
                let wrapped = Statement::If {
                    relation: *relation,
                    left: left.clone(),
                    right: right.clone(),
                    then_body: body.clone(),
                    else_body: vec![],
                    origin: origin.clone(),
                };
                let mut compiled =
                    compile(&[wrapped], p, owner, next, displays, predicates, general)?;
                let Step::If { predicate, yes, .. } = compiled.pop().unwrap() else {
                    unreachable!()
                };
                let update = compile(update, p, owner, next, displays, predicates, general)?;
                Ok(Step::Loop {
                    initialize: init,
                    predicate,
                    body: yes,
                    update,
                    origin: origin.clone(),
                })
            }
            Statement::Assign(_) => {
                let index = *next;
                *next += 1;
                Ok(Step::Assign(index))
            }
            Statement::Display { .. } => {
                let index = *displays;
                *displays += 1;
                Ok(Step::Display(index))
            }
            Statement::If {
                relation,
                left,
                right,
                then_body,
                else_body,
                origin,
            } => {
                if origin.instance != owner
                    || origin.source.is_empty()
                    || origin.line == 0
                    || origin.column == 0
                {
                    return Err(Error::new("invalid_ir", "invalid condition origin"));
                }
                let expression = Expression::Add {
                    left: left.clone(),
                    right: Box::new(Expression::Multiply {
                        left: Box::new(Expression::Affine {
                            constant: -1.0,
                            terms: vec![],
                        }),
                        right: right.clone(),
                    }),
                };
                let ordinary = affine(&expression, p, owner);
                let numeric = ordinary.is_err() && general;
                let dependencies = if numeric {
                    crate::event_numeric::dependencies(&expression, p, owner)?
                } else {
                    ordinary?
                };
                if !dependencies.operator_dependencies.is_empty() {
                    return Err(Error::new(
                        "unsupported_condition",
                        format!(
                            "event condition cannot depend on operators at {}",
                            origin.label()
                        ),
                    ));
                }
                let predicate = predicates.len();
                predicates.push(Predicate {
                    event: usize::MAX,
                    relation: *relation,
                    expression,
                    origin: origin.clone(),
                    dependencies,
                    numeric,
                });
                Ok(Step::If {
                    predicate,
                    yes: compile(then_body, p, owner, next, displays, predicates, general)?,
                    no: compile(else_body, p, owner, next, displays, predicates, general)?,
                })
            }
        })
        .collect()
}

impl Conditions {
    #[cfg(test)]
    pub(crate) fn new(program: &Program) -> Result<Self, Error> {
        Self::new_with_numeric(program, &vec![false; program.events.len()])
    }
    pub(crate) fn new_with_numeric(program: &Program, general: &[bool]) -> Result<Self, Error> {
        let mut predicates = Vec::new();
        let mut stateful_events = Vec::new();
        let mut state_references = Vec::new();
        let bodies = program
            .events
            .iter()
            .enumerate()
            .map(|(event_index, event)| {
                // Procedure events are executed by the single source-order
                // Plan, including their predicates and assignment effects.
                // Building a second legacy replay would lose call-local frames.
                if event.procedure_id.is_some() {
                    stateful_events.push(true);
                    state_references.push(std::collections::BTreeSet::new());
                    return Ok(Vec::new());
                }
                let start = predicates.len();
                let body = compile(
                    &event.body,
                    program,
                    &event.origin.instance,
                    &mut 0,
                    &mut 0,
                    &mut predicates,
                    general[event_index],
                )?;
                for predicate in &mut predicates[start..] {
                    predicate.event = event_index;
                }
                stateful_events.push(
                    event.procedure_id.is_some()
                        || predicates[start..]
                            .iter()
                            .any(|p| !p.dependencies.state_dependencies.is_empty()),
                );
                state_references.push(
                    predicates[start..]
                        .iter()
                        .flat_map(|p| p.dependencies.state_dependencies.iter().copied())
                        .collect::<std::collections::BTreeSet<_>>(),
                );
                Ok(body)
            })
            .collect::<Result<_, _>>()?;
        let assignments = program
            .events
            .iter()
            .enumerate()
            .map(|(index, event)| {
                if event.procedure_id.is_some() || !stateful_events[index] {
                    return Ok(Vec::new());
                }
                let mut assignments = event
                    .assignments()
                    .into_iter()
                    .map(|a| {
                        Ok(AssignmentBounds {
                            state: a.state,
                            expression: a.rhs.clone(),
                            dependencies: if general[index] {
                                crate::event_numeric::dependencies(
                                    &a.rhs,
                                    program,
                                    &event.origin.instance,
                                )?
                            } else {
                                affine(&a.rhs, program, &event.origin.instance)?
                            },
                            numeric: general[index]
                                && affine(&a.rhs, program, &event.origin.instance).is_err(),
                            row: usize::MAX,
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()?;
                // Only updates capable of reaching a predicate need replay bounds.
                // Sampling an unrelated operator output still settles normally.
                if event.procedure_id.is_some() {
                    for a in &mut assignments {
                        a.row = 0;
                    }
                    return Ok(assignments);
                }
                let mut references = state_references[index].clone();
                loop {
                    let previous = references.len();
                    for a in &mut assignments {
                        if references.contains(&a.state) {
                            a.row = 0;
                            references.extend(&a.dependencies.state_dependencies);
                        }
                    }
                    if references.len() == previous {
                        break;
                    }
                }
                Ok(assignments)
            })
            .collect::<Result<Vec<_>, Error>>()?;
        // Keep every original assignment, independently of replay-row pruning.
        let action_identity = program
            .events
            .iter()
            .map(|event| {
                event
                    .assignments()
                    .iter()
                    .map(|assignment| {
                        Ok(ActionIdentity {
                            state: assignment.state,
                            rhs: serde_json::to_vec(&assignment.rhs).map_err(|_| {
                                Error::new("invalid_ir", "cannot retain event assignment identity")
                            })?,
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()
            })
            .collect::<Result<Vec<_>, Error>>()?;
        Ok(Self {
            bodies,
            predicates,
            bounds: None,
            root_predicates: Vec::new(),
            assignments,
            action_identity,
            stateful_events,
            state_count: program.states.len(),
            node_count: program.nodes.len(),
            driven_nodes: Vec::new(),
            active_events: vec![true; program.events.len()],
            procedure_ids: program.events.iter().map(|e| e.procedure_id).collect(),
            ordinals: program
                .events
                .iter()
                .map(|e| e.expanded_statement_ordinal)
                .collect(),
            procedure_program: None,
            procedure_work: None,
        })
    }

    pub(crate) fn install_procedures(
        &mut self,
        prepared: &crate::procedure::Prepared,
    ) -> Result<(), Error> {
        prepared.work.debit(2, 64)?;
        self.procedure_program = Some(prepared.program.clone());
        self.procedure_work = Some(prepared.work.clone());
        Ok(())
    }
    /// Preserve predicate/action IDs while selecting only the assigned stage.
    pub(crate) fn restrict_events(&mut self, active: &[bool]) {
        self.active_events = active.to_vec();
        for (event, body) in self.bodies.iter_mut().enumerate() {
            if !active[event] {
                body.clear();
            }
        }
        for (event, assignments) in self.assignments.iter_mut().enumerate() {
            if !active[event] {
                for assignment in assignments {
                    assignment.row = usize::MAX;
                }
            }
        }
    }

    pub(crate) fn enabled(&self) -> bool {
        !self.predicates.is_empty() || self.procedure_ids.iter().any(Option::is_some)
    }

    /// Executed predicates and alternative proof predicates read state. Other blocks may
    /// write the same state at different event times, but not in this batch.
    pub(crate) fn check_selection_readers(
        &self,
        selection: &Selection,
        writers: &[Option<usize>],
    ) -> Result<(), Error> {
        for &(index, _) in &selection.decisions {
            let predicate = &self.predicates[index];
            if predicate
                .dependencies
                .state_dependencies
                .iter()
                .any(|&state| {
                    writers[state].is_some_and(|writer| {
                        writer != predicate.event
                            && !crate::procedure_frames::ordered(selection, writer, predicate.event)
                    })
                })
            {
                return Err(Error::new("unsupported_cross", format!(
                    "simultaneous event condition reads state written by another selected block at {}",
                    predicate.origin.label())));
            }
        }
        Ok(())
    }

    pub(crate) fn check_dependencies(&self, affected: &[bool]) -> Result<(), Error> {
        // Source-position plans certify each executed condition before selecting
        // its arm. They do not replay these assignments against old voltages.
        if self.procedure_program.is_some() {
            return Ok(());
        }

        for predicate in self
            .predicates
            .iter()
            .filter(|p| self.active_events[p.event])
        {
            if predicate
                .dependencies
                .node_dependencies
                .iter()
                .any(|&node| affected[node])
            {
                return Err(Error::new(
                    "unsupported_condition",
                    format!(
                        "event condition may depend on state through the voltage network at {}",
                        predicate.origin.label()
                    ),
                ));
            }
        }
        // A state condition cannot replay an assignment whose RHS needs the
        // post-event joint electrical solution. Such a replay would read old
        // voltages and choose a potentially different branch.
        for assignment in self
            .assignments
            .iter()
            .flatten()
            .filter(|a| a.row != usize::MAX)
        {
            if !assignment.dependencies.operator_dependencies.is_empty()
                || assignment
                    .dependencies
                    .node_dependencies
                    .iter()
                    .any(|&node| affected[node])
            {
                return Err(Error::new("unsupported_condition",
                    "state-dependent event condition needs an assignment with state-independent voltage inputs"));
            }
        }
        Ok(())
    }

    pub(crate) fn prepare(&mut self, program: &Program, driven: &[String]) -> Result<(), Error> {
        self.prepare_with_dc(program, driven, None)
    }
    pub(crate) fn prepare_with_dc(
        &mut self,
        program: &Program,
        driven: &[String],
        dc: Option<&crate::dc_projection::DcProjection>,
    ) -> Result<(), Error> {
        self.root_predicates.clear();
        self.driven_nodes = driven
            .iter()
            .map(|name| {
                program
                    .nodes
                    .iter()
                    .position(|n| n == name)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown event input"))
            })
            .collect::<Result<_, _>>()?;
        if self.enabled() {
            let mut expressions: Vec<_> = self
                .predicates
                .iter()
                .map(|p| (self.active_events[p.event] && !p.numeric).then_some(&p.expression))
                .collect();
            for assignment in self
                .assignments
                .iter_mut()
                .flatten()
                .filter(|a| a.row != usize::MAX)
            {
                assignment.row = expressions.len();
                expressions.push((!assignment.numeric).then_some(&assignment.expression));
            }
            self.bounds = Some(
                match dc {
                    Some(dc) => GuardBounds::project_with_dc(
                        program,
                        driven,
                        &expressions,
                        None,
                        true,
                        true,
                        Some(dc),
                    ),
                    None => GuardBounds::stateful_parameters(program, driven, &expressions),
                }
                .map_err(|e| Error::new("event_condition", e.message))?,
            );
            // A root enclosure contains times other than the actual root.
            // Preserve g(tau)=0 when a predicate has the same proven zero set.
            // Projection must be exact; rounded matching is never a proof.
            for event in &program.events {
                for trigger in event.trigger.leaves()? {
                    let matches = if let EventTrigger::Cross { guard, .. } = trigger {
                        let expressions: Vec<_> = std::iter::once(Some(guard))
                            .chain(self.predicates.iter().map(|p| {
                                (self.active_events[p.event] && !p.numeric).then_some(&p.expression)
                            }))
                            .collect();
                        match dc {
                            Some(dc) => GuardBounds::project_with_dc(
                                program,
                                driven,
                                &expressions,
                                None,
                                true,
                                false,
                                Some(dc),
                            ),
                            None => {
                                GuardBounds::stateful_expressions(program, driven, &expressions)
                            }
                        }
                        .map(|bounds| {
                            (0..self.predicates.len())
                                .filter_map(|i| {
                                    bounds.zero_set_ratio_sign(0, i + 1).map(|k| (i, k))
                                })
                                .collect()
                        })
                        .unwrap_or_default()
                    } else {
                        vec![]
                    };
                    self.root_predicates.push(matches);
                }
            }
        }
        Ok(())
    }

    /// State-independent ordinary predicates of the given event bodies, with
    /// their owner instance, for post-root derivative certificates. A predicate
    /// whose enclosure over the whole batch window excludes zero never needs
    /// one. `input_only` omits operator columns, whose same-time history a
    /// timer in the batch may change before tau+.
    pub(crate) fn right_limit_candidates(
        &self,
        events: &[usize],
        window: &[I],
        input_only: bool,
    ) -> Vec<(usize, &Expression, &str)> {
        let Some(bounds) = self.bounds.as_ref() else {
            return Vec::new();
        };
        let values = bounds.values_with_operators(window, &[]);
        self.predicates
            .iter()
            .enumerate()
            .filter(|(i, p)| {
                events.contains(&p.event)
                    && self.active_events.get(p.event).copied().unwrap_or(false)
                    && !p.numeric
                    && p.dependencies.state_dependencies.is_empty()
                    && p.dependencies.operator_dependencies.is_empty()
                    && values.get(*i).is_none_or(|v| !(v.lo > 0.0 || v.hi < 0.0))
                    && (!input_only || (!bounds.symbolic(*i) && bounds.operator_free(*i)))
            })
            .map(|(i, p)| (i, &p.expression, p.origin.instance.as_str()))
            .collect()
    }

    /// Right-limit candidates of the passive observer conditions. A passive
    /// event body also reads at tau+ (LRM 2.4 5.10.3.1), so a predicate on a
    /// driven node of another instance earns the same derivative certificate
    /// as an active one. The filters match `right_limit_candidates`.
    pub(crate) fn passive_right_limit_candidates(
        &self,
        events: &[usize],
        input_only: bool,
    ) -> Vec<(usize, &Expression, &str)> {
        let Some(bounds) = self.bounds.as_ref() else {
            return Vec::new();
        };
        self.predicates
            .iter()
            .enumerate()
            .filter(|(i, p)| {
                events.contains(&p.event)
                    && self.active_events.get(p.event).copied().unwrap_or(false)
                    && !p.numeric
                    && p.dependencies.state_dependencies.is_empty()
                    && p.dependencies.operator_dependencies.is_empty()
                    && (!input_only || (!bounds.symbolic(*i) && bounds.operator_free(*i)))
            })
            .map(|(i, p)| (i, &p.expression, p.origin.instance.as_str()))
            .collect()
    }

    /// Dependence of a row or expression on the inputs and histories that
    /// move over the right window (without a window every read moves). An
    /// ordinary row composes the dependence of the states it reads, so an
    /// exact cancellation such as `s=x; d=x-s` is proved. A nonlinear or
    /// symbolic value is constant only if every read is constant or its whole
    /// window enclosure `value` is a point. With no dependence, every read on
    /// this path is the same at te as at tau, so the root value, including an
    /// exact tie, is unchanged at tau+. None: unknown.
    fn dependence(
        &self,
        row: usize,
        numeric: bool,
        dependencies: &AffineState,
        moving: &[Option<Moving>],
        window: Option<&WindowReads>,
        value: Option<I>,
    ) -> Option<Moving> {
        if value.is_some_and(|v| v.lo == v.hi) {
            return Some(Moving::new());
        }
        let driven = self.driven_nodes.len();
        let input = |k: usize| window.is_none_or(|w| w.inputs.get(k).is_none_or(|v| v.lo != v.hi));
        let operator = |k: usize| {
            window.is_none_or(|w| {
                w.operators
                    .get(k)
                    .copied()
                    .flatten()
                    .is_none_or(|v| v.lo != v.hi)
            })
        };
        let columns = self
            .bounds
            .as_ref()
            .filter(|_| !numeric)
            .and_then(|bounds| bounds.columns(row));
        match columns {
            Some((inputs, states, operators)) => {
                let mut out = Moving::new();
                for (k, &c) in inputs.iter().enumerate() {
                    if !c.zero() && input(k) {
                        add_moving(&mut out, k, c);
                    }
                }
                for (k, &c) in operators.iter().enumerate() {
                    if !c.zero() && operator(k) {
                        add_moving(&mut out, driven + k, c);
                    }
                }
                for (state, &c) in states.iter().enumerate() {
                    if !c.zero() {
                        for &(k, d) in moving.get(state)?.as_ref()? {
                            add_moving(&mut out, k, c * d);
                        }
                    }
                }
                out.retain(|(_, c)| !c.zero());
                Some(out)
            }
            // Numeric and symbolic reads use their structural dependencies;
            // an unsolved internal node always moves.
            None => {
                let reads = dependencies.node_dependencies.iter().any(|&node| {
                    node != 0
                        && self
                            .driven_nodes
                            .iter()
                            .position(|&n| n == node)
                            .is_none_or(input)
                }) || dependencies
                    .operator_dependencies
                    .iter()
                    .any(|&k| operator(k))
                    || dependencies.state_dependencies.iter().any(|&state| {
                        moving
                            .get(state)
                            .is_none_or(|m| m.as_ref().is_none_or(|m| !m.is_empty()))
                    });
                (!reads).then(Moving::new)
            }
        }
    }

    /// Operator columns read by the ordinary rows of these event bodies; only
    /// these histories need a right-window enclosure.
    pub(crate) fn window_operators(&self, events: &[usize]) -> Vec<usize> {
        let Some(bounds) = self.bounds.as_ref() else {
            return Vec::new();
        };
        let predicates = self
            .predicates
            .iter()
            .enumerate()
            .filter(|(_, p)| events.contains(&p.event) && !p.numeric)
            .map(|(row, _)| row);
        let assignments = events
            .iter()
            .filter_map(|&event| self.assignments.get(event))
            .flatten()
            .filter(|a| a.row != usize::MAX && !a.numeric)
            .map(|a| a.row);
        let mut operators = std::collections::BTreeSet::new();
        for row in predicates.chain(assignments) {
            if let Some((_, _, columns)) = bounds.columns(row) {
                operators.extend(
                    columns
                        .iter()
                        .enumerate()
                        .filter(|(_, c)| !c.zero())
                        .map(|(k, _)| k),
                );
            }
        }
        operators.into_iter().collect()
    }

    /// Enclosure over the right window of an ordinary row or a numeric
    /// expression, replayed on the selected path. None when a read has no
    /// window certificate (an unknown state or history, a symbolic row, a
    /// straddled bin or selection, a domain or finiteness failure).
    fn window_value(
        &self,
        row: usize,
        numeric: Option<(&Expression, &AffineState)>,
        window: &WindowReads,
        states: &[Option<I>],
    ) -> Option<I> {
        let value = match numeric {
            Some((expression, dependencies)) => {
                if !dependencies.operator_dependencies.is_empty()
                    || dependencies
                        .state_dependencies
                        .iter()
                        .any(|&state| states.get(state).copied().flatten().is_none())
                {
                    return None;
                }
                let states: Vec<_> = states.iter().map(|v| v.unwrap_or(I::ZERO)).collect();
                window_bounds(expression, &window.nodes, &states).ok()?
            }
            None => {
                let bounds = self.bounds.as_ref()?;
                let (_, state_columns, operator_columns) = bounds.columns(row)?;
                let states = window_columns(state_columns, states)?;
                let operators = window_columns(operator_columns, &window.operators)?;
                bounds.value_with_parameters(row, &window.inputs, &states, &operators)
            }
        };
        value.finite().then_some(value)
    }

    /// Fund a right-window read from the paid ledger of this walk, if any.
    fn charge_window(
        &self,
        states: &crate::event_value_proof::LocalState,
        numeric: Option<&Expression>,
    ) -> Result<(), Error> {
        let size = numeric.map_or(self.node_count, expression_size);
        let amount = size
            .saturating_add(self.state_count)
            .saturating_add(self.driven_nodes.len())
            .saturating_add(1);
        if let Some(w) = states.history_work() {
            w.debit(2, amount as u64)
        } else if let Some(w) = states.floor_work() {
            crate::event_floor::charge(w, amount, "floor_source_window")
        } else {
            Ok(())
        }
    }

    pub(crate) fn select(&self, events: &[usize], inputs: &[I]) -> Result<Selection, Error> {
        self.select_at_roots(events, inputs, &[], &[])
    }

    pub(crate) fn select_at_roots(
        &self,
        events: &[usize],
        inputs: &[I],
        fired_leaves: &[usize],
        before_bounds: &[I],
    ) -> Result<Selection, Error> {
        self.select_with_proofs(events, inputs, fired_leaves, before_bounds, None)
    }
    pub(crate) fn select_with_proofs(
        &self,
        events: &[usize],
        inputs: &[I],
        fired_leaves: &[usize],
        before_bounds: &[I],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Selection, Error> {
        if let Some(program) = &self.procedure_program {
            let w = self.procedure_work.as_ref().expect("procedure owner");
            w.debit(
                2,
                (self.node_count + self.state_count + events.len() + 32) as u64,
            )?;
            let mut nodes = vec![
                I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY
                };
                self.node_count
            ];
            nodes[0] = I::ZERO;
            for (&node, &value) in self.driven_nodes.iter().zip(inputs) {
                nodes[node] = value;
            }
            let fired = events
                .iter()
                .copied()
                .filter(|&event| self.active_events.get(event) == Some(&true))
                .collect::<Vec<_>>();
            // Supply only independently forced pre-event voltages. Positive
            // Transition outputs are continuous at the event, while any state
            // assigned by this batch is excluded from a provider proof.
            if !fired.is_empty() {
                for &node in &self.driven_nodes {
                    w.debit(2, (program.nodes[node].len() + 32) as u64)?;
                }
                let driven = self
                    .driven_nodes
                    .iter()
                    .map(|&n| program.nodes[n].clone())
                    .collect::<Vec<_>>();
                crate::causal_event::fill_independent_pre_event_nodes(
                    program,
                    &driven,
                    &fired,
                    &mut nodes,
                    before_bounds,
                    proofs.map(|p| p.operators()).unwrap_or(&[]),
                    w,
                )?;
            }
            let plan =
                crate::procedure::execute(program, &fired, &nodes, before_bounds, proofs, w)?;
            let mut selection = Selection {
                actions: plan.actions.clone(),
                plan: Some(std::sync::Arc::new(plan)),
                ..Selection::default()
            };
            if proofs.is_some_and(|p| p.rooted_occurrence()) {
                selection.procedure_groups = vec![None; self.procedure_ids.len()];
                for &event in &fired {
                    if let Some(proc) = self.procedure_ids[event] {
                        selection.procedure_groups[event] = fired
                            .iter()
                            .copied()
                            .find(|&e| self.procedure_ids[e] == Some(proc));
                    }
                }
            }
            return Ok(selection);
        }
        if events
            .iter()
            .any(|&event| event >= self.active_events.len())
        {
            return Err(Error::new(
                "invalid_ir",
                "selected event index out of range",
            ));
        }
        if !events.iter().any(|&event| self.active_events[event]) {
            return Ok(Selection::default());
        }
        let operators = proofs.map(|p| p.operators()).unwrap_or(&[]);
        let mut values = self
            .bounds
            .as_ref()
            .map(|b| b.values_with_operators(inputs, operators))
            .unwrap_or_default();
        // at_root: a fired guard with the same exact zero set proves d(tau)=0.
        // certified: that root read also decides the body's observation.
        let mut at_root = vec![false; self.predicates.len()];
        let mut certified = vec![false; self.predicates.len()];
        let mut root_reads: Vec<Option<RootRead>> = vec![None; self.predicates.len()];
        let mut conflicting = vec![false; self.predicates.len()];
        for &leaf in fired_leaves {
            if let Some(predicates) = self.root_predicates.get(leaf) {
                for &(predicate, ratio) in predicates {
                    let read = if post_root_event(self.predicates[predicate].event) {
                        post_root_side(leaf).map_or(RootRead::Unsided, |side| {
                            RootRead::Value(side_value(side * ratio))
                        })
                    } else {
                        RootRead::Value(I::ZERO)
                    };
                    root_reads[predicate] = match (root_reads[predicate], read) {
                        (None | Some(RootRead::Unsided), read) => Some(read),
                        (old, RootRead::Unsided) => old,
                        (Some(old), read) => {
                            conflicting[predicate] |= old != read;
                            Some(old)
                        }
                    };
                }
            }
        }
        for (predicate, read) in root_reads.into_iter().enumerate() {
            // Inconsistent same-root sides are not a proof; keep the root box.
            match read.filter(|_| !conflicting[predicate]) {
                Some(RootRead::Value(value)) => {
                    values[predicate] = value;
                    at_root[predicate] = true;
                    certified[predicate] = true;
                }
                Some(RootRead::Unsided) => {
                    values[predicate] = I::ZERO;
                    at_root[predicate] = true;
                }
                None => {}
            }
        }
        #[allow(clippy::too_many_arguments)] // Keep the recursive event-selection context explicit.
        fn walk(
            body: &[Step],
            values: &[I],
            predicates: &[Predicate],
            actions: &mut Vec<usize>,
            decisions: &mut Vec<(usize, bool)>,
            ordered: &mut Vec<SelectedStep>,
            assignments: &[AssignmentBounds],
            identity: &[ActionIdentity],
            context: &Conditions,
            inputs: &[I],
            operators: &[I],
            states: &mut crate::event_value_proof::LocalState,
            written: &mut [bool],
            path: &mut PathFacts,
            root: RootFacts<'_>,
            proof_attempts: &mut usize,
            loop_iterations: &mut usize,
        ) -> Result<(), Error> {
            if let Some(w) = states.history_work() {
                w.debit(2, 0)?;
                w.debit(
                    2,
                    (context.node_count as u64)
                        .saturating_mul(2)
                        .saturating_add(1),
                )?;
            } else if let Some(w) = states.floor_work() {
                crate::event_floor::charge(w, context.node_count + 1, "floor_source_copy")?;
            }
            let bounds = context.bounds.as_ref();
            let mut numeric_nodes = vec![
                I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY
                };
                context.node_count
            ];
            numeric_nodes[0] = I::ZERO;
            for (&node, &value) in context.driven_nodes.iter().zip(inputs) {
                numeric_nodes[node] = value;
            }
            for step in body {
                if let Some(w) = states.history_work() {
                    w.step()?;
                }
                if let Some(w) = states.floor_work() {
                    crate::event_floor::charge(w, 1, "floor_source_ast")?;
                }
                match step {
                    Step::ArrayWrite {
                        index,
                        first,
                        last,
                        start,
                        predicate,
                        origin,
                    } => {
                        let value = crate::event_numeric::checked_index(
                            crate::event_numeric::bounds(index, &numeric_nodes, states)?,
                            *first,
                            *last,
                            origin,
                        )?;
                        decisions.push((*predicate, true));
                        let slot = *start + (value.lo - f64::from(*first)) as usize;
                        walk(
                            &[Step::Assign(slot)],
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            context,
                            inputs,
                            operators,
                            states,
                            written,
                            path,
                            root,
                            proof_attempts,
                            loop_iterations,
                        )?;
                    }
                    Step::Loop {
                        initialize,
                        predicate,
                        body,
                        update,
                        origin,
                    } => {
                        walk(
                            initialize,
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            context,
                            inputs,
                            operators,
                            states,
                            written,
                            path,
                            root,
                            proof_attempts,
                            loop_iterations,
                        )?;
                        loop {
                            let p = &predicates[*predicate];
                            let value = if p.numeric {
                                crate::event_numeric::bounds_with_proofs(
                                    &p.expression,
                                    &numeric_nodes,
                                    states,
                                )?
                            } else {
                                bounds
                                    .unwrap()
                                    .checked_value(*predicate, inputs, states, operators)?
                            };
                            let (yes, no) = crate::event_numeric::sign(p.relation, value);
                            // Same tau+ rule as an ordinary condition; loop bounds
                            // have no derivative certificate, only a window one.
                            let unsided = root.post
                                && value.zero()
                                && context
                                    .dependence(
                                        *predicate,
                                        p.numeric,
                                        &p.dependencies,
                                        &path.moving,
                                        root.window,
                                        None,
                                    )
                                    .is_none_or(|m| !m.is_empty());
                            let (yes, no) = match root.window.filter(|_| unsided) {
                                Some(window) => {
                                    context.charge_window(
                                        states,
                                        p.numeric.then_some(&p.expression),
                                    )?;
                                    context
                                        .window_value(
                                            *predicate,
                                            p.numeric.then_some((&p.expression, &p.dependencies)),
                                            window,
                                            &path.window,
                                        )
                                        .map_or((false, false), |v| {
                                            crate::event_numeric::sign(p.relation, v)
                                        })
                                }
                                None if unsided => (false, false),
                                None => (yes, no),
                            };
                            if !value.finite() || !(yes || no) {
                                return Err(Error::new(
                                    "event_condition",
                                    format!(
                                        "cannot certify loop continuation at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            decisions.push((*predicate, yes));
                            if no {
                                break;
                            }
                            if *loop_iterations >= 4096 {
                                return Err(Error::new(
                                    "event_loop_budget",
                                    format!(
                                        "event exceeds 4096 total loop iterations at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            *loop_iterations += 1;
                            walk(
                                body,
                                values,
                                predicates,
                                actions,
                                decisions,
                                ordered,
                                assignments,
                                identity,
                                context,
                                inputs,
                                operators,
                                states,
                                written,
                                path,
                                root,
                                proof_attempts,
                                loop_iterations,
                            )?;
                            walk(
                                update,
                                values,
                                predicates,
                                actions,
                                decisions,
                                ordered,
                                assignments,
                                identity,
                                context,
                                inputs,
                                operators,
                                states,
                                written,
                                path,
                                root,
                                proof_attempts,
                                loop_iterations,
                            )?;
                        }
                    }
                    Step::Assign(index) => {
                        actions.push(*index);
                        ordered.push(SelectedStep::Assign(*index));
                        if let Some(a) = assignments.get(*index).filter(|a| a.row != usize::MAX) {
                            let value = if a.numeric {
                                crate::event_numeric::bounds_with_proofs(
                                    &a.expression,
                                    &numeric_nodes,
                                    states,
                                )?
                            } else {
                                bounds
                                    .unwrap()
                                    .checked_value(a.row, inputs, states, operators)?
                            };
                            if !value.finite() {
                                return Err(Error::new(
                                    "event_condition",
                                    "nonfinite prior-assignment bounds",
                                ));
                            }
                            states.try_assign(a.state, &a.expression, &numeric_nodes, value)?;
                            written[a.state] = true;
                            // Replay the same write over the right window. A value
                            // read from a moving voltage or history at te varies
                            // with te, although its enclosure is taken at tau.
                            let window_value = match root.window {
                                Some(window) => {
                                    context.charge_window(
                                        states,
                                        a.numeric.then_some(&a.expression),
                                    )?;
                                    context.window_value(
                                        a.row,
                                        a.numeric.then_some((&a.expression, &a.dependencies)),
                                        window,
                                        &path.window,
                                    )
                                }
                                None => None,
                            };
                            path.moving[a.state] = context.dependence(
                                a.row,
                                a.numeric,
                                &a.dependencies,
                                &path.moving,
                                root.window,
                                window_value,
                            );
                            path.window[a.state] = window_value;
                        } else if let Some(a) = assignments.get(*index) {
                            // An untracked write is never read by a condition.
                            path.moving[a.state] = None;
                            path.window[a.state] = None;
                        }
                    }
                    Step::Display(index) => ordered.push(SelectedStep::Display(*index)),
                    Step::If { predicate, yes, no } => {
                        let p = &predicates[*predicate];
                        // A root read is certified only when this read uses it.
                        let (value, certified) = if p.numeric {
                            (
                                crate::event_numeric::bounds_with_proofs(
                                    &p.expression,
                                    &numeric_nodes,
                                    states,
                                )?,
                                false,
                            )
                        } else if (p.dependencies.state_dependencies.is_empty()
                            && !bounds.unwrap().symbolic(*predicate))
                            || (root.at_root[*predicate]
                                && p.dependencies
                                    .state_dependencies
                                    .iter()
                                    .all(|&state| !written[state]))
                        {
                            (values[*predicate], root.certified[*predicate])
                        } else {
                            (
                                bounds
                                    .unwrap()
                                    .checked_value(*predicate, inputs, states, operators)?,
                                false,
                            )
                        };
                        let value = if value.sign().is_none() {
                            let exact = states.try_value(&p.expression, &numeric_nodes)?;
                            if exact.is_some() {
                                if let Some(w) = states.floor_work() {
                                    crate::event_floor::charge(
                                        w,
                                        1024,
                                        "floor_source_exact_enclosure",
                                    )?;
                                }
                            }
                            let proved = match exact.as_ref() {
                                Some(v) => states.try_enclosure(v)?,
                                None => None,
                            };
                            proved
                                .filter(|v| value.lo <= v.lo && v.hi <= value.hi)
                                .unwrap_or(value)
                        } else {
                            value
                        };
                        // At tau+ an exact zero decides nothing by itself: use the
                        // derivative side of a state-independent value, or a
                        // time-invariant tie. Otherwise only an enclosure over the
                        // right window on this path can decide the comparison.
                        let mut unsided = false;
                        let value = if root.post && value.zero() && !certified {
                            let slope = (!p.numeric
                                && p.dependencies.state_dependencies.is_empty())
                            .then(|| post_root_slope(*predicate))
                            .flatten();
                            match slope {
                                Some(side) => side_value(side),
                                None => {
                                    unsided = context
                                        .dependence(
                                            *predicate,
                                            p.numeric,
                                            &p.dependencies,
                                            &path.moving,
                                            root.window,
                                            None,
                                        )
                                        .is_none_or(|m| !m.is_empty());
                                    value
                                }
                            }
                        } else {
                            value
                        };
                        let window_value = match root.window.filter(|_| unsided) {
                            Some(window) => {
                                context
                                    .charge_window(states, p.numeric.then_some(&p.expression))?;
                                context.window_value(
                                    *predicate,
                                    p.numeric.then_some((&p.expression, &p.dependencies)),
                                    window,
                                    &path.window,
                                )
                            }
                            None => None,
                        };
                        let (yes_proved, no_proved) = match p.relation {
                            _ if unsided => window_value.map_or((false, false), |v| {
                                crate::diagnostics::counter("post_root_window_reads", 1);
                                crate::event_numeric::sign(p.relation, v)
                            }),
                            Relation::Lt => (value.hi < 0.0, value.lo >= 0.0),
                            Relation::Le => (value.hi <= 0.0, value.lo > 0.0),
                            Relation::Gt => (value.lo > 0.0, value.hi <= 0.0),
                            Relation::Ge => (value.lo >= 0.0, value.hi < 0.0),
                        };
                        if !value.finite() || !(yes_proved || no_proved) {
                            let original = if unsided {
                                Error::new("event_condition", format!("cannot certify {:?} condition at {} just after its crossing root: the difference is exactly zero at tau and has no one-sided or right-window certificate", p.relation, p.origin.label()))
                            } else {
                                Error::new("event_condition", format!("cannot certify {:?} condition at {}: difference in [{:e}, {:e}]", p.relation, p.origin.label(), value.lo, value.hi))
                            };
                            if !value.finite() || *proof_attempts > MAX_BRANCH_PROOF_ATTEMPTS - 2 {
                                return Err(original);
                            }
                            *proof_attempts += 2;
                            crate::diagnostics::counter("event_branch_proof_attempts", 2);
                            // Both alternatives are checked against the same original
                            // enclosures. No sign assumption narrows a sampled value.
                            let mut ya = Vec::new();
                            let mut na = Vec::new();
                            let mut yd = Vec::new();
                            let mut nd = Vec::new();
                            let mut yo = Vec::new();
                            let mut no_ordered = Vec::new();
                            let mut ys = states.try_clone()?;
                            let mut ns = states.try_clone()?;
                            let mut yw = written.to_vec();
                            let mut nw = written.to_vec();
                            let mut yv = path.clone();
                            let mut nv = path.clone();
                            let yr = walk(
                                yes,
                                values,
                                predicates,
                                &mut ya,
                                &mut yd,
                                &mut yo,
                                assignments,
                                identity,
                                context,
                                inputs,
                                operators,
                                &mut ys,
                                &mut yw,
                                &mut yv,
                                root,
                                proof_attempts,
                                loop_iterations,
                            );
                            let nr = walk(
                                no,
                                values,
                                predicates,
                                &mut na,
                                &mut nd,
                                &mut no_ordered,
                                assignments,
                                identity,
                                context,
                                inputs,
                                operators,
                                &mut ns,
                                &mut nw,
                                &mut nv,
                                root,
                                proof_attempts,
                                loop_iterations,
                            );
                            // Never turn an invalid domain/IR/resource diagnostic
                            // into an alternative certificate or a cache miss.
                            for result in [&yr, &nr] {
                                if let Err(error) = result {
                                    if error.kind != "event_condition" {
                                        return Err(Error {
                                            kind: error.kind,
                                            message: error.message.clone(),
                                            sample: error.sample,
                                        });
                                    }
                                }
                            }
                            let same_writes = ya.len() == na.len()
                                && ya.iter().zip(&na).all(|(&a, &b)| {
                                    identity
                                        .get(a)
                                        .zip(identity.get(b))
                                        .is_some_and(|(a, b)| a == b)
                                });
                            let no_display = yo
                                .iter()
                                .chain(&no_ordered)
                                .all(|step| matches!(step, SelectedStep::Assign(_)));
                            let same_bounds = ys.len() == ns.len()
                                && ys.iter().zip(ns.iter()).all(|(a, b)| {
                                    a.lo.to_bits() == b.lo.to_bits()
                                        && a.hi.to_bits() == b.hi.to_bits()
                                });
                            if yr.is_err()
                                || nr.is_err()
                                || !same_writes
                                || !no_display
                                || !same_bounds
                                || yw != nw
                                || yv.moving != nv.moving
                            {
                                return Err(original);
                            }
                            ys.prepay_comparison(&ns)?;
                            states.merge(ys, &ns);
                            written.copy_from_slice(&yw);
                            // The actual tau+ path is one of the two arms.
                            for (state, (a, b)) in yv.window.iter().zip(&nv.window).enumerate() {
                                path.window[state] = a.zip(*b).map(|(a, b)| a.hull(b));
                            }
                            path.moving = yv.moving;
                            actions.extend(ya);
                            ordered.extend(yo);
                            // The chosen writes are identical. Keep the reads from
                            // both proofs for writer checks and certificate identity.
                            decisions.extend([(*predicate, true), (*predicate, false)]);
                            decisions.extend(yd);
                            decisions.extend(nd);
                            crate::diagnostics::counter("event_equivalent_branch_proofs", 1);
                            continue;
                        }
                        decisions.push((*predicate, yes_proved));
                        walk(
                            if yes_proved { yes } else { no },
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            context,
                            inputs,
                            operators,
                            states,
                            written,
                            path,
                            root,
                            proof_attempts,
                            loop_iterations,
                        )?;
                    }
                }
            }
            Ok(())
        }
        let mut result = Selection::default();
        let mut event_order = events.to_vec();
        let rooted = proofs.is_some_and(|p| p.rooted_occurrence());
        if rooted {
            if let Some(w) = proofs.and_then(|p| p.execution_work()) {
                w.debit(
                    2,
                    (self.procedure_ids.len() + events.len().saturating_mul(events.len()) + 16)
                        as u64,
                )?;
            }
            result.procedure_groups = vec![None; self.procedure_ids.len()];
            for &event in events {
                if let Some(proc) = self.procedure_ids[event] {
                    let group = events
                        .iter()
                        .copied()
                        .find(|&e| self.procedure_ids[e] == Some(proc))
                        .unwrap();
                    result.procedure_groups[event] = Some(group);
                }
            }
            for (i, &event) in events.iter().enumerate() {
                if let Some(proc) = self.procedure_ids[event] {
                    let rank = events[..i]
                        .iter()
                        .filter(|&&e| self.procedure_ids[e] == Some(proc))
                        .count();
                    let mut members = events
                        .iter()
                        .copied()
                        .filter(|&e| self.procedure_ids[e] == Some(proc))
                        .collect::<Vec<_>>();
                    members.sort_by_key(|&e| self.ordinals[e]);
                    event_order[i] = members[rank];
                }
            }
        }
        let mut procedure_frames = std::collections::BTreeMap::new();
        let mut proof_attempts = 0;
        // Right-window reads of this batch, shared by its tau+ bodies.
        let window = post_root_window()
            .filter(|w| w.inputs.len() == self.driven_nodes.len())
            .map(|w| {
                let mut nodes = vec![
                    I {
                        lo: f64::NEG_INFINITY,
                        hi: f64::INFINITY
                    };
                    self.node_count
                ];
                nodes[0] = I::ZERO;
                for (&node, &value) in self.driven_nodes.iter().zip(&w.inputs) {
                    nodes[node] = value;
                }
                WindowReads {
                    inputs: w.inputs,
                    operators: w.operators,
                    nodes,
                }
            });
        for &event in &event_order {
            if !self.active_events[event] {
                continue;
            }
            if self.stateful_events[event] && before_bounds.len() != self.state_count {
                return Err(Error::new(
                    "invalid_ir",
                    "event condition accepted state bounds length mismatch",
                ));
            }
            let mut loop_iterations = 0;
            let mut actions = Vec::new();
            let mut ordered = Vec::new();
            let mut states =
                crate::event_value_proof::LocalState::try_with_context(before_bounds, proofs)?;
            let mut written = vec![false; self.state_count];
            let post = post_root_event(event);
            let window = window.as_ref().filter(|_| post);
            // No other event changes the accepted states before this body.
            let mut path = PathFacts {
                moving: vec![Some(Moving::new()); self.state_count],
                window: if window.is_some() && before_bounds.len() == self.state_count {
                    before_bounds.iter().copied().map(Some).collect()
                } else {
                    vec![None; self.state_count]
                },
            };
            let group = result.procedure_groups.get(event).copied().flatten();
            if let Some((prior, prior_written, prior_path)) =
                group.and_then(|g| procedure_frames.remove(&g))
            {
                states = prior;
                written = prior_written;
                path = prior_path;
            }
            walk(
                &self.bodies[event],
                &values,
                &self.predicates,
                &mut actions,
                &mut result.decisions,
                &mut ordered,
                &self.assignments[event],
                &self.action_identity[event],
                self,
                inputs,
                operators,
                &mut states,
                &mut written,
                &mut path,
                RootFacts {
                    at_root: &at_root,
                    certified: &certified,
                    post,
                    window,
                },
                &mut proof_attempts,
                &mut loop_iterations,
            )?;
            if let Some(group) = group {
                procedure_frames.insert(group, (states, written, path));
            }
            result.actions.push((event, actions));
            result.ordered_steps.push((event, ordered));
        }
        Ok(result)
    }
}

#[cfg(test)]
mod branch_review_tests {
    use super::*;
    use serde_json::json;
    fn c(v: f64) -> serde_json::Value {
        json!({"op":"affine","constant":v,"terms":[]})
    }
    fn model(counts: &[usize], writes: bool) -> crate::events::EventModel {
        let o = json!({"source":"branch_review.va","line":1,"column":1,"instance":"D"});
        let mut events = vec![];
        for &n in counts {
            let assign = if writes {
                json!([{"kind":"assign","state":0,"rhs":c(1.)}])
            } else {
                json!([])
            };
            let body:Vec<_>=(0..n).map(|_|json!({"kind":"if","relation":"ge","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.),"then_body":assign,"else_body":assign,"origin":o})).collect();
            events.push(json!({"origin":o,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"body":body}));
        }
        let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],"states":[{"instance":"D","name":"q","kind":"real","initial":0}],"operators":[],"events":events,"contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"state","state":0}}]})).unwrap();
        crate::events::EventModel::new(p, vec!["u".into()], crate::ir::Tolerances::default())
            .unwrap()
    }
    #[test]
    fn budget_is_shared_across_events_and_nonfinite_predicate_cannot_fork() {
        let m = model(&[16, 16], false);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(&[0, 1], &[I { lo: -1., hi: 1. }])
        });
        assert!(r.is_ok());
        assert_eq!(d.counters["event_branch_proof_attempts"], 64);
        let m = model(&[16, 17], false);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(&[0, 1], &[I { lo: -1., hi: 1. }])
        });
        assert_eq!(r.err().unwrap().kind, "event_condition");
        assert_eq!(d.counters["event_branch_proof_attempts"], 64);
        let m = model(&[1], true);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(
                &[0],
                &[I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                }],
            )
        });
        assert_eq!(r.err().unwrap().kind, "event_condition");
        assert!(!d.counters.contains_key("event_branch_proof_attempts"));
    }
}

#[allow(clippy::too_many_arguments)]
fn validate_loop(
    init: &[Statement],
    relation: Relation,
    left: &Expression,
    right: &Expression,
    body: &[Statement],
    update: &[Statement],
    origin: &Origin,
    p: &Program,
    owner: &str,
) -> Result<(), Error> {
    let invalid = || {
        Error::new(
            "invalid_ir",
            format!("invalid bounded integer loop at {}", origin.label()),
        )
    };
    if origin.instance != owner
        || origin.source.is_empty()
        || origin.line == 0
        || origin.column == 0
        || !origin.valid_expansion()
    {
        return Err(invalid());
    }
    let ([Statement::Assign(start)], [Statement::Assign(end)]) = (init, update) else {
        return Err(invalid());
    };
    if start.state != end.state
        || p.states
            .get(start.state)
            .is_none_or(|s| s.instance != owner || s.kind != crate::ir::StateKind::Integer)
        || !matches!(left,Expression::State{state} if *state==start.state)
    {
        return Err(invalid());
    }
    crate::event_numeric::validate(&start.rhs, p, owner)?;
    crate::event_numeric::validate(right, p, owner)?;
    if !crate::event_numeric::integral(&start.rhs, p) || !crate::event_numeric::integral(right, p) {
        return Err(invalid());
    }
    fn strip(e: &Expression) -> Expression {
        match e {
            Expression::CheckedInteger { value, .. } => strip(value),
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(strip(left)),
                right: Box::new(strip(right)),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(strip(left)),
                right: Box::new(strip(right)),
            },
            _ => e.clone(),
        }
    }
    let step = affine(&strip(&end.rhs), p, owner)?;
    if !step.constant.is_finite()
        || step.constant == 0.
        || step.constant.fract() != 0.
        || step.nodes.iter().any(|v| *v != 0.)
        || !step.operator_dependencies.is_empty()
        || step
            .states
            .iter()
            .enumerate()
            .any(|(i, v)| *v != if i == start.state { 1. } else { 0. })
        || matches!(relation, Relation::Lt | Relation::Le) != (step.constant > 0.)
    {
        return Err(invalid());
    }
    let event = crate::ir::Event {
        trigger: EventTrigger::FinalStep {},
        procedure_id: None,
        expanded_statement_ordinal: None,
        body: body.to_vec(),
        origin: origin.clone(),
    };
    if event.assignments().iter().any(|a| a.state == start.state) {
        return Err(invalid());
    }
    Ok(())
}

#[cfg(test)]
#[path = "event_procedure_voltage_tests.rs"]
mod procedure_voltage_tests;
