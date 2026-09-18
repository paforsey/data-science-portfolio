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
figures and decisions are quoted from the study; update them if a re-run changes the results.
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

# (icon, value, label) quoted from the study.
STATS = [
    ("bars", "+20 pts", "cannibalization overstated by a flat logit"),
    ("layers", "3", "taste segments behind plan choice"),
    ("dollar", "$52.50", "recommended price per line"),
    ("flask", "108", "launch configurations scored"),
]

# (title, detail, section index) — index into the page's sections, in notebook order.
DECISIONS = [
    ("Nest plans by price tier, not carrier", "§03 · Carrier nests collapse to a flat logit", 3),
    ("Do not forecast with a flat logit", "§07 · Overstates high-margin draw by about 20 points", 7),
    ("Launch HD essentials at $52.50, no multi-line discount", "§08 · Best worst-case margin across three models", 8),
    ("Hold the fence; treat price as the open question", "§08 · Fence stable across scenarios, price $50–$55", 8),
    ("Read the rollout on plan mix, not margin", "§08 · Margin effect at the limit of detection", 8),
]

RELATED = []
