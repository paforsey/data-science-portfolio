"""Loads the synthetic tables, keeping the answer key out of reach of model code.

Model code calls load(), which refuses answer-key tables. Scoring cells call
load_answer_key(), and only after a model or policy is finished.
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / 'data' / 'synthetic'

MODEL_TABLES = [
    'accounts', 'monthly_panel', 'care_contacts', 'care_notes', 'campaigns', 'scoring_snapshot',
]
ANSWER_KEY_TABLES = [
    'truth_accounts', 'truth_potential_outcomes', 'truth_campaign_outcomes', 'truth_notes', 'future_panel',
    'generator_parameters',
]
POLICY_DOCUMENT = DATA / 'offer_policy.md'


def load(name):
    """Loads a table the carrier could actually hold. Answer-key tables are refused."""

    if name in ANSWER_KEY_TABLES:
        raise PermissionError(f'{name} is part of the withheld answer key; use load_answer_key() only when scoring')
    if name not in MODEL_TABLES:
        raise KeyError(f'unknown table {name!r}')

    return pd.read_parquet(DATA / f'{name}.parquet')


def load_answer_key(name):
    """Loads a withheld table. Used only in scoring cells, never to fit or tune a model."""

    if name not in ANSWER_KEY_TABLES:
        raise KeyError(f'{name!r} is not an answer-key table')

    return pd.read_parquet(DATA / f'{name}.parquet')


def load_policy():
    """Returns the offer policy document the agent retrieves from."""

    return POLICY_DOCUMENT.read_text(encoding = 'utf-8')
