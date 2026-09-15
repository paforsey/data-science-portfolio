"""Research-notebook page settings for Direct_Mail_Multivariate_Testing.ipynb.

Build from case-studies/multivariate-testing after re-exporting the notebook:

    jupyter nbconvert --to html Direct_Mail_Multivariate_Testing.ipynb \
        --output direct_mail_multivariate_testing
    python3 ../../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
        direct_mail_multivariate_testing.html web/direct_mail_multivariate_testing.html

The headline figures and key decisions are quoted from the notebook's outputs; update them
if a re-run changes the results.
"""

DESCRIPTION = (
    "Research notebook for the direct mail case study: an A/B test, a 2×2 factorial and a "
    "D-optimal multivariate landing-page test."
)
EYEBROW = "Experimental Design &middot; Direct Mail Testing"
CRUMBS = [
    ("Portfolio", "/"),
    ("Direct Mail Acquisition", "data-science-lifecycle.html"),
    ("Research Notebook", None),
]
BACK = ("Back to case study", "data-science-lifecycle.html")
KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# The second cell's bullets are the data disclosure.
NOTICE = {"source": "next-cell-list", "title": "Disclosure", "icon": "shield"}

# Sidebar labels, keyed by the start of each h2 heading's text.
SECTION_LABELS = [
    ("Abstract", "Abstract"),
    ("1.0", "Introduction"),
    ("2.0", "Stage 1 · Mailer A/B Test"),
    ("3.0", "Stage 2 · Creative × Timing"),
    ("4.0", "Stage 3 · Landing-Page Test"),
    ("5.0", "Summary & Conclusions"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("mail", "3", "designs fielded"),
    ("dollar", "$195K", "mailer savings, Creative A"),
    ("bars", "34% vs 60%", "completion, weakest vs strongest page"),
    ("flask", "24 runs", "instead of 96"),
]

# (title, detail, section index) — index into the page's sections, in notebook order.
DECISIONS = [
    ("Adopt the lower-cost mailer", "Stage 1 · p = 0.45", 2),
    ("Mail mid-month", "Stage 2 · p < 0.001", 3),
    ("Use a professional design with trust badges", "Stage 3 · 60% completion", 4),
    ("Choose hero imagery on brand grounds", "Stage 3 · effect too small to act on", 4),
]

RELATED = [
    ("Case study", "case-study.html"),
    ("Executive presentation", "executive-presentation.html"),
    ("Analytical plan", "analytical-plan.html"),
]
