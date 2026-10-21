//! Storage mutations for the marked history route borrow its original Work.
use crate::{ir::Error, transition_source_plan::Work};
use std::collections::VecDeque;

fn slots<T>() -> u64 {
    std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64
}
fn growth<T>(
    len: usize,
    capacity: usize,
    additional: usize,
    w: &Work,
) -> Result<Option<usize>, Error> {
    // The zero debit is deliberately first: exhausted retries do no metadata
    // work and do not add spend before returning the same request failure.
    w.debit(2, 0)?;
    w.debit(2, 8)?;
    let Some(needed) = len.checked_add(additional) else {
        w.debit(2, u64::MAX)?;
        return Err(Error::new(
            "step_budget",
            "history storage capacity exceeds addressable memory",
        ));
    };
    if needed <= capacity {
        return Ok(None);
    }
    let bytes = std::mem::size_of::<T>();
    // Explicit initial buffer policy, including tiny element types. reserve_exact
    // receives this chosen capacity; no implicit Vec growth policy is assumed.
    let minimum = if bytes == 1 {
        8
    } else if bytes <= 1024 {
        4
    } else {
        1
    };
    let next = needed.max(capacity.saturating_mul(2)).max(minimum);
    if next
        .checked_mul(bytes)
        .is_none_or(|n| n > isize::MAX as usize)
    {
        w.debit(2, u64::MAX)?;
        return Err(Error::new(
            "step_budget",
            "history storage capacity exceeds addressable memory",
        ));
    }
    // New logical buffer slots plus a conservative move of every retained
    // element, before the allocator can move their owned structures. Rational
    // payloads move by ownership here; this does not perform a deep clone.
    let items = (next as u64)
        .saturating_add(len as u64)
        .saturating_mul(slots::<T>());
    w.debit(2, items)?;
    Ok(Some(next))
}
pub(crate) fn push_vec<T>(values: &mut Vec<T>, value: T, w: &Work) -> Result<(), Error> {
    let next = growth::<T>(values.len(), values.capacity(), 1, w)?;
    w.debit(2, slots::<T>())?;
    if let Some(next) = next {
        values.reserve_exact(next - values.len());
        crate::diagnostics::counter("history_storage_growth", 1);
    }
    values.push(value);
    Ok(())
}
pub(crate) fn push_deque<T>(values: &mut VecDeque<T>, value: T, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    let next = growth::<T>(values.len(), values.capacity(), 1, w)?;
    if next.is_some() {
        w.debit(2, 3)?;
        if !values.as_slices().1.is_empty() {
            // RawVec may move all old elements; growth() funds that move.
            // VecDeque::handle_capacity_increase can then move one wrapped
            // fragment again. Its length is <=len; fund this distinct move
            // before reserve_exact, without reusing the new-buffer fee.
            w.debit(2, (values.len() as u64).saturating_mul(slots::<T>()))?;
        }
    }
    w.debit(2, slots::<T>())?;
    if let Some(next) = next {
        values.reserve_exact(next - values.len());
        crate::diagnostics::counter("history_storage_growth", 1);
    }
    values.push_back(value);
    Ok(())
}
pub(crate) fn append<T>(values: &mut Vec<T>, other: &mut Vec<T>, w: &Work) -> Result<(), Error> {
    let next = growth::<T>(values.len(), values.capacity(), other.len(), w)?;
    w.debit(2, (other.len() as u64).saturating_mul(slots::<T>()))?;
    if let Some(next) = next {
        values.reserve_exact(next - values.len());
        crate::diagnostics::counter("history_storage_growth", 1);
    }
    values.append(other);
    Ok(())
}

/// Fallible stable merge sort over indices; no event or Rational deep copies.
/// All scratch slots, comparisons and actual permutation swaps are paid first.
pub(crate) fn sort<T>(
    events: &mut [T],
    w: &Work,
    mut compare: impl FnMut(&T, &T) -> Result<std::cmp::Ordering, Error>,
) -> Result<(), Error> {
    w.debit(2, 0)?;
    w.debit(2, (events.len() as u64).saturating_mul(3))?;
    let mut order: Vec<usize> = (0..events.len()).collect();
    let mut tmp = vec![0; events.len()];
    let mut dest = vec![0; events.len()];
    let mut width = 1;
    while width < order.len() {
        let mut start = 0;
        while start < order.len() {
            let mid = (start + width).min(order.len());
            let end = (mid + width).min(order.len());
            let (mut a, mut b) = (start, mid);
            for slot in &mut tmp[start..end] {
                w.step()?;
                let take = a < mid
                    && (b == end || !compare(&events[order[a]], &events[order[b]])?.is_gt());
                *slot = if take {
                    let i = order[a];
                    a += 1;
                    i
                } else {
                    let i = order[b];
                    b += 1;
                    i
                };
            }
            start = end;
        }
        std::mem::swap(&mut order, &mut tmp);
        width = width.saturating_mul(2);
    }
    for (i, &source) in order.iter().enumerate() {
        w.step()?;
        dest[source] = i
    }
    let slots = std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64;
    for i in 0..dest.len() {
        w.step()?;
        while dest[i] != i {
            w.debit(2, slots.saturating_mul(3).saturating_add(4))?;
            let j = dest[i];
            events.swap(i, j);
            dest.swap(i, j)
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sufficient_capacity_moves_only_new_items_without_growth() {
        let w = Work::limited([128, 8192, 1_000_000_000]);
        let mut values = Vec::with_capacity(8);
        values.push(1u64);
        let cap = values.capacity();
        let mut queue = VecDeque::with_capacity(8);
        queue.push_back(1u64);
        let qcap = queue.capacity();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            push_vec(&mut values, 2, &w)?;
            push_deque(&mut queue, 2, &w)?;
            let mut extra = vec![3, 4];
            append(&mut values, &mut extra, &w)?;
            Ok::<_, Error>(())
        });
        result.unwrap();
        assert_eq!(values, [1, 2, 3, 4]);
        assert_eq!(queue, [1, 2]);
        assert_eq!(values.capacity(), cap);
        assert_eq!(queue.capacity(), qcap);
        assert!(!report.counters.contains_key("history_storage_growth"));
    }
    #[test]
    fn first_and_retained_item_growth_are_paid_before_mutation() {
        let w = Work::limited([128, 8192, 1_000_000_000]);
        let mut v = Vec::new();
        let mut q = VecDeque::new();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            push_vec(&mut v, 1u64, &w)?;
            push_deque(&mut q, 1u64, &w)?;
            let old_vcap = v.capacity();
            let old_qcap = q.capacity();
            while v.len() < old_vcap {
                v.push(2)
            }
            while q.len() < old_qcap {
                q.push_back(2)
            }
            push_vec(&mut v, 3, &w)?;
            push_deque(&mut q, 3, &w)?;
            assert!(v.capacity() > old_vcap && q.capacity() > old_qcap);
            Ok::<_, Error>(())
        });
        result.unwrap();
        assert_eq!(report.counters.get("history_storage_growth"), Some(&4));
        assert!(w.spent() > 0);
    }
    #[test]
    fn exhausted_reservation_keeps_buffers_and_two_retries_unchanged() {
        // Metadata fits; the first real storage reservation does not.
        let w = Work::limited([128, 8192, 8]);
        let mut values: Vec<[u64; 16]> = Vec::new();
        let mut queue: VecDeque<[u64; 16]> = VecDeque::new();
        let error = push_vec(&mut values, [1; 16], &w).unwrap_err();
        assert_eq!(error.kind, "step_budget");
        assert_eq!(values.capacity(), 0);
        assert!(values.is_empty());
        let used = w.spent();
        for _ in 0..2 {
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                push_deque(&mut queue, [1; 16], &w)
            });
            assert_eq!(result.unwrap_err().kind, "step_budget");
            assert_eq!(w.spent(), used);
            assert!(queue.is_empty());
            assert_eq!(queue.capacity(), 0);
            assert!(report.counters.is_empty());
            assert!(report.stages.is_empty());
        }
    }
    #[test]
    fn insertion_and_append_fees_also_precede_reserve() {
        // Enough for metadata plus first buffer storage, but not the final
        // insertion. The buffer must still have no allocation on failure.
        let slot = slots::<[u64; 16]>();
        let w = Work::limited([128, 8192, 8 + 3 + 4 * slot]);
        let mut q = VecDeque::new();
        assert_eq!(
            push_deque(&mut q, [0u64; 16], &w).unwrap_err().kind,
            "step_budget"
        );
        assert!(q.is_empty());
        assert_eq!(q.capacity(), 0);
        let w = Work::limited([128, 8192, 8]);
        let mut v = Vec::with_capacity(1);
        v.push([1u64; 16]);
        let mut other = vec![[2u64; 16]];
        let cap = v.capacity();
        let before = v.clone();
        let extra = other.clone();
        assert_eq!(
            append(&mut v, &mut other, &w).unwrap_err().kind,
            "step_budget"
        );
        let used = w.spent();
        for _ in 0..2 {
            assert_eq!(
                append(&mut v, &mut other, &w).unwrap_err().kind,
                "step_budget"
            );
            assert_eq!(w.spent(), used);
        }
        assert_eq!(v, before);
        assert_eq!(other, extra);
        assert_eq!(v.capacity(), cap);
    }
    #[test]
    fn minimum_buffers_zero_sized_items_and_capacity_overflow_are_bounded() {
        let w = Work::limited([128, 8192, 1_000_000_000]);
        assert_eq!(growth::<u8>(0, 0, 1, &w).unwrap(), Some(8));
        assert_eq!(growth::<u64>(0, 0, 1, &w).unwrap(), Some(4));
        assert_eq!(growth::<[u8; 2048]>(0, 0, 1, &w).unwrap(), Some(1));
        let mut z = Vec::<()>::new();
        push_vec(&mut z, (), &w).unwrap();
        assert_eq!(z.len(), 1);
        assert_eq!(z.capacity(), usize::MAX);
        assert_eq!(
            growth::<u64>(usize::MAX, 0, 1, &w).unwrap_err().kind,
            "step_budget"
        );
    }

    fn wrapped_queue() -> VecDeque<u64> {
        let mut q = VecDeque::with_capacity(4);
        let capacity = q.capacity();
        for i in 0..capacity {
            q.push_back(i as u64)
        }
        let shifted = capacity / 2;
        for _ in 0..shifted {
            q.pop_front();
        }
        for i in 0..shifted {
            q.push_back((capacity + i) as u64)
        }
        assert_eq!(q.len(), capacity);
        assert!(!q.as_slices().1.is_empty());
        q
    }
    #[test]
    fn wrapped_deque_funds_raw_buffer_and_additional_fragment_moves() {
        let mut q = wrapped_queue();
        let before = q.iter().copied().collect::<Vec<_>>();
        let cap = q.capacity();
        let len = q.len();
        let next = (cap * 2).max(len + 1).max(4);
        let slot = slots::<u64>();
        let cost = 8 + 3 + ((next + 2 * len + 1) as u64) * slot;
        let w = Work::limited([128, 8192, cost]);
        let (result, report) =
            crate::diagnostics::capture(Default::default(), || push_deque(&mut q, 99, &w));
        result.unwrap();
        assert_eq!(w.spent(), cost);
        assert_eq!(report.counters.get("history_storage_growth"), Some(&1));
        let mut expected = before;
        expected.push(99);
        assert_eq!(q.iter().copied().collect::<Vec<_>>(), expected);
        assert!(q.capacity() > cap);
    }
    #[test]
    fn wrapped_extra_move_failure_precedes_reserve_and_two_retries_are_sticky() {
        let mut q = wrapped_queue();
        let before = q.iter().copied().collect::<Vec<_>>();
        let cap = q.capacity();
        let len = q.len();
        let next = (cap * 2).max(len + 1).max(4);
        let slot = slots::<u64>();
        // The prior model's buffer+raw move+insert would fit. Only the newly
        // accounted wrapped-fragment move makes this reservation fail.
        let old_cost = 8 + 3 + ((next + len + 1) as u64) * slot;
        let w = Work::limited([128, 8192, old_cost]);
        let (result, report) =
            crate::diagnostics::capture(Default::default(), || push_deque(&mut q, 99, &w));
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(!report.counters.contains_key("history_storage_growth"));
        assert_eq!(q.capacity(), cap);
        assert_eq!(q.iter().copied().collect::<Vec<_>>(), before);
        let used = w.spent();
        for _ in 0..2 {
            let (result, report) =
                crate::diagnostics::capture(Default::default(), || push_deque(&mut q, 99, &w));
            assert_eq!(result.unwrap_err().kind, "step_budget");
            assert_eq!(w.spent(), used);
            assert!(report.counters.is_empty());
            assert!(report.stages.is_empty());
            assert_eq!(q.capacity(), cap);
            assert_eq!(q.iter().copied().collect::<Vec<_>>(), before);
        }
    }
}
