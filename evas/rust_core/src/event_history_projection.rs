//! Paid direct guard projection after original history qualification.
//! Keep the legacy direct matrix, fold order and signed-zero fallback. The
//! original history gate proves every guard uses only original driven nodes;
//! no alias expansion, DC solve, state or operator forcing is introduced.
use super::*;
use crate::transition_source_plan::Work;
fn vector<T>(n: usize, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (n as u64)
            .saturating_mul(std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64),
    )
}
fn copied(values: &[I], w: &Work) -> Result<Vec<I>, Error> {
    vector::<I>(values.len(), w)?;
    w.debit(2, (values.len() as u64).saturating_mul(2))?;
    Ok(values.to_vec())
}
pub(super) fn for_model(
    model: &crate::events::EventModel,
    states: Option<&[I]>,
) -> Result<GuardBounds, Error> {
    let role = crate::analytic_request::proof_owner(model).expect("paid projection role");
    let w = role.work();
    w.debit(2, 0)?;
    w.debit(2, 16)?;
    let program = &model.program;
    let count = program.nodes.len();
    let variables = count + program.states.len() + program.operators.len();
    let width = model.driven.len() + program.states.len() + program.operators.len() + 1;
    let indices = role.input_nodes();
    vector::<usize>(indices.len(), w)?;
    w.debit(2, indices.len() as u64)?;
    let input_nodes = indices.to_vec();
    let mut expressions = Vec::new();
    for (index, leaf) in model.triggers.iter().enumerate() {
        w.step()?;
        let guard = match &leaf.trigger {
            EventTrigger::Cross { guard, .. } if !model.dynamic_guards[index] => Some(guard),
            _ => None,
        };
        crate::history_storage::push_vec(&mut expressions, guard, w)?;
    }
    // Preserve both original affinity passes. The first checks the direct role;
    // the second below constructs the actual projected coefficients.
    for guard in expressions.iter().flatten() {
        let row = crate::history_admission::affine_paid(guard, program, w)?;
        for node in 1..count {
            w.step()?;
            if row[node].zero() {
                continue;
            }
            let mut driven = false;
            for &input in &input_nodes {
                w.step()?;
                if input == node {
                    driven = true;
                    break;
                }
            }
            if !driven {
                return Err(unresolved(
                    "history guard escaped independent original input qualification",
                ));
            }
        }
    }
    vector::<Option<Expression>>(expressions.len(), w)?;
    let symbolic = vec![None; expressions.len()];
    let mut nodes = Vec::new();
    for _ in 0..variables {
        w.step()?;
        vector::<I>(width, w)?;
        let row = vec![I::ZERO; width];
        crate::history_storage::push_vec(&mut nodes, row, w)?;
    }
    for (column, &node) in input_nodes.iter().enumerate() {
        w.step()?;
        nodes[node][column] = I::ONE;
    }
    for index in 0..program.states.len() + program.operators.len() {
        w.step()?;
        nodes[count + index][model.driven.len() + index] = I::ONE;
    }
    for row in &nodes {
        w.step()?;
        for value in row {
            w.step()?;
            if !value.finite() {
                return Err(unresolved("nonfinite event trajectory bounds"));
            }
        }
    }
    let mut coefficients = Vec::new();
    for expression in expressions {
        w.step()?;
        let row = if let Some(guard) = expression {
            let guard = crate::history_admission::affine_paid(guard, program, w)?;
            project_row(&guard, &nodes, width, w)?
        } else {
            vector::<I>(width, w)?;
            vec![I::ZERO; width]
        };
        crate::history_storage::push_vec(&mut coefficients, row, w)?;
    }
    let mut state_coefficients = Vec::new();
    for row in &coefficients {
        w.step()?;
        let copy = copied(
            &row[model.driven.len()..model.driven.len() + program.states.len()],
            w,
        )?;
        crate::history_storage::push_vec(&mut state_coefficients, copy, w)?;
    }
    if let Some(states) = states {
        if states.len() != program.states.len() {
            return Err(Error::new(
                "invalid_ir",
                "held state bounds length mismatch",
            ));
        }
        for row in &mut coefficients {
            for (index, state) in states.iter().enumerate() {
                w.debit(2, 8)?;
                row[width - 1] = row[width - 1] + row[model.driven.len() + index] * *state;
                row[model.driven.len() + index] = I::ZERO;
            }
        }
    }
    for row in &coefficients {
        for x in row {
            w.step()?;
            if !x.finite() {
                return Err(unresolved("nonfinite event trajectory bounds"));
            }
        }
    }
    for row in &coefficients {
        for x in &row[model.driven.len()..width - 1] {
            w.step()?;
            if !x.zero() {
                return Err(unresolved(
                    "cannot certify cross guard independence from event state",
                ));
            }
        }
    }
    let mut operator_coefficients = Vec::new();
    for row in &coefficients {
        w.step()?;
        let copy = copied(
            &row[model.driven.len() + program.states.len()..width - 1],
            w,
        )?;
        crate::history_storage::push_vec(&mut operator_coefficients, copy, w)?;
    }
    crate::diagnostics::counter("history_guard_projection_completed", 1);
    Ok(GuardBounds {
        coefficients,
        state_coefficients,
        operator_coefficients,
        driven_count: model.driven.len(),
        symbolic,
        input_nodes,
        node_count: count,
    })
}
fn project_row(guard: &[I], nodes: &[Vec<I>], width: usize, w: &Work) -> Result<Vec<I>, Error> {
    w.debit(2, 0)?;
    w.debit(2, 4)?;
    if guard.len() != nodes.len() + 1 {
        return Err(Error::new("invalid_ir", "event guard dimensions mismatch"));
    }
    for value in guard {
        w.step()?;
        if !value.finite() {
            return Err(unresolved("nonfinite event trajectory bounds"));
        }
    }
    let mut terms = Vec::new();
    for (j, value) in guard[..nodes.len()].iter().enumerate() {
        w.step()?;
        if !value.zero() {
            crate::history_storage::push_vec(&mut terms, (j, value), w)?;
        }
    }
    vector::<I>(width, w)?;
    let mut out = Vec::with_capacity(width);
    for column in 0..width {
        w.step()?;
        let base = if column == width - 1 {
            guard[nodes.len()]
        } else {
            I::ZERO
        };
        let mut sum = base;
        if [base.lo, base.hi]
            .iter()
            .any(|v| *v == 0. && v.is_sign_negative())
        {
            for j in 0..nodes.len() {
                w.debit(2, 4)?;
                sum = sum + guard[j] * nodes[j][column];
            }
        } else {
            for &(j, value) in &terms {
                w.step()?;
                let node = nodes[j][column];
                if !node.zero() {
                    w.debit(2, 4)?;
                    sum = sum + *value * node;
                }
            }
            if !sum.finite() {
                sum = base;
                for j in 0..nodes.len() {
                    w.debit(2, 4)?;
                    sum = sum + guard[j] * nodes[j][column];
                }
            }
        }
        w.debit(2, 2)?;
        out.push(sum);
    }
    Ok(out)
}
