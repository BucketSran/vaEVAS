//! Candidate value IDs, source control and call-site captures. Every executed
//! source value is an effect root even when a later statement overwrites it.
use super::*;
use crate::event_value_proof::{Context, LocalState};
use crate::interval::Interval as I;
use crate::ir::Statement as S;
use crate::procedure_operations::{Cell, Domain, Operation as O};
use crate::procedure_values::{Fault, Graph, Id};
use crate::same_time_root::PhysicalFrame;
use std::sync::Arc;

fn origin_copy(o: &ir::Origin, w: &Work) -> Result<ir::Origin, Error> {
    let mut fee = (o.source.len() + o.instance.len() + 64) as u64;
    for (name, _) in &o.expansion {
        w.step()?;
        fee = fee.saturating_add((name.len() + 32) as u64);
    }
    w.debit(2, fee)?;
    Ok(o.clone())
}
fn strings_copy_cost(values: &[String], w: &Work) -> Result<(), Error> {
    for value in values {
        w.debit(2, (value.len() + 32) as u64)?;
    }
    Ok(())
}
fn arena<T>(result: Result<T, Fault<Error>>) -> Result<T, Error> {
    result.map_err(|e| match e {
        Fault::Quota(e) | Fault::Evaluate(e) => e,
        Fault::InvalidId => invalid("procedure value graph has an invalid dependency"),
    })
}
#[path = "procedure_control.rs"]
mod control;
#[path = "procedure_history.rs"]
mod history;
#[path = "procedure_right_limit.rs"]
mod right_limit;
#[derive(Clone)]
pub(crate) struct Guard {
    pub relation: ir::Relation,
    pub left: Id,
    pub right: Id,
    value: bool,
    // Decided at the right limit tau+ of a cross-fired body.
    post_root: bool,
}
#[derive(Clone)]
struct Selector {
    index: Id,
    value: f64,
}
#[derive(Clone)]
pub(crate) struct OperatorView {
    pub input: Id,
    pub reset: Option<Id>,
}
#[derive(Clone)]
pub(crate) struct Plan {
    pub graph: Arc<Graph<O>>,
    pub foldable: Vec<bool>,
    pub source_certified: Vec<bool>,
    pub count: usize,
    pub updates: Vec<Id>,
    pub effects: Vec<Id>,
    pub contributions: Vec<Vec<Id>>,
    pub bounds: Vec<Vec<(Id, Id)>>,
    pub operators: Vec<Option<OperatorView>>,
    pub guards: Vec<Guard>,
    selectors: Vec<Selector>,
    pub actions: Vec<(usize, Vec<usize>)>,
    fired: Arc<Vec<usize>>,
    pub displays: Vec<(usize, String, Vec<Id>, ir::Origin)>,
    pub point_states: Vec<Option<f64>>,
    pub point_operators: Vec<Option<f64>>,
    pub base: Arc<LocalState>,
    pub work: Work,
    // Immutable values of this source-position activation. Certified parameter
    // nodes must not be replayed with an invented all-zero voltage frame.
    captured: Arc<Vec<Cell>>,
    branched: bool,
    cell: Arc<std::sync::OnceLock<Arc<crate::procedure_cell::Certificate>>>,
    observation: Arc<std::sync::OnceLock<Vec<f64>>>,
    // Decision 22: the roundings of program values on a same-time cycle,
    // recorded by the activation solves of this Plan, or taken over from a
    // later closure solve of the same activation, keyed by what they read:
    // the voltages of the marked nodes and the states before. Numeric values
    // read them for exactly these inputs; a marked value without its record
    // is refused, never executed.
    same_time: Arc<std::sync::Mutex<SameTimeRecords>>,
    // The procedure values on same-time cycles of this Plan's circuit and the
    // physical nodes their roundings read, from the circuit's structure.
    same_time_marks: Arc<std::sync::OnceLock<SameTimeMarks>>,
    // Exact driven source values of an observation, by node, for the exact
    // equation of a same-time cycle.
    exact_driven: Arc<std::sync::OnceLock<Vec<Option<num_rational::BigRational>>>>,
    identity: Vec<u8>,
}
#[derive(Default)]
struct SameTimeRecords {
    records: std::collections::BTreeMap<Vec<u64>, ActivationRecord>,
    // Keys taken over with values different from this Plan's own record;
    // they are read as missing.
    conflicting: std::collections::BTreeSet<Vec<u64>>,
}
impl SameTimeRecords {
    /// Upper bound on B-tree levels. The pinned Rust B-tree has at least six
    /// children per non-root internal node. The extra level covers root splits.
    fn levels(len: usize) -> u64 {
        let mut size = len;
        let mut levels = 2u64;
        while size >= 6 {
            size /= 6;
            levels += 1;
        }
        levels
    }
    /// One tree access compares at most eleven keys per level. A u64 word
    /// comparison is one work unit. The 16 units per level fund moving fixed
    /// key/value handles and allocating/splitting a node; this is a work bound,
    /// not a claim that work units equal malloc bytes. No old key is rehashed.
    fn reserve_key(&self, words: usize, map_ops: u64, set_ops: u64, w: &Work) -> Result<(), Error> {
        self.reserve_key_for(words, map_ops, set_ops, 0, w)
    }
    fn reserve_key_for(
        &self,
        words: usize,
        map_ops: u64,
        set_ops: u64,
        growth: usize,
        w: &Work,
    ) -> Result<(), Error> {
        let levels = Self::levels(self.records.len().saturating_add(growth))
            .saturating_mul(map_ops)
            .saturating_add(
                Self::levels(self.conflicting.len().saturating_add(growth)).saturating_mul(set_ops),
            );
        w.debit(
            2,
            (words as u64)
                .saturating_mul(11)
                .saturating_add(16)
                .saturating_mul(levels)
                .saturating_add(64),
        )
    }
    /// Reserve the whole transfer before changing marks, entries or tombstones.
    /// Entry-count metadata funds the iterator walk before it begins. Every
    /// source key then buys its bounded target lookup and tree mutation. Q limb
    /// traversal/copy/destruction uses the immutable record's O(1) cost summary.
    fn reserve_adoption(&self, source: &Self, mark_cost: u64, w: &Work) -> Result<(), Error> {
        w.debit(
            2,
            (source.records.len() as u64)
                .saturating_add(source.conflicting.len() as u64)
                .saturating_mul(64)
                .saturating_add(mark_cost)
                .saturating_add(128),
        )?;
        let growth = source
            .records
            .len()
            .saturating_add(source.conflicting.len());
        for key in &source.conflicting {
            self.reserve_key_for(key.len(), 1, 1, growth, w)?;
            w.debit(2, (key.len() as u64).saturating_mul(16).saturating_add(64))?;
            if let Some(old) = self.records.get(key) {
                w.debit(2, old.copy_cost())?;
            }
        }
        for (key, record) in &source.records {
            self.reserve_key_for(key.len(), 3, 2, growth, w)?;
            w.debit(
                2,
                (key.len() as u64)
                    .saturating_mul(16)
                    .saturating_add(record.copy_cost())
                    .saturating_add(64),
            )?;
            // The lookup itself was paid above, before accessing the old entry.
            if let Some(old) = self.records.get(key) {
                w.debit(2, old.copy_cost())?;
            }
        }
        Ok(())
    }
}
type SharedPhysical = Arc<PhysicalFrame>;
/// One certified activation. Program values are stored RN values; physical
/// values remain exact enclosures until an operation or store rounds them.
/// The physical vector is immutable and shared, never deep-cloned on adoption.
#[derive(Clone)]
struct ActivationRecord {
    values: Vec<(Id, f64)>,
    physical: SharedPhysical,
    physical_cost: u64,
}
impl ActivationRecord {
    fn copy_cost(&self) -> u64 {
        (self.values.len() as u64)
            .saturating_mul(32)
            .saturating_add(self.physical_cost)
            .saturating_add(128)
    }
    fn same(&self, other: &Self) -> bool {
        self.values.len() == other.values.len()
            && self
                .values
                .iter()
                .zip(&other.values)
                .all(|(a, b)| a.0 == b.0 && a.1.to_bits() == b.1.to_bits())
            // Ratio::eq may divide and allocate for unequal denominators.
            // Compare the stored proof representation directly, within the
            // prepaid limb traversal. Different representations conservatively
            // conflict; equality never invents a new mathematical proof.
            && (Arc::ptr_eq(&self.physical, &other.physical)
                || (self.physical.exact_reads == other.physical.exact_reads
                    && self.physical.values.len() == other.physical.values.len()
                    && self.physical.values.iter().zip(&other.physical.values).all(|(a,b)| match (a,b) {
                        (None,None) => true,
                        (Some(a),Some(b)) => [&a.lo,&a.hi].into_iter().zip([&b.lo,&b.hi])
                            .all(|(a,b)| a.numer() == b.numer() && a.denom() == b.denom()),
                        _ => false,
                    })))
    }
}
#[derive(Default)]
struct StoredActivation {
    given: Vec<(Id, f64)>,
    missing: Vec<Id>,
    physical: Option<SharedPhysical>,
}
struct SameTimeMarks {
    ids: Vec<Id>,
    reads: Vec<usize>,
}
impl PartialEq for Plan {
    fn eq(&self, other: &Self) -> bool {
        self.identity == other.identity
    }
}
impl Eq for Plan {}

struct Builder<'a> {
    p: &'a Program,
    w: &'a Work,
    domain: Domain<'a>,
    graph: Graph<O>,
    values: Vec<Cell>,
    physical_values: Vec<bool>,
    // Values that read a node without an input bound (a solved voltage).
    solved_values: Vec<bool>,
    // Depth of statements and values selected by a condition of this activation.
    selected: usize,
    // Values stored by an assignment of this activation (latched reads).
    stored: Vec<bool>,
    states: Vec<Id>,
    initial: Vec<Id>,
    bindings: Vec<Option<Id>>,
    owner: &'a str,
    procedure: usize,
    event: usize,
    event_loop_iterations: usize,
    fired: &'a [usize],
    effects: Vec<Id>,
    contributions: Vec<Vec<Id>>,
    bounds: Vec<Vec<(Id, Id)>>,
    operators: Vec<Option<OperatorView>>,
    capturing: Vec<bool>,
    operator_values: Vec<Option<Id>>,
    actions: Vec<(usize, Vec<usize>)>,
    displays: Vec<(usize, String, Vec<Id>, ir::Origin)>,
    decisions: Vec<bool>,
    guards: Vec<Guard>,
    selectors: Vec<Selector>,
}
impl Builder<'_> {
    fn add(&mut self, operation: O, operands: Vec<Id>) -> Result<Id, Error> {
        self.w.debit(2, (operands.len() * 32 + 72) as u64)?;
        let physical = matches!(&operation,O::Affine{terms,..} if terms.iter().any(|t|t.node!=0&&t.coefficient!=0.))
            || operands.iter().any(|&id| self.physical_values[id]);
        let solved = matches!(&operation,O::Affine{terms,..} if terms.iter().any(|t|t.node!=0&&t.coefficient!=0.
                &&self.domain.node_bounds.get(t.node).is_none_or(|b|!b.finite())))
            || operands.iter().any(|&id| self.solved_values[id]);
        let args = operands
            .iter()
            .map(|&id| {
                self.values
                    .get(id)
                    .ok_or_else(|| invalid("procedure dependency missing"))?
                    .copy(self.w)
            })
            .collect::<Result<Vec<_>, _>>()?;
        let value = operation.evaluate(&args, &self.domain, self.w)?;
        let id = arena(
            self.graph
                .append(operation, operands, &mut |n| self.w.debit(2, n)),
        )?;
        if self.values.len() == self.values.capacity() {
            let next = self.values.capacity().max(1).saturating_mul(2);
            self.w.debit(
                2,
                ((next + self.values.len()) * std::mem::size_of::<Cell>()) as u64,
            )?;
            self.values.reserve_exact(next - self.values.len());
        }
        self.w.debit(2, 16)?;
        self.physical_values.push(physical);
        self.solved_values.push(solved);
        self.stored.push(false);
        self.values.push(value);
        Ok(id)
    }
    fn o(&self, o: &ir::Origin) -> Result<Arc<ir::Origin>, Error> {
        Ok(Arc::new(origin_copy(o, self.w)?))
    }
    fn effect(&mut self, id: Id) -> Result<(), Error> {
        self.w.debit(2, 16)?;
        self.effects.push(id);
        Ok(())
    }
    fn integer(&mut self, arg: &ir::IntegerOperand) -> Result<Id, Error> {
        self.w.step()?;
        match arg {
            ir::IntegerOperand::IntegerLiteral { value } => {
                self.add(O::Literal(f64::from(*value)), Vec::new())
            }
            ir::IntegerOperand::IntegerState { state } => self
                .states
                .get(*state)
                .copied()
                .ok_or_else(|| invalid("integer state out of range")),
            ir::IntegerOperand::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                let args = args
                    .iter()
                    .map(|a| self.integer(a))
                    .collect::<Result<Vec<_>, _>>()?;
                let o = self.o(origin)?;
                self.add(O::Integer(*function, o), args)
            }
        }
    }
    fn resolve(&mut self, e: &E) -> Result<Id, Error> {
        self.w.step()?;
        match e {
            E::State { state } => self
                .states
                .get(*state)
                .copied()
                .ok_or_else(|| invalid("procedure state out of range")),
            E::RealCall {
                bindings,
                body,
                result,
                ..
            } => {
                self.w.debit(2, (bindings.len() * 128 + 128) as u64)?;
                for &binding in bindings {
                    self.w.step()?;
                    if binding >= self.bindings.len() {
                        return Err(invalid("call binding out of range"));
                    }
                }
                let mut saved = Vec::with_capacity(bindings.len());
                for &binding in bindings {
                    saved.push((binding, self.bindings[binding].take()));
                }
                let resolved = (|| {
                    self.steps(body)?;
                    let id = self.resolve(result)?;
                    self.effect(id)?;
                    Ok(id)
                })();
                // All restore storage and work was prepaid before mutation.
                // Restoring cannot fail even when the child exhausted Work.
                for (binding, value) in saved {
                    self.bindings[binding] = value;
                }
                resolved
            }
            E::UnsupportedSystemCall {
                function,
                args,
                origin,
                ..
            } => {
                for arg in args {
                    let id = self.resolve(arg)?;
                    self.effect(id)?;
                }
                Err(Error::new(
                    "unsupported_system_function",
                    format!(
                        "selected ${function} has no certified runtime implementation at {}",
                        origin.label()
                    ),
                ))
            }
            E::RealLocal { binding } => {
                if self
                    .p
                    .real_bindings
                    .get(*binding)
                    .is_none_or(|b| b.procedure_id != self.procedure)
                {
                    return Err(invalid("real local belongs to another procedure"));
                }
                self.bindings
                    .get(*binding)
                    .copied()
                    .flatten()
                    .ok_or_else(|| invalid("real local used before its source binding"))
            }
            E::Affine { constant, terms } => {
                // An empty wire affine is already one binary64 literal.
                // Preserve every nonempty dependency and every RN boundary.
                if terms.is_empty() {
                    return self.add(O::Literal(*constant), Vec::new());
                }
                self.w.debit(
                    2,
                    (terms.len() * std::mem::size_of::<ir::Term>() + 32) as u64,
                )?;
                self.add(
                    O::Affine {
                        constant: *constant,
                        terms: Arc::from(terms.as_slice()),
                    },
                    Vec::new(),
                )
            }
            E::RealBinary {
                operation,
                left,
                right,
                origin,
            } => {
                let a = self.resolve(left)?;
                let b = self.resolve(right)?;
                let o = self.o(origin)?;
                self.add(O::Real(*operation, o), vec![a, b])
            }
            E::RealBoundary {
                value,
                kind,
                origin,
            } => {
                let a = self.resolve(value)?;
                let o = self.o(origin)?;
                self.add(O::Boundary(*kind, o), vec![a])
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                let a = self.resolve(left)?;
                let b = self.resolve(right)?;
                self.add(
                    match e {
                        E::Add { .. } => O::Add,
                        E::Multiply { .. } => O::Multiply,
                        _ => O::Divide,
                    },
                    vec![a, b],
                )
            }
            E::Power { base, exponent } => {
                let a = self.resolve(base)?;
                // A selected polynomial of a solved voltage stays outside the
                // condition contract of an ordinary analog activation.
                if self.selected > 0 && self.event == usize::MAX && self.solved_values[a] {
                    return Err(Error::new(
                        "unsupported_transient",
                        "polynomial transient equations are not supported: a power of a solved voltage is selected by an analog condition",
                    ));
                }
                self.add(O::Power(*exponent), vec![a])
            }
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                origin,
            } => {
                let yes = self.condition(*relation, left, right, origin)?;
                self.selected += 1;
                let value = self.resolve(if yes { then_value } else { else_value });
                self.selected -= 1;
                value
            }
            E::ArrayRead {
                states,
                index,
                first,
                last,
                origin,
            } => {
                let index = self.resolve(index)?;
                self.effect(index)?;
                let value = crate::event_numeric::checked_index(
                    self.values[index].bound()?,
                    *first,
                    *last,
                    origin,
                )?
                .lo;
                self.w.debit(2, 64)?;
                self.selectors.push(Selector { index, value });
                self.states
                    .get(states[(value - f64::from(*first)) as usize])
                    .copied()
                    .ok_or_else(|| invalid("array read state out of range"))
            }
            E::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                let args = args
                    .iter()
                    .map(|a| self.integer(a))
                    .collect::<Result<Vec<_>, _>>()?;
                let o = self.o(origin)?;
                self.add(O::Integer(*function, o), args)
            }
            E::IntegerRound { value, origin } | E::CheckedInteger { value, origin } => {
                let value = self.resolve(value)?;
                let o = self.o(origin)?;
                self.add(
                    if matches!(e, E::IntegerRound { .. }) {
                        O::IntegerRound(o)
                    } else {
                        O::CheckedInteger(o)
                    },
                    vec![value],
                )
            }
            E::CheckedIndex {
                index,
                first,
                last,
                origin,
            } => {
                let value = self.resolve(index)?;
                let o = self.o(origin)?;
                self.add(O::Index(*first, *last, o), vec![value])
            }
            E::EventMath {
                function,
                args,
                origin,
            } => {
                let args = args
                    .iter()
                    .map(|a| self.resolve(a))
                    .collect::<Result<Vec<_>, _>>()?;
                let o = self.o(origin)?;
                self.add(O::Math(*function, o), args)
            }
            E::Operator { operator } => {
                if self.operators.get(*operator).is_none() {
                    return Err(invalid("operator out of range"));
                }
                // A mathematical call executes at this actual source step,
                // including repeated loop iterations. Its input is captured
                // now; earlier graph IDs keep their own immutable operands.
                if matches!(
                    self.p.operators[*operator],
                    ir::OperatorSpec::Math { .. } | ir::OperatorSpec::Sin { .. }
                ) {
                    self.capture_operator(*operator)?;
                    let input = self.operators[*operator].as_ref().unwrap().input;
                    let (function, origin) = match &self.p.operators[*operator] {
                        ir::OperatorSpec::Math {
                            function, origin, ..
                        } => (crate::operators::Function::from(*function), origin),
                        ir::OperatorSpec::Sin { origin, .. } => {
                            (crate::operators::Function::Sin, origin)
                        }
                        _ => unreachable!(),
                    };
                    let origin = self.o(origin)?;
                    return self.add(O::Elementary(function, origin), vec![input]);
                }
                if self.operators[*operator].is_none() {
                    self.capture_operator(*operator)?;
                }
                if let Some(id) = self.operator_values[*operator] {
                    return Ok(id);
                }
                let input = self.operators[*operator].as_ref().unwrap().input;
                let id = match &self.p.operators[*operator] {
                    ir::OperatorSpec::Math {
                        function, origin, ..
                    } => {
                        let o = self.o(origin)?;
                        self.add(O::Elementary((*function).into(), o), vec![input])?
                    }
                    ir::OperatorSpec::Sin { origin, .. } => {
                        let o = self.o(origin)?;
                        self.add(
                            O::Elementary(crate::operators::Function::Sin, o),
                            vec![input],
                        )?
                    }
                    _ => self.add(O::Operator(*operator), Vec::new())?,
                };
                self.operator_values[*operator] = Some(id);
                Ok(id)
            }
            E::Forcing { .. } => Err(Error::new(
                "unsupported_forcing_scope",
                "procedure forcing requires its original component dispatcher",
            )),
        }
    }
    fn condition(
        &mut self,
        relation: ir::Relation,
        left: &E,
        right: &E,
        origin: &ir::Origin,
    ) -> Result<bool, Error> {
        self.decide(relation, left, right, origin)?
    }
    /// Ok(Err): a comparison of a body that reads at tau+ is exactly zero at
    /// its crossing root and has no post-root certificate (right_limit).
    fn decide(
        &mut self,
        relation: ir::Relation,
        left: &E,
        right: &E,
        origin: &ir::Origin,
    ) -> Result<Result<bool, Error>, Error> {
        let left = self.resolve(left)?;
        let right = self.resolve(right)?;
        self.effect(left)?;
        self.effect(right)?;
        let a = &self.values[left];
        let b = &self.values[right];
        let compared = control::compare(relation, a, b, self.w)?;
        let post = self.event != usize::MAX && crate::event_conditions::post_root_reads(self.event);
        let decided = if post {
            match right_limit::decide(self, relation, left, right, compared, origin)? {
                right_limit::Outcome::Decided(value, post_root) => Some((value, post_root)),
                right_limit::Outcome::Unsided(error) => return Ok(Err(error)),
                right_limit::Outcome::Undecided => None,
            }
        } else {
            compared.map(|value| (value, false))
        };
        let Some((value, post_root)) = decided else {
            self.w.debit(
                2,
                (origin.source.len() + origin.instance.len())
                    .saturating_mul(2)
                    .saturating_add(256) as u64,
            )?;
            return Err(Error::new("event_condition",format!("procedure condition is not certified over its complete source-position enclosure at {}",origin.label())));
        };
        self.w.debit(2, 64)?;
        self.guards.push(Guard {
            relation,
            left,
            right,
            value,
            post_root,
        });
        self.decisions.push(value);
        Ok(Ok(value))
    }
    fn capture_operator(&mut self, index: usize) -> Result<(), Error> {
        self.w.step()?;
        if self.capturing[index] {
            return Err(invalid("operator call-site dependency cycle"));
        }
        self.capturing[index] = true;
        let spec = &self.p.operators[index];
        let input = match spec {
            ir::OperatorSpec::Ddt { input, .. }
            | ir::OperatorSpec::Idt { input, .. }
            | ir::OperatorSpec::IdtMod { input, .. }
            | ir::OperatorSpec::Math { input, .. }
            | ir::OperatorSpec::Sin { input, .. }
            | ir::OperatorSpec::AbsDelay { input, .. }
            | ir::OperatorSpec::Transition { input, .. }
            | ir::OperatorSpec::Slew { input, .. }
            | ir::OperatorSpec::LaplaceNd { input, .. } => input,
        };
        let input = self.resolve(input)?;
        self.effect(input)?;
        let reset = if let ir::OperatorSpec::Idt {
            reset: Some(reset), ..
        } = spec
        {
            let r = self.resolve(reset)?;
            self.effect(r)?;
            Some(r)
        } else {
            None
        };
        self.operators[index] = Some(OperatorView { input, reset });
        self.capturing[index] = false;
        Ok(())
    }
    fn checked_store(
        &mut self,
        state: usize,
        value: Id,
        origin: Option<&ir::Origin>,
    ) -> Result<Id, Error> {
        self.w.step()?;
        if self
            .p
            .states
            .get(state)
            .is_none_or(|s| s.kind != ir::StateKind::Integer)
        {
            return Ok(value);
        }
        let origin = origin.map(|o| self.o(o)).transpose()?;
        // The arena receives an already allocated operand buffer. Fund it
        // before vec! allocates, independently of add's retained-storage fee.
        self.w.debit(2, (std::mem::size_of::<Id>() + 32) as u64)?;
        self.add(O::IntegerStore(state, origin), vec![value])
    }
    fn statements(&mut self, body: &[S], index: &mut usize) -> Result<(), Error> {
        for s in body {
            self.w.step()?;
            match s {
                S::Assign(a) => {
                    if self
                        .p
                        .states
                        .get(a.state)
                        .is_none_or(|s| s.instance != self.owner)
                    {
                        return Err(invalid("procedure assignment owner mismatch"));
                    }
                    let value = self.resolve(&a.rhs)?;
                    let p = self.p;
                    let value = self.checked_store(
                        a.state,
                        value,
                        p.events.get(self.event).map(|e| &e.origin),
                    )?;
                    self.effect(value)?;
                    self.stored[value] = true;
                    self.states[a.state] = value;
                    if self.event != usize::MAX {
                        self.actions.last_mut().unwrap().1.push(*index);
                    }
                    *index += 1;
                }
                S::ArrayWrite {
                    states,
                    index: idx,
                    rhs,
                    first,
                    last,
                    origin,
                } => {
                    let id = self.resolve(idx)?;
                    self.effect(id)?;
                    let value = crate::event_numeric::checked_index(
                        self.values[id].bound()?,
                        *first,
                        *last,
                        origin,
                    )?
                    .lo;
                    self.w.debit(2, 64)?;
                    self.selectors.push(Selector { index: id, value });
                    let slot = (value - f64::from(*first)) as usize;
                    let rhs = self.resolve(rhs)?;
                    let rhs = self.checked_store(states[slot], rhs, Some(origin))?;
                    self.effect(rhs)?;
                    self.stored[rhs] = true;
                    self.states[states[slot]] = rhs;
                    if self.event != usize::MAX {
                        self.actions.last_mut().unwrap().1.push(*index + slot);
                    }
                    *index += states.len();
                }
                S::Display {
                    format,
                    args,
                    origin,
                } => {
                    self.w
                        .debit(2, (format.len() + args.len() * 16 + 64) as u64)?;
                    let args = args
                        .iter()
                        .map(|e| self.resolve(e))
                        .collect::<Result<Vec<_>, _>>()?;
                    for &id in &args {
                        self.effect(id)?;
                    }
                    self.w.debit(2, (format.len() + 32) as u64)?;
                    let origin = origin_copy(origin, self.w)?;
                    self.displays
                        .push((self.event, format.clone(), args, origin));
                }
                S::If {
                    relation,
                    left,
                    right,
                    then_body,
                    else_body,
                    origin,
                } => {
                    let yes = match self.decide(*relation, left, right, origin)? {
                        Ok(yes) => yes,
                        // Without a tau+ certificate only identical arms continue.
                        Err(error) => {
                            if !right_limit::same_arms(then_body, else_body, self.w)? {
                                return Err(error);
                            }
                            self.w.debit(2, 16)?;
                            self.decisions.extend([false, true]);
                            crate::diagnostics::counter("event_equivalent_branch_proofs", 1);
                            true
                        }
                    };
                    let start = *index;
                    let yes_count = count(then_body, self.w)?;
                    self.selected += 1;
                    if yes {
                        self.statements(then_body, index)?;
                    } else {
                        *index = start + yes_count;
                        self.statements(else_body, index)?;
                    }
                    self.selected -= 1;
                    *index = start + yes_count + count(else_body, self.w)?;
                }
                S::Loop {
                    initialize,
                    relation,
                    left,
                    right,
                    body,
                    update,
                    origin,
                } => {
                    self.statements(initialize, index)?;
                    let start = *index;
                    let update_start = start + count(body, self.w)?;
                    let end = update_start + count(update, self.w)?;
                    while self.condition(*relation, left, right, origin)? {
                        // One event shares the original 4096 allowance across
                        // sibling and nested loops. The request Work owner is
                        // still charged by every executed operation.
                        if self.event != usize::MAX {
                            if self.event_loop_iterations >= 4096 {
                                return Err(Error::new(
                                    "event_loop_budget",
                                    format!(
                                        "event exceeds 4096 total loop iterations at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            self.event_loop_iterations += 1;
                        }
                        let mut i = start;
                        self.statements(body, &mut i)?;
                        i = update_start;
                        self.statements(update, &mut i)?;
                    }
                    *index = end;
                }
            }
        }
        Ok(())
    }
    fn steps(&mut self, steps: &[ProcedureStep]) -> Result<(), Error> {
        for step in steps {
            self.w.step()?;
            match &step.action {
                A::Statement(s) => self.statements(std::slice::from_ref(s), &mut 0)?,
                A::Control(C::RealBind { binding, value, .. }) => {
                    let value = self.resolve(value)?;
                    self.effect(value)?;
                    self.bindings[*binding] = Some(value);
                }
                A::Control(C::EventGate { event }) => {
                    self.w.debit(2, self.fired.len() as u64)?;
                    if self.fired.contains(event) {
                        self.w.debit(2, 16)?;
                        self.actions.push((*event, Vec::new()));
                        self.event = *event;
                        self.event_loop_iterations = 0;
                        self.statements(&self.p.events[*event].body, &mut 0)?;
                        self.event = usize::MAX;
                    }
                }
                A::Control(C::ContributionCapture { contribution }) => {
                    let id = self.resolve(&self.p.contributions[*contribution].rhs)?;
                    self.effect(id)?;
                    self.w.debit(2, 16)?;
                    self.contributions[*contribution].push(id);
                }
                A::Control(C::StepBoundCapture { step_bound }) => {
                    let b = &self.p.step_bounds[*step_bound];
                    let v = self.resolve(&b.value)?;
                    let a = self.resolve(&b.active)?;
                    self.effect(v)?;
                    self.effect(a)?;
                    self.w.debit(2, 32)?;
                    self.bounds[*step_bound].push((v, a));
                }
                A::Control(C::ProcedureIf {
                    relation,
                    left,
                    right,
                    then_body,
                    else_body,
                    origin,
                }) => {
                    match self.condition(*relation, left, right, origin) {
                        Ok(yes) => {
                            self.selected += 1;
                            self.steps(if yes { then_body } else { else_body })?;
                            self.selected -= 1;
                        }
                        Err(error)
                            if error.kind == "event_condition"
                                && mesh_only(then_body, self.w)?
                                && mesh_only(else_body, self.w)? =>
                        {
                            // Mesh-only alternatives may conservatively request
                            // either cap. No program assignment, gate or physical
                            // contribution is executed speculatively here.
                            self.w.debit(2, 16)?;
                            self.decisions.extend([false, true]);
                            self.steps(then_body)?;
                            self.steps(else_body)?;
                        }
                        Err(error) => return Err(error),
                    }
                }
                A::Control(C::ProcedureLoop {
                    initialize,
                    relation,
                    left,
                    right,
                    body,
                    update,
                    origin,
                }) => {
                    self.steps(initialize)?;
                    while self.condition(*relation, left, right, origin)? {
                        self.steps(body)?;
                        self.steps(update)?;
                    }
                }
            }
        }
        Ok(())
    }
}
fn mesh_only(steps: &[ProcedureStep], w: &Work) -> Result<bool, Error> {
    for s in steps {
        w.step()?;
        match &s.action {
            A::Control(C::StepBoundCapture { .. }) => {}
            A::Control(C::ProcedureIf {
                then_body,
                else_body,
                ..
            }) => {
                if !mesh_only(then_body, w)? || !mesh_only(else_body, w)? {
                    return Ok(false);
                }
            }
            _ => return Ok(false),
        }
    }
    Ok(true)
}
fn count(body: &[S], w: &Work) -> Result<usize, Error> {
    let mut n = 0;
    for s in body {
        w.step()?;
        n += match s {
            S::Assign(_) => 1,
            S::ArrayWrite { states, .. } => states.len(),
            S::If {
                then_body,
                else_body,
                ..
            } => count(then_body, w)? + count(else_body, w)?,
            S::Loop {
                initialize,
                body,
                update,
                ..
            } => count(initialize, w)? + count(body, w)? + count(update, w)?,
            _ => 0,
        };
    }
    Ok(n)
}

impl Plan {
    #[cfg(test)]
    pub(crate) fn test_cell_certificate(&self) -> Option<&crate::procedure_cell::Certificate> {
        self.cell.get().map(AsRef::as_ref)
    }
    pub(crate) fn cell_bounds(
        &self,
        inputs: &[I],
        values: &[f64],
        n: usize,
    ) -> Result<Option<Vec<I>>, Error> {
        let Some(cell) = self.cell.get() else {
            return Ok(None);
        };
        if cell.matches(inputs, &self.base, Some(values), &self.work)? {
            cell.bounds(n, &self.work).map(Some)
        } else {
            Ok(None)
        }
    }
    pub(crate) fn try_cell(
        &self,
        p: &Program,
        driven: &[usize],
        inputs: &[f64],
        original_inputs: usize,
        node_count: usize,
        ids: &[Id],
    ) -> Result<Option<Vec<f64>>, Error> {
        self.work.debit(2, 0)?;
        if self.branched || !self.point_operators.is_empty() {
            return Ok(None);
        }
        self.work.debit(2, (original_inputs * 16 + 32) as u64)?;
        let inputs_bounds = inputs[..original_inputs]
            .iter()
            .copied()
            .map(I::point)
            .collect::<Vec<_>>();
        if let Some(cell) = self.cell.get() {
            if cell.matches(&inputs_bounds, &self.base, None, &self.work)? {
                self.work.debit(2, (cell.values.len() * 8 + 32) as u64)?;
                return Ok(Some(cell.values.clone()));
            }
        }
        let Some(cell) = crate::procedure_cell::certify(
            p,
            driven,
            inputs,
            original_inputs,
            node_count,
            ids,
            &self.graph,
            self.count,
            &self.base,
            &self.point_states,
            &self.base,
            &self.updates,
            &self.work,
        )?
        else {
            return Ok(None);
        };
        self.work.debit(2, (cell.values.len() * 8 + 32) as u64)?;
        let values = cell.values.clone();
        let _ = self.cell.set(cell);
        Ok(Some(values))
    }
    pub(crate) fn has_observation(&self) -> bool {
        self.observation.get().is_some()
    }
    /// A sufficient total-domain proof for every active source-position node.
    /// Builder emits only selected branches, but retains overwritten effects,
    /// unused RealBind values, displays, updates and condition operands here.
    /// A guard depending on candidate voltages needs a global branch proof.
    pub(crate) fn total_activation_domain(&self, w: &Work) -> Result<bool, Error> {
        w.debit(2, (self.count as u64).saturating_mul(8).saturating_add(64))?;
        let mut voltage = vec![false; self.count];
        for id in 0..self.count {
            w.step()?;
            let node = self
                .graph
                .node(id)
                .ok_or_else(|| invalid("missing activation node"))?;
            w.debit(
                2,
                (node.operands.len() as u64)
                    .saturating_mul(16)
                    .saturating_add(32),
            )?;
            let live = match &node.operation {
                O::Affine { terms, .. } => {
                    w.debit(
                        2,
                        (terms.len() as u64).saturating_mul(16).saturating_add(32),
                    )?;
                    terms.iter().any(|t| t.node != 0 && t.coefficient != 0.)
                }
                _ => node.operands.iter().any(|&i| voltage[i]),
            };
            voltage[id] = live;
            let total = match &node.operation {
                O::Literal(_)
                | O::Affine { .. }
                | O::State(_)
                | O::Operator(_)
                | O::Add
                | O::Multiply
                | O::Power(_)
                | O::Boundary(..) => true,
                O::Real(op, _) if !matches!(op, ir::RealOperation::Divide) => true,
                O::Divide | O::Real(ir::RealOperation::Divide, _) => {
                    node.operands.get(1).is_some_and(|&i| {
                        !voltage[i]
                            && self.captured[i]
                                .image
                                .is_some_and(|b| b.lo > 0. || b.hi < 0.)
                    })
                }
                // Candidate-independent partial operations were certified while
                // constructing this active path. No candidate can change them.
                _ => !live && self.captured[id].image.is_some(),
            };
            if !total {
                return Ok(false);
            }
        }
        for guard in &self.guards {
            w.step()?;
            if voltage[guard.left] || voltage[guard.right] {
                return Ok(false);
            }
        }
        for selector in &self.selectors {
            w.step()?;
            if voltage[selector.index] {
                return Ok(false);
            }
        }
        Ok(true)
    }
    /// Mark the procedure values on same-time cycles of this Plan's circuit
    /// and the physical nodes their roundings read (decision 22), once.
    pub(crate) fn mark_same_time(&self, ids: Vec<Id>, reads: Vec<usize>) -> Result<(), Error> {
        self.work
            .debit(2, ((ids.len() + reads.len()) * 8 + 64) as u64)?;
        let _ = self.same_time_marks.set(SameTimeMarks { ids, reads });
        Ok(())
    }
    /// The record key of these inputs: the bits of the marked voltages
    /// (ground excluded) and of the states before.
    fn same_time_key(&self, voltages: &[f64], before: &[f64], w: &Work) -> Result<Vec<u64>, Error> {
        self.work.debit(2, 0)?;
        if !self.work.same_owner(w) {
            return Err(invalid(
                "same-time key has a different request proof account",
            ));
        }
        let reads = self.same_time_marks.get().map(|m| m.reads.as_slice());
        let length = reads.map_or(voltages.len(), <[usize]>::len) + before.len();
        w.debit(2, (length * 16 + 32) as u64)?;
        // Reserve the complete key once. Collecting reads first and then
        // appending states could allocate a second, larger buffer.
        let mut key = Vec::with_capacity(length);
        match reads {
            Some(reads) => key.extend(
                reads
                    .iter()
                    .map(|&node| voltages.get(node).map_or(u64::MAX, |v| v.to_bits())),
            ),
            None => key.extend(voltages.iter().skip(1).map(|v| v.to_bits())),
        }
        key.extend(before.iter().map(|v| v.to_bits()));
        Ok(key)
    }
    /// Record the decision 22 roundings an activation solve found for these
    /// voltages and states, replacing an earlier record of the same inputs.
    /// Records are kept for the life of the Plan; each is paid.
    pub(crate) fn record_same_time(
        &self,
        voltages: &[f64],
        before: &[f64],
        values: Vec<(Id, f64)>,
        physical: PhysicalFrame,
    ) -> Result<(), Error> {
        let key = self.same_time_key(voltages, before, &self.work)?;
        let mut records = self
            .same_time
            .lock()
            .map_err(|_| invalid("same-time rounding record is poisoned"))?;
        // Buy the cost calculation before traversing variable-sized proof slots.
        self.work.debit(
            2,
            (physical.values.len() as u64)
                .saturating_mul(128)
                .saturating_add(physical.exact_reads.len() as u64)
                .saturating_add(16),
        )?;
        // This certified solve is the sole entry that clears a tombstone.
        let mut physical_cost = (physical.values.len() as u64)
            .saturating_mul(128)
            .saturating_add(physical.exact_reads.len() as u64);
        for q in physical.values.iter().flatten() {
            self.work.step()?;
            for r in [&q.lo, &q.hi] {
                physical_cost =
                    physical_cost.saturating_add((r.numer().bits() + r.denom().bits()).div_ceil(8));
            }
        }
        records.reserve_key(key.len(), 1, 1, &self.work)?;
        self.work.debit(2, physical_cost.saturating_add(64))?;
        let record = ActivationRecord {
            values,
            physical: Arc::new(physical),
            physical_cost,
        };
        let SameTimeRecords {
            records,
            conflicting,
        } = &mut *records;
        match records.entry(key) {
            std::collections::btree_map::Entry::Occupied(mut entry) => {
                self.work.debit(2, entry.get().copy_cost())?;
                conflicting.remove(entry.key());
                entry.insert(record);
            }
            std::collections::btree_map::Entry::Vacant(entry) => {
                conflicting.remove(entry.key());
                entry.insert(record);
            }
        }
        Ok(())
    }
    /// The decision 22 roundings recorded for these voltages and states.
    pub(crate) fn same_time_record(
        &self,
        voltages: &[f64],
        before: &[f64],
    ) -> Result<Option<Vec<(Id, f64)>>, Error> {
        Ok(self
            .same_time_values(voltages, before, &self.work)?
            .map(|r| r.values))
    }
    fn same_time_values(
        &self,
        voltages: &[f64],
        before: &[f64],
        w: &Work,
    ) -> Result<Option<ActivationRecord>, Error> {
        let key = self.same_time_key(voltages, before, w)?;
        let records = self
            .same_time
            .lock()
            .map_err(|_| invalid("same-time rounding record is poisoned"))?;
        records.reserve_key(key.len(), 1, 1, w)?;
        if records.conflicting.contains(&key) {
            return Ok(None);
        }
        let found = records.records.get(&key);
        if let Some(record) = found {
            w.debit(2, record.copy_cost())?;
        }
        Ok(found.cloned())
    }
    /// The decision 22 values a numeric read of `roots` uses (`stored`): the
    /// record of these inputs, and, when the roots read a marked value it does
    /// not hold, the marked values to refuse. An unmarked Plan, or an executed
    /// read, uses neither. Effect roots without a record are checked with
    /// executed values; they are never published.
    fn stored_same_time(
        &self,
        stored: bool,
        roots: &[Id],
        nodes: &[f64],
        before: &[f64],
        w: &Work,
    ) -> Result<StoredActivation, Error> {
        let Some(marks) = self
            .same_time_marks
            .get()
            .filter(|m| stored && !m.ids.is_empty())
        else {
            return Ok(StoredActivation::default());
        };
        let record = self.same_time_values(nodes, before, w)?;
        let (given, physical) = match record {
            Some(r) => (r.values, Some(r.physical)),
            None => (Vec::new(), None),
        };
        w.debit(
            2,
            (marks.ids.len() as u64)
                .saturating_mul((given.len() as u64).saturating_add(1))
                .saturating_mul(16)
                .saturating_add(32),
        )?;
        let missing = marks
            .ids
            .iter()
            .copied()
            .filter(|id| !given.iter().any(|(given, _)| given == id))
            .collect::<Vec<_>>();
        if missing.is_empty() || !self.reaches(roots, &missing, w)? {
            return Ok(StoredActivation {
                given,
                physical,
                missing: Vec::new(),
            });
        }
        Ok(StoredActivation {
            given,
            missing,
            physical,
        })
    }
    /// Whether some root reads one of `targets` (itself or through operands).
    fn reaches(&self, roots: &[Id], targets: &[Id], w: &Work) -> Result<bool, Error> {
        w.debit(2, (self.count * 8 + 64) as u64)?;
        let mut seen = vec![false; self.count];
        let mut stack = roots.to_vec();
        while let Some(id) = stack.pop() {
            w.step()?;
            if id >= self.count || std::mem::replace(&mut seen[id], true) {
                continue;
            }
            if targets.contains(&id) {
                return Ok(true);
            }
            if let Some(node) = self.graph.node(id) {
                stack.extend_from_slice(&node.operands);
            }
        }
        Ok(false)
    }
    /// Decision 22: take over the same-time roundings that a later solve of the
    /// same activation path (equal identity: a closure iteration of the same
    /// event) recorded, so this Plan's readers at that solve's voltages read
    /// them. A key this Plan recorded with different values is then read as
    /// missing.
    pub(crate) fn adopt_same_time(&self, other: &Plan) -> Result<(), Error> {
        // Sticky entry check precedes even an identity comparison or fast path.
        self.work.debit(2, 64)?;
        if !self.work.same_owner(&other.work) {
            return Err(invalid(
                "same-time records have different request proof accounts",
            ));
        }
        if Arc::ptr_eq(&self.same_time, &other.same_time) {
            return Ok(());
        }
        self.work.debit(
            2,
            (self.identity.len() as u64)
                .saturating_add(other.identity.len() as u64)
                .saturating_mul(2)
                .saturating_add(64),
        )?;
        if self.identity != other.identity {
            return Ok(());
        }
        // Lock both owners in a fixed address order. Reserve the complete
        // transfer before cloning keys/values or changing either marks or
        // records. Borrow the immutable source directly; no snapshot is needed.
        self.work.debit(2, 64)?;
        let self_first = Arc::as_ptr(&self.same_time) < Arc::as_ptr(&other.same_time);
        let (first, second) = if self_first {
            (&self.same_time, &other.same_time)
        } else {
            (&other.same_time, &self.same_time)
        };
        let first = first
            .lock()
            .map_err(|_| invalid("same-time rounding record is poisoned"))?;
        let second = second
            .lock()
            .map_err(|_| invalid("same-time rounding record is poisoned"))?;
        let (source, mut ours) = if self_first {
            (second, first)
        } else {
            (first, second)
        };
        let marks = other.same_time_marks.get();
        let mark_cost = marks.map_or(0, |m| {
            (m.ids.len() as u64)
                .saturating_add(m.reads.len() as u64)
                .saturating_mul(16)
                .saturating_add(64)
        });
        ours.reserve_adoption(&source, mark_cost, &self.work)?;
        if self.same_time_marks.get().is_none() {
            if let Some(m) = marks {
                let _ = self.same_time_marks.set(SameTimeMarks {
                    ids: m.ids.clone(),
                    reads: m.reads.clone(),
                });
            }
        }
        for key in &source.conflicting {
            ours.records.remove(key);
            ours.conflicting.insert(key.clone());
        }
        for (key, record) in &source.records {
            match ours.records.get(key) {
                Some(old) if old.same(record) => {}
                Some(_) => {
                    ours.records.remove(key);
                    ours.conflicting.insert(key.clone());
                }
                None if ours.conflicting.contains(key) => {}
                None => {
                    ours.records.insert(key.clone(), record.clone());
                }
            }
        }
        Ok(())
    }
    /// Exact driven source values of this observation, by node.
    pub(crate) fn set_exact_driven(&self, values: Vec<Option<num_rational::BigRational>>) {
        let _ = self.exact_driven.set(values);
    }
    // Keep nominal/full boxes, source frame, and original Work explicit.
    #[allow(clippy::too_many_arguments)]
    fn evaluate(
        &self,
        execute_effects: bool,
        roots: &[Id],
        nodes: &[Option<f64>],
        node_bounds: &[I],
        states: &[Option<f64>],
        state_bounds: &[I],
        operators: &[Option<f64>],
        operator_bounds: &[I],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<Cell>, Error> {
        self.evaluate_with(
            execute_effects,
            roots,
            (nodes, node_bounds),
            (states, state_bounds),
            (operators, operator_bounds),
            context,
            &StoredActivation::default(),
            w,
        )
    }
    // `evaluate` with the decision 22 rounding of some values given and the
    // marked values without a record (`missing`) refused.
    #[allow(clippy::too_many_arguments)]
    fn evaluate_with(
        &self,
        execute_effects: bool,
        roots: &[Id],
        (nodes, node_bounds): (&[Option<f64>], &[I]),
        (states, state_bounds): (&[Option<f64>], &[I]),
        (operators, operator_bounds): (&[Option<f64>], &[I]),
        context: Option<&Context<'_>>,
        stored: &StoredActivation,
        w: &Work,
    ) -> Result<Vec<Cell>, Error> {
        w.debit(2, ((roots.len() + self.effects.len()) * 16 + 64) as u64)?;
        let fresh;
        let local = if context.is_none() {
            &*self.base
        } else {
            fresh = LocalState::try_with_context(state_bounds, context)?;
            &fresh
        };
        let domain = Domain {
            nodes,
            node_bounds,
            states,
            state_bounds,
            operators,
            operator_bounds,
            local,
        };
        let mut all = if execute_effects {
            self.effects.clone()
        } else {
            Vec::new()
        };
        all.extend_from_slice(roots);
        let exact_count = if stored.physical.is_some() {
            self.count
        } else {
            0
        };
        w.debit(
            2,
            (exact_count as u64).saturating_mul(160).saturating_add(64),
        )?;
        let mut exact_cells = vec![None; exact_count];
        let mut physical_reads = vec![false; exact_count];
        let mut values = arena(self.graph.evaluate_indexed(
            &all,
            &mut |id, op, args| {
                let physical_operand = stored.physical.as_ref().is_some_and(|physical| match op {
                    O::Affine { terms, .. } => terms.iter().any(|t| physical.exact_reads.get(t.node).copied().unwrap_or(false)),
                    O::Add | O::Multiply | O::Divide | O::Power(_) | O::Boundary(ir::RealBoundaryKind::Sample, _) =>
                        self.graph.node(id).is_some_and(|n| n.operands.iter().any(|&i| physical_reads[i])),
                    _ => false,
                });
                // Expanded physical intermediates also have numeric projection
                // records. They must never replace the physical proof operand.
                if let Some(&(_, value)) = stored.given.iter().find(|(given, _)| *given == id).filter(|_| !physical_operand) {
                    w.step()?;
                    if stored.physical.is_some() {
                        exact_cells[id] = Some(crate::same_time_root::Q::point(crate::same_time_root::binary(value, w)?));
                    }
                    return Ok(Cell {
                        source_domain: None,
                        nominal: Some(value),
                        image: Some(I::point(value)),
                        mathematical: None,
                        proof: None,
                    });
                }
                if stored.missing.contains(&id) {
                    return Err(Error::new(
                        "unsupported_transient",
                        format!(
                            "procedure value {id} on a same-time cycle through a program real has no \
                             stored rounding for these voltages and states: reading it where its \
                             activation was not solved is not implemented (capability limit)"
                        ),
                    ));
                }
                if let Some(physical) = &stored.physical {
                    use crate::same_time_root as root;
                    w.step()?;
                    let node = self.graph.node(id).ok_or_else(|| invalid("missing procedure node"))?;
                    let physical_read = matches!(op, O::Affine { terms, .. } if terms.iter().any(|t| physical.exact_reads.get(t.node).copied().unwrap_or(false)))
                        || node.operands.iter().any(|&i| physical_reads[i]);
                    if physical_read {
                        let q = match op {
                            O::Affine { constant, terms } => {
                                w.debit(2, (terms.len() as u64).saturating_mul(32).saturating_add(64))?;
                                let expression = ir::Expression::Affine { constant: *constant, terms: terms.to_vec() };
                                root::activation_image(&expression, &physical.values, &physical.exact_reads, w)?
                            }
                            _ => {
                                w.debit(2, (node.operands.len() as u64).saturating_mul(16).saturating_add(32))?;
                                let operands = node.operands.iter().map(|&i| exact_cells[i].as_ref()).collect::<Option<Vec<_>>>();
                                match operands { Some(args) => root::procedure_image(op, &args, w)?, None => None }
                            }
                        }.ok_or_else(|| Error::new("unsupported_transient",
                            "same-time physical consumer has no exact certified operation image (capability limit)"))?;
                        let lo = root::nearest(&q.lo, "same-time physical consumer", w)?;
                        let hi = root::nearest(&q.hi, "same-time physical consumer", w)?;
                        if lo.to_bits() != hi.to_bits() && lo != hi {
                            return Err(Error::new("unsupported_transient",
                                "same-time physical consumer has no certified rounding (capability limit)"));
                        }
                        let image = root::enclosure(&q, "same-time physical consumer", w)?;
                        let proof = if q.is_point() { Some(Arc::new(root::copy_q(&q, w)?.lo)) } else { None };
                        physical_reads[id] = match op {
                            O::Real(..) => false,
                            O::Boundary(kind, _) => matches!(kind, ir::RealBoundaryKind::Sample),
                            _ => true,
                        };
                        exact_cells[id] = Some(q);
                        return Ok(Cell { source_domain: None, nominal: Some(lo), image: Some(image),
                            mathematical: proof.clone(), proof });
                    }
                }
                let value = op.evaluate(args, &domain, w)?;
                if stored.physical.is_some() {
                    if let Some(q) = value.proof.as_ref().or(value.mathematical.as_ref()) {
                        w.debit(2, (q.numer().bits() + q.denom().bits()).div_ceil(8).saturating_mul(4).saturating_add(128))?;
                        exact_cells[id] = Some(crate::same_time_root::Q::point((**q).clone()));
                    }
                }
                // Builder.add may postpone unknown electrical values. This final
                // evaluation cannot discard an unresolved overwritten store merely
                // because only effect roots retain it.
                if matches!(op, O::IntegerStore(..)) && value.image.is_none() {
                    return Err(Error::new(
                        "integer_range",
                        "integer store has no complete solved image",
                    ));
                }
                Ok(value)
            },
            &mut |v: &Cell| v.copy(w),
            &mut |n| w.debit(2, n),
        ))?;
        Ok(values.split_off(if execute_effects {
            self.effects.len()
        } else {
            0
        }))
    }
    pub(crate) fn numeric_values(
        &self,
        roots: &[Id],
        nodes: &[f64],
        before: &[f64],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<f64>, Error> {
        self.numeric_selected(true, true, roots, nodes, before, context, w)
    }
    /// `numeric_values` executed: the activation's own values at these
    /// voltages, for a solve that has not stored its decision 22 roundings.
    pub(crate) fn executed_values(
        &self,
        roots: &[Id],
        nodes: &[f64],
        before: &[f64],
        w: &Work,
    ) -> Result<Vec<f64>, Error> {
        self.numeric_selected(true, false, roots, nodes, before, None, w)
    }
    #[allow(clippy::too_many_arguments)]
    fn numeric_selected(
        &self,
        execute_effects: bool,
        stored: bool,
        roots: &[Id],
        nodes: &[f64],
        before: &[f64],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<f64>, Error> {
        w.debit(
            2,
            ((nodes.len() + before.len() + self.point_operators.len()) * 40 + 64) as u64,
        )?;
        let points = nodes.iter().copied().map(Some).collect::<Vec<_>>();
        let bounds = nodes.iter().copied().map(I::point).collect::<Vec<_>>();
        let states = before.iter().copied().map(Some).collect::<Vec<_>>();
        let state_bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
        let operators = self
            .observation
            .get()
            .map(|v| v.iter().copied().map(Some).collect::<Vec<_>>())
            .unwrap_or_else(|| self.point_operators.clone());
        let operator_bounds = operators
            .iter()
            .map(|v| {
                v.map(I::point).unwrap_or(I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                })
            })
            .collect::<Vec<_>>();
        // A same-time cycle's program values are the roundings its solve
        // recorded for these inputs (decision 22), never their execution.
        let stored = self.stored_same_time(stored, roots, nodes, before, w)?;
        self.evaluate_with(
            execute_effects,
            roots,
            (&points, &bounds),
            (&states, &state_bounds),
            (&operators, &operator_bounds),
            context,
            &stored,
            w,
        )?
        .iter()
        .zip(roots)
        .map(|(cell, id)| {
            cell.point().map_err(|e| {
                Error::new(
                    e.kind,
                    format!(
                        "{} (procedure value {id}, before {}, operation {:?})",
                        e.message,
                        before.len(),
                        self.graph.node(*id).map(|n| &n.operation)
                    ),
                )
            })
        })
        .collect()
    }
    // Keep nominal/full boxes, source frame, and original Work explicit.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn reset_captures(
        &self,
        nodes: &[f64],
        node_bounds: &[I],
        before: &[f64],
        before_bounds: &[I],
        operator_points: &[f64],
        operator_bounds: &[I],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<Option<I>>, Error> {
        w.debit(
            2,
            ((self.operators.len() + nodes.len() + before.len() + operator_points.len()) * 32 + 64)
                as u64,
        )?;
        let ids = self
            .operators
            .iter()
            .filter_map(|v| v.as_ref().and_then(|v| v.reset))
            .collect::<Vec<_>>();
        let points = nodes.iter().copied().map(Some).collect::<Vec<_>>();
        let states = before.iter().copied().map(Some).collect::<Vec<_>>();
        let ops = operator_points
            .iter()
            .copied()
            .map(Some)
            .collect::<Vec<_>>();
        // A reset that reads a same-time cycle reads its stored roundings.
        let stored = self.stored_same_time(true, &ids, nodes, before, w)?;
        let values = self.evaluate_with(
            true,
            &ids,
            (&points, node_bounds),
            (&states, before_bounds),
            (&ops, operator_bounds),
            context,
            &stored,
            w,
        )?;
        let mut values = values.iter();
        let mut resets = Vec::with_capacity(self.operators.len());
        for capture in &self.operators {
            w.step()?;
            resets.push(if capture.as_ref().is_some_and(|v| v.reset.is_some()) {
                Some(
                    values
                        .next()
                        .ok_or_else(|| invalid("missing reset capture"))?
                        .bound()?,
                )
            } else {
                None
            });
        }
        Ok(resets)
    }
    pub(crate) fn numeric_states(
        &self,
        p: &Program,
        nodes: &[f64],
        before: &[f64],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<f64>, Error> {
        let states = self.numeric_values(&self.updates, nodes, before, context, w)?;
        for (value, spec) in states.iter().zip(&p.states) {
            w.step()?;
            crate::events::check_state(*value, &spec.kind)?;
        }
        Ok(states)
    }
    pub(crate) fn history_bound_images(
        &self,
        nodes: &[I],
        before: &[I],
        w: &Work,
    ) -> Result<Vec<Option<I>>, Error> {
        w.debit(2, ((nodes.len() + self.bounds.len()) * 32 + 64) as u64)?;
        let points = nodes
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        let mut result = Vec::with_capacity(self.bounds.len());
        for captures in &self.bounds {
            let mut bound: Option<I> = None;
            for &(value, active) in captures {
                w.debit(2, 32)?;
                let values = self.evaluate(
                    false,
                    &[value, active],
                    &points,
                    nodes,
                    &self.point_states,
                    before,
                    &self.point_operators,
                    &[],
                    None,
                    w,
                )?;
                let a = values[1].bound()?;
                if a.zero() {
                    continue;
                }
                let v = values[0].bound()?;
                if !a.finite() || !v.finite() || v.lo < 0. {
                    return Err(Error::new(
                        "invalid_bound_step",
                        "source-position history cap must be finite and nonnegative",
                    ));
                }
                bound = Some(bound.map_or(v, |old| I {
                    lo: old.lo.min(v.lo),
                    hi: old.hi.min(v.hi),
                }));
            }
            result.push(bound);
        }
        Ok(result)
    }
    pub(crate) fn next_bound_time(
        &self,
        time: f64,
        max_step: f64,
        solution: &ir::Solution,
        operator_bounds: &[I],
        w: &Work,
    ) -> Result<f64, Error> {
        let boxes = solution.certified_voltage_bounds.as_ref().ok_or_else(|| {
            Error::new(
                "bound_step_precision",
                "source-position timestep request requires certified node bounds",
            )
        })?;
        w.debit(2, ((boxes.len() + self.count) * 32 + 64) as u64)?;
        let nodes = boxes
            .iter()
            .map(|b| I { lo: b[0], hi: b[1] })
            .collect::<Vec<_>>();
        self.next_bound_time_from_boxes(time, max_step, &nodes, operator_bounds, w)
    }
    /// Accepted physical boxes, with no nominal midpoint used as a proof.
    pub(crate) fn next_bound_time_from_boxes(
        &self,
        time: f64,
        max_step: f64,
        nodes: &[I],
        operator_bounds: &[I],
        w: &Work,
    ) -> Result<f64, Error> {
        w.debit(2, ((nodes.len() + self.count) * 32 + 64) as u64)?;
        let points = nodes
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        let mut roots = Vec::new();
        for row in &self.bounds {
            for &(value, active) in row {
                w.debit(2, 16)?;
                roots.push(value);
                roots.push(active);
            }
        }
        let values = self.evaluate(
            true,
            &roots,
            &points,
            nodes,
            &self.point_states,
            &self.base[..],
            &self.point_operators,
            operator_bounds,
            None,
            w,
        )?;
        let mut step = max_step;
        for pair in values.as_chunks::<2>().0 {
            w.step()?;
            let active = pair[1].bound()?;
            if active.zero() {
                continue;
            }
            if !active.finite() {
                return Err(Error::new(
                    "bound_step_precision",
                    "nonfinite source-position timestep activation",
                ));
            }
            let value = pair[0].bound()?;
            if !value.finite() || value.lo < 0. {
                return Err(Error::new(
                    "invalid_bound_step",
                    "$bound_step must be certified finite and nonnegative",
                ));
            }
            step = step.min(value.lo);
        }
        let end = if (time + step).is_finite() {
            (I::point(time) + I::point(step)).lo
        } else {
            f64::INFINITY
        };
        Ok(end.max(time.next_up()))
    }
    pub(crate) fn state_bounds(
        &self,
        nodes: &[I],
        before: &[I],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<Vec<I>, Error> {
        w.debit(
            2,
            ((nodes.len() + before.len() + self.point_operators.len()) * 24 + 64) as u64,
        )?;
        let points = nodes
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        let ops = context.map(Context::operators).unwrap_or(&[]);
        self.evaluate(
            true,
            &self.updates,
            &points,
            nodes,
            &self.point_states,
            before,
            &self.point_operators,
            ops,
            context,
            w,
        )?
        .iter()
        .map(Cell::bound)
        .collect()
    }
}

pub(crate) fn execute(
    p: &Program,
    fired: &[usize],
    nodes: &[I],
    before: &[I],
    context: Option<&Context<'_>>,
    w: &Work,
) -> Result<Plan, Error> {
    w.debit(
        2,
        ((p.states.len()
            + p.real_bindings.len()
            + p.contributions.len()
            + p.step_bounds.len()
            + p.operators.len()
            + nodes.len()
            + 64)
            * 64) as u64,
    )?;
    let local = LocalState::try_with_context(before, context)?;
    let nominal = context.and_then(Context::nominal_frame);
    let state_points = before
        .iter()
        .enumerate()
        .map(|(i, b)| {
            nominal
                .and_then(|f| f.states.get(i).copied())
                .or_else(|| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
        })
        .collect::<Vec<_>>();
    let mut node_points = nodes
        .iter()
        .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
        .collect::<Vec<_>>();
    if let Some(f) = nominal {
        // The Conditions caller already binds driven-node slots into nodes.
        // Nonpoint values require that caller's explicit input index map.
        let _ = &f.inputs;
    }
    let operator_bounds = context.map(Context::operators).unwrap_or(&[]);
    let operator_points = operator_bounds
        .iter()
        .enumerate()
        .map(|(i, b)| {
            nominal
                .and_then(|f| f.operators.get(i).copied())
                .or_else(|| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
        })
        .collect::<Vec<_>>();
    if !node_points.is_empty() {
        node_points[0] = Some(0.);
    }
    let domain = Domain {
        nodes: &node_points,
        node_bounds: nodes,
        states: &state_points,
        state_bounds: before,
        operators: &operator_points,
        operator_bounds,
        local: &local,
    };
    let mut builder = Builder {
        p,
        w,
        domain,
        graph: Graph::new(),
        values: Vec::new(),
        physical_values: Vec::new(),
        solved_values: Vec::new(),
        selected: 0,
        stored: Vec::new(),
        states: Vec::new(),
        initial: Vec::new(),
        bindings: vec![None; p.real_bindings.len()],
        owner: "",
        procedure: usize::MAX,
        event: usize::MAX,
        event_loop_iterations: 0,
        fired,
        effects: Vec::new(),
        contributions: vec![Vec::new(); p.contributions.len()],
        bounds: vec![Vec::new(); p.step_bounds.len()],
        operators: vec![None; p.operators.len()],
        capturing: vec![false; p.operators.len()],
        operator_values: vec![None; p.operators.len()],
        actions: Vec::new(),
        displays: Vec::new(),
        decisions: Vec::new(),
        guards: Vec::new(),
        selectors: Vec::new(),
    };
    for state in 0..p.states.len() {
        let id = builder.add(O::State(state), Vec::new())?;
        builder.initial.push(id);
    }
    let mut updates = builder.initial.clone();
    for procedure in &p.procedures {
        w.debit(
            2,
            ((p.states.len() + p.real_bindings.len()) * 16 + 32) as u64,
        )?;
        builder.states = builder.initial.clone();
        builder.bindings.fill(None);
        builder.owner = &procedure.instance;
        builder.procedure = procedure.procedure_id;
        builder.steps(&procedure.body)?;
        for (state, &id) in builder.states.iter().enumerate() {
            w.step()?;
            if id != builder.initial[state] {
                if updates[state] != builder.initial[state] {
                    return Err(Error::new(
                        "event_conflict",
                        "different analog procedures write the same state",
                    ));
                }
                updates[state] = id;
            }
        }
    }
    // Fixed-width identity encoding has an O(1) size bound before any walk or
    // allocation. Length prefixes distinguish the three ordered sequences.
    let identity_len = updates
        .len()
        .saturating_add(builder.effects.len())
        .saturating_mul(8)
        .saturating_add(builder.decisions.len())
        .saturating_add(24);
    w.debit(
        2,
        (identity_len as u64).saturating_mul(2).saturating_add(64),
    )?;
    let mut identity = Vec::with_capacity(identity_len);
    identity.extend_from_slice(&(updates.len() as u64).to_le_bytes());
    for &id in &updates {
        identity.extend_from_slice(&(id as u64).to_le_bytes());
    }
    identity.extend_from_slice(&(builder.effects.len() as u64).to_le_bytes());
    for &id in &builder.effects {
        identity.extend_from_slice(&(id as u64).to_le_bytes());
    }
    identity.extend_from_slice(&(builder.decisions.len() as u64).to_le_bytes());
    identity.extend(builder.decisions.iter().map(|&v| u8::from(v)));
    let count = builder.values.len();
    w.debit(2, (count * 16 + 32) as u64)?;
    let mut foldable = Vec::with_capacity(count);
    let mut source_certified = Vec::with_capacity(count);
    for (id, value) in builder.values.iter().enumerate() {
        w.step()?;
        source_certified.push(
            value.proof.is_some()
                && matches!(
                    builder.graph.node(id).map(|n| &n.operation),
                    Some(O::Real(..) | O::Boundary(..))
                ),
        );
        let known = builder
            .graph
            .node(id)
            .map(|node| node.operation.captured_binary_identity(value, w))
            .transpose()?
            .unwrap_or(false);
        let same = if known {
            true
        } else if let Some((math, point)) = value.mathematical.as_ref().zip(value.nominal) {
            let mut paid = crate::exact_source::history_paid::Paid::new(w);
            let binary = paid.binary(point);
            let binary = paid.finish(binary)?;
            if let Some(binary) = binary {
                let mut paid = crate::exact_source::history_paid::Paid::new(w);
                let order = paid.cmp(math, &binary);
                paid.finish(order)?.is_some_and(|o| o.is_eq())
            } else {
                false
            }
        } else {
            false
        };
        foldable.push(same);
    }
    let branched = !builder.decisions.is_empty();
    w.debit(2, 128)?;
    let captured = Arc::new(std::mem::take(&mut builder.values));
    w.debit(2, (std::mem::size_of_val(fired) + 64) as u64)?;
    let fired = Arc::new(fired.to_vec());
    Ok(Plan {
        graph: Arc::new(builder.graph),
        foldable,
        source_certified,
        count,
        updates,
        effects: builder.effects,
        contributions: builder.contributions,
        bounds: builder.bounds,
        operators: builder.operators,
        guards: builder.guards,
        selectors: builder.selectors,
        actions: builder.actions,
        fired,
        displays: builder.displays,
        point_states: state_points,
        point_operators: operator_points,
        base: Arc::new(local),
        work: w.clone(),
        captured,
        branched,
        cell: Arc::new(std::sync::OnceLock::new()),
        observation: Arc::new(std::sync::OnceLock::new()),
        same_time: Arc::new(std::sync::Mutex::new(SameTimeRecords::default())),
        same_time_marks: Arc::new(std::sync::OnceLock::new()),
        exact_driven: Arc::new(std::sync::OnceLock::new()),
        identity,
    })
}

pub(crate) struct CircuitView {
    pub plan: Arc<Plan>,
    pub before: Vec<f64>,
    pub node_count: usize,
    pub ids: Vec<Id>,
    pub physical_program: Option<Arc<Program>>,
}
impl CircuitView {
    /// A remaining RN cell whose electrical ancestry is entirely driven can
    /// benefit from exact physical source membership at this observation.
    pub(crate) fn unresolved_source_rounding(&self, sources: &[usize]) -> Result<bool, Error> {
        if self.physical_program.is_none() {
            return Ok(false);
        }
        let w = &self.plan.work;
        w.debit(
            2,
            ((self.plan.count + sources.len() + self.ids.len()) * 32 + 128) as u64,
        )?;
        let mut pure = vec![false; self.plan.count];
        let mut used = vec![false; self.plan.count];
        let mut needed = vec![false; self.plan.count];
        for &id in &self.ids {
            w.step()?;
            needed[id] = true;
        }
        for id in 0..self.plan.count {
            w.step()?;
            let node = self
                .plan
                .graph
                .node(id)
                .ok_or_else(|| invalid("missing source rounding operand"))?;
            let (mut only_sources, mut source_used) = match &node.operation {
                O::Operator(_) => (false, false),
                O::Affine { terms, .. } => {
                    let mut valid = true;
                    let mut used = false;
                    for term in terms.iter() {
                        w.debit(2, (sources.len() + 1) as u64)?;
                        valid &= term.node == 0 || sources.contains(&term.node);
                        used |= term.node != 0;
                    }
                    (valid, used)
                }
                _ => (true, false),
            };
            for &child in &node.operands {
                w.step()?;
                only_sources &= pure[child];
                source_used |= used[child];
            }
            pure[id] = only_sources;
            used[id] = source_used;
            if needed[id]
                && !self.plan.source_certified[id]
                && only_sources
                && source_used
                && matches!(node.operation, O::Real(..) | O::Boundary(..))
            {
                return Ok(true);
            }
        }
        Ok(false)
    }
    /// The exact source value of a driven node at this activation, if known.
    pub(crate) fn exact_input(&self, node: usize) -> Option<num_rational::BigRational> {
        if node >= self.node_count {
            return None;
        }
        if let Some(Some(value)) = self.plan.exact_driven.get().and_then(|v| v.get(node)) {
            return Some(value.clone());
        }
        self.plan.base.floor_node(node).cloned()
    }
    /// The voltages with the activation's procedure values: on a same-time
    /// cycle the roundings the solve stored for them (decision 22).
    pub(crate) fn expand(&self, voltages: &[f64]) -> Result<Vec<f64>, Error> {
        let w = &self.plan.work;
        w.debit(2, ((self.node_count + self.plan.count) * 16 + 64) as u64)?;
        let mut values = voltages[..self.node_count].to_vec();
        values.extend(
            self.plan
                .numeric_values(&self.ids, &values, &self.before, None, w)?,
        );
        Ok(values)
    }
    /// `expand` with every procedure value executed, for a solve's own
    /// iterates before it stores its roundings.
    pub(crate) fn expand_executed(&self, voltages: &[f64]) -> Result<Vec<f64>, Error> {
        let w = &self.plan.work;
        w.debit(2, ((self.node_count + self.plan.count) * 16 + 64) as u64)?;
        let mut values = voltages[..self.node_count].to_vec();
        values.extend(
            self.plan
                .executed_values(&self.ids, &values, &self.before, w)?,
        );
        Ok(values)
    }
    /// Extend this candidate's public certificate using the same activation
    /// and the current history domains, which may have widened after restart.
    pub(crate) fn expand_bounds(
        &self,
        public: &[I],
        points: &[f64],
        operator_bounds: &[I],
    ) -> Result<Vec<I>, Error> {
        let w = &self.plan.work;
        w.debit(
            2,
            ((public.len() + self.before.len() + operator_bounds.len() + self.ids.len()) * 48 + 64)
                as u64,
        )?;
        if public.len() != self.node_count || points.len() != self.node_count + self.ids.len() {
            return Err(invalid("procedure private certificate dimensions mismatch"));
        }
        let nodes = points[..self.node_count]
            .iter()
            .copied()
            .map(Some)
            .collect::<Vec<_>>();
        let states = self.before.iter().copied().map(Some).collect::<Vec<_>>();
        let operators = self
            .plan
            .observation
            .get()
            .map(|values| values.iter().copied().map(Some).collect::<Vec<_>>())
            .unwrap_or_else(|| self.plan.point_operators.clone());
        let cells = self.plan.evaluate(
            false,
            &self.ids,
            &nodes,
            public,
            &states,
            &self.plan.base,
            &operators,
            operator_bounds,
            None,
            w,
        )?;
        let mut values = Vec::with_capacity(points.len());
        values.extend_from_slice(public);
        for (cell, &point) in cells.iter().zip(&points[self.node_count..]) {
            values.push(cell.bound()?.hull(I::point(point)));
        }
        Ok(values)
    }
}
struct Layout {
    program: Program,
    names: Vec<String>,
    parameters: Vec<Id>,
    ids: Vec<Id>,
}
fn reference(node: usize) -> E {
    E::Affine {
        constant: 0.,
        terms: vec![ir::Term {
            node,
            coefficient: 1.,
        }],
    }
}
impl Plan {
    fn layout(&self, p: &Program, driven: &[String], w: &Work) -> Result<Layout, Error> {
        w.debit(
            2,
            ((self.count + p.nodes.len() + driven.len() + p.contributions.len()) * 128 + 64) as u64,
        )?;
        strings_copy_cost(&p.nodes, w)?;
        strings_copy_cost(driven, w)?;
        let mut program = Program {
            schema_version: p.schema_version,
            nodes: p.nodes.clone(),
            contributions: Vec::new(),
            states: Vec::new(),
            events: Vec::new(),
            operators: Vec::new(),
            step_bounds: Vec::new(),
            procedures: Vec::new(),
            real_bindings: Vec::new(),
        };
        let mut names = driven.to_vec();
        let mut parameters = Vec::new();
        let mut physical = Vec::with_capacity(self.count);
        let mut voltage = Vec::with_capacity(self.count);
        for id in 0..self.count {
            w.step()?;
            let n = self
                .graph
                .node(id)
                .ok_or_else(|| invalid("missing graph node"))?;
            let live = !self.source_certified[id]
                && (matches!(&n.operation,O::Affine{terms,..} if terms.iter().any(|t|t.node!=0&&t.coefficient!=0.))
                    || n.operands.iter().any(|&i| voltage[i]));
            voltage.push(live);
            physical.push(
                live || (!self.foldable[id]
                    && matches!(
                        &n.operation,
                        O::Add
                            | O::Multiply
                            | O::Divide
                            | O::Power(_)
                            | O::Math(
                                ir::EventMathFunction::Floor
                                    | ir::EventMathFunction::Abs
                                    | ir::EventMathFunction::Min
                                    | ir::EventMathFunction::Max,
                                _
                            )
                    )),
            );
        }
        let mut needed = vec![false; self.count];
        let mut stack = self
            .contributions
            .iter()
            .flatten()
            .copied()
            .collect::<Vec<_>>();
        while let Some(id) = stack.pop() {
            w.step()?;
            if needed[id] {
                continue;
            }
            needed[id] = true;
            if !physical[id] {
                continue;
            }
            let n = self
                .graph
                .node(id)
                .ok_or_else(|| invalid("invalid captured graph root"))?;
            for &child in &n.operands {
                w.step()?;
                stack.push(child);
            }
        }
        let mut slots = vec![usize::MAX; self.count];
        let mut ids = Vec::new();
        let origin = p
            .contributions
            .first()
            .map(|c| &c.origin)
            .or_else(|| p.events.first().map(|e| &e.origin))
            .ok_or_else(|| invalid("procedure has no physical/source origin"))?;
        for id in 0..self.count {
            w.step()?;
            let n = self
                .graph
                .node(id)
                .ok_or_else(|| invalid("missing procedure graph node"))?;
            let depends = physical[id];
            if !needed[id] {
                continue;
            }
            let name = format!("$procedure_value_{id}");
            let node = program.nodes.len();
            program.nodes.push(name.clone());
            slots[id] = node;
            ids.push(id);
            if !depends {
                names.push(name);
                parameters.push(id);
                continue;
            }
            w.debit(2, (n.operands.len() * 64 + 128) as u64)?;
            let args = n
                .operands
                .iter()
                .map(|&i| {
                    w.step()?;
                    // A source literal is a coefficient, not an independent
                    // uncertain forcing variable. Keep actual RN and snapshot
                    // nodes as references; only literal leaves are embedded.
                    Ok(
                        match &self
                            .graph
                            .node(i)
                            .ok_or_else(|| invalid("missing layout operand"))?
                            .operation
                        {
                            O::Literal(value) => E::Affine {
                                constant: *value,
                                terms: Vec::new(),
                            },
                            O::Affine { constant, terms } if terms.is_empty() => E::Affine {
                                constant: *constant,
                                terms: Vec::new(),
                            },
                            _ => reference(slots[i]),
                        },
                    )
                })
                .collect::<Result<Vec<_>, Error>>()?;
            let rhs = match &n.operation {
                O::Affine { constant, terms } => E::Affine {
                    constant: *constant,
                    terms: terms.to_vec(),
                },
                O::Add => E::Add {
                    left: Box::new(args[0].clone()),
                    right: Box::new(args[1].clone()),
                },
                O::Multiply => E::Multiply {
                    left: Box::new(args[0].clone()),
                    right: Box::new(args[1].clone()),
                },
                O::Divide => E::Divide {
                    left: Box::new(args[0].clone()),
                    right: Box::new(args[1].clone()),
                },
                O::Real(operation, o) => E::RealBinary {
                    operation: *operation,
                    left: Box::new(args[0].clone()),
                    right: Box::new(args[1].clone()),
                    origin: origin_copy(o, w)?,
                },
                O::Boundary(kind, o) => E::RealBoundary {
                    value: Box::new(args[0].clone()),
                    kind: *kind,
                    origin: origin_copy(o, w)?,
                },
                O::Power(exponent) => E::Power {
                    base: Box::new(args[0].clone()),
                    exponent: *exponent,
                },
                O::Elementary(function, o) => E::EventMath {
                    function: function.internal(),
                    args,
                    origin: origin_copy(o, w)?,
                },
                O::Math(function, o) => E::EventMath {
                    function: match function {
                        ir::EventMathFunction::Ln => crate::operators::Function::Ln.internal(),
                        ir::EventMathFunction::Sqrt => crate::operators::Function::Sqrt.internal(),
                        other => *other,
                    },
                    args,
                    origin: origin_copy(o, w)?,
                },
                // IntegerStore changes no value. Its full-domain assertion is
                // retained among effect roots and checked after the solve.
                O::IntegerStore(..) => args[0].clone(),
                O::IntegerRound(o) => E::IntegerRound {
                    value: Box::new(args[0].clone()),
                    origin: origin_copy(o, w)?,
                },
                O::CheckedInteger(o) => E::CheckedInteger {
                    value: Box::new(args[0].clone()),
                    origin: origin_copy(o, w)?,
                },
                O::Index(first, last, o) => E::CheckedIndex {
                    index: Box::new(args[0].clone()),
                    first: *first,
                    last: *last,
                    origin: origin_copy(o, w)?,
                },
                _ => return Err(invalid("physical procedure graph has an invalid leaf")),
            };
            w.debit(2, (origin.instance.len() + 32) as u64)?;
            let owned_origin = origin_copy(origin, w)?;
            program.contributions.push(ir::Contribution {
                branch: ir::BranchIdentity {
                    instance: origin.instance.clone(),
                    local_positive: name,
                    local_negative: "0".into(),
                    kind: ir::ContributionKind::Voltage,
                },
                positive: node,
                negative: 0,
                rhs,
                origin: owned_origin,
            });
        }
        for (index, captures) in self.contributions.iter().enumerate() {
            for &id in captures {
                w.debit(2, 128)?;
                let c = &p.contributions[index];
                w.debit(
                    2,
                    (c.branch.instance.len()
                        + c.branch.local_positive.len()
                        + c.branch.local_negative.len()
                        + 96) as u64,
                )?;
                let copied_origin = origin_copy(&c.origin, w)?;
                program.contributions.push(ir::Contribution {
                    branch: c.branch.clone(),
                    positive: c.positive,
                    negative: c.negative,
                    rhs: reference(slots[id]),
                    origin: copied_origin,
                });
            }
        }
        Ok(Layout {
            program,
            names,
            parameters,
            ids,
        })
    }
    pub(crate) fn circuit(
        self: &Arc<Self>,
        p: &Program,
        driven: &[String],
        before: &[f64],
        operators: &[f64],
        tolerances: ir::Tolerances,
        w: &Work,
    ) -> Result<crate::solver::Circuit, Error> {
        w.debit(2, 0)?;
        w.debit(2, ((operators.len() + p.nodes.len()) * 24 + 64) as u64)?;
        if self.observation.get().is_none() {
            let _ = self.observation.set(operators.to_vec());
        }
        let layout = self.layout(p, driven, w)?;
        w.debit(2, (layout.parameters.len() * 8 + 64) as u64)?;
        let parameters = layout
            .parameters
            .iter()
            .map(|&id| {
                self.captured
                    .get(id)
                    .ok_or_else(|| invalid("missing captured procedure parameter"))?
                    .point()
            })
            .collect::<Result<Vec<_>, Error>>()?;
        let eligible = p.operators.is_empty()
            && !self.branched
            && layout.ids.iter().any(|&id| {
                !self.source_certified[id]
                    && matches!(
                        self.graph.node(id).map(|n| &n.operation),
                        Some(O::Real(..) | O::Boundary(..))
                    )
            });
        let physical_program = if eligible {
            let copy = crate::procedure_cell::clone_program(&layout.program, w)?;
            w.debit(2, 64)?;
            Some(Arc::new(copy))
        } else {
            None
        };
        let mut circuit = crate::solver::Circuit::new(layout.program, &layout.names, tolerances)?;
        // Parameters still allocate their current (point, image) vector.
        w.debit(
            2,
            (layout.parameters.len() * std::mem::size_of::<(f64, I)>() + 64) as u64,
        )?;
        circuit.set_procedure_parameters(parameters);
        // This View owns a current before vector and shares this exact immutable
        // activation, rather than deep-cloning Plan's vectors/Origins/identity.
        w.debit(2, 16)?;
        w.debit(
            2,
            (std::mem::size_of_val(before)
                + std::mem::size_of::<CircuitView>()
                + 2 * std::mem::size_of::<usize>()) as u64,
        )?;
        circuit.set_procedure_view(Arc::new(CircuitView {
            plan: Arc::clone(self),
            before: before.to_vec(),
            node_count: p.nodes.len(),
            ids: layout.ids,
            physical_program,
        }));
        // Decision 22: the procedure values on same-time cycles of this
        // circuit and the nodes their roundings read key this Plan's records.
        let structure = circuit.same_time_structure();
        if !structure.values.is_empty() {
            let view = circuit
                .procedure_view()
                .ok_or_else(|| invalid("procedure circuit lost its view"))?;
            let ids = structure
                .values
                .iter()
                .map(|&node| {
                    view.ids
                        .get(node.wrapping_sub(view.node_count))
                        .copied()
                        .ok_or_else(|| invalid("same-time value has no procedure value"))
                })
                .collect::<Result<Vec<_>, Error>>()?;
            self.mark_same_time(ids, structure.reads.clone())?;
        }
        Ok(circuit)
    }
    // Keep nominal/full boxes, source frame, and original Work explicit.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certificate(
        self: &Arc<Self>,
        p: &Program,
        driven: &[String],
        tolerances: ir::Tolerances,
        input_bounds: &[I],
        before_bounds: &[I],
        operator_bounds: &[I],
        voltages: &[f64],
        states: &[f64],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        w.debit(2, 0)?;
        w.debit(2, (states.len() + voltages.len() + 1) as u64)?;
        if states.len() != p.states.len()
            || voltages.len() != p.nodes.len()
            || states
                .iter()
                .chain(voltages)
                .any(|value| !value.is_finite())
        {
            return Err(invalid(
                "procedure observation has invalid state or voltage representatives",
            ));
        }
        if let Some(cell) = self.cell.get() {
            if cell.matches(input_bounds, before_bounds, Some(voltages), w)? {
                w.debit(2, (states.len() * 16 + 32) as u64)?;
                if states.len() == cell.states.len()
                    && states
                        .iter()
                        .zip(&cell.states)
                        .all(|(a, b)| a.to_bits() == b.to_bits())
                {
                    return Ok((
                        cell.states.iter().copied().map(I::point).collect(),
                        cell.bounds(p.nodes.len(), w)?,
                    ));
                }
            }
        }

        let before = self
            .point_states
            .iter()
            .copied()
            .collect::<Option<Vec<_>>>()
            .or_else(|| self.actions.is_empty().then(|| states.to_vec()))
            .ok_or_else(|| invalid("procedure has no accepted nominal state"))?;
        let operators = self
            .observation
            .get()
            .cloned()
            .or_else(|| {
                self.point_operators
                    .iter()
                    .copied()
                    .collect::<Option<Vec<_>>>()
            })
            .ok_or_else(|| invalid("procedure has no operator observation"))?;
        let layout = self.layout(p, driven, w)?;
        let mut circuit = self.circuit(p, driven, &before, &operators, tolerances.clone(), w)?;
        w.debit(
            2,
            ((p.nodes.len() + before.len() + operators.len() + voltages.len()) * 40 + 64) as u64,
        )?;
        let mut boxes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            p.nodes.len()
        ];
        if !boxes.is_empty() {
            boxes[0] = I::ZERO;
        }
        // Source membership is a proof input, not a repeated string search in
        // the projected output loop. Reserve storage and every name comparison
        // before looking at bytes; all debits use the existing request owner.
        w.debit(2, p.nodes.len() as u64)?;
        let mut exogenous = vec![false; p.nodes.len()];
        for (name, &bound) in driven.iter().zip(input_bounds) {
            for (i, node) in p.nodes.iter().enumerate() {
                w.debit(2, (node.len() + name.len() + 1) as u64)?;
                if node == name {
                    boxes[i] = bound;
                    exogenous[i] = true;
                    break;
                }
            }
        }
        let provided =
            if self.branched || !self.selectors.is_empty() || !layout.parameters.is_empty() {
                crate::causal_event::fill_independent_pre_event_nodes(
                    p,
                    driven,
                    &self.fired,
                    &mut boxes,
                    before_bounds,
                    operator_bounds,
                    w,
                )?
            } else {
                false
            };
        let recertification = if provided {
            context
                .map(|c| c.try_with_operators(operator_bounds))
                .transpose()?
        } else {
            None
        };
        let context = recertification.as_ref().or(context);
        let points = boxes
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        if provided {
            self.recertify_controls(
                &exogenous,
                &points,
                &boxes,
                before_bounds,
                operator_bounds,
                context,
                w,
            )?;
        }
        let params = self.evaluate(
            false,
            &layout.parameters,
            &points,
            &boxes,
            &self.point_states,
            before_bounds,
            &self.point_operators,
            operator_bounds,
            context,
            w,
        )?;
        let parameter_bounds = params
            .iter()
            .map(Cell::bound)
            .collect::<Result<Vec<_>, _>>()?;
        circuit.set_procedure_parameter_bounds(&parameter_bounds)?;
        // Decision 22: the program values of a same-time cycle are certified
        // only where the activation's solve stored them.
        if self
            .same_time_marks
            .get()
            .is_some_and(|m| !m.ids.is_empty())
            && self.same_time_values(voltages, &before, w)?.is_none()
        {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot certify same-time program values: their activation stored no rounding for \
                 these voltages and states",
            ));
        }
        let mut values = voltages[..p.nodes.len()].to_vec();
        values.extend(self.numeric_values(&layout.ids, &values, &before, context, w)?);
        let solution = ir::Solution {
            certified_voltage_bounds: None,
            voltages: values,
            max_residual_v: 0.,
            max_residual_ratio: 0.,
            max_scaled_residual_ratio: None,
            max_voltage_correction_v: None,
            max_voltage_correction_ratio: None,
        };
        w.debit(
            2,
            ((layout
                .program
                .nodes
                .len()
                .saturating_mul(layout.program.nodes.len() + layout.names.len() + 1))
            .saturating_mul(64)) as u64,
        )?;
        let mut nodes = if let Ok(map) =
            crate::affine_bounds::node_map(&layout.program, &layout.names)
        {
            let inputs = input_bounds
                .iter()
                .chain(&parameter_bounds)
                .copied()
                .chain([I::ONE])
                .collect::<Vec<_>>();
            let projected = map
                .iter()
                .map(|row| {
                    row.iter()
                        .zip(&inputs)
                        .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
                })
                .collect::<Vec<_>>();
            for (node, (&point, bound)) in solution.voltages.iter().zip(&projected).enumerate() {
                w.step()?;
                // Declared exogenous source domains are inputs to this proof,
                // not solver error to be contracted. Preserve their full boxes;
                // every dependent unknown and captured value is checked below.
                if exogenous.get(node).copied().unwrap_or(false) {
                    if !bound.finite() || point < bound.lo || point > bound.hi {
                        w.debit(2, (p.nodes[node].len() + 256) as u64)?;
                        return Err(Error::new("waveform_accuracy",format!("declared source representative escapes its admissible domain: node {} native {:e}, projected [{:e},{:e}], original [{:e},{:e}], {} fired",p.nodes[node],point,bound.lo,bound.hi,boxes[node].lo,boxes[node].hi,self.actions.len())));
                    }
                    continue;
                }
                let budget = tolerances.absolute
                    + tolerances.relative * point.abs().max(bound.lo.abs()).max(bound.hi.abs());
                if !bound.finite() || point - bound.lo > budget || bound.hi - point > budget {
                    // Name the node whose same-time value the image cannot bound.
                    let name = &layout.program.nodes[node];
                    w.debit(2, (name.len() + 256) as u64)?;
                    return Err(Error::new("waveform_accuracy",format!("same-time forward error at {name} is not certified: procedure affine image [{:e},{:e}] excludes native {:e} within original voltage budget {budget:e}; {} fired gates",bound.lo,bound.hi,point,self.actions.len())));
                }
            }
            projected
        } else {
            circuit.waveform_bounds(&solution, input_bounds)?
        };
        let bounds = self.state_bounds(&nodes, before_bounds, context, w)?;
        // A no-gate ordinary refresh executes local assignments and their
        // domain obligations, but does not replace the accepted event-memory
        // record with its transient source frame (for example reset=0).
        let ordinary = if self.actions.is_empty() {
            Some(self.numeric_states(p, voltages, &before, context, w)?)
        } else {
            None
        };
        let native = ordinary.as_deref().unwrap_or(states);
        for (index, (&v, b)) in native.iter().zip(&bounds).enumerate() {
            w.step()?;
            if !b.finite() || v < b.lo || v > b.hi {
                return Err(Error::new("event_accuracy",format!("procedure state {index} native {v:e} escapes its complete rounded image [{:e},{:e}]; {} fired gates",b.lo,b.hi,self.actions.len())));
            }
        }
        nodes.truncate(voltages.len());
        if ordinary.is_some() {
            w.debit(2, (before_bounds.len() * 16) as u64)?;
            Ok((before_bounds.to_vec(), nodes))
        } else {
            Ok((bounds, nodes))
        }
    }
}

#[cfg(test)]
mod activation_tests {
    use super::*;
    fn program() -> Program {
        serde_json::from_str(include_str!("testdata/real_call_activation.json")).unwrap()
    }
    #[test]
    fn same_call_site_reenters_with_fresh_math_and_preserves_failed_request_owner() {
        // Source: initial n=2; timer(1) for(i=1;i<=n;i++)q=exp(i).
        // The fixture retains one Loop and one RealCall with two owned slots.
        let p = program();
        let before = vec![I::ZERO, I::ZERO, I::point(2.)];
        let nodes = vec![I::ZERO; p.nodes.len()];
        let owner = Work::default();
        super::super::validate(&p, &owner).unwrap();
        let plan = execute(&p, &[0], &nodes, &before, None, &owner).unwrap();
        let result = plan
            .numeric_states(&p, &vec![0.; p.nodes.len()], &[0., 0., 2.], None, &owner)
            .unwrap();
        assert_eq!(result, [2_f64.exp(), 3., 2.]);
        let spent = owner.spent();
        for cap in [spent / 4, spent / 2, spent * 3 / 4] {
            let request = Work::limited([128, 8192, cap]);
            let original = before.clone();
            let result = (|| {
                super::super::validate(&p, &request)?;
                let plan = execute(&p, &[0], &nodes, &before, None, &request)?;
                plan.numeric_states(&p, &vec![0.; p.nodes.len()], &[0., 0., 2.], None, &request)
            })();
            assert!(result.is_err());
            let charged = request.spent();
            assert!(charged > cap);
            assert!(execute(&p, &[0], &nodes, &before, None, &request).is_err());
            assert!(request.spent() > charged);
            assert_eq!(before, original);
        }
    }
    #[test]
    fn one_source_pow_rounds_after_the_complete_mathematical_chain() {
        // Independently computed using exact binary64 inputs and 180/260-digit
        // Decimal ln/exp: the true result is strictly above 1+2^-53.
        // Rounding ln, the synthetic multiply, or exp separately returns 1.
        let p: Program =
            serde_json::from_str(include_str!("testdata/pow_midpoint_source_program.json"))
                .unwrap();
        let owner = Work::default();
        super::super::validate(&p, &owner).unwrap();
        let nodes = vec![I::ZERO; p.nodes.len()];
        let before = vec![I::ZERO; p.states.len()];
        let previous = owner.spent();
        let plan = execute(&p, &[0], &nodes, &before, None, &owner).unwrap();
        let build_cost = owner.spent() - previous;
        let result = plan
            .numeric_states(
                &p,
                &vec![0.; p.nodes.len()],
                &vec![0.; p.states.len()],
                None,
                &owner,
            )
            .unwrap();
        assert_eq!(result[0].to_bits(), 0x3ff0000000000001);
        let cap = build_cost / 2;
        let limited = Work::limited([128, 8192, cap]);
        assert!(execute(&p, &[0], &nodes, &before, None, &limited).is_err());
        let spent = limited.spent();
        assert!(execute(&p, &[0], &nodes, &before, None, &limited).is_err());
        assert!(limited.spent() > spent);
        assert!(before.iter().all(|b| b.zero()));
    }
    #[test]
    fn overwritten_integer_effect_requires_a_complete_final_domain() {
        let p = program();
        let w = Work::default();
        let before = vec![I::ZERO, I::ZERO, I::point(2.)];
        let nodes = vec![I::ZERO; p.nodes.len()];
        let mut plan = execute(&p, &[0], &nodes, &before, None, &w).unwrap();
        let mut graph = Graph::new();
        let mut debit = |n| w.debit(2, n);
        let operand = arena(graph.append(O::Operator(0), Vec::new(), &mut debit)).unwrap();
        w.debit(2, 40).unwrap();
        let effect =
            arena(graph.append(O::IntegerStore(1, None), vec![operand], &mut debit)).unwrap();
        let output = arena(graph.append(O::Literal(0.), Vec::new(), &mut debit)).unwrap();
        plan.graph = Arc::new(graph);
        plan.effects = vec![effect];
        // The selected store is not a result root. Missing its domain must
        // still reject before evaluate discards the effect result Cells.
        let error = plan
            .evaluate(true, &[output], &[], &[], &[], &[], &[], &[], None, &w)
            .err()
            .unwrap();
        assert_eq!(error.kind, "integer_range");
        assert_eq!(
            plan.evaluate(
                true,
                &[output],
                &[],
                &[],
                &[],
                &[],
                &[Some(1.)],
                &[I::ONE],
                None,
                &w
            )
            .unwrap()[0]
                .point()
                .unwrap(),
            0.
        );
    }
    #[test]
    fn internal_elementary_layout_functions_are_not_transport_variants() {
        for function in [
            "internal_sin",
            "internal_cos",
            "internal_exp",
            "internal_ln",
            "internal_sqrt",
            "internal_tanh",
        ] {
            let wire = format!(
                r#"{{"op":"event_math","function":"{function}","args":[{{"op":"affine","constant":1,"terms":[]}}],"origin":{{"source":"raw.va","line":1,"column":1,"instance":"dut"}}}}"#
            );
            assert!(serde_json::from_str::<E>(&wire).is_err());
        }
    }
}

#[cfg(test)]
mod immutable_plan_owner_tests {
    use super::*;
    fn fixture(point: f64, w: &Work) -> (Program, Arc<Plan>, Vec<f64>) {
        let p: Program =
            serde_json::from_str(include_str!("testdata/real_call_activation.json")).unwrap();
        super::super::validate(&p, w).unwrap();
        let before = vec![point, 0., 2.];
        let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            p.nodes.len()
        ];
        nodes[0] = I::ZERO;
        nodes[1] = I::ONE;
        let plan = execute(&p, &[], &nodes, &bounds, None, w).unwrap();
        w.debit(
            2,
            (std::mem::size_of_val(&plan) + 2 * std::mem::size_of::<usize>()) as u64,
        )
        .unwrap();
        (p, Arc::new(plan), before)
    }
    fn circuit(
        plan: &Arc<Plan>,
        p: &Program,
        before: &[f64],
        w: &Work,
    ) -> Result<crate::solver::Circuit, Error> {
        plan.circuit(p, &["u".into()], before, &[], ir::Tolerances::default(), w)
    }
    #[test]
    fn immutable_plan_owner_views_share_only_exact_activation_and_keep_current_before() {
        let w = Work::default();
        let (p, first, before) = fixture(0.1, &w);
        let (_, same_number, other_before) = fixture(0.1, &w);
        let (_, changed, changed_before) = fixture(0.2, &w);
        assert!(first.as_ref() == same_number.as_ref());
        assert!(first.as_ref() == changed.as_ref());
        for (plan, current) in [
            (&first, &before),
            (&same_number, &other_before),
            (&changed, &changed_before),
        ] {
            let prior = w.spent();
            let a = circuit(plan, &p, current, &w).unwrap();
            assert!(w.spent() > prior);
            let b = circuit(plan, &p, current, &w).unwrap();
            let av = a.procedure_view().unwrap();
            let bv = b.procedure_view().unwrap();
            assert!(Arc::ptr_eq(&av.plan, plan));
            assert!(Arc::ptr_eq(&bv.plan, plan));
            assert_eq!(av.node_count, p.nodes.len());
            assert_eq!(
                av.before.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
                current.iter().map(|v| v.to_bits()).collect::<Vec<_>>()
            );
            assert_ne!(av.before.as_ptr(), bv.before.as_ptr());
            assert!(av.plan.work.same_owner(&w));
            let solution = a.solve(&[1.]).unwrap();
            assert_eq!(solution.voltages[2].to_bits(), current[0].to_bits());
        }
        assert!(!Arc::ptr_eq(&first, &same_number));
        assert!(!Arc::ptr_eq(&first.cell, &same_number.cell));
        assert!(!Arc::ptr_eq(&first.observation, &same_number.observation));
        let foreign = Work::default();
        let (_, other, _) = fixture(0.1, &foreign);
        assert!(!other.work.same_owner(&w));
        assert!(!Arc::ptr_eq(&first, &other));
    }
    #[test]
    fn immutable_plan_owner_failed_original_work_is_sticky_without_view_or_cache_mutation() {
        let w = Work::limited([128, 8192, 5_000_000]);
        let (p, plan, before) = fixture(0.1, &w);
        let strong = Arc::strong_count(&plan);
        let identity = plan.identity.clone();
        let mut exhausted = false;
        for _ in 0..10_000 {
            match circuit(&plan, &p, &before, &w) {
                Ok(circuit) => {
                    let view = circuit.procedure_view().unwrap();
                    assert!(Arc::ptr_eq(&view.plan, &plan));
                }
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(exhausted);
        assert!(w.spent() > 5_000_000);
        let spent = w.spent();
        assert_eq!(Arc::strong_count(&plan), strong);
        for _ in 0..2 {
            assert_eq!(
                circuit(&plan, &p, &before, &w).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
            assert_eq!(Arc::strong_count(&plan), strong);
            assert_eq!(plan.identity, identity);
        }
        // Cached-certificate entry must fail before even consulting its slot.
        for _ in 0..2 {
            assert_eq!(
                plan.certificate(
                    &p,
                    &["u".into()],
                    ir::Tolerances::default(),
                    &[I::ONE],
                    &before.iter().copied().map(I::point).collect::<Vec<_>>(),
                    &[],
                    &[0., 1., 0.1],
                    &before,
                    None,
                    &w
                )
                .err()
                .unwrap()
                .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
            assert_eq!(Arc::strong_count(&plan), strong);
        }
    }
}

#[cfg(test)]
mod same_time_record_tests {
    use super::*;
    use crate::ir::{EventTrigger, Request, Solution, Tolerances};

    // @(timer(0.5)) q = -0.5*V(y) + V(u) + 1 with V(y) <+ q: the same-time
    // equation y = -y/2 + u + 1 has the root 2(u + 1)/3, so decision 22 stores
    // RN(2/3) at u = 0 (testdata/same_time_record.va).
    fn fixture(w: &Work) -> (Program, Arc<Plan>, Vec<f64>) {
        let request: Request =
            serde_json::from_str(include_str!("testdata/same_time_record.json")).unwrap();
        let p = request.program;
        let before = vec![0.; p.states.len()];
        let old = before.iter().map(|&v| I::point(v)).collect::<Vec<_>>();
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            p.nodes.len()
        ];
        nodes[0] = I::ZERO;
        nodes[1] = I { lo: 0., hi: 16. };
        let timer = p
            .events
            .iter()
            .position(|e| matches!(e.trigger, EventTrigger::Timer { .. }))
            .unwrap();
        let plan = execute(&p, &[timer], &nodes, &old, None, w).unwrap();
        (p, Arc::new(plan), before)
    }

    #[test]
    fn stored_roundings_outlive_later_solves_and_ignore_the_ground_zero_sign() {
        let w = Work::default();
        let (p, plan, before) = fixture(&w);
        let c = plan
            .circuit(&p, &["u".into()], &before, &[], Tolerances::default(), &w)
            .unwrap();
        let first = c.solve(&[0.]).unwrap();
        let rn = 2.0_f64 / 3.0;
        assert_eq!(first.voltages[2].to_bits(), rn.to_bits());
        // More solves of the same activation than the eight records it kept
        // before (review r1 R2-R1): the first record is still read.
        for u in 1..=12 {
            c.solve(&[f64::from(u)]).unwrap();
        }
        let q = |nodes: &[f64]| {
            plan.numeric_states(&p, nodes, &before, None, &w)
                .map(|s| s[0])
        };
        assert_eq!(q(&first.voltages).unwrap().to_bits(), rn.to_bits());
        // The sign of the ground zero is not an input of the record.
        let mut negative_ground = first.voltages.clone();
        negative_ground[0] = -0.0;
        assert_eq!(q(&negative_ground).unwrap().to_bits(), rn.to_bits());
    }

    #[test]
    fn a_missing_stored_rounding_is_refused_never_executed() {
        let w = Work::default();
        let (p, plan, before) = fixture(&w);
        let c = plan
            .circuit(&p, &["u".into()], &before, &[], Tolerances::default(), &w)
            .unwrap();
        let first = c.solve(&[0.]).unwrap();
        // Voltages this activation was never solved at have no record: the
        // executed value of the rounded map is not read in its place.
        let mut other = first.voltages.clone();
        other[2] = 0.5;
        let error = plan
            .numeric_states(&p, &other, &before, None, &w)
            .unwrap_err();
        assert_eq!(error.kind, "unsupported_transient");
        assert!(
            error.message.contains("has no stored rounding"),
            "{}",
            error.message
        );
        // Nor is the certificate of such a point given by execution: it is
        // refused as a certificate.
        let unsolved = Solution {
            voltages: other,
            ..first.clone()
        };
        let error = c.waveform_bounds(&unsolved, &[I::point(0.)]).unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(
            error.message.contains("stored no rounding"),
            "{}",
            error.message
        );
    }
}

#[cfg(test)]
mod activation_transfer_tests {
    use super::*;
    fn marked(w: &Work) -> Plan {
        let request: crate::ir::Request =
            serde_json::from_str(include_str!("testdata/same_time_record.json")).unwrap();
        let p = request.program;
        let before = vec![I::ZERO; p.states.len()];
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            p.nodes.len()
        ];
        nodes[0] = I::ZERO;
        nodes[1] = I::ZERO;
        let timer = p
            .events
            .iter()
            .position(|e| matches!(e.trigger, crate::ir::EventTrigger::Timer { .. }))
            .unwrap();
        let plan = execute(&p, &[timer], &nodes, &before, None, w).unwrap();
        plan.mark_same_time(vec![7], vec![1]).unwrap();
        plan
    }
    #[test]
    fn conflict_is_transitive_and_only_recertification_clears_it() {
        let w = Work::default();
        let a = marked(&w);
        let b = marked(&w);
        let c = marked(&w);
        let nodes = [0., 0.];
        let before = [0.];
        a.record_same_time(
            &nodes,
            &before,
            vec![(7, 2.0 / 3.0)],
            PhysicalFrame::default(),
        )
        .unwrap();
        b.record_same_time(
            &nodes,
            &before,
            vec![(7, (2.0_f64 / 3.0).next_up())],
            PhysicalFrame::default(),
        )
        .unwrap();
        c.adopt_same_time(&a).unwrap();
        a.adopt_same_time(&b).unwrap();
        c.adopt_same_time(&a).unwrap();
        assert!(c.same_time_record(&nodes, &before).unwrap().is_none());
        c.adopt_same_time(&b).unwrap();
        assert!(c.same_time_record(&nodes, &before).unwrap().is_none());
        c.record_same_time(
            &nodes,
            &before,
            vec![(7, 2.0 / 3.0)],
            PhysicalFrame::default(),
        )
        .unwrap();
        assert_eq!(
            c.same_time_record(&nodes, &before).unwrap().unwrap()[0].1,
            2.0 / 3.0
        );
    }
    #[test]
    fn exhausted_transfer_and_retries_leave_target_unchanged() {
        let w = Work::for_limit(100_000_000);
        let a = marked(&w);
        let b = marked(&w);
        for k in 0..16384 {
            a.record_same_time(
                &[0., k as f64],
                &[0.],
                vec![(7, k as f64)],
                PhysicalFrame::default(),
            )
            .unwrap();
        }
        b.record_same_time(&[0., -1.], &[0.], vec![(7, -1.)], PhysicalFrame::default())
            .unwrap();
        w.debit(2, 100_000_000 - w.spent()).unwrap();
        for _ in 0..3 {
            assert_eq!(b.adopt_same_time(&a).unwrap_err().kind, "step_budget");
            let guard = b.same_time.lock().unwrap();
            assert_eq!(guard.records.len(), 1);
            assert!(guard.conflicting.is_empty());
        }
    }
    #[test]
    fn exhausted_identity_lengths_and_equal_buffers_are_guarded() {
        for n in [0, 1, 1024, 1 << 20] {
            let limit = 20_000_000;
            let w = Work::for_limit(limit);
            let mut a = marked(&w);
            let mut b = marked(&w);
            w.debit(2, 4 * n as u64 + 4096).unwrap();
            a.identity = vec![1; n];
            b.identity = vec![1; n];
            w.debit(2, limit - w.spent()).unwrap();
            for _ in 0..3 {
                let spent = w.spent();
                assert_eq!(b.adopt_same_time(&a).unwrap_err().kind, "step_budget");
                assert_eq!(w.spent() - spent, 64);
            }
        }
    }
    #[test]
    fn positive_low_remainder_transfer_is_atomic_with_many_tombstones() {
        const LIMIT: u64 = 1_000_000_000;
        for remaining in [0, 1, 8192] {
            let w = Work::for_limit(LIMIT);
            let a = marked(&w);
            let b = marked(&w);
            for k in 0..1792 {
                let x = marked(&w);
                let y = marked(&w);
                let key = [0., k as f64];
                x.record_same_time(&key, &[], vec![(7, 0.)], PhysicalFrame::default())
                    .unwrap();
                y.record_same_time(&key, &[], vec![(7, 1.)], PhysicalFrame::default())
                    .unwrap();
                x.adopt_same_time(&y).unwrap();
                a.adopt_same_time(&x).unwrap();
            }
            let x = marked(&w);
            let key = [0., 1792.];
            b.record_same_time(&key, &[], vec![(7, 0.)], PhysicalFrame::default())
                .unwrap();
            x.record_same_time(&key, &[], vec![(7, 1.)], PhysicalFrame::default())
                .unwrap();
            b.adopt_same_time(&x).unwrap();
            let before = {
                let g = a.same_time.lock().unwrap();
                (g.records.len(), g.conflicting.clone())
            };
            w.debit(2, LIMIT - w.spent() - remaining).unwrap();
            let result = a.adopt_same_time(&b);
            if result.is_err() {
                let g = a.same_time.lock().unwrap();
                assert_eq!(g.records.len(), before.0);
                assert_eq!(g.conflicting, before.1);
            } else {
                let g = a.same_time.lock().unwrap();
                assert_eq!(g.conflicting.len(), 1793);
            }
            // This structure no longer reallocates or rehashes all target keys at 1792.
        }
    }
}
