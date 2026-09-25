"""Research-notebook page settings for the four international roaming notebooks.

The study is split across 01_state_model.ipynb through 04_segmentation.ipynb, merged into one
page (the data generator, data/00, is not part of the merge). Execute all four notebooks, then
build from case-studies/international-roaming:

    python3 ../../tools/notebook-restyle/merge_notebooks.py international_roaming.merged.ipynb \
        01_state_model.ipynb 02_magnitude_model.ipynb 03_simulation.ipynb 04_segmentation.ipynb
    jupyter nbconvert --to html international_roaming.merged.ipynb --output international_roaming.export
    python3 ../../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
        international_roaming.export.html web/international_roaming.html

The merged notebook nests four models as h1 with their steps as h2, so SECTION_LEVEL puts the
models in the navigator and their steps in the contents. The headline figures are quoted
from the study; update them if a re-run changes the results.
"""

DESCRIPTION = (
    "Research notebook for the international roaming price decision: coverage-state and "
    "magnitude models, a 12-month simulation, and segmentation."
)
EYEBROW = "ML Research &middot; International Roaming Pricing"
CRUMBS = [
    ("Portfolio", "/"),
    ("International Roaming", "data-science-lifecycle.html"),
    ("Research Notebook", None),
]
BACK = ("Back to case study", "data-science-lifecycle.html")
KERNEL = "Python 3 (ipykernel) · 3.9"  # the notebook's kernelspec display name and language version

# The second cell's bullets are the disclosure.
NOTICE = {"source": "next-cell-list", "title": "Disclosure", "icon": "shield"}

SECTION_LEVEL = "h1"  # models are h1; their steps are h2
TIDY_MARKDOWN = True  # Purpose / Design Notes / Observations blocks
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep 01-04 matching the notebook's own model numbers
OVERVIEW_LABEL = "Overview"
# The closing cell carries no h1, so it is given its own section.
CLOSING_SECTION = {"starts_with": "The Complete Study Chain", "label": "Summary", "number": "05"}

# Sidebar labels and navigator captions, keyed by the start of each h1 heading.
SECTION_LABELS = [
    ("Overview", "Overview"),
    ("01", "The State Model"),
    ("02", "The Magnitude Model"),
    ("03", "The 12-Month Simulation"),
    ("04", "Segmentation and Handoff"),
    ("Summary", "Summary"),
]

# (icon, value, label) quoted from the study.
STATS = [
    ("dollar", "$100M", "revenue objective"),
    ("bars", "+20%", "best evaluated price"),
    ("dollar", "+$104M", "modeled annual revenue"),
    ("layers", "4", "models behind one price"),
]

# (title, detail, section index) — index into the page's sections, in notebook order.
DECISIONS = [
    ("Recommend a 20% increase", "§03 · Best price within the evaluated range", 3),
    ("Read it from the as-fitted model", "§03 · No sensitivity adjustment applied", 3),
    ("Keep one portfolio-wide price", "§04 · Segment pricing added little", 4),
    ("Report outcomes as ranges", "§03 · P5 to P95, never a single number", 3),
]

RELATED = [
    ("Analytical plan", "analytical-plan.html"),
    ("Case study", "case-study.html"),
    ("Scenario tool", "scenario-analysis/scenario-analysis.html"),
    ("Executive presentation", "executive-presentation.html"),
]
