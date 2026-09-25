"""Research-notebook page settings for consumer_subscription_prediction.ipynb.

Build from selected-work after re-exporting the notebook:

    jupyter nbconvert --to html consumer_subscription_prediction.ipynb
    python3 ../tools/notebook-restyle/restyle_notebook.py web/consumer_subscription_prediction_config.py \
        consumer_subscription_prediction.html web/consumer_subscription_prediction.html

The headline figures and key decisions are quoted from the notebook's outputs; the retraining
figures come from one timed run of the workflow, so update them whenever the notebook is rerun.
"""

DESCRIPTION = (
    "Research notebook comparing logistic regression, random forest and gradient boosting for "
    "subscription prediction, then retraining them in a supervised LangGraph workflow."
)
EYEBROW = "Classification &middot; Agentic Retraining"
CRUMBS = [
    ("Portfolio", "/"),
    ("Selected Work", "/#selected-work"),
    ("Research Notebook", None),
]
BACK = None
KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# The Abstract cell's bullets become the summary notice under the header.
NOTICE = {"source": "next-cell-list", "title": "Abstract", "icon": "info", "variant": "info"}

TIDY_MARKDOWN = True
WRAP_TEXT_OUTPUT = False  # outputs are aligned tables; wrapping them would break the columns
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = False  # headings carry no numbers; sections are numbered in order
OVERVIEW_LABEL = "Overview"  # unused while the Abstract is the notice, kept for safety

# Sidebar labels, keyed by the start of each h2 heading's text.
SECTION_LABELS = [
    ("Introduction", "Introduction"),
    ("Exploratory Data Analysis", "Exploratory Analysis"),
    ("Methods", "Classification Models"),
    ("Results", "Results"),
    ("Conclusions", "Model Selection"),
    ("Automating the Retraining Pipeline", "Automated Retraining"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("layers", "45,211", "bank marketing records"),
    ("bars", "0.8058", "test AUC, gradient boosting"),
    ("route", "3", "models retrained in parallel"),
    ("clock", "35%", "faster than the manual rerun"),
]

# (title, detail, section index) — index into the page's sections, 0 Introduction through
# 5 Automated Retraining.
DECISIONS = [
    ("Select gradient boosting on test AUC", "Model Selection · highest AUC, 0.8058", 4),
    ("Confirm with 100 Monte Carlo splits", "Results · small spread across splits", 3),
    ("Let code, not the LLM, apply the rules", "Automated Retraining · fixed checks on every fit", 5),
    ("Require approval before promoting a model", "Automated Retraining · the run pauses for review", 5),
]

RELATED = [
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]
