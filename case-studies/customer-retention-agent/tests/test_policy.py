"""The policy's hard rules: every planted violation is caught, and a compliant message passes."""

import pandas as pd
import pytest

from retention import features as F, policy as P

COMPLIANT = f"Hi there! You can get {P.OFFER_TERMS['discount']}. Reply YES to add it. {P.OPT_OUT}"


def test_compliant_message_passes():
    assert P.check_draft(COMPLIANT, 'discount') == []


@pytest.mark.parametrize('message, problem', [
    ('Hi there! ' + 'We value you. ' * 30 + f"{P.OFFER_TERMS['discount']}. {P.OPT_OUT}", 'characters'),
    (f"Hi there! You can get {P.OFFER_TERMS['discount']}.", 'Reply STOP'),
    (f'Hi there! You can get $15 off for 3 months. {P.OPT_OUT}', 'offer terms missing'),
    (f"Hi there! Act now: {P.OFFER_TERMS['discount']}. {P.OPT_OUT}", 'pressure'),
    (f"Hi there! We noticed you might leave: {P.OFFER_TERMS['discount']}. {P.OPT_OUT}", 'churn'),
    (f"Hi there! Better than Verizon: {P.OFFER_TERMS['discount']}. {P.OPT_OUT}", 'competitor'),
])
def test_planted_violation_is_caught(message, problem):
    assert any(problem in p for p in P.check_draft(message, 'discount'))


def account(**fields):
    base = dict(do_not_contact = False, last_offer_month = pd.NA, last_offer = None, last_offer_accepted = pd.NA,
                late_payments_3m = 0, tenure = 24, device_age = 30, months_to_payoff = 0, plan = 'unlimited')
    return pd.DataFrame([base | fields]).astype({'last_offer_month': 'Int64', 'last_offer_accepted': 'boolean'})


def test_eligibility_rules():
    assert P.eligible(account(), 24).iloc[0].to_dict() == {'discount': True, 'device': True, 'data': False}
    assert not P.eligible(account(do_not_contact = True), 24).iloc[0].any()
    assert not P.eligible(account(last_offer_month = 23, last_offer = 'device', last_offer_accepted = False), 24).iloc[0].any()
    assert not P.eligible(account(tenure = 3), 24).at[0, 'discount']
    assert not P.eligible(account(last_offer_month = 19, last_offer = 'discount', last_offer_accepted = True), 24).at[0, 'discount']
    assert not P.eligible(account(months_to_payoff = 8), 24).at[0, 'device']
    assert P.eligible(account(plan = '15gb'), 24).at[0, 'data']


def test_accepted_offer_blocks_new_offers_for_six_months():
    accepted = dict(last_offer_month = 19, last_offer = 'device', last_offer_accepted = True)
    assert not P.eligible(account(**accepted), 24).iloc[0].any()
    assert P.eligible(account(**accepted), 25).at[0, 'discount']
    declined = dict(last_offer_month = 19, last_offer = 'device', last_offer_accepted = False)
    assert P.eligible(account(**declined), 24).at[0, 'discount']
    assert not P.eligible(account(last_offer_month = 22, last_offer = 'device', last_offer_accepted = False), 24).iloc[0].any()


def test_accepted_discount_still_blocks_the_discount_for_twelve_months():
    accepted = dict(last_offer_month = 19, last_offer = 'discount', last_offer_accepted = True)
    assert not P.eligible(account(**accepted), 30).at[0, 'discount']
    assert P.eligible(account(**accepted), 30).at[0, 'device']
    assert P.eligible(account(**accepted), 31).at[0, 'discount']


def test_accepted_offer_window_matches_the_policy_gap():
    campaigns = pd.DataFrame({'account_id': [1, 2], 'month': [19, 19], 'arm': ['device', 'device'], 'accepted': [True, False]})
    rows = pd.DataFrame({'account_id': [1, 1, 2], 'month': [24, 25, 24]})
    assert F.in_accepted_offer_window(rows, campaigns).tolist() == [True, False, False]
