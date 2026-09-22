"""The nightly pipeline: sections 01–04 as functions the scheduled job can call.

The notebooks explain and evaluate each step; this module runs them. It trains the churn model on
the latest 12 labeled months, trains the uplift models on the randomized test, scores a night's
accounts, and plans that night's offers with the section 04 guardrails.

Months after 24 don't exist in the model-facing data: the study withholds them. `observed_panel()`
releases them one month at a time, standing in for the new data a live carrier would receive.
"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import data, features as F, optimizer as O, policy as P, uplift as U

LAST_OBSERVED_MONTH = 24
TRAINING_WINDOW = 12
CAMPAIGN_1_MONTH = 13
HORIZONS = {1: 'p_churn_30', 2: 'p_churn_60', 3: 'p_churn_90'}
CHURN_SETTINGS = dict(
    objective = 'binary', n_estimators = 400, learning_rate = 0.03, num_leaves = 15, min_child_samples = 500,
    subsample = 0.8, subsample_freq = 1, colsample_bytree = 0.8, reg_lambda = 1.0, random_state = 20260921, verbose = -1)
CODE_TO_REASON = {'billing': 'price', 'network': 'network', 'device': 'device', 'service': 'service', 'account': 'moving'}


def observed_panel(through_month):
    """The monthly panel as the carrier would hold it at the end of `through_month`."""

    panel = data.load('monthly_panel')
    if through_month > LAST_OBSERVED_MONTH:
        feed = data.load_answer_key('future_panel')
        panel = pd.concat([panel, feed[feed['month'] <= through_month]], ignore_index = True)

    return panel[panel['month'] <= through_month]


def account_months(through_month):
    """Section 01's features for every account-month through `through_month`, with offer-affected months flagged."""

    rows = F.build_features(observed_panel(through_month), data.load('accounts'), data.load('care_contacts'))
    affected = F.offer_windows(data.load('campaigns')).assign(offer_affected = True)
    rows = rows.merge(affected, on = ['account_id', 'month'], how = 'left')
    rows['offer_affected'] = rows['offer_affected'].eq(True)

    return rows


@dataclass
class ChurnModel:
    model: lgb.LGBMClassifier
    trained_through: int

    def probabilities(self, rows):
        """30-, 60-, and 90-day churn, rolling the monthly hazard forward with tenure and the phone aging."""
        monthly = np.column_stack([self.model.predict_proba(F.as_model_frame(F.age(rows, k)))[:, 1] for k in range(3)])
        survival = np.cumprod(1 - monthly, axis = 1)
        return pd.DataFrame({name: 1 - survival[:, k - 1] for k, name in HORIZONS.items()}, index = rows.index)


def train_churn_model(rows, last_label_month):
    """The gradient-boosted hazard on the 12 months of labels ending at `last_label_month`."""

    window = rows[rows['month'].between(last_label_month - TRAINING_WINDOW, last_label_month - 1)
                  & rows['left_next_month'].notna() & ~rows['offer_affected']]
    model = lgb.LGBMClassifier(**CHURN_SETTINGS).fit(F.as_model_frame(window), window['left_next_month'].astype(int))

    return ChurnModel(model, last_label_month)


def uplift_inputs(rows, risk):
    X = F.as_model_frame(rows).reset_index(drop = True)
    X = pd.concat([X, U.situation_flags(rows).reset_index(drop = True)], axis = 1)
    X['p_churn_90'] = np.asarray(risk)

    return X


def train_uplift_models(rows):
    """Section 02's risk-scaled logit for each offer, on the randomized month-13 test."""

    campaigns = data.load('campaigns')
    test = rows[rows['month'] == CAMPAIGN_1_MONTH].merge(
        campaigns.loc[campaigns['campaign'] == 'campaign_1', ['account_id', 'arm', 'accepted']], on = 'account_id').reset_index(drop = True)
    panel = data.load('monthly_panel')
    left = set(panel.loc[panel['month'].between(CAMPAIGN_1_MONTH + 1, CAMPAIGN_1_MONTH + 3) & panel['churned'], 'account_id'])
    y = test['account_id'].isin(left).astype(int).to_numpy()
    risk = train_churn_model(rows, CAMPAIGN_1_MONTH).probabilities(test)['p_churn_90']
    X = uplift_inputs(test, risk)

    models, rates = {}, {}
    for offer in P.OFFERS:
        pair = test['arm'].isin(['control', offer]).to_numpy()
        t = (test.loc[pair, 'arm'] == offer).astype(int).to_numpy()
        models[offer] = U.RiskScaledLogit().fit(X[pair].reset_index(drop = True), t, y[pair])
        rates[offer] = float(test.loc[test['arm'] == offer, 'accepted'].mean())

    return models, rates, evidence_gate(test, y)


def evidence_gate(test, y):
    """Offers whose randomized effect on 90-day churn has a 95% interval above zero (section 04)."""

    control = y[test['arm'].eq('control').to_numpy()]
    passed = []
    for offer in P.OFFERS:
        offered = y[test['arm'].eq(offer).to_numpy()]
        effect = control.mean() - offered.mean()
        se = np.sqrt(control.mean() * (1 - control.mean()) / len(control) + offered.mean() * (1 - offered.mean()) / len(offered))
        if effect - 1.96 * se > 0:
            passed.append(offer)

    return passed


def code_reasons(through_month):
    """Each account's most common rep reason code through `through_month` (section 03)."""

    contacts = data.load('care_contacts')
    contacts = contacts[contacts['month'] <= through_month].assign(reason = lambda d: d['reason_code'].map(CODE_TO_REASON))
    counts = contacts.groupby(['account_id', 'reason']).agg(n = ('month', 'size'), last = ('month', 'max')).reset_index()
    best = counts.sort_values(['account_id', 'n', 'last']).groupby('account_id').tail(1)

    return best.rename(columns = {'reason': 'reason_from_codes'})[['account_id', 'reason_from_codes']]


def snapshot(rows, month):
    """The night's accounts: active at the end of `month`, with the fields the policy rules need."""

    tonight = rows[rows['month'] == month].drop(columns = ['left_next_month', 'offer_affected'])
    accounts = data.load('accounts')[['account_id', 'do_not_contact']]
    offers = data.load('campaigns').query('arm != "control"').sort_values('month').groupby('account_id').last()
    tonight = tonight.merge(accounts, on = 'account_id')
    tonight['last_offer_month'] = tonight['account_id'].map(offers['month']).astype('Int64')
    tonight['last_offer'] = tonight['account_id'].map(offers['arm'])
    tonight['last_offer_accepted'] = tonight['account_id'].map(offers['accepted']).astype('boolean')
    tonight['late_payments_3m'] = tonight['late_payments_3m'].astype(int)

    return tonight.reset_index(drop = True)


def plan_night(rows, month, churn_model, uplift_models, accept_rates, gated_offers, budget, holdout_share = 0.1, seed = 0):
    """The night's plan: score, build candidates with the guardrails, and select within the exposure budget."""

    tonight = snapshot(rows, month)
    risk = churn_model.probabilities(tonight)
    churn_scores = pd.concat([tonight[['account_id']], risk], axis = 1)
    X = uplift_inputs(tonight, risk['p_churn_90'])
    uplift_scores = tonight[['account_id']].copy()
    for offer, model in uplift_models.items():
        uplift_scores[f'uplift_{offer}'] = model.predict_uplift(X)
        uplift_scores[f'accept_{offer}'] = accept_rates[offer]
    candidates = O.build_candidates(tonight, churn_scores, uplift_scores, code_reasons(month), month,
                                    offers = gated_offers, accept_rates = accept_rates)
    plan, summary = O.plan_tonight(candidates, budget, holdout_share = holdout_share, seed = seed)

    return tonight, churn_scores, plan, summary
