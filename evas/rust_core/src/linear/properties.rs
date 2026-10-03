//! Supplemental generated systems: dyadic coefficients give an exact known RHS.
use super::{dense, sparse, Row};
use proptest::prelude::*;
use std::collections::BTreeMap;

proptest! {
    #![proptest_config(ProptestConfig::with_cases(128))]
    #[test]
    fn generated_diagonally_dominant_systems_recover_independent_solution(
        size in 32usize..97,
        edges in prop::collection::vec((any::<u16>(), -4i8..5), 384),
        roots in prop::collection::vec(-32i8..33, 96),
    ) {
        let expected:Vec<_>=roots[..size].iter().map(|&x| f64::from(x)/8.0).collect();
        let mut rows:Vec<Row>=Vec::new();
        for i in 0..size {
            let mut row=BTreeMap::from([(i,1.0)]);
            for &(column, value) in &edges[4*i..4*i+4] {
                let column=usize::from(column)%size;
                if column != i { *row.entry(column).or_default() += f64::from(value)/256.0; }
            }
            rows.push(row.into_iter().filter(|(_,v)| *v != 0.0).collect());
        }
        // All terms fit exactly in binary64: small dyadic matrix * dyadic roots.
        let rhs:Vec<_>=rows.iter().map(|r| r.iter().map(|&(j,a)| a*expected[j]).sum::<f64>()).collect();
        let matrix=rows.iter().map(|row| {
            let mut dense=vec![0.0;size];
            for &(j,a) in row { dense[j]=a; }
            dense
        }).collect();
        let dense=dense::Factorization::new(matrix,size).unwrap().solve(rhs.clone()).unwrap();
        let sparse=sparse::Factorization::new(rows.clone(),size).unwrap().solve(rhs.clone()).unwrap();
        for actual in [&dense,&sparse] {
            for (a,b) in actual.iter().zip(&expected) { prop_assert!((a-b).abs()<1e-12); }
            for (row,b) in rows.iter().zip(&rhs) {
                let residual=row.iter().map(|&(j,a)| a*actual[j]).sum::<f64>()-b;
                prop_assert!(residual.abs()<1e-12);
            }
        }
    }
}
