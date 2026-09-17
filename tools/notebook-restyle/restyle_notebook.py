"""Restyles an nbconvert HTML export of a portfolio notebook into the research-notebook layout.

What differs per notebook (header figures, key decisions, labels, links) lives in a config
module kept next to the notebook; the styles (notebook.css) and page markup
(notebook_template.html) beside this script are shared. Run after re-exporting a notebook
with `jupyter nbconvert --to html`:

    python3 tools/notebook-restyle/restyle_notebook.py <config.py> <export.html> <out.html>

The notebook's cells are kept as they are; only their presentation changes:

  - a section sidebar built from the notebook's h2 headings (and, optionally, its h3s)
  - a summary header with four headline figures and a notice (a disclosure or context note)
  - code cells as cards with a copy button, and outputs beneath them
  - markdown "Recommendation" bullets split into Interpretation and Decision callouts
  - with TIDY_MARKDOWN, "Purpose:" and "Design Notes:" labels styled as a lead line and a
    list label, "Observations:" lists pulled out as callouts, numbered lists split by
    two-space sub-bullets rejoined, and horizontal rules and empty code cells dropped
  - with WRAP_TEXT_OUTPUT, plain-text outputs wrap instead of scrolling sideways, for prose
    such as model responses (leave it off where outputs are aligned tables)
  - a right-hand rail with key decisions, section progress and related links
  - a "Hide code" toggle
  - with KNOWLEDGE_FILES or EXTRA_VIEWS, source files shown as their own sections: knowledge
    base files split into chunks, or a narration script split into slides with each slide's
    audio player beneath its text

The input must be a fresh nbconvert export; output this script produced is refused.
"""

import html
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent

ICONS = {
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "dollar": '<path d="M12 2v20M17 6.5c-.8-1.5-2.7-2.5-5-2.5-2.8 0-5 1.6-5 3.8 0 5.2 10 2.7 10 8.2 0 2.3-2.2 4-5 4-2.4 0-4.4-1.1-5.2-2.8"/>',
    "bars": '<path d="M5 20v-6M10 20V9M15 20v-9M20 20V5"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3M7.3 14h9.4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7.1 0l3-3a5 5 0 0 0-7.1-7.1l-1.2 1.2M14 10a5 5 0 0 0-7.1 0l-3 3a5 5 0 0 0 7.1 7.1l1.2-1.2"/>',
    "shield": '<path d="M12 2l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V5z"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    "layers": '<path d="M12 3l9 4.5-9 4.5-9-4.5z"/><path d="M3 12l9 4.5 9-4.5"/><path d="M3 16.5l9 4.5 9-4.5"/>',
    "route": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10M18 10c0 4-4 5-8 6"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    "doc": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "audio": '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
}


def icon(name, cls="icon"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


CONFIG_DIR = HERE  # set to the config's own folder, so its relative paths resolve there


def load_config(path):
    global CONFIG_DIR
    spec = importlib.util.spec_from_file_location("notebook_config", path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    CONFIG_DIR = Path(path).resolve().parent
    return config


def section_label(config, heading_text):
    for prefix, label in config.SECTION_LABELS:
        if heading_text.startswith(prefix):
            return label
    raise SystemExit(f"no sidebar label for section heading {heading_text!r}; update SECTION_LABELS")


def slug(text, used):
    """A stable anchor for a heading, since some exports carry no ids."""
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    anchor, n = base, 2
    while anchor in used:
        anchor, n = f"{base}-{n}", n + 1
    used.add(anchor)
    return anchor


def strip_number(heading_text):
    """'2.0 Part 1: A/B Test' -> 'Part 1: A/B Test'; '1 · Knowledge Base' -> 'Knowledge Base'."""
    return re.sub(r"^\d+(?:\.\d+)?\s*(?:·\s*)?", "", heading_text)


def heading_text(tag):
    return tag.get_text().replace("¶", "").strip()


def inner(tag):
    return "".join(str(child) for child in tag.children)


def label_of(p):
    """'Purpose' for a paragraph that starts with <strong>Purpose:</strong>, else None."""
    first = next((c for c in p.children if c.name is not None or c.strip()), None)
    if first is None or first.name != "strong":
        return None
    text = first.get_text(strip=True)
    return text[:-1] if text.endswith(":") else None


def recommendation_callouts(rendered):
    """Split a markdown cell whose list holds a 'Recommendation' bullet into callouts.
    Returns None when the cell has no such bullet."""
    for ul in rendered.find_all("ul"):
        items = ul.find_all("li", recursive=False)
        rec = next(
            (li for li in items if li.find("strong") and li.find("strong").get_text(strip=True).startswith("Recommendation")),
            None,
        )
        if rec is None:
            continue
        rec.find("strong").decompose()
        decision = inner(rec).strip().lstrip(":").strip()
        decision = decision[:1].upper() + decision[1:]
        others = "".join(str(li) for li in items if li is not rec)
        ul.decompose()
        lead = inner(rendered).strip()
        interp = (
            f'<div class="callout interp"><span class="callout-mark" aria-hidden="true">!</span>'
            f'<div><p class="callout-title">Interpretation</p><ul>{others}</ul></div></div>'
            if others else ""
        )
        decided = (
            f'<div class="callout decision"><span class="callout-mark ok">{icon("check")}</span>'
            f'<div><p class="callout-title">Decision</p><p>{decision}</p></div></div>'
        )
        return (f'<div class="md">{lead}</div>' if lead else "") + f'<div class="callouts">{interp}{decided}</div>'
    return None


def rejoin_lists(root):
    """Two-space sub-bullets render as <ol>, <ul>, <ol start="2">, ...: nest each <ul> in the
    item before it and continue the numbered list."""
    prev = None
    for node in list(root.children):
        if node.name is None:
            if node.strip():
                prev = None
            continue
        if prev is not None and prev.name == "ol" and node.name == "ul":
            prev.find_all("li", recursive=False)[-1].append(node.extract())
            continue
        if prev is not None and prev.name == "ol" and node.name == "ol" and node.get("start"):
            for li in node.find_all("li", recursive=False):
                prev.append(li.extract())
            node.decompose()
            continue
        prev = node


def tidy_blocks(rendered):
    """Markdown as .md blocks, with labelled paragraphs styled and Observations lists as callouts."""
    for rule in rendered.find_all("hr"):
        rule.decompose()
    # Cells written as raw HTML wrap everything in one <div>; work on its children so the
    # labelled paragraphs inside are visible to the passes below.
    children = [c for c in rendered.children if c.name is not None or c.strip()]
    if len(children) == 1 and children[0].name == "div":
        children[0].unwrap()
    rejoin_lists(rendered)
    out, pending = [], []

    def flush():
        text = "".join(pending).strip()
        if text:
            out.append(f'<div class="md">{text}</div>')
        pending.clear()

    nodes = list(rendered.children)
    i = 0
    while i < len(nodes):
        node = nodes[i]
        label = label_of(node) if node.name == "p" else None
        if label == "Observations":
            j = i + 1
            while j < len(nodes) and nodes[j].name is None:
                j += 1
            if j < len(nodes) and nodes[j].name in ("ol", "ul"):
                flush()
                out.append(
                    '<div class="callouts"><div class="callout interp"><span class="callout-mark" aria-hidden="true">i</span>'
                    f'<div><p class="callout-title">Observations</p>{nodes[j]}</div></div></div>'
                )
                i = j + 1
                continue
        if label:
            node.find("strong").decompose()
            rest = inner(node).strip()
            if rest:
                pending.append(f'<p class="lead"><span class="lead-label">{html.escape(label)}</span> {rest}</p>')
            else:
                pending.append(f'<p class="md-label">{html.escape(label)}</p>')
        else:
            pending.append(str(node))
        i += 1
    flush()
    return "".join(out)


def knowledge_file(path, spec, section):
    """Renders a knowledge base file the way the notebook reads it: metadata from the
    header, then one chunk per '## ' section. The chunk count is asserted against the
    notebook's own output so the page cannot drift from the data."""
    text = Path(path).read_text(encoding="utf-8")

    domain = re.search(r"Domain:\s*(.+)", text)
    domain = domain.group(1).strip() if domain else "Unknown"
    tags_match = re.search(r"Tags:\s*(.*?)\n\nContent Type:", text, re.DOTALL)
    tags = [t.strip() for t in tags_match.group(1).replace("\n", " ").split(",") if t.strip()] if tags_match else []
    summary = re.search(r"Document Summary:\s*\n+(.+?)\n\n", text, re.DOTALL)
    summary = " ".join(summary.group(1).split()) if summary else ""

    # The notebook's split: everything before the first "## " is metadata, never a chunk.
    parts = re.split(r"\n##\s+", text)[1:]
    expected = spec.get("expected_chunks")
    if expected is not None and len(parts) != expected:
        raise SystemExit(f"{Path(path).name}: {len(parts)} chunks, expected {expected}")

    chunks = []
    for n, part in enumerate(parts, start=1):
        lines = part.strip().split("\n")
        topic = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        content = re.sub(r"\n?-{3,}\s*$", "", content).strip()
        anchor = f'{spec["anchor"]}-{n}'
        section["subsections"].append((anchor, topic))
        chunks.append(
            f'<article class="kb-chunk" id="{html.escape(anchor, quote=True)}">'
            f'<header><span class="chunk-num">Chunk {n}/{len(parts)}</span>'
            f"<h3>{html.escape(topic)}</h3></header>"
            f"<pre>{html.escape(content)}</pre></article>"
        )

    tag_html = "".join(f"<span>{html.escape(t)}</span>" for t in tags)
    head = (
        '<div class="kb-head">'
        f'<div><b>File</b><span>{html.escape(Path(path).name)}</span></div>'
        f'<div><b>Domain</b><span>{html.escape(domain)}</span></div>'
        f'<div><b>Chunks</b><span>{len(parts)}, one per section</span></div>'
        f'<div style="grid-column: 1 / -1;"><b>Tags</b><div class="tags">{tag_html}</div></div>'
        "</div>"
    )
    note = (
        f'<p class="kb-note">{icon("info")}<span>The header above is metadata: the loader reads '
        f'Domain and Tags from it, then splits the file on each <code>##</code> heading. Every '
        f'chunk below is embedded separately, so a question retrieves the section it is about '
        f'rather than the whole document.</span></p>'
    )
    intro = f'<p class="kb-summary">{html.escape(summary)}</p>' if summary else ""
    return head + intro + note + "".join(chunks)


def narration_slides(path, expected=None):
    """Splits a narration script the way the TTS notebook reads it: '# SLIDE n', an
    '## ESTIMATED TIME:' line, blank-line-separated paragraphs, and a closing '---'."""
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^# SLIDE (\d+)[ \t]*$", text, flags=re.M)
    slides = []
    for number, body in zip(parts[1::2], parts[2::2]):
        estimate = re.search(r"^## ESTIMATED TIME:\s*(.+?)\s*$", body, flags=re.M)
        body = re.sub(r"\n-{3,}\s*$", "", body.rstrip()).rstrip()
        narration = re.sub(r"^## .*$", "", body, flags=re.M).strip()
        if not narration:
            raise SystemExit(f"{Path(path).name}: slide {number} has no narration")
        slides.append({
            "number": int(number),
            "estimate": estimate.group(1) if estimate else "",
            "raw": f"# SLIDE {number}{body}",
        })
    if not slides:
        raise SystemExit(f"{Path(path).name}: no '# SLIDE n' headers")
    if expected is not None and len(slides) != expected:
        raise SystemExit(f"{Path(path).name}: {len(slides)} slides, expected {expected}")
    return slides


def estimate_seconds(estimate):
    minutes = re.search(r"(\d+)\s*minute", estimate)
    seconds = re.search(r"(\d+)\s*second", estimate)
    return (int(minutes.group(1)) * 60 if minutes else 0) + (int(seconds.group(1)) if seconds else 0)


def clock(seconds):
    seconds = round(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


AUDIO_STYLE = (
    "<style>"
    ".kb-chunk .audio-body{padding:.8rem 1rem;border-top:1px solid var(--line)}"
    ".kb-chunk audio{display:block;width:100%}"
    ".kb-chunk details{border-top:1px solid var(--line)}"
    ".kb-chunk summary{padding:.55rem 1rem;cursor:pointer;font-size:.8rem;color:var(--muted)}"
    ".kb-chunk details pre{border-top:1px solid var(--line)}"
    "</style>"
)
AUDIO_SCRIPT = (
    "<script>document.addEventListener('play',function(e){"
    "if(e.target.tagName!=='AUDIO')return;"
    "document.querySelectorAll('audio').forEach(function(a){if(a!==e.target)a.pause();});"
    "},true);</script>"
)


def m4a_seconds(path):
    """The clip's duration as reported by macOS afinfo."""
    afinfo = shutil.which("afinfo")
    if afinfo is None:
        raise SystemExit("afinfo was not found; reading audio durations requires macOS")
    result = subprocess.run([afinfo, str(path)], capture_output=True, text=True)
    match = re.search(r"estimated duration:\s*([\d.]+)", result.stdout)
    if result.returncode != 0 or not match:
        raise SystemExit(f"could not read the duration of {path}")
    return float(match.group(1))


def narration_view(spec, section):
    """The narration script, one block per slide with its headers, and beneath each slide's
    text the published clip and the LLM-prepared text that was actually spoken. Durations
    are read from the clips, so the page cannot drift from them."""
    script = CONFIG_DIR / spec["script"]
    slides = narration_slides(script, spec.get("expected_slides"))
    audio_dir = CONFIG_DIR / spec["audio_dir"]
    lengths, blocks = [], []
    for s in slides:
        n = s["number"]
        clip = audio_dir / f"slide_{n:02d}.m4a"
        if not clip.exists():
            raise SystemExit(f"missing audio clip {clip}")
        seconds = m4a_seconds(clip)
        lengths.append(seconds)
        spoken = audio_dir / f"slide_{n:02d}.txt"
        spoken_html = (
            f'<details><summary>Spoken text, as prepared by the LLM</summary>'
            f'<pre>{html.escape(spoken.read_text(encoding="utf-8").strip())}</pre></details>'
            if spoken.exists() else ""
        )
        anchor = f'{spec["anchor"]}-{n}'
        section["subsections"].append((anchor, f"Slide {n}"))
        src = spec["audio_url"].format(n=n)
        blocks.append(
            f'<article class="kb-chunk" id="{html.escape(anchor, quote=True)}">'
            f'<header><span class="chunk-num">Slide {n}</span>'
            f'<h3>Estimated {html.escape(s["estimate"])} &middot; audio {clock(seconds)}</h3></header>'
            f'<pre>{html.escape(s["raw"])}</pre>'
            f'<div class="audio-body"><audio controls preload="none" src="{html.escape(src, quote=True)}">'
            f'<a href="{html.escape(src, quote=True)}">Download slide {n} audio</a></audio></div>'
            f"{spoken_html}</article>"
        )
    estimated = sum(estimate_seconds(s["estimate"]) for s in slides)
    head = (
        '<div class="kb-head">'
        f'<div><b>Script</b><span>{html.escape(script.name)}</span></div>'
        f'<div><b>Voice</b><span>{html.escape(spec["voice"])}</span></div>'
        f'<div><b>Format</b><span>{html.escape(spec["format"])}</span></div>'
        f'<div><b>Slides</b><span>{len(slides)}</span></div>'
        f'<div><b>Estimated total</b><span>{clock(estimated)}</span></div>'
        f'<div><b>Audio total</b><span>{clock(sum(lengths))}</span></div>'
        "</div>"
    )
    note = (
        f'<p class="kb-note">{icon("info")}<span>Each slide shows the script as written: a '
        f'<code># SLIDE</code> header and an <code>## ESTIMATED TIME</code> line, which the notebook '
        f'reads as metadata and never speaks, then the narration. The player beneath plays the clip '
        f'published with the presentation, and the spoken text under it is the LLM-prepared version, '
        f'so small wording differences are expected.</span></p>'
    )
    intro = f'<p class="kb-summary">{html.escape(spec["summary"])}</p>' if spec.get("summary") else ""
    return AUDIO_STYLE + head + intro + note + "".join(blocks) + AUDIO_SCRIPT


VIEW_RENDERERS = {"narration": narration_view}


def code_cell(cell, skip_empty=False, wrap_text=False):
    prompt = cell.select_one(".jp-InputPrompt").get_text(strip=True)
    text_class = "out-text wrap" if wrap_text else "out-text"
    pre = cell.select_one(".highlight pre")
    if skip_empty and (pre is None or not pre.get_text().strip()):
        return ""
    parts = [
        '<div class="nb-cell code-cell">'
        f'<div class="prompt in">{html.escape(prompt)}</div>'
        '<div class="code-card"><button type="button" class="copy" aria-label="Copy code">Copy</button>'
        f"{pre}</div></div>"
    ]
    for child in cell.select(".jp-OutputArea-child"):
        out_prompt = child.select_one(".jp-OutputPrompt")
        label = out_prompt.get_text(strip=True) if out_prompt else ""
        output = child.select_one(".jp-OutputArea-output")
        if output is None:
            continue
        classes = output.get("class", [])
        if "jp-RenderedImage" in classes:
            body = f'<div class="out-image">{inner(output)}</div>'
        elif output.get("data-mime-type") == "text/plain" or "jp-RenderedText" in classes:
            body = f'<div class="{text_class}">{inner(output)}</div>'
        else:
            body = f'<div class="out-html">{inner(output)}</div>'
        parts.append(
            '<div class="nb-cell out-cell">'
            f'<div class="prompt out">{html.escape(label)}</div>{body}</div>'
        )
    return "".join(parts)


def build(src_html, config):
    soup = BeautifulSoup(src_html, "html.parser")
    if soup.find(attrs={"data-restyled": "notebook"}):
        raise SystemExit("input is already restyled; pass a fresh nbconvert export")
    cells = soup.select("div.jp-Cell")
    assert len(cells) > 2, "expected an nbconvert export with notebook cells"
    tidy = getattr(config, "TIDY_MARKDOWN", False)
    numbered = getattr(config, "NUMBER_FROM_HEADINGS", False)

    # Title cell: h1, a subtitle paragraph, and (for some notebooks) the notice paragraph.
    title_cell = cells[0].select_one(".jp-RenderedMarkdown")
    h1 = title_cell.find("h1")
    title = heading_text(h1)
    subtitle_p = title_cell.find("p")
    if label_of(subtitle_p):
        subtitle_p.find("strong").decompose()
    subtitle = subtitle_p.get_text(strip=True)

    notice = config.NOTICE
    notice_class = "disclosure" + (f' {notice["variant"]}' if notice.get("variant") else "")
    leftover = None
    if notice["source"] == "next-cell-list":
        items = "".join(str(li) for li in cells[1].select_one(".jp-RenderedMarkdown").find_all("li"))
        assert items, "expected the notice bullets in the second cell"
        notice_body = f"<ul>{items}</ul>"
        first_body_cell = 2
    elif notice["source"] in ("title-paragraph", "next-cell-paragraph"):
        # The labelled paragraph sits either in the title cell or in the one after it.
        source_cell = title_cell if notice["source"] == "title-paragraph" else cells[1].select_one(".jp-RenderedMarkdown")
        para = next(
            (p for p in source_cell.find_all("p")
             if p.find("strong") and p.find("strong").get_text(strip=True).startswith(notice["label"])),
            None,
        )
        assert para is not None, f"expected a paragraph labelled {notice['label']!r} in the title cell"
        para.find("strong").decompose()
        notice_body = f"<p>{inner(para).strip()}</p>"
        para.decompose()
        if notice["source"] == "title-paragraph":
            h1.decompose()
            subtitle_p.decompose()
            leftover = title_cell
            first_body_cell = 1
        else:
            # The title cell holds only the header block; the rest of the notice cell
            # (design notes and the like) still belongs in the overview.
            leftover = source_cell
            first_body_cell = 2
    else:
        raise SystemExit(f"unknown NOTICE source {notice['source']!r}")
    notice_html = f'<div class="{notice_class}">{icon(notice["icon"])}<div><b>{html.escape(notice["title"])}</b>{notice_body}</div></div>'

    body, sections, pending = [], [], []
    # Some exports carry no heading ids; anchors are generated and kept unique.
    used_anchors = set()
    section_tag = getattr(config, "SECTION_LEVEL", "h2")
    sub_tag = "h2" if section_tag == "h1" else "h3"

    def open_section(anchor, label, number, heading_html):
        if sections:
            body.append("</section>")
        sections.append({"anchor": anchor, "label": label, "number": number, "subsections": []})
        body.append(
            f'<section class="nb-section" id="{html.escape(anchor, quote=True)}" data-section="{len(sections)}">'
            f'<h2 class="section-head"><span class="section-num">{number}</span>{heading_html}</h2>'
        )

    def open_overview():
        # Content ahead of the first h2 becomes an Overview section.
        if pending and not sections:
            label = config.OVERVIEW_LABEL
            open_section("overview", label, "00" if numbered else "01", html.escape(label))
            body.extend(pending)
            pending.clear()

    if leftover is not None:
        blocks = tidy_blocks(leftover) if tidy else inner(leftover).strip()
        if blocks:
            pending.append(blocks if tidy else f'<div class="md">{blocks}</div>')

    for cell in cells[first_body_cell:]:
        target = body if sections else pending
        if "jp-CodeCell" in cell.get("class", []):
            html_cell = code_cell(cell, skip_empty=tidy, wrap_text=getattr(config, "WRAP_TEXT_OUTPUT", False))
            if html_cell:
                target.append(html_cell)
            continue
        rendered = cell.select_one(".jp-RenderedMarkdown")
        head = rendered.find(section_tag)
        # A closing cell with no section heading of its own still opens its own section.
        closing_cfg = getattr(config, "CLOSING_SECTION", None)
        if head is None and closing_cfg and sections:
            first = rendered.find(["h1", "h2", "h3", "h4"])
            if first is not None and heading_text(first).startswith(closing_cfg["starts_with"]):
                open_section(
                    slug(closing_cfg["label"], used_anchors),
                    closing_cfg["label"],
                    closing_cfg.get("number", f"{len(sections) + 1:02d}"),
                    html.escape(closing_cfg["label"]),
                )
                target = body
        if head is not None:
            open_overview()
            text = heading_text(head)
            if numbered:
                match = re.match(r"\d+", text)
                number = f"{int(match.group()):02d}" if match else "00"
            else:
                number = f"{len(sections) + 1:02d}"
            anchor = head.get("id") or slug(text, used_anchors)
            head.decompose()
            open_section(anchor, section_label(config, text), number, html.escape(strip_number(text)))
            target = body
        if sections:
            for sub in rendered.find_all(sub_tag):
                sub_anchor = sub.get("id") or slug(heading_text(sub), used_anchors)
                sub["id"] = sub_anchor
                sections[-1]["subsections"].append((sub_anchor, heading_text(sub)))
        if head is not None and not tidy:
            rest = inner(rendered).strip()
            if rest:
                body.append(f'<div class="md">{rest}</div>')
            continue
        callouts = recommendation_callouts(rendered)
        if callouts is None:
            callouts = tidy_blocks(rendered) if tidy else f'<div class="md">{inner(rendered)}</div>'
        if callouts:
            target.append(callouts)
    open_overview()

    # Source files the notebook reads, each shown as its own section.
    for spec in getattr(config, "KNOWLEDGE_FILES", []):
        body.append("</section>")
        sections.append({
            "anchor": spec["anchor"],
            "label": spec["label"],
            "number": spec.get("number", ""),
            "subsections": [],
        })
        body.append(
            f'<section class="nb-section" id="{html.escape(spec["anchor"], quote=True)}" '
            f'data-section="{len(sections)}">'
            f'<h2 class="section-head">{html.escape(spec["label"])}</h2>'
        )
        body.append(knowledge_file(CONFIG_DIR / spec["path"], spec, sections[-1]))

    # Other source views: a narration script, or the audio produced from it.
    for spec in getattr(config, "EXTRA_VIEWS", []):
        body.append("</section>")
        sections.append({
            "anchor": spec["anchor"],
            "label": spec["label"],
            "number": spec.get("number", ""),
            "subsections": [],
        })
        body.append(
            f'<section class="nb-section" id="{html.escape(spec["anchor"], quote=True)}" '
            f'data-section="{len(sections)}">'
            f'<h2 class="section-head">{html.escape(spec["label"])}</h2>'
        )
        if spec["type"] not in VIEW_RENDERERS:
            raise SystemExit(f"unknown EXTRA_VIEWS type {spec['type']!r}")
        body.append(VIEW_RENDERERS[spec["type"]](spec, sections[-1]))

    # With a navigator, each section ends with a way into the next one.
    navigator = bool(getattr(config, "TABS", None)) or getattr(config, "SECTION_LEVEL", "h2") == "h1"
    if navigator and sections:
        closing = []
        for i, s in enumerate(sections):
            prev_btn = (
                f'<button type="button" data-goto="{i - 1}">&larr; {html.escape(sections[i - 1]["label"])}</button>'
                if i else '<button type="button" disabled>&larr; Previous</button>'
            )
            if i + 1 < len(sections):
                nxt = sections[i + 1]
                next_btn = (
                    '<span class="next-label">Next</span>'
                    f'<button type="button" class="next" data-goto="{i + 1}">{html.escape(nxt["label"])} &rarr;</button>'
                )
            else:
                next_btn = '<button type="button" disabled>Next &rarr;</button>'
            closing.append(f'<div class="section-nav">{prev_btn}{next_btn}</div>')
        # Insert each section's navigation just before the section closes.
        rebuilt, n = [], 0
        for piece in body:
            if piece == "</section>":
                rebuilt.append(closing[n])
                n += 1
            rebuilt.append(piece)
        body = rebuilt
        body.append(closing[n] if n < len(closing) else "")
    body.append("</section>")

    stats = "".join(
        f'<div class="stat">{icon(name)}<div><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div></div>'
        for name, value, label in config.STATS
    )
    show_subsections = getattr(config, "TOC_SUBSECTIONS", False)
    toc = "".join(
        f'<li><a href="#{html.escape(s["anchor"], quote=True)}" data-toc="{i + 1}"><span>{s["number"]}</span>{html.escape(s["label"])}</a>'
        + (
            '<ol class="toc-sub">'
            + "".join(f'<li><a href="#{html.escape(a, quote=True)}">{html.escape(t)}</a></li>' for a, t in s["subsections"])
            + "</ol>"
            if show_subsections and s["subsections"] else ""
        )
        + "</li>"
        for i, s in enumerate(sections)
    )
    decisions = "".join(
        f'<li><a href="#{html.escape(sections[idx]["anchor"], quote=True)}"><span class="decision-num">{i + 1}</span>'
        f'<span><b>{html.escape(t)}</b><small>{html.escape(d)}</small></span></a></li>'
        for i, (t, d, idx) in enumerate(config.DECISIONS)
    )
    progress = "".join(
        f'<li data-progress="{i + 1}"><span class="progress-mark">{icon("check")}</span>{html.escape(s["label"])}</li>'
        for i, s in enumerate(sections)
    )
    related = "".join(
        f'<li><a href="{href}" target="_blank" rel="noopener">{icon("link")}{html.escape(name)}</a></li>'
        for name, href in config.RELATED
    )
    crumbs = '<span aria-hidden="true">/</span>'.join(
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' if href else f"<b>{html.escape(label)}</b>"
        for label, href in config.CRUMBS
    )

    tabs = ""
    if navigator:
        # A tab owns one section by default; TABS lets a tab own a run of them, so a
        # whole notebook can sit behind one tab beside its source files.
        groups = getattr(config, "TABS", None) or [
            {"label": s["label"], "number": s["number"], "sections": [i]}
            for i, s in enumerate(sections)
        ]
        buttons = []
        for t, group in enumerate(groups):
            caption = (
                f'<b>{html.escape(group["number"])}</b>' if group.get("number")
                else f'{icon(group["icon"], cls="icon tab-icon")}' if group.get("icon") else ""
            )
            buttons.append(
                f'<button type="button" class="nav-tab{" is-file" if group.get("icon") else ""}" '
                f'data-goto="{t}" data-sections="{",".join(str(i) for i in group["sections"])}" '
                f'aria-current="false">{caption}<span>{html.escape(group["label"])}</span></button>'
            )
        tabs = '<nav class="nb-nav" aria-label="Sections">' + "".join(buttons) + "</nav>"

    css = (HERE / "notebook.css").read_text()
    template = (HERE / "notebook_template.html").read_text()
    replacements = {
        "{{NAVIGATOR}}": tabs,
        "{{TITLE}}": html.escape(title),
        "{{SUBTITLE}}": html.escape(subtitle),
        "{{DESCRIPTION}}": html.escape(config.DESCRIPTION, quote=True),
        "{{CSS}}": css,
        "{{CRUMBS}}": crumbs,
        "{{BACK_HREF}}": html.escape(config.BACK[1], quote=True),
        "{{BACK_LABEL}}": html.escape(config.BACK[0]),
        "{{KERNEL}}": html.escape(config.KERNEL),
        "{{EYEBROW}}": config.EYEBROW,
        "{{STATS}}": stats,
        "{{NOTICE}}": notice_html,
        "{{TOC}}": toc,
        "{{BODY}}": "\n".join(body),
        "{{DECISIONS}}": decisions,
        "{{PROGRESS}}": progress,
        "{{RELATED}}": related,
    }
    page = template
    for key, value in replacements.items():
        assert key in page, f"template is missing {key}"
        page = page.replace(key, value)
    return page


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    config, src, out = load_config(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.write_text(build(src.read_text(encoding="utf-8"), config), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
