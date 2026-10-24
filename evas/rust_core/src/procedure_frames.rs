//! Candidate-only frames shared by the steps of one proven occurrence.
use crate::{event_conditions::Selection, ir::Error, transition_source_plan::Work};
pub(crate) struct Frames<'a, T> {
    selection: &'a Selection,
    frames: Vec<Option<T>>,
}
impl<'a, T> Frames<'a, T> {
    pub(crate) fn new(selection: &'a Selection, work: Option<&Work>) -> Result<Self, Error> {
        let len = selection.procedure_groups.len();
        if let Some(w) = work {
            w.debit(
                2,
                (len as u64).saturating_mul(
                    std::mem::size_of::<Option<T>>().div_ceil(std::mem::size_of::<usize>()) as u64,
                ),
            )?;
        }
        Ok(Self {
            selection,
            frames: (0..len).map(|_| None).collect(),
        })
    }
    pub(crate) fn take(&mut self, event: usize) -> Option<T> {
        self.selection
            .procedure_groups
            .get(event)
            .copied()
            .flatten()
            .and_then(|g| self.frames.get_mut(g)?.take())
    }
    pub(crate) fn put(&mut self, event: usize, value: T) {
        if let Some(g) = self
            .selection
            .procedure_groups
            .get(event)
            .copied()
            .flatten()
        {
            self.frames[g] = Some(value);
        }
    }
}
pub(crate) fn ordered(selection: &Selection, a: usize, b: usize) -> bool {
    selection
        .procedure_groups
        .get(a)
        .copied()
        .flatten()
        .is_some_and(|g| selection.procedure_groups.get(b) == Some(&Some(g)))
}
