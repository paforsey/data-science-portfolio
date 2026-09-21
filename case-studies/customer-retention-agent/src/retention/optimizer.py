"""Chooses whom to contact tonight, with which offer, within the retention budget.

Every number comes from the models, not the language model: section 01's churn risk, section 02's
uplift and acceptance, and section 03's reason. The agent calls `plan_tonight()` as a tool.

Two guardrails come from section 04's evidence. The budget caps exposure, what the offers would
cost if every one were accepted, because the customers an offer helps are also the ones who take
it. And only offers whose randomized test showed an effect are used.
"""

import numpy as np
import pandas as pd

from . import policy

MARGIN_RATE = 0.55
DEVICE_PAYMENT_PER_LINE = 22.0
VALUE_MONTHS = 24
MONTHLY_DISCOUNT = 0.99
REASON_BOOST = {'discount': ['price'], 'device': ['device'], 'data': ['price']}


def customer_value(rows, p_churn_90):
    """Expected 24-month margin: service margin times the chance of still being a customer each month.

    The monthly churn rate is the one implied by the 90-day risk, held constant; the service bill
    excludes device installments, which are the phone's cost, not margin.
    """

    financed = rows['months_to_payoff'].to_numpy() > 0
    service_bill = rows['bill'].to_numpy() - np.where(financed, DEVICE_PAYMENT_PER_LINE * rows['lines'].to_numpy(), 0.0)
    monthly = 1 - (1 - np.asarray(p_churn_90)) ** (1 / 3)
    k = np.arange(1, VALUE_MONTHS + 1)
    survival = (1 - monthly[:, None]) ** k

    return (service_bill[:, None] * MARGIN_RATE * survival * MONTHLY_DISCOUNT ** k).sum(axis = 1)


def build_candidates(snapshot, churn_scores, uplift_scores, reasons, month, adjust_by_reason = True,
                     offers = None, accept_rates = None):
    """One row per eligible account and offer, with its expected benefit and expected cost.

    `adjust_by_reason`: no offer for customers whose rep codes point to a move, and the uplift of the
    offer that matches the reason doubled for ranking (section 03). `offers`: the offers allowed.
    `accept_rates`: per-offer acceptance rates to use instead of the per-customer model.
    """

    rows = (snapshot.merge(churn_scores[['account_id', 'p_churn_90']], on = 'account_id')
            .merge(uplift_scores, on = 'account_id')
            .merge(reasons[['account_id', 'reason_from_codes']], on = 'account_id', how = 'left'))
    rows['value'] = customer_value(rows, rows['p_churn_90'])
    allowed = policy.eligible(rows, month)

    candidates = []
    for offer in offers or policy.OFFERS:
        uplift = rows[f'uplift_{offer}'].to_numpy()
        if adjust_by_reason:
            reason = rows['reason_from_codes'].fillna('none')
            uplift = np.where(reason.eq('moving'), 0.0, uplift)
            uplift = np.where(reason.isin(REASON_BOOST[offer]), uplift * 2, uplift)
        accept = np.full(len(rows), accept_rates[offer]) if accept_rates else rows[f'accept_{offer}'].to_numpy()
        candidates.append(pd.DataFrame({
            'account_id': rows['account_id'], 'offer': offer, 'eligible': allowed[offer].to_numpy(),
            'p_churn_90': rows['p_churn_90'], 'uplift': uplift, 'accept': accept, 'value': rows['value'],
            'reason': rows['reason_from_codes'],
        }))
    candidates = pd.concat(candidates, ignore_index = True)
    candidates = candidates[candidates['eligible']].drop(columns = 'eligible')
    candidates['exposure'] = candidates['offer'].map(policy.OFFER_COST)
    candidates['expected_cost'] = candidates['accept'] * candidates['exposure']
    candidates['expected_benefit'] = candidates['uplift'] * candidates['value']
    candidates['net_value'] = candidates['expected_benefit'] - candidates['expected_cost']

    return candidates.reset_index(drop = True)


def select_greedy(candidates, budget, score = 'net_value', budget_on = 'exposure'):
    """At most one offer per account, best value per budget dollar first, until the budget is spent.

    Only offers expected to pay for themselves are considered. Each account keeps its offer with the
    best ratio; accounts are then taken in ratio order while the budget lasts. `budget_on` is
    'exposure' (cost if accepted) or 'expected_cost' (cost times acceptance).
    """

    pool = candidates[candidates[score] > 0].copy()
    pool['ratio'] = pool[score] / pool[budget_on]
    pool = pool.sort_values('ratio', ascending = False).drop_duplicates('account_id')
    chosen = pool[pool[budget_on].cumsum() <= budget]

    return chosen.drop(columns = 'ratio').reset_index(drop = True)


def select_exact(candidates, budget, score = 'net_value', budget_on = 'exposure', time_limit = 120):
    """The same choice as an integer program: maximize total score, one offer per account, within budget."""

    import pulp

    pool = candidates[candidates[score] > 0].reset_index(drop = True)
    problem = pulp.LpProblem('retention_offers', pulp.LpMaximize)
    x = [pulp.LpVariable(f'x{i}', cat = 'Binary') for i in range(len(pool))]
    problem += pulp.lpSum(s * v for s, v in zip(pool[score], x))
    problem += pulp.lpSum(c * v for c, v in zip(pool[budget_on], x)) <= budget
    for _, idx in pool.groupby('account_id').indices.items():
        if len(idx) > 1:
            problem += pulp.lpSum(x[i] for i in idx) <= 1
    problem.solve(pulp.PULP_CBC_CMD(msg = False, timeLimit = time_limit))
    picked = np.array([v.value() for v in x]) > 0.5

    return pool[picked].reset_index(drop = True)


def plan_tonight(candidates, budget, holdout_share = 0.1, seed = 0):
    """The agent's tool: tonight's offers, with the numbers behind each, and a summary.

    A random `holdout_share` of the chosen customers is held back and not contacted, so the realized
    effect of the plan can be measured against them (section 06).
    """

    chosen = select_greedy(candidates, budget)
    chosen['holdout'] = np.random.default_rng(seed).random(len(chosen)) < holdout_share
    contacted = chosen[~chosen['holdout']]
    summary = {
        'customers': len(contacted),
        'held_out': int(chosen['holdout'].sum()),
        'exposure': round(float(contacted['exposure'].sum()), 2),
        'expected_cost': round(float(contacted['expected_cost'].sum()), 2),
        'model_customers_kept': round(float(contacted['uplift'].sum()), 1),
        'by_offer': contacted['offer'].value_counts().to_dict(),
    }

    return chosen, summary
