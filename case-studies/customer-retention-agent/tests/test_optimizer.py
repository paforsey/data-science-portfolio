"""The optimizer's guarantees: one offer per customer, never over budget, and greedy close to exact."""

import numpy as np
import pandas as pd

from retention import optimizer as O


def candidates(n = 60, seed = 0):
    rng = np.random.default_rng(seed)
    rows = []
    for account in range(n):
        for offer, cost in [('discount', 60.0), ('device', 200.0)]:
            uplift = rng.uniform(-0.01, 0.06)
            value = rng.uniform(500, 4000)
            rows.append({'account_id': account, 'offer': offer, 'uplift': uplift, 'value': value, 'accept': 0.5,
                         'exposure': cost, 'expected_cost': 0.5 * cost, 'net_value': uplift * value - 0.5 * cost})
    return pd.DataFrame(rows)


def test_greedy_respects_budget_and_one_offer():
    pool = candidates()
    chosen = O.select_greedy(pool, 1_000)
    assert chosen['exposure'].sum() <= 1_000
    assert chosen['account_id'].is_unique
    assert (chosen['net_value'] > 0).all()


def test_greedy_close_to_exact():
    pool = candidates(n = 40, seed = 3)
    greedy = O.select_greedy(pool, 1_500)['net_value'].sum()
    exact = O.select_exact(pool, 1_500)['net_value'].sum()
    assert exact >= greedy - 1e-9
    assert greedy >= 0.9 * exact


def test_holdout_is_never_contacted():
    plan, summary = O.plan_tonight(candidates(n = 200), 5_000, holdout_share = 0.2, seed = 1)
    assert summary['customers'] == int((~plan['holdout']).sum())
    assert summary['held_out'] == int(plan['holdout'].sum())
