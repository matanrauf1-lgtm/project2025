import numpy as np
import pandas as pd
import pytest

from ism_core import (
    transitive_closure, compute_ism_levels, ism_cycle_members,
    classify_micmac, compute_godet_micmac, compute_katz_micmac, build_analysis_results,
)


def make_irm(factors, edges):
    irm = pd.DataFrame(0, index=factors, columns=factors)
    for f in factors:
        irm.loc[f, f] = 1
    for a, b in edges:
        irm.loc[a, b] = 1
    return irm


CHAIN = ['A', 'B', 'C', 'D']
CHAIN_EDGES = [('A', 'B'), ('B', 'C'), ('C', 'D')]


def test_transitive_closure_chain():
    frm = transitive_closure(make_irm(CHAIN, CHAIN_EDGES))
    expected = np.triu(np.ones((4, 4), dtype=int))
    assert (frm.values == expected).all()


def test_transitive_closure_keeps_existing_cycle():
    frm = transitive_closure(make_irm(['A', 'B', 'C'], [('A', 'B'), ('B', 'C'), ('C', 'A')]))
    assert frm.values.all()


def test_levels_chain_most_dependent_first():
    frm = transitive_closure(make_irm(CHAIN, CHAIN_EDGES))
    assert compute_ism_levels(frm) == [['D'], ['C'], ['B'], ['A']]


def test_levels_cycle_shares_level():
    factors = ['A', 'B', 'C']
    frm = transitive_closure(make_irm(factors, [('A', 'B'), ('B', 'A'), ('B', 'C')]))
    levels = compute_ism_levels(frm)
    assert levels == [['C'], ['A', 'B']]
    assert ism_cycle_members(frm) == {'A', 'B'}


def test_classify_micmac_quadrants():
    dp = pd.Series({'drv': 10, 'lnk': 10, 'dep': 1, 'aut': 1})
    dep = pd.Series({'drv': 1, 'lnk': 10, 'dep': 10, 'aut': 1})
    cls = classify_micmac(dp, dep)['Classification']
    assert cls['drv'].startswith('Driving')
    assert cls['lnk'].startswith('Linkage')
    assert cls['dep'].startswith('Dependent')
    assert cls['aut'].startswith('Autonomous')


def test_katz_matches_godet_on_acyclic_graph():
    irm = make_irm(CHAIN, CHAIN_EDGES)
    dp_g, dep_g, _ = compute_godet_micmac(irm)
    dp_k, dep_k, alpha = compute_katz_micmac(irm)
    assert alpha == 1.0
    assert np.allclose(dp_g, dp_k) and np.allclose(dep_g, dep_k)


def test_katz_alpha_below_inverse_spectral_radius():
    irm = make_irm(['A', 'B', 'C'], [('A', 'B'), ('B', 'C'), ('C', 'A'), ('A', 'C')])
    M = irm.values.astype(float)
    np.fill_diagonal(M, 0)
    rho = max(abs(np.linalg.eigvals(M)))
    _, _, alpha = compute_katz_micmac(irm)
    assert 0 < alpha < 1 / rho


def test_katz_keeps_short_paths_with_two_cycle():
    # מעגל באורך 2 (A↔B) ועוד מסלול קצר B→C: בחזקה בודדת של Godet הקשת B→C
    # מופיעה רק בחזקות אי-זוגיות; בסכום המצטבר היא תמיד נספרת.
    irm = make_irm(['A', 'B', 'C'], [('A', 'B'), ('B', 'A'), ('B', 'C')])
    dp, dep, _ = compute_katz_micmac(irm)
    assert dep['C'] > 0
    assert dp['B'] > dp['A'] > dp['C'] == 0
    assert dp.sum() == pytest.approx(100)


def test_katz_distinguishes_saturated_frm():
    factors = ['A', 'B', 'C', 'D']
    irm = make_irm(factors, [('A', 'B'), ('A', 'C'), ('A', 'D'), ('B', 'C'), ('C', 'D'), ('D', 'A')])
    frm = transitive_closure(irm)
    classic = classify_micmac(frm.sum(axis=1), frm.sum(axis=0))
    res = build_analysis_results(irm, frm, classic)
    assert res['classic_degenerate']
    assert res['micmac_katz']['DP'].nunique() > 1
    assert res['micmac_katz']['DP'].idxmax() == 'A'


def test_empty_influence_returns_zeros():
    irm = make_irm(['A', 'B'], [])
    dp, dep, _ = compute_katz_micmac(irm)
    assert (dp == 0).all() and (dep == 0).all()
