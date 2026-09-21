"""Uplift learners: how much an offer lowers each customer's churn, from a randomized test.

Uplift here is the reduction in the probability of leaving: control churn minus offer churn,
so a positive value means the offer keeps the customer. Each learner takes features X, a 0/1
offer flag t, and a 0/1 churn outcome y, and returns a model with `predict_uplift(X)`.

Meta-learners, with LightGBM churn models:
- T-learner: separate churn models for offered and control customers; uplift is their difference.
- X-learner: imputes each customer's effect from the other group's model, then models those
  effects directly, which helps when the effect is simpler than churn itself.
- DR-learner: models a doubly robust pseudo-outcome, cross-fitted, which stays unbiased if either
  the churn models or the (known, randomized) offer probability is right.
- Flag DR-learner: the same pseudo-outcome, but the effect model is a ridge regression on a
  handful of situation flags. With a rare outcome and a test of this size, a flexible effect
  model fits noise; a constrained one can't.
- Risk-scaled logit: a logistic regression of churn on section 01's churn risk, the flags, the
  offer, and offer-by-flag interactions. An offer scales a customer's odds of leaving, so its
  uplift grows with risk as well as with the situation.
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import KFold

FLAGS = [
    'price_pressure', 'billing_6m', 'service_6m', 'device_6m', 'network_6m', 'account_6m',
    'near_payoff', 'old_device', 'plan_15gb', 'capped_15gb', 'long_tenure', 'no_contacts_6m',
    'pressure_x_billing', 'payoff_x_device', 'payoff_x_old', 'long_x_quiet',
]

OUTCOME_SETTINGS = dict(
    objective = 'binary', n_estimators = 300, learning_rate = 0.03, num_leaves = 15, min_child_samples = 200,
    subsample = 0.8, subsample_freq = 1, colsample_bytree = 0.8, reg_lambda = 1.0, verbose = -1)
EFFECT_SETTINGS = dict(
    objective = 'regression', n_estimators = 200, learning_rate = 0.03, num_leaves = 7, min_child_samples = 400,
    subsample = 0.8, subsample_freq = 1, colsample_bytree = 0.8, reg_lambda = 5.0, verbose = -1)


def _outcome_model(X, y, seed):
    return lgb.LGBMClassifier(**OUTCOME_SETTINGS, random_state = seed).fit(X, y)


def _effect_model(X, target, seed):
    return lgb.LGBMRegressor(**EFFECT_SETTINGS, random_state = seed).fit(X, target)


def situation_flags(features):
    """0/1 flags for the situations an offer is meant for, from `retention.features` rows."""

    f = features
    d = pd.DataFrame(index = f.index)
    d['price_pressure'] = (f['bill_change_max_3m'] > 0.05) | (f['competitor_promo_max_3m'] > 0.4)
    for code in ['billing', 'service', 'device', 'network', 'account']:
        d[f'{code}_6m'] = f[f'{code}_contacts_6m'] > 0
    d['near_payoff'] = f['months_to_payoff'] <= 3
    d['old_device'] = f['device_age'] >= 30
    d['plan_15gb'] = f['plan'] == '15gb'
    d['capped_15gb'] = d['plan_15gb'] & (f['throttle_days_3m'] > 0)
    d['long_tenure'] = f['tenure'] >= 36
    d['no_contacts_6m'] = f[[c for c in f.columns if c.endswith('_contacts_6m')]].sum(axis = 1) == 0
    d['pressure_x_billing'] = d['price_pressure'] & d['billing_6m']
    d['payoff_x_device'] = d['near_payoff'] & d['device_6m']
    d['payoff_x_old'] = d['near_payoff'] & d['old_device']
    d['long_x_quiet'] = d['long_tenure'] & d['no_contacts_6m']

    return d[FLAGS].astype(float)


class TLearner:

    def fit(self, X, t, y, seed = 0):
        self.control = _outcome_model(X[t == 0], y[t == 0], seed)
        self.offered = _outcome_model(X[t == 1], y[t == 1], seed)
        return self

    def predict_uplift(self, X):
        return self.control.predict_proba(X)[:, 1] - self.offered.predict_proba(X)[:, 1]


class XLearner:

    def fit(self, X, t, y, seed = 0):
        control = _outcome_model(X[t == 0], y[t == 0], seed)
        offered = _outcome_model(X[t == 1], y[t == 1], seed)
        # Effect imputed for each customer: what the other arm's model expects, minus what happened
        effect_offered = control.predict_proba(X[t == 1])[:, 1] - y[t == 1]
        effect_control = y[t == 0] - offered.predict_proba(X[t == 0])[:, 1]
        self.tau_offered = _effect_model(X[t == 1], effect_offered, seed)
        self.tau_control = _effect_model(X[t == 0], effect_control, seed)
        self.share_offered = t.mean()
        return self

    def predict_uplift(self, X):
        # Weight each effect model by how much data stands behind the other arm's imputation
        e = self.share_offered
        return e * self.tau_control.predict(X) + (1 - e) * self.tau_offered.predict(X)


class DRLearner:

    def fit(self, X, t, y, seed = 0, folds = 2):
        # Churn models for each arm, cross-fitted so no row is scored by a model that saw it
        e = t.mean()
        mu0 = np.zeros(len(y))
        mu1 = np.zeros(len(y))
        for train, held in KFold(folds, shuffle = True, random_state = seed).split(X):
            tr_t, tr_y = t[train], y[train]
            mu0[held] = _outcome_model(X.iloc[train][tr_t == 0], tr_y[tr_t == 0], seed).predict_proba(X.iloc[held])[:, 1]
            mu1[held] = _outcome_model(X.iloc[train][tr_t == 1], tr_y[tr_t == 1], seed).predict_proba(X.iloc[held])[:, 1]
        pseudo = (mu0 - mu1) + (1 - t) * (y - mu0) / (1 - e) - t * (y - mu1) / e
        self.tau = self._effect_model(X, pseudo, seed)
        return self

    def _effect_model(self, X, pseudo, seed):
        return _effect_model(X, pseudo, seed)

    def predict_uplift(self, X):
        return self.tau.predict(X)


class FlagDRLearner(DRLearner):
    """DR-learner whose effect model is a ridge regression on the situation flags in X."""

    alpha = 100.0

    def _effect_model(self, X, pseudo, seed):
        return Ridge(alpha = self.alpha).fit(X[FLAGS], pseudo)

    def predict_uplift(self, X):
        return self.tau.predict(X[FLAGS])


class RiskScaledLogit:
    """Logistic churn model: risk, flags, offer, and offer-by-flag terms. Needs `p_churn_90` in X."""

    C = 0.3

    def _design(self, X, t):
        risk = logit(np.clip(X['p_churn_90'].to_numpy(), 1e-4, 0.99))[:, None]
        flags = X[FLAGS].to_numpy()
        return np.hstack([risk, flags, t[:, None], flags * t[:, None]])

    def fit(self, X, t, y, seed = 0):
        self.model = LogisticRegression(C = self.C, max_iter = 2000).fit(self._design(X, t), y)
        return self

    def churn(self, X, offered):
        return self.model.predict_proba(self._design(X, np.full(len(X), offered)))[:, 1]

    def predict_uplift(self, X):
        return self.churn(X, 0) - self.churn(X, 1)

    def odds_multipliers(self):
        """How the offer multiplies the odds of leaving: overall, and added by each flag."""
        k = len(FLAGS)
        coef = self.model.coef_[0]
        return pd.Series(np.exp(np.r_[coef[1 + k], coef[2 + k:]]), index = ['offer'] + FLAGS)


LEARNERS = {'T-learner': TLearner, 'X-learner': XLearner, 'DR-learner': DRLearner,
            'Flag DR-learner': FlagDRLearner, 'Risk-scaled logit': RiskScaledLogit}


def cross_predict(learner, X, t, y, folds = 5, seed = 0):
    """Out-of-fold uplift for every row: each row is scored by a model that never saw it."""

    uplift = np.zeros(len(y))
    for train, held in KFold(folds, shuffle = True, random_state = seed).split(X):
        model = learner().fit(X.iloc[train], t[train], y[train], seed = seed)
        uplift[held] = model.predict_uplift(X.iloc[held])

    return uplift
