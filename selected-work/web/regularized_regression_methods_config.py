"""Research-notebook page settings for regularized_regression_methods.ipynb.

Build from selected-work after re-exporting the notebook:

    jupyter nbconvert --to html regularized_regression_methods.ipynb
    python3 ../tools/notebook-restyle/restyle_notebook.py web/regularized_regression_methods_config.py \
        regularized_regression_methods.html web/regularized_regression_methods.html

The headline figures and key decisions are quoted from the notebook's outputs; update them if
the models are refit.
"""

DESCRIPTION = (
    "Research notebook deriving ridge regression in closed form, then comparing ridge, LASSO, "
    "adaptive LASSO, elastic net and group LASSO on three problems."
)
EYEBROW = "Regression &middot; Regularization Methods"
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

# Sidebar labels, keyed by the start of each h2 heading's text. The two Ridge headings are
# keyed in full enough to tell them apart.
SECTION_LABELS = [
    ("Introduction", "Introduction"),
    ("Ridge Regression: Closed-Form", "Closed-Form Ridge"),
    ("Ridge, LASSO, Adaptive LASSO", "Temperature Forecasting"),
    ("Group LASSO", "Group LASSO"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("layers", "4", "penalties compared on one forecast"),
    ("bars", "2.0590", "lowest test MSE, ridge"),
    ("check", "15 of 21", "predictors kept by adaptive LASSO"),
    ("flask", "0.7500", "colon cancer test accuracy"),
]

# (title, detail, section index) — index into the page's sections, 0 Introduction through
# 3 Group LASSO.
DECISIONS = [
    ("Derive ridge before fitting it", "Closed-Form Ridge · the estimator from first principles", 1),
    ("Tune each penalty by cross-validation", "Temperature Forecasting · λ chosen on training data", 2),
    ("Prefer ridge for the temperature forecast", "Temperature Forecasting · lowest MSE, all 21 kept", 2),
    ("Select genes as groups, not splines", "Group LASSO · 3 of 20 gene groups dropped", 3),
]

RELATED = [
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]
