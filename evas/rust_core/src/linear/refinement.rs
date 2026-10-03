//! Compensated b-Ax for a retry, not a forward-error certificate.
use super::Row;

pub(crate) fn residual(constant: f64, row: &Row, values: &[f64]) -> Option<f64> {
    let mut sum = constant;
    let mut low = 0.0;
    for &(node, coefficient) in row {
        let product = -coefficient * values[node];
        let product_error = (-coefficient).mul_add(values[node], -product);
        let next = sum + product;
        let part = next - sum;
        let sum_error = (sum - (next - part)) + (product - part);
        low += sum_error + product_error;
        sum = next;
    }
    let result = sum + low;
    result.is_finite().then_some(result)
}
