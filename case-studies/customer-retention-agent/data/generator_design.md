# Data Generator Design

Design for `data/00_generate_and_validate_data.ipynb`. It follows the rate-plan study's generator:
Part 1 generates, Part 2 validates, and the answer key is written to separate files that the
modeling notebooks cannot load by accident. Section 11 records what changed from the first draft
during tuning, and why.

All data is synthetic. Plan names, prices, offers, and results are illustrative.

## 1. What the generator has to make possible

Each later phase needs something specific from the data:

| Phase | Needs from the data |
|---|---|
| 2 · Churn timing | Monthly history with real churn timing: an early-tenure risk, a jump after the device is paid off, and triggers the model can see (bill shock, dropped calls, care contacts) |
| 3 · Offer effect | A randomized past campaign with effects that vary by customer in ways the observables reveal, including customers an offer pushes away, plus a non-random campaign whose naive estimate is biased |
| 4 · Churn reasons | Care notes whose topics reflect a hidden reason for leaving, recoverable but not perfectly |
| 5 · Optimizer | True churn probabilities under every offer for tonight's customers, so every targeting policy can be scored exactly |
| 6 · Agent | Customer records, notes, eligibility fields, and an offer policy document to retrieve from |
| 7 · Monitoring | Months after the scoring date, including a planned shift the drift checks should catch |

**The finding the data must support:** the customers most likely to leave are often not the ones an
offer can keep. The generator builds this in on purpose (section 5) and Part 2 checks that it is there.

## 2. Population and timeline

- **Unit:** the account (a household on one bill, 1–5 lines), as in the rate-plan study.
- **Size:** 84,000 active accounts at month 1, plus 900 new accounts a month, so about 105,000
  accounts ever appear and about 75,000 are active at month 24.
- **Regions:** 8, each with its own network quality and competitor promotion intensity.

| Months | What happens |
|---|---|
| 1–24 | Observed history: usage, bills, care contacts, churn |
| 12 | A $5-per-line price increase on the unlimited plans |
| 13 | **Campaign 1:** randomized retention test (section 6) |
| 16–18 | A competitor promotion surge in two regions |
| 19 | **Campaign 2:** the usual targeted campaign, not randomized (section 6) |
| End of 24 | **Scoring date:** tonight's batch for the optimizer and agent |
| 25–30 | Held-out future, used only by Phase 7 monitoring; from month 27 a competitor promotion runs everywhere, the drift to detect |

## 3. Tables

### Model-facing (`load()`)

| Table | One row per | Main fields |
|---|---|---|
| `accounts` | account | region, plan (Unlimited Plus, Unlimited, 15 GB), lines, join month, autopay, do-not-contact flag |
| `monthly_panel` | account × active month | bill, change vs. prior 3-month average, data used, days throttled, dropped-call rate, care contacts, unresolved ticket, late payment, device age, months to device payoff, competitor promotion index, churned this month |
| `care_contacts` | contact | account, month, channel, reason code (entered by the rep, so noisy), note id if a note exists |
| `care_notes` | note | note id, account, month, note text |
| `campaigns` | account × campaign | campaign, month, arm (control, discount, device, data), accepted, offer cost |
| `scoring_snapshot` | account active at the end of month 24 | month-24 observables, 3-month summaries, tenure, and the most recent retention offer (month, type, accepted) |
| `offer_policy.md` | — | the policy document the agent retrieves from (section 8) |

### Answer key (`load_answer_key()` only)

| Table | Contents |
|---|---|
| `truth_accounts` | hidden reason for leaving, hidden frailty, sleeping-dog flag, month churned |
| `truth_potential_outcomes` | for each account in the snapshot: true probability of leaving within 90 days under each of the four arms, true acceptance rate of each offer, and true 24-month customer value |
| `truth_campaign_outcomes` | the same potential outcomes for every account in both past campaigns, at the time of the offer; Phase 3 scores the uplift model against these |
| `truth_notes` | each note's account reason and prompt settings: the note's own topic, secondary issue, routine topic, whether the concern was only hinted, style |

`care_notes_cache.parquet` holds each note with its full prompt, which reveals the hidden reason. It exists only so the notebook can rerun without API calls, and no loader reads it.
| `future_panel` | months 25–30 under no new offers, released month by month in Phase 7 |
| `generator_parameters` | every setting in the notebook, including the true offer effects |

## 4. How churn works

Each month, each active account has a probability of leaving (a discrete-time hazard):

```
logit(hazard) = baseline
              + tenure curve            (higher in the first year, flattening after)
              + device payoff jump      (the first months after the device is paid off)
              + reason-specific trigger (below)
              + hidden frailty          (per-account, unobserved, SD 0.6)
```

**Result:** about 1.55% of accounts leave each month, about 17% a year.

**Hidden reason for leaving.** Every account gets one, which decides what pushes it out the door:

| Reason | Share | What raises its risk |
|---|---|---|
| Price | 37% | Bill increases and competitor promotions |
| Network | 21% | Dropped calls (concentrated in weak-network regions) |
| Device | 19% | Old device, especially just after it's paid off |
| Service | 14% | Repeated care contacts and unresolved tickets |
| Relocation | 9% | A move; nothing the carrier does changes it, and nothing it sees predicts it |

Shares shift with observables (for example, network-reason accounts cluster in weak-network regions),
so the reason is partly predictable from the panel, partly from the rep's reason code (right 70% of
the time), and partly only from the notes.

## 5. How offers work

| Offer | Terms | Cost to the carrier if accepted |
|---|---|---|
| Discount | $10 off per month for 6 months | $60 |
| Device | $200 upgrade credit on a new 24-month installment | $200 |
| Data | Free data upgrade for 6 months (15 GB plan only) | $30 |

An accepted offer multiplies the account's monthly churn probability for the next 6 months, fading to
half that effect by month 6. The effect depends on the hidden reason **and on an observable
situation**:

| Reason | Discount | Device | Data |
|---|---|---|---|
| Price | 0.10 | 0.60 | 0.70 |
| Network | 0.95 | 0.95 | 0.85 |
| Device | 0.95 | 0.05 | 0.95 |
| Service | 0.60 | 0.80 | 0.85 |
| Relocation | 1.00 | 1.00 | 1.00 |

(Below 1 lowers risk: 0.10 means an accepted offer cuts the churn probability by 90%.)

- **Situations.** Each offer works fully only in its situation: the discount for price-reason customers
  under price pressure (a bill increase over 5% or a competitor promotion index over 0.4 in the past
  3 months), the device credit for device- and price-reason customers whose phone is paid off or within
  3 months of it, and the data upgrade for 15 GB customers who hit their cap. Outside its situation,
  only a tenth of the effect remains.
- **Deliberately strong.** The matched effects are set large enough that a 40,000-account test carries
  enough signal to learn who responds (section 11). The write-up says so.
- **Acceptance** is 90% for a well-matched offer and 10–50% otherwise, somewhat lower for customers
  who have already made up their minds (high hidden frailty).
- **Sleeping dogs.** About 11% of accounts are long-tenure, low-risk, paid-off, and rarely call care.
  They accept half as often, and any retention contact raises their churn probability 1.15× for 3
  months, because it prompts them to shop around. For most of them the net effect is harmful.

**Built-in finding.** Relocation and network accounts have high risk but offers barely move them,
sleeping dogs have low risk and negative uplift, and most high-risk customers aren't in an offer's
situation. Ranking by risk therefore picks many customers an offer can't save.

## 6. Past campaigns

**Campaign 1, month 13, randomized.** 40,000 randomly chosen active accounts (excluding do-not-contact):
40% control, 20% for each offer. It follows the month-12 price increase, so price pressure is visible
in the bills. This is the training data for the uplift model in Phase 3.

**Campaign 2, month 19, targeted.** The top 10,000 of an at-risk list that scores recent care contacts,
a bill increase, a phone paid off in the past 3 months, and late payments. The offer follows a rep's
rule of thumb (billing complaint → discount, old device → device, capped heavy user → data). The
targeting correlates with risk, so a naive comparison of offered versus not-offered customers gives a
biased effect. Phase 3 uses this to show why the randomized test matters.

## 7. Care contacts and notes

- **Contacts:** generated in the monthly panel, more often for service- and network-reason accounts
  and after bill increases.
- **Notes:** gpt-4o-mini writes 6,000 notes, sampled from contacts (mostly months 13–24) and weighted
  toward accounts still active at month 24, so the agent has notes to retrieve. Notes are third person,
  at most 3 sentences and about 60 words, in clipped rep shorthand or short plain sentences.
  - Each prompt describes the customer's situation (never the category name) plus a few account facts
    (plan, lines, tenure band, device age, recent bill change, dropped-call level) and a style: terse
    rep shorthand or full sentences.
  - 15% are routine contacts unrelated to the reason (address change, payment arrangement, adding a
    line, autopay). Of the rest, 30% are about some other issue than the account's hidden reason,
    because customers don't only call about what would make them leave; 20% also mention a secondary
    issue; and in half the customer only hints at the concern, so topics overlap the way real notes do.
  - Result: a simple classifier reads a note's own topic 95% of the time but the account's hidden
    reason only 67% of the time.
  - No names, phone numbers, account numbers, or dates. Notes are 2–4 sentences.
- **Cache:** notes are saved to `data/synthetic/care_notes_cache.parquet` with their prompts, and the
  notebook reuses the cache whenever the prompts match. Generating them needs an OpenAI key and costs
  well under a dollar.

## 8. Offer policy document

`offer_policy.md` is written for retrieval: short sections, one topic each. Rules marked **(hard)**
are also checked in code by the agent's compliance step.

- **Offers and exact terms:** the three offers above, worded as customers would see them.
- **Eligibility (hard):**
  - Discount: tenure ≥ 6 months, no loyalty discount in the past 12 months, at most one late payment in
    the past 3 months.
  - Device: phone ≥ 18 months old, paid off or within 3 months of payoff, no late payment in the past
    3 months.
  - Data: 15 GB plan only.
- **Contact rules (hard):** at most one retention offer per account per 90 days; never contact
  do-not-contact accounts (about 3%); one offer per message; SMS up to 320 characters, ending with
  "Reply STOP to opt out."
- **Message standards:** state the offer terms exactly; no deadlines or pressure; never mention
  churn, risk scores, or predictions; no competitor names; nothing the customer didn't share.
- **Escalation (hard):** an account with an unresolved support ticket goes to a care follow-up, not an
  offer; a customer whose contacts show a move gets no offer; a bill or price complaint is not a reason
  to withhold an offer. (Tightened in Phase 6: the first wording, "notes show an unresolved service
  problem", led the agent to withhold offers from price-sensitive customers.)

The nightly budget is set in Phase 5, not in the generator.

## 9. Validation checks (Part 2)

Part 2 confirms each structure is present and not trivially easy to find, on the exported files.

| # | Check | Target |
|---|---|---|
| 1 | Churn rate and timing | 1.1–1.6% a month; first year clearly above 3+ years; higher after device payoff |
| 2 | Campaign 1 balance | Arms balanced on observables (standardized differences < 0.1) |
| 3 | Offer effects | True average reduction: discount 10–25%, device 8–20%, data 1–10%. Learnable: a segment estimate's top fifth captures ≥ 1.5× the average true uplift for discount and device, averaged over 5 splits |
| 4 | Effect heterogeneity | Top-decile best-offer uplift ≥ 3× the average; 5–15% of accounts harmed by the discount |
| 5 | **The built-in finding** | Risk and best-offer uplift only moderately related (rank correlation ≤ 0.5); under the same $40,000 budget, an ideal uplift-first policy saves at least 30% more customers than an ideal risk-first policy |
| 6 | Campaign 2 confounding | The naive discount estimate misses the true effect on its recipients by at least half |
| 7 | Notes carry signal | A simple text classifier recovers the hidden reason with 60–80% accuracy |
| 8 | No leakage | Model-facing tables contain no answer-key fields, and `load()` refuses answer-key tables |

## 10. Run time and size

The whole notebook runs in about 35 seconds once the notes are cached. First-time note generation
takes about 20 minutes at 8 parallel requests, under the API's rate limit; progress is saved every 500
notes, and later runs regenerate only notes whose prompts changed. The synthetic tables total about
45 MB.

## 11. Changes during tuning

The first draft's parameters failed several checks. What changed, and why:

| Change | Why |
|---|---|
| Population 53,000 → 105,000 accounts; campaign 1 16,000 → 40,000; campaign 2 5,000 → 10,000 | At about 5% churn over 90 days, the smaller test held too little information to learn who responds |
| Offer effects depend on an observable situation, and matched effects are much stronger | A simple uplift learner on the first draft captured only 1.1–1.3× the average uplift in its top fifth (an oracle got 4×). Stronger, visible effects are what make Phase 3 learnable |
| Price increase moved from month 10 to month 12 | Campaign 1 now follows it, so price pressure is visible when offers are made |
| Acceptance falls with hidden frailty | Customers who have already decided to leave are harder to keep; this also keeps risk and uplift from moving in lockstep |
| Sleeping-dog penalty 1.5× → 1.15×; share 12% → 11% | At 1.5× the device and data offers did net harm on average |
| Campaign 2's list flags phones paid off in the past 3 months, not those about to be | Churn jumps after payoff, not before, so the original list selected low-risk accounts and showed little bias |
| Rep reason code right 70% of the time, not 55% | Gives the uplift model a usable, still noisy, observable hint of the reason |
| Balance target < 0.05 → < 0.1 | With 8,000 accounts an arm, chance alone produces differences near 0.05; 0.1 is the usual rule of thumb |
| Detectability of the average effect → learnability of who responds | Even with the larger test, the average effect's z-score depends on luck; what Phase 3 needs is to rank customers |
| Rank correlation target ≤ 0.3 → ≤ 0.5; top-decile target 4× → 3× | The first targets were guesses. The policy comparison in check 5 is the real test of the finding, and it passes by a wide margin |
| `generator_parameters` moved to the answer key; `truth_campaign_outcomes` and `truth_notes` added | The parameters contain the true offer effects; the campaign truth lets Phase 3 score the uplift model per customer |
| Notes: third person, shorter, half only hinted, 30% about another issue | The first 6,000 notes echoed the prompt wording; a classifier recovered the hidden reason 95% of the time, which would make Phase 4 trivial |
| Note generation throttled to 8 parallel requests, with saved progress | The first run hit the 500-requests-a-minute limit and lost its progress |
