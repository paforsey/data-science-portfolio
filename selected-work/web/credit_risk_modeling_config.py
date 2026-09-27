"""Research-notebook page settings for credit_risk_modeling.ipynb.

Build from selected-work after re-exporting the notebook:

    jupyter nbconvert --to html credit_risk_modeling.ipynb
    python3 ../tools/notebook-restyle/restyle_notebook.py web/credit_risk_modeling_config.py \
        credit_risk_modeling.html web/credit_risk_modeling.html

The headline figures and key decisions are quoted from the notebook's outputs; update them if
the sample or the split changes.
"""

DESCRIPTION = (
    "Research notebook benchmarking random forest, SVM and XGBoost against a logistic "
    "baseline for loan default, on discrimination and calibration."
)
EYEBROW = "Model Comparison &middot; Credit Risk"
CRUMBS = [
    ("Selected Work", "/#selected-work"),
    ("Credit Risk", None),
    ("Research Notebook", None),
]
BACK = None
KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# The Abstract cell's three labelled lists become the summary notice under the header.
# The cell after the title (a heading and one paragraph) shows as its own box above the Abstract.
SUMMARY = {"icon": "bars", "variant": "info"}

NOTICE = {"source": "next-cell-list", "title": "Abstract", "icon": "info", "variant": "info"}

TIDY_MARKDOWN = True
WRAP_TEXT_OUTPUT = False  # outputs are aligned tables; wrapping them would break the columns
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep 01-10 matching the notebook's own section numbers
OVERVIEW_LABEL = "Overview"  # unused while the Abstract is the notice, kept for safety

# Sidebar labels, keyed by the start of each h2 heading's text. "1.0" does not match "10.0".
SECTION_LABELS = [
    ("1.0", "Introduction"),
    ("2.0", "Data & Preprocessing"),
    ("3.0", "Exploratory Analysis"),
    ("4.0", "Model Specification"),
    ("5.0", "Baseline Model"),
    ("6.0", "Baseline Performance"),
    ("7.0", "Comparative Analysis"),
    ("8.0", "Limitations"),
    ("9.0", "Lessons Learned"),
    ("10.0", "Conclusions"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("bars", "150,000", "LendingClub loans, split by date"),
    ("layers", "3", "complex models against one baseline"),
    ("flask", "+0.0028", "largest AUC gain over the baseline"),
    ("check", "0.1667", "baseline Brier after recalibration"),
]

# (title, detail, section index) — index into the page's sections, 0 Introduction through
# 9 Conclusions.
DECISIONS = [
    ("Split training and test loans by date", "Data · before 2016, then 2016 onward", 1),
    ("Test every model against the baseline", "Comparative Analysis · paired DeLong, gains under 0.003", 6),
    ("Recalibrate before judging calibration", "Comparative Analysis · Brier 0.2309 to 0.1667", 6),
    ("Keep the recalibrated logistic baseline", "Conclusions · within 0.003 AUC, still interpretable", 9),
]

RELATED = [
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]
