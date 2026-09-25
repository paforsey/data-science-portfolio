"""Research-notebook page settings for the presentation narration TTS notebook.

The notebook lives in the site repo, beside the scripts it processes
(datafxlab/paforsey/tts/tts_research_01_baseline.ipynb). Build from selected-work after
re-exporting it:

    jupyter nbconvert --to html ../../datafxlab/paforsey/tts/tts_research_01_baseline.ipynb \
        --output-dir . --output presentation_narration_tts
    python3 ../tools/notebook-restyle/restyle_notebook.py web/presentation_narration_config.py \
        presentation_narration_tts.html web/presentation_narration_tts.html

The Narration Script & Audio tab is rendered from the script file and the published clips,
so rebuild after either changes. Audio durations are read with macOS afinfo.
"""

DESCRIPTION = (
    "Research notebook that turns an executive presentation script into one narrated "
    "audio file per slide, using a local LLM for text preparation and Kokoro for speech."
)
EYEBROW = "AI Narration &middot; Text-to-Speech"
CRUMBS = [
    ("Portfolio", "/"),
    ("Selected Work", "/#selected-work"),
    ("Research Notebook", None),
]
BACK = None
KERNEL = "Python (TTS Research) · 3.11"  # the notebook's kernelspec display name and language version

# The "Context, for anyone starting here." paragraph becomes the notice.
NOTICE = {"source": "next-cell-paragraph", "label": "Context", "title": "Context", "icon": "info", "variant": "info"}

TIDY_MARKDOWN = True
WRAP_TEXT_OUTPUT = False  # the run output is an aligned table
TOC_SUBSECTIONS = True
NUMBER_FROM_HEADINGS = True  # keep §1 and §2 matching the notebook's own cross-references
OVERVIEW_LABEL = "Overview"

# Sidebar labels, keyed by the start of each h2 heading's text.
SECTION_LABELS = [
    ("1 ·", "LLM Text Preparation"),
    ("2 ·", "Script to Audio Files"),
]

# (icon, value, label) quoted from the notebook's design notes and observations.
STATS = [
    ("doc", "9", "slides narrated from one script"),
    ("clock", "10.0", "minutes of narration"),
    ("layers", "2", "local models: Qwen3 and Kokoro-82M"),
    ("audio", "~85%", "smaller as 64 kbps AAC than WAV"),
]

# (title, detail, section index) — index into the page's sections:
# 0 Overview, 1 §1, 2 §2, 3 Narration Script & Audio.
DECISIONS = [
    ("Keep the script as the single source of narration", "Overview · Headers and timing are never spoken", 0),
    ("Prepare text with a local LLM before synthesis", "§1 · Facts, names and negations preserved", 1),
    ("Send one paragraph per LLM call", "§2.3 · Stays inside the output limit", 2),
    ("Publish 64 kbps AAC instead of WAV", "§2.4 · About 85% smaller", 2),
]

RELATED = [
    ("International roaming executive presentation", "/case-studies/international-roaming/executive-presentation.html"),
    ("All selected work", "/#selected-work"),
    ("Featured case studies", "/#case-studies"),
]

# The narration script with each slide's audio beneath its text, shown as one view.
EXTRA_VIEWS = [
    {
        "type": "narration",
        "label": "Narration Script & Audio",
        "anchor": "narration",
        "script": "../../../datafxlab/paforsey/tts/international_roaming_script.txt",
        "audio_dir": "../../../datafxlab/paforsey/public/case-studies/international-roaming/audio",
        "audio_url": "/case-studies/international-roaming/audio/slide_{n:02d}.m4a",
        "expected_slides": 9,
        "voice": "am_michael (Kokoro-82M)",
        "format": "AAC, 64 kbps, .m4a",
        "summary": (
            "The International Roaming Pricing executive presentation script, exactly as the "
            "notebook reads it, with the clip the presentation plays for each slide."
        ),
    },
]

# Two views: the notebook, and the script with its audio.
TABS = [
    {"label": "Notebook", "number": "01", "sections": [0, 1, 2]},
    {"label": "Narration Script & Audio", "icon": "audio", "sections": [3]},
]
