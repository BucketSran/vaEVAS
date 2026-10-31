//! Append-only value dependencies for one procedure construction.
//!
//! Arithmetic, branch selection and source rounding belong to the consumer.
//! Each evaluation memo is local to that call. The graph owns no proof allowance.
use std::mem::size_of;

pub(crate) type Id = usize;

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Fault<E> {
    InvalidId,
    Quota(E),
    Evaluate(E),
}

pub(crate) struct Node<T> {
    pub operation: T,
    pub operands: Vec<Id>,
}

pub(crate) struct Graph<T> {
    nodes: Vec<Node<T>>,
}

fn pay<E>(debit: &mut impl FnMut(u64) -> Result<(), E>, cost: u64) -> Result<(), Fault<E>> {
    debit(cost).map_err(Fault::Quota)
}

fn storage<T>(count: usize) -> u64 {
    16_u64.saturating_add((count as u64).saturating_mul(size_of::<T>() as u64))
}

impl<T> Default for Graph<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T> Graph<T> {
    pub(crate) fn new() -> Self {
        Self { nodes: Vec::new() }
    }

    /// Move a caller-paid operation and operand buffer into the graph.
    /// Their construction/deep contents must already have been paid by the caller;
    /// this method pays for retained operand capacity and node allocation/moves.
    /// Every dependency must precede the new node. Failure never appends a node.
    pub(crate) fn append<E>(
        &mut self,
        operation: T,
        operands: Vec<Id>,
        debit: &mut impl FnMut(u64) -> Result<(), E>,
    ) -> Result<Id, Fault<E>> {
        pay(
            debit,
            16_u64.saturating_add((operands.len() as u64).saturating_mul(8)),
        )?;
        let id = self.nodes.len();
        if operands.iter().any(|&operand| operand >= id) {
            return Err(Fault::InvalidId);
        }
        pay(debit, storage::<Id>(operands.capacity()))?;
        if self.nodes.len() == self.nodes.capacity() {
            let capacity = self.nodes.capacity().saturating_mul(2).max(1);
            pay(
                debit,
                storage::<Node<T>>(capacity).saturating_add(storage::<Node<T>>(id)),
            )?;
            self.nodes.reserve_exact(capacity - id);
        }
        // No fallible callback follows the mutation.
        self.nodes.push(Node {
            operation,
            operands,
        });
        Ok(id)
    }

    /// Borrow without copying. Consumers pay their own repeated lookups/scans.
    pub(crate) fn node(&self, id: Id) -> Option<&Node<T>> {
        self.nodes.get(id)
    }

    /// Evaluate only nodes reachable from roots, once per node in this call.
    /// Operand order and duplicate wires are retained. The operation callback
    /// owns numerical work/rounding and must charge its actual work externally.
    /// `clone_value` must prepay the actual value copy before copying, including
    /// BigRational limbs or nested Vec contents; no unit-cost Clone is assumed.
    /// It uses the same external owner as debit; a copy failure is Quota(E).
    /// No returned/memo value is reused across calls, candidates or root domains.
    /// Traversal/memo slots cover the whole graph and are prepaid before allocation.
    /// Callbacks own their side effects; failures discard local values, not charges.
    /// Lazy branches must be selected by the consumer before choosing roots.
    pub(crate) fn evaluate<V, E, F, C, D>(
        &self,
        roots: &[Id],
        operation: &mut F,
        clone_value: &mut C,
        debit: &mut D,
    ) -> Result<Vec<V>, Fault<E>>
    where
        F: FnMut(&T, &[V]) -> Result<V, E>,
        C: FnMut(&V) -> Result<V, E>,
        D: FnMut(u64) -> Result<(), E>,
    {
        self.evaluate_indexed(
            roots,
            &mut |_, node: &T, inputs: &[V]| operation(node, inputs),
            clone_value,
            debit,
        )
    }

    /// `evaluate` with the ID of each evaluated node passed to its callback.
    pub(crate) fn evaluate_indexed<V, E, F, C, D>(
        &self,
        roots: &[Id],
        operation: &mut F,
        clone_value: &mut C,
        debit: &mut D,
    ) -> Result<Vec<V>, Fault<E>>
    where
        F: FnMut(Id, &T, &[V]) -> Result<V, E>,
        C: FnMut(&V) -> Result<V, E>,
        D: FnMut(u64) -> Result<(), E>,
    {
        pay(
            debit,
            16_u64.saturating_add((roots.len() as u64).saturating_mul(8)),
        )?;
        if roots.iter().any(|&id| id >= self.nodes.len()) {
            return Err(Fault::InvalidId);
        }
        if roots.is_empty() {
            return Ok(Vec::new());
        }
        let count = self.nodes.len();
        pay(
            debit,
            storage::<bool>(count)
                .saturating_add(storage::<Id>(count))
                .saturating_add((count as u64).saturating_mul(8)),
        )?;
        let mut reached = vec![false; count];
        let mut stack = Vec::with_capacity(count);
        for &id in roots {
            if !reached[id] {
                reached[id] = true;
                stack.push(id);
            }
        }
        while let Some(id) = stack.pop() {
            let node = &self.nodes[id];
            pay(
                debit,
                8_u64.saturating_add((node.operands.len() as u64).saturating_mul(8)),
            )?;
            for &operand in &node.operands {
                if !reached[operand] {
                    reached[operand] = true;
                    stack.push(operand);
                }
            }
        }
        pay(
            debit,
            storage::<Option<V>>(count).saturating_add((count as u64).saturating_mul(8)),
        )?;
        let mut memo: Vec<Option<V>> = Vec::with_capacity(count);
        memo.resize_with(count, || None);
        // Append validates operand < id, so index order is a topological order.
        for (id, node) in self.nodes.iter().enumerate() {
            if !reached[id] {
                continue;
            }
            pay(debit, storage::<V>(node.operands.len()).saturating_add(8))?;
            let mut inputs = Vec::with_capacity(node.operands.len());
            for &operand in &node.operands {
                pay(debit, 8)?;
                let input = memo[operand].as_ref().ok_or(Fault::InvalidId)?;
                inputs.push(clone_value(input).map_err(Fault::Quota)?);
            }
            memo[id] = Some(operation(id, &node.operation, &inputs).map_err(Fault::Evaluate)?);
        }
        pay(debit, storage::<V>(roots.len()))?;
        let mut output = Vec::with_capacity(roots.len());
        for &id in roots {
            pay(debit, 8)?;
            let value = memo[id].as_ref().ok_or(Fault::InvalidId)?;
            output.push(clone_value(value).map_err(Fault::Quota)?);
        }
        Ok(output)
    }
}
