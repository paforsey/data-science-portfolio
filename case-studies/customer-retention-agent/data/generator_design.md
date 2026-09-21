# Data Generator Design

Design for `data/00_generate_and_validate_data.ipynb`, to be agreed before any code is written.
It follows the rate-plan study's generator: Part 1 generates, Part 2 validates, and the answer key is
written to separate files that the modeling notebooks cannot load by accident.

All data is synthetic. Plan names, prices, offers, and results are illustrative.

## 1. What the generator has to make possible

Each later phase needs something specific from the data:

| Phase | Needs from the data |
|---|---|
| 2 · Churn timing | Monthly history with real churn timing: an early-tenure risk, a jump after the device is paid off, and triggers the model can see (bill shock, dropped calls, care contacts) |
| 3 · Offer effect | A randomized past campaign with effects that vary by customer, including customers an offer pushes away, plus a non-random campaign whose naive estimate is biased |
| 4 · Churn reasons | Care notes whose topics reflect a hidden reason for leaving, recoverable but not perfectly |
| 5 · Optimizer | True churn probabilities under every offer for tonight's customers, so every targeting policy can be scored exactly |
| 6 · Agent | Customer records, notes, eligibility fields, and an offer policy document to retrieve from |
| 7 · Monitoring | Months after the scoring date, including a planned shift the drift checks should catch |

**The finding the data must support:** the customers most likely to leave are often not the ones an
offer can keep. The generator builds this in on purpose (section 5) and Part 2 checks that it is there.

## 2. Population and timeline

- **Unit:** the account (a household on one bill, 1–5 lines), as in the rate-plan study.
- **Size:** 42,000 active accounts at month 1, plus about 450 new accounts a month, so about 53,000
  accounts ever appear and about 40,000 are active at month 24.
- **Regions:** 8, each with its own network quality and competitor promotion intensity.

| Months | What happens |
|---|---|
| 1–24 | Observed history: usage, bills, care contacts, churn |
| 13 | **Campaign 1:** randomized retention test (section 6) |
| 16–18 | A competitor promotion surge in two regions |
| 19 | **Campaign 2:** the usual targeted campaign, not randomized (section 6) |
| End of 24 | **Scoring date:** tonight's batch for the optimizer and agent |
| 25–30 | Held-out future, used only by Phase 7 monitoring; month 27 adds a new competitor promotion as the drift to detect |

## 3. Tables

### Model-facing (`load()`)

| Table | One row per | Main fields |
|---|---|---|
| `accounts` | account | region, plan (Unlimited Plus, Unlimited, 15 GB), lines, join month, autopay, device installment end month, do-not-contact flag, last retention offer month |
| `monthly_panel` | account × active month | bill, change vs. prior 3-month average, data used, days throttled, dropped-call rate, care contacts, unresolved ticket, late payment, device age, months to device payoff, competitor promotion index, churned this month |
| `care_contacts` | contact | account, month, channel, reason code (entered by the rep, so noisy), note id if a note exists |
| `care_notes` | note | note id, account, month, note text |
| `campaigns` | account × campaign | campaign, month, arm (control, discount, device, data), accepted, offer cost |
| `scoring_snapshot` | account active at month 24 | the features as of the scoring date, with no outcomes |
| `offer_policy.md` | — | the policy document the agent retrieves from (section 8) |
| `generator_parameters` | parameter | every setting in this document, for reproducibility |

### Answer key (`load_answer_key()` only)

| Table | Contents |
|---|---|
| `truth_accounts` | hidden reason for leaving, hidden frailty, sleeping-dog flag |
| `truth_potential_outcomes` | for each account in the snapshot: true probability of leaving within 90 days under each of the four arms, and true 24-month customer value |
| `future_panel` | months 25–30 under no offers, released month by month in Phase 7 |

## 4. How churn works

Each month, each active account has a probability of leaving (a discrete-time hazard):

```
logit(hazard) = baseline
              + tenure curve            (higher in the first year, flattening after)
              + device payoff jump      (the first months after the device is paid off)
              + reason-specific trigger (below)
              + hidden frailty          (per-account, unobserved, SD 0.5)
```

**Target:** 1.1–1.6% of accounts leave each month, about 15% a year.

**Hidden reason for leaving.** Every account gets one, which decides what pushes it out the door:

| Reason | Share | What raises its risk |
|---|---|---|
| Price | 35% | Bill increases and competitor promotions |
| Network | 20% | Dropped calls (concentrated in weak-network regions) |
| Device | 20% | Old device, especially once it's paid off |
| Service | 15% | Repeated care contacts and unresolved tickets |
| Relocation | 10% | A random move; nothing the carrier does changes it |

Shares shift with observables (for example, network-reason accounts cluster in weak-network regions),
so the reason is partly predictable from the panel, and partly only from the notes.

## 5. How offers work

| Offer | Terms | Cost to the carrier if accepted |
|---|---|---|
| Discount | $10 off per month for 6 months | $60 |
| Device | $200 upgrade credit on a new 24-month installment | $200 |
| Data | Free data upgrade for 6 months (15 GB plan only) | $30 |

An accepted offer multiplies the account's monthly churn probability for the next 6 months, fading
over that time. The effect depends on the hidden reason:

| Reason | Discount | Device | Data |
|---|---|---|---|
| Price | 0.45 | 0.75 | 0.80 |
| Network | 0.90 | 0.95 | 0.85 |
| Device | 0.85 | 0.40 | 0.95 |
| Service | 0.70 | 0.85 | 0.85 |
| Relocation | 1.00 | 1.00 | 1.00 |

(Below 1 lowers risk: 0.45 means the offer cuts the churn probability by more than half.)
The data offer works better for heavy users who hit their cap. Acceptance is more likely when an
offer fits the reason.

**Sleeping dogs.** About 12% of accounts are long-tenure, low-risk, paid-off, and rarely call care.
For them, any retention contact raises churn probability by 1.5× for 3 months, because it prompts
them to shop around. Unless the offer fits them well, their net effect is harmful.

**Built-in finding.** Network- and relocation-reason accounts have high risk but offers barely move
them, and sleeping dogs have low risk and negative uplift. Ranking by risk therefore picks many
customers an offer can't save.

## 6. Past campaigns

**Campaign 1, month 13, randomized.** 16,000 randomly chosen active accounts: 40% control, 20% for
each offer. This is the training data for the uplift model in Phase 3.

**Campaign 2, month 19, targeted.** About 5,000 accounts chosen the way a business usually picks
them: a recent care contact, a bill increase, or device payoff within 2 months. The offer follows a
rep's rule of thumb (price complaint → discount, old device → device). The targeting correlates with
risk, so a naive comparison of offered versus not-offered customers gives a biased effect. Phase 3
uses this to show why the randomized test matters.

## 7. Care contacts and notes

- **Contacts:** generated in the monthly panel, more often for service- and network-reason accounts
  and after bill increases. The rep's reason code matches the hidden reason only about 55% of the
  time.
- **Notes:** gpt-4o-mini writes about 6,000 notes, sampled from recent contacts (mostly months 13–24)
  and weighted toward accounts still active at month 24, so the agent has notes to retrieve.
  - Each prompt gives the hidden reason plus a few account facts (plan, lines, tenure band, device
    age, recent bill change, dropped-call level) and a style: terse rep shorthand or full sentences.
  - 15% are routine contacts unrelated to the reason (address change, payment arrangement), and 20%
    also mention a secondary issue, so topics overlap the way real notes do.
  - No names, phone numbers, or other personal details. Notes are 2–4 sentences.
- **Cache:** notes are saved to `data/synthetic/care_notes.parquet` with the prompt settings used, and
  the notebook reuses the cache. Regenerating needs an OpenAI key and costs roughly a dollar or two.

## 8. Offer policy document

`offer_policy.md` is written for retrieval: short sections, one topic each. Rules marked **(hard)**
are also checked in code by the agent's compliance step.

- **Offers and exact terms:** the three offers above, worded as customers would see them.
- **Eligibility (hard):**
  - Discount: tenure ≥ 6 months, no discount in the past 12 months, not more than 30 days past due.
  - Device: device ≥ 18 months old, installment paid off or within 3 months of payoff, good standing.
  - Data: 15 GB plan only.
- **Contact rules (hard):** at most one retention offer per account per 90 days; never contact
  do-not-contact accounts (about 3%); SMS up to 320 characters; include "Reply STOP to opt out."
- **Message standards:** state the offer terms exactly; no deadlines or pressure; never mention
  predicted churn or "we noticed you might leave"; no competitor names; plain, friendly tone.
- **Escalation:** complaints about unresolved service issues go to a care follow-up, not an offer.

The nightly budget is set in Phase 5, not in the generator.

## 9. Validation checks (Part 2)

Part 2 confirms each structure is present and not trivially easy to find. Any failure means tuning
the parameters above before moving on.

| # | Check | Target |
|---|---|---|
| 1 | Monthly churn rate | 1.1–1.6%, higher in year one, a visible jump after device payoff |
| 2 | Campaign 1 balance | Arms balanced on observables (standardized differences < 0.05) |
| 3 | Average offer effects | Each offer lowers 90-day churn by roughly 10–25% relative to control; discount and device detectable in campaign 1 |
| 4 | Effect heterogeneity | Top-decile true uplift at least 4× the average; about 10% of accounts harmed by contact |
| 5 | **The built-in finding** | Rank correlation between true risk and true best-offer uplift ≤ 0.3; under the same budget, an oracle uplift policy saves at least 30% more customers than an oracle risk policy |
| 6 | Campaign 2 confounding | The naive discount estimate is off by at least half of the true effect |
| 7 | Notes carry signal | A simple text classifier recovers the hidden reason with 60–80% accuracy |
| 8 | No leakage | Model-facing tables contain no answer-key fields, and `load()` refuses answer-key tables |

## 10. Run time

Under a minute for everything except the notes. First-time note generation takes about 10–15
minutes with batched API calls; after that the cache makes it instant.
