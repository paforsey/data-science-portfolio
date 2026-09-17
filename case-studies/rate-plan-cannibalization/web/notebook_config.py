"""Research-notebook page settings for the two rate plan cannibalization notebooks.

The study is split across 01_choice_model_estimation.ipynb and 02_launch_forecast.ipynb, merged
into one page. Execute both notebooks, then build from case-studies/rate-plan-cannibalization:

    python3 ../../tools/notebook-restyle/merge_notebooks.py rate_plan_cannibalization.merged.ipynb \
        01_choice_model_estimation.ipynb 02_launch_forecast.ipynb
    jupyter nbconvert --to html rate_plan_cannibalization.merged.ipynb --output rate_plan_cannibalization.export
    python3 ../../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
        rate_plan_cannibalization.export.html web/rate_plan_cannibalization.html

The merged notebook and the export are build artifacts. Models are h1 across both notebooks,
numbered 01-08 straight through, so SECTION_LEVEL puts all eight in one navigator. The headline
figures describe the study design; replace them with results once the models are built.
"""

DESCRIPTION = (
    "Research notebook for a lower-priced wireless plan launch: revealed- and stated-preference "
    "choice models, a launch simulation scored against a withheld answer key, and a recommendation."
)
EYEBROW = "ML Research &middot; Rate Plan Design"
CRUMBS = [
    ("Portfolio", "/"),
    ("Rate Plan Cannibalization", None),
    ("Research Notebook", None),
]
BACK = ("Back to portfolio", "/")
KERNEL = "Python 3 (ipykernel) · 3.12"

# The second cell's bullets are the disclosure.
NOTICE = {"source": "next-cell-list", "title": "Disclosure", "icon": "shield"}

SECTION_LEVEL = "h1"  # models are h1; their steps are h2
TIDY_MARKDOWN = True
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep 01-08 matching the notebooks' own section numbers
OVERVIEW_LABEL = "Overview"
CLOSING_SECTION = {"starts_with": "The Complete Study Chain", "label": "Summary", "number": "09"}

# Sidebar labels and navigator captions, keyed by the start of each h1 heading.
SECTION_LABELS = [
    ("Overview", "Overview"),
    ("01", "Revealed Preference"),
    ("02", "Mixed Logit"),
    ("03", "Joint Nested Model"),
    ("04", "Taste Classes"),
    ("05", "Back-Test"),
    ("06", "Launch Simulation"),
    ("07", "Scoring"),
    ("08", "Recommendation"),
    ("Summary", "Summary"),
]

# (icon, value, label): study design facts until results replace them.
STATS = [
    ("layers", "8", "models across two notebooks"),
    ("bars", "108", "launch configurations scored"),
    ("flask", "4,000", "conjoint respondents"),
    ("shield", "1", "withheld answer key"),
]

# (title, detail, section index): filled in once the recommendation is made.
DECISIONS = []

RELATED = []
