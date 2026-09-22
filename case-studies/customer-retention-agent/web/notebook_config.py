"""Research-notebook page settings for the six customer retention agent notebooks.

The study is split across 01_churn_survival.ipynb through 06_automation_monitoring.ipynb, merged
into one page (the data generator, 00, is not part of the merge, same as the rate-plan study).
Execute all six notebooks, then build from case-studies/customer-retention-agent:

    python3 ../../tools/notebook-restyle/merge_notebooks.py customer_retention_agent.merged.ipynb \
        01_churn_survival.ipynb 02_offer_uplift.ipynb 03_churn_reasons_nlp.ipynb \
        04_offer_optimizer.ipynb 05_retention_agent.ipynb 06_automation_monitoring.ipynb
    jupyter nbconvert --to html customer_retention_agent.merged.ipynb --output customer_retention_agent.export
    python3 ../../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
        customer_retention_agent.export.html web/customer_retention_agent.html

The merged notebook and the export are build artifacts. Sections are h1, one per notebook,
numbered 01-06 straight through; each ends with its own "Section 0N Summary" (h2, inside the
section, not a separate top-level closing section). The headline figures and decisions are
quoted from the study; update them if a re-run changes the results.
"""

DESCRIPTION = (
    "Research notebook for an AI retention agent: churn timing, causal uplift, topic modeling of "
    "care notes, a budget-limited optimizer, a LangGraph agent, and nightly automation with monitoring."
)
EYEBROW = "ML Research &middot; Customer Retention"
CRUMBS = [
    ("Portfolio", "/"),
    ("AI Customer Retention Agent", None),
    ("Research Notebook", None),
]
BACK = ("Back to portfolio", "/")
KERNEL = "Python 3 (ipykernel) · 3.12"

# The second cell's bullets are the disclosure.
NOTICE = {"source": "next-cell-list", "title": "Disclosure", "icon": "shield"}

SECTION_LEVEL = "h1"  # one h1 per notebook; each notebook's own steps are h2
TIDY_MARKDOWN = True
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep 01-06 matching the notebooks' own section numbers
OVERVIEW_LABEL = "Overview"

# Sidebar labels and navigator captions, keyed by the start of each h1 heading.
SECTION_LABELS = [
    ("Overview", "Overview"),
    ("01", "Churn Timing"),
    ("02", "Offer Effect"),
    ("03", "Churn Reasons"),
    ("04", "Offer Optimizer"),
    ("05", "Retention Agent"),
    ("06", "Automation & Monitoring"),
]

# (icon, value, label) quoted from the study.
STATS = [
    ("route", "7×", "more customers kept, uplift vs risk-first targeting"),
    ("layers", "5", "uplift learners compared against a withheld answer key"),
    ("chat", "97%", "agent drafts passing every check on the first try"),
    ("dollar", "$6,042", "net value from a $40,000 nightly budget"),
]

# (title, detail, section index) — index into the page's sections, in notebook order.
DECISIONS = [
    ("Rank by uplift, not churn risk", "§04 · Keeps 19.8 customers for $40K vs 2.7 for risk-first", 4),
    ("Gate offers on the randomized test, not the estimate", "§04 · A plan taken at face value forecast +$65K and lost $6.5K", 4),
    ("Use the risk-scaled logit, not a gradient-boosted uplift model", "§02 · 4% base rate; flexible learners fit noise", 2),
    ("Move routing and the opt-out line into code", "§05 · The model withheld offers from 13 of 16 price-sensitive customers it escalated", 5),
    ("Monitor drift against last month, not the training window", "§06 · The training window itself held a price increase and a promotion", 6),
]

RELATED = []
