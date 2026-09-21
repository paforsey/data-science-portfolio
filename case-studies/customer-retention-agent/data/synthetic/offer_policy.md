# Retention Offer Policy

Synthetic policy for the AI Customer Retention Agent case study. Offers and terms are illustrative.

## Offers and exact terms
- **Loyalty discount:** $10 off the monthly bill for 6 months.
- **Device upgrade credit:** a $200 credit toward a new phone on a 24-month installment plan.
- **Data upgrade:** a free upgrade to unlimited data for 6 months, for the 15 GB plan.
Describe an offer only with these terms. Never add, round, or combine offers.

## Eligibility: loyalty discount (hard)
- Customer for at least 6 months.
- No loyalty discount in the past 12 months.
- No more than one late payment in the past 3 months.

## Eligibility: device upgrade credit (hard)
- Current phone at least 18 months old.
- Phone paid off, or within 3 months of payoff.
- No late payment in the past 3 months.

## Eligibility: data upgrade (hard)
- 15 GB plan only.

## Contact rules (hard)
- At most one retention offer per account in any 90 days.
- Never contact an account marked do-not-contact.
- One offer per message.
- SMS messages are at most 320 characters and end with "Reply STOP to opt out."

## Message standards
- State the offer and its terms exactly, in plain language.
- Friendly and direct. No deadlines, countdowns, or pressure.
- Never mention churn, risk scores, predictions, or "we noticed you might leave."
- Never name a competitor.
- Don't reference details the customer didn't share with us, such as usage patterns, unless they're on the bill.

## Escalation
- If the customer's notes show an unresolved service problem, route the account to a care follow-up instead of sending an offer.
- If the notes show the customer is moving out of the coverage area, don't send an offer.
