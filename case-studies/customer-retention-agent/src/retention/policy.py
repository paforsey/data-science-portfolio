"""The offer policy's hard rules, as code.

`data/synthetic/offer_policy.md` states the rules in words; the rules marked (hard) there are
checked here, so the optimizer never proposes an offer the policy forbids and the agent's
compliance step can verify every draft. Each check takes `scoring_snapshot`-style rows.
"""

import pandas as pd

OFFERS = ['discount', 'device', 'data']
OFFER_COST = {'discount': 60.0, 'device': 200.0, 'data': 30.0}
OFFER_TERMS = {
    'discount': '$10 off the monthly bill for 6 months',
    'device': 'a $200 credit toward a new phone on a 24-month installment plan',
    'data': 'a free upgrade to unlimited data for 6 months',
}
CONTACT_GAP_MONTHS = 3
SMS_MAX_CHARACTERS = 320
OPT_OUT = 'Reply STOP to opt out.'


def can_contact(rows, month):
    """Not do-not-contact, and no retention offer in the past 90 days."""

    recent = rows['last_offer_month'].fillna(-99).astype(int) > month - CONTACT_GAP_MONTHS

    return ~rows['do_not_contact'].astype(bool) & ~recent


def eligible(rows, month):
    """One column per offer: True where the policy allows making that offer tonight."""

    contact = can_contact(rows, month)
    recent_discount = (rows['last_offer'].eq('discount') & rows['last_offer_accepted'].fillna(False).astype(bool)
                       & (rows['last_offer_month'].fillna(-99).astype(int) > month - 12))
    late = rows['late_payments_3m'].astype(int)

    return pd.DataFrame({
        'discount': contact & (rows['tenure'] >= 6) & ~recent_discount & (late <= 1),
        'device': contact & (rows['device_age'] >= 18) & (rows['months_to_payoff'] <= 3) & (late == 0),
        'data': contact & rows['plan'].eq('15gb'),
    }, index = rows.index)


OFFER_FACTS = {
    'discount': ['$10', '6 months'],
    'device': ['$200', '24-month'],
    'data': ['unlimited data', '6 months'],
}
BANNED = {
    'mentions churn or prediction': r'\b(churn|leave us|leaving us|thinking of leaving|might leave|at risk|risk score|predict)',
    'pressure or deadline': r'\b(act now|hurry|today only|limited time|last chance|expires?|before it\'s gone|don\'t miss)\b',
    'names a competitor': r'\b(verizon|at&t|t-mobile|sprint|us cellular|mint|visible|cricket)\b',
}


def check_message(text, channel = 'sms'):
    """Hard message rules: length and opt-out for SMS. Returns a list of problems, empty if none."""

    problems = []
    if channel == 'sms':
        if len(text) > SMS_MAX_CHARACTERS:
            problems.append(f'SMS is {len(text)} characters; the limit is {SMS_MAX_CHARACTERS}')
        if not text.rstrip().endswith(OPT_OUT):
            problems.append(f'SMS must end with "{OPT_OUT}"')

    return problems


def check_draft(text, offer, channel = 'sms'):
    """Every hard rule a draft must meet: message rules, the offer's exact terms, and banned content."""

    import re

    problems = check_message(text, channel)
    missing = [fact for fact in OFFER_FACTS[offer] if fact.lower() not in text.lower()]
    if missing:
        problems.append(f'offer terms missing: {", ".join(missing)}')
    for rule, pattern in BANNED.items():
        if re.search(pattern, text, flags = re.IGNORECASE):
            problems.append(rule)

    return problems
