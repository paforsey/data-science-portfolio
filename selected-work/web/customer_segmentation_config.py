"""Research-notebook page settings for customer_segmentation.ipynb.

Build from selected-work after re-exporting the notebook:

    jupyter nbconvert --to html customer_segmentation.ipynb
    python3 ../tools/notebook-restyle/restyle_notebook.py web/customer_segmentation_config.py \
        customer_segmentation.html web/customer_segmentation.html

The headline figures and key decisions are quoted from the notebook's outputs; update them
if the study is rerun on a different window of transactions or a different candidate grid.
"""

DESCRIPTION = (
    "Research notebook comparing seven customer segmentation methods on the same "
    "transaction history, judged on stability, out-of-time behavior, and deployability."
)
EYEBROW = "Clustering &middot; Customer Segmentation"
CRUMBS = [
    ("Portfolio", "/"),
    ("Selected Work", "/#selected-work"),
    ("Research Notebook", None),
]
BACK = None
KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# The Abstract cell's bullets become the summary notice under the header, so the page opens
# on the finding. Sections then start at Introduction.
NOTICE = {"source": "next-cell-list", "title": "Abstract", "icon": "info", "variant": "info"}

TIDY_MARKDOWN = True
WRAP_TEXT_OUTPUT = False  # outputs are aligned tables; wrapping them would break the columns
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = False  # headings carry no numbers; sections are numbered in order
OVERVIEW_LABEL = "Overview"  # unused while the Abstract is the notice, kept for safety

# Sidebar labels, keyed by the start of each h2 heading's text. Every h2 needs a match or
# the build stops. "Study Design" and "Study Limitations" are keyed in full, not on "Study".
SECTION_LABELS = [
    ("Introduction", "Introduction"),
    ("Data Readiness", "Data Readiness"),
    ("Study Design", "Study Design"),
    ("Customer Feature Construction", "Customer Features"),
    ("Shared Modeling Matrix", "Shared Matrix"),
    ("Candidate Segmentation Methods", "Candidate Methods"),
    ("Statistical Evidence", "Statistical Evidence"),
    ("Business Evidence", "Business Evidence"),
    ("Operational Fit", "Operational Fit"),
    ("Sensitivity Analysis", "Sensitivity"),
    ("Recommendation", "Recommendation"),
    ("Study Limitations", "Limitations"),
    ("Conclusions", "Conclusions"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("layers", "52", "configurations across 7 methods"),
    ("bars", "4,966", "customers in the shared matrix"),
    ("flask", "6", "months of out-of-time evidence"),
    ("check", "5", "RFM segments recommended"),
]

# (title, detail, section index) — index into the page's sections, 0 Introduction through
# 12 Conclusions.
DECISIONS = [
    ("Give every method the same feature matrix", "Shared Matrix · seven behaviors, one pipeline", 4),
    ("Score RFM on values, never on row order", "Candidate Methods · tied customers share a score", 5),
    ("Judge segments on later behavior, not fit", "Business Evidence · six months held back", 7),
    ("Require assignments to survive preprocessing", "Sensitivity · clustering ARI fell to 0.007", 9),
]

RELATED = [
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]
