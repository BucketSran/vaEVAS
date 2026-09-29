//! Maintain exact active column degrees as numeric elimination changes fill.
//! This is a minimum-column-count heuristic, not AMD or COLAMD.
use std::collections::BTreeSet;

pub(super) struct Columns {
    rows: Vec<BTreeSet<usize>>,
    degrees: Option<BTreeSet<(usize, usize)>>,
    next: usize,
}

impl Columns {
    pub(super) fn new(rows: Vec<BTreeSet<usize>>, reorder: bool) -> Self {
        let degrees = reorder.then(|| {
            rows.iter()
                .enumerate()
                .map(|(col, ids)| (ids.len(), col))
                .collect()
        });
        Self {
            rows,
            degrees,
            next: 0,
        }
    }

    pub(super) fn take_next(&mut self) -> (usize, BTreeSet<usize>) {
        let column = match &mut self.degrees {
            Some(degrees) => degrees.pop_first().unwrap().1,
            None => {
                let column = self.next;
                self.next += 1;
                column
            }
        };
        (column, std::mem::take(&mut self.rows[column]))
    }

    pub(super) fn insert(&mut self, column: usize, row: usize) {
        let count = self.rows[column].len();
        if self.rows[column].insert(row) {
            if let Some(degrees) = &mut self.degrees {
                degrees.remove(&(count, column));
                degrees.insert((count + 1, column));
            }
        }
    }

    pub(super) fn remove(&mut self, column: usize, row: usize) {
        let count = self.rows[column].len();
        if self.rows[column].remove(&row) {
            if let Some(degrees) = &mut self.degrees {
                degrees.remove(&(count, column));
                degrees.insert((count - 1, column));
            }
        }
    }
}
