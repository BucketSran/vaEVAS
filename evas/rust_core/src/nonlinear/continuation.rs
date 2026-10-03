//! Bounded residual homotopy for a subset of square voltage systems.
//! Intermediate equations provide initial guesses only. A result must pass
//! unmodified Newton acceptance on the original equations at lambda=1.
use super::{evaluate, newton, Equation, Error, Evaluation, Solution, Tolerances};

pub(super) struct Path<'a> {
    anchor: &'a [f64],
    scales: &'a [f64],
    // Each branch has one unknown endpoint and a distinct target column.
    targets: &'a [(usize, usize, f64)],
    lambda: f64,
}

impl Path<'_> {
    pub(super) fn apply(
        &self,
        result: &mut Evaluation,
        values: &[f64],
        tolerance: &Tolerances,
    ) -> Result<(), Error> {
        for (i, &(node, column, sign)) in self.targets.iter().enumerate() {
            let diagonal = (1.0 - self.lambda) * sign;
            result.residuals[i] = self.lambda * (result.residuals[i] / self.scales[i])
                + diagonal * (values[node] - self.anchor[node]);
            let row = &mut result.jacobian[i];
            for (_, value) in row.iter_mut() {
                *value = self.lambda * (*value / self.scales[i]);
            }
            match row.binary_search_by_key(&column, |&(j, _)| j) {
                Ok(j) => row[j].1 += diagonal,
                Err(j) => row.insert(j, (column, diagonal)),
            }
            row.retain(|(_, value)| *value != 0.0);
            let scale = row.iter().fold(0.0_f64, |a, (_, b)| a.max(b.abs()));
            result.row_scales[i] = if scale > 0.0 { scale } else { 1.0 };
            result.bounds[i] = tolerance.absolute
                + tolerance.relative * values[node].abs().max(self.anchor[node].abs());
            if !result.residuals[i].is_finite()
                || !result.bounds[i].is_finite()
                || row.iter().any(|(_, value)| !value.is_finite())
            {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite residual continuation trial",
                ));
            }
        }
        Ok(())
    }
}

pub(super) fn solve(
    equations: &[Equation],
    unknown: &[usize],
    columns: &[Option<usize>],
    anchor: Vec<f64>,
    tolerance: &Tolerances,
) -> Option<Solution> {
    if unknown.is_empty() || unknown.len() > 32 || equations.len() != unknown.len() {
        return None;
    }
    let mut seen = vec![false; unknown.len()];
    let mut targets = Vec::with_capacity(unknown.len());
    for eq in equations {
        let target = match (columns[eq.positive], columns[eq.negative]) {
            (Some(column), None) => (eq.positive, column, 1.0),
            (None, Some(column)) => (eq.negative, column, -1.0),
            _ => return None,
        };
        if seen[target.1] {
            return None;
        }
        seen[target.1] = true;
        targets.push(target);
    }
    let scales = evaluate(equations, columns, &anchor, tolerance)
        .ok()?
        .row_scales;
    // Intermediate equations only supply guesses. Solving each artificial
    // stage to a sub-ulp user budget would prevent an exactly representable
    // final root from ever reaching the original acceptance checks.
    let working = Tolerances {
        absolute: tolerance.absolute.max(1e-12),
        relative: tolerance.relative.max(1e-10),
    };
    let (mut lambda, mut step) = (0.0_f64, 0.125_f64);
    let mut values = anchor.clone();
    for _ in 0..32 {
        let next = (lambda + step).min(1.0);
        let path = Path {
            anchor: &anchor,
            scales: &scales,
            targets: &targets,
            lambda: next,
        };
        match newton(
            equations,
            unknown,
            columns,
            values.clone(),
            &working,
            Some(&path),
        ) {
            Ok(solution) => {
                values = solution.voltages;
                lambda = next;
                if lambda == 1.0 {
                    return newton(equations, unknown, columns, values, tolerance, None).ok();
                }
                step = (2.0 * step).min(0.25);
            }
            Err(_) => {
                step *= 0.5;
                if step < 1.0 / 16384.0 {
                    return None;
                }
            }
        }
    }
    None
}
