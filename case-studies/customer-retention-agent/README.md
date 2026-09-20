# AI Customer Retention Agent — Project Plan

Case Study 4. Status: planning (no code yet).

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
  00_data_generator.ipynb
  01_churn_survival.ipynb
  02_offer_uplift.ipynb
  03_churn_reasons_nlp.ipynb
  04_offer_optimizer.ipynb
  05_retention_agent.ipynb      (LangGraph)
  06_automation_monitoring.ipynb
  src/retention/                (reusable code the agent and nightly job import)
  data/  outputs/  web/
```

**New for this study:** a small `src/` package. The agent and the nightly job need to import the models and tools, which notebooks alone can't provide.

## 3. Phases

### Phase 0: Setup and decisions
- Branch `customer-retention-agent` off `main`.
- Settle the open decisions in section 5.
- **Done when:** the folder skeleton exists and the decisions are recorded in this README.

### Phase 1: Synthetic data generator (`00`)
- **Subscribers:** about 100k, with 24 months of monthly history. Fields include tenure, plan, monthly revenue per subscriber, data use, dropped calls, care contacts, contract end date, device age, bill shock, and exposure to competitor promotions.
- **Hidden churn process:** a known formula that sets each subscriber's churn rate over time. It includes a hidden reason for leaving (price, network, device, service, relocation).
- **Past retention campaign with random offer assignment:** needed to train the uplift model. Offers are none, discount, device upgrade, and data add-on. Effects vary by customer and include "sleeping dogs," customers the offer pushes toward leaving. A second campaign with non-random targeting gives a confounded dataset, which lets the study show why randomization matters.
- **Care notes:** text written from each subscriber's hidden reason. Two options:
  - LLM-written for a subset of about 5–10k notes.
  - Templates plus LLM paraphrasing for the full set.
- **Offer policy document:** eligibility, discount limits, contact frequency, do-not-contact rules, and fairness rules. This is the source the agent retrieves from.
- **Done when:** saved tables, notes, and the policy document exist, plus a hidden answer key (true churn rates and true offer effects) used only for evaluation.

### Phase 2: Churn timing model (`01`)
- Baseline Cox model (lifelines), then a gradient-boosted survival model (scikit-survival, or XGBoost's survival objective).
- **Output:** probability of leaving within 30, 60, and 90 days.
- **Metrics:** concordance index (C-index), integrated Brier score, calibration by risk group, and comparison against the true churn rates.

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

## 5. Decisions needed before Phase 1

1. **LLM provider.** Use gpt-4o-mini to match the site chat, or show a second provider?
2. **Care notes.** LLM-written subset, or templates plus paraphrasing for everything?
3. **Scale.** Is 100k subscribers over 24 months right, or smaller so notebooks run faster?
4. **Agent depth.** A single graph (recommended first), with a supervisor and sub-agents as a later step?
5. **Web demo.** Notebooks and case study page only, or also a static walkthrough of a nightly run with the approval screen?
