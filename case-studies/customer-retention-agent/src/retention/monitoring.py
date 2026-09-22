"""Checks the nightly job runs before trusting its models: input drift and churn calibration.

Two signals, either of which triggers retraining:
- Population stability index (PSI) on the model's inputs, this month against last month. Below 0.1
  is stable; 0.1–0.25 is a shift worth watching; above 0.25 the population changed suddenly.
  PSI against the training window is reported too, but doesn't trigger anything: a training window
  that contained a price increase or a promotion differs from every ordinary month (section 06).
- Calibration: predicted next-month churn against what happened, once the month is known.
"""

import numpy as np
import pandas as pd

MONITORED = [
    'bill_change_max_3m', 'competitor_promo_max_3m', 'dropped_call_rate_3m', 'care_contacts_3m',
    'throttle_days_3m', 'device_age', 'months_to_payoff', 'tenure', 'bill',
]
PSI_WATCH = 0.10
PSI_ALERT = 0.25
CALIBRATION_ALERT = 0.20


def psi(expected, actual, bins = 10):
    """Population stability index of `actual` against `expected`, on the expected distribution's deciles."""

    expected, actual = np.asarray(expected, dtype = float), np.asarray(actual, dtype = float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        edges = np.unique(np.r_[expected.min(), np.median(expected), expected.max()])
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)

    return float(np.sum((a - e) * np.log(a / e)))


def drift_report(baseline, current, columns = MONITORED):
    """PSI for each monitored input, with its status."""

    report = pd.DataFrame({'psi': {c: psi(baseline[c], current[c]) for c in columns}})
    report['status'] = np.select([report['psi'] > PSI_ALERT, report['psi'] > PSI_WATCH], ['alert', 'watch'], 'stable')

    return report.sort_values('psi', ascending = False)


def calibration_gap(predicted, observed):
    """Relative gap between mean predicted and observed churn: +0.2 means 20% over-predicted."""

    return float(np.mean(predicted) / max(np.mean(observed), 1e-9) - 1)


def should_retrain(drift, calibration = None):
    """Retrain when any input shifted sharply since last month, or the latest known month is off by more than 20%."""

    reasons = [f'{c}: PSI {r.psi:.2f}' for c, r in drift.iterrows() if r.status == 'alert']
    if calibration is not None and abs(calibration) > CALIBRATION_ALERT:
        reasons.append(f'calibration off by {calibration:+.0%}')

    return bool(reasons), reasons
