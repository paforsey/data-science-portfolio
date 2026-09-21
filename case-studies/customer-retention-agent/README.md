# AI Customer Retention Agent — Project Plan

Case Study 4. Status: Phase 2 done (churn timing); Phase 3 (offer effect) next.

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

### Phase 3: Offer effect model (`02`)
- **Methods:** T-learner and X-learner (LightGBM, via EconML or CausalML), one effect estimate per offer type.
- **Metrics:** Qini curve, area under the uplift curve, and error against the true effects.
- **Side experiment:** the same model trained on the confounded campaign, to show the bias.

### Phase 4: Churn reasons from notes (`03`)
- Sentence embeddings plus BERTopic, then an LLM names each topic.
- **Validation:** agreement between the topics and the hidden reasons (adjusted Rand index).
- **Output:** each customer's top reason, which the agent uses when writing messages.

### Phase 5: Offer optimizer (`04`)
- **Formula:** expected value = P(churn within 90 days) × offer effect × customer lifetime value − offer cost. Solved as a budget-limited selection problem (knapsack with a greedy or integer-programming solver).
- **Comparisons:** random targeting, highest-risk-first, and uplift-based targeting, evaluated against the hidden answer key.
- **Deliverable:** this comparison is the study's main chart.
- Packaged as a plain function so the agent can call it as a tool.

### Phase 6: LangGraph retention agent (`05`)
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

Run from this folder. `outputs/` is not tracked; rerunning the notebooks regenerates it.

Notebooks use the Python 3.12 "base" kernel. Already installed there: numpy, pandas, scikit-learn, LightGBM, XGBoost, sentence-transformers, LangChain, LangGraph, Chroma, the OpenAI SDK, and PuLP.

Still to install, each before the phase that needs it:

| Package | Phase |
|---|---|
| `lifelines` | 2 (churn timing) · installed 2026-09-21 |
| `econml` | 3 (offer effect) |
| `bertopic` (brings `umap-learn`, `hdbscan`) | 4 (churn reasons) |
