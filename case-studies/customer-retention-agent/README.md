# AI Customer Retention Agent — Project Plan

Case Study 4. Status: Phase 6 done (retention agent); Phase 7 (automation and monitoring) next.

All data is synthetic. Plan names, prices, offers, and results are illustrative.

## 1. The story

**Business question:** A telecom carrier has a fixed monthly retention budget. Each night, which at-risk subscribers should it contact, with which offer, and what should the message say?

**Main finding to demonstrate:** The customers most likely to leave are often not the ones an offer can keep. The study compares a common baseline, "call the highest-risk customers," against targeting by uplift under the same budget. The result is reported as extra subscribers kept and net revenue per dollar spent.

**Guiding design rule:** The ML models and plain code produce every number. The LLM handles only language and judgment: reading notes, drafting messages, and checking policy. This design choice is itself something to explain on the case study page.

**What it demonstrates:**

| Area | Where |
|---|---|
| ML: survival analysis (churn timing) | `01_churn_survival` |
| ML: causal uplift modeling (offer effect) | `02_offer_uplift` |
| ML / NLP: embeddings and topic modeling (churn reasons) | `03_churn_reasons_nlp` |
| Optimization under a budget | `04_offer_optimizer` |
| AI: LLM drafting, LLM-as-judge, RAG | `05_retention_agent` |
| LangChain: tools, retrievers, structured output | `05_retention_agent` |
| LangGraph: agentic graph, fan-out, human-in-the-loop, checkpointing | `05_retention_agent` |
| Automation: nightly run, drift checks, retraining, regression tests | `06_automation_monitoring` |

## 2. Folder structure (follows the rate-plan study)

```
case-studies/customer-retention-agent/
  README.md
  data/00_generate_and_validate_data.ipynb
  data/generator_design.md
  data/synthetic/               (generated tables, offer policy, cached care notes)
  01_churn_survival.ipynb
  02_offer_uplift.ipynb
  03_churn_reasons_nlp.ipynb
  04_offer_optimizer.ipynb
  05_retention_agent.ipynb      (LangGraph)
  06_automation_monitoring.ipynb
  src/retention/                (reusable code the agent and nightly job import)
  outputs/                      (handoff tables between notebooks; not tracked)
  web/
```

**New for this study:** a small `src/` package. The agent and the nightly job need to import the models and tools, which notebooks alone can't provide.

As in the rate-plan study, modeling notebooks load data through `load()`, which refuses the answer-key tables. Those load only through `load_answer_key()`, and only in cells that score a finished model or policy.

## 3. Phases

### Phase 0: Setup and decisions
- Branch `customer-retention-agent` off `main`.
- Settle the open decisions in section 5.
- **Done when:** the folder skeleton exists and the decisions are recorded in this README. *Done 2026-09-21.*

### Phase 1: Synthetic data generator (`data/00`)
- **Design:** [data/generator_design.md](data/generator_design.md), reviewed before any code is written.
- **Accounts:** about 105k, with 24 months of monthly history. Fields include tenure, plan, monthly revenue per subscriber, data use, dropped calls, care contacts, contract end date, device age, bill shock, and exposure to competitor promotions.
- **Hidden churn process:** a known formula that sets each subscriber's churn rate over time. It includes a hidden reason for leaving (price, network, device, service, relocation).
- **Past retention campaign with random offer assignment:** needed to train the uplift model. Offers are none, discount, device upgrade, and data add-on. Effects vary by customer and include "sleeping dogs," customers the offer pushes toward leaving. A second campaign with non-random targeting gives a confounded dataset, which lets the study show why randomization matters.
- **Care notes:** gpt-4o-mini writes about 6,000 notes from each subscriber's hidden reason. The notes are cached in `data/synthetic/`, so the notebook reruns without an API key.
- **Offer policy document:** eligibility, discount limits, contact frequency, do-not-contact rules, and fairness rules. This is the source the agent retrieves from.
- **Done when:** saved tables, notes, and the policy document exist, plus a hidden answer key (true churn rates and true offer effects) used only for evaluation.

### Phase 2: Churn timing model (`01`) · done
- Time-varying Cox model (lifelines), then a gradient-boosted discrete-time hazard (LightGBM on account-months, rolled forward three months). scikit-survival was dropped: it would have forced numpy 2 into the shared base environment.
- **Output:** probability of leaving within 30, 60, and 90 days, saved to `outputs/churn_scores.parquet` for tonight's batch and `outputs/campaign_1_churn_scores.parquet` for Phase 3.
- **Metrics:** C-index, AUC, Brier score, and calibration by decile on a month-21 backtest, then against the answer key for tonight's batch.
- **Result:** the gradient-boosted model reaches a C-index of 0.61 (true probabilities: 0.75; tenure alone: 0.53) and is well calibrated on tonight's batch, but over-predicted by about 15% after the competitor surge in the backtest.
- Features live in `src/retention/features.py`, shared with every later phase and the nightly run.

### Phase 3: Offer effect model (`02`) · done
- **Methods:** five uplift learners, written in `src/retention/uplift.py` rather than taken from EconML or CausalML (both would have forced numpy 2 or a source build): T-, X-, and DR-learners on LightGBM, a DR-learner with a ridge effect model on 16 situation flags, and a risk-scaled logit (churn risk, flags, offer, and offer-by-flag terms). Plus an acceptance model per offer.
- **Metrics:** Qini curves on observed outcomes (scikit-uplift), then the true uplift held by each model's top fifth, from the answer key.
- **Side experiment:** campaign 2's naive discount estimate (0.39 points) against its true effect on the recipients (0.89 points).
- **Result:** with a 4% outcome, the gradient-boosted learners fit noise (1.2–1.3× in their top fifth); the risk-scaled logit reaches 1.7–1.9× on the test and 1.8–2.8× on tonight's batch, against a ceiling of about 4×, and is used downstream. Observed Qini curves can't separate the models; only the answer key can.
- **Output:** `outputs/uplift_scores.parquet`: uplift and acceptance probability per offer for tonight's batch.

### Phase 4: Churn reasons from notes (`03`) · done
- Local sentence embeddings (all-MiniLM-L6-v2), fine-grained BERTopic clusters (34 topics), and gpt-4o-mini naming each topic and mapping it to a retention category with structured output. Names are cached in `cache/topic_labels.json`, so reruns need no API key.
- **Validation:** 74% of notes get their own topic's category (over 90% for price, device, and moving), but an account's notes point to its real reason only 52% of the time; its rep codes, added up over every contact, 90%.
- **Targeting:** adjusting Phase 3's uplift by the account's reason lifts the top fifth's share of the true benefit, most with the codes (discount 2.78× to 3.14×). Phase 5 should use the code reason; the agent reads the notes.
- **Output:** `outputs/note_topics.parquet`, `outputs/account_reasons.parquet`, `outputs/note_embeddings.npy`.

### Phase 5: Offer optimizer (`04`) · done
- **Formula:** expected value = uplift × 24-month customer value − acceptance × offer cost, one offer per customer, greedy by value per budget dollar (checked against an exact integer program in PuLP; identical here).
- **Guardrails:** a plan built straight from the estimates forecast +$65K and really lost $6.5K (the winner's curse: the best of many noisy estimates are the overestimated ones). Three rules grounded in pre-launch evidence fix it: only offers whose test showed an effect (drops the data upgrade), the test's average acceptance for costs, and a budget on exposure rather than expected cost. Each night holds back 10% of the chosen customers to measure the real effect.
- **Result:** for $40,000, the uplift plan keeps 19.8 customers and earns $6,042; risk-first targeting keeps 2.7 and loses $9,486; the oracle keeps 44.7. Net value peaks at $20–40K of budget.
- **Code:** `src/retention/policy.py` (the policy's hard rules) and `src/retention/optimizer.py` (`build_candidates`, `select_greedy`, `select_exact`, `plan_tonight`, the agent's tool).
- **Output:** `outputs/tonight_plan.parquet`: 666 customers, 614 contacted and 52 held out.

### Phase 6: LangGraph retention agent (`05`) · done
**Graph flow:**
1. `load_batch`: tonight's scored subscribers.
2. `select_under_budget`: optimizer tool.
3. Fan out one branch per selected customer (LangGraph's Send):
   - `gather_context`: RAG over the customer's notes and the offer policy (Chroma, as in the RAG-Enhanced Coaching notebook).
   - `draft_outreach`: structured output with channel, offer, message, and rationale.
   - `compliance_check`: code checks the hard rules, then an LLM judge scores tone and accuracy. Failing drafts go back for revision, at most twice.
4. `aggregate`: collect all drafts.
5. `human_approval`: the graph pauses (`interrupt`) so a reviewer can approve, edit, or reject.
6. `dispatch`: write approved messages to a simulated outbox.
7. `run_report`.

**LangChain components:** tool definitions, retrievers, and structured-output schemas.

**Persistence:** a SQLite checkpointer, so an approval can resume after a pause.

**Metrics:**
- share of drafts passing compliance
- LLM judge scores
- a hand-rated sample
- cost and response time per run

**As built** (`src/retention/agent.py`, `05_retention_agent.ipynb`):
- Routing moved to code: an open support ticket goes to care follow-up (`route_customer` tool); the model only writes the message and the rationale. The first version let the model route from the notes and it withheld offers from 13 price-sensitive customers of 16 it escalated.
- The opt-out line is appended in code: first-draft pass rate went from 46% to 97%.
- Drafter and judge share one reading of the policy; the judge scores terms, tone, pressure, and privacy.
- Result on a 40-customer batch: 37 offers, all passing (36 on the first draft), 3 routed to care; every planted violation caught; the careless edit held back at dispatch. $0.27 per 1,000 customers, about 4 minutes for a full night.
- LLM responses are cached in `cache/llm_cache.sqlite` (thread-safe wrapper for the parallel branches), so reruns are free and reproducible; `cache/agent_run_log.json` keeps the live run's cost and time.

### Phase 7: Automation and monitoring (`06`)
- A nightly entry point (`python -m retention.run_nightly`) scheduled with launchd or cron.
- **Drift checks:** population stability index (PSI) on model inputs, and tracking of predicted versus actual churn. Drift above a threshold triggers retraining.
- **Regression tests:** a pytest suite for the agent that runs fixed cases through the graph.
- **Optional:** LangSmith tracing.

### Phase 8: Write-up and publishing
- This README, case study page in `web/`, and a built notebook page (same process as the rate-plan study).
- Later: a knowledge base document for the site chat, once the figures are final.

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Synthetic data too clean, so the models look unrealistically good | Add noise, missing values, confounded past targeting, and delayed outcomes |
| LLM cost of generating notes | Generate a subset, cache results, use a small model |
| Agent's numbers look invented | The agent can only get numbers from tools, and every rationale must cite a tool output |
| Fairness and ethics questions | No protected attributes, and fairness rules in the policy document |
| Scope creep (multi-agent, web demo) | Build a single graph first. The web demo is a stretch goal |
| Figures quoted as real | Label all results synthetic, as in the other studies |

## 5. Decisions (settled 2026-09-21)

| Decision | Choice | Why |
|---|---|---|
| LLM provider | OpenAI gpt-4o-mini | Matches the site chat, and it's cheap enough for thousands of notes and drafts |
| Care notes | LLM-written for a subset (about 6,000), cached | Realistic text for topic modeling at low cost; reruns need no API key |
| Scale | About 105k accounts over 24 months (first set at 50k) | Raised during generator tuning: at 50k the randomized test held too little signal to learn who responds. The generator still runs in about 10 seconds |
| Agent depth | A single graph first | Easier to build, test, and explain. A supervisor with sub-agents can come later |
| Web demo | Deferred | Notebooks and the case study page come first |

## 6. Environment and notebooks

| Notebook | What it does | Run time |
|---|---|---|
| `data/00_generate_and_validate_data.ipynb` | Generates and validates the synthetic data; reuses cached care notes | ~35 s |
| `01_churn_survival.ipynb` | Section 01: churn timing (Cox and gradient-boosted hazard), backtest, tonight's scores | ~25 s |
| `02_offer_uplift.ipynb` | Section 02: uplift learners on the randomized test, campaign 2 bias, acceptance, tonight's uplift | ~2.5 min |
| `03_churn_reasons_nlp.ipynb` | Section 03: note embeddings, BERTopic, LLM topic names (cached), validation, reasons and targeting | ~1.5 min |
| `04_offer_optimizer.ipynb` | Section 04: eligibility, customer value, guardrails, policy comparison, budget sweep, tonight's plan | ~10 s |
| `05_retention_agent.ipynb` | Section 05: LangGraph agent on a 40-customer batch, checks, stress test, human approval, cost | ~30 s cached; ~15 s of API calls live |

Run from this folder. `outputs/` is not tracked; rerunning the notebooks regenerates it.

Notebooks use the Python 3.12 "base" kernel. Already installed there: numpy, pandas, scikit-learn, LightGBM, XGBoost, sentence-transformers, LangChain, LangGraph, Chroma, the OpenAI SDK, and PuLP.

Still to install, each before the phase that needs it:

| Package | Phase |
|---|---|
| `lifelines` | 2 (churn timing) · installed 2026-09-21 |
| `langgraph-checkpoint-sqlite` | 6 (agent) · installed 2026-09-21 |
| `scikit-uplift` | 3 (offer effect, metrics only) · installed 2026-09-21; `econml` skipped (needs numpy 2) |
| `bertopic` (brings `umap-learn`, `hdbscan`) | 4 (churn reasons) · installed 2026-09-21. The base environment's TensorFlow is broken (protobuf 6), so `03` marks it unavailable before importing umap |
