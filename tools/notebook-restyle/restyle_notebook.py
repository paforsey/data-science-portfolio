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

The input must be a fresh nbconvert export; output this script produced is refused.
"""

import html
import importlib.util
import re
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
}


def icon(name, cls="icon"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def load_config(path):
    spec = importlib.util.spec_from_file_location("notebook_config", path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def section_label(config, heading_text):
    for prefix, label in config.SECTION_LABELS:
        if heading_text.startswith(prefix):
            return label
    raise SystemExit(f"no sidebar label for section heading {heading_text!r}; update SECTION_LABELS")


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
    elif notice["source"] == "title-paragraph":
        para = next(
            (p for p in title_cell.find_all("p", recursive=False)
             if p.find("strong") and p.find("strong").get_text(strip=True).startswith(notice["label"])),
            None,
        )
        assert para is not None, f"expected a paragraph labelled {notice['label']!r} in the title cell"
        para.find("strong").decompose()
        notice_body = f"<p>{inner(para).strip()}</p>"
        for tag in (para, h1, subtitle_p):
            tag.decompose()
        leftover = title_cell
        first_body_cell = 1
    else:
        raise SystemExit(f"unknown NOTICE source {notice['source']!r}")
    notice_html = f'<div class="{notice_class}">{icon(notice["icon"])}<div><b>{html.escape(notice["title"])}</b>{notice_body}</div></div>'

    body, sections, pending = [], [], []

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
        h2 = rendered.find("h2")
        if h2 is not None:
            open_overview()
            text = heading_text(h2)
            if numbered:
                match = re.match(r"\d+", text)
                number = f"{int(match.group()):02d}" if match else "00"
            else:
                number = f"{len(sections) + 1:02d}"
            anchor = h2.get("id")
            h2.decompose()
            open_section(anchor, section_label(config, text), number, html.escape(strip_number(text)))
            target = body
        if sections:
            for h3 in rendered.find_all("h3"):
                sections[-1]["subsections"].append((h3.get("id"), heading_text(h3)))
        if h2 is not None and not tidy:
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

    css = (HERE / "notebook.css").read_text()
    template = (HERE / "notebook_template.html").read_text()
    replacements = {
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
