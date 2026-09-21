"""Builds each account's features for a month, from tables the carrier holds.

Every phase uses the same features: the churn model (Phase 2), the uplift model (Phase 3),
the optimizer (Phase 5), and the agent's nightly run. A row describes an account as of the end
of a month, using only that month and earlier.
"""

import numpy as np
import pandas as pd

DEVICE_TERM = 24
CODES = ['billing', 'network', 'device', 'service', 'account']

PANEL_FIELDS = [
    'bill', 'bill_change', 'data_gb', 'throttle_days', 'dropped_call_rate', 'care_contacts',
    'unresolved_ticket', 'late_payment', 'device_age', 'months_to_payoff', 'competitor_promo',
]
WINDOW_FIELDS = [
    'bill_change_max_3m', 'care_contacts_3m', 'throttle_days_3m', 'dropped_call_rate_3m',
    'late_payments_3m', 'competitor_promo_max_3m',
]
CODE_FIELDS = [f'{c}_contacts_6m' for c in CODES]
ACCOUNT_FIELDS = ['plan', 'lines', 'autopay', 'region_id']
DERIVED_FIELDS = ['tenure', 'months_since_payoff']
FEATURES = PANEL_FIELDS + WINDOW_FIELDS + CODE_FIELDS + DERIVED_FIELDS + ACCOUNT_FIELDS
CATEGORIES = {'plan': ['unlimited_plus', 'unlimited', '15gb'], 'region_id': list(range(8))}
AGING = ['tenure', 'device_age', 'months_since_payoff']


def build_features(panel, accounts, contacts):
    """Features for every account-month in the panel, plus whether the account left the next month.

    `left_next_month` is missing in the panel's last month, where the next month isn't observed yet.
    Rows for the month an account leaves are dropped: the account is gone by the end of it.
    """

    df = panel.sort_values(['account_id', 'month']).reset_index(drop = True)
    grouped = df.groupby('account_id', sort = False)

    def rolling(column, how, window, by = None):
        g = (by if by is not None else grouped)[column].rolling(window, min_periods = 1)
        return getattr(g, how)().reset_index(level = 0, drop = True).astype(float)

    df['late_payment'] = df['late_payment'].astype(int)
    df['bill_change_max_3m'] = rolling('bill_change', 'max', 3)
    df['care_contacts_3m'] = rolling('care_contacts', 'sum', 3)
    df['throttle_days_3m'] = rolling('throttle_days', 'sum', 3)
    df['dropped_call_rate_3m'] = rolling('dropped_call_rate', 'mean', 3)
    df['late_payments_3m'] = rolling('late_payment', 'sum', 3)
    df['competitor_promo_max_3m'] = rolling('competitor_promo', 'max', 3)

    codes = (contacts.groupby(['account_id', 'month', 'reason_code']).size().unstack('reason_code')
             .reindex(columns = CODES).fillna(0).astype(int).reset_index())
    df = df.merge(codes, on = ['account_id', 'month'], how = 'left')
    df[CODES] = df[CODES].fillna(0).astype(int)
    grouped = df.groupby('account_id', sort = False)
    for code in CODES:
        df[f'{code}_contacts_6m'] = rolling(code, 'sum', 6, grouped)

    nxt = grouped[['month', 'churned']].shift(-1)
    df['left_next_month'] = np.where(nxt['month'].eq(df['month'] + 1), nxt['churned'].astype(float), np.nan)

    df = df.merge(accounts[['account_id', 'join_month'] + ACCOUNT_FIELDS], on = 'account_id')
    df['tenure'] = df['month'] - df['join_month']
    df['months_since_payoff'] = df['device_age'] - DEVICE_TERM
    df = df[~df['churned']].drop(columns = CODES + ['join_month', 'churned'])

    return df[['account_id', 'month'] + FEATURES + ['left_next_month']].reset_index(drop = True)


def offer_windows(campaigns, months = 6):
    """(account, month) pairs whose next-month churn an offer could have changed.

    An offer made in month m affects months m+1 … m+`months`, so the features of months
    m … m+`months`-1 have a treated label. Control-arm accounts are never offered anything.
    """

    offered = campaigns.loc[campaigns['arm'] != 'control', ['account_id', 'month']]
    windows = [offered.assign(month = offered['month'] + k) for k in range(months)]

    return pd.concat(windows, ignore_index = True).drop_duplicates()


def age(features, months):
    """The same features `months` later, if nothing changed but time: tenure and the phone age."""

    aged = features.copy()
    for column in AGING:
        aged[column] = aged[column] + months
    aged['months_to_payoff'] = np.maximum(aged['months_to_payoff'] - months, 0)

    return aged


def as_model_frame(features):
    """Model-ready columns, with categorical fields typed for LightGBM."""

    X = features[FEATURES].copy()
    for column, categories in CATEGORIES.items():
        X[column] = pd.Categorical(X[column], categories = categories)
    X['autopay'] = X['autopay'].astype(int)
    X['unresolved_ticket'] = X['unresolved_ticket'].astype(int)
    X['late_payment'] = X['late_payment'].astype(int)

    return X
