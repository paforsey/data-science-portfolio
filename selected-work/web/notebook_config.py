"""Research-notebook page settings for rag-enhanced_coaching.ipynb.

Build from selected-work after re-exporting the notebook:

    jupyter nbconvert --to html rag-enhanced_coaching.ipynb
    python3 ../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
        rag-enhanced_coaching.html web/rag-enhanced_coaching.html

The headline figures and key decisions are quoted from the notebook's design notes and
outputs; update them if the knowledge base or pipeline changes.
"""

DESCRIPTION = (
    "Research notebook for a retrieval-augmented financial coach: a Chroma knowledge base, "
    "question classification and profile-aware responses."
)
EYEBROW = "AI Financial Coaching &middot; Retrieval-Augmented Generation"
CRUMBS = [
    ("Portfolio", "/"),
    ("Selected Work", "/#selected-work"),
    ("Research Notebook", None),
]
BACK = ("Back to selected work", "/#selected-work")
KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# The title cell's "Context, for anyone starting here." paragraph becomes the notice.
# The header block is its own cell now; the Context paragraph opens the cell after it.
NOTICE = {"source": "next-cell-paragraph", "label": "Context", "title": "Context", "icon": "info", "variant": "info"}

TIDY_MARKDOWN = True
WRAP_TEXT_OUTPUT = True  # the coach's responses print as prose, one paragraph per line
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep §1 and §2 matching the notebook's own cross-references
OVERVIEW_LABEL = "Overview"

# Sidebar labels, keyed by the start of each h2 heading's text.
SECTION_LABELS = [
    ("1 ·", "Knowledge Base & Vector Store"),
    ("2 ·", "RAG-Enhanced Coaching"),
]

# (icon, value, label) quoted from the notebook's design notes and outputs.
STATS = [
    ("book", "2", "knowledge domains seeded"),
    ("layers", "24", "chunks, one per subsection"),
    ("route", "4", "question paths after classification"),
    ("chat", "250", "word cap per response"),
]

# (title, detail, section index) — index into the page's sections: 0 Overview, 1 §1, 2 §2.
DECISIONS = [
    ("Use one Chroma collection for every topic", "§1 · Retrieval stays cross-domain", 1),
    ("Chunk by subsection, tagged by source file", "§1 · 24 chunks from 2 files", 1),
    ("Classify every question before answering", "§2 · Four paths, retrieval to decline", 2),
    ("Let knowledge-base context outrank the model", "§2.2 · The prompt forbids contradicting it", 2),
]

RELATED = [
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]

# The knowledge base files the notebook loads, shown as their own views so a reader can
# see how each file is structured. Rendered from the files themselves, split the same way
# load_knowledge_document splits them: metadata from the header, one chunk per "## " section.
KNOWLEDGE_FILES = [
    {
        "path": "../knowledge_base/01_emergency_fund.txt",
        "label": "Emergency Fund",
        "anchor": "file-emergency-fund",
        "expected_chunks": 10,
    },
    {
        "path": "../knowledge_base/02_debt_reduction.txt",
        "label": "Debt Reduction",
        "anchor": "file-debt-reduction",
        "expected_chunks": 14,
    },
]

# Three views: the notebook, then one per knowledge base file.
TABS = [
    {"label": "Notebook", "number": "01", "sections": [0, 1, 2]},
    {"label": "Emergency Fund", "icon": "doc", "sections": [3]},
    {"label": "Debt Reduction", "icon": "doc", "sections": [4]},
]
