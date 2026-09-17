"""Research-notebook page settings for the presentation narration TTS notebook.

The notebook lives in the site repo, beside the scripts it processes
(datafxlab/paforsey/tts/tts_research_01_baseline.ipynb). Build from selected-work after
re-exporting it:

    jupyter nbconvert --to html ../../datafxlab/paforsey/tts/tts_research_01_baseline.ipynb \
        --output-dir . --output presentation_narration_tts
    python3 ../tools/notebook-restyle/restyle_notebook.py web/presentation_narration_config.py \
        presentation_narration_tts.html web/presentation_narration_tts.html

The Script and Audio tabs are rendered from the script file and the published clips, so
rebuild after either changes. Audio durations are read with macOS afinfo.
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
BACK = ("Back to selected work", "/#selected-work")
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
# 0 Overview, 1 §1, 2 §2, 3 Script, 4 Audio.
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

# The narration script and the audio produced from it, each shown as its own view.
EXTRA_VIEWS = [
    {
        "type": "script",
        "label": "Narration Script",
        "anchor": "script",
        "path": "../../../datafxlab/paforsey/tts/international_roaming_script.txt",
        "expected_slides": 9,
        "summary": (
            "The International Roaming Pricing executive presentation script, exactly as the "
            "notebook reads it."
        ),
    },
    {
        "type": "audio",
        "label": "Narration Audio",
        "anchor": "audio",
        "script": "../../../datafxlab/paforsey/tts/international_roaming_script.txt",
        "audio_dir": "../../../datafxlab/paforsey/public/case-studies/international-roaming/audio",
        "audio_url": "/case-studies/international-roaming/audio/slide_{n:02d}.m4a",
        "expected_slides": 9,
        "voice": "am_michael (Kokoro-82M)",
        "format": "AAC, 64 kbps, .m4a",
        "summary": "The nine clips the executive presentation plays, one per slide.",
    },
]

# Three views: the notebook, the script, and the audio.
TABS = [
    {"label": "Notebook", "number": "01", "sections": [0, 1, 2]},
    {"label": "Narration Script", "icon": "doc", "sections": [3]},
    {"label": "Narration Audio", "icon": "audio", "sections": [4]},
]
